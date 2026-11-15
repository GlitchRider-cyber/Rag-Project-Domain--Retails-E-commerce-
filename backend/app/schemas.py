"""Pydantic request / response models."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


# ── Chat ────────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    message: str = Field(..., min_length=1, max_length=2000)


class SourceItem(BaseModel):
    chunk_id: int
    content: str
    section: Optional[str] = None
    metadata: dict[str, Any] = {}
    score: float
    doc_type: str


class ChatResponse(BaseModel):
    session_id: str
    message_id: int
    answer: str
    sources: list[SourceItem] = []


# ── Sources ─────────────────────────────────────────────────────────────────

class SourceResponse(BaseModel):
    chunk_id: int
    content: str
    section: Optional[str] = None
    metadata: dict[str, Any] = {}
    doc_type: str


# ── Feedback ────────────────────────────────────────────────────────────────

class FeedbackRequest(BaseModel):
    message_id: int
    rating: int = Field(..., ge=-1, le=1)
    comment: Optional[str] = None


class FeedbackResponse(BaseModel):
    id: int
    message: str = "Feedback recorded"


# ── Ingest ──────────────────────────────────────────────────────────────────

class IngestRequest(BaseModel):
    data_dir: str = "data"


class IngestResponse(BaseModel):
    documents: int
    chunks: int
    message: str = "Ingestion complete"


# ── Health ──────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    database: str
    chunks_count: int = 0
