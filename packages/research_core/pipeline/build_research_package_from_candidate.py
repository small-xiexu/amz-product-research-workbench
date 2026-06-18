#!/usr/bin/env python3
"""Build a minimal research package from one candidate in a candidate pool."""

from __future__ import annotations

import json
from pathlib import Path
import re
import sys
from typing import Any
import argparse


PREFERRED_STATUSES = ("继续看", "试做", "观察", "先放弃")

PRODUCT_ROUTE_DEFINITIONS: tuple[dict[str, Any], ...] = (
    {
        "route_id": "core_hands_free_waist",
        "route_name": "基础款：腰包/腰带 + 单牵引绳",
        "route_type": "主线",
        "priority": 10,
        "opportunity": "最贴近 hands free dog leash 主需求，适合先拿样确认腰带、防滑、弹力绳和腰包细节。",
        "risks": "容易同质化，不能只比低价；腰带下滑、扣具强度和弹力寿命会直接影响差评。",
        "validation_actions": [
            "让供应商分别报基础款和升级款真实阶梯价。",
            "样品重点测腰带防滑、弹力段回弹、扣具拉力和腰包容量。",
        ],
        "decision_hint": "可以作为主推基准款，但必须和升级款一起比较利润和差异化。",
    },
    {
        "route_id": "dual_leash_waist_bag",
        "route_name": "升级款：双牵引绳 + 腰包/腰带",
        "route_type": "升级",
        "priority": 20,
        "opportunity": "对应多狗家庭和更高客单价场景，和基础免手持款有明显区分，值得单独验证。",
        "risks": "双犬同时拉拽时更考验防缠绕、两侧受力、腰带防滑和双扣强度，不能只看图片像不像。",
        "validation_actions": [
            "让供应商确认单体/双体、单套/双套是否同链接可选，并拆分报价。",
            "样品要测两犬拉拽、防缠绕、腰带位移、双扣和缝线强度。",
        ],
        "decision_hint": "不要混在普通腰包款里看；作为升级路线单独算成本、售价和样品测试。",
    },
    {
        "route_id": "multi_dog_without_waist",
        "route_name": "旁支：一拖二/双头多狗绳",
        "route_type": "旁支",
        "priority": 30,
        "opportunity": "能覆盖多狗需求和防缠绕卖点，可作为副方向观察。",
        "risks": "如果没有腰包/腰带/免手持结构，就不是当前主线，混进去会拉偏选品判断。",
        "validation_actions": [
            "确认是否真的能腰部佩戴；不能免手持的只进旁支，不进主推。",
            "重点看旋转扣、防缠绕结构和两犬长度差。",
        ],
        "decision_hint": "只作多狗变体池观察，除非补齐腰包/免手持证据。",
    },
    {
        "route_id": "safety_upgrade",
        "route_name": "安全升级：反光/双手柄/防爆冲",
        "route_type": "功能升级",
        "priority": 40,
        "opportunity": "反光、双手柄、防爆冲和加强扣具可以转成页面卖点，也能解释为什么比低价款贵。",
        "risks": "这些功能如果只停留在标题词，样品不达标反而容易被差评打回来。",
        "validation_actions": [
            "把反光面积、双手柄位置、弹力段长度、扣具材质写进打样清单。",
            "让供应商提供细节图、视频或测试说明。",
        ],
        "decision_hint": "适合作为基础/升级路线的必验卖点，不建议单独作为产品路线。",
    },
    {
        "route_id": "adjacent_or_watch",
        "route_name": "观察：斜挎/六合一/普通弹力绳",
        "route_type": "观察",
        "priority": 50,
        "opportunity": "可能有可借鉴结构或低价供给，可留作备选。",
        "risks": "形态容易偏离跑步腰包免手持，不能因为有牵引绳关键词就纳入主线。",
        "validation_actions": [
            "打开详情确认佩戴方式、适用场景和是否支持腰部免手持。",
            "证据不足时只留观察，不进入优先询价。",
        ],
        "decision_hint": "除非后续补到清晰腰包/免手持证据，否则不作为主线。",
    },
)

