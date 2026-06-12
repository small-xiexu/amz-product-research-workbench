#!/usr/bin/env python3
"""Build a minimal research package from one candidate in a candidate pool."""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any
import argparse


PREFERRED_STATUSES = ("继续看", "试做", "观察", "先放弃")


def build_research_package(
    candidate_pool: dict[str, Any],
    candidate_id: str | None,
    voc_package: dict[str, Any] | None = None,
) -> dict[str, Any]:
    candidate = _select_candidate(candidate_pool.get("candidates", []), candidate_id)
    metadata = candidate_pool.get("metadata", {})
    source_brief = candidate_pool.get("source_brief", {})
    competition = candidate.get("competition_structure", {})
    profit_space = candidate.get("preliminary_profit_space", {})
    competitor_candidates = candidate.get("competitor_candidates", {})
    market_structure = candidate.get("market_structure", {})
    status = candidate.get("status", "观察")
    voc_analysis = _build_voc_analysis(voc_package)
    voc_review_sources = _build_review_sources(voc_package)
    voc_opportunities = _build_voc_opportunities(voc_package, candidate.get("candidate_id"))
    voc_summary_line = _voc_summary_line(voc_package)
    entry_barriers = _build_entry_barriers(candidate)
    go_nogo_scorecard = _build_go_nogo_scorecard(candidate, entry_barriers, voc_package)
    decision_review = _build_decision_review(candidate, voc_package, go_nogo_scorecard)

    package = {
        "metadata": {
            "site": metadata.get("site", source_brief.get("site", "US")),
            "seed_keyword_or_category": candidate.get("name", "未命名候选方向"),
            "product_shape": f"{candidate.get('candidate_type', 'candidate')}：{candidate.get('reason', '')}",
            "generated_at": metadata.get("generated_at", ""),
            "data_sources": metadata.get("data_sources", []) + candidate.get("source_refs", []),
            "candidate_id": candidate.get("candidate_id"),
            "candidate_pool_id": metadata.get("pool_id"),
        },
        "constraints": {
            "exclusion_rules": source_brief.get("exclusion_rules", []),
            "preference_rules": source_brief.get("preference_rules", {}),
        },
        "operator_inputs": {
            "target_price_range": profit_space.get("price_band", "待补"),
            "purchase_cost": "待补",
            "exchange_rate": "待补",
            "fba_fee": "待补",
            "storage_fee": "按建议售价 3% 待算",
            "inbound_placement_fee": "待补",
            "ad_rate_assumption": 0.2,
            "return_rate_assumption": "待补",
        },
        "product_flags": candidate.get("risk_flags", []),
        "raw_sources": {
            "candidate_pool": {
                "pool_id": metadata.get("pool_id"),
                "candidate_id": candidate.get("candidate_id"),
                "source_refs": candidate.get("source_refs", []),
            },
            "review_voc_package": voc_review_sources,
        },
        "normalized_tables": {
            "candidate": candidate,
            "top100": candidate.get("top_products", []),
            "top_product_tags": market_structure.get("tagged_products", []),
            "voc_evidence": _collect_voc_evidence(voc_package),
        },
        "market_structure": market_structure,
        "market_analysis": {
            "market_size": _market_size_text(candidate),
            "price_band": _price_band_text(candidate),
            "brand_concentration": _brand_concentration_text(candidate),
            "seller_concentration": _seller_concentration_text(candidate),
            "new_listing_ratio": _new_listing_text(candidate),
            "return_rate": _return_rate_text(candidate),
        },
        "keyword_analysis": {
            "search_signal": candidate.get("demand_evidence", {}).get("search_signal", "待填"),
            "trend_signal": candidate.get("demand_evidence", {}).get("trend_signal", "待填"),
        },
        "competitor_pool": {
            "top10": _competitor_items(competitor_candidates.get("top10", [])),
            "recent_winners": _competitor_items(competitor_candidates.get("recent_winners", [])),
            "structure_supplement": _competitor_items(competitor_candidates.get("structure_supplement", [])),
        },
        "competitor_selection_logic": _build_competitor_selection_logic(candidate),
        "profit_reference": {
            "base_fba_gross_profit": "待补",
            "base_fba_margin": "待补",
            "post_ads_returns_gross_profit": "待补",
            "post_ads_returns_margin": "待补",
            "preliminary_profit_space": profit_space,
        },
        "return_risk": candidate.get("return_risk", {}),
        "ip_screening": candidate.get("ip_compliance_risk", {}),
        "compliance_screening": candidate.get("ip_compliance_risk", {}),
        "review_sources": voc_review_sources,
        "voc_analysis": voc_analysis,
        "opportunity_hypotheses": [
            {
                "candidate_id": candidate.get("candidate_id"),
                "hypothesis": candidate.get("reason", ""),
                "evidence": candidate.get("appearance_reason", []),
                "missing_data": candidate.get("missing_data", []),
            }
        ] + voc_opportunities,
        "status_card": {
            "status": status,
            "reason": _append_sentence(candidate.get("reason", "待补"), voc_summary_line),
            "next_step": _status_next_step(decision_review, candidate),
        },
        "decision_review": decision_review,
        "validation_actions": {},
        "entry_barriers": entry_barriers,
        "competitor_deep_dive": _build_competitor_deep_dive(competitor_candidates),
        "report_summary": {
            "bullets": [
                candidate.get("reason", "待补"),
                f"当前状态：{status}",
                "正式结论需要补齐利润、知产/合规和供应链复核。",
            ] + ([voc_summary_line] if voc_summary_line else [])
        },
        "dashboard_views": {
            "cards": [
                {
                    "title": candidate.get("name", "候选方向"),
                    "status": status,
                    "missing_data": candidate.get("missing_data", []),
                },
                _voc_dashboard_card(voc_package),
            ]
        },
        "workspace_views": {
            "candidate_card": candidate
        },
        "excel_sheets": {
            "data_source": "data.xlsx"
        },
    }
    if not voc_package:
        package["dashboard_views"]["cards"] = [card for card in package["dashboard_views"]["cards"] if card]
    return package


