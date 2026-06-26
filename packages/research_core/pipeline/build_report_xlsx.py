#!/usr/bin/env python3
"""Stage 12 post-Agent: Build XLSX decision workbook and run delivery QA.

Prerequisites: report_data.json and HTML must already exist (written by
Report Generation Agent in Stage 12).

Output: 决策工具包.xlsx + delivery_qa_result.json + qa_notes.md
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

from packages.report_renderer.xlsx_writer import write_xlsx
from packages.research_core.pipeline.audit_run_status import audit_run_status
from packages.research_core.pipeline.build_analysis_packet import (
    load_packets,
    _extract_product_name,
    build_analysis_packet,
)
from packages.research_core.pipeline.xlsx_back_table import (
    xlsx_sheets_from_report_data,
)
from packages.research_core.pipeline.delivery_qa import (
    run_delivery_qa,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build XLSX workbook and run delivery QA (Stage 12 post-Agent)."
    )
    parser.add_argument(
        "run_dir", type=Path,
        help="Path to run directory (e.g. runs/20260623_加液马桶刷)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    run_dir: Path = args.run_dir.expanduser().resolve()
    if not run_dir.is_dir():
        print(f"ERROR: run_dir not found: {run_dir}", file=sys.stderr)
        return 2

    analysis_dir = run_dir / "analysis"
    product_name = _extract_product_name(run_dir)
    report_data_path = analysis_dir / "report_data.json"
    html_path = analysis_dir / f"{product_name}_分析报告.html"
    xlsx_path = analysis_dir / f"{product_name}_决策工具包.xlsx"
    judgment_path = analysis_dir / "integrated_operator_judgment.json"

    # ── Prerequisite checks ──────────────────────────────────────────
    if not report_data_path.exists():
        print(
            f"ERROR: report_data.json missing — "
            f"Report Generation Agent must write: {report_data_path}",
            file=sys.stderr,
        )
        return 3

    if not html_path.exists():
        print(
            f"ERROR: HTML missing — "
            f"Report Generation Agent must write: {html_path}",
            file=sys.stderr,
        )
        return 3

    # ── Load analysis for QA ─────────────────────────────────────────
    packets = load_packets(run_dir)
    analysis = build_analysis_packet(run_dir, packets)

    # ── Generate XLSX ────────────────────────────────────────────────
    write_xlsx(xlsx_path, xlsx_sheets_from_report_data(report_data_path, judgment_path))
    print(f"Wrote {xlsx_path}")

    # ── Run QA ───────────────────────────────────────────────────────
    qa = run_delivery_qa(report_data_path, html_path, xlsx_path, analysis)
    qa_path = analysis_dir / "delivery_qa_result.json"
    qa_path.write_text(json.dumps(qa, ensure_ascii=False, indent=2), encoding="utf-8")

    # ── QA notes ─────────────────────────────────────────────────────
    judgment = None
    if judgment_path.exists():
        judgment = json.loads(judgment_path.read_text(encoding="utf-8"))
    _write_qa_notes(analysis_dir, qa, judgment)

    # ── Audit ────────────────────────────────────────────────────────
    audit = audit_run_status(run_dir)
    audit_path = run_dir / "audit_run_status.json"
    audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {qa_path}")
    print(f"Wrote {audit_path}")

    if qa.get("status") != "pass":
        print(f"QA FAILED — check failures and retry accordingly", file=sys.stderr)
        classification = qa.get("failure_classification") or {}
        for cls_key, cls_info in classification.items():
            target = cls_info.get("retry_target", "?")
            stage = cls_info.get("retry_stage", "?")
            print(f"  [{cls_key}] → retry {stage} ({target})", file=sys.stderr)
            for fn in cls_info.get("failures", []):
                print(f"    - {fn}", file=sys.stderr)
        return 1

    print("Report delivery: PASS")
    return 0


def _write_qa_notes(
    analysis_dir: Path, qa: dict[str, Any], judgment: dict[str, Any] | None
) -> None:
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
        if name in (
            "report_data_sources_note", "report_data_values_note",
            "report_data_value_mismatches", "forbidden_html_hits",
            "p0_blocker_hits",
        ):
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

    # Failure classification
    classification = qa.get("failure_classification") or {}
    if classification:
        lines.append("")
        lines.append("## 失败分类与打回目标")
        lines.append("")
        for cls_key, cls_info in classification.items():
            label_map = {
                "analysis": "分析错误 → retry Stage 10 (Lead Operator Agent)",
                "rendering": "渲染错误 → retry Stage 12 (Report Generation Agent)",
                "data": "数据错误 → retry Stage 11 (build_report_seed)",
            }
            lines.append(f"### {label_map.get(cls_key, cls_key)}")
            for fn in cls_info.get("failures", []):
                lines.append(f"- {fn}")

    if judgment:
        lines.append("")
        lines.append("## 集成判断摘要")
        lines.append("")
        lines.append(f"- 最终判词: {judgment.get('final_verdict', '')}")
        lines.append(f"- 置信度: {judgment.get('confidence', '')}")

    notes_path = analysis_dir / "qa_notes.md"
    notes_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
