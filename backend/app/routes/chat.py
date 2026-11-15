"""POST /chat – Streaming RAG chat endpoint."""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from sse_starlette.sse import EventSourceResponse

from app.config import settings
from app.db import get_pool
from app.schemas import ChatRequest
from app.retrieval.embed import embed_query
from app.retrieval.search import hybrid_search
from app.retrieval.rewrite import rewrite_query
from app.llm.prompts import SYSTEM_PROMPT, build_prompt
from app.llm.generate import generate_stream

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/chat")
async def chat(req: ChatRequest):
    """Streaming RAG chat. Returns SSE with token and sources events."""
    pool = await get_pool()

    # ── Session management ──────────────────────────────────────────────
    session_id = req.session_id or str(uuid.uuid4())
    async with pool.acquire() as conn:
        exists = await conn.fetchval(
            "SELECT 1 FROM chat_sessions WHERE id = $1", session_id
        )
        if not exists:
            await conn.execute(
                "INSERT INTO chat_sessions (id) VALUES ($1)", session_id
            )

    # ── Chat history ────────────────────────────────────────────────────
    chat_history: list[dict[str, str]] = []
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT role, content FROM messages
            WHERE session_id = $1
            ORDER BY created_at DESC
            LIMIT 10
            """,
            session_id,
        )
        chat_history = [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]

    # ── Query rewriting ─────────────────────────────────────────────────
    rewritten_query = await rewrite_query(req.message, chat_history)

    # ── Retrieval ───────────────────────────────────────────────────────
    query_emb = embed_query(rewritten_query)
    results = await hybrid_search(
        query=rewritten_query,
        query_embedding=query_emb,
        top_k=settings.RETRIEVAL_TOP_K,
    )

    # Filter by relevance threshold
    relevant = [r for r in results if r["score"] >= settings.RELEVANCE_THRESHOLD]
    if not relevant:
        relevant = results[:3]  # fallback: use top 3 even if below threshold

    # ── Build prompt & stream ───────────────────────────────────────────
    prompt = build_prompt(relevant, req.message, chat_history)

    async def event_generator():
        full_answer: list[str] = []
        try:
            async for token in generate_stream(prompt, SYSTEM_PROMPT):
                full_answer.append(token)
                yield {"event": "token", "data": token}

            # Sources event
            sources = [
                {
                    "chunk_id": r["chunk_id"],
                    "section": r.get("section", ""),
                    "doc_type": r["doc_type"],
                    "score": round(r["score"], 4),
                }
                for r in relevant
            ]

            answer_text = "".join(full_answer)

            # Save messages to DB
            async with pool.acquire() as conn:
                # Save user message
                await conn.execute(
                    "INSERT INTO messages (session_id, role, content) VALUES ($1, $2, $3)",
                    session_id,
                    "user",
                    req.message,
                )
                # Save assistant message
                msg_row = await conn.fetchrow(
                    """
                    INSERT INTO messages (session_id, role, content, sources)
                    VALUES ($1, $2, $3, $4::jsonb)
                    RETURNING id
                    """,
                    session_id,
                    "assistant",
                    answer_text,
                    json.dumps(sources),
                )
                # Update session timestamp
                await conn.execute(
                    "UPDATE chat_sessions SET updated_at = now() WHERE id = $1",
                    session_id,
                )

            yield {
                "event": "sources",
                "data": json.dumps(
                    {
                        "session_id": session_id,
                        "message_id": msg_row["id"],
                        "sources": sources,
                    }
                ),
            }

            yield {"event": "done", "data": ""}

        except Exception:
            logger.exception("Error in chat stream")
            yield {
                "event": "error",
                "data": "An error occurred. Please try again.",
            }

    return EventSourceResponse(event_generator())
