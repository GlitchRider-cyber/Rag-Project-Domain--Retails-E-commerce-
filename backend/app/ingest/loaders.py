"""Data loaders for products, policies, and FAQs."""

from __future__ import annotations

import json
import logging
import re
import sys
from pathlib import Path
from typing import Any

# Ensure backend directory is in sys.path BEFORE any app.* imports
_this_dir = Path(__file__).resolve().parent
_backend_dir = _this_dir.parent.parent
_root_dir = _backend_dir.parent
for p in (str(_backend_dir), str(_root_dir)):
    if p not in sys.path:
        sys.path.insert(0, p)

logger = logging.getLogger(__name__)


def load_products(path: str | Path) -> list[dict[str, Any]]:
    """Load products.json and return a list of product dicts."""
    path = Path(path)
    logger.info("Loading products from %s", path)
    with open(path, "r", encoding="utf-8") as f:
        products = json.load(f)
    logger.info("Loaded %d products", len(products))
    return products


def load_markdown(path: str | Path) -> str:
    """Load a single markdown file and return its content."""
    path = Path(path)
    logger.info("Loading markdown from %s", path)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def load_policies(dir_path: str | Path) -> list[dict[str, str]]:
    """Load all .md files from a policies directory.

    Returns a list of dicts with ``title`` and ``content`` keys.
    """
    dir_path = Path(dir_path)
    policies: list[dict[str, str]] = []
    if not dir_path.exists():
        logger.warning("Policies directory not found: %s", dir_path)
        return policies
    for md_file in sorted(dir_path.glob("*.md")):
        title = md_file.stem.replace("_", " ").replace("-", " ").title()
        content = load_markdown(md_file)
        policies.append({"title": title, "content": content, "filename": md_file.name})
        logger.info("Loaded policy: %s", title)
    logger.info("Loaded %d policies", len(policies))
    return policies


def load_faqs(path: str | Path) -> list[dict[str, str]]:
    """Load faqs.md and split by ``## Q:`` headings into Q&A pairs.

    Returns a list of dicts with ``question`` and ``answer`` keys.
    """
    path = Path(path)
    logger.info("Loading FAQs from %s", path)
    content = load_markdown(path)

    # Split on lines starting with ## Q:
    parts = re.split(r"(?m)^## Q:\s*", content)
    qa_pairs: list[dict[str, str]] = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        lines = part.split("\n", 1)
        question = lines[0].strip()
        answer = lines[1].strip() if len(lines) > 1 else ""
        if question:
            qa_pairs.append({"question": question, "answer": answer})

    logger.info("Loaded %d FAQ pairs", len(qa_pairs))
    return qa_pairs


if __name__ == "__main__":
    # If run directly as python -m backend.app.ingest.loaders, run the ingestion runner
    from app.ingest.runner import main
    main()
