#!/usr/bin/env python3
"""Build a Stage 7 market precheck report from market, search and VOC evidence.

This module is the thin orchestration layer. The heavy lifting lives in:
  - build_analysis_packet.py   evidence packets → analysis_packet
  - seed_report_data.py        analysis_packet  → report_data.json seed
  - xlsx_back_table.py         report_data.json → XLSX sheets
  - delivery_qa.py             QA checks (source_path + value consistency + HTML scan)
  - constants.py               shared constants
  - _utils.py                  shared helpers
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

from packages.report_renderer.xlsx_writer import write_xlsx
from packages.research_core.pipeline.audit_run_status import audit_run_status

# Re-export public API for backward compatibility
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
    _has_8_sections,
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
    report_data_path = analysis_dir / "report_data.json"
    xlsx_path = analysis_dir / (
        _extract_product_name(run_dir) + "_数据回表.xlsx"
    )
    html_path = analysis_dir / (
        _extract_product_name(run_dir) + "_分析报告.html"
    )

    is_seed = not report_data_path.exists()
    if is_seed:
        seed = seed_report_data_from_analysis(analysis)
        report_data_path.write_text(json.dumps(seed, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Wrote seed {report_data_path} (待 AI 增强后重跑脚本同步 XLSX)")

    analysis_packet_path = analysis_dir / "analysis_packet.json"
    analysis_packet_path.write_text(json.dumps(analysis, ensure_ascii=False, indent=2), encoding="utf-8")
    write_xlsx(xlsx_path, xlsx_sheets_from_report_data(report_data_path))

    if not html_path.exists():
        print(f"Wrote {report_data_path}")
        print(f"Wrote {xlsx_path}")
        print(f"HTML MISSING — AI must write: {html_path}")
        print("QA SKIPPED — 重跑本脚本以执行完整 QA 校验")
        return 0

    qa = run_delivery_qa(report_data_path, html_path, xlsx_path, analysis)
    qa_path = analysis_dir / "delivery_qa_result.json"
    qa_path.write_text(json.dumps(qa, ensure_ascii=False, indent=2), encoding="utf-8")

    audit = audit_run_status(run_dir)
    audit_path = run_dir / "audit_run_status.json"
    audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {qa_path}")
    print(f"Wrote {audit_path}")

    return 0 if qa.get("status") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
