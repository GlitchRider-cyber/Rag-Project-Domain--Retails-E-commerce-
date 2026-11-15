#!/usr/bin/env python3
"""
CLI script to run data ingestion from the command line.

Usage:
    python ingest_cli.py [--data-dir ../data]
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure backend directory and root are in sys.path
_this_dir = Path(__file__).resolve().parent
_root_dir = _this_dir.parent
for p in (str(_this_dir), str(_root_dir)):
    if p not in sys.path:
        sys.path.insert(0, p)

from app.ingest.runner import main

if __name__ == "__main__":
    main()