def _build_entry_barriers(candidate: dict[str, Any]) -> list[dict[str, Any]]:
    competition = candidate.get("competition_structure", {})
    return_risk = candidate.get("return_risk", {})
    ip_risk = candidate.get("ip_compliance_risk", {})
    new_listing = candidate.get("new_listing_opportunity", {})

    top10_avg_review = None
    top10 = candidate.get("competitor_candidates", {}).get("top10", [])
    if top10:
        review_counts = [item.get("rating_count") for item in top10 if isinstance(item.get("rating_count"), (int, float))]
        if review_counts:
            top10_avg_review = sum(review_counts) / len(review_counts)

    top_brand_share = competition.get("top_brand_units_share")
    if isinstance(top_brand_share, float) and top_brand_share <= 1:
        brand_share_pct = top_brand_share * 100
    elif isinstance(top_brand_share, (int, float)):
        brand_share_pct = float(top_brand_share)
    else:
        brand_share_pct = None

    ip_level = str(ip_risk.get("level", "待确认"))
    return_level = str(return_risk.get("level", "待确认"))

    def review_barrier_level(avg: float | None) -> str:
        if avg is None:
            return "待确认"
        return "高" if avg > 2000 else ("中" if avg >= 500 else "低")

    def brand_barrier_level(share_pct: float | None) -> str:
        if share_pct is None:
            return "待确认"
        return "高" if share_pct > 40 else ("中" if share_pct >= 20 else "低")

    barriers = [
        {
            "type": "Review门槛",
            "level": review_barrier_level(top10_avg_review),
            "data_basis": f"Top10平均评分数 {round(top10_avg_review) if top10_avg_review else '待补'}",
            "rule": ">2000=高，500-2000=中，<500=低",
        },
        {
            "type": "资金壁垒",
            "level": "待补",
            "data_basis": "首批备货 + FBA + 头程估算待运营填写利润模板后计算",
            "rule": "依赖运营填写利润复核模板",
        },
        {
            "type": "技术壁垒",
            "level": "待确认" if "待确认" in ip_level else ("高" if "高" in ip_level else "低"),
            "data_basis": f"知产/合规初筛状态：{ip_level}",
            "rule": "有认证要求=高，无=低",
        },
        {
            "type": "合规壁垒",
            "level": "待确认" if "待确认" in ip_level else ("高" if "高" in ip_level else "低"),
            "data_basis": f"知产/合规初筛状态：{ip_level}。强认证（UL/FCC/CE等）判为高。",
            "rule": "有强认证=高，无=低",
        },
        {
            "type": "供应链壁垒",
            "level": "中" if return_level in ("中", "高") else "低",
            "data_basis": f"退货风险等级：{return_level}",
            "rule": "定制件/强季节/高退货=高，通用白牌=低",
        },
        {
            "type": "品牌壁垒",
            "level": brand_barrier_level(brand_share_pct),
            "data_basis": f"头部品牌销量占比 {f'{brand_share_pct:.1f}%' if brand_share_pct is not None else '待补'}",
            "rule": ">40%=高，20-40%=中，<20%=低",
        },
    ]
    return barriers


