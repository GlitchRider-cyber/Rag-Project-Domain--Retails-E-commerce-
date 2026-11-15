"""FastAPI application entry point for Aurelia & Co. RAG Assistant."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db import init_db, close_pool
from app.routes import chat, ingest, sources, feedback, health

# ── Logging ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


# ── Lifespan ────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    logger.info("Starting Aurelia & Co. RAG backend…")
    await init_db()
    logger.info("Database initialised")
    yield
    logger.info("Shutting down…")
    await close_pool()
    logger.info("Database pool closed")


# ── App ─────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Aurelia & Co. RAG Assistant",
    description="AI-powered shopping assistant for Aurelia & Co.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(chat.router, tags=["Chat"])
app.include_router(ingest.router, tags=["Ingest"])
app.include_router(sources.router, tags=["Sources"])
app.include_router(feedback.router, tags=["Feedback"])
app.include_router(health.router, tags=["Health"])