ROUTE_DEEP_DIVE_CONFIG: dict[str, dict[str, Any]] = {
    "core_hands_free_waist": {
        "seller_sprite_exports": [
            "用 hands free dog leash / dog running leash 跑搜索结果、市场分析 Top100 和 ABA。",
            "挑 3-5 个基础腰包/腰带款 ASIN 做关键词反查，看成交词是不是免手持跑步场景。",
        ],
        "sorftime_checks": [
            "keyword_detail：hands free dog leash、dog running leash。",
            "product_traffic_terms：基础腰带款 Top3 ASIN，确认流量词是不是腰部免手持。",
            "keyword_extends：排掉普通 dog leash、斜挎包、单独腰包等混池词。",
        ],
        "supply_chain_search_terms": ["跑步牵引绳 腰包", "免手持 狗绳 腰带", "宠物跑步牵引绳 腰包", "腰带 弹力 牵引绳"],
        "review_terms": ("hands free", "waist", "belt", "pouch", "bungee", "running", "jogging", "腰", "免手持"),
        "decision_gate": [
            "基础款样品能解决腰带下滑、扣具强度和弹力寿命。",
            "真实最高规格采购价 + 包装重量回填后，利润仍能接受。",
            "核心流量词与免手持跑步场景一致，不是普通 dog leash 混池。",
        ],
    },
    "dual_leash_waist_bag": {
        "seller_sprite_exports": [
            "用 double dog leash / dual dog leash / two dog leash 补搜索结果和关键词反查。",
            "单独拉双牵引 + 腰包款竞品 ASIN，不和普通腰包款混在一个 VOC 批次里判断。",
        ],
        "sorftime_checks": [
            "keyword_detail：double dog leash、dual dog leash、hands free leash for two dogs。",
            "product_traffic_terms：双狗腰包款代表 ASIN，确认是否有 two dogs / dual dog 成交流量。",
            "competitor_product_keywords：看升级款是否能避开普通低价 dog leash 竞争。",
        ],
        "supply_chain_search_terms": ["双牵引绳 腰包", "双狗 跑步 腰带", "一拖二 腰包 牵引绳", "双体 牵引绳 腰包"],
        "review_terms": (
            "double",
            "dual dog",
            "dual leash",
            "two dog",
            "two dogs",
            "2 dog",
            "2 dogs",
            "multiple dogs",
            "双",
            "两只",
            "多狗",
            "一拖二",
        ),
        "decision_gate": [
            "双犬同时拉拽时，腰带、防缠绕、双扣和缝线强度能过样品测试。",
            "评价插件覆盖双狗路线 ASIN，能看清真实差评是不是可解决。",
            "1688 供应商能拆分单体/双体、单套/双套报价，并确认最高规格真实价格。",
        ],
    },
    "multi_dog_without_waist": {
        "seller_sprite_exports": [
            "用 dual dog leash / no tangle dog leash 补旁支竞品，不和免手持腰包款合并判断。",
            "看一拖二路线是否只是低价配件，还是能形成独立需求。",
        ],
        "sorftime_checks": [
            "keyword_detail：dual dog leash、no tangle dog leash。",
            "product_traffic_terms：普通一拖二代表 ASIN，确认它是否抢的是多狗词而非免手持词。",
        ],
        "supply_chain_search_terms": ["一拖二 狗绳", "双头 狗狗牵引绳", "双狗 防缠绕 牵引绳", "多狗 牵引绳"],
        "review_terms": ("dual dog", "dual leash", "two dog", "2 dog", "no tangle", "tangle free", "一拖二", "双头", "防缠绕"),
        "decision_gate": [
            "确认它是否真的能腰部佩戴；不能免手持的，不进主推路线。",
            "若只覆盖多狗防缠绕需求，作为旁支观察，不抢主线资源。",
        ],
    },
    "safety_upgrade": {
        "seller_sprite_exports": [
            "不用单独立一条大盘，放进基础款和升级款竞品反查里看功能词。",
            "重点看 reflective / no pull / bungee / padded handle 是否真实带来转化。",
        ],
        "sorftime_checks": [
            "keyword_extends：查 reflective、no pull、bungee、padded handle 等功能长尾。",
            "similar_product_feature：方向确定后再用一次，确认热销品共有功能点。",
        ],
        "supply_chain_search_terms": ["反光 狗绳", "防爆冲 牵引绳", "双手柄 狗绳", "弹力 缓冲 牵引绳"],
        "review_terms": ("reflective", "no pull", "bungee", "padded handle", "handle", "tangle", "反光", "防爆冲", "弹力", "手柄"),
        "decision_gate": [
            "这些功能必须落到样品检查项，不能只停留在标题词。",
            "基础款和升级款都要验证反光面积、手柄位置、弹力段和扣具材质。",
        ],
    },
}


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
    supply_chain_signal = profit_space.get("supply_chain_signal", {}) if isinstance(profit_space, dict) else {}
    voc_analysis = _build_voc_analysis(voc_package)
    voc_review_sources = _build_review_sources(voc_package)
    voc_opportunities = _build_voc_opportunities(voc_package, candidate.get("candidate_id"))
    voc_summary_line = _voc_summary_line(voc_package)
    entry_barriers = _build_entry_barriers(candidate)
    go_nogo_scorecard = _build_go_nogo_scorecard(candidate, entry_barriers, voc_package)
    decision_review = _build_decision_review(candidate, voc_package, go_nogo_scorecard)
    product_route_matrix = _build_product_route_matrix(candidate, supply_chain_signal)
    route_deep_dive_plan = _build_route_deep_dive_plan(candidate, product_route_matrix, voc_package)
    ai_analysis = _build_ai_analysis_brief(
        candidate,
        voc_package,
        go_nogo_scorecard,
        product_route_matrix,
        route_deep_dive_plan,
    )

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
            "purchase_cost": _supply_chain_purchase_cost_text(supply_chain_signal),
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
            "sorftime_category_report": candidate.get("demand_evidence", {}).get("sorftime_category_report", {}),
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
            "supply_chain_signal": profit_space.get("supply_chain_signal", {}),
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
        "ai_analysis": ai_analysis,
        "product_route_matrix": product_route_matrix,
        "route_deep_dive_plan": route_deep_dive_plan,
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


