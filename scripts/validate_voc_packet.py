#!/usr/bin/env python3
"""Stage 8 产出后契约校验：检查 VOC evidence packet 的数据结构完整性。

在 VOC Evidence Agent 产出 voc_evidence_packet.json 后立即运行，确保：
  - pain_points 结构完整（≥3 条评论提及 + review_id + quote）
  - 每条保留路线至少 2 个 ASIN 覆盖
  - execution_provenance 正确（executed_by_agent=true, execution_mode="agent"）
  - spec_requirement / unmet_needs / differentiation_opportunities 结构合规
  - 必填顶层字段齐全

校验失败 → 打回 VOC Evidence Agent 修复，不进入 Stage 9。

Usage:
  python3 scripts/validate_voc_packet.py <run_dir>
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from packages.research_core.pipeline._utils import first_text, load_json

VOC_PACKET_PATH = "review_voc/voc_evidence_packet.json"
ROUTE_MATRIX_PATH = "route_matrix_confirm.json"


def _check_top_level_fields(packet: dict[str, Any]) -> list[str]:
    """检查 VOC packet 必填顶层字段。"""
    required = [
        "schema_version", "packet_id", "run_id",
        "pain_points", "spec_requirement", "unmet_needs",
        "differentiation_opportunities", "route_coverage",
        "execution_provenance", "data_gaps", "confidence",
    ]
    errors: list[str] = []
    for field in required:
        if field not in packet:
            errors.append(f"voc_evidence_packet 缺少必填字段: {field}")
    for list_field in ("pain_points", "unmet_needs", "differentiation_opportunities", "data_gaps"):
        val = packet.get(list_field)
        if val is not None and not isinstance(val, list):
            errors.append(f"{list_field} 必须是 list，实际为 {type(val).__name__}")
    return errors


def _check_pain_points(pain_points: list[Any]) -> list[str]:
    """检查痛点结构: 每个痛点必须有 evidence_refs 带 review_id + quote。"""
    errors: list[str] = []
    if not pain_points:
        errors.append("pain_points 为空——VOC Agent 未提取痛点")
        return errors

    for i, pp in enumerate(pain_points):
        if not isinstance(pp, dict):
            errors.append(f"pain_points[{i}] 不是 dict，是 {type(pp).__name__}")
            continue

        # 必填字段
        for field in ("pain_point_id", "category", "priority", "description"):
            if not pp.get(field):
                errors.append(f"pain_points[{i}] 缺少字段: {field}")

        # 优先级校验
        priority = pp.get("priority", "")
        if priority not in ("P0", "P1", "P2", ""):
            errors.append(f"pain_points[{i}].priority 值无效: '{priority}'（应为 P0/P1/P2）")

        # evidence_refs 溯源
        refs = pp.get("evidence_refs", [])
        if not isinstance(refs, list) or len(refs) == 0:
            errors.append(f"pain_points[{i}] 缺少 evidence_refs——每个痛点必须溯源到具体评论")
            continue

        has_review_id = False
        has_quote = False
        for j, ref in enumerate(refs):
            if not isinstance(ref, dict):
                errors.append(f"pain_points[{i}].evidence_refs[{j}] 不是 dict")
                continue
            if ref.get("review_id"):
                has_review_id = True
            if ref.get("quote"):
                has_quote = True

        if not has_review_id:
            errors.append(f"pain_points[{i}].evidence_refs 中缺少 review_id")
        if not has_quote:
            errors.append(f"pain_points[{i}].evidence_refs 中缺少 quote（评论原文引用）")

        # 提及频次
        mention_count = pp.get("mention_count", 0)
        if isinstance(mention_count, (int, float)) and mention_count < 3:
            errors.append(
                f"pain_points[{i}] mention_count={mention_count} < 3——"
                f"痛点至少需要 3 条评论提及"
            )

    return errors


def _check_spec_requirement(spec: dict[str, Any] | None) -> list[str]:
    """检查 spec_requirement 结构。"""
    errors: list[str] = []
    if spec is None:
        errors.append("spec_requirement 缺失——VOC Agent 应推导产品规格建议")
        return errors
    if not isinstance(spec, dict):
        errors.append(f"spec_requirement 应为 dict，实际为 {type(spec).__name__}")
        return errors

    for field in ("spec_requirement", "sample_tests", "listing_risk_note"):
        if field not in spec:
            errors.append(f"spec_requirement 缺少字段: {field}")
    return errors


def _check_execution_provenance(ep: dict[str, Any] | None) -> list[str]:
    """检查 execution_provenance 必须标记为真实 Agent 执行。"""
    errors: list[str] = []
    if ep is None:
        errors.append("execution_provenance 缺失")
        return errors
    if not isinstance(ep, dict):
        errors.append(f"execution_provenance 应为 dict，实际为 {type(ep).__name__}")
        return errors

    if ep.get("executed_by_agent") is not True:
        errors.append(
            "execution_provenance.executed_by_agent 必须为 true——"
            "VOC 分析必须由 VOC Evidence Agent 执行，禁止主 Agent 代跑"
        )
    if ep.get("execution_mode") != "agent":
        errors.append(
            f"execution_provenance.execution_mode 应为 'agent'，"
            f"实际为 '{ep.get('execution_mode')}'——禁止标记为 serial_fallback"
        )
    if not ep.get("agent_role"):
        errors.append("execution_provenance.agent_role 缺失")
    return errors


def _check_route_coverage(
    route_coverage: list[Any] | None, run_dir: Path
) -> list[str]:
    """检查每条保留路线至少 2 个 ASIN 覆盖。"""
    errors: list[str] = []
    route_matrix_path = run_dir / ROUTE_MATRIX_PATH
    if not route_matrix_path.exists():
        return [f"[SKIP] {ROUTE_MATRIX_PATH} 不存在，跳过路线覆盖检查"]

    route_matrix = load_json(route_matrix_path)
    all_routes = route_matrix.get("route_matrix") or []
    selected = [
        r for r in all_routes
        if isinstance(r, dict)
        and r.get("selection_status") not in ("excluded", "rejected")
        and r.get("status") not in ("excluded", "rejected")
    ]
    if not selected:
        return []

    selected_ids = {
        first_text(r.get("route_id") or r.get("name") or r.get("route_name") or "").casefold()
        for r in selected
    }
    selected_ids.discard("")

    if route_coverage is None:
        # 无法按字段检查，只检查 route_matrix 确认的路线是否都有覆盖
        return []

    # route_coverage 应包含每条保留路线的 ASIN 覆盖信息
    covered: dict[str, int] = {}
    for entry in (route_coverage or []):
        if not isinstance(entry, dict):
            continue
        rid = first_text(entry.get("route_id") or entry.get("route_name") or "").casefold()
        if not rid:
            continue
        asin_count = len(entry.get("asins") or entry.get("reference_asins") or [])
        covered[rid] = asin_count

    for rid in selected_ids:
        count = covered.get(rid, 0)
        if count == 0:
            errors.append(
                f"路线 '{rid}' 无 ASIN 覆盖——运营需补充评论导出"
            )
        elif count == 1:
            errors.append(
                f"路线 '{rid}' 仅 1 个 ASIN——置信度将标记为 low，"
                f"建议补充 ≥ 2 个 ASIN 评论"
            )

    return errors


def validate_voc_packet(run_dir: Path) -> tuple[bool, list[str]]:
    """验证 VOC evidence packet。返回 (pass, errors)。"""
    packet_path = run_dir / VOC_PACKET_PATH
    if not packet_path.exists():
        return False, [f"文件不存在: {packet_path}"]

    try:
        packet = load_json(packet_path)
    except Exception as e:
        return False, [f"JSON 解析失败: {e}"]

    all_errors: list[str] = []
    all_errors.extend(_check_top_level_fields(packet))
    all_errors.extend(_check_pain_points(packet.get("pain_points") or []))
    all_errors.extend(_check_spec_requirement(packet.get("spec_requirement")))
    all_errors.extend(_check_execution_provenance(packet.get("execution_provenance")))
    all_errors.extend(
        _check_route_coverage(packet.get("route_coverage"), run_dir)
    )

    return len(all_errors) == 0, all_errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Stage 8 VOC evidence packet 契约校验"
    )
    parser.add_argument("run_dir", type=Path, help="Run 目录路径")
    args = parser.parse_args(argv)
    run_dir: Path = args.run_dir.expanduser().resolve()
    if not run_dir.is_dir():
        print(f"ERROR: run_dir 不存在: {run_dir}", file=sys.stderr)
        return 2

    ok, errors = validate_voc_packet(run_dir)
    if ok:
        print("[PASS] voc_evidence_packet 契约校验通过，可进入 Stage 9。")
    else:
        print(f"[FAIL] voc_evidence_packet 契约校验失败 ({len(errors)} 个问题):")
        for err in errors:
            print(f"  - {err}")
        print("\n请打回 VOC Evidence Agent 修复以上问题后重新校验。", file=sys.stderr)

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
