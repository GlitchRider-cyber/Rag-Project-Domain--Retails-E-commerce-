#!/usr/bin/env python3
"""
Aurelia & Co. — Ingestion Runner CLI

Loads raw product catalog, markdown policies, and FAQs,
generates embeddings, and upserts everything into PostgreSQL + pgvector.

Usage:
    # From project root:
    python -m backend.app.ingest.runner

    # Or with custom data directory:
    python -m backend.app.ingest.runner --data-dir data

    # Or from inside backend folder:
    python -m app.ingest.runner
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Ensure backend directory and root directory are in sys.path BEFORE any app imports
_this_dir = Path(__file__).resolve().parent
_app_dir = _this_dir.parent
_backend_dir = _app_dir.parent
_root_dir = _backend_dir.parent

for _p in (str(_backend_dir), str(_root_dir)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Pre-flight dependency check with friendly message
_MISSING_DEPS = []
for _mod, _pkg in [
    ("asyncpg", "asyncpg"),
    ("pgvector", "pgvector"),
    ("sentence_transformers", "sentence-transformers"),
    ("pydantic_settings", "pydantic-settings"),
]:
    try:
        __import__(_mod)
    except ImportError:
        _MISSING_DEPS.append(_pkg)

if _MISSING_DEPS:
    print("\n" + "=" * 65, file=sys.stderr)
    print("❌ ERROR: Missing required Python dependencies:", file=sys.stderr)
    for _d in _MISSING_DEPS:
        print(f"   • {_d}", file=sys.stderr)
    print("\nPlease install all dependencies from requirements.txt:", file=sys.stderr)
    print("   pip install -r backend/requirements.txt", file=sys.stderr)
    print("=" * 65 + "\n", file=sys.stderr)
    sys.exit(1)

from app.config import settings
from app.db import init_db, close_pool
from app.ingest.pipeline import run_ingestion

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("ingest-runner")


async def execute_ingestion(data_dir: str) -> None:
    """Run full schema setup, embedding, and ingestion."""
    print("=" * 65)
    print("  Aurelia & Co. — Brand RAG Knowledge Base Ingestion")
    print("=" * 65)
    db_display = settings.DATABASE_URL.split("@")[-1] if "@" in settings.DATABASE_URL else settings.DATABASE_URL
    print(f"Target Database : {db_display}")
    print(f"Embedding Model : sentence-transformers/all-MiniLM-L6-v2 (384-dim)")
    print(f"Data Directory  : {data_dir}")
    print("-" * 65)

    try:
        logger.info("Step 1/3: Initializing database schema and pgvector extension...")
        await init_db()
        logger.info("✓ Database tables verified/created successfully.")

        logger.info("Step 2/3: Loading documents and generating embeddings...")
        stats = await run_ingestion(data_dir)

        logger.info("Step 3/3: Ingestion finished!")
        print("-" * 65)
        print(f"✓ Summary: {stats['documents']} document(s) registered, {stats['chunks']} chunk(s) stored in vector DB.")
        print("=" * 65)

    except Exception as exc:
        logger.error("Ingestion failed: %s", exc)
        print("\nTroubleshooting tips:")
        print("1. Ensure PostgreSQL is running on the host/port in your .env file.")
        print("2. Ensure the database exists (e.g. online_bazaar).")
        print("3. Ensure pgvector extension is available: CREATE EXTENSION vector;")
        print("4. Verify credentials in .env (DATABASE_URL).")
        raise
    finally:
        await close_pool()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the Aurelia & Co. knowledge base ingestion pipeline into pgvector."
    )
    parser.add_argument(
        "--data-dir",
        default="data",
        help="Path to directory containing products.json, policies/, and faqs.md (default: data)",
    )
    args = parser.parse_args()

    # Automatically resolve data directory
    resolved_path = Path(args.data_dir)
    if not resolved_path.exists():
        candidates = [
            _root_dir / args.data_dir,
            _backend_dir.parent / args.data_dir,
            Path.cwd() / args.data_dir,
        ]
        for c in candidates:
            if c.exists():
                resolved_path = c
                break

    asyncio.run(execute_ingestion(str(resolved_path)))


if __name__ == "__main__":
    main()
