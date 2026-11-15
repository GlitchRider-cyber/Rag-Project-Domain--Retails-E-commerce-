"""Query rewriting for multi-turn conversations using Gemini."""

from __future__ import annotations

import logging

from google import genai

from app.config import settings

logger = logging.getLogger(__name__)


async def rewrite_query(question: str, chat_history: list[dict[str, str]]) -> str:
    """Rewrite a follow-up question into a standalone question using chat history.

    If the question is already standalone (no chat history, or no pronouns
    referencing prior turns), return it as-is.
    """
    if not chat_history:
        return question

    # Build a concise history summary (last 6 turns)
    recent = chat_history[-6:]
    history_text = "\n".join(
        f"{msg['role'].capitalize()}: {msg['content']}" for msg in recent
    )

    prompt = (
        "Given the following conversation history and a follow-up question, "
        "rewrite the follow-up question to be a standalone question that "
        "captures all necessary context. If the question is already standalone, "
        "return it unchanged. Return ONLY the rewritten question, nothing else.\n\n"
        f"Conversation History:\n{history_text}\n\n"
        f"Follow-up Question: {question}\n\n"
        "Standalone Question:"
    )

    try:
        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        response = client.models.generate_content(
            model=settings.GEMINI_CHAT_MODEL,
            contents=prompt,
        )
        rewritten = response.text.strip()
        if rewritten:
            logger.info("Rewrote query: '%s' -> '%s'", question, rewritten)
            return rewritten
    except Exception:
        logger.exception("Query rewrite failed, using original question")

    return question
