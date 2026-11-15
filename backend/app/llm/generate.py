"""Streaming response generation via Google Gemini."""

from __future__ import annotations

import asyncio
import logging
from typing import AsyncGenerator

from google import genai
from google.genai import types

from app.config import settings

logger = logging.getLogger(__name__)


async def generate_stream(
    prompt: str, system_prompt: str
) -> AsyncGenerator[str, None]:
    """Stream tokens from Gemini, yielding each chunk of text as it arrives.

    Uses run_in_executor to wrap the synchronous Gemini streaming iterator
    inside the async event loop so it doesn't block the server.
    """
    try:
        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        loop = asyncio.get_event_loop()

        # Build the iterator synchronously in a thread pool executor
        # so we don't block the event loop during the HTTP connection.
        def _build_stream():
            return client.models.generate_content_stream(
                model=settings.GEMINI_CHAT_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=0.3,
                    max_output_tokens=1024,
                ),
            )

        stream = await loop.run_in_executor(None, _build_stream)

        # Iterate chunk-by-chunk. Each `.next()` call is blocking,
        # so we offload it to the thread pool as well.
        def _next_chunk(iterator):
            try:
                return next(iterator)
            except StopIteration:
                return None

        while True:
            chunk = await loop.run_in_executor(None, _next_chunk, stream)
            if chunk is None:
                break
            if chunk.text:
                yield chunk.text

    except Exception:
        logger.exception("Gemini streaming generation failed")
        yield (
            "I'm sorry, I encountered an error generating a response. "
            "Please try again or contact support@aureliaandco.com."
        )
