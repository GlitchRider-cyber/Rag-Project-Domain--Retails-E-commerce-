"""Hybrid search: vector + full-text with Reciprocal Rank Fusion."""

from __future__ import annotations

import json
import logging
from typing import Any

from app.db import get_pool

logger = logging.getLogger(__name__)


async def vector_search(
    query_embedding: list[float], top_k: int = 6
) -> list[dict[str, Any]]:
    """Cosine similarity search via pgvector."""
    pool = await get_pool()
    embedding_str = "[" + ",".join(str(v) for v in query_embedding) + "]"

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, content, section, metadata, doc_type,
                   1 - (embedding <=> $1::vector) AS score
            FROM chunks
            WHERE embedding IS NOT NULL
            ORDER BY embedding <=> $1::vector
            LIMIT $2;
            """,
            embedding_str,
            top_k,
        )

    return [_row_to_dict(r) for r in rows]


async def fulltext_search(query: str, top_k: int = 6) -> list[dict[str, Any]]:
    """PostgreSQL full-text search using ts_rank."""
    pool = await get_pool()

    # Build tsquery from the raw query (plainto_tsquery handles punctuation)
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, content, section, metadata, doc_type,
                   ts_rank(tsv, plainto_tsquery('english', $1)) AS score
            FROM chunks
            WHERE tsv @@ plainto_tsquery('english', $1)
            ORDER BY score DESC
            LIMIT $2;
            """,
            query,
            top_k,
        )

    return [_row_to_dict(r) for r in rows]


async def hybrid_search(
    query: str,
    query_embedding: list[float],
    top_k: int = 6,
) -> list[dict[str, Any]]:
    """Run vector + full-text search and merge with Reciprocal Rank Fusion (k=60)."""
    vec_results, ft_results = await _gather(
        vector_search(query_embedding, top_k * 2),
        fulltext_search(query, top_k * 2),
    )

    rrf_k = 60
    scores: dict[int, float] = {}
    result_map: dict[int, dict[str, Any]] = {}

    for rank, r in enumerate(vec_results, start=1):
        cid = r["chunk_id"]
        scores[cid] = scores.get(cid, 0) + 1.0 / (rrf_k + rank)
        result_map[cid] = r

    for rank, r in enumerate(ft_results, start=1):
        cid = r["chunk_id"]
        scores[cid] = scores.get(cid, 0) + 1.0 / (rrf_k + rank)
        if cid not in result_map:
            result_map[cid] = r

    # Sort by fused score descending
    sorted_ids = sorted(scores, key=lambda cid: scores[cid], reverse=True)[:top_k]

    results = []
    for cid in sorted_ids:
        entry = result_map[cid]
        entry["score"] = scores[cid]
        results.append(entry)

    return results


# ── helpers ─────────────────────────────────────────────────────────────────

async def _gather(*coros):
    """Run coroutines concurrently."""
    import asyncio

    return await asyncio.gather(*coros)


def _row_to_dict(row) -> dict[str, Any]:
    """Convert an asyncpg Record to a result dict."""
    metadata = row["metadata"]
    if isinstance(metadata, str):
        metadata = json.loads(metadata)
    return {
        "chunk_id": row["id"],
        "content": row["content"],
        "section": row.get("section"),
        "metadata": metadata,
        "score": float(row["score"]),
        "doc_type": row["doc_type"],
    }
