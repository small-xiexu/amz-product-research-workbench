#!/usr/bin/env python3
"""Stage 8 产出后契约校验：检查 VOC evidence packet 的数据结构完整性。

在 VOC Evidence Agent 产出 voc_evidence_packet.json 后立即运行，确保：
  - pain_points 结构完整（≥3 条评论提及 + review_id + quote）
  - 每条保留路线至少 2 个 ASIN 覆盖
  - execution_provenance 正确（executed_by_agent=true, execution_mode="agent"）
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
from packages.research_core.pipeline._validator_format import (
    ValidatorError,
    format_human,
    format_agent_replay,
)

VOC_PACKET_PATH = "review_voc/voc_evidence_packet.json"
ROUTE_MATRIX_PATH = "route_matrix_confirm.json"
CONTRACT_REF = "references/contracts/voc_evidence.md"


def _check_top_level_fields(packet: dict[str, Any]) -> list[ValidatorError]:
    """检查 VOC packet 必填顶层字段。"""
    required = [
        ("schema_version", "string", '"p5-voc-evidence-v1"'),
        ("packet_id", "string", '"voc_evidence_packet"'),
        ("run_id", "string", None),
        ("pain_points", "list[dict]", "≥ 1，每条 ≥ 3 条评论引用"),
        ("route_refs", "list[string]", "覆盖所有 selected_routes"),
        ("execution_provenance", "dict", 'executed_by_agent=true, execution_mode="agent"'),
        ("confidence", "string", '"high" / "medium" / "low"'),
    ]
    errors: list[ValidatorError] = []
    for field, expected_type, expected_val in required:
        if field not in packet:
            errors.append(ValidatorError(
                code="MISSING_FIELD",
                field_path=f"voc_evidence_packet.{field}",
                message=f"缺少必填字段: {field}",
                expected=expected_val or expected_type,
                contract_ref=CONTRACT_REF + "#必填顶层字段",
                fix_hint=f"添加 `\"{field}\"` 字段，类型为 {expected_type}",
            ))
    for list_field in ("pain_points", "route_refs"):
        val = packet.get(list_field)
        if val is not None and not isinstance(val, list):
            errors.append(ValidatorError(
                code="TYPE_ERROR",
                field_path=f"voc_evidence_packet.{list_field}",
                message=f"{list_field} 必须是 list",
                expected="list",
                actual=type(val).__name__,
                contract_ref=CONTRACT_REF + "#必填顶层字段",
                fix_hint=f"将 {list_field} 改为数组格式",
            ))
    return errors


def _check_pain_points(pain_points: list[Any]) -> list[ValidatorError]:
    """检查痛点结构: 每个痛点必须有 evidence_refs 带 review_id + quote。"""
    errors: list[ValidatorError] = []
    if not pain_points:
        errors.append(ValidatorError(
            code="EMPTY_VALUE",
            field_path="voc_evidence_packet.pain_points",
            message="pain_points 为空——VOC Agent 未提取痛点",
            expected="至少 1 个 pain_point",
            contract_ref=CONTRACT_REF + "#pain_points-每条必填",
            fix_hint="从 normalized_reviews 中提取至少 1 个痛点，每个带 ≥ 3 条 evidence_refs",
        ))
        return errors

    for i, pp in enumerate(pain_points):
        field_prefix = f"pain_points[{i}]"
        if not isinstance(pp, dict):
            errors.append(ValidatorError(
                code="TYPE_ERROR",
                field_path=f"voc_evidence_packet.{field_prefix}",
                message=f"pain_points[{i}] 不是 dict",
                expected="dict",
                actual=type(pp).__name__,
                contract_ref=CONTRACT_REF + "#pain_points-每条必填",
                fix_hint=f"将 pain_points[{i}] 改为 dict 对象",
            ))
            continue

        for field in ("pain_point_id", "dimension", "priority", "description"):
            if not pp.get(field):
                errors.append(ValidatorError(
                    code="MISSING_FIELD",
                    field_path=f"voc_evidence_packet.{field_prefix}.{field}",
                    message=f"缺少字段: {field}",
                    contract_ref=CONTRACT_REF + "#pain_points-每条必填",
                    fix_hint=f"在 pain_points[{i}] 中添加 `\"{field}\"`",
                ))

        priority = pp.get("priority", "")
        if priority not in ("P0", "P1", "P2", ""):
            errors.append(ValidatorError(
                code="INVALID_ENUM",
                field_path=f"voc_evidence_packet.{field_prefix}.priority",
                message=f"priority 值无效: '{priority}'",
                expected="{P0, P1, P2}",
                actual=str(priority),
                contract_ref=CONTRACT_REF + "#pain_points-每条必填",
                fix_hint="将 priority 改为 P0 / P1 / P2 之一",
            ))

        refs = pp.get("evidence_refs", [])
        if not isinstance(refs, list) or len(refs) == 0:
            errors.append(ValidatorError(
                code="EMPTY_VALUE",
                field_path=f"voc_evidence_packet.{field_prefix}.evidence_refs",
                message="缺少 evidence_refs——每个痛点必须溯源到具体评论",
                expected="list[dict]，≥ 3 条，每条含 review_id + quote",
                contract_ref=CONTRACT_REF + "#evidence_refs-每条必填",
                fix_hint=f"为 pain_points[{i}] 添加 ≥ 3 条 evidence_refs，每条含 review_id 和 quote",
            ))
            continue

        has_review_id = False
        has_quote = False
        for j, ref in enumerate(refs):
            if not isinstance(ref, dict):
                errors.append(ValidatorError(
                    code="TYPE_ERROR",
                    field_path=f"voc_evidence_packet.{field_prefix}.evidence_refs[{j}]",
                    message=f"evidence_refs[{j}] 不是 dict",
                    expected="dict",
                    actual=type(ref).__name__,
                    fix_hint=f"将 evidence_refs[{j}] 改为 `{{\"review_id\": \"...\", \"quote\": \"...\"}}`",
                ))
                continue
            if ref.get("review_id"):
                has_review_id = True
            if ref.get("quote"):
                has_quote = True

        if not has_review_id:
            errors.append(ValidatorError(
                code="MISSING_FIELD",
                field_path=f"voc_evidence_packet.{field_prefix}.evidence_refs",
                message="evidence_refs 中缺少 review_id",
                expected="每条 ref 含 review_id 字段",
                contract_ref=CONTRACT_REF + "#evidence_refs-每条必填",
                fix_hint="确保 evidence_refs 中至少 1 条含 review_id",
            ))
        if not has_quote:
            errors.append(ValidatorError(
                code="MISSING_FIELD",
                field_path=f"voc_evidence_packet.{field_prefix}.evidence_refs",
                message="evidence_refs 中缺少 quote（评论原文引用）",
                expected="每条 ref 含 quote 字段",
                contract_ref=CONTRACT_REF + "#evidence_refs-每条必填",
                fix_hint="确保 evidence_refs 中至少 1 条含 quote 原文",
            ))

        mention_count = pp.get("mention_count", 0)
        if isinstance(mention_count, (int, float)) and mention_count < 3:
            errors.append(ValidatorError(
                code="VALUE_RANGE",
                field_path=f"voc_evidence_packet.{field_prefix}.mention_count",
                message=f"mention_count={mention_count} < 3",
                expected="≥ 3",
                actual=str(mention_count),
                contract_ref=CONTRACT_REF + "#禁止事项",
                fix_hint="该痛点至少需要 3 条评论提及，否则降低到 P2 或合并到相似痛点",
            ))

    return errors


def _check_execution_provenance(ep: dict[str, Any] | None) -> list[ValidatorError]:
    """检查 execution_provenance 必须标记为真实 Agent 执行。"""
    if ep is None:
        return [ValidatorError(
            code="MISSING_FIELD",
            field_path="voc_evidence_packet.execution_provenance",
            message="execution_provenance 缺失",
            expected='{"executed_by_agent": true, "execution_mode": "agent", ...}',
            contract_ref=CONTRACT_REF + "#execution_provenance-必填",
            fix_hint="添加 execution_provenance，标记 executed_by_agent=true, execution_mode='agent'",
        )]
    if not isinstance(ep, dict):
        return [ValidatorError(
            code="TYPE_ERROR",
            field_path="voc_evidence_packet.execution_provenance",
            message="execution_provenance 不是 dict",
            expected="dict",
            actual=type(ep).__name__,
            fix_hint="将 execution_provenance 改为 dict 格式",
        )]

    errors: list[ValidatorError] = []
    if ep.get("executed_by_agent") is not True:
        errors.append(ValidatorError(
            code="INVALID_VALUE",
            field_path="execution_provenance.executed_by_agent",
            message="executed_by_agent 必须为 true——VOC 分析必须由 Agent 执行",
            expected="true",
            actual=str(ep.get("executed_by_agent")),
            contract_ref=CONTRACT_REF + "#execution_provenance-必填",
            fix_hint="设置 executed_by_agent=true，禁止主 Agent 代跑 VOC 分析",
        ))
    if ep.get("execution_mode") != "agent":
        errors.append(ValidatorError(
            code="INVALID_ENUM",
            field_path="execution_provenance.execution_mode",
            message=f"execution_mode 应为 'agent'，实际为 '{ep.get('execution_mode')}'",
            expected="agent",
            actual=str(ep.get("execution_mode")),
            contract_ref=CONTRACT_REF + "#禁止事项",
            fix_hint="设置 execution_mode='agent'，禁止标记为 serial_fallback",
        ))
    if not ep.get("agent_role"):
        errors.append(ValidatorError(
            code="MISSING_FIELD",
            field_path="execution_provenance.agent_role",
            message="agent_role 缺失",
            expected='"VOC Evidence Agent"',
            fix_hint='添加 "agent_role": "VOC Evidence Agent"',
        ))
    return errors


def _check_route_coverage(
    route_refs: list[str], run_dir: Path
) -> list[ValidatorError]:
    """检查 route_refs 覆盖所有保留路线。"""
    route_matrix_path = run_dir / ROUTE_MATRIX_PATH
    if not route_matrix_path.exists():
        return [ValidatorError(
            code="SKIP",
            field_path=ROUTE_MATRIX_PATH,
            message=f"{ROUTE_MATRIX_PATH} 不存在，跳过路线覆盖检查",
            severity="WARN",
        )]

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

    route_refs_set = {str(r).casefold() for r in (route_refs or []) if r}
    missing = selected_ids - route_refs_set
    if missing:
        return [ValidatorError(
            code="ROUTE_NOT_COVERED",
            field_path="voc_evidence_packet.route_refs",
            message=f"未覆盖以下保留路线: {sorted(missing)}",
            expected=f"覆盖 {sorted(selected_ids)}",
            actual=f"已覆盖 {sorted(route_refs_set)}，缺失 {sorted(missing)}",
            contract_ref=CONTRACT_REF + "#禁止事项",
            fix_hint=(
                f"不得以'量太少'为由跳过路线。为缺失路线分析评论，"
                f"并在 route_refs 中补充: {sorted(missing)}"
            ),
        )]
    return []


def validate_voc_packet(run_dir: Path) -> tuple[bool, list[ValidatorError]]:
    """验证 VOC evidence packet。返回 (pass, errors)。"""
    packet_path = run_dir / VOC_PACKET_PATH
    if not packet_path.exists():
        return False, [ValidatorError(
            code="FILE_NOT_FOUND",
            field_path=str(packet_path),
            message=f"文件不存在: {packet_path}",
            fix_hint="VOC Evidence Agent 必须用 Write 工具写入 voc_evidence_packet.json",
        )]

    try:
        packet = load_json(packet_path)
    except json.JSONDecodeError as e:
        return False, [ValidatorError(
            code="JSON_SYNTAX_ERROR",
            field_path=f"{packet_path}:{e.lineno}:{e.colno}",
            message=f"JSON 语法错误: {e.msg}",
            fix_hint="检查该位置附近是否有未转义的双引号、中文引号、或多余的逗号",
        )]
    except Exception as e:
        return False, [ValidatorError(
            code="JSON_PARSE_ERROR",
            field_path=str(packet_path),
            message=f"JSON 解析失败: {e}",
        )]

    all_errors: list[ValidatorError] = []
    all_errors.extend(_check_top_level_fields(packet))
    all_errors.extend(_check_pain_points(packet.get("pain_points") or []))
    all_errors.extend(_check_execution_provenance(packet.get("execution_provenance")))
    all_errors.extend(
        _check_route_coverage(packet.get("route_refs") or [], run_dir)
    )

    return len(all_errors) == 0, all_errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Stage 8 VOC evidence packet 契约校验"
    )
    parser.add_argument("run_dir", type=Path, help="Run 目录路径")
    parser.add_argument("--json", action="store_true", help="JSON 格式输出")
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
        print(format_human(errors))
        print()
        print(
            format_agent_replay(errors, "Stage 8 VOC 评论分析"),
            file=sys.stderr,
        )

    if args.json:
        from packages.research_core.pipeline._validator_format import format_json
        print(format_json(errors))

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
