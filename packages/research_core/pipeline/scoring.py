"""Market opportunity scoring — scorecard computation from candidate evidence."""

from __future__ import annotations

from typing import Any

from packages.research_core.pipeline.market_text import _fmt_number, _fmt_percent, _positive_count, _price_band_text
from packages.research_core.pipeline.voc_analysis import _voc_summary
from packages.research_core.pipeline.market_boundary import _is_broad_market_keyword



def _build_entry_barriers(candidate: dict[str, Any]) -> list[dict[str, Any]]:
    competition = candidate.get("competition_structure", {})
    return_risk = candidate.get("return_risk", {})
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
            "type": "价格带壁垒",
            "level": "中",
            "data_basis": _price_band_text(candidate),
            "rule": "价格带有销量且低评论样本存在=低；价格带被头部垄断或样本不足=中/高",
        },
        {
            "type": "退货/体验壁垒",
            "level": "中" if return_level in ("中", "高") else "低",
            "data_basis": f"退货风险等级：{return_level}",
            "rule": "退货率高、评论痛点集中或体验门槛高=高；否则按中低处理",
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
        broad_keyword = _is_broad_market_keyword(str(demand.get("top_keyword") or ""))
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
            if broad_keyword:
                score -= 1.0
                note_parts.append(f"卖家精灵核心词过宽：{demand.get('top_keyword')}")
            else:
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

    def score_category_clarity() -> tuple[float, str]:
        category_report = demand.get("sorftime_category_report", {}) if isinstance(demand.get("sorftime_category_report"), dict) else {}
        boundary = candidate.get("candidate_boundary_review", {}) if isinstance(candidate.get("candidate_boundary_review"), dict) else {}
        audit = candidate.get("market_boundary_audit", {}) if isinstance(candidate.get("market_boundary_audit"), dict) else {}
        score = 5.0
        notes: list[str] = []
        if category_report.get("category_name") or category_report.get("node_id"):
            score += 1.5
            notes.append("已有 Sorftime/类目候选信号")
        if boundary.get("recommended_mainline"):
            score += 1.5
            notes.append(f"主线边界：{boundary.get('recommended_mainline')}")
        mixed = boundary.get("exclude_routes") if isinstance(boundary.get("exclude_routes"), list) else []
        if mixed:
            score += 0.5
            notes.append(f"已记录排除/混池 {len(mixed)} 项")
        if audit.get("broad_keyword"):
            score = min(score, 5.0)
            notes.append(f"核心词过宽：{audit.get('broad_keyword')}")
        if _positive_count(audit.get("excluded_competitor_count")):
            score = min(score, 4.5)
            notes.append(f"竞品池发现 {audit.get('excluded_competitor_count')} 个非同类样本")
        if _positive_count(audit.get("suspect_competitor_count")):
            score = min(score, 6.0)
            notes.append(f"仍有 {audit.get('suspect_competitor_count')} 个边界样本待复核")
        return max(1.0, min(10.0, score)), "；".join(notes) or "小类边界待补"

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
            if barrier.get("type") == "退货/体验壁垒":
                return_level = str(barrier.get("level", "待确认"))
        if return_level == "低":
            return_score = 7.0
        elif return_level == "中":
            return_score = 5.0
        elif return_level == "高":
            return_score = 3.0
        return return_score, f"退货/体验壁垒：{return_level or '待确认'}"

    def score_data_completeness() -> tuple[float, str]:
        quality = candidate.get("market_structure", {}).get("data_quality", {})
        audit = candidate.get("market_boundary_audit", {}) if isinstance(candidate.get("market_boundary_audit"), dict) else {}
        quality_score_value = quality.get("quality_score")
        if isinstance(quality_score_value, (int, float)):
            score = max(1.0, min(10.0, quality_score_value / 10))
            note = f"Top商品质量分 {quality_score_value}；实际 {quality.get('actual_count')} / 要求 {quality.get('expected_count')}"
            if _positive_count(audit.get("excluded_competitor_count")) or audit.get("broad_keyword"):
                score = min(score, 6.0)
                note += "；但竞品/关键词边界存在污染，完整度按可用证据降权"
            return score, note
        return 5.0, "数据完整度待确认"

    def score_voc_evidence() -> tuple[float, str]:
        summary = _voc_summary(voc_package)
        review_count = _positive_count(summary.get("review_count"))
        asin_count = _positive_count(summary.get("asin_count"))
        curated_count = len(voc_package.get("pain_points", [])) if isinstance(voc_package, dict) and isinstance(voc_package.get("pain_points"), list) else 0
        if review_count >= 100 and asin_count >= 5:
            if curated_count:
                return 8.0, f"VOC 样本 {review_count} 条，覆盖 {asin_count} 个 ASIN，已形成 {curated_count} 个痛点"
            return 6.0, f"VOC 样本 {review_count} 条，覆盖 {asin_count} 个 ASIN，但仍需把原始评论归纳成痛点"
        if review_count >= 30 and asin_count >= 2:
            return 6.5 if curated_count else 5.5, f"VOC 样本 {review_count} 条，覆盖 {asin_count} 个 ASIN"
        if review_count:
            return 5.0, f"VOC 样本 {review_count} 条，覆盖 {asin_count} 个 ASIN，样本偏少"
        return 4.0, "评论 VOC 待接入"

    gating_reasons: list[str] = []
    if not candidate.get("market_structure"):
        gating_reasons.append("市场结构证据不足")
    if not candidate.get("competitor_candidates"):
        gating_reasons.append("代表竞品证据不足")
    if not voc_package:
        gating_reasons.append("评论 VOC 未接入")
    boundary_audit = candidate.get("market_boundary_audit", {}) if isinstance(candidate.get("market_boundary_audit"), dict) else {}
    if boundary_audit.get("broad_keyword"):
        gating_reasons.append(f"核心词过宽：{boundary_audit.get('broad_keyword')}")
    if _positive_count(boundary_audit.get("excluded_competitor_count")):
        gating_reasons.append(f"竞品池存在 {boundary_audit.get('excluded_competitor_count')} 个非同类样本，需先清洗边界")
    if voc_package and not voc_package.get("pain_points"):
        gating_reasons.append("VOC 已接入但痛点尚未完成结构化归纳")

    weights = {
        "市场规模": 0.16,
        "竞争格局": 0.16,
        "需求清晰度": 0.14,
        "小类边界清晰度": 0.12,
        "新品友好度": 0.12,
        "VOC证据质量": 0.14,
        "退货/体验风险": 0.10,
        "数据完整度": 0.12,
    }

    s_market, n_market = score_market_size()
    s_competition, n_competition = score_competition()
    s_demand, n_demand = score_demand_clarity()
    s_category, n_category = score_category_clarity()
    s_new, n_new = score_new_listing_friendliness()
    s_voc, n_voc = score_voc_evidence()
    s_risk, n_risk = score_risk()
    s_data, n_data = score_data_completeness()

    dimensions = {
        "市场规模": {"score": round(s_market, 1), "weight": weights["市场规模"], "note": n_market},
        "竞争格局": {"score": round(s_competition, 1), "weight": weights["竞争格局"], "note": n_competition},
        "需求清晰度": {"score": round(s_demand, 1), "weight": weights["需求清晰度"], "note": n_demand},
        "小类边界清晰度": {"score": round(s_category, 1), "weight": weights["小类边界清晰度"], "note": n_category},
        "新品友好度": {"score": round(s_new, 1), "weight": weights["新品友好度"], "note": n_new},
        "VOC证据质量": {"score": round(s_voc, 1), "weight": weights["VOC证据质量"], "note": n_voc},
        "退货/体验风险": {"score": round(s_risk, 1), "weight": weights["退货/体验风险"], "note": n_risk},
        "数据完整度": {"score": round(s_data, 1), "weight": weights["数据完整度"], "note": n_data},
    }

    weighted_total = sum(dim["score"] * dim["weight"] for dim in dimensions.values())
    weighted_total = round(weighted_total, 2)

    if weighted_total >= 7.5 and not gating_reasons:
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
        "note": "评分基于当前市场、关键词、竞品、VOC 和数据完整度自动估算；GO 只表示市场机会可继续深挖，不代表进入采购或上架。",
    }
