"""Prompt templates for the Aurelia & Co. RAG assistant."""

from __future__ import annotations

from typing import Any

SYSTEM_PROMPT = (
    "You are Aurelia, the AI shopping assistant for Aurelia & Co. "
    "Answer ONLY from the provided context. "
    "Cite sources with [1], [2] etc. "
    "Never invent prices, availability, or policies. "
    "If the context doesn't contain the answer, say so and suggest contacting "
    "support at support@aureliaandco.com. "
    "Be friendly, concise, and helpful."
)


def build_prompt(
    context_chunks: list[dict[str, Any]],
    question: str,
    chat_history: list[dict[str, str]] | None = None,
) -> str:
    """Build the full user prompt with numbered context and chat history."""
    parts: list[str] = []

    # Context
    parts.append("Context:")
    for i, chunk in enumerate(context_chunks, start=1):
        source_label = chunk.get("section", chunk.get("doc_type", "source"))
        parts.append(f"\n[{i}] ({source_label})\n{chunk['content']}")

    parts.append("")

    # Recent chat history (if any)
    if chat_history:
        parts.append("Recent conversation:")
        for msg in chat_history[-4:]:
            role = msg["role"].capitalize()
            parts.append(f"{role}: {msg['content']}")
        parts.append("")

    # The question
    parts.append(f"Question: {question}")

    return "\n".join(parts)
