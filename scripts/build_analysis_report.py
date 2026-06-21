#!/usr/bin/env python3
"""CLI thin wrapper — business logic lives in packages/research_core/pipeline/build_analysis_report.py."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.research_core.pipeline.build_analysis_report import main

if __name__ == "__main__":
    raise SystemExit(main())
