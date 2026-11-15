"""Alias and wrapper for loaders and ingestion runner."""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure backend directory is in sys.path BEFORE any app.* imports
_this_dir = Path(__file__).resolve().parent
_backend_dir = _this_dir.parent.parent
_root_dir = _backend_dir.parent
for p in (str(_backend_dir), str(_root_dir)):
    if p not in sys.path:
        sys.path.insert(0, p)

# Re-export everything from loaders
from app.ingest.loaders import load_products, load_markdown, load_policies, load_faqs

if __name__ == "__main__":
    # If run directly as python -m backend.app.ingest.loader, invoke the runner
    from app.ingest.runner import main
    main()
