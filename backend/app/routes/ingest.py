"""POST /ingest – Admin-only data ingestion endpoint."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Header, HTTPException

from app.config import settings
from app.schemas import IngestRequest, IngestResponse
from app.ingest.pipeline import run_ingestion

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/ingest", response_model=IngestResponse)
async def ingest(
    req: IngestRequest,
    x_admin_password: str = Header(..., alias="X-Admin-Password"),
):
    """Run the ingestion pipeline. Requires admin password in header."""
    if x_admin_password != settings.ADMIN_PASSWORD:
        raise HTTPException(status_code=403, detail="Invalid admin password")

    try:
        stats = await run_ingestion(req.data_dir)
        return IngestResponse(
            documents=stats["documents"],
            chunks=stats["chunks"],
        )
    except Exception:
        logger.exception("Ingestion failed")
        raise HTTPException(status_code=500, detail="Ingestion failed")
