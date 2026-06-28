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
from packages.research_core.pipeline.build_analysis_packet import build_analysis_packet
from packages.research_core.pipeline.seed_report_data import seed_report_data_from_analysis
from packages.research_core.pipeline.xlsx_back_table import xlsx_sheets_from_report_data
from packages.research_core.pipeline.delivery_qa import run_delivery_qa

EVAL_DIR = Path(__file__).resolve().parent


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run amazon-product-research eval checks.")
    parser.add_argument(
        "check",
        nargs="?",
        default="all",
        choices=("all", "build_minimal_analysis_packet", "stage9_qa_pipeline"),
    )
    args = parser.parse_args(argv)

    failures = 0
    if args.check in ("all", "build_minimal_analysis_packet"):
        if _run_minimal_analysis_packet_eval() != 0:
            failures += 1
    if args.check in ("all", "stage9_qa_pipeline"):
        if _run_stage9_qa_pipeline_eval() != 0:
            failures += 1
    if failures:
        print(f"\n{failures} eval(s) failed")
    return failures


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
        assert seed.get("hero", {}).get("verdict") in (
            "建议进入小批量验证",
            "建议补齐数据后再评估",
            "建议暂停推进",
        ), f"unexpected verdict: {seed.get('hero', {}).get('verdict')}"
        print(f"generated: {report_data_path}")
        print(f"generated: {xlsx_path}")
        print("eval_ok")
    return 0


def _run_stage9_qa_pipeline_eval() -> int:
    """验证 Stage 9 QA 管线：source_path 校验 + 值一致性 + 禁止模式。"""
    with tempfile.TemporaryDirectory(prefix="amz_skill_eval_qa_") as tmp:
        run_dir = Path(tmp)
        analysis_dir = run_dir / "analysis"
        analysis_dir.mkdir(parents=True, exist_ok=True)
        _write_minimal_evidence_packets(run_dir)

        # 构建最小可用的 analysis 和 report_data
        packets = _load_packets(run_dir)
        analysis = build_analysis_packet(run_dir, packets)
        report_data_path = analysis_dir / "report_data.json"
        html_path = analysis_dir / "eval_分析报告.html"
        xlsx_path = analysis_dir / "eval_决策工具包.xlsx"

        # ---- Case 1: 空 source_path 应阻断 QA ----
        bad_seed = seed_report_data_from_analysis(analysis)
        # 注入一条空 source_path
        bad_seed["hero"]["metrics"]["target_market"]["source_path"] = ""
        report_data_path.write_text(json.dumps(bad_seed, ensure_ascii=False, indent=2), encoding="utf-8")
        html_path.write_text("<html><style>.hero{}</style><body></body></html>")
        xlsx_path.write_text("fake")

        qa1 = run_delivery_qa(report_data_path, html_path, xlsx_path, analysis)
        assert qa1["status"] == "fail", f"qa1 should fail on empty source_path, got {qa1['status']}"
        assert not qa1["checks"]["report_data_sources_valid"], "report_data_sources_valid should be False"
        print("  [PASS] Case 1: empty source_path → QA fail")

        # ---- Case 2: __ai_judgment__ 应允许通过 ----
        clean_seed = seed_report_data_from_analysis(analysis)
        report_data_path.write_text(json.dumps(clean_seed, ensure_ascii=False, indent=2), encoding="utf-8")
        qa2 = run_delivery_qa(report_data_path, html_path, xlsx_path, analysis)
        # seed 只有 __ai_judgment__，无空字符串，应 pass（或在仅有其他非 source 相关失败时也合理）
        src_valid = qa2["checks"]["report_data_sources_valid"]
        assert src_valid, f"qa2 source validation should pass with __ai_judgment__, got note: {qa2['checks'].get('report_data_sources_note', '')}"
        print(f"  [PASS] Case 2: __ai_judgment__ → source_valid={src_valid}")

        # ---- Case 3: 值一致性校验 ----
        # 构造值不匹配的场景：source_path 指向可解析的标量字段，value 故意写错
        mismatch_seed = seed_report_data_from_analysis(analysis)
        # analysis.seller_sprite_validation.primary_market.label 一定是标量字符串
        mismatch_seed["hero"]["metrics"]["target_market"] = {
            "label": "目标市场", "value": "WRONG_MARKET_NAME",
            "source_path": "analysis.seller_sprite_validation.primary_market.label",
        }
        report_data_path.write_text(json.dumps(mismatch_seed, ensure_ascii=False, indent=2), encoding="utf-8")
        qa3 = run_delivery_qa(report_data_path, html_path, xlsx_path, analysis)
        values_consistent = qa3["checks"].get("report_data_values_consistent", True)
        assert not values_consistent, (
            f"Case 3: value mismatch MUST be detected, but report_data_values_consistent={values_consistent}"
            f" (note: {qa3['checks'].get('report_data_values_note', 'N/A')})"
        )
        print(f"  [PASS] Case 3: value mismatch correctly detected (values_consistent={values_consistent})")

        # ---- Case 4: 禁止模式检查 ----
        html_bad = html_path.read_text() + "source_path: should be caught"
        html_path.write_text(html_bad)
        qa4 = run_delivery_qa(report_data_path, html_path, xlsx_path, analysis)
        assert not qa4["checks"]["has_no_forbidden_html_patterns"], "forbidden pattern 'source_path' should be caught"
        print(f"  [PASS] Case 4: forbidden HTML pattern detected")

        # ---- Case 5: delivery_qa_result.json 结构完整 ----
        required_checks = [
            "report_data_exists", "html_exists", "xlsx_exists",
            "report_data_has_required_sections", "report_data_sources_valid",
            "report_data_values_consistent", "has_no_forbidden_html_patterns",
            "has_inline_style", "has_8_sections", "has_gonogo_class",
        ]
        missing = [k for k in required_checks if k not in qa4["checks"]]
        assert not missing, f"delivery_qa_result missing checks: {missing}"
        print(f"  [PASS] Case 5: delivery_qa_result has all {len(required_checks)} required checks")

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
        "routes": [{"route_name": "eval route", "route_type": "标准款"}],
        "reference_asins": [],
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    (run_dir / "selection_brief.json").write_text(json.dumps({
        "candidate_name": "eval candidate",
        "site": "US",
    }, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_packets(run_dir: Path) -> dict[str, Any]:
    from packages.research_core.pipeline.build_analysis_packet import load_packets
    return load_packets(run_dir)


if __name__ == "__main__":
    raise SystemExit(main())
