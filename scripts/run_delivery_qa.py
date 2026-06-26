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

from packages.research_core.pipeline.delivery_qa import run_delivery_qa


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


def find_report_files(run_dir: Path) -> tuple[Path | None, Path | None, Path | None]:
    """Find report_data.json, HTML, and XLSX in the analysis directory."""
    analysis_dir = run_dir / "analysis"
    report_data = analysis_dir / "report_data.json"
    if not report_data.exists():
        report_data = None

    html_path = None
    xlsx_path = None
    if analysis_dir.is_dir():
        for f in analysis_dir.iterdir():
            if f.suffix == ".html" and f.name.endswith("_分析报告.html"):
                html_path = f
            elif f.suffix == ".xlsx" and f.name.endswith("_决策工具包.xlsx"):
                xlsx_path = f

    return report_data, html_path, xlsx_path


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
        _print_summary(result)

    if result.get("status") == "fail":
        return 1
    return 0


def _print_summary(result: dict) -> None:
    """Print a human-readable QA summary."""
    print(f"QA Rule Version: {result.get('qa_rule_version', '?')}")
    print(f"Status: {result['status'].upper()}")
    print(f"Generated: {result.get('generated_at', '?')}")
    print()

    checks = result.get("checks", {})
    failures = result.get("failures", [])

    for name, passed in checks.items():
        if name in ("report_data_sources_note", "report_data_values_note",
                     "report_data_value_mismatches", "forbidden_html_hits",
                     "p0_blocker_hits", "conflict_leak_hits",
                     "report_template_css_hits", "report_class_hits",
                     "fixed_data_source_section_hits"):
            continue
        if isinstance(passed, bool):
            icon = "PASS" if passed else "FAIL"
            print(f"  [{icon}] {name}")

    if failures:
        print(f"\nFailures ({len(failures)}):")
        for f in failures:
            print(f"  - {f}")

    # Print detail subsections
    if checks.get("forbidden_html_hits"):
        print("\nForbidden HTML patterns found:")
        for hit in checks["forbidden_html_hits"]:
            print(f"  - {hit}")

    if checks.get("conflict_leak_hits"):
        print("\nConflict process leaks found:")
        for hit in checks["conflict_leak_hits"]:
            print(f"  - {hit}")

    if checks.get("p0_blocker_hits"):
        print("\nP0 Blocker hits:")
        for hit in checks["p0_blocker_hits"]:
            print(f"  - {hit}")

    if checks.get("report_template_css_hits"):
        print("\nReport template CSS issues:")
        for hit in checks["report_template_css_hits"]:
            print(f"  - {hit}")

    if checks.get("report_class_hits"):
        print("\nReport class issues:")
        for hit in checks["report_class_hits"]:
            print(f"  - {hit}")

    if checks.get("fixed_data_source_section_hits"):
        print("\nReport section issues:")
        for hit in checks["fixed_data_source_section_hits"]:
            print(f"  - {hit}")

    if checks.get("report_data_sources_note"):
        print(f"\nSource note: {checks['report_data_sources_note']}")

    if checks.get("report_data_values_note"):
        print(f"\nValues note: {checks['report_data_values_note']}")

    if checks.get("report_data_value_mismatches"):
        print("\nValue mismatches:")
        for m in checks["report_data_value_mismatches"][:10]:
            print(f"  - {m.get('key', '?')}: reported={m.get('reported', '?')} vs resolved={m.get('resolved', '?')}")


if __name__ == "__main__":
    raise SystemExit(main())