def _build_go_nogo_scorecard(
    candidate: dict[str, Any],
    entry_barriers: list[dict[str, Any]],
    voc_package: dict[str, Any] | None,
) -> dict[str, Any]:
    demand = candidate.get("demand_evidence", {})
    competition = candidate.get("competition_structure", {})
    profit = candidate.get("preliminary_profit_space", {})
    new_listing = candidate.get("new_listing_opportunity", {})

    def score_market_size() -> tuple[float, str]:
        avg_units = demand.get("market_avg_monthly_units")
        avg_rev = demand.get("market_avg_monthly_revenue_usd")
        if avg_units is None and avg_rev is None:
            return 5.0, "数据待补，默认中等"
        score = 5.0
        note_parts = []
        if avg_units is not None:
            if avg_units >= 500:
                score = 8.0
                note_parts.append(f"月均销量 {avg_units:,.0f}（体量充足）")
            elif avg_units >= 200:
                score = 6.0
                note_parts.append(f"月均销量 {avg_units:,.0f}（体量一般）")
            else:
                score = 3.0
                note_parts.append(f"月均销量 {avg_units:,.0f}（体量偏小）")
        if avg_rev is not None:
            if avg_rev >= 10000:
                score = max(score, 8.0)
                note_parts.append(f"月均销售额 USD {avg_rev:,.0f}（规模可观）")
            elif avg_rev >= 5000:
                score = max(score, 6.0)
        return score, "；".join(note_parts) or "待补"

    def score_competition() -> tuple[float, str]:
        top10_share = competition.get("top10_product_units_share")
        brand_share = competition.get("top_brand_units_share")
        # Sorftime keyword_competitor_count supplements SellerSprite concentration data
        kw_competitor_count = competition.get("keyword_competitor_count")
        # Sorftime category_trend concentration signal
        sf_ct = demand.get("sorftime_category_trend", {})
        conc_trend = sf_ct.get("top3_concentration_trend", "")

        score = 5.0
        note_parts = []
        if top10_share is not None:
            share_pct = top10_share * 100 if top10_share <= 1 else top10_share
            if share_pct < 50:
                score = 8.0
                note_parts.append(f"Top10占比 {share_pct:.1f}%（竞争分散，可进入）")
            elif share_pct < 70:
                score = 5.5
                note_parts.append(f"Top10占比 {share_pct:.1f}%（竞争中等集中）")
            else:
                score = 3.0
                note_parts.append(f"Top10占比 {share_pct:.1f}%（竞争高度集中）")
        if brand_share is not None:
            b_pct = brand_share * 100 if brand_share <= 1 else brand_share
            if b_pct > 40:
                score = min(score, 3.5)
                note_parts.append(f"头部品牌占比 {b_pct:.1f}%（品牌壁垒高）")
        if kw_competitor_count is not None:
            if kw_competitor_count > 50000:
                score = min(score, 4.0)
                note_parts.append(f"Sorftime 搜索竞品数 {kw_competitor_count:,}（竞争激烈）")
            elif kw_competitor_count > 20000:
                note_parts.append(f"Sorftime 搜索竞品数 {kw_competitor_count:,}（竞争中等）")
            else:
                score = min(score + 0.5, 10.0)
                note_parts.append(f"Sorftime 搜索竞品数 {kw_competitor_count:,}（竞争相对可控）")
        if "恶化" in conc_trend:
            score = min(score, 4.0)
            note_parts.append(f"Sorftime：集中度趋势恶化")
        elif "分散" in conc_trend:
            score = min(score + 0.5, 10.0)
            note_parts.append(f"Sorftime：集中度趋势分散")
        return score, "；".join(note_parts) or "待补"

    def score_demand_clarity() -> tuple[float, str]:
        search_signal = demand.get("search_signal", "")
        trend_signal = demand.get("trend_signal", "")
        has_aba = bool(demand.get("aba_top_search_term"))
        has_keyword = bool(demand.get("top_keyword"))
        # Sorftime keyword verification supplements SellerSprite signals
        sf_kw_list = demand.get("sorftime_keyword_verification", [])
        sf_top_kw = sf_kw_list[0] if sf_kw_list else {}
        has_sf_search = bool(sf_top_kw.get("monthly_search_volume"))
        sf_trend = sf_top_kw.get("trend_direction", "")
        # Sorftime category trend supplements trend signal
        sf_ct = demand.get("sorftime_category_trend", {})
        sf_trend_dir = sf_ct.get("trend_direction", "")
        effective_trend = sf_trend_dir or sf_trend or str(trend_signal)

        score = 5.0
        note_parts = []
        if has_keyword:
            score += 1.0
            note_parts.append(f"卖家精灵核心词：{demand.get('top_keyword')}")
        if has_aba:
            score += 0.5
            note_parts.append("ABA 搜索词有数据")
        if has_sf_search:
            score += 1.0
            note_parts.append(f"Sorftime 月搜索量 {sf_top_kw.get('monthly_search_volume'):,}（{sf_top_kw.get('keyword')}）")
        if "增长" in effective_trend:
            score += 1.5
            note_parts.append(f"趋势增长（{effective_trend}）")
        elif "衰退" in effective_trend:
            score -= 2.0
            note_parts.append(f"趋势衰退（{effective_trend}）")
        elif "季节性" in effective_trend:
            score -= 0.5
            note_parts.append(f"强季节性（{effective_trend}）")
        score = max(1.0, min(10.0, score))
        return score, "；".join(note_parts) or "待补"

    def score_entry_barriers() -> tuple[float, str]:
        barrier_score_map = {"低": 9.0, "中": 6.0, "高": 3.0, "待确认": 5.0, "待补": 5.0}
        scores = []
        for b in entry_barriers:
            level = str(b.get("level", "待确认"))
            if level in barrier_score_map:
                scores.append(barrier_score_map[level])
        if not scores:
            return 5.0, "壁垒数据待补"
        avg = sum(scores) / len(scores)
        high_barriers = [b["type"] for b in entry_barriers if b.get("level") == "高"]
        note = f"综合壁垒评分 {avg:.1f}"
        if high_barriers:
            note += f"；高壁垒项：{'、'.join(high_barriers)}"
        return round(avg, 1), note

    def score_profitability() -> tuple[float, str]:
        margin = None
        for field in ("post_ads_returns_margin", "base_fba_margin"):
            val = profit.get(field)
            if isinstance(val, (int, float)):
                margin = float(val)
                break
        if margin is None:
            return 5.0, "利润数据待补，无法计算"
        margin_pct = margin * 100 if -1 <= margin <= 1 else margin
        if margin_pct >= 25:
            return 9.0, f"利润率 {margin_pct:.1f}%（空间充足）"
        elif margin_pct >= 15:
            return 6.5, f"利润率 {margin_pct:.1f}%（利润一般）"
        elif margin_pct >= 5:
            return 4.0, f"利润率 {margin_pct:.1f}%（利润偏紧）"
        else:
            return 2.0, f"利润率 {margin_pct:.1f}%（利润不健康）"

    def score_new_listing_friendliness() -> tuple[float, str]:
        friendliness = new_listing.get("friendliness", {}) if isinstance(new_listing, dict) else {}
        overall = friendliness.get("overall") if isinstance(friendliness, dict) else ""
        recent_count = new_listing.get("new_listing_count_6m")
        recent_share = new_listing.get("recent_6m_units_share")
        if overall == "绿":
            return 8.0, f"近半年新品信号较好；新品数 {recent_count}，销量占比 {_fmt_percent(recent_share)}"
        if overall == "黄":
            return 6.0, f"近半年新品信号一般；新品数 {recent_count}，销量占比 {_fmt_percent(recent_share)}"
        if overall == "红":
            return 3.5, f"近半年新品信号偏弱；新品数 {recent_count}，销量占比 {_fmt_percent(recent_share)}"
        return 5.0, "新品友好度待确认"

    def score_risk() -> tuple[float, str]:
        return_score = 5.0
        return_level = ""
        for barrier in entry_barriers:
            if barrier.get("type") in {"技术壁垒", "合规壁垒"} and barrier.get("level") == "高":
                return 3.0, f"{barrier.get('type')}为高，需要专业复核"
            if barrier.get("type") == "供应链壁垒":
                return_level = str(barrier.get("level", "待确认"))
        if return_level == "低":
            return_score = 7.0
        elif return_level == "中":
            return_score = 5.0
        elif return_level == "高":
            return_score = 3.0
        return return_score, f"退货/供应链壁垒：{return_level or '待确认'}；知产/合规未专业复核前仅作早期风险参考"

    def score_data_completeness() -> tuple[float, str]:
        quality = candidate.get("market_structure", {}).get("data_quality", {})
        quality_score_value = quality.get("quality_score")
        if isinstance(quality_score_value, (int, float)):
            return max(1.0, min(10.0, quality_score_value / 10)), (
                f"Top商品质量分 {quality_score_value}；实际 {quality.get('actual_count')} / 要求 {quality.get('expected_count')}"
            )
        return 5.0, "数据完整度待确认"

    gating_reasons = [
        "利润复核未回填",
        "知产/合规初筛未回填",
    ]

    weights = {
        "市场规模": 0.16,
        "竞争格局": 0.16,
        "需求清晰度": 0.14,
        "新品友好度": 0.12,
        "利润可行性": 0.16,
        "知产/合规/退货风险": 0.14,
        "数据完整度": 0.12,
    }

    s_market, n_market = score_market_size()
    s_competition, n_competition = score_competition()
    s_demand, n_demand = score_demand_clarity()
    s_new, n_new = score_new_listing_friendliness()
    s_profit, n_profit = score_profitability()
    s_risk, n_risk = score_risk()
    s_data, n_data = score_data_completeness()

    dimensions = {
        "市场规模": {"score": round(s_market, 1), "weight": weights["市场规模"], "note": n_market},
        "竞争格局": {"score": round(s_competition, 1), "weight": weights["竞争格局"], "note": n_competition},
        "需求清晰度": {"score": round(s_demand, 1), "weight": weights["需求清晰度"], "note": n_demand},
        "新品友好度": {"score": round(s_new, 1), "weight": weights["新品友好度"], "note": n_new},
        "利润可行性": {"score": round(s_profit, 1), "weight": weights["利润可行性"], "note": n_profit},
        "知产/合规/退货风险": {"score": round(s_risk, 1), "weight": weights["知产/合规/退货风险"], "note": n_risk},
        "数据完整度": {"score": round(s_data, 1), "weight": weights["数据完整度"], "note": n_data},
    }

    weighted_total = sum(dim["score"] * dim["weight"] for dim in dimensions.values())
    weighted_total = round(weighted_total, 2)

    if gating_reasons:
        decision = "WAIT"
    elif weighted_total >= 7.5:
        decision = "GO"
    elif weighted_total >= 6.0:
        decision = "WAIT"
    elif weighted_total >= 4.0:
        decision = "WAIT"
    else:
        decision = "NO-GO"

    return {
        "weighted_score": weighted_total,
        "decision": decision,
        "gating_reasons": gating_reasons,
        "dimensions": dimensions,
        "note": "评分基于当前已有数据自动估算；利润或知产/合规未回填时只能给 WAIT/观察，不给强 GO。",
    }


