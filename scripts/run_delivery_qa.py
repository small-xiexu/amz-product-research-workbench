#!/usr/bin/env python3
"""Run script-side Delivery QA on a completed run directory.

Usage:
  python3 scripts/run_delivery_qa.py <run_dir>

Exit codes:
  0 — QA passed (all checks green)
  1 — QA failed (at least one check failed)
  2 — run_dir not found or missing required files
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.research_core.pipeline.delivery_qa import (
    find_report_files,
    print_qa_summary,
    run_delivery_qa,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run script-side Delivery QA on a run directory."
    )
    parser.add_argument(
        "run_dir",
        type=Path,
        help="Path to run directory (e.g. runs/20260623_sample)",
    )
    parser.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        default=False,
        help="Output full QA result as JSON",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    run_dir: Path = args.run_dir.expanduser().resolve()

    if not run_dir.is_dir():
        print(f"ERROR: run_dir not found: {run_dir}", file=sys.stderr)
        return 2

    report_data_path, html_path, xlsx_path = find_report_files(run_dir)

    missing = []
    if not report_data_path:
        missing.append("report_data.json")
    if not html_path:
        missing.append("<品名>_分析报告.html")
    if not xlsx_path:
        missing.append("<品名>_决策工具包.xlsx")

    if missing:
        print(f"ERROR: missing required files in {run_dir / 'analysis'}: {', '.join(missing)}", file=sys.stderr)
        return 2

    result = run_delivery_qa(report_data_path, html_path, xlsx_path)

    if args.json_output:
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    else:
        print_qa_summary(result)

    if result.get("status") == "fail":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
