"""POST /feedback – Record user feedback on a message."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from app.db import get_pool
from app.schemas import FeedbackRequest, FeedbackResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/feedback", response_model=FeedbackResponse)
async def submit_feedback(req: FeedbackRequest):
    """Save thumbs-up / thumbs-down feedback for a message."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Verify message exists
        msg_exists = await conn.fetchval(
            "SELECT 1 FROM messages WHERE id = $1", req.message_id
        )
        if not msg_exists:
            raise HTTPException(status_code=404, detail="Message not found")

        row = await conn.fetchrow(
            """
            INSERT INTO feedback (message_id, rating, comment)
            VALUES ($1, $2, $3)
            RETURNING id
            """,
            req.message_id,
            req.rating,
            req.comment,
        )

    return FeedbackResponse(id=row["id"])
