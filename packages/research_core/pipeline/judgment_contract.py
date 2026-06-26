"""Contract tests for integrated_operator_judgment.json structure.

Validates that judgment output is structurally complete regardless of whether
it was produced by real Agent spawn or serial_fallback mode.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


# ── Schema constants ──────────────────────────────────────────────────────

ALLOWED_VERDICTS = {"go", "watch", "no_go", "blocked"}
ALLOWED_CONFIDENCE = {"high", "medium", "low"}

# Top-level required fields (decision summary)
REQUIRED_DECISION_FIELDS = [
    "schema_version",
    "final_verdict",
    "verdict_reason",
    "confidence",
    "biggest_opportunity",
    "biggest_risk",
    "required_next_actions",
    "operator_constraints",
    "constraints_applied",
    "evidence_refs",
    "execution_provenance",
]

# 9 deep analysis fields — every one must be present and non-empty
DEEP_ANALYSIS_FIELDS = {
    "route_recommendation": {
        "required_keys": ["routes", "primary_recommendation"],
        "description": "路线级推荐",
    },
    "route_tradeoff": {
        "required_sub_keys": ["route_name", "gain", "lose", "best_for", "worst_for"],
        "description": "路线取舍分析",
    },
    "competitor_benchmark": {
        "required_sub_keys": ["asin", "differentiation_direction", "pricing_anchor", "why_benchmark"],
        "description": "竞品对标",
    },
    "competitor_weakness_map": {
        "required_sub_keys": ["asin", "fatal_weakness", "my_counter"],
        "description": "竞品弱点地图",
    },
    "price_band_analysis": {
        "required_sub_keys": ["range", "competitive_meaning", "entry_recommendation"],
        "description": "价格带解读",
    },
    "voc_to_spec": {
        "required_sub_keys": ["dimension", "spec_requirement", "benchmark_gap", "differentiation_opportunity"],
        "description": "VOC→规格推导",
    },
    "keyword_strategy": {
        "required_keys": ["primary_attack", "testable", "negative"],
        "description": "关键词策略",
    },
    "risk_mitigation": {
        "required_sub_keys": ["operational_meaning", "mitigation_path"],
        "description": "风险缓解",
    },
    "validation_roadmap": {
        "required_sub_keys": ["phase", "actions", "exit_criteria", "if_fail"],
        "description": "验证路线图",
    },
}


# ── Validation functions ──────────────────────────────────────────────────

def validate_judgment_structure(judgment: dict[str, Any]) -> dict[str, Any]:
    """Validate structural completeness of integrated_operator_judgment.

    Returns:
        {
            "pass": bool,
            "missing_decision_fields": [...],
            "missing_deep_fields": [...],
            "incomplete_deep_fields": [...],
            "verdict_valid": bool,
            "confidence_valid": bool,
            "issues": [...],
        }
    """
    issues: list[str] = []
    missing_decision: list[str] = []
    missing_deep: list[str] = []
    incomplete_deep: list[str] = []

    # ── Decision summary fields ─────────────────────────────────
    for field in REQUIRED_DECISION_FIELDS:
        if field not in judgment:
            missing_decision.append(field)
            issues.append(f"缺少必填字段: {field}")

    # ── Verdict/confidence enum validation ──────────────────────
    verdict_valid = True
    if "final_verdict" in judgment:
        if judgment["final_verdict"] not in ALLOWED_VERDICTS:
            verdict_valid = False
            issues.append(f"verdict 值无效: '{judgment['final_verdict']}'，允许: {ALLOWED_VERDICTS}")

    confidence_valid = True
    if "confidence" in judgment:
        if judgment["confidence"] not in ALLOWED_CONFIDENCE:
            confidence_valid = False
            issues.append(f"confidence 值无效: '{judgment['confidence']}'，允许: {ALLOWED_CONFIDENCE}")

    # ── schema_version ──────────────────────────────────────────
    if judgment.get("schema_version") not in ("judgment-v2", "judgment-v1"):
        issues.append(f"schema_version 非预期: '{judgment.get('schema_version')}'")

    # ── required_next_actions ───────────────────────────────────
    actions = judgment.get("required_next_actions")
    if not isinstance(actions, list) or len(actions) < 1:
        issues.append("required_next_actions 为空或非列表——至少应有一条下一步建议")

    # ── operator_constraints ────────────────────────────────────
    constraints = judgment.get("operator_constraints")
    if not isinstance(constraints, dict):
        issues.append("operator_constraints 缺失或非 dict")

    # ── evidence_refs ───────────────────────────────────────────
    refs = judgment.get("evidence_refs")
    if not isinstance(refs, list) or len(refs) < 1:
        issues.append("evidence_refs 为空——必须包含至少一个证据引用")

    # ── 10 deep analysis fields ─────────────────────────────────
    for field_name, spec in DEEP_ANALYSIS_FIELDS.items():
        if field_name not in judgment:
            missing_deep.append(field_name)
            issues.append(f"缺少深度分析字段: {field_name} ({spec['description']})")
            continue

        field_value = judgment[field_name]
        if field_value is None or (isinstance(field_value, (dict, list)) and len(field_value) == 0):
            incomplete_deep.append(f"{field_name} (为空)")
            issues.append(f"深度分析字段为空: {field_name} ({spec['description']})")
            continue

        # Check sub-structure
        if isinstance(field_value, list):
            if len(field_value) == 0:
                incomplete_deep.append(f"{field_name} (空列表)")
                issues.append(f"深度分析字段为空列表: {field_name}")
            elif "required_sub_keys" in spec:
                for i, item in enumerate(field_value):
                    if isinstance(item, dict):
                        for key in spec["required_sub_keys"]:
                            val = item.get(key)
                            if key not in item:
                                incomplete_deep.append(f"{field_name}[{i}].{key} (缺失)")
                                issues.append(f"深度分析字段缺子字段: {field_name}[{i}].{key}")
                            elif isinstance(val, str) and _is_placeholder(val):
                                incomplete_deep.append(f"{field_name}[{i}].{key} (__ai_judgment__)")
                                issues.append(f"深度分析字段未填充: {field_name}[{i}].{key}")
        elif isinstance(field_value, dict):
            if "required_keys" in spec:
                for key in spec["required_keys"]:
                    if key not in field_value:
                        incomplete_deep.append(f"{field_name}.{key}")
                        issues.append(f"深度分析字段缺少子字段: {field_name}.{key}")
                    else:
                        val = field_value.get(key)
                        # Empty lists are acceptable (e.g. keyword_strategy.negative = [])
                        # but placeholder strings and empty dicts are not
                        if isinstance(val, str) and _is_placeholder(val):
                            incomplete_deep.append(f"{field_name}.{key} (__ai_judgment__)")
                            issues.append(f"深度分析字段未填充: {field_name}.{key}")
                        elif isinstance(val, dict) and len(val) == 0:
                            incomplete_deep.append(f"{field_name}.{key} (空dict)")
                            issues.append(f"深度分析字段为空dict: {field_name}.{key}")

    passed = (
        len(missing_decision) == 0
        and len(missing_deep) == 0
        and len(issues) == 0
        and verdict_valid
        and confidence_valid
    )

    return {
        "pass": passed,
        "missing_decision_fields": missing_decision,
        "missing_deep_fields": missing_deep,
        "incomplete_deep_fields": incomplete_deep,
        "verdict_valid": verdict_valid,
        "confidence_valid": confidence_valid,
        "issues": issues,
    }


def _is_placeholder(val: Any) -> bool:
    """Check if a value is an unfilled placeholder."""
    if val is None:
        return True
    if isinstance(val, str) and val.strip() in ("", "__ai_judgment__"):
        return True
    if isinstance(val, (list, dict)) and len(val) == 0:
        return True
    return False


def validate_judgment_file(judgment_path: Path) -> dict[str, Any]:
    """Read and validate a judgment JSON file."""
    if not judgment_path.exists():
        return {"pass": False, "issues": [f"文件不存在: {judgment_path}"],
                "missing_decision_fields": [], "missing_deep_fields": [],
                "incomplete_deep_fields": [], "verdict_valid": False,
                "confidence_valid": False}
    try:
        data = json.loads(judgment_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, ValueError) as e:
        return {"pass": False, "issues": [f"JSON 解析失败: {e}"],
                "missing_decision_fields": [], "missing_deep_fields": [],
                "incomplete_deep_fields": [], "verdict_valid": False,
                "confidence_valid": False}
    if not isinstance(data, dict):
        return {"pass": False, "issues": ["根节点不是 JSON 对象"],
                "missing_decision_fields": [], "missing_deep_fields": [],
                "incomplete_deep_fields": [], "verdict_valid": False,
                "confidence_valid": False}
    return validate_judgment_structure(data)
