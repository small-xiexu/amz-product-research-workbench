#!/usr/bin/env python3
"""Build report seed, XLSX back-table, and delivery QA from evidence packets.

Orchestration layer for the Stage 7 report handoff. This script creates the
report_data.seed.json handoff for Report Generation Agent. After the agent has
written report_data.json and the formal HTML report, rerunning this script
creates the XLSX back-table and delivery QA artifacts.

Architecture:
  build_analysis_packet.py   evidence packets → analysis_packet
  seed_report_data.py        analysis_packet  → report_data.seed.json
  build_integrated_judgment  P6 evaluations   → integrated_operator_judgment
  Report Generation Agent    seed + judgment  → report_data.json + HTML
  [THIS MODULE]              report_data.json + HTML → XLSX → QA
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

from packages.report_renderer.xlsx_writer import write_xlsx
from packages.research_core.pipeline.audit_run_status import audit_run_status

from packages.research_core.pipeline.constants import (
    QA_RULE_VERSION,
    REPORT_VERDICT_LABELS,
    ALLOWED_VERDICTS,
    FORBIDDEN_HTML_PATTERNS,
    REQUIRED_SECTION_MARKERS,
    VOC_REQUIRED_EVIDENCE_FIELDS,
    REQUIRED_REPORT_DATA_SECTIONS,
    REQUIRED_REPORT_DATA_DECLARATIONS,
)
from packages.research_core.pipeline._utils import (
    _report_value,
    _source_packet_ref,
    _contract_verdict,
    _lead_analysis,
    load_json,
    _NOT_FOUND,
    _split_path,
    _navigate,
    first_text,
    first_dict,
    as_list,
    compact_list,
    join_text,
    public_text,
    first_row_text,
    numeric_value,
    fmt_number,
    fmt_percent,
    dedupe_rows,
)
from packages.research_core.pipeline.build_analysis_packet import (
    load_packets,
    _extract_product_name,
    build_analysis_packet,
    source_packet_row,
    build_route_matrix_fallback,
    build_search_validation,
    build_keyword_demand_rows,
    build_category_background_rows,
    build_traffic_term_groups,
    search_summary,
    build_market_validation,
    market_summary,
    build_reference_asin_pool,
    _build_reference_asin_pool_from_excel,
    _fill_market_validation_from_excel_if_empty,
    build_category_opportunity,
    normalize_category_candidates,
    normalize_price_band_opportunity,
    score_new_release_opportunities,
    normalize_category_seasonality,
    category_opportunity_summary,
    build_keyword_pool,
    normalize_keyword_roles,
    summarize_mix_pool,
    build_voc_translation,
    voc_summary,
    build_route_judgment,
    build_category_selection_derivation,
    derivation_step,
    build_rejected_alternative_rows,
    build_disconfirming_evidence,
    build_blocking_gaps,
    build_evidence_boundaries,
    build_next_stage_conditions,
    build_human_review_focus,
    decide_verdict,
    build_market_synthesis,
    next_move_for_verdict,
    one_sentence_conclusion,
    confidence_level,
    confidence_from_counts,
    _find_product_excel,
    _parse_product_top100,
    _compute_price_bands,
)
from packages.research_core.pipeline.seed_report_data import (
    seed_report_data_from_analysis,
    _core_search_volume_estimate,
    _recommended_price_from_routes,
    _evidence_sources_from_analysis,
    _data_sources_from_analysis,
)
from packages.research_core.pipeline.xlsx_back_table import (
    xlsx_sheets_from_report_data,
    build_workbook_sheets,
    summary_rows,
    source_packet_rows,
    category_derivation_rows,
    category_candidate_rows,
    reference_asin_rows,
    market_opportunity_rows,
    keyword_pool_rows,
    voc_rows,
    route_rows,
    risk_next_rows,
)
from packages.research_core.pipeline.delivery_qa import (
    run_delivery_qa,
    _load_packets_for_qa,
    _has_no_removed_legacy_sections,
    _has_no_forbidden_html_patterns,
    _has_inline_style,
    _has_required_operator_sections,
    _has_gonogo_class,
    _has_voc_evidence_refs,
    _report_data_has_required_sections,
    _validate_report_data_sources,
    _extract_source_paths,
    _try_resolve_path,
    _validate_values_against_sources,
    _is_empty,
    _values_match,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Stage 7 analysis report from evidence packets.")
    parser.add_argument("run_dir", type=Path, help="Path to run directory (e.g. runs/20260623_加液马桶刷)")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    run_dir: Path = args.run_dir.expanduser().resolve()
    if not run_dir.is_dir():
        print(f"ERROR: run_dir not found: {run_dir}", file=sys.stderr)
        return 2

    analysis_dir = run_dir / "analysis"
    analysis_dir.mkdir(parents=True, exist_ok=True)

    packets = load_packets(run_dir)
    analysis = build_analysis_packet(run_dir, packets)

    report_seed_path = analysis_dir / "report_data.seed.json"
    report_data_path = analysis_dir / "report_data.json"
    product_name = _extract_product_name(run_dir)
    html_path = analysis_dir / f"{product_name}_分析报告.html"
    xlsx_path = analysis_dir / f"{product_name}_决策工具包.xlsx"

    # ── Step 1: Generate seed ───────────────────────────────────────────
    seed = seed_report_data_from_analysis(analysis)
    report_seed_path.write_text(json.dumps(seed, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote seed {report_seed_path}")

    # ── Step 2: Write analysis_packet ───────────────────────────────────
    analysis_packet_path = analysis_dir / "analysis_packet.json"
    analysis_packet_path.write_text(json.dumps(analysis, ensure_ascii=False, indent=2), encoding="utf-8")

    # ── Step 3: Check Report Generation Agent handoff ───────────────────
    judgment_path = analysis_dir / "integrated_operator_judgment.json"
    judgment = None
    if judgment_path.exists():
        judgment = json.loads(judgment_path.read_text(encoding="utf-8"))

    if not report_data_path.exists():
        print(f"REPORT DATA MISSING — Report Generation Agent must write: {report_data_path}")
        print("HTML/XLSX/QA SKIPPED — rerun this script after report_data.json and HTML exist")
        return 0

    if not html_path.exists():
        print(f"HTML MISSING — Report Generation Agent must write: {html_path}")
        print("XLSX/QA SKIPPED — rerun this script after the formal HTML report exists")
        return 0

    # ── Step 4: Generate XLSX decision workbook ─────────────────────────
    write_xlsx(xlsx_path, xlsx_sheets_from_report_data(report_data_path, judgment_path))
    print(f"Wrote {xlsx_path}")

    # ── Step 5: Run QA ──────────────────────────────────────────────────
    qa = run_delivery_qa(report_data_path, html_path, xlsx_path, analysis)
    qa_path = analysis_dir / "delivery_qa_result.json"
    qa_path.write_text(json.dumps(qa, ensure_ascii=False, indent=2), encoding="utf-8")

    # ── Step 6: Generate QA notes ───────────────────────────────────────
    _write_qa_notes(analysis_dir, qa, judgment)

    # ── Step 7: Audit run status ────────────────────────────────────────
    audit = audit_run_status(run_dir)
    audit_path = run_dir / "audit_run_status.json"
    audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {qa_path}")
    print(f"Wrote {audit_path}")

    if qa.get("status") != "pass":
        print(f"QA FAILED: {qa.get('failures', [])}", file=sys.stderr)
        return 1

    print("Stage 7 report delivery: PASS")
    return 0


def _write_qa_notes(analysis_dir: Path, qa: dict[str, Any], judgment: dict[str, Any] | None) -> None:
    """Generate qa_notes.md with human-readable QA summary."""
    lines = [
        "# QA 交付检查报告",
        "",
        f"**状态**: {qa.get('status', 'unknown')}",
        f"**QA 规则版本**: {qa.get('qa_rule_version', '')}",
        f"**生成时间**: {qa.get('generated_at', '')}",
        "",
        "## 检查项",
        "",
    ]
    checks = qa.get("checks") or {}
    for name, passed in sorted(checks.items()):
        if name in ("report_data_sources_note", "report_data_values_note",
                     "report_data_value_mismatches", "forbidden_html_hits",
                     "p0_blocker_hits"):
            continue
        icon = "通过" if passed else "未通过"
        lines.append(f"- [{icon}] {name}")

    lines.append("")
    lines.append("## QA 备注")
    lines.append("")
    if checks.get("report_data_sources_note"):
        lines.append(f"- 数据源: {checks['report_data_sources_note']}")
    if checks.get("report_data_values_note"):
        lines.append(f"- 值校验: {checks['report_data_values_note']}")
    if checks.get("p0_blocker_hits"):
        lines.append(f"- P0 阻断: {checks['p0_blocker_hits']}")

    if judgment:
        lines.append("")
        lines.append("## 集成判断摘要")
        lines.append("")
        lines.append(f"- 最终判词: {judgment.get('final_verdict', '')}")
        lines.append(f"- 置信度: {judgment.get('confidence', '')}")
        lines.append(f"- 推荐路线: {judgment.get('recommended_route', {}).get('name', '') if isinstance(judgment.get('recommended_route'), dict) else judgment.get('recommended_route', '')}")

    failures = qa.get("failures") or []
    if failures:
        lines.append("")
        lines.append("## 未通过项")
        lines.append("")
        for f in failures:
            lines.append(f"- {f}")

    notes_path = analysis_dir / "qa_notes.md"
    notes_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {notes_path}")


if __name__ == "__main__":
    raise SystemExit(main())
