#!/usr/bin/env python3
"""CLI thin wrapper for P1 quick market check."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.research_core.pipeline.quick_market_check import main


if __name__ == "__main__":
    raise SystemExit(main())
