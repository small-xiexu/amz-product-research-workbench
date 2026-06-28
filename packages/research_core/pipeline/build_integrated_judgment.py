#!/usr/bin/env python3
"""Build integrated_operator_judgment skeleton from P6 evaluations and evidence packets.

Generates the full judgment skeleton with all 9 deep analysis fields marked as
``__ai_judgment__`` placeholders. The skeleton is then filled in two stages:

- Stage 10a: Route Strategy Agent + Growth & Risk Agent (parallel) fill the 9
  deep analysis fields (5 route/competition fields + 4 growth/risk fields).
- Stage 10b: Lead Operator Agent validates the 9 fields, writes decision summary
  (final_verdict, confidence, etc.), and merges everything into the final judgment.

This script only produces the skeleton; it does NOT make operational judgments.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from packages.research_core.contracts.p6_contracts import P6_EVALUATION_DIMENSIONS
from packages.research_core.contracts.p7_contracts import (
    P7_SCHEMA_VERSION,
    P7_STAGE_ID,
)
from packages.research_core.pipeline._utils import load_json
from packages.research_core.pipeline.constants import VOC_MIN_REVIEW_THRESHOLD
from packages.research_core.pipeline.public_language import public_text


def build_integrated_judgment(run_dir: Path) -> dict[str, Any]:
    """Generate a handoff skeleton for downstream judgment Agents.

    The script prepares structure and lineage only.  It deliberately does not
    decide final_verdict, opportunity, risk, or next-step strategy; those fields
    belong to Route Strategy / Growth & Risk / Lead Operator Agents.
    """
    run_id = run_dir.name
    now = datetime.now().isoformat(timespec="seconds")

    evaluations = _load_evaluations(run_dir)
    summary = load_json(run_dir / "evaluations" / "evaluation_summary.json", required=False)
    route_matrix = load_json(run_dir / "route_matrix_confirm.json", required=False)

    recommended_route = _extract_recommended_route(route_matrix)
    rejected_routes = _extract_rejected_routes(route_matrix)
    constraints_applied = _build_constraints_applied(summary)
    evidence_refs = _collect_evidence_refs(evaluations, summary)

    # v2 深度运营分析字段（脚本生成骨架，Agent 填充内容）
    route_recommendation = _build_route_recommendation(route_matrix)
    route_tradeoff = _build_route_tradeoff(route_matrix)
    competitor_benchmark = _build_competitor_benchmark(run_dir)
    competitor_weakness_map = _build_competitor_weakness_map(run_dir)
    price_band_analysis = _build_price_band_analysis(run_dir)
    voc_to_spec = _build_voc_to_spec(run_dir)
    keyword_strategy = _build_keyword_strategy(run_dir)
    risk_mitigation = _build_risk_mitigation(evaluations)
    validation_roadmap = _build_validation_roadmap(evaluations)

    return {
        "schema_version": P7_SCHEMA_VERSION,
        "packet_id": "integrated_operator_judgment",
        "stage": P7_STAGE_ID,
        "run_id": run_id,
        "final_verdict": "blocked",
        "verdict_reason": (
            "脚本仅生成集成判断骨架，当前不满足交付条件；必须先完成 "
            "Route Strategy Agent、Growth & Risk Agent 与 Lead Operator Agent 的最终判断。"
        ),
        "recommended_route": recommended_route,
        "rejected_routes": rejected_routes,
        "biggest_opportunity": {
            "dimension": "__ai_judgment__",
            "detail": "__ai_judgment__",
        },
        "biggest_risk": {
            "dimension": "__ai_judgment__",
            "detail": "__ai_judgment__",
        },
        "required_next_actions": [
            "并行启动 Route Strategy Agent 与 Growth & Risk Agent，填充 9 个深度分析字段。",
            "深度分析校验通过后，启动 Lead Operator Agent 写入最终判断。",
        ],
        "operator_constraints": {
            "source_path": "evaluations/evaluation_summary.json",
            "constraints": summary.get("operator_judgment_constraints") or [],
        },
        "constraints_applied": constraints_applied,
        "evidence_refs": evidence_refs,
        "confidence": "low",
        "route_recommendation": route_recommendation,
        "route_tradeoff": route_tradeoff,
        "competitor_benchmark": competitor_benchmark,
        "competitor_weakness_map": competitor_weakness_map,
        "price_band_analysis": price_band_analysis,
        "voc_to_spec": voc_to_spec,
        "keyword_strategy": keyword_strategy,
        "risk_mitigation": risk_mitigation,
        "validation_roadmap": validation_roadmap,
        "generated_at": now,
        "execution_provenance": {
            "executed_by_agent": False,
            "agent_role": "Integrated Operator Judgment Skeleton",
            "execution_mode": "script_generated_skeleton",
            "subagent_id": "",
            "note": (
                "Script generated judgment skeleton with '__ai_judgment__' placeholders for 9 deep analysis fields "
                "and decision-summary fields. Stage 10a: Route Strategy Agent + Growth & Risk Agent "
                "(parallel spawn) fill the 9 deep fields. Stage 10b: Lead Operator Agent validates those fields, "
                "writes decision summary, and merges into final judgment. "
                "Report Generation Agent must transcribe only filled fields; '__ai_judgment__' placeholders in report_data.json mean 'analysis pending'."
            ),
        },
    }


def _load_evaluations(run_dir: Path) -> dict[str, Any]:
    evals: dict[str, Any] = {}
    eval_dir = run_dir / "evaluations"
    for dim in P6_EVALUATION_DIMENSIONS:
        path = eval_dir / f"{dim}_evaluation.json"
        if path.exists():
            evals[dim] = load_json(path)
    return evals


def _extract_recommended_route(route_matrix: dict[str, Any]) -> dict[str, Any]:
    selected = route_matrix.get("selected_routes") or []
    for route in selected:
        if isinstance(route, dict) and route.get("role") == "mainline":
            return {
                "name": route.get("route_name", route.get("name", "")),
                "role": route.get("role", "mainline"),
                "rationale": route.get("decision_reason", route.get("rationale", "")),
            }
    if selected:
        first = selected[0]
        if isinstance(first, dict):
            return {
                "name": first.get("route_name", first.get("name", "")),
                "role": first.get("role", "primary"),
                "rationale": first.get("decision_reason", first.get("rationale", "")),
            }
    return {"name": "", "role": "unknown", "rationale": "路线矩阵中无明确主路线"}


def _extract_rejected_routes(route_matrix: dict[str, Any]) -> list[dict[str, Any]]:
    rejected = route_matrix.get("rejected_routes") or []
    result: list[dict[str, Any]] = []
    for route in rejected:
        if isinstance(route, dict):
            result.append({
                "name": route.get("route_name", route.get("name", "")),
                "reason": route.get("rejection_reason", route.get("reason", "")),
            })
    return result


def _build_constraints_applied(summary: dict[str, Any]) -> list[str]:
    constraints = summary.get("operator_judgment_constraints") or []
    result: list[str] = []
    for c in constraints:
        if c and str(c).strip():
            result.append(str(c).strip())
    if not result:
        result.append("所有维度均未出现阻断项，可在建议进入小批量验证、建议先验证、建议暂停推进范围内判断")
    return [public_text(item) for item in result]


def _collect_evidence_refs(
    evaluations: dict[str, Any],
    summary: dict[str, Any],
) -> list[str]:
    refs: list[str] = []
    for dim, ev in evaluations.items():
        for ref in ev.get("evidence_refs") or []:
            if ref and isinstance(ref, str) and ref.strip():
                refs.append(ref.strip())
    # Add reference to evaluation_summary itself
    refs.append("evaluations/evaluation_summary.json")
    return refs


P7_OUTPUT_ARTIFACTS = [
    "analysis/integrated_operator_judgment.json",
]


def run_integrated_judgment(run_dir: Path) -> dict[str, Any]:
    """Generate judgment, write output file, update progress. Returns the judgment dict."""
    judgment = build_integrated_judgment(run_dir)

    analysis_dir = run_dir / "analysis"
    analysis_dir.mkdir(parents=True, exist_ok=True)
    output_path = analysis_dir / "integrated_operator_judgment.json"
    output_path.write_text(
        json.dumps(judgment, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    update_progress(run_dir, judgment)
    return judgment


def _build_route_recommendation(route_matrix: dict[str, Any] | None) -> dict[str, Any]:
    """生成路线推荐骨架。Agent 需填充每条路线的 opportunity/risk/differentiation/benchmark_asins。"""
    routes: list[dict[str, Any]] = []
    if route_matrix:
        for route in (route_matrix.get("selected_routes") or []):
            if isinstance(route, dict):
                routes.append({
                    "name": route.get("route_name", route.get("name", "")),
                    "role": route.get("role", ""),
                    "priority": route.get("priority", ""),
                    "opportunity": "__ai_judgment__",
                    "risk": "__ai_judgment__",
                    "differentiation": "__ai_judgment__",
                    "benchmark_asins": [],
                })
    return {
        "routes": routes,
        "primary_recommendation": "__ai_judgment__",
        "alternative_routes": [],
        "exclusion_reasons": [],
    }


def _build_competitor_benchmark(run_dir: Path) -> list[dict[str, Any]]:
    """从市场结构证据包提取竞品骨架。Agent 需填充 differentiation_direction/pricing_anchor/why_benchmark。"""
    ms_packet = load_json(run_dir / "market_structure" / "market_structure_evidence_packet.json", required=False)
    if not ms_packet:
        return []
    facts = ms_packet.get("facts") or {}
    if not isinstance(facts, dict):
        facts = {}
    top_asins = facts.get("top_asins") or facts.get("reference_asin_pool") or []
    if isinstance(top_asins, dict):
        top_asins = list(top_asins.values())
    result: list[dict[str, Any]] = []
    for asin_data in (top_asins if isinstance(top_asins, list) else [])[:10]:
        if isinstance(asin_data, dict):
            result.append({
                "asin": asin_data.get("asin", ""),
                "name": asin_data.get("name", asin_data.get("title", "")),
                "price": asin_data.get("price", ""),
                "monthly_sales": asin_data.get("monthly_sales", ""),
                "rating": asin_data.get("rating", ""),
                "route": asin_data.get("route_ref", ""),
                "differentiation_direction": "__ai_judgment__",
                "pricing_anchor": "__ai_judgment__",
                "why_benchmark": "__ai_judgment__",
            })
    return result


def _build_price_band_analysis(run_dir: Path) -> list[dict[str, Any]]:
    """从市场结构证据包提取价格带骨架。Agent 需填充 competitive_meaning/entry_recommendation。"""
    ms_packet = load_json(run_dir / "market_structure" / "market_structure_evidence_packet.json", required=False)
    if not ms_packet:
        return []
    facts = ms_packet.get("facts") or {}
    if not isinstance(facts, dict):
        facts = {}
    price_dist = facts.get("price_distribution") or {}
    bands = price_dist.get("bands") or price_dist.get("price_bands") or []
    result: list[dict[str, Any]] = []
    for band in (bands if isinstance(bands, list) else []):
        if isinstance(band, dict):
            result.append({
                "range": band.get("range", band.get("price_range", "")),
                "product_count": band.get("count", band.get("product_count", "")),
                "sales_share": band.get("sales_share", ""),
                "avg_rating": band.get("avg_rating", ""),
                "new_product_share": band.get("new_product_share", ""),
                "competitive_meaning": "__ai_judgment__",
                "entry_recommendation": "__ai_judgment__",
            })
    return result


def _get_voc_review_count(run_dir: Path) -> int:
    """Read VOC review count from voc_gate.json. Returns 0 if gate not found."""
    voc_gate = load_json(run_dir / "review_voc" / "voc_gate.json", required=False)
    if not voc_gate:
        return 0
    thresholds = voc_gate.get("thresholds") or {}
    return int(thresholds.get("current_total_reviews", 0))


def _build_voc_to_spec(run_dir: Path) -> list[dict[str, Any]]:
    """从 VOC 证据包提取痛点骨架。Agent 需填充 spec_requirement/benchmark_gap/differentiation_opportunity。"""
    voc_packet = load_json(run_dir / "review_voc" / "voc_evidence_packet.json", required=False)
    if not voc_packet:
        return []
    review_count = _get_voc_review_count(run_dir)
    is_degraded = review_count < VOC_MIN_REVIEW_THRESHOLD
    facts = voc_packet.get("facts") or {}
    if not isinstance(facts, dict):
        facts = {}
    pain_points = facts.get("pain_points") or facts.get("top_pain_points") or []
    result: list[dict[str, Any]] = []
    for pp in (pain_points if isinstance(pain_points, list) else [])[:8]:
        if isinstance(pp, dict):
            entry: dict[str, Any] = {
                "priority": pp.get("priority", "P1"),
                "dimension": pp.get("dimension", ""),
                "frequency": pp.get("review_count", pp.get("frequency", "")),
                "evidence_quotes": pp.get("evidence_quotes", [])[:3],
                "spec_requirement": "__ai_judgment__",
                "benchmark_gap": "__ai_judgment__",
                "differentiation_opportunity": "__ai_judgment__",
            }
            if is_degraded:
                entry["data_note"] = f"样本不足（仅 {review_count} 条评论），评论采集完成后重新推导"
                entry["issue_description"] = f"基于有限样本（{review_count} 条评论），__ai_judgment__"
            result.append(entry)
    return result


def _build_keyword_strategy(run_dir: Path) -> dict[str, Any]:
    """从搜索需求证据包提取关键词骨架。Agent 需填充 strategy_rationale 和 strategy_note。"""
    sd_packet = load_json(run_dir / "search_demand" / "search_demand_evidence_packet.json", required=False)
    if not sd_packet:
        return {"primary_attack": [], "testable": [], "negative": [], "strategy_note": "__ai_judgment__"}
    facts = sd_packet.get("facts") or {}
    if not isinstance(facts, dict):
        facts = {}
    kw_pool = facts.get("keyword_pool_by_role") or facts.get("keyword_pool") or {}
    result: dict[str, Any] = {"primary_attack": [], "testable": [], "negative": [], "strategy_note": "__ai_judgment__"}
    for role_key, target_key in [("primary_attack", "primary_attack"), ("testable", "testable"), ("negative", "negative")]:
        kws = kw_pool.get(role_key) or []
        for kw in (kws if isinstance(kws, list) else [])[:10]:
            if isinstance(kw, dict):
                result[target_key].append({
                    "keyword": kw.get("keyword", kw.get("term", "")),
                    "monthly_search_volume": kw.get("monthly_search_volume", ""),
                    "cpc": kw.get("cpc", ""),
                    "competitor_count": kw.get("competitor_count", ""),
                    "strategy_rationale": "__ai_judgment__",
                })
    return result


def _build_risk_mitigation(evaluations: dict[str, Any]) -> list[dict[str, Any]]:
    """从风险评价提取风险骨架。Agent 需填充 operational_meaning/mitigation_path。"""
    risk_eval = evaluations.get("risk") or {}
    risks = risk_eval.get("risks") or []
    result: list[dict[str, Any]] = []
    for risk in (risks if isinstance(risks, list) else [])[:8]:
        if isinstance(risk, dict):
            result.append({
                "risk": risk.get("risk", risk.get("description", "")),
                "severity": risk.get("severity", risk.get("level", "")),
                "likelihood": risk.get("likelihood", ""),
                "operational_meaning": "__ai_judgment__",
                "mitigation_path": "__ai_judgment__",
            })
        elif isinstance(risk, str):
            result.append({
                "risk": risk,
                "severity": "",
                "likelihood": "",
                "operational_meaning": "__ai_judgment__",
                "mitigation_path": "__ai_judgment__",
            })
    return result


def _build_route_tradeoff(route_matrix: dict[str, Any] | None) -> list[dict[str, Any]]:
    """生成路线取舍分析骨架。Agent 需填充 gain/lose/best_for/worst_for。"""
    routes: list[dict[str, Any]] = []
    if route_matrix:
        for route in (route_matrix.get("selected_routes") or []):
            if isinstance(route, dict):
                routes.append({
                    "route_name": route.get("route_name", route.get("name", "")),
                    "gain": "__ai_judgment__",
                    "lose": "__ai_judgment__",
                    "best_for": "__ai_judgment__",
                    "worst_for": "__ai_judgment__",
                })
    return routes


def _build_competitor_weakness_map(run_dir: Path) -> list[dict[str, Any]]:
    """从 VOC 证据包提取竞品弱点骨架。Agent 需填充 fatal_weakness/my_counter/counter_difficulty，route 从路线矩阵补。"""
    voc_packet = load_json(run_dir / "review_voc" / "voc_evidence_packet.json", required=False)
    if not voc_packet:
        return []
    facts = voc_packet.get("facts") or {}
    if not isinstance(facts, dict):
        facts = {}
    pain_points = facts.get("pain_points") or facts.get("top_pain_points") or []
    seen_asins: set[str] = set()
    result: list[dict[str, Any]] = []
    for pp in (pain_points if isinstance(pain_points, list) else []):
        if isinstance(pp, dict):
            for ref in (pp.get("evidence_refs") or [])[:2]:
                if isinstance(ref, dict):
                    asin = ref.get("asin", "")
                    if asin and asin not in seen_asins:
                        seen_asins.add(asin)
                        result.append({
                            "asin": asin,
                            "route": "__ai_judgment__",
                            "fatal_weakness": "__ai_judgment__",
                            "voc_evidence": ref.get("quote", ""),
                            "my_counter": "__ai_judgment__",
                            "counter_difficulty": "__ai_judgment__",
                        })
    return result


def _build_validation_roadmap(evaluations: dict[str, Any]) -> list[dict[str, Any]]:
    """生成验证路线图骨架。

    Agent 需根据品类特征填充每条 action 的具体内容、通过标准和不通过应对。
    骨架提供了运营基线阶段结构——阶段名和关键里程碑是固定的，actions 内具体步骤由 Agent 细化。
    """
    risk_eval = evaluations.get("risk", {})
    risk_items = risk_eval.get("risks", risk_eval.get("route_evaluations", [])) if isinstance(risk_eval, dict) else []
    has_safety_risk = any(
        "安全" in _risk_name_for_match(r) or "safety" in _risk_name_for_match(r).lower()
        for r in (risk_items if isinstance(risk_items, list) else [])
    )

    phase1_actions = [
        "__ai_judgment__品牌注册：完成亚马逊品牌注册（Brand Registry）→ 解锁 A+页面、Vine计划、品牌旗舰店、品牌分析报告。如果美国商标尚未下证，此项为阶段0前置。",
    ]
    if has_safety_risk:
        phase1_actions.append("__ai_judgment__品质工程验证：安全可靠性项目（关键结构件/功能件等）送第三方测试，取得测试报告。")

    return [
        {
            "phase": "阶段1：上线前准备（Week 1-4，品牌注册 + 品质验证）",
            "actions": phase1_actions,
            "exit_criteria": "__ai_judgment__",
            "if_fail": "__ai_judgment__",
        },
        {
            "phase": "阶段2：小规模市场验证（Week 5-12，首发 + 广告测试）",
            "actions": [
                "__ai_judgment__最小可行上线：首单FBA + Listing完整搭建（已有品牌注册→A+页面可用）。",
                "__ai_judgment__Vine送测 + 广告小规模测试 + 竞品监控。",
            ],
            "exit_criteria": "__ai_judgment__",
            "if_fail": "__ai_judgment__",
        },
        {
            "phase": "阶段3：规模化放量（Week 13-26，补货 + 广告放量 + 品牌深化）",
            "actions": [
                "__ai_judgment__补货决策 + 广告放量 + 品牌旗舰店建设 + 评论积累。",
            ],
            "exit_criteria": "__ai_judgment__",
            "if_fail": "__ai_judgment__",
        },
    ]


def _risk_name_for_match(risk: Any) -> str:
    if isinstance(risk, dict):
        return str(risk.get("risk_name", risk.get("risk", risk.get("description", ""))))
    return str(risk)


def update_progress(run_dir: Path, judgment: dict[str, Any]) -> None:
    progress_path = run_dir / "progress.json"
    progress = load_json(progress_path, required=False)
    if not progress:
        progress = {
            "schema_version": "p0-contract-v1",
            "current_stage": P7_STAGE_ID,
            "stages": {},
            "updated_at": "",
            "global_blockers": [],
            "next_action": {},
            "completed_artifacts": [],
        }

    stages = progress.setdefault("stages", {})
    stages[P7_STAGE_ID] = {
        "status": "running",
        "attempts": 1,
        "started_at": judgment.get("generated_at", ""),
        "input_artifacts": [
            "evaluations/evaluation_summary.json",
            "route_matrix_confirm.json",
        ],
        "output_artifacts": [
            "analysis/integrated_operator_judgment.json",
        ],
        "validation_checks": [
            {
                "name": "judgment_skeleton_generated",
                "pass": True,
                "detail": "脚本只生成骨架，等待 Stage 10a/10b Agent 填写最终判断。",
            }
        ],
        "resume_policy": {
            "reuse_existing_artifacts": True,
            "allow_repeat_mcp_call": False,
        },
        "notes": (
            "集成判断骨架已生成；最终判断需由 Lead Operator Agent 写入。"
        ),
    }

    artifact = "analysis/integrated_operator_judgment.json"
    progress["completed_artifacts"] = [
        item for item in (progress.get("completed_artifacts") or []) if item != artifact
    ]

    progress["current_stage"] = P7_STAGE_ID
    progress["updated_at"] = judgment.get("generated_at", "")
    progress["next_action"] = {
        "type": "ai_step",
        "stage_id": P7_STAGE_ID,
        "description": (
            "脚本阶段完成，集成判断骨架已生成。下一步："
            "深度分析阶段 — 强制并行启动 Route Strategy Agent + Growth & Risk Agent，"
            "填充 9 个深度分析字段；随后启动 Lead Operator Agent 写入最终判断。"
        ),
    }

    progress_path.write_text(
        json.dumps(progress, ensure_ascii=False, indent=2), encoding="utf-8"
    )