def _select_candidate(candidates: list[dict[str, Any]], candidate_id: str | None) -> dict[str, Any]:
    if not candidates:
        raise ValueError("candidate_pool.candidates is empty")

    if candidate_id and candidate_id not in ("", "__first__"):
        for candidate in candidates:
            if candidate.get("candidate_id") == candidate_id:
                return candidate
        raise ValueError(f"candidate_id not found: {candidate_id}")

    for status in PREFERRED_STATUSES:
        for candidate in candidates:
            if candidate.get("status") == status:
                return candidate
    return candidates[0]


def _build_review_sources(voc_package: dict[str, Any] | None) -> dict[str, Any]:
    if not voc_package:
        return {}
    metadata = voc_package.get("metadata", {})
    summary = voc_package.get("summary", {})
    return {
        "package_id": metadata.get("package_id"),
        "source_type": metadata.get("source_type"),
        "source_files": metadata.get("source_files", []),
        "generated_at": metadata.get("generated_at"),
        "summary": summary,
        "collection_context": summary.get("collection_context", {}),
        "ai_report_reference": voc_package.get("ai_report_reference", {}),
    }


def _build_decision_review(
    candidate: dict[str, Any],
    voc_package: dict[str, Any] | None,
    go_nogo_scorecard: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "status_explanation": _status_explanation(candidate, voc_package),
        "facts": _decision_facts(candidate, voc_package),
        "inferences": _decision_inferences(candidate, voc_package),
        "missing_inputs": _decision_missing_inputs(candidate, voc_package),
        "action_items": _decision_action_items(candidate, voc_package),
        "risk_matrix": _decision_risk_matrix(candidate, voc_package),
        "go_nogo_scorecard": go_nogo_scorecard or {},
    }


