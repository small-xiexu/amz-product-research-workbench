#!/usr/bin/env python3
"""Stage 9 产出后契约校验：检查 6 份评价 JSON 的数据结构完整性。

在 6 个 Evaluation Agent 产出评价后立即运行，确保：
  - 6 份评价文件均存在
  - 每份含 score (0-100) / rating / confidence / key_reasons / risks / required_followups / evidence_refs
  - route_breakdown 结构存在（路线级评分）
  - tier 合规（full 路线 6 维，light 路线 2 维 + 4 placeholder）
  - 跨维度冲突标记

校验失败 → 打回对应 Evaluation Agent 修复，不进入 Stage 10。

Usage:
  python3 scripts/validate_evaluation.py <run_dir>
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

EVALUATIONS_DIR = "evaluations"
CORE_DIMS = ["market_demand", "data_quality"]
AUX_DIMS = ["competition", "price_profit", "voc_opportunity", "risk"]
ALL_DIMS = CORE_DIMS + AUX_DIMS
VALID_RATINGS = {"strong", "moderate", "weak", "blocked", "watch"}
VALID_CONFIDENCE = {"high", "medium", "low"}
REQUIRED_FIELDS = {
    "score", "rating", "confidence", "key_reasons", "risks",
    "required_followups", "evidence_refs",
}
CONTRACT_REF = "references/contracts/evaluation.md"


def _check_evaluation_file(
    run_dir: Path, dim: str
) -> tuple[dict[str, Any] | None, list[ValidatorError]]:
    """加载并校验单份评价文件。"""
    errors: list[ValidatorError] = []
    path = run_dir / EVALUATIONS_DIR / f"{dim}_evaluation.json"
    prefix = f"{dim}_evaluation"

    if not path.exists():
        errors.append(ValidatorError(
            code="FILE_NOT_FOUND",
            field_path=str(path),
            message=f"{dim}_evaluation.json 不存在",
            fix_hint=f"确保 {dim} Evaluation Agent 用 Write 工具写入评价到 {path}",
        ))
        return None, errors

    try:
        ev = load_json(path)
    except Exception as e:
        errors.append(ValidatorError(
            code="JSON_PARSE_ERROR",
            field_path=str(path),
            message=f"JSON 解析失败: {e}",
        ))
        return None, errors

    if not isinstance(ev, dict):
        errors.append(ValidatorError(
            code="TYPE_ERROR",
            field_path=prefix,
            message="内容不是 dict",
            expected="dict",
            actual=type(ev).__name__,
            contract_ref=CONTRACT_REF,
            fix_hint="评价文件顶层必须是 JSON 对象 `{...}`",
        ))
        return None, errors

    # 必填字段
    missing = REQUIRED_FIELDS - set(ev.keys())
    for field in sorted(missing):
        errors.append(ValidatorError(
            code="MISSING_FIELD",
            field_path=f"{prefix}.{field}",
            message=f"缺少必填字段: {field}",
            contract_ref=CONTRACT_REF + "#所有-6-份评价的通用必填字段",
            fix_hint=f"在评价 JSON 中添加 `\"{field}\"` 字段",
        ))

    # score 范围
    score = ev.get("score")
    if not isinstance(score, (int, float)):
        errors.append(ValidatorError(
            code="TYPE_ERROR",
            field_path=f"{prefix}.score",
            message=f"score 不是数字",
            expected="int (0-100)",
            actual=type(score).__name__,
            contract_ref=CONTRACT_REF + "#所有-6-份评价的通用必填字段",
            fix_hint="将 score 设为 0-100 之间的整数",
        ))
    elif score < 0 or score > 100:
        errors.append(ValidatorError(
            code="VALUE_RANGE",
            field_path=f"{prefix}.score",
            message=f"score={score} 超出 0-100 范围",
            expected="0 ≤ score ≤ 100",
            actual=str(score),
            contract_ref=CONTRACT_REF + "#所有-6-份评价的通用必填字段",
            fix_hint="将 score 调整到 0-100 范围",
        ))

    # rating 枚举
    rating = ev.get("rating", "")
    if rating not in VALID_RATINGS:
        errors.append(ValidatorError(
            code="INVALID_ENUM",
            field_path=f"{prefix}.rating",
            message=f"rating='{rating}' 不在允许范围",
            expected=f"{{{', '.join(sorted(VALID_RATINGS))}}}",
            actual=str(rating),
            contract_ref=CONTRACT_REF + "#所有-6-份评价的通用必填字段",
            fix_hint=f"将 rating 改为 {sorted(VALID_RATINGS)} 之一",
        ))

    # confidence 枚举
    confidence = ev.get("confidence", "")
    if confidence not in VALID_CONFIDENCE:
        errors.append(ValidatorError(
            code="INVALID_ENUM",
            field_path=f"{prefix}.confidence",
            message=f"confidence='{confidence}' 不在允许范围",
            expected=f"{{{', '.join(sorted(VALID_CONFIDENCE))}}}",
            actual=str(confidence),
            contract_ref=CONTRACT_REF + "#所有-6-份评价的通用必填字段",
            fix_hint=f"将 confidence 改为 {sorted(VALID_CONFIDENCE)} 之一",
        ))

    # key_reasons 非空
    key_reasons = ev.get("key_reasons", [])
    if not isinstance(key_reasons, list) or len(key_reasons) == 0:
        errors.append(ValidatorError(
            code="EMPTY_VALUE",
            field_path=f"{prefix}.key_reasons",
            message="key_reasons 为空或非 list",
            expected="list[string]（至少 1 条）",
            actual=type(key_reasons).__name__ if not isinstance(key_reasons, list) else "空列表",
            contract_ref=CONTRACT_REF + "#所有-6-份评价的通用必填字段",
            fix_hint="至少写 1 条评分理由，如 `[\"需求搜索量稳定在 5K-10K\"]`",
        ))

    # evidence_refs 非空
    evidence_refs = ev.get("evidence_refs", [])
    if not isinstance(evidence_refs, list) or len(evidence_refs) == 0:
        errors.append(ValidatorError(
            code="EMPTY_VALUE",
            field_path=f"{prefix}.evidence_refs",
            message="evidence_refs 为空或非 list",
            expected="list[string]（至少 1 条）",
            actual=type(evidence_refs).__name__ if not isinstance(evidence_refs, list) else "空列表",
            contract_ref=CONTRACT_REF + "#禁止事项",
            fix_hint="至少引用 1 条证据文件路径，如 `[\"market_structure/market_structure_evidence_packet.json\"]`",
        ))

    # route_breakdown 存在且结构正确
    route_breakdown = ev.get("route_breakdown")
    if route_breakdown is None:
        errors.append(ValidatorError(
            code="MISSING_FIELD",
            field_path=f"{prefix}.route_breakdown",
            message="route_breakdown 缺失——需要路线级评分",
            expected="list[dict] 或 dict",
            contract_ref=CONTRACT_REF + "#route_breakdown-每条必填",
            fix_hint="添加 route_breakdown，每条路线含 route_id + score + rating + reason",
        ))
    elif not isinstance(route_breakdown, (dict, list)):
        errors.append(ValidatorError(
            code="TYPE_ERROR",
            field_path=f"{prefix}.route_breakdown",
            message=f"route_breakdown 类型异常",
            expected="list[dict] 或 dict",
            actual=type(route_breakdown).__name__,
            contract_ref=CONTRACT_REF + "#route_breakdown-每条必填",
            fix_hint="将 route_breakdown 改为 list[dict] 格式",
        ))
    elif isinstance(route_breakdown, list):
        for i, item in enumerate(route_breakdown):
            if isinstance(item, dict) and not item.get("route_id"):
                errors.append(ValidatorError(
                    code="MISSING_FIELD",
                    field_path=f"{prefix}.route_breakdown[{i}]",
                    message="缺少 route_id——list 形式必须每个条目自带 route_id",
                    expected="kebab-case 英文 route_id",
                    contract_ref=CONTRACT_REF + "#route_breakdown-每条必填",
                    fix_hint=f"在 route_breakdown[{i}] 中添加 `\"route_id\": \"<kebab-case>\"`",
                ))

    return ev, errors


def _check_tier_compliance(
    evaluations: dict[str, dict[str, Any] | None], run_dir: Path
) -> list[ValidatorError]:
    """检查 tier 合规。"""
    errors: list[ValidatorError] = []
    dcc_path = run_dir / "data_completeness_check.json"
    if not dcc_path.exists():
        return []

    dcc = load_json(dcc_path)
    tier_summary = dcc.get("tier_summary", {})
    if not tier_summary:
        return []

    full_count = tier_summary.get("full_count", 0)
    light_count = tier_summary.get("light_count", 0)

    if light_count > 0 and full_count == 0:
        for dim in AUX_DIMS:
            ev = evaluations.get(dim)
            if ev is None:
                continue
            ep = ev.get("execution_provenance", {}) or {}
            mode = ep.get("execution_mode", "")
            if mode != "tier_light_skipped":
                errors.append(ValidatorError(
                    code="TIER_VIOLATION",
                    field_path=f"{dim}_evaluation.execution_provenance.execution_mode",
                    message=f"应为 tier_light（仅有 light 路线），但 execution_mode='{mode}'",
                    expected="tier_light_skipped",
                    actual=str(mode),
                    contract_ref=CONTRACT_REF + "#tier-规则",
                    fix_hint=f"将 {dim}_evaluation 的 execution_provenance.execution_mode 设为 'tier_light_skipped'",
                ))

    return errors


def _check_cross_dimension_consistency(
    evaluations: dict[str, dict[str, Any] | None]
) -> list[ValidatorError]:
    """检查跨维度硬规则一致性。"""
    errors: list[ValidatorError] = []
    for dim, ev in evaluations.items():
        if ev is None:
            continue
        score = ev.get("score", 0)
        rating = ev.get("rating", "")
        if isinstance(score, (int, float)) and score > 90 and rating == "weak":
            errors.append(ValidatorError(
                code="SCORE_RATING_CONFLICT",
                field_path=f"{dim}_evaluation",
                message=f"score={score} 但 rating='weak'——高分与弱评级矛盾",
                expected="score > 90 时应为 strong 或 watch",
                actual=f"score={score}, rating={rating}",
                contract_ref=CONTRACT_REF + "#禁止事项",
                fix_hint=f"调整 {dim} 的 rating 与 score 保持一致，或将 score 降到 ≤ 90",
            ))
        if isinstance(score, (int, float)) and score < 20 and rating == "strong":
            errors.append(ValidatorError(
                code="SCORE_RATING_CONFLICT",
                field_path=f"{dim}_evaluation",
                message=f"score={score} 但 rating='strong'——低分与强评级矛盾",
                expected="score < 20 时应为 weak 或 blocked",
                actual=f"score={score}, rating={rating}",
                contract_ref=CONTRACT_REF + "#禁止事项",
                fix_hint=f"调整 {dim} 的 rating 与 score 保持一致，或将 score 提高到 ≥ 20",
            ))

    return errors


def validate_evaluations(run_dir: Path) -> tuple[bool, list[ValidatorError]]:
    """验证所有 6 份评价。"""
    all_errors: list[ValidatorError] = []
    evaluations: dict[str, dict[str, Any] | None] = {}

    for dim in ALL_DIMS:
        ev, errors = _check_evaluation_file(run_dir, dim)
        evaluations[dim] = ev
        all_errors.extend(errors)

    if all_errors:
        return False, all_errors

    all_errors.extend(_check_tier_compliance(evaluations, run_dir))
    all_errors.extend(_check_cross_dimension_consistency(evaluations))

    return len(all_errors) == 0, all_errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Stage 9 评价文件契约校验"
    )
    parser.add_argument("run_dir", type=Path, help="Run 目录路径")
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

    ok, errors = validate_evaluations(run_dir)
    if ok:
        print("[PASS] 全部 6 份评价契约校验通过，可进入 Stage 10。")
    else:
        print(f"[FAIL] 评价契约校验失败 ({len(errors)} 个问题):")
        print(format_human(errors))
        print()
        print(
            format_agent_replay(errors, "Stage 9 六维评价"),
            file=sys.stderr,
        )

    if args.json:
        from packages.research_core.pipeline._validator_format import format_json
        print(format_json(errors))

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
