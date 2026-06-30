#!/usr/bin/env python3
"""Stage 6 产出后契约校验：检查 evidence packet 的数据结构完整性。

在 Agent 产出 evidence packet 后立即运行，确保：
  - evidence_items[].facts 元素全是 dict（无裸 string）
  - route_refs 覆盖 route_matrix_confirm.json 中的所有保留路线
  - 必填顶层字段齐全

校验失败 → 打回 Stage 6 Agent 修复，不进入 Stage 7。

Usage:
  python3 scripts/validate_evidence_packet.py <run_dir> [--packet market_structure|search_demand]
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

CONTRACT_REF = "references/contracts/deep_evidence.md#evidence-packet-必填顶层字段"


def _check_top_level_fields(packet: dict[str, Any], packet_name: str) -> list[ValidatorError]:
    """检查 evidence packet 必填顶层字段。"""
    required = [
        ("schema_version", "string", '"p4-deep-contract-v1"'),
        ("packet_id", "string", f'"{packet_name}_evidence"'),
        ("run_id", "string", None),
        ("primary_source", "string", '"sellersprite" 或 "sorftime"'),
        ("evidence_items", "list[dict]", "至少 1 条"),
        ("route_refs", "list[string]", None),
        ("selected_routes", "list[string]", None),
        ("data_gaps", "list[dict]", None),
        ("confidence", "string", '"high" / "medium" / "low"'),
    ]
    errors: list[ValidatorError] = []
    for field, expected_type, expected_val in required:
        if field not in packet:
            errors.append(ValidatorError(
                code="MISSING_FIELD",
                field_path=f"{packet_name}.{field}",
                message=f"缺少必填字段: {field}",
                expected=expected_val or expected_type,
                contract_ref=CONTRACT_REF,
                fix_hint=f"在 {packet_name}_evidence_packet.json 中添加 `\"{field}\"` 字段，类型为 {expected_type}",
            ))
        elif field == "evidence_items":
            if not isinstance(packet[field], list):
                errors.append(ValidatorError(
                    code="TYPE_ERROR",
                    field_path=f"{packet_name}.evidence_items",
                    message="evidence_items 必须是 list",
                    expected="list[dict]",
                    actual=type(packet[field]).__name__,
                    contract_ref=CONTRACT_REF,
                    fix_hint="将 evidence_items 改为数组格式: `[{...}, {...}]`",
                ))
            elif len(packet[field]) == 0:
                errors.append(ValidatorError(
                    code="EMPTY_VALUE",
                    field_path=f"{packet_name}.evidence_items",
                    message="evidence_items 为空——Agent 未填充证据",
                    expected="至少 1 条 evidence_item",
                    contract_ref=CONTRACT_REF,
                    fix_hint="至少填充 1 条 evidence_item，每条含 item_type + facts + route_refs",
                ))
    return errors


def _check_facts_structure(evidence_items: list[Any], packet_name: str) -> list[ValidatorError]:
    """检查 evidence_items 中 facts 的结构完整性。"""
    errors: list[ValidatorError] = []
    for ei_idx, item in enumerate(evidence_items):
        field_prefix = f"{packet_name}.evidence_items[{ei_idx}]"
        if not isinstance(item, dict):
            errors.append(ValidatorError(
                code="TYPE_ERROR",
                field_path=field_prefix,
                message=f"evidence_items[{ei_idx}] 不是 dict",
                expected="dict",
                actual=type(item).__name__,
                contract_ref=CONTRACT_REF,
                fix_hint=f"将 evidence_items[{ei_idx}] 改为 dict 格式，含 item_type/facts/route_refs",
            ))
            continue
        facts = item.get("facts")
        if facts is None:
            continue
        if isinstance(facts, dict):
            if len(facts) == 0:
                errors.append(ValidatorError(
                    code="EMPTY_VALUE",
                    field_path=f"{field_prefix}.facts",
                    message="facts 为空 dict——Agent 未填充证据",
                    expected="至少 1 个字段的 dict",
                    contract_ref="references/contracts/deep_evidence.md#evidence_items-每条",
                    fix_hint="填充 facts 内容，写入从 MCP 工具采集到的实际数据",
                ))
        elif isinstance(facts, list):
            non_dict_count = sum(1 for f in facts if not isinstance(f, dict))
            if non_dict_count > 0:
                errors.append(ValidatorError(
                    code="TYPE_ERROR",
                    field_path=f"{field_prefix}.facts",
                    message=f"facts 列表包含 {non_dict_count} 个非 dict 元素",
                    expected="list[dict]",
                    actual=f"{non_dict_count} 个非 dict / {len(facts)} 个总计",
                    contract_ref="references/contracts/deep_evidence.md#evidence_items-每条",
                    fix_hint="确保 facts 数组中每个元素都是 dict 类型",
                ))
            if len(facts) == 0:
                errors.append(ValidatorError(
                    code="EMPTY_VALUE",
                    field_path=f"{field_prefix}.facts",
                    message="facts 为空 list——Agent 未填充证据",
                    expected="至少 1 个 dict 元素",
                    contract_ref="references/contracts/deep_evidence.md#evidence_items-每条",
                    fix_hint="在 facts 数组中至少添加 1 条证据记录",
                ))
        else:
            errors.append(ValidatorError(
                code="TYPE_ERROR",
                field_path=f"{field_prefix}.facts",
                message=f"facts 类型异常: {type(facts).__name__}",
                expected="dict 或 list[dict]",
                actual=type(facts).__name__,
                contract_ref="references/contracts/deep_evidence.md#evidence_items-每条",
                fix_hint="facts 必须是 dict 或 list[dict]",
            ))
    return errors


def _check_route_coverage(
    packet: dict[str, Any], run_dir: Path, packet_name: str
) -> list[ValidatorError]:
    """检查 packet 的 route_refs 是否覆盖所有保留路线。"""
    route_matrix_path = run_dir / "route_matrix_confirm.json"
    if not route_matrix_path.exists():
        return [ValidatorError(
            code="SKIP",
            field_path="route_matrix_confirm.json",
            message="route_matrix_confirm.json 不存在，跳过路线覆盖检查",
            severity="WARN",
            fix_hint="确保 Stage 5 已生成 route_matrix_confirm.json",
        )]

    route_matrix = load_json(route_matrix_path)
    all_routes = route_matrix.get("route_matrix") or []
    selected = [
        r for r in all_routes
        if isinstance(r, dict) and r.get("selection_status") not in ("excluded", "rejected")
        and r.get("status") not in ("excluded", "rejected")
    ]
    if not selected:
        return []

    selected_ids = {
        first_text(r.get("route_id") or r.get("name") or r.get("route_name") or "").casefold()
        for r in selected
    }
    selected_ids.discard("")
    route_refs = {str(r).casefold() for r in (packet.get("route_refs") or []) if r}
    selected_routes = {str(r).casefold() for r in (packet.get("selected_routes") or []) if r}

    covered = route_refs | selected_routes
    missing = selected_ids - covered
    if missing:
        return [ValidatorError(
            code="ROUTE_NOT_COVERED",
            field_path=f"{packet_name}.route_refs",
            message=f"未覆盖以下保留路线: {sorted(missing)}",
            expected=f"覆盖 {sorted(selected_ids)}",
            actual=f"已覆盖 {sorted(covered)}，缺失 {sorted(missing)}",
            contract_ref="references/contracts/deep_evidence.md#evidence-packet-必填顶层字段",
            fix_hint=(
                f"为每条缺失路线添加 evidence_item，"
                f"并在 route_refs 中包含: {sorted(missing)}"
            ),
        )]
    return []


def validate_evidence_packet(
    run_dir: Path, packet_name: str
) -> tuple[bool, list[ValidatorError]]:
    """验证单个 evidence packet。返回 (pass, errors)。"""
    packet_path = None
    if packet_name == "market_structure":
        packet_path = run_dir / "market_structure" / "market_structure_evidence_packet.json"
    elif packet_name == "search_demand":
        packet_path = run_dir / "search_demand" / "search_demand_evidence_packet.json"
    else:
        return False, [ValidatorError(
            code="INVALID_PACKET",
            field_path="--packet",
            message=f"未知 packet 类型: {packet_name}",
            expected="market_structure 或 search_demand",
        )]

    if not packet_path.exists():
        return False, [ValidatorError(
            code="FILE_NOT_FOUND",
            field_path=str(packet_path),
            message=f"文件不存在: {packet_path}",
            fix_hint="Agent 必须用 Write 工具写入 evidence packet 到正确路径",
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
    all_errors.extend(_check_top_level_fields(packet, packet_name))
    all_errors.extend(
        _check_facts_structure(packet.get("evidence_items") or [], packet_name)
    )
    all_errors.extend(_check_route_coverage(packet, run_dir, packet_name))

    return len(all_errors) == 0, all_errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Stage 6 evidence packet 契约校验"
    )
    parser.add_argument("run_dir", type=Path, help="Run 目录路径")
    parser.add_argument(
        "--packet",
        choices=["market_structure", "search_demand"],
        default=None,
        help="仅校验指定 packet（不指定则校验全部）",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="以 JSON 格式输出结构化错误",
    )
    args = parser.parse_args(argv)
    run_dir: Path = args.run_dir.expanduser().resolve()
    if not run_dir.is_dir():
        print(f"ERROR: run_dir 不存在: {run_dir}", file=sys.stderr)
        return 2

    packets = args.packet
    if packets is None:
        packets = ["market_structure", "search_demand"]

    if isinstance(packets, str):
        packets = [packets]

    all_pass = True
    all_errors: list[ValidatorError] = []
    for pkt in packets:
        ok, errors = validate_evidence_packet(run_dir, pkt)
        all_errors.extend(errors)
        if ok:
            print(f"[PASS] {pkt}_evidence_packet 契约校验通过")
        else:
            all_pass = False
            print(f"[FAIL] {pkt}_evidence_packet 契约校验失败 ({len(errors)} 个问题):")
            print(format_human(errors))
            print()

    if all_pass:
        print("\n所有 evidence packet 校验通过，可进入 Stage 7。")
    else:
        # 输出 agent replay 格式到 stderr，方便直接拷贝给 Agent
        print(
            format_agent_replay(all_errors, "Stage 6 深挖证据包"),
            file=sys.stderr,
        )

    if args.json:
        from packages.research_core.pipeline._validator_format import format_json
        print(format_json(all_errors))

    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
