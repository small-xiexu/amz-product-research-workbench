#!/usr/bin/env python3
"""P6 evaluation_summary — pure governance aggregation.

Agent 先产出 6 份评价 JSON 到 evaluations/ 目录。本脚本只做：
  - 校验 6 份评价文件的 schema
  - 聚合为 evaluation_summary（跨维度张力检测、blocked 规则、P0 治理约束）
  - 更新 progress.json

脚本不再自行从 evidence packet 生成评价。
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from packages.research_core.contracts.p0_contracts import summarize_evaluation_constraints
from packages.research_core.contracts.validators import ContractValidationError
from packages.research_core.pipeline._utils import load_json


P6_SCHEMA_VERSION = "p6-evaluation-v1"
P6_STAGE_ID = "stage_8_evaluation"
EVALUATIONS_DIR = "evaluations"

P6_INPUT_ARTIFACTS = [
    "evaluations/market_demand_evaluation.json",
    "evaluations/competition_evaluation.json",
    "evaluations/price_profit_evaluation.json",
    "evaluations/voc_opportunity_evaluation.json",
    "evaluations/risk_evaluation.json",
    "evaluations/data_quality_evaluation.json",
    "progress.json",
]
P6_OUTPUT_ARTIFACTS = [
    "evaluations/market_demand_evaluation.json",
    "evaluations/competition_evaluation.json",
    "evaluations/price_profit_evaluation.json",
    "evaluations/voc_opportunity_evaluation.json",
    "evaluations/risk_evaluation.json",
    "evaluations/data_quality_evaluation.json",
    "evaluations/evaluation_summary.json",
]


class P6EvaluationError(ContractValidationError):
    """Raised when evaluations cannot be generated."""


# ── Main entry ─────────────────────────────────────────────────────────────

def run_evaluations(run_dir: Path | str) -> dict[str, Path]:
    """Read 6 Agent-produced evaluation files, validate, synthesize.

    Supports tier-based evaluation: light routes only require market_demand
    and data_quality evaluations. Missing non-core dimensions for light-only
    runs get tier_light placeholder entries instead of raising an error.
    """
    run_path = Path(run_dir).expanduser().resolve()
    now = datetime.now(timezone.utc).isoformat()
    run_id = run_path.name

    eval_dir = run_path / EVALUATIONS_DIR
    core_dims = ["market_demand", "data_quality"]
    aux_dims = ["competition", "price_profit", "voc_opportunity", "risk"]
    dims = core_dims + aux_dims
    required_fields = {"score", "rating", "confidence", "key_reasons", "risks", "required_followups", "evidence_refs"}

    # Read tier info
    tier_info = _read_tier_info(run_path)
    all_light = tier_info is not None and tier_info.get("light_count", 0) > 0 and tier_info.get("full_count", 0) == 0

    evaluations: dict[str, dict[str, Any]] = {}
    missing: list[str] = []
    for dim in dims:
        path = eval_dir / f"{dim}_evaluation.json"
        if not path.is_file():
            if all_light and dim in aux_dims:
                # Light route: auxiliary dimensions get placeholder
                evaluations[dim] = _tier_light_placeholder(dim, run_id, now)
                continue
            missing.append(dim)
            continue
        ev = load_json(path)
        ev_missing = required_fields - set(ev.keys())
        if ev_missing:
            print(f"[ERROR] {dim}_evaluation.json missing fields: {ev_missing}", file=sys.stderr)
            missing.append(dim)
            continue
        evaluations[dim] = ev

    if missing:
        print(
            f"[ERROR] 请先运行 6 个 Evaluation Agent 产出评价文件。"
            f"缺失：{missing}",
            file=sys.stderr,
        )
        raise P6EvaluationError(
            f"Agent 评价文件不完整，缺少 {len(missing)}/{len(dims)} 项: {missing}"
        )

    summary = _build_summary(evaluations, run_id, now, tier_info)

    summary_path = eval_dir / "evaluation_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    progress = load_json(run_path / "progress.json")
    updated_progress = _update_progress(progress, evaluations, summary, run_path)
    (run_path / "progress.json").write_text(
        json.dumps(updated_progress, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    output_paths: dict[str, Path] = {}
    for dim in dims:
        output_paths[f"{dim}_evaluation"] = eval_dir / f"{dim}_evaluation.json"
    output_paths["evaluation_summary"] = summary_path
    output_paths["progress"] = run_path / "progress.json"
    return output_paths


# ── Tier support ────────────────────────────────────────────────────────────

def _read_tier_info(run_path: Path) -> dict[str, Any] | None:
    """Read tier classification from data_completeness_check.json."""
    dcc_path = run_path / "data_completeness_check.json"
    if not dcc_path.is_file():
        return None
    dcc = load_json(dcc_path)
    return dcc.get("tier_summary")


def _tier_light_placeholder(dim: str, run_id: str, now: str) -> dict[str, Any]:
    """Generate a placeholder evaluation for a light-route skipped dimension."""
    return {
        "schema_version": P6_SCHEMA_VERSION,
        "packet_id": f"{dim}_evaluation",
        "stage": "evaluation",
        "score": 0,
        "rating": "watch",
        "confidence": "low",
        "key_reasons": [f"[tier_light] 该路线数据不足（参考ASIN<2 或搜索量<5K），跳过完整{dim}评价"],
        "risks": ["路线数据不足以支撑该维度判断"],
        "required_followups": ["补足参考ASIN和搜索量数据后可重新评价"],
        "evidence_refs": ["data_completeness_check.json#tier_summary"],
        "execution_provenance": {
            "executed_by_agent": False,
            "agent_role": f"{dim} Evaluation Agent",
            "execution_mode": "tier_light_skipped",
            "subagent_id": "",
            "note": f"轻量路线自动跳过 {dim} 评价（仅做 market_demand + data_quality 二维定性）",
        },
    }


# ── evaluation_summary ─────────────────────────────────────────────────────

def _build_summary(
    evaluations: dict[str, dict[str, Any]],
    run_id: str,
    now: str,
    tier_info: dict[str, Any] | None = None,
) -> dict[str, Any]:
    dim_results: dict[str, dict[str, Any]] = {}
    blocked_dims: list[str] = []
    low_conf_dims: list[str] = []
    tensions: list[str] = []

    for dim, ev in evaluations.items():
        dim_results[dim] = {
            "score": ev["score"],
            "rating": ev["rating"],
            "confidence": ev["confidence"],
            "key_reasons": ev["key_reasons"][:3],
            "risks": ev["risks"],
            "required_followups": ev["required_followups"],
            "evidence_refs": ev["evidence_refs"],
        }
        if ev["rating"] == "blocked":
            blocked_dims.append(dim)
        if ev["confidence"] == "low":
            low_conf_dims.append(dim)

    # Cross-dimension tensions
    tensions = _detect_tensions(evaluations)

    # Use P0 governance logic
    summary_for_p0 = {
        "dimension_results": dim_results,
        "blocked_dimensions": blocked_dims,
        "low_confidence_dimensions": low_conf_dims,
    }
    constraints = summarize_evaluation_constraints(summary_for_p0)

    result: dict[str, Any] = {
        "schema_version": P6_SCHEMA_VERSION,
        "packet_id": "evaluation_summary",
        "stage": "evaluation_summary",
        "dimension_results": dim_results,
        "blocked_dimensions": blocked_dims,
        "low_confidence_dimensions": low_conf_dims,
        "cross_dimension_tensions": tensions,
        "operator_judgment_constraints": constraints.get("operator_judgment_constraints", []),
        "recommended_final_verdict_range": constraints.get("recommended_final_verdict_range", ["go", "watch", "no_go"]),
        "execution_provenance": {
            "executed_by_agent": False,
            "agent_role": "Lead Operator Agent (upstream)",
            "execution_mode": "serial_fallback",
            "subagent_id": "",
            "note": "evaluation_summary 由脚本聚合 6 个分项评价，应用 P0 治理规则生成约束，供 P7 资深运营专家 Agent 使用。",
        },
    }
    if tier_info:
        result["tier_summary"] = tier_info
    return result


def _detect_tensions(evaluations: dict[str, dict[str, Any]]) -> list[dict[str, str]]:
    tensions: list[dict[str, str]] = []
    market = evaluations.get("market_demand", {})
    voc = evaluations.get("voc_opportunity", {})
    competition = evaluations.get("competition", {})
    price = evaluations.get("price_profit", {})
    dq = evaluations.get("data_quality", {})

    if voc.get("rating") == "strong" and market.get("rating") in ("weak", "blocked"):
        tensions.append({
            "tension": "VOC 机会强但市场需求弱",
            "detail": "VOC 痛点明确但搜索/市场信号不足。可能是一个小众高需求方向，也可能是因为市场数据不足导致的误判。",
            "resolution_hint": "P7 资深运营专家需判断: 是否因数据不足导致市场信号弱，还是这个方向真实需求有限。",
        })
    if market.get("rating") == "strong" and competition.get("rating") in ("weak", "blocked"):
        tensions.append({
            "tension": "市场需求强但竞争 blocked",
            "detail": "市场容量/需求存在但竞争结构不支持直接进入。",
            "resolution_hint": "P7 需评估: 是否可以通过差异化路线避开竞争，还是竞争壁垒确实无法突破。",
        })
    if market.get("rating") == "strong" and price.get("rating") in ("weak", "blocked"):
        tensions.append({
            "tension": "市场需求强但价格带 blocked",
            "detail": "需求存在但价格带支撑不足。",
            "resolution_hint": "P7 需评估: 目标价格带是否可通过产品差异化实现溢价。",
        })
    if dq.get("rating") == "blocked":
        tensions.append({
            "tension": "数据质量 blocked",
            "detail": "数据样本不足或存在未解决的 blocking 冲突，当前不能形成任何强结论。",
            "resolution_hint": "必须先补数或解决冲突，再重新运行 P6 评价。",
        })
    return tensions


def _update_progress(
    progress: dict[str, Any],
    evaluations: dict[str, dict[str, Any]],
    summary: dict[str, Any],
    run_path: Path,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    stages = dict(progress.get("stages", {}))
    stage_8 = dict(stages.get(P6_STAGE_ID, {}))

    stage_8["status"] = "done"
    stage_8["updated_at"] = now
    stage_8["output_artifacts"] = P6_OUTPUT_ARTIFACTS
    stage_8["attempts"] = stage_8.get("attempts", 0) + 1

    stages[P6_STAGE_ID] = stage_8
    completed = list(progress.get("completed_artifacts", []))
    for art in P6_OUTPUT_ARTIFACTS:
        if art not in completed:
            completed.append(art)

    # Determine next_action from summary
    blocked = summary.get("blocked_dimensions", [])
    verdict_range = summary.get("recommended_final_verdict_range", [])
    if "data_quality" in blocked:
        next_desc = "数据质量 blocked — 必须先补数或解决冲突，再重新运行 P6"
        next_substage = "P6"
    elif blocked:
        next_desc = f"核心维度 blocked: {', '.join(blocked)} — 不能直接 go，转到 P7 资深运营专家判断"
        next_substage = "P7"
    else:
        next_desc = "评价完成，转到 P7 资深运营专家综合判断"
        next_substage = "P7"

    return {
        **progress,
        "current_stage": P6_STAGE_ID,
        "stages": stages,
        "completed_artifacts": completed,
        "updated_at": now,
        "next_action": {
            "type": "proceed",
            "description": next_desc,
            "stage_id": P6_STAGE_ID,
            "next_substage": next_substage,
            "user_action_required": False,
        },
        "warnings": progress.get("warnings", []),
    }


# ── CLI ────────────────────────────────────────────────────────────────────

def _cli_main() -> int:
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="P6: Build evaluations and evaluation_summary")
    parser.add_argument("run_dir", type=str, help="Path to run directory")
    args = parser.parse_args()

    try:
        output_paths = run_evaluations(args.run_dir)
        print(f"P6 evaluations complete. Outputs:")
        for name, path in sorted(output_paths.items()):
            print(f"  {name}: {path}")
        return 0
    except P6EvaluationError as e:
        print(f"P6 evaluation error: {e}", file=sys.stderr)
        return 2
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(_cli_main())