def _status_explanation(candidate: dict[str, Any], voc_package: dict[str, Any] | None) -> str:
    # Status interpretation is Claude's work, not a script rule.
    return ""


def _decision_facts(candidate: dict[str, Any], voc_package: dict[str, Any] | None) -> list[str]:
    facts = [
        f"市场规模：{_market_size_text(candidate)}",
        f"价格带：{_price_band_text(candidate)}",
        f"竞争结构：{_brand_concentration_text(candidate)}",
        f"新品机会：{_new_listing_text(candidate)}",
        f"退货率：{_return_rate_text(candidate)}",
    ]
    if voc_package:
        summary = voc_package.get("summary", {})
        scope = _voc_scope_text(summary)
        facts.append(
            f"评论 VOC：已接入 {summary.get('review_count', 0)} 条评论，覆盖 {summary.get('asin_count', 0)} 个 ASIN，低分评论 {summary.get('low_rating_count', 0)} 条。"
            + (f"{scope}。" if scope else "")
        )
    market_structure_summary = _market_structure_summary_line(candidate)
    if market_structure_summary:
        facts.append(market_structure_summary)
    return [item for item in facts if item and "待填" not in item]


def _decision_inferences(candidate: dict[str, Any], voc_package: dict[str, Any] | None) -> list[str]:
    # Rule-based inference text removed. Claude reads the facts section above
    # and provides real inferences in conversation.
    return []


def _decision_missing_inputs(candidate: dict[str, Any], voc_package: dict[str, Any] | None) -> list[str]:
    missing = list(candidate.get("missing_data", []))
    if voc_package:
        missing = [item for item in missing if "评论" not in item and "VOC" not in item]
    for item in ["建议售价", "采购价", "FBA费用", "头程费用", "入库配置费", "商标/专利复核", "合规认证复核"]:
        if item not in missing:
            missing.append(item)
    quality = candidate.get("market_structure", {}).get("data_quality", {})
    expected_count = quality.get("expected_count")
    actual_count = quality.get("actual_count")
    if isinstance(expected_count, int) and isinstance(actual_count, int) and actual_count < expected_count:
        top100_gap = f"完整 Top{expected_count} 商品明细（当前 {actual_count} 条）"
        if top100_gap not in missing:
            missing.append(top100_gap)
    return missing


def _decision_action_items(candidate: dict[str, Any], voc_package: dict[str, Any] | None) -> list[str]:
    # Action items are Claude's work, not hardcoded script rules.
    return []


