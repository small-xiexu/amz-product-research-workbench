#!/usr/bin/env python3
"""Build P6 evaluations and evaluation_summary from P4/P5 evidence packets.

Responsibility split:
  - Script (this module): deterministic data extraction from upstream packets,
    rule-based scoring/rating per dimension, governance-driven summary.
  - Each evaluation is data-driven, not black-box judgment: every score, rating,
    and reason traces to a specific field in an upstream evidence packet.
  - Execution is serial_fallback — no real subagent spawn in this implementation.
  - evaluation_summary is a governance layer, not a mechanical aggregator.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from packages.research_core.contracts.p0_contracts import summarize_evaluation_constraints
from packages.research_core.contracts.validators import ContractValidationError
from packages.research_core.pipeline._utils import as_list, load_json, first_text, numeric_value


P6_SCHEMA_VERSION = "p6-evaluation-v1"
P6_STAGE_ID = "stage_8_evaluation"
EVALUATIONS_DIR = "evaluations"

P6_INPUT_ARTIFACTS = [
    "market_structure/market_structure_evidence_packet.json",
    "search_demand/search_demand_evidence_packet.json",
    "conflict_review/conflict_resolution_packet.json",
    "conflict_review/deep_data_completeness_check.json",
    "review_voc/review_voc_package.json",
    "review_voc/voc_evidence_packet.json",
    "route_matrix_confirm.json",
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

RATING_THRESHOLDS = {"strong": 70, "watch": 50, "weak": 30}


class P6EvaluationError(ContractValidationError):
    """Raised when evaluations cannot be generated."""


# ── Main entry ─────────────────────────────────────────────────────────────

def run_evaluations(run_dir: Path | str) -> dict[str, Path]:
    """Run full P6: generate all 7 evaluation files and update progress."""
    run_path = Path(run_dir).expanduser().resolve()
    _validate_inputs(run_path)

    market = load_json(run_path / "market_structure" / "market_structure_evidence_packet.json")
    search = load_json(run_path / "search_demand" / "search_demand_evidence_packet.json")
    conflict = load_json(run_path / "conflict_review" / "conflict_resolution_packet.json")
    completeness = load_json(run_path / "conflict_review" / "deep_data_completeness_check.json")
    voc_package = load_json(run_path / "review_voc" / "review_voc_package.json")
    voc_evidence = load_json(run_path / "review_voc" / "voc_evidence_packet.json")
    route_matrix = load_json(run_path / "route_matrix_confirm.json")
    progress = load_json(run_path / "progress.json")

    packets = {
        "market": market,
        "search": search,
        "conflict": conflict,
        "completeness": completeness,
        "voc_package": voc_package,
        "voc_evidence": voc_evidence,
        "route_matrix": route_matrix,
    }

    now = datetime.now(timezone.utc).isoformat()
    run_id = run_path.name

    evaluations = {
        "market_demand": _build_market_demand(packets, run_id, now),
        "competition": _build_competition(packets, run_id, now),
        "price_profit": _build_price_profit(packets, run_id, now),
        "voc_opportunity": _build_voc_opportunity(packets, run_id, now),
        "risk": _build_risk(packets, run_id, now),
        "data_quality": _build_data_quality(packets, run_id, now),
    }

    summary = _build_summary(evaluations, run_id, now)

    output_dir = run_path / EVALUATIONS_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    output_paths: dict[str, Path] = {}
    for dim, eval_packet in evaluations.items():
        path = output_dir / f"{dim}_evaluation.json"
        path.write_text(json.dumps(eval_packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        output_paths[f"{dim}_evaluation"] = path

    summary_path = output_dir / "evaluation_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    output_paths["evaluation_summary"] = summary_path

    updated_progress = _update_progress(progress, evaluations, summary, run_path)
    progress_path = run_path / "progress.json"
    progress_path.write_text(json.dumps(updated_progress, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    output_paths["progress"] = progress_path

    return output_paths


# ── Provenance helper ──────────────────────────────────────────────────────

def _provenance(dimension: str) -> dict[str, Any]:
    return {
        "executed_by_agent": False,
        "agent_role": f"{dimension} Evaluation Agent",
        "execution_mode": "serial_fallback",
        "subagent_id": "",
        "note": (
            f"脚本基于 P4/P5 上游证据包做确定性数据提取和规则评分。"
            f"评分逻辑可追溯至具体 evidence packet 字段。"
            f"未 spawn 真实 {dimension} Evaluation Agent。"
        ),
    }


# ── Scoring helpers ────────────────────────────────────────────────────────

def _score_to_rating(score: int, blockers: list[str]) -> str:
    if blockers:
        return "blocked"
    if score >= RATING_THRESHOLDS["strong"]:
        return "strong"
    if score >= RATING_THRESHOLDS["watch"]:
        return "watch"
    if score >= RATING_THRESHOLDS["weak"]:
        return "weak"
    return "blocked"


def _confidence_from_signal_count(positive: int, total: int, data_gaps: list[str]) -> str:
    if total == 0:
        return "low"
    if data_gaps and positive < total * 0.5:
        return "low"
    ratio = positive / total
    if ratio >= 0.75:
        return "high"
    if ratio >= 0.5:
        return "medium"
    return "low"


_Signal = tuple[bool, str, str]  # (hit, reason, evidence_ref)


# ── Dimension: market_demand ───────────────────────────────────────────────

def _build_market_demand(p: dict[str, Any], run_id: str, now: str) -> dict[str, Any]:
    search = p["search"]
    market = p["market"]

    signals: list[_Signal] = []
    reasons: list[str] = []
    risks: list[str] = []

    # 1. Keyword demand presence
    kw_demand = as_list(search.get("keyword_demand"))
    kw_facts = [f for f in as_list(search.get("facts")) if "keyword" in str(f.get("source", "")).lower()]
    kw_signals = kw_demand or kw_facts
    has_kw_data = bool(kw_signals)
    signals.append((has_kw_data, "搜索需求数据存在，有关键词搜索量数据", "search_demand/search_demand_evidence_packet.json#keyword_demand"))
    if not has_kw_data:
        risks.append("缺少关键词搜索量数据，需求规模判断依赖间接信号")

    # 2. Multiple significant keywords
    significant_kws = 0
    for kw in kw_signals:
        vol = numeric_value(kw.get("monthly_search_volume") or kw.get("value"))
        if vol and vol >= 500:
            significant_kws += 1
    has_multi_kw = significant_kws >= 3
    signals.append((has_multi_kw, f"{significant_kws} 个关键词月搜索量 >= 500", "search_demand/search_demand_evidence_packet.json#keyword_demand"))

    # 3. Category market data
    market_size = market.get("market_size") or {}
    primary = market_size.get("primary_market") or {}
    overview = primary.get("overview_all") or {}
    has_market_data = bool(overview.get("样本商品数") or primary.get("sample_count"))
    signals.append((has_market_data, "市场结构数据存在，包含类目 Top100 样本", "market_structure/market_structure_evidence_packet.json#market_size"))

    # 4. Demand signal strength
    derived_list = as_list(search.get("derived_metrics"))
    first_derived = derived_list[0] if derived_list else {}
    demand_level = first_text(
        (search.get("trend_signal") or {}).get("trend_direction"),
        first_derived.get("value") if isinstance(first_derived, dict) else "",
    )
    has_strong_signal = demand_level in ("strong", "moderate", "up", "stable", "rising")
    signals.append((has_strong_signal, f"需求趋势信号: {demand_level or '未明确'}", "search_demand/search_demand_evidence_packet.json#trend_signal"))

    # 5. Category trend
    trend = search.get("trend_signal") or {}
    has_positive_trend = trend.get("trend_direction") in ("up", "stable", "rising")
    signals.append((has_positive_trend, f"类目趋势方向: {trend.get('trend_direction', '未明确')}", "search_demand/search_demand_evidence_packet.json#trend_signal"))

    score = _compute_score(signals)
    data_gaps_list = [str(g.get("gap", g)) for g in as_list(search.get("data_gaps")) + as_list(market.get("data_gaps"))[:8] if g]
    conf = _confidence_from_signal_count(sum(1 for s in signals if s[0]), len(signals), data_gaps_list)
    blockers = _collect_blockers(search, market, "market_demand")

    return {
        "schema_version": P6_SCHEMA_VERSION,
        "packet_id": "market_demand_evaluation",
        "stage": "evaluation",
        "score": score,
        "rating": _score_to_rating(score, blockers),
        "confidence": conf,
        "key_reasons": [s[1] for s in signals if s[0]] or ["市场需求信号不足，无法形成判断"],
        "risks": risks,
        "required_followups": _demand_followups(signals, data_gaps_list),
        "evidence_refs": [s[2] for s in signals],
        "execution_provenance": _provenance("Market Demand"),
    }


def _demand_followups(signals: list[_Signal], gaps: list[str]) -> list[str]:
    fu: list[str] = []
    if not signals[0][0]:
        fu.append("补关键词搜索量数据（keyword_miner / keyword_research）")
    if not signals[2][0]:
        fu.append("补类目 Top100 市场数据（market_research）")
    if not signals[3][0]:
        fu.append("确认需求趋势方向，避免在下降赛道投入")
    for g in gaps[:3]:
        fu.append(f"数据缺口: {g}")
    return fu if fu else ["当前市场需求信号充分，无需补充验证"]


# ── Dimension: competition ─────────────────────────────────────────────────

def _build_competition(p: dict[str, Any], run_id: str, now: str) -> dict[str, Any]:
    market = p["market"]
    conflict = p["conflict"]

    signals: list[_Signal] = []
    risks: list[str] = []

    # 1. Product concentration
    conc_data = market.get("product_concentration") or market.get("market_concentration") or {}
    top3_share = numeric_value(
        conc_data.get("top3_share")
        or conc_data.get("top3_product_sales_volume_share")
        or _find_metric_value(market, "concentration")
    )
    low_concentration = top3_share is None or top3_share <= 0.5
    share_text = f"{top3_share:.0%}" if top3_share is not None else "未知"
    signals.append((low_concentration, f"Top3 商品销量集中度: {share_text}（≤50% 为健康）", "market_structure/market_structure_evidence_packet.json#product_concentration"))
    if not low_concentration and top3_share is not None:
        risks.append(f"头部商品集中度偏高（Top3={share_text}），新品进入难度大")

    # 2. Brand concentration
    brand_conc = market.get("brand_concentration") or {}
    top3_brand = numeric_value(brand_conc.get("top3_share") or brand_conc.get("top3_brand_share"))
    low_brand_conc = top3_brand is None or top3_brand <= 0.5
    brand_text = f"{top3_brand:.0%}" if top3_brand is not None else "未知"
    signals.append((low_brand_conc, f"Top3 品牌集中度: {brand_text}（≤50% 为健康）", "market_structure/market_structure_evidence_packet.json#brand_concentration"))
    if not low_brand_conc and top3_brand is not None:
        risks.append(f"品牌集中度偏高（Top3={brand_text}），需差异化或强品牌策略")

    # 3. Review barrier
    review_metric = _find_metric_value(market, "review_threshold")
    review_barrier_low = review_metric is None or review_metric >= 0.05
    signals.append((review_barrier_low, "评论门槛可接受（存在低评论有量样本）", "market_structure/market_structure_evidence_packet.json#derived_metrics"))
    if not review_barrier_low:
        risks.append("评论门槛过高，新品冷启动难度大")

    # 4. New product signals
    new_signal = market.get("new_product_signal") or {}
    has_new_opportunity = bool(new_signal) and new_signal.get("new_release_opportunity_level", "") != "weak"
    signals.append((has_new_opportunity, "存在新品进入机会", "market_structure/market_structure_evidence_packet.json#new_product_signal"))

    # 5. Mixed pool risk
    mixed_level = _find_mixed_pool(market)
    no_blocking_mix = mixed_level not in ("blocking",)
    signals.append((no_blocking_mix, f"混池风险水平: {mixed_level}", "market_structure/market_structure_evidence_packet.json"))
    if mixed_level == "blocking":
        risks.append("混池风险为 blocking 级，关键词/类目覆盖严重混池")

    score = _compute_score(signals)
    data_gaps_list = [str(g.get("gap", g)) for g in as_list(market.get("data_gaps"))[:8] if g]
    conf = _confidence_from_signal_count(sum(1 for s in signals if s[0]), len(signals), data_gaps_list)
    blockers = _collect_blockers_search(market, conflict, "competition")

    return {
        "schema_version": P6_SCHEMA_VERSION,
        "packet_id": "competition_evaluation",
        "stage": "evaluation",
        "score": score,
        "rating": _score_to_rating(score, blockers),
        "confidence": conf,
        "key_reasons": [s[1] for s in signals if s[0]] or ["竞争信号不足，无法形成判断"],
        "risks": risks,
        "required_followups": _competition_followups(signals, data_gaps_list),
        "evidence_refs": [s[2] for s in signals],
        "execution_provenance": _provenance("Competition"),
    }


def _competition_followups(signals: list[_Signal], gaps: list[str]) -> list[str]:
    fu: list[str] = []
    if not signals[0][0]:
        fu.append("补商品集中度数据（market_research）")
    if not signals[1][0]:
        fu.append("补品牌集中度数据")
    if not signals[2][0]:
        fu.append("确认低评论新品是否有可见度")
    for g in gaps[:3]:
        fu.append(f"数据缺口: {g}")
    return fu if fu else ["竞争结构清晰，无需补充验证"]


# ── Dimension: price_profit ────────────────────────────────────────────────

def _build_price_profit(p: dict[str, Any], run_id: str, now: str) -> dict[str, Any]:
    market = p["market"]

    signals: list[_Signal] = []
    risks: list[str] = []

    # 1. Price band data exists
    price_band = market.get("price_band") or {}
    grouped = price_band.get("primary_market_distribution_grouped") or {}
    has_price_data = bool(grouped)
    signals.append((has_price_data, "价格带分布数据存在", "market_structure/market_structure_evidence_packet.json#price_band"))
    if not has_price_data:
        risks.append("缺少价格带分布数据，无法评估利润想象空间")

    # 2. Strong price bands exist
    strong_bands = sum(1 for v in grouped.values() if isinstance(v, dict) and v.get("opportunity_level") == "strong")
    has_opportunity_bands = strong_bands >= 1
    signals.append((has_opportunity_bands, f"存在 {strong_bands} 个强机会价格带", "market_structure/market_structure_evidence_packet.json#price_band"))

    # 3. Price range width
    avg_price = numeric_value(
        ((market.get("market_size") or {}).get("primary_market") or {}).get("overview_all", {}).get("平均价格($)")
    )
    has_price_data_detail = avg_price is not None
    signals.append((has_price_data_detail, f"均价约 ${avg_price:.0f}" if avg_price else "均价数据可用", "market_structure/market_structure_evidence_packet.json#market_size"))

    # 4. No extreme compression
    price_range = 0
    band_keys = list(grouped.keys())
    if len(band_keys) >= 3:
        price_range = len(band_keys)
    no_compression = price_range >= 2 or not has_price_data
    signals.append((no_compression, f"价格带分布 {price_range} 段，有分层空间" if price_range else "价格带分布未压缩", "market_structure/market_structure_evidence_packet.json#price_band"))
    if not no_compression and has_price_data:
        risks.append("价格带极窄，差异化空间有限")

    score = _compute_score(signals)
    data_gaps_list = [str(g.get("gap", g)) for g in as_list(market.get("data_gaps"))[:8] if g]

    # Cap confidence at medium: no real cost data
    raw_conf = _confidence_from_signal_count(sum(1 for s in signals if s[0]), len(signals), data_gaps_list)
    conf = "medium" if raw_conf == "high" else raw_conf

    return {
        "schema_version": P6_SCHEMA_VERSION,
        "packet_id": "price_profit_evaluation",
        "stage": "evaluation",
        "score": score,
        "rating": _score_to_rating(score, []),
        "confidence": conf,
        "key_reasons": [s[1] for s in signals if s[0]] or [
            "价格利润数据不足，未做真实毛利计算（无成本输入）",
        ],
        "risks": risks + ["未做真实毛利计算：没有供应商报价、FBA 费、关税等成本输入"],
        "required_followups": _price_followups(signals, data_gaps_list),
        "evidence_refs": [s[2] for s in signals],
        "execution_provenance": _provenance("Price Profit"),
    }


def _price_followups(signals: list[_Signal], gaps: list[str]) -> list[str]:
    fu: list[str] = []
    if not signals[0][0]:
        fu.append("补价格带分布数据")
    fu.append("需供应商报价后才能做真实毛利测算（FBA 费、头程、关税、佣金）")
    for g in gaps[:2]:
        fu.append(f"数据缺口: {g}")
    return fu


# ── Dimension: voc_opportunity ─────────────────────────────────────────────

def _build_voc_opportunity(p: dict[str, Any], run_id: str, now: str) -> dict[str, Any]:
    voc_pkg = p["voc_package"]
    voc_ev = p["voc_evidence"]

    signals: list[_Signal] = []
    risks: list[str] = []

    # 1. Review coverage
    review_count = (voc_ev.get("review_scope") or {}).get("review_count") or voc_pkg.get("stats", {}).get("review_count", 0)
    has_reviews = isinstance(review_count, (int, float)) and review_count >= 30
    signals.append((has_reviews, f"评论样本 {review_count} 条（≥30 为充足）", "review_voc/voc_evidence_packet.json#review_scope"))
    if not has_reviews:
        risks.append(f"评论样本不足（{review_count} 条），VOC 分析置信度低")

    # 2. ASIN coverage
    asin_count = (voc_ev.get("review_scope") or {}).get("asin_count") or voc_pkg.get("stats", {}).get("asin_count", 0)
    has_asins = isinstance(asin_count, (int, float)) and asin_count >= 3
    signals.append((has_asins, f"覆盖 {asin_count} 个 ASIN（≥3 为充足）", "review_voc/voc_evidence_packet.json#review_scope"))

    # 3. Pain points identified
    pain_points = as_list(voc_ev.get("pain_points_by_dimension"))
    has_pain_points = len(pain_points) > 0
    signals.append((has_pain_points, f"识别到 {len(pain_points)} 个痛点维度", "review_voc/voc_evidence_packet.json#pain_points_by_dimension"))
    if not has_pain_points:
        risks.append("VOC 证据包中 pain_points_by_dimension 为空，痛点归因待 VOC Evidence Agent 补齐")

    # 4. Pain points have evidence refs
    pp_with_refs = sum(1 for pp in pain_points if isinstance(pp, dict) and pp.get("evidence_refs"))
    has_evidence = pp_with_refs > 0 if pain_points else False
    signals.append((has_evidence or not pain_points, f"{pp_with_refs}/{len(pain_points)} 个痛点有证据溯源" if pain_points else "无痛点维度（VOC Agent 未填充）", "review_voc/voc_evidence_packet.json#pain_points_by_dimension"))

    score = _compute_score(signals)
    data_gaps_list = [str(g.get("gap", g)) for g in as_list(voc_ev.get("data_gaps"))[:8] if g]
    conf = _confidence_from_signal_count(sum(1 for s in signals if s[0]), len(signals), data_gaps_list)
    # VOC confidence is capped by review count
    if isinstance(review_count, (int, float)) and review_count < 30:
        conf = "low"

    return {
        "schema_version": P6_SCHEMA_VERSION,
        "packet_id": "voc_opportunity_evaluation",
        "stage": "evaluation",
        "score": score,
        "rating": _score_to_rating(score, []),
        "confidence": conf,
        "key_reasons": [s[1] for s in signals if s[0]] or ["VOC 痛点分析尚未完成，需 VOC Evidence Agent 先填充 pain_points_by_dimension"],
        "risks": risks,
        "required_followups": _voc_followups(signals, pain_points, data_gaps_list),
        "evidence_refs": [s[2] for s in signals],
        "execution_provenance": _provenance("VOC Opportunity"),
    }


def _voc_followups(signals: list[_Signal], pain_points: list[dict], gaps: list[str]) -> list[str]:
    fu: list[str] = []
    if not signals[0][0]:
        fu.append("补评论样本（目标 ≥30 条评论，覆盖 ≥3 个 ASIN）")
    if not signals[2][0]:
        fu.append("需 VOC Evidence Agent 基于 review_voc_package.json 的 normalized_reviews 生成 pain_points_by_dimension")
    for g in gaps[:3]:
        fu.append(f"数据缺口: {g}")
    return fu if fu else ["VOC 机会信号充足，可进入规格映射和样品验证"]


# ── Dimension: risk ────────────────────────────────────────────────────────

def _build_risk(p: dict[str, Any], run_id: str, now: str) -> dict[str, Any]:
    market = p["market"]
    conflict = p["conflict"]
    search = p["search"]
    completeness = p["completeness"]

    signals: list[_Signal] = []
    risks: list[str] = []

    # 1. No blocking conflicts
    blocking = as_list(conflict.get("blocking_conflicts"))
    no_blocking = not any(
        isinstance(c, dict) and c.get("status") not in ("resolved", "accepted", "waived")
        for c in blocking
    )
    signals.append((no_blocking, "无未解决的 blocking 级冲突", "conflict_review/conflict_resolution_packet.json#blocking_conflicts"))
    if not no_blocking:
        risks.append("存在未解决的 blocking 级冲突，需运营或补数确认")

    # 2. No compliance/blocking category risks
    risks_section = market.get("risks") or search.get("risks") or {}
    compliance_risk = risks_section.get("compliance") or risks_section.get("ip_risk", "")
    no_compliance = not compliance_risk or str(compliance_risk).lower() in ("none", "low", "无", "低")
    signals.append((no_compliance, "未发现合规/知产阻断风险", "market_structure/market_structure_evidence_packet.json"))
    if not no_compliance:
        risks.append(f"合规/知产风险: {compliance_risk}")

    # 3. Return rate acceptable
    overview = ((market.get("market_size") or {}).get("primary_market") or {}).get("overview_all") or {}
    return_rate = numeric_value(overview.get("同类目退货率", overview.get("退货率")))
    return_ok = return_rate is None or return_rate <= 0.15
    signals.append((return_ok, f"类目退货率: {return_rate:.0%}" if return_rate is not None else "退货率数据未获取", "market_structure/market_structure_evidence_packet.json#market_size"))
    if not return_ok and return_rate is not None:
        risks.append(f"类目退货率偏高（{return_rate:.0%}），影响利润模型")

    # 4. Seasonality not extreme
    trend = search.get("trend_signal") or {}
    seasonality = trend.get("seasonality_level", "")
    no_extreme_season = seasonality not in ("high", "extreme", "强季节", "极端")
    signals.append((no_extreme_season, f"季节性水平: {seasonality or '未明确'}", "search_demand/search_demand_evidence_packet.json#trend_signal"))
    if not no_extreme_season:
        risks.append(f"强季节性（{seasonality}），备货和验证窗口受限")

    # 5. No completeness blocker
    completeness_blocker = completeness.get("p4_blocker") or completeness.get("blocker")
    no_comp_blocker = not completeness_blocker
    signals.append((no_comp_blocker, "无 P4 数据完整性阻断", "conflict_review/deep_data_completeness_check.json"))
    if not no_comp_blocker:
        risks.append("P4 数据完整性存在阻断项")

    score = _compute_score(signals)
    data_gaps_list = [str(g.get("gap", g)) for g in as_list(market.get("data_gaps"))[:8] if g]
    conf = _confidence_from_signal_count(sum(1 for s in signals if s[0]), len(signals), data_gaps_list)

    return {
        "schema_version": P6_SCHEMA_VERSION,
        "packet_id": "risk_evaluation",
        "stage": "evaluation",
        "score": score,
        "rating": _score_to_rating(score, []),
        "confidence": conf,
        "key_reasons": [s[1] for s in signals if s[0]] or ["风险评估信号不足，需补全冲突、退货率和季节性数据"],
        "risks": risks,
        "required_followups": _risk_followups(signals, data_gaps_list),
        "evidence_refs": [s[2] for s in signals],
        "execution_provenance": _provenance("Risk"),
    }


def _risk_followups(signals: list[_Signal], gaps: list[str]) -> list[str]:
    fu: list[str] = []
    if not signals[0][0]:
        fu.append("先解决 blocking 级冲突才能输出 risk evaluation")
    if not signals[2][0]:
        fu.append("补退货率数据，做 FBA 费 + 退货成本测算")
    if not signals[3][0]:
        fu.append("确认季节性峰值和低谷，规划备货窗口")
    for g in gaps[:2]:
        fu.append(f"数据缺口: {g}")
    return fu if fu else ["当前风险信号在可接受范围内"]


# ── Dimension: data_quality ────────────────────────────────────────────────

def _build_data_quality(p: dict[str, Any], run_id: str, now: str) -> dict[str, Any]:
    completeness = p["completeness"]
    conflict = p["conflict"]
    route_matrix = p["route_matrix"]
    market = p["market"]
    search = p["search"]

    signals: list[_Signal] = []
    risks: list[str] = []
    blockers: list[str] = []

    # 1. Route coverage
    routes = as_list(route_matrix.get("route_matrix"))
    has_routes = len(routes) > 0
    signals.append((has_routes, f"路线矩阵覆盖 {len(routes)} 条路线", "route_matrix_confirm.json#route_matrix"))
    if not has_routes:
        risks.append("路线矩阵为空，无法覆盖目标市场")

    # 2. No blocking conflicts
    blocking = as_list(conflict.get("blocking_conflicts"))
    unresolved_blocking = [
        c for c in blocking
        if isinstance(c, dict) and c.get("status") not in ("resolved", "accepted", "waived")
    ]
    no_conflict_blocker = len(unresolved_blocking) == 0
    signals.append((no_conflict_blocker, "无未解决的 blocking 冲突", "conflict_review/conflict_resolution_packet.json#blocking_conflicts"))
    if not no_conflict_blocker:
        blockers.append("blocking_conflict_unresolved")
        risks.append(f"存在 {len(unresolved_blocking)} 个未解决的 blocking 冲突")

    # 3. Basis mismatch check
    basis_mismatches = as_list(conflict.get("basis_mismatches"))
    no_basis_issue = len(basis_mismatches) == 0
    signals.append((no_basis_issue, "无 metric_basis 不匹配问题", "conflict_review/conflict_resolution_packet.json"))
    if not no_basis_issue:
        risks.append(f"存在 {len(basis_mismatches)} 个 basis_mismatch，部分指标不可直接比较")

    # 4. Sample adequacy (from market + search)
    market_gaps = as_list(market.get("data_gaps"))
    search_gaps = as_list(search.get("data_gaps"))
    critical_gap_count = sum(
        1 for g in market_gaps + search_gaps
        if isinstance(g, dict) and any(
            w in str(g.get("gap", g)).lower()
            for w in ("缺失", "不足", "未接入", "blocking", "不收敛")
        )
    )
    sample_ok = critical_gap_count < 2
    signals.append((sample_ok, f"关键数据缺口: {critical_gap_count} 个（<2 为充足）", "market_structure/search_demand evidence packets#data_gaps"))

    # 5. Completeness check
    comp_blocker = completeness.get("p4_blocker") or completeness.get("blocker")
    if comp_blocker:
        blockers.append("p4_completeness_blocker")
        risks.append(f"P4 数据完整性阻断: {comp_blocker}")

    score = _compute_score(signals)
    data_gaps_list = [str(g.get("gap", g)) for g in market_gaps + search_gaps[:8] if g]
    conf = _confidence_from_signal_count(sum(1 for s in signals if s[0]), len(signals), data_gaps_list)

    return {
        "schema_version": P6_SCHEMA_VERSION,
        "packet_id": "data_quality_evaluation",
        "stage": "evaluation",
        "score": score,
        "rating": _score_to_rating(score, blockers),
        "confidence": conf,
        "key_reasons": [s[1] for s in signals if s[0]] or ["数据质量信号不足"],
        "risks": risks,
        "required_followups": _dq_followups(signals, data_gaps_list),
        "evidence_refs": [s[2] for s in signals],
        "execution_provenance": _provenance("Data Quality"),
    }


def _dq_followups(signals: list[_Signal], gaps: list[str]) -> list[str]:
    fu: list[str] = []
    if not signals[0][0]:
        fu.append("补路线矩阵覆盖")
    if not signals[1][0]:
        fu.append("解决 blocking 级冲突后再评估")
    if not signals[3][0]:
        fu.append("补关键数据缺口（市场结构/搜索需求）")
    for g in gaps[:2]:
        fu.append(f"数据缺口: {g}")
    return fu if fu else ["数据质量良好，可支撑正式判断"]


# ── evaluation_summary ─────────────────────────────────────────────────────

def _build_summary(evaluations: dict[str, dict[str, Any]], run_id: str, now: str) -> dict[str, Any]:
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

    return {
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


# ── Helpers ────────────────────────────────────────────────────────────────

def _compute_score(signals: list[_Signal]) -> int:
    if not signals:
        return 0
    hit = sum(1 for s in signals if s[0])
    return round(hit / len(signals) * 100)


def _find_metric_value(packet: dict[str, Any], keyword: str) -> float | None:
    for metric in as_list(packet.get("derived_metrics")):
        if isinstance(metric, dict) and keyword.lower() in str(metric.get("id", "")).lower():
            val = metric.get("value") or metric.get("values")
            if isinstance(val, dict):
                val = val.get("unit_share") or val.get("share") or val.get("value")
            return numeric_value(val)
    return None


def _find_mixed_pool(packet: dict[str, Any]) -> str:
    facts = as_list(packet.get("facts"))
    for fact in facts:
        if isinstance(fact, dict) and "mixed" in str(fact.get("subject", "")).lower():
            level = str(fact.get("value") or "").lower()
            if level in ("none", "mild", "material", "blocking"):
                return level
    # Check derived metrics
    for metric in as_list(packet.get("derived_metrics")):
        if isinstance(metric, dict) and "mixed" in str(metric.get("id", "")).lower():
            val = str(metric.get("value") or "").lower()
            if val in ("none", "mild", "material", "blocking"):
                return val
    return "unknown"


def _collect_blockers(search: dict[str, Any], market: dict[str, Any], dim: str) -> list[str]:
    blockers: list[str] = []
    # Check for explicitly weak signals from derived_metrics
    for metric in as_list(search.get("derived_metrics")) + as_list(market.get("derived_metrics")):
        if isinstance(metric, dict):
            val = str(metric.get("value") or "").lower()
            if val in ("negative", "blocking"):
                blockers.append(f"blocking_signal:{metric.get('id', 'unknown')}")
    return blockers


def _collect_blockers_search(market: dict[str, Any], conflict: dict[str, Any], dim: str) -> list[str]:
    blockers: list[str] = []
    # Check conflict blockers
    for c in as_list(conflict.get("blocking_conflicts")):
        if isinstance(c, dict) and c.get("status") not in ("resolved", "accepted", "waived"):
            blockers.append(f"blocking_conflict:{c.get('conflict_id', 'unknown')}")
    # Check for mixed pool blocking
    mixed = _find_mixed_pool(market)
    if mixed == "blocking":
        blockers.append("mixed_pool_blocking")
    return blockers


def _validate_inputs(run_path: Path) -> None:
    missing = []
    for artifact in P6_INPUT_ARTIFACTS:
        if not (run_path / artifact).exists():
            missing.append(artifact)
    # progress.json and workflow_state.json are optional for P6
    non_blocking = {"progress.json"}
    blocking_missing = [m for m in missing if m not in non_blocking]
    if blocking_missing:
        raise P6EvaluationError(
            f"Missing required input artifacts: {', '.join(blocking_missing)}"
        )


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
