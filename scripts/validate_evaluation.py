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


def _check_evaluation_file(
    run_dir: Path, dim: str
) -> tuple[dict[str, Any] | None, list[str]]:
    """加载并校验单份评价文件。返回 (evaluation_dict, errors)。"""
    errors: list[str] = []
    path = run_dir / EVALUATIONS_DIR / f"{dim}_evaluation.json"

    if not path.exists():
        errors.append(f"{dim}_evaluation.json 不存在")
        return None, errors

    try:
        ev = load_json(path)
    except Exception as e:
        errors.append(f"{dim}_evaluation.json JSON 解析失败: {e}")
        return None, errors

    if not isinstance(ev, dict):
        errors.append(f"{dim}_evaluation.json 内容不是 dict")
        return None, errors

    # Check required fields
    missing = REQUIRED_FIELDS - set(ev.keys())
    if missing:
        errors.append(f"{dim}_evaluation.json 缺少字段: {sorted(missing)}")

    # Check score range
    score = ev.get("score")
    if not isinstance(score, (int, float)):
        errors.append(f"{dim}.score 不是数字: {type(score).__name__}")
    elif score < 0 or score > 100:
        errors.append(f"{dim}.score={score} 超出 0-100 范围")

    # Check rating
    rating = ev.get("rating", "")
    if rating not in VALID_RATINGS:
        errors.append(
            f"{dim}.rating='{rating}' 不在允许范围 {sorted(VALID_RATINGS)}"
        )

    # Check confidence
    confidence = ev.get("confidence", "")
    if confidence not in VALID_CONFIDENCE:
        errors.append(
            f"{dim}.confidence='{confidence}' 不在允许范围 {sorted(VALID_CONFIDENCE)}"
        )

    # Check key_reasons is non-empty list
    key_reasons = ev.get("key_reasons", [])
    if not isinstance(key_reasons, list) or len(key_reasons) == 0:
        errors.append(f"{dim}.key_reasons 为空或非 list——至少需要 1 条理由")

    # Check risks is list
    risks = ev.get("risks", [])
    if not isinstance(risks, list):
        errors.append(f"{dim}.risks 应为 list")

    # Check evidence_refs is non-empty list
    evidence_refs = ev.get("evidence_refs", [])
    if not isinstance(evidence_refs, list) or len(evidence_refs) == 0:
        errors.append(f"{dim}.evidence_refs 为空或非 list——至少需要 1 条证据引用")

    # Check route_breakdown presence (route-level ratings)
    route_breakdown = ev.get("route_breakdown")
    if route_breakdown is None:
        errors.append(f"{dim}.route_breakdown 缺失——需要路线级评分")
    elif not isinstance(route_breakdown, (dict, list)):
        errors.append(
            f"{dim}.route_breakdown 类型异常: {type(route_breakdown).__name__}"
        )

    return ev, errors


def _check_tier_compliance(
    evaluations: dict[str, dict[str, Any] | None], run_dir: Path
) -> list[str]:
    """检查 tier 合规：full 路线 6 维齐，light 路线需标记跳过维度。"""
    errors: list[str] = []
    dcc_path = run_dir / "data_completeness_check.json"
    if not dcc_path.exists():
        return []  # No tier info, skip

    dcc = load_json(dcc_path)
    tier_summary = dcc.get("tier_summary", {})
    if not tier_summary:
        return []

    full_count = tier_summary.get("full_count", 0)
    light_count = tier_summary.get("light_count", 0)

    if light_count > 0 and full_count == 0:
        # All light: aux dims should be tier_light_skipped
        for dim in AUX_DIMS:
            ev = evaluations.get(dim)
            if ev is None:
                continue  # Already reported as missing
            ep = ev.get("execution_provenance", {}) or {}
            mode = ep.get("execution_mode", "")
            if mode != "tier_light_skipped":
                errors.append(
                    f"{dim} 应为 tier_light（仅有 light 路线），"
                    f"但 execution_mode='{mode}' 而非 'tier_light_skipped'"
                )

    return errors


def _check_cross_dimension_consistency(
    evaluations: dict[str, dict[str, Any] | None]
) -> list[str]:
    """检查跨维度基本一致性（非逻辑判断，只做硬规则）。"""
    errors: list[str] = []

    dq = evaluations.get("data_quality")
    if dq and dq.get("rating") == "blocked":
        # Data quality blocked → 提醒后续阶段必须标注
        pass  # Not an error per se, just a governance flag

    # If any dimension has score > 90 but rating == "weak", that's suspicious
    for dim, ev in evaluations.items():
        if ev is None:
            continue
        score = ev.get("score", 0)
        rating = ev.get("rating", "")
        if isinstance(score, (int, float)) and score > 90 and rating == "weak":
            errors.append(
                f"{dim}: score={score} 但 rating='weak'——高分与弱评级矛盾，请检查"
            )
        if isinstance(score, (int, float)) and score < 20 and rating == "strong":
            errors.append(
                f"{dim}: score={score} 但 rating='strong'——低分与强评级矛盾，请检查"
            )

    return errors


def validate_evaluations(run_dir: Path) -> tuple[bool, list[str]]:
    """验证所有 6 份评价。返回 (pass, errors)。"""
    all_errors: list[str] = []
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
        for err in errors:
            print(f"  - {err}")
        print(
            "\n请打回对应 Evaluation Agent 修复以上问题后重新校验。",
            file=sys.stderr,
        )

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
