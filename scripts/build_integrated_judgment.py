#!/usr/bin/env python3
"""Generate integrated_operator_judgment skeleton from P6 evaluation outputs.

Usage:
  python3 scripts/build_integrated_judgment.py <run_dir>
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.research_core.pipeline.build_integrated_judgment import (
    run_integrated_judgment,
)
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build integrated operator judgment skeleton from P6 evaluations."
    )
    parser.add_argument(
        "run_dir", type=Path,
        help="Path to run directory (e.g. runs/20260623_sample)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    run_dir: Path = args.run_dir.expanduser().resolve()
    if not run_dir.is_dir():
        print(f"ERROR: run_dir not found: {run_dir}", file=sys.stderr)
        return 2

    eval_dir = run_dir / "evaluations"
    if not eval_dir.is_dir():
        print(
            f"ERROR: evaluations directory not found. Run P6 first: {eval_dir}",
            file=sys.stderr,
        )
        return 3

    summary_path = eval_dir / "evaluation_summary.json"
    if not summary_path.exists():
        print(
            f"ERROR: evaluation_summary.json not found: {summary_path}",
            file=sys.stderr,
        )
        return 4

    try:
        judgment = run_integrated_judgment(run_dir)
    except Exception as e:
        print(f"ERROR: judgment generation failed: {e}", file=sys.stderr)
        return 5

    output_path = run_dir / "analysis" / "integrated_operator_judgment.json"
    print(f"Wrote {output_path}")
    print(f"Updated {run_dir / 'progress.json'}")
    print("P7 skeleton only: final verdict must be written by Lead Operator Agent.")
    print("Next: spawn Route Strategy Agent + Growth & Risk Agent, then run Lead Operator Agent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
