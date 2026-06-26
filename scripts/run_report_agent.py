#!/usr/bin/env python3
"""Run Report Generation Agent to produce report_data.json and HTML.

Usage:
  python3 scripts/run_report_agent.py <run_dir>

This runs the agent in serial_fallback mode. After the agent completes,
run build_analysis_report.py again to generate XLSX and QA artifacts.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.research_core.pipeline.report_agent import run_report_agent


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Report Generation Agent (serial_fallback mode)."
    )
    parser.add_argument(
        "run_dir",
        type=Path,
        help="Path to run directory (e.g. runs/20260623_sample)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    run_dir: Path = args.run_dir.expanduser().resolve()

    if not run_dir.is_dir():
        print(f"ERROR: run_dir not found: {run_dir}", file=sys.stderr)
        return 2

    analysis_dir = run_dir / "analysis"
    seed_path = analysis_dir / "report_data.seed.json"
    if not seed_path.exists():
        print(
            f"ERROR: report_data.seed.json not found in {analysis_dir}",
            file=sys.stderr,
        )
        print(
            "Run build_analysis_report.py first to generate the seed.",
            file=sys.stderr,
        )
        return 3

    judgment_path = analysis_dir / "integrated_operator_judgment.json"
    if not judgment_path.exists():
        print(
            "WARNING: integrated_operator_judgment.json not found. "
            "Report will be generated without judgment context.",
            file=sys.stderr,
        )

    result = run_report_agent(run_dir)

    if result.get("status") == "error":
        print(f"ERROR: {result.get('error')}", file=sys.stderr)
        return 1

    outputs = result.get("outputs") or {}
    print(f"Wrote {outputs.get('report_data', '')}")
    print(f"Wrote {outputs.get('html', '')}")

    validation = result.get("validation") or {}
    if not validation.get("valid"):
        print(f"VALIDATION ISSUES: {validation.get('issues', [])}", file=sys.stderr)
        return 4

    print(
        f"Report Generation Agent: OK (mode={result.get('execution_mode', 'serial_fallback')})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
