#!/usr/bin/env python3
"""Build integrated_operator_judgment from P6 evaluations and evidence packets.

Deterministic judgment logic that applies P0 governance rules to produce
a final go/watch/no_go verdict with structured reasoning.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from packages.research_core.contracts.p6_contracts import (
    P6_CORE_DIMENSIONS,
    P6_EVALUATION_DIMENSIONS,
)
from packages.research_core.contracts.p7_contracts import (
    P7_SCHEMA_VERSION,
    P7_STAGE_ID,
    P7_ALLOWED_VERDICTS,
)
from packages.research_core.pipeline._utils import load_json


def build_integrated_judgment(run_dir: Path) -> dict[str, Any]:
    """Generate integrated_operator_judgment from P6 evaluation outputs."""
    run_id = run_dir.name
    now = datetime.now().isoformat(timespec="seconds")

    evaluations = _load_evaluations(run_dir)
    summary = load_json(run_dir / "evaluations" / "evaluation_summary.json", required=False)
    route_matrix = load_json(run_dir / "route_matrix_confirm.json", required=False)

    final_verdict = _determine_verdict(summary, evaluations)
    verdict_reason = _build_verdict_reason(final_verdict, evaluations, summary)
    recommended_route = _extract_recommended_route(route_matrix)
    rejected_routes = _extract_rejected_routes(route_matrix)
    biggest_opportunity = _find_biggest_opportunity(evaluations)
    biggest_risk = _find_biggest_risk(evaluations, summary)
    required_next_actions = _build_next_actions(final_verdict, evaluations, summary)
    constraints_applied = _build_constraints_applied(summary)
    evidence_refs = _collect_evidence_refs(evaluations, summary)
    confidence = _determine_confidence(evaluations, summary)

    # v2 深度运营分析字段（脚本生成骨架，Agent 填充内容）
    route_recommendation = _build_route_recommendation(route_matrix)
    route_tradeoff = _build_route_tradeoff(route_matrix)
    competitor_benchmark = _build_competitor_benchmark(run_dir)
    competitor_weakness_map = _build_competitor_weakness_map(run_dir)
    cold_start_estimate = _build_cold_start_estimate(run_dir)
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
        "final_verdict": final_verdict,
        "verdict_reason": verdict_reason,
        "recommended_route": recommended_route,
        "rejected_routes": rejected_routes,
        "biggest_opportunity": biggest_opportunity,
        "biggest_risk": biggest_risk,
        "required_next_actions": required_next_actions,
        "constraints_applied": constraints_applied,
        "evidence_refs": evidence_refs,
        "confidence": confidence,
        "route_recommendation": route_recommendation,
        "route_tradeoff": route_tradeoff,
        "competitor_benchmark": competitor_benchmark,
        "competitor_weakness_map": competitor_weakness_map,
        "cold_start_estimate": cold_start_estimate,
        "price_band_analysis": price_band_analysis,
        "voc_to_spec": voc_to_spec,
        "keyword_strategy": keyword_strategy,
        "risk_mitigation": risk_mitigation,
        "validation_roadmap": validation_roadmap,
        "generated_at": now,
        "execution_provenance": {
            "executed_by_agent": False,
            "agent_role": "Integrated Operator Judgment",
            "execution_mode": "serial_fallback",
            "subagent_id": "",
            "note": "Deterministic judgment from P6 evaluations + P0 governance rules",
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


def _determine_verdict(
    summary: dict[str, Any],
    evaluations: dict[str, Any],
) -> str:
    verdict_range = summary.get("recommended_final_verdict_range", [])

    if "blocked" in verdict_range:
        return "blocked"

    blocked = set(summary.get("blocked_dimensions") or [])
    core_blocked = blocked & P6_CORE_DIMENSIONS

    # Count strong/watch dimensions
    strong_count = 0
    watch_count = 0
    for dim, ev in evaluations.items():
        rating = ev.get("rating", "")
        if rating == "strong":
            strong_count += 1
        elif rating == "watch":
            watch_count += 1

    if "go" in verdict_range:
        if core_blocked:
            return "watch"
        if strong_count >= 4:
            return "go"
        if strong_count + watch_count >= 4:
            return "watch"
        return "watch"

    # verdict_range is ["watch", "no_go"]
    if strong_count + watch_count >= 3:
        return "watch"
    return "no_go"


def _build_verdict_reason(
    verdict: str,
    evaluations: dict[str, Any],
    summary: dict[str, Any],
) -> str:
    blocked = summary.get("blocked_dimensions") or []
    low_conf = summary.get("low_confidence_dimensions") or []
    tensions = summary.get("cross_dimension_tensions") or []

    parts: list[str] = []

    if verdict == "blocked":
        parts.append("数据质量不达标")
        if tensions:
            parts.append("；".join(str(t) for t in tensions[:2]))
        return "，".join(parts) + "，必须先补数再推进。"

    if verdict == "go":
        parts.append("6 项评价维度整体信号偏正面")
        strong_dims = [
            d for d, ev in evaluations.items() if ev.get("rating") == "strong"
        ]
        if strong_dims:
            dim_names = {
                "market_demand": "市场需求",
                "competition": "竞争格局",
                "price_profit": "价格利润",
                "voc_opportunity": "VOC机会",
                "risk": "风险",
                "data_quality": "数据质量",
            }
            strong_labels = [dim_names.get(d, d) for d in strong_dims[:4]]
            parts.append(f"{'、'.join(strong_labels)}均处于 strong 水平")
        if low_conf:
            parts.append(f"{len(low_conf)} 项低置信度，P7 会跟踪但暂不阻断")
        return "，".join(parts) + "。"

    if verdict == "watch":
        if blocked:
            core_blocked = [d for d in blocked if d in P6_CORE_DIMENSIONS]
            if core_blocked:
                parts.append(f"核心维度 blocked: {', '.join(core_blocked)}")
                parts.append("不能直接 go，需补充信息后重新评估")
                return "，".join(parts) + "。"
            else:
                parts.append(f"辅助维度 blocked: {', '.join(blocked)}")
                parts.append("核心维度无阻塞，但需关注辅助维度风险后谨慎推进")
                return "，".join(parts) + "。"
        weak_dims = [
            d for d, ev in evaluations.items() if ev.get("rating") in ("weak", "blocked")
        ]
        if weak_dims:
            dim_names = {
                "market_demand": "市场需求",
                "competition": "竞争格局",
                "price_profit": "价格利润",
                "voc_opportunity": "VOC机会",
                "risk": "风险",
                "data_quality": "数据质量",
            }
            weak_labels = [dim_names.get(d, d) for d in weak_dims]
            parts.append(f"{'、'.join(weak_labels)}信号偏弱")
        if low_conf:
            parts.append(f"{len(low_conf)} 项置信度偏低")
        parts.append("建议补充数据后再做最终判断")
        return "，".join(parts) + "。"

    # no_go
    if blocked:
        parts.append(f"关键维度 blocked: {', '.join(blocked[:3])}")
    parts.append("核心条件不满足，建议暂缓推进")
    return "，".join(parts) + "。"


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


def _find_biggest_opportunity(evaluations: dict[str, Any]) -> dict[str, Any]:
    best_dim = ""
    best_score = -1
    for dim, ev in evaluations.items():
        score = ev.get("score", 0)
        if isinstance(score, (int, float)) and score > best_score:
            best_score = float(score)
            best_dim = dim

    if best_dim and best_dim in evaluations:
        ev = evaluations[best_dim]
        return {
            "dimension": best_dim,
            "score": ev.get("score", 0),
            "rating": ev.get("rating", ""),
            "top_reason": (ev.get("key_reasons") or [""])[0],
        }
    return {"dimension": "", "score": 0, "rating": "", "top_reason": "无足够数据识别机会"}


def _find_biggest_risk(
    evaluations: dict[str, Any],
    summary: dict[str, Any],
) -> dict[str, Any]:
    blocked = set(summary.get("blocked_dimensions") or [])
    if blocked:
        blk = next(iter(blocked))
        if blk in evaluations:
            ev = evaluations[blk]
            return {
                "dimension": blk,
                "score": ev.get("score", 0),
                "rating": "blocked",
                "top_risk": (ev.get("risks") or ["数据阻塞"])[0] if ev.get("risks") else "数据阻塞",
            }

    worst_dim = ""
    worst_score = 999
    for dim, ev in evaluations.items():
        score = ev.get("score", 0)
        if isinstance(score, (int, float)) and score < worst_score:
            worst_score = float(score)
            worst_dim = dim

    if worst_dim and worst_dim in evaluations:
        ev = evaluations[worst_dim]
        return {
            "dimension": worst_dim,
            "score": ev.get("score", 0),
            "rating": ev.get("rating", ""),
            "top_risk": (ev.get("risks") or ["信号偏弱"])[0] if ev.get("risks") else "信号偏弱",
        }
    return {"dimension": "", "score": 0, "rating": "", "top_risk": "无法评估"}


def _build_next_actions(
    verdict: str,
    evaluations: dict[str, Any],
    summary: dict[str, Any],
) -> list[str]:
    actions: list[str] = []

    if verdict == "blocked":
        actions.append("补齐阻塞数据：检查 data_quality_evaluation 的 required_followups")
        actions.append("解决 blocking_conflicts 后重新触发 P4→P6 流程")

    for dim, ev in evaluations.items():
        rating = ev.get("rating", "")
        if rating in ("weak", "blocked"):
            followups = ev.get("required_followups") or []
            for fu in followups[:2]:
                if fu and str(fu).strip():
                    actions.append(str(fu).strip())

    low_conf = summary.get("low_confidence_dimensions") or []
    if low_conf:
        actions.append(f"跟踪低置信度维度: {', '.join(low_conf[:3])}，下次迭代优先验证")

    if verdict == "go":
        actions.append("进入供应商阶段：基于推荐路线和价格带联系供应商打样")
        actions.append("根据 VOC 痛点制定品质验收标准")
    elif verdict == "watch":
        actions.append("补齐关键缺口后重新评估，重点关注 blocked/weak 维度")
    elif verdict == "no_go":
        # Look for alternative routes that weren't selected
        actions.append("不建议当前路线推进，可考虑评估路线矩阵中的备选路线")

    seen: set[str] = set()
    result: list[str] = []
    for action in actions:
        if action and action not in seen:
            seen.add(action)
            result.append(action)
    return result


def _build_constraints_applied(summary: dict[str, Any]) -> list[str]:
    constraints = summary.get("operator_judgment_constraints") or []
    result: list[str] = []
    for c in constraints:
        if c and str(c).strip():
            result.append(str(c).strip())
    if not result:
        result.append("所有维度均未 blocked，P7 可在 go/watch/no_go 范围内自由判断")
    return result


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


def _determine_confidence(
    evaluations: dict[str, Any],
    summary: dict[str, Any],
) -> str:
    low_conf_dims = set(summary.get("low_confidence_dimensions") or [])
    blocked_dims = set(summary.get("blocked_dimensions") or [])

    # More than half dimensions low confidence = overall low
    if len(low_conf_dims) >= 3:
        return "low"

    # Any core dimension blocked or low = medium at best
    if (low_conf_dims | blocked_dims) & P6_CORE_DIMENSIONS:
        return "medium"

    # Check how many dimensions are high confidence
    high_count = 0
    for dim, ev in evaluations.items():
        if ev.get("confidence") == "high" and dim not in blocked_dims:
            high_count += 1

    if high_count >= 4:
        return "high"
    if high_count >= 2:
        return "medium"
    return "low"


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
                    "opportunity": "",
                    "risk": "",
                    "differentiation": "",
                    "benchmark_asins": [],
                })
    return {
        "routes": routes,
        "primary_recommendation": "",
        "alternative_routes": [],
        "exclusion_reasons": [],
    }


def _build_competitor_benchmark(run_dir: Path) -> list[dict[str, Any]]:
    """从市场结构证据包提取竞品骨架。Agent 需填充 differentiation/pricing_anchor。"""
    ms_packet = load_json(run_dir / "market_structure" / "market_structure_evidence_packet.json", required=False)
    if not ms_packet:
        return []
    facts = ms_packet.get("facts") or {}
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
                "differentiation_direction": "",
                "pricing_anchor": "",
                "why_benchmark": "",
            })
    return result


def _build_price_band_analysis(run_dir: Path) -> list[dict[str, Any]]:
    """从市场结构证据包提取价格带骨架。Agent 需填充 competitive_meaning/entry_recommendation。"""
    ms_packet = load_json(run_dir / "market_structure" / "market_structure_evidence_packet.json", required=False)
    if not ms_packet:
        return []
    facts = ms_packet.get("facts") or {}
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
                "competitive_meaning": "",
                "entry_recommendation": "",
            })
    return result


def _build_voc_to_spec(run_dir: Path) -> list[dict[str, Any]]:
    """从 VOC 证据包提取痛点骨架。Agent 需填充 spec_requirement/benchmark_gap/differentiation_opportunity。"""
    voc_packet = load_json(run_dir / "review_voc" / "voc_evidence_packet.json", required=False)
    if not voc_packet:
        return []
    facts = voc_packet.get("facts") or {}
    pain_points = facts.get("pain_points") or facts.get("top_pain_points") or []
    result: list[dict[str, Any]] = []
    for pp in (pain_points if isinstance(pain_points, list) else [])[:8]:
        if isinstance(pp, dict):
            result.append({
                "priority": pp.get("priority", "P1"),
                "dimension": pp.get("dimension", ""),
                "frequency": pp.get("review_count", pp.get("frequency", "")),
                "evidence_quotes": pp.get("evidence_quotes", [])[:3],
                "spec_requirement": "",
                "benchmark_gap": "",
                "differentiation_opportunity": "",
            })
    return result


def _build_keyword_strategy(run_dir: Path) -> dict[str, Any]:
    """从搜索需求证据包提取关键词骨架。Agent 需填充 strategy_rationale。"""
    sd_packet = load_json(run_dir / "search_demand" / "search_demand_evidence_packet.json", required=False)
    if not sd_packet:
        return {"primary_attack": [], "testable": [], "negative": [], "strategy_note": ""}
    facts = sd_packet.get("facts") or {}
    kw_pool = facts.get("keyword_pool_by_role") or facts.get("keyword_pool") or {}
    result: dict[str, Any] = {"primary_attack": [], "testable": [], "negative": [], "strategy_note": ""}
    for role_key, target_key in [("primary_attack", "primary_attack"), ("testable", "testable"), ("negative", "negative")]:
        kws = kw_pool.get(role_key) or []
        for kw in (kws if isinstance(kws, list) else [])[:10]:
            if isinstance(kw, dict):
                result[target_key].append({
                    "keyword": kw.get("keyword", kw.get("term", "")),
                    "monthly_search_volume": kw.get("monthly_search_volume", ""),
                    "cpc": kw.get("cpc", ""),
                    "competitor_count": kw.get("competitor_count", ""),
                    "strategy_rationale": "",
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
                "operational_meaning": "",
                "mitigation_path": "",
            })
        elif isinstance(risk, str):
            result.append({
                "risk": risk,
                "severity": "",
                "likelihood": "",
                "operational_meaning": "",
                "mitigation_path": "",
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
                    "gain": "",
                    "lose": "",
                    "best_for": "",
                    "worst_for": "",
                })
    return routes


def _build_competitor_weakness_map(run_dir: Path) -> list[dict[str, Any]]:
    """从 VOC 证据包提取竞品弱点骨架。Agent 需填充 fatal_weakness/voc_evidence/my_counter。"""
    voc_packet = load_json(run_dir / "review_voc" / "voc_evidence_packet.json", required=False)
    if not voc_packet:
        return []
    facts = voc_packet.get("facts") or {}
    # 从差评中提取 ASIN 列表
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
                            "route": "",
                            "fatal_weakness": "",
                            "voc_evidence": ref.get("quote", ""),
                            "my_counter": "",
                            "counter_difficulty": "",
                        })
    return result


def _build_cold_start_estimate(run_dir: Path) -> dict[str, Any]:
    """从市场结构证据包提取冷启动数据骨架。Agent 需填充 review_threshold/cpc_estimate/timeline/budget_range。"""
    ms_packet = load_json(run_dir / "market_structure" / "market_structure_evidence_packet.json", required=False)
    facts = (ms_packet or {}).get("facts") or {}
    top_asins = facts.get("top_asins") or facts.get("reference_asin_pool") or []
    if isinstance(top_asins, dict):
        top_asins = list(top_asins.values())
    # 取头部评论数作为门槛参考
    review_counts = []
    for a in (top_asins if isinstance(top_asins, list) else [])[:20]:
        if isinstance(a, dict):
            rc = a.get("rating_count") or a.get("review_count") or 0
            try:
                review_counts.append(int(rc))
            except (ValueError, TypeError):
                pass
    avg_reviews = sum(review_counts) // len(review_counts) if review_counts else 0
    return {
        "review_threshold": f"头部竞品平均{avg_reviews}评" if avg_reviews else "",
        "cpc_estimate": "",
        "timeline": "",
        "budget_range": "",
        "confidence_note": "以上为数量级估算，基于类目平均数据。实际取决于产品力、Listing质量和广告效率。",
    }


def _build_validation_roadmap(evaluations: dict[str, Any]) -> list[dict[str, Any]]:
    """生成验证路线图骨架。Agent 需根据品类特征自行定义阶段数、时间线和每步的 actions/exit_criteria/if_fail。"""
    return []  # 阶段数、时间线、决策条件完全由 Agent 根据证据决定，脚本不预设模板


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
        "status": "done",
        "started_at": judgment.get("generated_at", ""),
        "output_artifacts": [
            "analysis/integrated_operator_judgment.json",
        ],
        "validation_checks": [],
        "resume_policy": {"reuse_existing_artifacts": True},
        "notes": f"final_verdict={judgment.get('final_verdict', '')}, confidence={judgment.get('confidence', '')}",
    }

    completed = progress.setdefault("completed_artifacts", [])
    artifact = "analysis/integrated_operator_judgment.json"
    if artifact not in completed:
        completed.append(artifact)

    progress["current_stage"] = P7_STAGE_ID
    progress["updated_at"] = judgment.get("generated_at", "")
    progress["next_action"] = {
        "type": "ai_step",
        "description": (
            "P7 脚本阶段完成。下一步：Report Generation Agent 增强 report_data.json → "
            "生成 HTML 报告 → 脚本回写 XLSX → QA 校验"
        ),
    }

    progress_path.write_text(
        json.dumps(progress, ensure_ascii=False, indent=2), encoding="utf-8"
    )
