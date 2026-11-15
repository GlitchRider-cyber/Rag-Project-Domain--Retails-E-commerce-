"""Chunking strategies for different document types."""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


def chunk_product(product: dict[str, Any]) -> dict[str, Any]:
    """Create a single chunk for a product – never split a product across chunks.

    Returns a dict with content, section, metadata, doc_type.
    """
    lines = [
        f"Product: {product.get('name', 'Unknown')}",
        f"SKU: {product.get('sku', '')}",
        f"Category: {product.get('category', '')} > {product.get('subcategory', '')}",
        f"Price: ${product.get('price', 0):.2f} {product.get('currency', 'USD')}",
        f"Material: {product.get('material', '')}",
        f"Sizes: {', '.join(product.get('sizes', []))}",
        f"Colors: {', '.join(product.get('colors', []))}",
        f"In Stock: {'Yes' if product.get('in_stock', True) else 'No'}",
        "",
        product.get("description", ""),
        "",
        "Features:",
    ]
    for feat in product.get("features", []):
        lines.append(f"  • {feat}")

    lines.append("")
    lines.append(f"Care Instructions: {product.get('care_instructions', '')}")

    if product.get("tags"):
        lines.append(f"Tags: {', '.join(product['tags'])}")

    content = "\n".join(lines)

    return {
        "content": content,
        "section": product.get("name", "Unknown Product"),
        "metadata": {
            "id": product.get("id", ""),
            "sku": product.get("sku", ""),
            "category": product.get("category", ""),
            "subcategory": product.get("subcategory", ""),
            "price": product.get("price", 0),
            "in_stock": product.get("in_stock", True),
        },
        "doc_type": "product",
    }


def chunk_policy(content: str, title: str) -> list[dict[str, Any]]:
    """Split a policy markdown by ``##`` headings.

    Keeps the heading with its content.  Target 300-500 tokens per chunk
    with a small context overlap (the heading is always prepended).
    """
    # Split on ## headings (keep the heading with the section)
    sections = re.split(r"(?m)^(## .+)$", content)

    chunks: list[dict[str, Any]] = []
    current_heading = title
    current_body = ""

    for part in sections:
        part = part.strip()
        if not part:
            continue
        if part.startswith("## "):
            # flush previous
            if current_body.strip():
                chunks.append(_make_policy_chunk(current_heading, current_body, title))
            current_heading = part.lstrip("# ").strip()
            current_body = ""
        else:
            current_body += part + "\n"

    # flush last
    if current_body.strip():
        chunks.append(_make_policy_chunk(current_heading, current_body, title))

    # If there were no ## headings at all, produce a single chunk
    if not chunks:
        chunks.append(_make_policy_chunk(title, content, title))

    logger.info("Chunked policy '%s' into %d chunks", title, len(chunks))
    return chunks


def _make_policy_chunk(heading: str, body: str, policy_title: str) -> dict[str, Any]:
    text = f"{heading}\n\n{body.strip()}"
    return {
        "content": text,
        "section": heading,
        "metadata": {"policy": policy_title},
        "doc_type": "policy",
    }


def chunk_faqs(qa_pairs: list[dict[str, str]]) -> list[dict[str, Any]]:
    """One chunk per Q&A pair."""
    chunks: list[dict[str, Any]] = []
    for qa in qa_pairs:
        content = f"Q: {qa['question']}\n\nA: {qa['answer']}"
        chunks.append({
            "content": content,
            "section": qa["question"],
            "metadata": {},
            "doc_type": "faq",
        })
    logger.info("Chunked %d FAQ pairs", len(chunks))
    return chunks
