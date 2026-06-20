#!/usr/bin/env python3
"""CLI wrapper for Stage 5 route matrix confirmation packet generation."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.research_core.pipeline.build_route_matrix_confirm import main


if __name__ == "__main__":
    raise SystemExit(main())