def _decision_risk_matrix(candidate: dict[str, Any], voc_package: dict[str, Any] | None) -> list[dict[str, str]]:
    competition = candidate.get("competition_structure", {})
    return_risk = candidate.get("return_risk", {})
    ip_risk = candidate.get("ip_compliance_risk", {})
    top10_share = competition.get("top10_product_units_share")
    first_pain = _first_pain_name(voc_package)
    data_quality = candidate.get("market_structure", {}).get("data_quality", {})
    return [
        {
            "dimension": "市场容量",
            "level": "中",
            "basis": _market_size_text(candidate),
        },
        {
            "dimension": "竞争集中度",
            "level": "高" if isinstance(top10_share, (int, float)) and top10_share >= 0.5 else "中",
            "basis": _brand_concentration_text(candidate),
        },
        {
            "dimension": "新品机会",
            "level": "中",
            "basis": _new_listing_text(candidate),
        },
        {
            "dimension": "评论/VOC",
            "level": "高" if first_pain else "待补",
            "basis": f"首要痛点：{first_pain}" if first_pain else "未接入评论 VOC",
        },
        {
            "dimension": "退货风险",
            "level": str(return_risk.get("level", "待确认")),
            "basis": _return_rate_text(candidate),
        },
        {
            "dimension": "利润不确定性",
            "level": "待补",
            "basis": "采购价、FBA、头程和入库配置费仍未补齐。",
        },
        {
            "dimension": "知产/合规",
            "level": str(ip_risk.get("level", "待确认")),
            "basis": str(ip_risk.get("notes", "待复核")),
        },
        {
            "dimension": "数据质量",
            "level": str(data_quality.get("level", "待确认")),
            "basis": _market_structure_summary_line(candidate) or "Top 商品明细待补",
        },
    ]


def _status_next_step(decision_review: dict[str, Any], candidate: dict[str, Any]) -> str:
    # Next step suggestion is Claude's work.
    return ""


def _first_pain_name(voc_package: dict[str, Any] | None) -> str:
    if not voc_package:
        return ""
    pain_points = voc_package.get("pain_points", [])
    if not pain_points:
        return ""
    return str(pain_points[0].get("name", ""))


def _market_size_text(candidate: dict[str, Any]) -> str:
    demand = candidate.get("demand_evidence", {})
    competition = candidate.get("competition_structure", {})
    parts = []
    if competition.get("sample_product_count") is not None:
        parts.append(f"样本商品数 {_fmt_number(competition.get('sample_product_count'))}")
    if demand.get("market_avg_monthly_units") is not None:
        parts.append(f"市场月均销量 {_fmt_number(demand.get('market_avg_monthly_units'))}")
    if demand.get("market_avg_monthly_revenue_usd") is not None:
        parts.append(f"市场月均销售额 USD {_fmt_number(demand.get('market_avg_monthly_revenue_usd'))}")
    if competition.get("top10_avg_monthly_units") is not None:
        parts.append(f"Top10 月均销量 {_fmt_number(competition.get('top10_avg_monthly_units'))}")
    return "；".join(parts) if parts else "待填"


def _price_band_text(candidate: dict[str, Any]) -> str:
    demand = candidate.get("demand_evidence", {})
    profit = candidate.get("preliminary_profit_space", {})
    parts = []
    if profit.get("top_price_band_by_units"):
        parts.append(f"销量集中价格带 {profit.get('top_price_band_by_units')} USD")
    if profit.get("top_price_band_units_share") is not None:
        parts.append(f"该价格带销量占比 {_fmt_percent(profit.get('top_price_band_units_share'))}")
    if demand.get("market_avg_price_usd") is not None:
        parts.append(f"市场平均价 USD {_fmt_number(demand.get('market_avg_price_usd'))}")
    return "；".join(parts) if parts else "待填"


def _brand_concentration_text(candidate: dict[str, Any]) -> str:
    competition = candidate.get("competition_structure", {})
    top_brand = competition.get("top_brand")
    top_share = competition.get("top_brand_units_share")
    top10_share = competition.get("top10_product_units_share")
    parts = []
    if top_brand:
        parts.append(f"头部品牌 {top_brand} 销量占比 {_fmt_percent(top_share)}")
    if top10_share is not None:
        parts.append(f"Top10 商品销量占比 {_fmt_percent(top10_share)}")
    return "；".join(parts) if parts else "待填"


def _seller_concentration_text(candidate: dict[str, Any]) -> str:
    competition = candidate.get("competition_structure", {})
    location = competition.get("top_seller_location")
    share = competition.get("top_seller_location_units_share")
    if location:
        return f"主要卖家所在地 {location}，销量占比 {_fmt_percent(share)}"
    return "待填"


def _new_listing_text(candidate: dict[str, Any]) -> str:
    new_listing = candidate.get("new_listing_opportunity", {})
    parts = []
    if new_listing.get("new_listing_count_6m") is not None:
        parts.append(f"近半年新品 {new_listing.get('new_listing_count_6m')} 个")
    if new_listing.get("new_listing_avg_monthly_units") is not None:
        parts.append(f"近半年新品月均销量 {_fmt_number(new_listing.get('new_listing_avg_monthly_units'))}")
    if new_listing.get("recent_6m_units_share") is not None:
        parts.append(f"近半年新品销量占比 {_fmt_percent(new_listing.get('recent_6m_units_share'))}")
    return "；".join(parts) if parts else "待填"


def _return_rate_text(candidate: dict[str, Any]) -> str:
    return_risk = candidate.get("return_risk", {})
    market_rate = return_risk.get("market_return_rate")
    category_rate = return_risk.get("category_return_rate")
    if market_rate is None and category_rate is None:
        return "待填"
    return f"市场退货率 {_fmt_percent(market_rate)}；类目退货率 {_fmt_percent(category_rate)}"


