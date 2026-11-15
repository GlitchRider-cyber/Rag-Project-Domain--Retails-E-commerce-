"""GET /health – Readiness / liveness check."""

from __future__ import annotations

import logging

from fastapi import APIRouter

from app.db import get_pool
from app.schemas import HealthResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health():
    """Check database connectivity and return basic stats."""
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            chunks_count = await conn.fetchval("SELECT count(*) FROM chunks")
        return HealthResponse(
            status="healthy",
            database="connected",
            chunks_count=chunks_count or 0,
        )
    except Exception as exc:
        logger.exception("Health check failed")
        return HealthResponse(
            status="unhealthy",
            database=f"error: {exc}",
            chunks_count=0,
        )
