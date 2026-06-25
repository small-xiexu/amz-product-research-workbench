#!/usr/bin/env python3
"""CLI thin wrapper for P2 MCP candidate pool."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.research_core.pipeline.build_mcp_candidate_pool import main


if __name__ == "__main__":
    raise SystemExit(main())