def _market_structure_summary_line(candidate: dict[str, Any]) -> str:
    market_structure = candidate.get("market_structure", {})
    summary = market_structure.get("summary", {}) if isinstance(market_structure, dict) else {}
    if summary.get("quality_summary"):
        return f"数据质量：{summary.get('quality_summary')}"
    return ""


def _competitor_items(items: Any) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        return []
    result = []
    for item in items:
        if not isinstance(item, dict):
            continue
        result.append(
            {
                "asin": item.get("asin"),
                "title": item.get("title"),
                "brand": item.get("brand"),
                "seller": item.get("seller"),
                "price": item.get("price"),
                "monthly_units": item.get("monthly_units"),
                "monthly_revenue_usd": item.get("monthly_revenue_usd"),
                "units_share": item.get("units_share"),
                "bsr": item.get("bsr"),
                "rating": item.get("rating"),
                "rating_count": item.get("rating_count"),
                "listing_date": item.get("listing_date"),
                "listing_days": item.get("listing_days"),
                "note": item.get("note"),
                "url": item.get("url"),
            }
        )
    return result


def _fmt_number(value: Any) -> str:
    if value is None:
        return "待填"
    if isinstance(value, (int, float)):
        if abs(value) >= 1000:
            return f"{value:,.0f}"
        if value == int(value):
            return str(int(value))
        return f"{value:.2f}"
    return str(value)


def _fmt_percent(value: Any) -> str:
    if value is None:
        return "待填"
    if isinstance(value, (int, float)):
        percent_value = value * 100 if -1 <= value <= 1 else value
        return f"{percent_value:.2f}%"
    text = str(value)
    return text if "%" in text else text + "%"


def _build_voc_analysis(voc_package: dict[str, Any] | None) -> dict[str, Any]:
    if not voc_package:
        return {}
    summary = voc_package.get("summary", {})
    return {
        "summary": summary,
        "source_scope": {
            "entry_site": summary.get("primary_entry_site", ""),
            "primary_review_region": summary.get("primary_review_region", ""),
            "entry_site_distribution": summary.get("entry_site_distribution", []),
            "review_region_distribution": summary.get("review_region_distribution", []),
            "note": summary.get("source_scope_note", ""),
        },
        "pain_points": _trim_findings(voc_package.get("pain_points", []), finding_limit=8, evidence_limit=5),
        "highlights": _trim_findings(voc_package.get("highlights", []), finding_limit=6, evidence_limit=5),
        "opportunity_hypotheses": voc_package.get("opportunity_hypotheses", [])[:8],
        "evidence_policy": "评论结论必须追溯到 review_id、ASIN、评分和评论链接。",
    }


def _trim_findings(findings: list[dict[str, Any]], finding_limit: int, evidence_limit: int) -> list[dict[str, Any]]:
    trimmed = []
    for finding in findings[:finding_limit]:
        trimmed.append(
            {
                **finding,
                "evidence": finding.get("evidence", [])[:evidence_limit],
            }
        )
    return trimmed


def _build_voc_opportunities(voc_package: dict[str, Any] | None, candidate_id: str | None) -> list[dict[str, Any]]:
    if not voc_package:
        return []
    opportunities = []
    for item in voc_package.get("opportunity_hypotheses", [])[:8]:
        opportunities.append(
            {
                "candidate_id": candidate_id,
                "source": "review_voc_package",
                "topic": item.get("name"),
                "hypothesis": item.get("hypothesis"),
                "evidence_review_ids": item.get("evidence_review_ids", []),
                "confidence": item.get("confidence", "待确认"),
            }
        )
    return opportunities


def _collect_voc_evidence(voc_package: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not voc_package:
        return []
    rows: list[dict[str, Any]] = []
    for finding_type, findings in (
        ("痛点", voc_package.get("pain_points", [])),
        ("亮点", voc_package.get("highlights", [])),
    ):
        for finding in findings:
            for evidence in finding.get("evidence", []):
                rows.append(
                    {
                        "finding_type": finding_type,
                        "finding_name": finding.get("name"),
                        "review_count": finding.get("review_count"),
                        "severity": finding.get("severity"),
                        **evidence,
                    }
                )
    return rows or _collect_raw_review_evidence(voc_package)


def _collect_raw_review_evidence(voc_package: dict[str, Any], limit: int = 80) -> list[dict[str, Any]]:
    reviews = [item for item in voc_package.get("normalized_reviews", []) if isinstance(item, dict)]
    reviews.sort(key=lambda item: (review_rating_sort_key(item), -(item.get("helpful_count") or 0)))
    rows: list[dict[str, Any]] = []
    for review in reviews:
        snippet = review_snippet(review)
        if not snippet:
            continue
        rows.append(
            {
                "finding_type": "原始评论",
                "finding_name": "待 Claude 归纳",
                "review_count": "",
                "severity": "待分析",
                "review_id": review.get("review_id"),
                "asin": review.get("asin"),
                "site": review.get("site"),
                "review_region": review.get("review_region"),
                "rating": review.get("rating"),
                "review_date": review.get("review_date"),
                "snippet": snippet,
                "url": review.get("url"),
            }
        )
        if len(rows) >= limit:
            break
    return rows


def review_rating_sort_key(review: dict[str, Any]) -> float:
    rating = review.get("rating")
    if isinstance(rating, (int, float)):
        return float(rating)
    try:
        return float(str(rating).strip())
    except (TypeError, ValueError):
        return 9.0


def review_snippet(review: dict[str, Any], limit: int = 180) -> str:
    text = str(review.get("review_text_zh") or review.get("review_text") or "").strip()
    text = " ".join(text.split())
    return text[:limit]


def _build_competitor_selection_logic(candidate: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in candidate.get("next_review_voc_asins", []) or []:
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "asin": item.get("asin"),
                "brand": item.get("brand"),
                "title": item.get("title"),
                "price_usd": item.get("price_usd"),
                "monthly_units": item.get("monthly_units"),
                "rating": item.get("rating"),
                "rating_count": item.get("rating_count"),
                "competitor_type": item.get("competitor_type") or item.get("reason"),
                "coverage_dimensions": item.get("coverage_dimensions", []),
                "selection_reason": item.get("selection_reason") or item.get("reason"),
            }
        )
    return rows


