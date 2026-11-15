"""Database connection pool and schema initialisation (asyncpg + pgvector)."""

from __future__ import annotations

import logging
from typing import Optional

import asyncpg

from app.config import settings

logger = logging.getLogger(__name__)

_pool: Optional[asyncpg.Pool] = None


async def get_pool() -> asyncpg.Pool:
    """Return the global connection pool, creating it on first call."""
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            dsn=settings.DATABASE_URL,
            min_size=2,
            max_size=10,
            command_timeout=60,
        )
        logger.info("Database connection pool created")
    return _pool


async def close_pool() -> None:
    """Gracefully close the pool."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
        logger.info("Database connection pool closed")


async def init_db() -> None:
    """Create the pgvector extension and all required tables if they don't exist."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Enable pgvector
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector;")

        # Documents table – one row per source file
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id          SERIAL PRIMARY KEY,
                name        TEXT NOT NULL UNIQUE,
                doc_type    TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
            );
        """)

        # Chunks table – embeddings live here
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS chunks (
                id          SERIAL PRIMARY KEY,
                document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                content     TEXT NOT NULL,
                section     TEXT,
                metadata    JSONB NOT NULL DEFAULT '{}',
                doc_type    TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                embedding   vector(384),
                tsv         tsvector GENERATED ALWAYS AS (to_tsvector('english', content)) STORED,
                created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
            );
        """)

        # HNSW index for fast approximate nearest-neighbour search
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_chunks_embedding_hnsw
            ON chunks USING hnsw (embedding vector_cosine_ops);
        """)

        # GIN index for full-text search
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_chunks_tsv
            ON chunks USING gin (tsv);
        """)

        # Chat sessions
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS chat_sessions (
                id          TEXT PRIMARY KEY,
                created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
            );
        """)

        # Messages
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id          SERIAL PRIMARY KEY,
                session_id  TEXT NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
                role        TEXT NOT NULL,
                content     TEXT NOT NULL,
                sources     JSONB,
                created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
            );
        """)

        # Feedback
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS feedback (
                id          SERIAL PRIMARY KEY,
                message_id  INTEGER NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
                rating      INTEGER NOT NULL,
                comment     TEXT,
                created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
            );
        """)

    logger.info("Database schema initialised")
