#!/usr/bin/env python3
"""Run lightweight evals for the amazon-product-research skill (Link B pipeline)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.report_renderer.xlsx_writer import write_xlsx
from packages.research_core.pipeline.build_analysis_report import (
    build_analysis_packet,
    seed_report_data_from_analysis,
    xlsx_sheets_from_report_data,
)

EVAL_DIR = Path(__file__).resolve().parent


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run amazon-product-research eval checks.")
    parser.add_argument(
        "check",
        nargs="?",
        default="build_minimal_analysis_packet",
        choices=("build_minimal_analysis_packet",),
    )
    args = parser.parse_args(argv)

    if args.check == "build_minimal_analysis_packet":
        return _run_minimal_analysis_packet_eval()
    raise ValueError(f"unsupported eval check: {args.check}")


def _run_minimal_analysis_packet_eval() -> int:
    with tempfile.TemporaryDirectory(prefix="amz_skill_eval_") as tmp:
        run_dir = Path(tmp)
        analysis_dir = run_dir / "analysis"
        analysis_dir.mkdir(parents=True, exist_ok=True)
        _write_minimal_evidence_packets(run_dir)

        packets = _load_packets(run_dir)
        analysis = build_analysis_packet(run_dir, packets)

        report_data_path = analysis_dir / "report_data.json"
        xlsx_path = analysis_dir / "analysis_report.xlsx"
        seed = seed_report_data_from_analysis(analysis)
        report_data_path.write_text(json.dumps(seed, ensure_ascii=False, indent=2), encoding="utf-8")
        write_xlsx(xlsx_path, xlsx_sheets_from_report_data(report_data_path))

        assert report_data_path.exists(), "report_data.json not written"
        assert xlsx_path.exists(), "analysis_report.xlsx not written"
        assert seed.get("hero", {}).get("verdict") in ("继续看", "谨慎继续", "暂缓"), f"unexpected verdict: {seed.get('hero', {}).get('verdict')}"
        print(f"generated: {report_data_path}")
        print(f"generated: {xlsx_path}")
        print("eval_ok")
    return 0


def _write_minimal_evidence_packets(run_dir: Path) -> None:
    market_dir = run_dir / "market_structure"
    search_dir = run_dir / "search_demand"
    voc_dir = run_dir / "review_voc"
    for d in (market_dir, search_dir, voc_dir):
        d.mkdir(parents=True, exist_ok=True)

    (market_dir / "market_structure_evidence_packet.json").write_text(json.dumps({
        "packet_id": "market_structure",
        "summary": {"top_categories": [], "reference_asin_pool": []},
        "primary_market_distribution_grouped": {},
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    (search_dir / "search_demand_evidence_packet.json").write_text(json.dumps({
        "packet_id": "search_demand",
        "summary": {},
        "facts": [],
        "keywords": [],
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    (voc_dir / "voc_evidence_packet.json").write_text(json.dumps({
        "packet_id": "voc_evidence",
        "summary": {"review_count": 10, "asin_count": 2, "low_rating_count": 3},
        "pain_points_by_dimension": [],
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    (run_dir / "route_matrix_confirm.json").write_text(json.dumps({
        "routes": [{"route_name": "eval route", "route_type": "主线"}],
        "reference_asins": [],
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    (run_dir / "selection_brief.json").write_text(json.dumps({
        "candidate_name": "eval candidate",
        "site": "US",
    }, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_packets(run_dir: Path) -> dict[str, Any]:
    from packages.research_core.pipeline.build_analysis_report import load_packets
    return load_packets(run_dir)


if __name__ == "__main__":
    raise SystemExit(main())
