"""GET /sources/{chunk_id} – Retrieve a single chunk's content and metadata."""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, HTTPException

from app.db import get_pool
from app.schemas import SourceResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/sources/{chunk_id}", response_model=SourceResponse)
async def get_source(chunk_id: int):
    """Return the full content and metadata for a given chunk."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, content, section, metadata, doc_type FROM chunks WHERE id = $1",
            chunk_id,
        )

    if row is None:
        raise HTTPException(status_code=404, detail="Chunk not found")

    metadata = row["metadata"]
    if isinstance(metadata, str):
        metadata = json.loads(metadata)

    return SourceResponse(
        chunk_id=row["id"],
        content=row["content"],
        section=row["section"],
        metadata=metadata,
        doc_type=row["doc_type"],
    )
