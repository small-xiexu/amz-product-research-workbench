#!/usr/bin/env python3
"""Stage 12 后置校验：检查 report_data.json 中 XLSX 必需字段的空值率。

在 Report Generation Agent 产出 report_data.json 后运行，确保：
  - competitors 列表中 ASIN/价格/月销等关键字段非空
  - keywords 列表中有实际关键词数据
  - product_routes 中每条路线的关键字段非空
  - 空值率超过阈值时打回 Agent 修复

校验失败 → 打回 Stage 12 Agent 补填 JSON，不进入 Stage 13 QA。
空值率 > 30% 的 section 报 FAIL。

Usage:
  python3 scripts/validate_report_data_completeness.py <run_dir> [--max-empty-ratio 0.30]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from packages.research_core.pipeline._validator_format import (
    ValidatorError,
    format_human,
    format_agent_replay,
)

DEFAULT_MAX_EMPTY_RATIO = 0.30

XLSX_SENSITIVE_SECTIONS: list[tuple[str, bool, list[str]]] = [
    ("competitors", True, ["asin", "price", "monthly_sales", "rating", "rating_count"]),
    ("keywords", True, ["keyword", "role"]),
    ("product_routes", True, ["route_name", "market_demand", "competition"]),
    ("pain_points", True, ["dimension", "priority"]),
]

CONTRACT_REF = "references/contracts/report_data.md"


def _extract_value(val: Any) -> str:
    if isinstance(val, dict):
        return str(val.get("value", val))
    if val is None:
        return ""
    return str(val)


def _section_empty_ratio(items: list[Any], child_keys: list[str]) -> tuple[float, int, list[str]]:
    if not items:
        return 1.0, 0, ["section 为空列表"]

    total_checked = 0
    empty_count = 0
    missing_details: list[str] = []

    for i, item in enumerate(items):
        if not isinstance(item, dict):
            empty_count += len(child_keys)
            total_checked += len(child_keys)
            missing_details.append(f"[{i}] 不是 dict")
            continue
        for key in child_keys:
            total_checked += 1
            val = _extract_value(item.get(key))
            if not val or val.strip() == "":
                empty_count += 1
                missing_details.append(f"[{i}].{key} 为空")

    ratio = empty_count / max(total_checked, 1)
    return ratio, total_checked, missing_details[:15]


def validate_report_data_completeness(
    run_dir: Path, max_empty_ratio: float = DEFAULT_MAX_EMPTY_RATIO
) -> tuple[bool, list[ValidatorError]]:
    """校验 report_data.json XLSX 关键字段完整性。"""
    errors: list[ValidatorError] = []
    report_path = run_dir / "analysis" / "report_data.json"

    if not report_path.exists():
        return False, [ValidatorError(
            code="FILE_NOT_FOUND",
            field_path=str(report_path),
            message=f"文件不存在: {report_path}",
            fix_hint="Report Generation Agent 必须写入 report_data.json 到 analysis/ 目录",
        )]

    try:
        with open(report_path, encoding="utf-8") as f:
            report = json.load(f)
    except Exception as e:
        return False, [ValidatorError(
            code="JSON_PARSE_ERROR",
            field_path=str(report_path),
            message=f"JSON 解析失败: {e}",
        )]

    if not isinstance(report, dict):
        return False, [ValidatorError(
            code="TYPE_ERROR",
            field_path="report_data.json",
            message="内容不是 dict",
            expected="dict",
            actual=type(report).__name__,
        )]

    all_pass = True

    for section_name, is_list, child_keys in XLSX_SENSITIVE_SECTIONS:
        section_data = report.get(section_name)
        if section_data is None:
            errors.append(ValidatorError(
                code="MISSING_SECTION",
                field_path=f"report_data.{section_name}",
                message=f"缺少 section: {section_name}（XLSX 对应 sheet 将为空）",
                severity="WARN",
                fix_hint=f"在 report_data.json 中添加 `\"{section_name}\"` 数据",
            ))
            continue

        items = section_data if isinstance(section_data, list) else [section_data] if isinstance(section_data, dict) else []
        ratio, total, details = _section_empty_ratio(items, child_keys)

        if ratio > max_empty_ratio:
            all_pass = False
            errors.append(ValidatorError(
                code="EMPTY_RATIO_HIGH",
                field_path=f"report_data.{section_name}",
                message=f"{total} 个字段中空值率 {ratio:.0%}，超过阈值 {max_empty_ratio:.0%}",
                expected=f"空值率 ≤ {max_empty_ratio:.0%}",
                actual=f"空值率 {ratio:.0%}",
                contract_ref=CONTRACT_REF + "#xlsx-关键字段",
                fix_hint=(
                    f"补填 {section_name} 中 {', '.join(child_keys)} 字段。"
                    f"空值详情: {'; '.join(details[:3])}"
                ),
            ))

    return all_pass, errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Stage 12 report_data.json 完整性校验"
    )
    parser.add_argument("run_dir", type=Path, help="Run 目录路径")
    parser.add_argument(
        "--max-empty-ratio",
        type=float,
        default=DEFAULT_MAX_EMPTY_RATIO,
        help=f"允许的最大空值率（默认 {DEFAULT_MAX_EMPTY_RATIO:.0%}）",
    )
    parser.add_argument("--json", action="store_true", help="JSON 格式输出")
    args = parser.parse_args(argv)
    run_dir: Path = args.run_dir.expanduser().resolve()
    if not run_dir.is_dir():
        print(f"ERROR: run_dir 不存在: {run_dir}", file=sys.stderr)
        return 2

    ok, errors = validate_report_data_completeness(run_dir, args.max_empty_ratio)
    if ok:
        print("[PASS] report_data.json 完整性校验通过，可进入 Stage 13 QA。")
    else:
        print(f"[FAIL] report_data.json 关键字段空值率过高 ({len(errors)} 个问题):")
        print(format_human(errors))
        print()
        print(
            format_agent_replay(errors, "Stage 12 报告数据完整性"),
            file=sys.stderr,
        )

    if args.json:
        from packages.research_core.pipeline._validator_format import format_json
        print(format_json(errors))

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