def _voc_summary_line(voc_package: dict[str, Any] | None) -> str:
    if not voc_package:
        return ""
    summary = voc_package.get("summary", {})
    scope = _voc_scope_text(summary)
    return (
        f"评论 VOC 已接入：共 {summary.get('review_count', 0)} 条评论、"
        f"{summary.get('asin_count', 0)} 个 ASIN，低分评论 {summary.get('low_rating_count', 0)} 条。"
        + (f"{scope}。" if scope else "")
    )


def _voc_dashboard_card(voc_package: dict[str, Any] | None) -> dict[str, Any] | None:
    if not voc_package:
        return None
    summary = voc_package.get("summary", {})
    return {
        "title": "评论 VOC",
        "status": "已接入",
        "review_count": summary.get("review_count", 0),
        "entry_site": summary.get("primary_entry_site", ""),
        "primary_review_region": summary.get("primary_review_region", ""),
        "low_rating_count": summary.get("low_rating_count", 0),
        "analysis_note": "痛点/亮点分析由 Claude 在对话中完成，请读取 normalized_reviews。",
    }


def _voc_scope_text(summary: dict[str, Any]) -> str:
    if not summary:
        return ""
    entry_site = summary.get("primary_entry_site")
    review_region = summary.get("primary_review_region")
    if entry_site and review_region:
        return f"采集入口为「{entry_site}」，评论地区以「{review_region}」为主，入口站点不等同于目标市场"
    if entry_site:
        return f"采集入口为「{entry_site}」，入口站点不等同于目标市场"
    if review_region:
        return f"评论地区以「{review_region}」为主"
    return ""


def _append_sentence(base: str, sentence: str) -> str:
    if not sentence:
        return base
    return f"{base} {sentence}"


# ── 重点竞品深拆卡 ─────────────────────────────────────────────────────────────

def _build_competitor_deep_dive(competitor_candidates: dict[str, Any]) -> list[dict[str, Any]]:
    """Build raw competitor data cards for Claude to analyze.

    No analysis text is generated here — learnable points, barriers, and
    strategic notes are for Claude to assess in conversation.
    """
    cards: list[dict[str, Any]] = []
    seen_asins: set[str] = set()

    def add_card(item: dict[str, Any], card_type: str) -> None:
        asin = str(item.get("asin") or "").strip()
        if not asin or asin in seen_asins:
            return
        seen_asins.add(asin)
        cards.append({
            "asin": asin,
            "card_type": card_type,
            "title": item.get("title"),
            "brand": item.get("brand"),
            "price_usd": item.get("price"),
            "monthly_units": item.get("monthly_units"),
            "rating": item.get("rating"),
            "rating_count": item.get("rating_count"),
            "listing_days": item.get("listing_days"),
            "note": item.get("note"),
            "url": item.get("url"),
            "traffic_keywords": [],  # P19 Sorftime 补充
        })

    for item in (competitor_candidates.get("top10") or [])[:3]:
        add_card(item, "标杆老品")
    for item in (competitor_candidates.get("recent_winners") or [])[:2]:
        add_card(item, "近半年新品")

    return cards


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a minimal research package from one candidate in a candidate pool.")
    parser.add_argument("candidate_pool_json")
    parser.add_argument("output_json")
    parser.add_argument("candidate_id", nargs="?", default=None)
    parser.add_argument("--voc-package", default="", help="Optional review_voc_package.json from review plugin exports.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    pool_path = Path(args.candidate_pool_json)
    output_path = Path(args.output_json)
    voc_package = json.loads(Path(args.voc_package).read_text(encoding="utf-8")) if args.voc_package else None
    candidate_pool = json.loads(pool_path.read_text(encoding="utf-8"))
    package = build_research_package(candidate_pool, args.candidate_id, voc_package)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(package, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
