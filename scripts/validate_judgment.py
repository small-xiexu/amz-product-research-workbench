#!/usr/bin/env python3
"""Stage 10 产出后契约校验：检查 integrated_operator_judgment.json 的完整性。

两个校验模式（可组合使用）：

  --check-placeholders  Stage 10a 后运行：检查 9 个深度分析字段无 __ai_judgment__ 占位
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
from packages.research_core.pipeline._validator_format import (
    ValidatorError,
    format_human,
    format_agent_replay,
)

JUDGMENT_PATH = "analysis/integrated_operator_judgment.json"
EVALUATION_SUMMARY_PATH = "evaluations/evaluation_summary.json"

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
CONTRACT_REF = "references/contracts/integrated_judgment.md"


def _deep_scan_placeholders(value: Any, path: str = "$") -> list[tuple[str, str]]:
    """递归扫描字典/列表/字符串中的 __ai_judgment__ 占位符。返回 [(path, snippet)]。"""
    hits: list[tuple[str, str]] = []
    if isinstance(value, str):
        if PLACEHOLDER_MARKER in value:
            snippet = value[:80] + ("..." if len(value) > 80 else "")
            hits.append((path, snippet))
    elif isinstance(value, dict):
        for key, val in value.items():
            hits.extend(_deep_scan_placeholders(val, f"{path}.{key}"))
    elif isinstance(value, list):
        for i, item in enumerate(value):
            hits.extend(_deep_scan_placeholders(item, f"{path}[{i}]"))
    return hits


def check_placeholders(judgment: dict[str, Any]) -> tuple[bool, list[ValidatorError]]:
    """检查 9 个深度分析字段是否仍有 __ai_judgment__ 占位符。"""
    errors: list[ValidatorError] = []
    total_placeholders = 0

    for field in DEEP_ANALYSIS_FIELDS:
        value = judgment.get(field)
        if value is None:
            errors.append(ValidatorError(
                code="MISSING_FIELD",
                field_path=f"integrated_operator_judgment.{field}",
                message=f"{field} 字段缺失——Stage 10a Agent 未写入",
                contract_ref=CONTRACT_REF + "#stage-10a-深度分析字段",
                fix_hint=f"对应 Agent 必须写入 {field} 字段，不能留空",
            ))
            continue

        hits = _deep_scan_placeholders(value, f"$.{field}")
        for path, snippet in hits[:5]:
            errors.append(ValidatorError(
                code="PLACEHOLDER_FOUND",
                field_path=path,
                message=f"占位符残留: {snippet!r}",
                expected="真实分析内容",
                actual="__ai_judgment__",
                contract_ref=CONTRACT_REF + "#硬约束",
                fix_hint=f"将 {path} 中的 __ai_judgment__ 替换为真实分析数据",
            ))
            total_placeholders += 1
        if len(hits) > 5:
            total_placeholders += len(hits) - 5
            errors.append(ValidatorError(
                code="PLACEHOLDER_FOUND",
                field_path=f"$.{field}",
                message=f"... 及其他 {len(hits) - 5} 处占位符",
                fix_hint=f"递归扫描 {field}，替换所有 __ai_judgment__",
            ))

    if total_placeholders > 0:
        errors.insert(0, ValidatorError(
            code="PLACEHOLDER_SUMMARY",
            field_path="integrated_operator_judgment",
            message=(
                f"发现 {total_placeholders} 处 __ai_judgment__ 占位符——"
                f"Stage 10a Agent 未完整填充 {len(DEEP_ANALYSIS_FIELDS)} 个深度分析字段"
            ),
            expected="所有 9 个字段均由 Agent 填充真实内容",
            actual=f"{total_placeholders} 处占位符残留",
            contract_ref=CONTRACT_REF + "#硬约束",
            fix_hint="10a 任何字段仍含占位 → verdict 强制 blocked。打回对应 Agent 完整填充。",
        ))

    return len(errors) == 0, errors


def check_verdict(
    judgment: dict[str, Any], run_dir: Path
) -> tuple[bool, list[ValidatorError]]:
    """检查 final_verdict 有效性、治理规则合规、Stage 9 交叉一致性。"""
    errors: list[ValidatorError] = []

    # 1. Check decision fields exist
    for field in DECISION_FIELDS:
        if field not in judgment:
            errors.append(ValidatorError(
                code="MISSING_FIELD",
                field_path=f"integrated_operator_judgment.{field}",
                message=f"缺少决策字段: {field}",
                contract_ref=CONTRACT_REF + "#stage-10b-决策摘要字段",
                fix_hint=f"Lead Operator Agent 必须写入 {field}",
            ))
        elif field == "verdict_reason" and not judgment.get(field):
            errors.append(ValidatorError(
                code="EMPTY_VALUE",
                field_path="integrated_operator_judgment.verdict_reason",
                message="verdict_reason 为空——Lead Operator 未写裁决理由",
                expected="2-4 段综合判断理由",
                contract_ref=CONTRACT_REF + "#stage-10b-决策摘要字段",
                fix_hint="填写 verdict_reason，讲清维度间张力和最终权衡",
            ))
        elif field == "required_next_actions" and not isinstance(judgment.get(field), list):
            errors.append(ValidatorError(
                code="TYPE_ERROR",
                field_path="integrated_operator_judgment.required_next_actions",
                message="required_next_actions 必须是 list",
                expected="list[string]",
                actual=type(judgment.get(field)).__name__,
                fix_hint="改为数组格式: `[\"动作1\", \"动作2\"]`",
            ))

    # 2. final_verdict valid
    verdict = judgment.get("final_verdict", "")
    if verdict not in VALID_VERDICTS:
        errors.append(ValidatorError(
            code="INVALID_ENUM",
            field_path="integrated_operator_judgment.final_verdict",
            message=f"final_verdict='{verdict}' 不在允许范围",
            expected=f"{{{', '.join(sorted(VALID_VERDICTS))}}}",
            actual=str(verdict),
            contract_ref=CONTRACT_REF + "#stage-10b-决策摘要字段",
            fix_hint=f"将 final_verdict 改为 {sorted(VALID_VERDICTS)} 之一",
        ))

    # 3. confidence
    confidence = judgment.get("confidence", "")
    if confidence not in VALID_CONFIDENCE:
        errors.append(ValidatorError(
            code="INVALID_ENUM",
            field_path="integrated_operator_judgment.confidence",
            message=f"confidence='{confidence}' 不在允许范围",
            expected=f"{{{', '.join(sorted(VALID_CONFIDENCE))}}}",
            actual=str(confidence),
            contract_ref=CONTRACT_REF + "#stage-10b-决策摘要字段",
            fix_hint=f"将 confidence 改为 {sorted(VALID_CONFIDENCE)} 之一",
        ))

    # 4. Placeholders check (10a must be done before 10b)
    placeholder_ok, placeholder_errors = check_placeholders(judgment)
    if not placeholder_ok:
        errors.append(ValidatorError(
            code="PREREQUISITE_FAILED",
            field_path="integrated_operator_judgment",
            message="深度分析字段仍有 __ai_judgment__ 占位——Stage 10a 未完成，不能进入 10b 裁决",
            contract_ref=CONTRACT_REF + "#硬约束",
            fix_hint="先完成 Stage 10a，确保 9 个字段全部由 Agent 填充，再运行 10b",
        ))

    # 5. Cross-consistency with Stage 9
    summary_path = run_dir / EVALUATION_SUMMARY_PATH
    if summary_path.exists():
        summary = load_json(summary_path)
        errors.extend(_check_stage9_consistency(judgment, summary))
    else:
        errors.append(ValidatorError(
            code="SKIP",
            field_path=EVALUATION_SUMMARY_PATH,
            message=f"{EVALUATION_SUMMARY_PATH} 不存在，跳过 Stage 9 交叉一致性检查",
            severity="WARN",
        ))

    # 6. Decision placeholder check
    errors.extend(_check_decision_placeholders(judgment))

    # 7. Governance rules
    errors.extend(_check_governance_rules(judgment, run_dir))

    return len(errors) == 0, errors


def _check_stage9_consistency(
    judgment: dict[str, Any], summary: dict[str, Any]
) -> list[ValidatorError]:
    """检查 Stage 9 评分与 Stage 10 裁决的一致性。"""
    errors: list[ValidatorError] = []
    blocked_dims = summary.get("blocked_dimensions", [])
    verdict = judgment.get("final_verdict", "")

    if "data_quality" in blocked_dims and verdict == "go":
        errors.append(ValidatorError(
            code="GOVERNANCE_VIOLATION",
            field_path="integrated_operator_judgment.final_verdict",
            message="data_quality rating=blocked，final_verdict 不能为 'go'——必须先补数",
            expected="watch 或 blocked",
            actual="go",
            contract_ref=CONTRACT_REF + "#硬约束",
            fix_hint="将 final_verdict 改为 'watch'（补数后再判断）或 'blocked'",
        ))
    if blocked_dims and verdict == "go":
        errors.append(ValidatorError(
            code="GOVERNANCE_VIOLATION",
            field_path="integrated_operator_judgment.final_verdict",
            message=f"核心维度 blocked: {blocked_dims}，final_verdict 不能为 'go'",
            expected="watch 或 blocked",
            actual="go",
            contract_ref=CONTRACT_REF + "#硬约束",
            fix_hint="任一核心维度 blocked 时，该路线不能直接放行",
        ))
    if not blocked_dims and verdict == "blocked":
        errors.append(ValidatorError(
            code="GOVERNANCE_INCONSISTENCY",
            field_path="integrated_operator_judgment.final_verdict",
            message="Stage 9 无 blocked 维度，但 final_verdict='blocked'——请检查裁决理由",
            severity="WARN",
        ))

    tensions = summary.get("cross_dimension_tensions", [])
    if tensions:
        verdict_reason = judgment.get("verdict_reason", "")
        if verdict_reason and len(str(verdict_reason)) < 50:
            errors.append(ValidatorError(
                code="VALUE_RANGE",
                field_path="integrated_operator_judgment.verdict_reason",
                message=f"存在 {len(tensions)} 个跨维度冲突但 verdict_reason 过短（< 50 字符）",
                expected="详细解释如何解决跨维度张力",
                actual=f"{len(str(verdict_reason))} 字符",
                fix_hint="在 verdict_reason 中明确说明如何权衡这些冲突",
            ))

    return errors


def _check_governance_rules(
    judgment: dict[str, Any], run_dir: Path
) -> list[ValidatorError]:
    """检查治理规则合规。"""
    errors: list[ValidatorError] = []

    missing_rs = [f for f in ROUTE_STRATEGY_FIELDS if f not in judgment]
    missing_gr = [f for f in GROWTH_RISK_FIELDS if f not in judgment]
    if missing_rs:
        errors.append(ValidatorError(
            code="MISSING_FIELD",
            field_path="integrated_operator_judgment",
            message=f"Route Strategy Agent 字段缺失: {missing_rs}——Stage 10a 未完成",
            contract_ref=CONTRACT_REF + "#stage-10a-深度分析字段",
            fix_hint=f"运行 Route Strategy Agent 填充: {missing_rs}",
        ))
    if missing_gr:
        errors.append(ValidatorError(
            code="MISSING_FIELD",
            field_path="integrated_operator_judgment",
            message=f"Growth & Risk Agent 字段缺失: {missing_gr}——Stage 10a 未完成",
            contract_ref=CONTRACT_REF + "#stage-10a-深度分析字段",
            fix_hint=f"运行 Growth & Risk Agent 填充: {missing_gr}",
        ))

    ep = judgment.get("execution_provenance", {}) or {}
    if ep.get("execution_mode") == "script_generated_skeleton":
        verdict = judgment.get("final_verdict", "")
        if verdict not in ("blocked", ""):
            errors.append(ValidatorError(
                code="PROVENANCE_STALE",
                field_path="integrated_operator_judgment.execution_provenance",
                message="execution_provenance 仍为 script_generated_skeleton——Lead Operator 未更新",
                expected="execution_mode: agent",
                actual="script_generated_skeleton",
                fix_hint="Lead Operator Agent 更新 execution_provenance 为真实的 agent 模式",
            ))

    for field in ("biggest_opportunity", "biggest_risk"):
        val = judgment.get(field, {}) or {}
        if isinstance(val, dict):
            if not val.get("dimension"):
                errors.append(ValidatorError(
                    code="MISSING_FIELD",
                    field_path=f"integrated_operator_judgment.{field}.dimension",
                    message=f"{field}.dimension 缺失——需指明来自哪个评价维度",
                    contract_ref=CONTRACT_REF + "#stage-10b-决策摘要字段",
                    fix_hint=f"在 {field} 中添加 'dimension' 字段",
                ))
            if not val.get("description") and not val.get("reason"):
                errors.append(ValidatorError(
                    code="MISSING_FIELD",
                    field_path=f"integrated_operator_judgment.{field}",
                    message=f"{field} 缺少 description/reason——需写明具体内容",
                    fix_hint=f"在 {field} 中添加 description 或 reason",
                ))

    return errors


def _check_decision_placeholders(judgment: dict[str, Any]) -> list[ValidatorError]:
    """Check Stage 10b decision-summary fields are not skeleton placeholders."""
    errors: list[ValidatorError] = []
    for field in DECISION_FIELDS:
        hits = _deep_scan_placeholders(judgment.get(field), f"$.{field}")
        if hits:
            errors.append(ValidatorError(
                code="PLACEHOLDER_FOUND",
                field_path=f"integrated_operator_judgment.{field}",
                message=f"{field} 仍含 __ai_judgment__——Lead Operator Agent 未完成最终判断",
                contract_ref=CONTRACT_REF + "#硬约束",
                fix_hint=f"Lead Operator Agent 必须填写 {field}，替换所有占位符",
            ))
    return errors


def validate_judgment(
    run_dir: Path,
    check_placeholders_flag: bool = False,
    check_verdict_flag: bool = False,
) -> tuple[bool, list[ValidatorError]]:
    """验证 judgment。"""
    if not check_placeholders_flag and not check_verdict_flag:
        return False, [ValidatorError(
            code="NO_CHECK_MODE",
            field_path="CLI",
            message="请指定至少一个检查模式: --check-placeholders 或 --check-verdict",
        )]

    judgment_path = run_dir / JUDGMENT_PATH
    if not judgment_path.exists():
        return False, [ValidatorError(
            code="FILE_NOT_FOUND",
            field_path=str(judgment_path),
            message=f"文件不存在: {judgment_path}",
            fix_hint="确保 Stage 10 Agent 已写入 integrated_operator_judgment.json",
        )]

    try:
        judgment = load_json(judgment_path)
    except Exception as e:
        return False, [ValidatorError(
            code="JSON_PARSE_ERROR",
            field_path=str(judgment_path),
            message=f"JSON 解析失败: {e}",
        )]

    all_errors: list[ValidatorError] = []

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
        "--check-placeholders", action="store_true",
        help="检查 9 个深度分析字段无 __ai_judgment__ 占位 (Stage 10a)",
    )
    parser.add_argument(
        "--check-verdict", action="store_true",
        help="检查 final_verdict 有效性 + 治理规则 + Stage 9 交叉一致性 (Stage 10b)",
    )
    parser.add_argument("--json", action="store_true", help="JSON 格式输出")
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
        print(format_human(errors))
        print()
        print(
            format_agent_replay(errors, "Stage 10 运营判断"),
            file=sys.stderr,
        )

    if args.json:
        from packages.research_core.pipeline._validator_format import format_json
        print(format_json(errors))

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
