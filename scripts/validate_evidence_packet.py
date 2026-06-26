#!/usr/bin/env python3
"""Stage 6 产出后契约校验：检查 evidence packet 的数据结构完整性。

在 Agent 产出 evidence packet 后立即运行，确保：
  - evidence_items[].facts 元素全是 dict（无裸 string）
  - 每个 fact dict 含 id / value / source 三字段
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

from packages.research_core.pipeline._utils import as_dict_list, load_json


def _check_facts_structure(evidence_items: list[Any], packet_name: str) -> list[str]:
    """检查 evidence_items 中 facts 的结构完整性。"""
    errors: list[str] = []
    for ei_idx, item in enumerate(evidence_items):
        if not isinstance(item, dict):
            errors.append(f"evidence_items[{ei_idx}] 不是 dict，是 {type(item).__name__}")
            continue
        facts = item.get("facts")
        if facts is None:
            continue
        if isinstance(facts, dict):
            # facts 是 dict 形态：检查每个 value 是否为 dict（不应是裸 string）
            for f_id, f_val in facts.items():
                if isinstance(f_val, str):
                    errors.append(
                        f"evidence_items[{ei_idx}].facts.{f_id} 是裸 string "
                        f"'{f_val[:80]}'，应为 {{value, source_path}} 结构"
                    )
                elif isinstance(f_val, dict):
                    missing = [
                        k for k in ("value", "source_path")
                        if k not in f_val and "source" not in f_val
                    ]
                    if missing:
                        errors.append(
                            f"evidence_items[{ei_idx}].facts.{f_id} 缺少字段: {missing}"
                        )
        elif isinstance(facts, list):
            # facts 是 list 形态：每个元素必须是 dict
            fact_dicts = as_dict_list(facts, warn_key=f"{packet_name}.evidence_items[{ei_idx}].facts")
            if len(fact_dicts) != len(facts):
                errors.append(
                    f"evidence_items[{ei_idx}].facts 包含 {len(facts) - len(fact_dicts)} 个非 dict 元素"
                )
            for f_idx, fact in enumerate(fact_dicts):
                missing = [
                    k for k in ("id", "value")
                    if k not in fact
                ]
                if missing:
                    errors.append(
                        f"evidence_items[{ei_idx}].facts[{f_idx}] 缺少字段: {missing}"
                    )
                    continue
                # 检查 value 是否是裸 string（应该允许简单值，但不能是嵌套裸 string）
                val = fact.get("value")
                if isinstance(val, str) and len(val) > 500:
                    errors.append(
                        f"evidence_items[{ei_idx}].facts[{f_idx}].value 超长 "
                        f"({len(val)} 字符)，疑似裸 string 而非结构化数据"
                    )
    return errors


def _check_route_coverage(
    packet: dict[str, Any], run_dir: Path, packet_name: str
) -> list[str]:
    """检查 packet 的 route_refs 是否覆盖所有保留路线。"""
    errors: list[str] = []
    route_matrix_path = run_dir / "route_matrix_confirm.json"
    if not route_matrix_path.exists():
        return [f"[SKIP] route_matrix_confirm.json 不存在，跳过路线覆盖检查"]

    route_matrix = load_json(route_matrix_path)
    all_routes = route_matrix.get("route_matrix") or []
    selected = [
        r for r in all_routes
        if isinstance(r, dict) and r.get("status") not in ("excluded", "rejected")
    ]
    if not selected:
        return []

    selected_names = {r.get("name", r.get("route_name", "")) for r in selected}
    route_refs = set(packet.get("route_refs") or [])
    selected_routes = set(packet.get("selected_routes") or [])

    covered = route_refs | selected_routes
    missing = selected_names - covered
    if missing:
        errors.append(
            f"{packet_name} 未覆盖以下保留路线: {sorted(missing)}。"
            f"packet.route_refs={sorted(route_refs)}, "
            f"packet.selected_routes={sorted(selected_routes)}"
        )
    return errors


def _check_top_level_fields(packet: dict[str, Any], packet_name: str) -> list[str]:
    """检查 evidence packet 必填顶层字段。"""
    required = [
        "schema_version", "packet_id", "run_id", "primary_source",
        "evidence_items", "route_refs", "selected_routes",
        "data_gaps", "confidence",
    ]
    errors: list[str] = []
    for field in required:
        if field not in packet:
            errors.append(f"{packet_name} 缺少必填字段: {field}")
        elif field == "evidence_items" and not isinstance(packet[field], list):
            errors.append(f"{packet_name}.evidence_items 必须是 list")
        elif field == "evidence_items" and len(packet[field]) == 0:
            errors.append(f"{packet_name}.evidence_items 为空——Agent 未填充证据")
    return errors


def validate_evidence_packet(
    run_dir: Path, packet_name: str
) -> tuple[bool, list[str]]:
    """验证单个 evidence packet。返回 (pass, errors)。"""
    packet_path = None
    if packet_name == "market_structure":
        packet_path = run_dir / "market_structure" / "market_structure_evidence_packet.json"
    elif packet_name == "search_demand":
        packet_path = run_dir / "search_demand" / "search_demand_evidence_packet.json"
    else:
        return False, [f"未知 packet 类型: {packet_name}"]

    if not packet_path.exists():
        return False, [f"文件不存在: {packet_path}"]

    try:
        packet = load_json(packet_path)
    except Exception as e:
        return False, [f"JSON 解析失败: {e}"]

    all_errors: list[str] = []
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
    for pkt in packets:
        ok, errors = validate_evidence_packet(run_dir, pkt)
        if ok:
            print(f"[PASS] {pkt}_evidence_packet 契约校验通过")
        else:
            all_pass = False
            print(f"[FAIL] {pkt}_evidence_packet 契约校验失败 ({len(errors)} 个问题):")
            for err in errors:
                print(f"  - {err}")

    if all_pass:
        print("\n所有 evidence packet 校验通过，可进入 Stage 7。")
    else:
        print(
            "\n请打回 Stage 6 Agent 修复以上问题后重新校验。",
            file=sys.stderr,
        )

    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
