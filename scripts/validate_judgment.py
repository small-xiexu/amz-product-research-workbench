#!/usr/bin/env python3
"""Stage 10 产出后契约校验：检查 integrated_operator_judgment.json 的完整性。

两个校验模式（可组合使用）：

  --check-placeholders  Stage 10a 后运行：检查 10 个深度分析字段无 __ai_judgment__ 占位
  --check-verdict       Stage 10b 后运行：检查 final_verdict 有效性、治理规则合规、
                        Stage 9 评分与 Stage 10 裁决交叉一致性

校验失败 → 打回对应 Agent 修复，不进入 Stage 11。

Usage:
  python3 scripts/validate_judgment.py <run_dir> --check-placeholders
  python3 scripts/validate_judgment.py <run_dir> --check-verdict
  python3 scripts/validate_judgment.py <run_dir> --check-placeholders --check-verdict
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from packages.research_core.pipeline._utils import load_json

JUDGMENT_PATH = "analysis/integrated_operator_judgment.json"
EVALUATION_SUMMARY_PATH = "evaluations/evaluation_summary.json"

# 10 deep analysis fields (Stage 10a agents fill these)
ROUTE_STRATEGY_FIELDS = [
    "route_recommendation",
    "route_tradeoff",
    "competitor_benchmark",
    "competitor_weakness_map",
    "price_band_analysis",
]
GROWTH_RISK_FIELDS = [
    "voc_to_spec",
    "keyword_strategy",
    "risk_mitigation",
    "validation_roadmap",
]
DEEP_ANALYSIS_FIELDS = ROUTE_STRATEGY_FIELDS + GROWTH_RISK_FIELDS

# Decision summary fields (Stage 10b Lead Operator fills these)
DECISION_FIELDS = [
    "final_verdict",
    "verdict_reason",
    "confidence",
    "biggest_opportunity",
    "biggest_risk",
    "required_next_actions",
]

VALID_VERDICTS = {"go", "watch", "no_go", "blocked"}
VALID_CONFIDENCE = {"high", "medium", "low"}

PLACEHOLDER_MARKER = "__ai_judgment__"


def _deep_scan_placeholders(value: Any, path: str = "$") -> list[str]:
    """递归扫描字典/列表/字符串中的 __ai_judgment__ 占位符。"""
    hits: list[str] = []
    if isinstance(value, str):
        if PLACEHOLDER_MARKER in value:
            hits.append(f"{path}: {value!r}")
    elif isinstance(value, dict):
        for key, val in value.items():
            hits.extend(_deep_scan_placeholders(val, f"{path}.{key}"))
    elif isinstance(value, list):
        for i, item in enumerate(value):
            hits.extend(_deep_scan_placeholders(item, f"{path}[{i}]"))
    return hits


def check_placeholders(judgment: dict[str, Any]) -> tuple[bool, list[str]]:
    """检查 10 个深度分析字段是否仍有 __ai_judgment__ 占位符。

    返回 (pass, errors)。pass=True 表示全部字段已由 Agent 填充。
    """
    errors: list[str] = []
    total_placeholders = 0

    for field in DEEP_ANALYSIS_FIELDS:
        value = judgment.get(field)
        if value is None:
            errors.append(f"{field} 字段缺失——Stage 10a Agent 未写入")
            continue

        hits = _deep_scan_placeholders(value, f"$.{field}")
        if hits:
            total_placeholders += len(hits)
            errors.extend(hits[:5])  # Show up to 5 examples per field
            if len(hits) > 5:
                errors.append(f"  ... 及其他 {len(hits) - 5} 处占位符")

    if total_placeholders > 0:
        errors.insert(
            0,
            f"发现 {total_placeholders} 处 __ai_judgment__ 占位符——"
            f"Stage 10a Agent 未完整填充 {len(DEEP_ANALYSIS_FIELDS)} 个深度分析字段",
        )

    return len(errors) == 0, errors


def check_verdict(
    judgment: dict[str, Any], run_dir: Path
) -> tuple[bool, list[str]]:
    """检查 final_verdict 有效性、治理规则合规、Stage 9 交叉一致性。

    返回 (pass, errors)。
    """
    errors: list[str] = []

    # 1. Check decision fields exist
    for field in DECISION_FIELDS:
        if field not in judgment:
            errors.append(f"缺少决策字段: {field}")
        elif field == "verdict_reason" and not judgment.get(field):
            errors.append("verdict_reason 为空——Lead Operator 未写裁决理由")
        elif field == "required_next_actions" and not isinstance(
            judgment.get(field), list
        ):
            errors.append("required_next_actions 必须是 list")

    # 2. Check final_verdict is valid
    verdict = judgment.get("final_verdict", "")
    if verdict not in VALID_VERDICTS:
        errors.append(
            f"final_verdict='{verdict}' 不在允许范围 {sorted(VALID_VERDICTS)}"
        )

    # 3. Check confidence
    confidence = judgment.get("confidence", "")
    if confidence not in VALID_CONFIDENCE:
        errors.append(
            f"confidence='{confidence}' 不在允许范围 {sorted(VALID_CONFIDENCE)}"
        )

    # 4. Check placeholders in deep fields (Stage 10a should be done)
    placeholder_ok, placeholder_errors = check_placeholders(judgment)
    if not placeholder_ok:
        errors.append(
            "深度分析字段仍有 __ai_judgment__ 占位——"
            "Stage 10a 未完成，不能进入 10b 裁决"
        )

    # 5. Cross-consistency with Stage 9
    summary_path = run_dir / EVALUATION_SUMMARY_PATH
    if summary_path.exists():
        summary = load_json(summary_path)
        errors.extend(
            _check_stage9_consistency(judgment, summary)
        )
    else:
        errors.append(
            f"[SKIP] {EVALUATION_SUMMARY_PATH} 不存在，跳过 Stage 9 交叉一致性检查"
        )

    # 6. Governance rules
    errors.extend(_check_governance_rules(judgment, run_dir))

    return len(errors) == 0, errors


def _check_stage9_consistency(
    judgment: dict[str, Any], summary: dict[str, Any]
) -> list[str]:
    """检查 Stage 9 评分与 Stage 10 裁决的一致性。"""
    errors: list[str] = []

    blocked_dims = summary.get("blocked_dimensions", [])
    verdict = judgment.get("final_verdict", "")

    # If any core dimension is blocked, verdict cannot be "go"
    if "data_quality" in blocked_dims and verdict == "go":
        errors.append(
            "data_quality rating=blocked，final_verdict 不能为 'go'——"
            "必须先补数或解决冲突"
        )
    if blocked_dims and verdict == "go":
        errors.append(
            f"核心维度 blocked: {blocked_dims}，final_verdict 不能为 'go'"
        )

    # If no blocked dims and verdict is "blocked", ask why
    if not blocked_dims and verdict == "blocked":
        errors.append(
            "Stage 9 无 blocked 维度，但 final_verdict='blocked'——"
            "请检查裁决理由是否充分"
        )

    # Check tension resolution
    tensions = summary.get("cross_dimension_tensions", [])
    if tensions:
        verdict_reason = judgment.get("verdict_reason", "")
        if verdict_reason and len(str(verdict_reason)) < 50:
            errors.append(
                f"存在 {len(tensions)} 个跨维度冲突但 verdict_reason 过短——"
                "需要明确解释如何解决了这些张力"
            )

    return errors


def _check_governance_rules(
    judgment: dict[str, Any], run_dir: Path
) -> list[str]:
    """检查治理规则合规。"""
    errors: list[str] = []

    verdict = judgment.get("final_verdict", "")

    # Check that Route Strategy and Growth & Risk fields are both present
    # (Stage 10a must complete both agents)
    missing_rs = [
        f for f in ROUTE_STRATEGY_FIELDS if f not in judgment
    ]
    missing_gr = [
        f for f in GROWTH_RISK_FIELDS if f not in judgment
    ]
    if missing_rs:
        errors.append(
            f"Route Strategy Agent 字段缺失: {missing_rs}——"
            "Stage 10a 未完成"
        )
    if missing_gr:
        errors.append(
            f"Growth & Risk Agent 字段缺失: {missing_gr}——"
            "Stage 10a 未完成"
        )

    # Check execution_provenance reflects real Agent execution
    ep = judgment.get("execution_provenance", {}) or {}
    if ep.get("execution_mode") == "script_generated_skeleton":
        if verdict not in ("blocked", ""):
            errors.append(
                "execution_provenance 仍为 script_generated_skeleton——"
                "Lead Operator Agent 未更新执行来源"
            )

    # biggest_opportunity and biggest_risk should reference specific dimensions
    for field in ("biggest_opportunity", "biggest_risk"):
        val = judgment.get(field, {}) or {}
        if isinstance(val, dict):
            if not val.get("dimension"):
                errors.append(f"{field}.dimension 缺失——需指明来自哪个评价维度")
            if not val.get("detail"):
                errors.append(f"{field}.detail 缺失——需写明具体内容")

    return errors


def validate_judgment(
    run_dir: Path,
    check_placeholders_flag: bool = False,
    check_verdict_flag: bool = False,
) -> tuple[bool, list[str]]:
    """验证 judgment。返回 (pass, errors)。"""
    if not check_placeholders_flag and not check_verdict_flag:
        return False, ["请指定至少一个检查模式: --check-placeholders 或 --check-verdict"]

    judgment_path = run_dir / JUDGMENT_PATH
    if not judgment_path.exists():
        return False, [f"文件不存在: {judgment_path}"]

    try:
        judgment = load_json(judgment_path)
    except Exception as e:
        return False, [f"JSON 解析失败: {e}"]

    all_errors: list[str] = []

    if check_placeholders_flag:
        ok, errors = check_placeholders(judgment)
        all_errors.extend(errors)
        if not ok:
            return False, all_errors

    if check_verdict_flag:
        ok, errors = check_verdict(judgment, run_dir)
        all_errors.extend(errors)
        if not ok:
            return False, all_errors

    return len(all_errors) == 0, all_errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Stage 10 integrated_operator_judgment 契约校验"
    )
    parser.add_argument("run_dir", type=Path, help="Run 目录路径")
    parser.add_argument(
        "--check-placeholders",
        action="store_true",
        help="检查 10 个深度分析字段无 __ai_judgment__ 占位 (Stage 10a)",
    )
    parser.add_argument(
        "--check-verdict",
        action="store_true",
        help="检查 final_verdict 有效性 + 治理规则 + Stage 9 交叉一致性 (Stage 10b)",
    )
    args = parser.parse_args(argv)

    run_dir: Path = args.run_dir.expanduser().resolve()
    if not run_dir.is_dir():
        print(f"ERROR: run_dir 不存在: {run_dir}", file=sys.stderr)
        return 2

    ok, errors = validate_judgment(
        run_dir,
        check_placeholders_flag=args.check_placeholders,
        check_verdict_flag=args.check_verdict,
    )

    if ok:
        mode = []
        if args.check_placeholders:
            mode.append("占位符检查")
        if args.check_verdict:
            mode.append("裁决检查")
        print(f"[PASS] integrated_operator_judgment {' + '.join(mode)} 通过，可进入下一阶段。")
    else:
        print(f"[FAIL] integrated_operator_judgment 校验失败 ({len(errors)} 个问题):")
        for err in errors:
            print(f"  - {err}")
        print("\n请打回对应 Agent 修复以上问题后重新校验。", file=sys.stderr)

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
