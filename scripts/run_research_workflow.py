#!/usr/bin/env python3
"""CLI wrapper for the V1 product research workflow."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.research_core.workflows import WorkflowConfig, run_research_workflow


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run V1 Amazon product research workflow.")
    parser.add_argument("manual_export_folder", help="Folder containing SellerSprite/Amazon manual exports.")
    parser.add_argument("output_dir", help="Directory to write workflow outputs.")
    parser.add_argument("--site", default="US", help="Amazon marketplace, such as US.")
    parser.add_argument("--task-name", default="", help="Task name written into import_manifest metadata.")
    parser.add_argument("--candidate-id", default="", help="Candidate id to deep-dive. Defaults to first candidate.")
    parser.add_argument("--candidate-name", default="", help="Candidate name for VOC report. Defaults to selected candidate name.")
    parser.add_argument(
        "--review-input",
        action="append",
        default=[],
        help="Optional review plugin .xlsx export or .html AI report. Repeat for multiple files.",
    )
    parser.add_argument(
        "--profit-template",
        default="",
        help="Optional filled profit review template. If provided, profit results are merged before rendering final report.",
    )
    parser.add_argument(
        "--ip-compliance-template",
        default="",
        help="Optional filled IP/compliance review template. If provided, screening results are merged before rendering final report.",
    )
    parser.add_argument(
        "--sorftime-verification",
        default="",
        help="Optional Sorftime verification JSON file. If provided, merged into candidate_pool without re-calling MCP.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = WorkflowConfig(
        manual_export_folder=Path(args.manual_export_folder),
        output_dir=Path(args.output_dir),
        site=args.site,
        task_name=args.task_name,
        candidate_id=args.candidate_id,
        candidate_name=args.candidate_name,
        review_inputs=tuple(Path(item) for item in args.review_input),
        profit_template=Path(args.profit_template) if args.profit_template else None,
        ip_compliance_template=Path(args.ip_compliance_template) if args.ip_compliance_template else None,
        sorftime_verification=Path(args.sorftime_verification) if args.sorftime_verification else None,
    )
    try:
        result = run_research_workflow(config)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    print(f"Wrote workflow outputs: {result.output_dir}")
    print(f"Selected candidate: {result.selected_candidate_id} / {result.selected_candidate_name}")
    print(f"Final report: {result.report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
