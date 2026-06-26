#!/usr/bin/env python3
"""End-to-end pipeline orchestrator for Stages 1-4 — CLI entry.

Usage:
  python3 scripts/run_pipeline.py <run_dir> --intent "目标品类方向" [--mode targeted|exploration] [--site US]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.research_core.pipeline.run_pipeline import run_pipeline


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run pipeline stages 1-4.")
    parser.add_argument("run_dir", type=Path, help="Run directory (e.g. runs/20260625_sample)")
    parser.add_argument("--intent", required=True, help="目标品类方向描述")
    parser.add_argument("--mode", choices=["exploration", "targeted"], default="targeted")
    parser.add_argument("--site", default="US")
    parser.add_argument("--from-stage", type=int, default=1, help="Start from this stage (1-5)")
    args = parser.parse_args(argv)

    run_dir: Path = args.run_dir.expanduser().resolve()
    return run_pipeline(run_dir, args.intent, args.mode, args.site, args.from_stage)


if __name__ == "__main__":
    raise SystemExit(main())
