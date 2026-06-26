#!/usr/bin/env python3
"""CLI entry for P6: run all 6 evaluations and generate evaluation_summary."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.research_core.pipeline.build_evaluation_summary import run_evaluations, P6EvaluationError


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    if not argv:
        print("Usage: python3 scripts/build_evaluation_summary.py <run_dir>", file=sys.stderr)
        return 2

    run_dir = Path(argv[0]).expanduser().resolve()
    if not run_dir.exists():
        print(f"Run directory does not exist: {run_dir}", file=sys.stderr)
        return 2

    try:
        output_paths = run_evaluations(run_dir)
        print("P6 evaluations complete. Outputs:")
        for name, path in sorted(output_paths.items()):
            print(f"  {name}: {path}")
        return 0
    except P6EvaluationError as e:
        print(f"P6 evaluation error: {e}", file=sys.stderr)
        return 2
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