def _build_ai_analysis_brief(
    candidate: dict[str, Any],
    voc_package: dict[str, Any] | None,
    go_nogo_scorecard: dict[str, Any],
    product_route_matrix: list[dict[str, Any]] | None = None,
    route_deep_dive_plan: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    profit = candidate.get("preliminary_profit_space", {})
    supply_chain_signal = profit.get("supply_chain_signal", {}) if isinstance(profit, dict) else {}
    voc_summary = _voc_summary(voc_package)
    data_source_scope = [
        "卖家精灵：先看市场大不大、头部强不强、价格好不好打",
        "Sorftime：看实时词和竞品流量，别只信一份历史表",
        "评价插件：看买家到底在吐槽什么",
        "1688 插件：看有没有货、多少钱、供应商能不能聊",
    ]
    gating = go_nogo_scorecard.get("gating_reasons") if isinstance(go_nogo_scorecard.get("gating_reasons"), list) else []
    supply_price = _supply_chain_purchase_cost_text(supply_chain_signal)
    supplier_count = supply_chain_signal.get("visual_confirmed_count") or supply_chain_signal.get("supplier_count") or 0
    review_count = _positive_count(voc_summary.get("review_count"))
    low_rating_count = _positive_count(voc_summary.get("low_rating_count"))
    asin_count = _positive_count(voc_summary.get("asin_count"))
    top_keyword = _top_sorftime_keyword_summary(candidate)
    route_summary = _product_route_plain_summary(product_route_matrix or [])

    return {
        "persona": "资深亚马逊运营专家",
        "role_scope": "先说人话结论，再看证据：这块就是先告诉你能不能继续、还差什么、卡在哪。",
        "data_source_scope": data_source_scope,
        "decision_principle": "数据越多越好，但不是拿来堆字。利润、合规、供应商没闭环前，不直接开干。",
        "thesis": {
            "title": _expert_thesis_title(go_nogo_scorecard),
            "body": _expert_thesis_body(review_count, supplier_count, gating),
        },
        "insights": [
            {
                "label": "市场能不能进",
                "title": "有量，但不能拿普通款硬冲",
                "body": _market_plain_summary(candidate),
            },
            {
                "label": "产品路线怎么走",
                "title": "先把路铺开，再挑主推款",
                "body": route_summary,
            },
            {
                "label": "需求和关键词",
                "title": "先盯准用户到底拿它来干嘛",
                "body": top_keyword or "关键词还要继续校准，别用泛词直接判断需求。",
            },
            {
                "label": "评论里在说啥",
                "title": "评论里最要命的是稳不稳、好不好用",
                "body": _voc_plain_summary(voc_package, review_count, asin_count, low_rating_count),
            },
            {
                "label": "供应链能不能接",
                "title": "先问清能不能稳定做，再谈卖点",
                "body": _supply_plain_summary(supplier_count, supply_price),
            },
            {
                "label": "现在卡哪",
                "title": "现在还差几块拼图",
                "body": _gating_plain_summary(gating),
            },
        ],
        "product_spec_actions": [
            "样品先测稳定性：腰带会不会滑、扣具会不会断、弹力绳会不会拉垮。",
            "把差评里的问题写成打样清单，让供应商逐条回答能不能改。",
            "页面不要只喊“免手持”，要把适合什么体型、什么场景讲清楚。",
            "如果做升级款，优先验证双手柄、反光、腰包容量和防滑结构。",
            "双牵引绳 + 腰包款要单独测防缠绕、两犬受力、腰带防滑和双扣强度。",
        ],
        "supplier_validation_actions": [
            "先从 3-5 家开始聊，别一上来海问几十家。",
            "直接问四件事：真实阶梯价、包装重量、能不能改款、样品多久到。",
            "让供应商拍细节图或视频，重点看扣具、缝线、腰带防滑和弹力段。",
            "基础款和升级款都要报价，别只看最低价把利润算歪。",
        ],
        "next_operator_actions": [
            "先补利润模板：售价、FBA、头程、入库配置费、广告费率和退货假设。",
            "再过一遍知产/合规：商标、外观/结构专利、材质安全和站点要求。",
            "把 1688 优先联系清单压缩到 3-5 家，拿到真实报价和样品证据后再决策。",
        ],
        "product_route_matrix": product_route_matrix or [],
        "route_deep_dive_plan": route_deep_dive_plan or [],
    }


def _expert_thesis_title(go_nogo_scorecard: dict[str, Any]) -> str:
    decision = str(go_nogo_scorecard.get("decision") or "WAIT").upper()
    if decision == "GO":
        return "可以进入试单准备，但仍要保留费用和合规复核。"
    if decision == "NO-GO":
        return "暂不建议立项，先止损或换方向。"
    return "继续看，但不要直接立项。"


def _expert_thesis_body(review_count: int, supplier_count: Any, gating: list[Any]) -> str:
    evidence = [
        f"评价样本 {review_count} 条" if review_count else "",
        f"1688 优先联系款 {supplier_count} 个" if supplier_count else "",
    ]
    gating_text = "；".join(map(str, gating[:3])) if gating else "利润、合规、样品和供应商真实确认仍需闭环"
    return _join_text(
        "我的判断是：可以继续看，但现在还不到立项的时候。",
        "；".join(item for item in evidence if item),
        f"还没闭环的是：{gating_text}",
    )


def _market_plain_summary(candidate: dict[str, Any]) -> str:
    demand = candidate.get("demand_evidence", {})
    competition = candidate.get("competition_structure", {})
    avg_units = demand.get("market_avg_monthly_units")
    top10_share = competition.get("top10_product_units_share")
    new_listing = candidate.get("new_listing_opportunity", {})
    recent_share = new_listing.get("recent_6m_units_share")
    parts = []
    if avg_units is not None:
        parts.append(f"平均每个商品月销约 {_fmt_number(avg_units)}，说明不是冷门小池子")
    else:
        parts.append("市场体量还要继续确认")
    if top10_share is not None:
        parts.append(f"但 Top10 吃掉约 {_fmt_percent(top10_share)} 销量，不能只靠低价硬打")
    if recent_share is not None:
        parts.append(f"近半年新品销量占比约 {_fmt_percent(recent_share)}，新品机会有但不算轻松")
    return "；".join(parts[:3])


def _top_sorftime_keyword_summary(candidate: dict[str, Any]) -> str:
    demand = candidate.get("demand_evidence", {})
    keywords = demand.get("sorftime_keyword_verification", [])
    if isinstance(keywords, list) and keywords:
        top_keyword = next((item for item in keywords if isinstance(item, dict) and item.get("monthly_search_volume")), keywords[0])
        if isinstance(top_keyword, dict):
            keyword = top_keyword.get("keyword") or "Sorftime 关键词"
            volume = top_keyword.get("monthly_search_volume") or top_keyword.get("weekly_search_volume")
            if volume is not None:
                return f"核心词「{keyword}」月搜约 {_fmt_number(volume)}，需求是有的；但要围绕具体使用场景筛，别被泛词带偏。"
            return f"已接入 Sorftime 关键词「{keyword}」，还要结合 ABA 和竞品词判断购买意图。"
    top_keyword = demand.get("top_keyword")
    if top_keyword:
        return f"卖家精灵核心词是「{top_keyword}」，下一步要确认它是不是目标形态的成交词。"
    return "关键词还要继续校准，别用泛词直接判断需求。"


def _voc_plain_summary(
    voc_package: dict[str, Any] | None,
    review_count: int,
    asin_count: int,
    low_rating_count: int,
) -> str:
    first_pain = _first_pain_name(voc_package)
    if review_count:
        base = f"已经看了 {review_count} 条评论、{asin_count} 个 ASIN，其中低分 {low_rating_count} 条"
        if first_pain:
            return f"{base}；优先解决「{first_pain}」，否则后面容易吃差评。"
        return f"{base}；下一步要把差评里的高频问题整理成打样检查表。"
    return "评论还没进来前，不要急着定产品方案。"


def _supply_plain_summary(supplier_count: Any, supply_price: str) -> str:
    parts = []
    if supplier_count:
        parts.append(f"现在有 {supplier_count} 个供应链候选，说明不是找不到货")
    else:
        parts.append("供应链候选还不够，需要继续找货")
    if supply_price != "待补":
        parts.append(f"采购价大致在 {supply_price}")
    parts.append("但真实报价、包装重量和能不能改款，必须问到供应商再算数")
    return "；".join(parts)


def _gating_plain_summary(gating: list[Any]) -> str:
    if not gating:
        return "继续把利润、合规、样品和供应商确认补齐，再决定是否 Go。"
    friendly = []
    for item in gating[:4]:
        text = str(item)
        if "利润" in text:
            friendly.append("利润还没算完整")
        elif "合规" in text or "知产" in text:
            friendly.append("合规/知产还没查完")
        else:
            friendly.append(text)
    return "；".join(friendly) + "。这些没补齐前，最多是继续看，不是直接开干。"


def _build_product_route_matrix(candidate: dict[str, Any], supply_chain_signal: dict[str, Any]) -> list[dict[str, Any]]:
    review = supply_chain_signal.get("visual_review_candidates") if isinstance(supply_chain_signal, dict) else {}
    review = review if isinstance(review, dict) else {}
    route_buckets = {definition["route_id"]: [] for definition in PRODUCT_ROUTE_DEFINITIONS}
    for group_key, group_label in (("priority_candidates", "优先联系"), ("watchlist_candidates", "观察待核")):
        items = review.get(group_key)
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            item_with_group = {**item, "route_source_group": group_label}
            for route_id in _classify_supply_route(item_with_group):
                route_buckets.setdefault(route_id, []).append(item_with_group)

    if not any(route_buckets.values()):
        for item in _market_route_reference_items(candidate):
            route_buckets.setdefault("adjacent_or_watch", []).append(item)

    routes: list[dict[str, Any]] = []
    for definition in PRODUCT_ROUTE_DEFINITIONS:
        items = route_buckets.get(definition["route_id"], [])
        if not items and definition["route_id"] != "dual_leash_waist_bag":
            continue
        price_min, price_max = _route_price_range(_route_price_items(items))
        priority_count = sum(1 for item in items if item.get("route_source_group") == "优先联系")
        watchlist_count = sum(1 for item in items if item.get("route_source_group") == "观察待核")
        routes.append(
            {
                "route_id": definition["route_id"],
                "route_name": definition["route_name"],
                "route_type": definition["route_type"],
                "candidate_count": len(items),
                "priority_count": priority_count,
                "watchlist_count": watchlist_count,
                "price_cny_min": price_min,
                "price_cny_max": price_max,
                "price_text": _route_price_text(price_min, price_max),
                "representative_items": [_route_item_summary(item) for item in items[:3]],
                "opportunity": definition["opportunity"],
                "risks": definition["risks"],
                "validation_actions": definition["validation_actions"],
                "decision_hint": definition["decision_hint"],
            }
        )
    routes.sort(key=lambda item: _route_priority(item.get("route_id")))
    return routes


def _classify_supply_route(item: dict[str, Any]) -> list[str]:
    text = _route_item_text(item)
    shape_text = _route_shape_text(item)
    review_text = _route_review_text(item)
    waist_terms = (
        "腰包",
        "腰带",
        "腰部",
        "束腰",
        "zipper pouch",
        "pouch",
    )
    has_waist = _contains_any(shape_text, waist_terms) or (
        _contains_any(review_text, waist_terms) and not _negates_waist_signal(review_text)
    )
    if _negates_waist_signal(review_text):
        has_waist = False
    has_dual = _contains_any(
        shape_text,
        (
            "一拖二",
            "双牵",
            "双头",
            "双钩",
            "双体",
            "双套",
            "两根牵引绳",
            "两犬",
            "两只狗",
            "多狗",
            "多犬",
            "two dog",
            "dual leash",
        ),
    ) or bool(re.search(r"(?:\*2|x2|×2)\s*(?:双体|双套|牵引|狗|犬)?", shape_text, flags=re.IGNORECASE))
    has_safety = _contains_any(
        text,
        (
            "反光",
            "夜跑",
            "防爆冲",
            "防冲",
            "弹力",
            "缓冲",
            "双手柄",
            "双把手",
            "近控",
            "防缠绕",
            "旋转扣",
            "金属扣",
            "耐用扣",
            "加固",
        ),
    )
    routes: list[str] = []
    if has_dual and has_waist:
        routes.append("dual_leash_waist_bag")
    elif has_waist:
        routes.append("core_hands_free_waist")
    elif has_dual:
        routes.append("multi_dog_without_waist")
    if has_safety:
        routes.append("safety_upgrade")
    if not routes:
        routes.append("adjacent_or_watch")
    return _dedupe_strings(routes)


def _route_item_text(item: dict[str, Any], include_review_notes: bool = True) -> str:
    fields: list[Any] = [
        item.get("title"),
        item.get("stock_text"),
        item.get("customization_text"),
        item.get("detail_summary"),
        item.get("detail_text_excerpt"),
        item.get("moq_text"),
    ]
    if include_review_notes:
        fields.append(item.get("rationale"))
    for key in ("sku_texts", "sku_options", "supplier_tags", "risk_notes"):
        value = item.get(key)
        if isinstance(value, list):
            fields.extend(value)
    return " ".join(str(field).lower() for field in fields if field not in (None, ""))


def _route_shape_text(item: dict[str, Any]) -> str:
    fields: list[Any] = [
        item.get("title"),
        item.get("stock_text"),
        item.get("moq_text"),
        item.get("customization_text"),
    ]
    for key in ("sku_texts", "sku_options"):
        value = item.get(key)
        if isinstance(value, list):
            fields.extend(value)
    return " ".join(str(field).lower() for field in fields if field not in (None, ""))


def _route_review_text(item: dict[str, Any]) -> str:
    fields: list[Any] = [item.get("rationale")]
    risks = item.get("risk_notes")
    if isinstance(risks, list):
        fields.extend(risks)
    return " ".join(str(field).lower() for field in fields if field not in (None, ""))


def _negates_waist_signal(text: str) -> bool:
    return bool(
        re.search(r"(?:没有|无|缺少|不是|不显示|不明显|未见|不含).{0,8}(?:腰包|腰带|腰部|免手持|解放双手)", text)
        or re.search(r"(?:核实|确认|需确认|需核实|待确认).{0,10}(?:是否有|有无)?.{0,8}(?:腰包|腰带|腰部|免手持|解放双手)", text)
    )


def _contains_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(needle.lower() in text for needle in needles)


def _dedupe_strings(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def _route_price_range(items: list[dict[str, Any]]) -> tuple[Any, Any]:
    lows: list[float] = []
    highs: list[float] = []
    for item in items:
        low = _first_numeric(
            item.get("detail_price_cny_min"),
            item.get("price_cny_min"),
            item.get("conservative_price_cny"),
        )
        high = _first_numeric(
            item.get("conservative_price_cny"),
            item.get("detail_price_cny_max"),
            item.get("price_cny_max"),
            item.get("price_cny_min"),
        )
        if low is not None:
            lows.append(low)
        if high is not None:
            highs.append(high)
    return (min(lows) if lows else None, max(highs) if highs else None)


def _route_price_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    priority_items = [item for item in items if item.get("route_source_group") == "优先联系"]
    return priority_items or items


def _first_numeric(*values: Any) -> float | None:
    for value in values:
        if isinstance(value, bool) or value in (None, ""):
            continue
        if isinstance(value, (int, float)):
            return float(value)
        try:
            return float(str(value).replace(",", "").strip())
        except ValueError:
            continue
    return None


def _route_price_text(low: Any, high: Any) -> str:
    if low is None and high is None:
        return "待询价"
    if low is not None and high is not None and low != high:
        return f"¥{_compact_number(low)}-{_compact_number(high)}"
    value = low if low is not None else high
    return f"¥{_compact_number(value)}"


def _compact_number(value: Any) -> str:
    if isinstance(value, (int, float)):
        return str(int(value)) if float(value).is_integer() else f"{float(value):.2f}".rstrip("0").rstrip(".")
    return str(value)


def _route_item_summary(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": item.get("title") or "未命名商品",
        "url": item.get("url"),
        "price_text": _route_item_price_text(item),
        "status": item.get("route_source_group") or item.get("status_label") or "待确认",
        "rationale": item.get("rationale") or item.get("detail_summary") or "",
    }


def _route_item_price_text(item: dict[str, Any]) -> str:
    low = _first_numeric(item.get("detail_price_cny_min"), item.get("price_cny_min"))
    high = _first_numeric(item.get("conservative_price_cny"), item.get("detail_price_cny_max"), item.get("price_cny_max"))
    return _route_price_text(low, high)


def _route_priority(route_id: Any) -> int:
    for definition in PRODUCT_ROUTE_DEFINITIONS:
        if definition["route_id"] == route_id:
            return int(definition["priority"])
    return 999


def _market_route_reference_items(candidate: dict[str, Any], limit: int = 5) -> list[dict[str, Any]]:
    tagged = candidate.get("market_structure", {}).get("tagged_products", [])
    if not isinstance(tagged, list):
        return []
    result: list[dict[str, Any]] = []
    for item in tagged:
        if not isinstance(item, dict):
            continue
        result.append(
            {
                "title": item.get("title"),
                "url": item.get("url"),
                "price_cny_min": None,
                "price_cny_max": None,
                "route_source_group": "市场样本",
                "rationale": "卖家精灵 Top 商品样本，供应链路线待 1688 进一步验证。",
            }
        )
        if len(result) >= limit:
            break
    return result


def _product_route_plain_summary(routes: list[dict[str, Any]]) -> str:
    if not routes:
        return "供应链路线还没拆开，下一步先把 1688 候选按基础款、升级款和旁支款分组。"
    dual = next((route for route in routes if route.get("route_id") == "dual_leash_waist_bag"), {})
    core = next((route for route in routes if route.get("route_id") == "core_hands_free_waist"), {})
    parts = []
    if core.get("candidate_count"):
        parts.append(f"基础腰包/腰带款有 {core.get('candidate_count')} 个候选，可做主线基准")
    if dual.get("candidate_count"):
        parts.append(f"双牵引绳 + 腰包款有 {dual.get('candidate_count')} 个候选，必须作为升级路线单独验证")
    else:
        parts.append("双牵引绳 + 腰包款目前证据不足，后续找货要主动补这个路线")
    parts.append("普通一拖二/双头绳如果没有腰包结构，只能放旁支观察，不能混进主线。")
    return "；".join(parts)


def _build_route_deep_dive_plan(
    candidate: dict[str, Any],
    product_route_matrix: list[dict[str, Any]],
    voc_package: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    if not product_route_matrix:
        return []
    plan: list[dict[str, Any]] = []
    for route in product_route_matrix:
        if not isinstance(route, dict):
            continue
        item = _route_deep_dive_item(candidate, route, voc_package)
        if item:
            plan.append(item)
    plan.sort(key=lambda item: (int(item.get("sort_priority", 999)), str(item.get("route_name") or "")))
    return plan


def _route_deep_dive_item(
    candidate: dict[str, Any],
    route: dict[str, Any],
    voc_package: dict[str, Any] | None,
) -> dict[str, Any]:
    route_id = str(route.get("route_id") or "")
    config = ROUTE_DEEP_DIVE_CONFIG.get(route_id, {})
    route_type = str(route.get("route_type") or "路线")
    candidate_count = _positive_count(route.get("candidate_count"))
    priority_count = _positive_count(route.get("priority_count"))
    representative_items = route.get("representative_items") if isinstance(route.get("representative_items"), list) else []
    competitor_asins = _route_competitor_asins(candidate, route_id)
    review_summary = _route_review_evidence_summary(voc_package, route_id)
    recommended_depth = _route_recommended_depth(route_type, candidate_count, priority_count, competitor_asins)
    current_evidence_level = _route_current_evidence_level(candidate_count, priority_count, competitor_asins, review_summary)
    data_gap = _route_data_gaps(route_type, candidate_count, competitor_asins, review_summary)
    return {
        "route_id": route_id,
        "route_name": route.get("route_name"),
        "route_type": route_type,
        "recommended_depth": recommended_depth,
        "current_evidence_level": current_evidence_level,
        "why": _route_plan_why(route, recommended_depth, competitor_asins),
        "seller_sprite_exports": list(config.get("seller_sprite_exports", [])),
        "sorftime_checks": list(config.get("sorftime_checks", [])),
        "review_voc_asin_plan": competitor_asins,
        "review_coverage": review_summary,
        "supply_chain_search_terms": list(config.get("supply_chain_search_terms", [])),
        "decision_gate": list(config.get("decision_gate", [])) or _default_route_decision_gate(route),
        "data_gaps": data_gap,
        "next_step": _route_next_step(recommended_depth, data_gap, route),
        "representative_1688_items": representative_items[:3],
        "sort_priority": _route_plan_priority(route_type, recommended_depth, route_id),
    }


def _route_recommended_depth(
    route_type: str,
    candidate_count: int,
    priority_count: int,
    competitor_asins: list[dict[str, Any]],
) -> str:
    if route_type in {"主线", "升级"}:
        if candidate_count or competitor_asins:
            return "必须路线小深挖"
        return "必须主动补数"
    if route_type == "旁支":
        return "小深挖观察" if candidate_count or competitor_asins else "低优先补数"
    if route_type == "功能升级":
        return "作为规格维度验证"
    if priority_count:
        return "小深挖观察"
    return "观察，不进主推"


def _route_current_evidence_level(
    candidate_count: int,
    priority_count: int,
    competitor_asins: list[dict[str, Any]],
    review_summary: dict[str, Any],
) -> str:
    review_count = _positive_count(review_summary.get("matched_review_count"))
    if priority_count >= 3 and len(competitor_asins) >= 2 and review_count >= 20:
        return "强"
    if candidate_count or competitor_asins or review_count:
        return "中"
    return "弱"


def _route_data_gaps(
    route_type: str,
    candidate_count: int,
    competitor_asins: list[dict[str, Any]],
    review_summary: dict[str, Any],
) -> list[str]:
    gaps: list[str] = []
    if candidate_count <= 0:
        gaps.append("1688 还没有明确候选，需要按这条路线重新搜。")
    if not competitor_asins:
        gaps.append("还缺这条路线的代表 ASIN，评价和 Sorftime 流量词无法单独判断。")
    matched_review_count = _positive_count(review_summary.get("matched_review_count"))
    matched_asins = review_summary.get("matched_asins") if isinstance(review_summary.get("matched_asins"), list) else []
    if matched_review_count < 30:
        gaps.append("评价样本还不够，至少补到 30 条以上再归纳痛点。")
    if route_type in {"主线", "升级"} and len(matched_asins) < 2:
        gaps.append("VOC 覆盖的 ASIN 太少，容易把单个竞品问题当成整条路线问题。")
    return gaps


def _route_plan_why(
    route: dict[str, Any],
    recommended_depth: str,
    competitor_asins: list[dict[str, Any]],
) -> str:
    route_name = str(route.get("route_name") or "这条路线")
    count = _positive_count(route.get("candidate_count"))
    price = str(route.get("price_text") or "待询价")
    if "必须" in recommended_depth:
        return f"{route_name}不能混在大方向里看；现在有 {count} 个 1688 候选、价格 {price}，还要单独看竞品、评价和最高规格成本。"
    if competitor_asins:
        return f"{route_name}已有可参考 ASIN，但还要确认它是主线机会还是旁支需求。"
    return f"{route_name}先保留观察，不要因为关键词相近就直接放进主推判断。"


def _route_next_step(recommended_depth: str, data_gaps: list[str], route: dict[str, Any]) -> str:
    if data_gaps:
        return data_gaps[0]
    if "规格维度" in recommended_depth:
        return "把这条路线的功能点写进基础款/升级款样品检查表。"
    if "必须" in recommended_depth:
        return "先补路线专属 ASIN、评价和 1688 定向搜索，再决定是否进完整深挖。"
    return str(route.get("decision_hint") or "先作为旁支观察，等证据变强再升级。")


def _route_plan_priority(route_type: str, recommended_depth: str, route_id: str) -> int:
    if "必须" in recommended_depth:
        return 10 + _route_priority(route_id)
    if route_type == "旁支":
        return 200 + _route_priority(route_id)
    if route_type == "功能升级":
        return 300 + _route_priority(route_id)
    return 500 + _route_priority(route_id)


def _route_competitor_asins(candidate: dict[str, Any], route_id: str, limit: int = 5) -> list[dict[str, Any]]:
    terms = _route_competitor_terms(route_id)
    groups = candidate.get("competitor_candidates", {})
    if not isinstance(groups, dict):
        return []
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for group_key, group_label in (
        ("top10", "标杆老品"),
        ("recent_winners", "近半年新品"),
        ("structure_supplement", "结构补充"),
    ):
        items = groups.get(group_key)
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "")
            if not _route_competitor_match(title, route_id, terms):
                continue
            asin = str(item.get("asin") or "").strip()
            if not asin or asin in seen:
                continue
            seen.add(asin)
            result.append(
                {
                    "asin": asin,
                    "title": title,
                    "competitor_type": group_label,
                    "price_usd": item.get("price"),
                    "monthly_units": item.get("monthly_units"),
                    "rating_count": item.get("rating_count"),
                    "reason": _route_competitor_reason(route_id, title),
                    "url": item.get("url"),
                }
            )
            if len(result) >= limit:
                return result
    return result


def _route_competitor_terms(route_id: str) -> tuple[str, ...]:
    if route_id == "core_hands_free_waist":
        return ("hands free", "waist", "belt", "pouch", "bungee", "running", "jogging")
    if route_id == "dual_leash_waist_bag":
        return ("double", "dual dog", "dual leash", "two dog", "2 dog", "multiple dogs", "waist", "belt", "pouch")
    if route_id == "multi_dog_without_waist":
        return ("dual dog", "dual leash", "two dog", "2 dog", "no-tangle", "tangle free", "splitter")
    if route_id == "safety_upgrade":
        return ("reflective", "no pull", "bungee", "padded", "handle", "tangle")
    return ()


def _route_competitor_match(title: str, route_id: str, terms: tuple[str, ...]) -> bool:
    text = title.lower()
    if route_id == "core_hands_free_waist":
        return "hands free" in text and ("waist" in text or "belt" in text or "pouch" in text)
    if route_id == "dual_leash_waist_bag":
        has_dual = any(term in text for term in ("double", "dual dog", "dual leash", "two dog", "two dogs", "2 dog", "2 dogs"))
        has_waist = any(term in text for term in ("waist", "belt", "pouch", "fanny pack", "hands free"))
        return has_dual and has_waist
    if route_id == "multi_dog_without_waist":
        has_dual = any(term in text for term in ("dual dog", "dual leash", "two dog", "two dogs", "2 dog", "2 dogs", "no-tangle", "tangle free"))
        has_waist = any(term in text for term in ("waist", "belt", "pouch", "fanny pack", "hands free"))
        return has_dual and not has_waist
    if route_id == "safety_upgrade":
        return any(term in text for term in terms)
    return bool(terms and any(term in text for term in terms))


def _route_competitor_reason(route_id: str, title: str) -> str:
    if route_id == "dual_leash_waist_bag":
        return "标题同时命中双狗/双牵引和腰部免手持结构，适合单独抓评价。"
    if route_id == "core_hands_free_waist":
        return "标题命中 hands free + waist/belt/pouch，可作为基础主线标杆。"
    if route_id == "multi_dog_without_waist":
        return "标题命中双狗/防缠绕，但没有明确腰包结构，适合旁支观察。"
    if route_id == "safety_upgrade":
        return "标题命中反光、防冲、弹力或手柄等功能词，可用于规格验证。"
    return f"标题与路线关键词匹配：{title[:80]}"


def _route_review_evidence_summary(voc_package: dict[str, Any] | None, route_id: str) -> dict[str, Any]:
    config = ROUTE_DEEP_DIVE_CONFIG.get(route_id, {})
    terms = tuple(str(term).lower() for term in config.get("review_terms", ()) if term)
    reviews = [item for item in (voc_package or {}).get("normalized_reviews", []) if isinstance(item, dict)]
    if not terms or not reviews:
        return {
            "matched_review_count": 0,
            "matched_asins": [],
            "note": "评价插件尚未覆盖这条路线，或还没有可匹配的评论文本。",
        }
    matched: list[dict[str, Any]] = []
    matched_asins: set[str] = set()
    for review in reviews:
        text = " ".join(
            str(review.get(key) or "").lower()
            for key in ("review_text", "review_text_zh", "variant", "color", "size")
        )
        if any(term in text for term in terms):
            matched.append(review)
            asin = str(review.get("asin") or "").strip()
            if asin:
                matched_asins.add(asin)
    sample_ids = [str(item.get("review_id") or "") for item in matched[:5] if item.get("review_id")]
    return {
        "matched_review_count": len(matched),
        "matched_asins": sorted(matched_asins),
        "sample_review_ids": sample_ids,
        "note": "仅按路线关键词粗筛评论，后续仍要由 Claude 结合原文判断真实痛点。",
    }


def _default_route_decision_gate(route: dict[str, Any]) -> list[str]:
    return [
        "这条路线有独立竞品、独立需求词和可承接供应商。",
        "评论痛点能被样品或供应商改款动作解决。",
        "按最高规格采购价测算后仍有合理利润空间。",
    ]


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


def _supply_chain_purchase_cost_text(signal: dict[str, Any]) -> str:
    if not isinstance(signal, dict) or not signal:
        return "待补"
    low = signal.get("purchase_price_cny_min")
    high = signal.get("purchase_price_cny_max")
    conservative = signal.get("conservative_purchase_price_cny") or high
    if low is None and high is None:
        return "待补"
    if low is not None and high is not None and low != high:
        suffix = f"（保守按 RMB {conservative}）" if conservative is not None else ""
        return f"RMB {low}-{high}{suffix}"
    value = low if low is not None else high
    suffix = f"（保守按 RMB {conservative}）" if conservative is not None and conservative != value else ""
    return f"RMB {value}{suffix}"


def _decision_missing_inputs(candidate: dict[str, Any], voc_package: dict[str, Any] | None) -> list[str]:
    missing = list(candidate.get("missing_data", []))
    if voc_package:
        missing = [item for item in missing if "评论" not in item and "VOC" not in item]
    supply_chain_signal = (candidate.get("preliminary_profit_space") or {}).get("supply_chain_signal", {})
    required_items = ["建议售价", "FBA费用", "头程费用", "入库配置费", "商标/专利复核", "合规认证复核"]
    if not isinstance(supply_chain_signal, dict) or not supply_chain_signal.get("purchase_price_cny_min"):
        required_items.insert(1, "采购价")
    for item in required_items:
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
    supply_chain_signal = (candidate.get("preliminary_profit_space") or {}).get("supply_chain_signal", {})
    has_purchase_cost = isinstance(supply_chain_signal, dict) and supply_chain_signal.get("purchase_price_cny_min") is not None
    top10_share = competition.get("top10_product_units_share")
    first_pain = _first_pain_name(voc_package)
    voc_summary = _voc_summary(voc_package)
    review_count = _positive_count(voc_summary.get("review_count"))
    voc_risk_level = "高" if first_pain else ("中" if review_count else "待补")
    if review_count:
        voc_risk_basis = _voc_risk_basis(voc_summary, first_pain)
    elif first_pain:
        voc_risk_basis = f"首要痛点：{first_pain}"
    else:
        voc_risk_basis = "未接入评论 VOC"
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
            "level": voc_risk_level,
            "basis": voc_risk_basis,
        },
        {
            "dimension": "退货风险",
            "level": str(return_risk.get("level", "待确认")),
            "basis": _return_rate_text(candidate),
        },
        {
            "dimension": "利润不确定性",
            "level": "待补",
            "basis": "FBA、头程和入库配置费仍未补齐。"
            if has_purchase_cost
            else "采购价、FBA、头程和入库配置费仍未补齐。",
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
    pain_points = voc_package.get("pain_points") or (voc_package.get("voc_analysis", {}) or {}).get("pain_points", [])
    if not pain_points:
        return ""
    return str(pain_points[0].get("name", ""))


def _voc_summary(voc_package: dict[str, Any] | None) -> dict[str, Any]:
    if not voc_package:
        return {}
    for key in ("summary", "stats"):
        value = voc_package.get(key)
        if isinstance(value, dict):
            return value
    voc_analysis = voc_package.get("voc_analysis", {})
    if isinstance(voc_analysis, dict) and isinstance(voc_analysis.get("summary"), dict):
        return voc_analysis["summary"]
    return {}


def _voc_risk_basis(summary: dict[str, Any], first_pain: str) -> str:
    parts = [f"已接入 {_fmt_number(_positive_count(summary.get('review_count')))} 条评论"]
    asin_count = _positive_count(summary.get("asin_count"))
    low_rating_count = _positive_count(summary.get("low_rating_count"))
    media_review_count = _positive_count(summary.get("media_review_count"))
    if asin_count:
        parts.append(f"覆盖 {_fmt_number(asin_count)} 个 ASIN")
    if low_rating_count:
        parts.append(f"低分 {_fmt_number(low_rating_count)} 条")
    if media_review_count:
        parts.append(f"含图/视频 {_fmt_number(media_review_count)} 条")
    suffix = f"首要痛点：{first_pain}" if first_pain else "原始评论证据已入库，待进一步归纳首要痛点"
    return "，".join(parts) + f"；{suffix}"


def _positive_count(value: Any) -> int:
    if isinstance(value, bool) or value is None:
        return 0
    if isinstance(value, (int, float)):
        return int(value) if value > 0 else 0
    if isinstance(value, str):
        normalized = value.replace(",", "").strip()
        if normalized.isdigit():
            return int(normalized)
    return 0


def _market_size_text(candidate: dict[str, Any]) -> str:
    demand = candidate.get("demand_evidence", {})
    competition = candidate.get("competition_structure", {})
    category_report = demand.get("sorftime_category_report", {})
    parts = []
    if competition.get("sample_product_count") is not None:
        parts.append(f"样本商品数 {_fmt_number(competition.get('sample_product_count'))}")
    if demand.get("market_avg_monthly_units") is not None:
        parts.append(f"市场月均销量 {_fmt_number(demand.get('market_avg_monthly_units'))}")
    if demand.get("market_avg_monthly_revenue_usd") is not None:
        parts.append(f"市场月均销售额 USD {_fmt_number(demand.get('market_avg_monthly_revenue_usd'))}")
    if competition.get("top10_avg_monthly_units") is not None:
        parts.append(f"Top10 月均销量 {_fmt_number(competition.get('top10_avg_monthly_units'))}")
    if isinstance(category_report, dict) and category_report.get("product_count"):
        parts.append(
            f"Sorftime category_report 样本 {category_report.get('product_count')} 个"
            + (f"，总月销量 {_fmt_number(category_report.get('total_monthly_units'))}" if category_report.get("total_monthly_units") is not None else "")
        )
    return "；".join(parts) if parts else "待填"


def _price_band_text(candidate: dict[str, Any]) -> str:
    demand = candidate.get("demand_evidence", {})
    profit = candidate.get("preliminary_profit_space", {})
    category_report = demand.get("sorftime_category_report", {})
    parts = []
    if profit.get("top_price_band_by_units"):
        parts.append(f"销量集中价格带 {profit.get('top_price_band_by_units')} USD")
    if profit.get("top_price_band_units_share") is not None:
        parts.append(f"该价格带销量占比 {_fmt_percent(profit.get('top_price_band_units_share'))}")
    if demand.get("market_avg_price_usd") is not None:
        parts.append(f"市场平均价 USD {_fmt_number(demand.get('market_avg_price_usd'))}")
    if isinstance(category_report, dict) and category_report.get("avg_price_usd") is not None:
        parts.append(f"Sorftime 均价 USD {_fmt_number(category_report.get('avg_price_usd'))}")
    return "；".join(parts) if parts else "待填"


def _brand_concentration_text(candidate: dict[str, Any]) -> str:
    competition = candidate.get("competition_structure", {})
    category_report = candidate.get("demand_evidence", {}).get("sorftime_category_report", {})
    top_brand = competition.get("top_brand")
    top_share = competition.get("top_brand_units_share")
    top10_share = competition.get("top10_product_units_share")
    parts = []
    if top_brand:
        parts.append(f"头部品牌 {top_brand} 销量占比 {_fmt_percent(top_share)}")
    if top10_share is not None:
        parts.append(f"Top10 商品销量占比 {_fmt_percent(top10_share)}")
    if isinstance(category_report, dict) and category_report.get("top10_units_share") is not None:
        parts.append(f"Sorftime Top10 销量占比 {_fmt_percent(category_report.get('top10_units_share'))}")
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
    category_report = candidate.get("demand_evidence", {}).get("sorftime_category_report", {})
    parts = []
    if new_listing.get("new_listing_count_6m") is not None:
        parts.append(f"近半年新品 {new_listing.get('new_listing_count_6m')} 个")
    if new_listing.get("new_listing_avg_monthly_units") is not None:
        parts.append(f"近半年新品月均销量 {_fmt_number(new_listing.get('new_listing_avg_monthly_units'))}")
    if new_listing.get("recent_6m_units_share") is not None:
        parts.append(f"近半年新品销量占比 {_fmt_percent(new_listing.get('recent_6m_units_share'))}")
    if isinstance(category_report, dict) and category_report.get("new_product_count_6m") is not None:
        parts.append(
            f"Sorftime 近半年新品 {category_report.get('new_product_count_6m')} 个"
            + (f"，销量占比 {_fmt_percent(category_report.get('new_product_units_share'))}" if category_report.get("new_product_units_share") is not None else "")
        )
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


def _join_text(*parts: Any) -> str:
    cleaned = [str(part).strip().rstrip("。；;") for part in parts if part not in (None, "")]
    return "；".join(part for part in cleaned if part)


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
