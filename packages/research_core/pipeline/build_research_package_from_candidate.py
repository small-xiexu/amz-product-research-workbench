#!/usr/bin/env python3
"""Build a minimal research package from one candidate in a candidate pool."""

from __future__ import annotations

import json
from pathlib import Path
import re
import sys
from typing import Any
import argparse

from packages.research_core.contracts import validate_research_package_chapters


PREFERRED_STATUSES = ("继续看", "试做", "观察", "先放弃")

PRODUCT_ROUTE_DEFINITIONS: tuple[dict[str, Any], ...] = (
    {
        "route_id": "base_core",
        "route_name": "基础款：核心形态 / 标准配置",
        "route_type": "主线",
        "priority": 10,
        "always_consider": True,
        "match_terms": ("基础", "标准", "basic", "standard", "classic"),
        "competitor_terms": ("basic", "standard", "classic"),
        "review_terms": ("basic", "standard", "easy to use", "fit", "quality", "基础", "标准", "好用", "质量"),
        "route_search_terms": ["{candidate_name} 基础款", "{candidate_name} 标准款"],
        "seller_sprite_exports": [
            "用主关键词导出搜索结果、市场分析 Top100 和 ABA。",
            "挑 3-5 个标准形态 ASIN 做关键词反查，看真实成交词是不是目标场景。",
        ],
        "sorftime_checks": [
            "keyword_detail：主关键词和 1-2 个标准形态长尾词。",
            "product_traffic_terms：基础款 Top3 ASIN，确认它们靠什么词拿流量。",
        ],
        "opportunity": "先建立主线基准，看这个品类最常见、最容易量产的标准形态是否值得进入样品验证。",
        "risks": "标准款往往同质化强，不能只看低价；要确认差评是否集中在质量、尺寸、稳定性或使用体验。",
        "validation_actions": [
            "补标准形态代表 ASIN、关键词反查和评论 VOC，确认基础需求是否真实存在。",
            "把最容易差评的基础体验转成后续产品验证点：尺寸、稳定性、耐用性和使用门槛。",
        ],
        "decision_gate": [
            "标准形态能解决核心使用痛点。",
            "主关键词与目标形态一致，不是被泛词或混池词带偏。",
        ],
        "decision_hint": "作为主推基准款观察，但必须和升级款/场景款一起比较需求、评论门槛和差异化。",
    },
    {
        "route_id": "upgraded_core",
        "route_name": "升级款：更高客单价 / 更强功能配置",
        "route_type": "升级",
        "priority": 20,
        "always_consider": True,
        "match_terms": (
            "升级",
            "高配",
            "加强",
            "加厚",
            "重型",
            "专业",
            "premium",
            "upgraded",
            "heavy duty",
            "reinforced",
            "pro",
        ),
        "competitor_terms": ("premium", "upgraded", "heavy duty", "reinforced", "pro"),
        "review_terms": ("premium", "upgraded", "durable", "sturdy", "heavy duty", "加强", "耐用", "结实"),
        "route_search_terms": ["{candidate_name} 升级款", "{candidate_name} 高配", "{candidate_name} 加强"],
        "seller_sprite_exports": [
            "用升级/高配/专业款长尾词补搜索结果和关键词反查。",
            "单独拉升级款竞品 ASIN，不和标准款混在同一批 VOC 里判断。",
        ],
        "sorftime_checks": [
            "keyword_detail：升级款/高配款长尾词。",
            "product_traffic_terms：升级款代表 ASIN，确认是否有独立成交流量。",
            "competitor_product_keywords：看升级款是否避开纯低价竞争。",
        ],
        "opportunity": "升级款通常更适合做差异化和客单价，需要单独看是否真的有需求，而不是只把它当标题或图片里的一个规格。",
        "risks": "升级配置如果只是标题词或图片装饰，样品不达标会直接变成差评；成本也容易被低估。",
        "validation_actions": [
            "把标准款和升级款分别拉代表 ASIN，看升级点是否有独立需求和转化词。",
            "用评论证据单独验证升级点：强度、材质、结构、配件和实际使用差异。",
        ],
        "decision_gate": [
            "升级点有独立竞品、独立需求词或明确 VOC 痛点承接。",
            "升级路线有独立关键词、竞品或评论痛点承接。",
            "升级后价格带仍有销量和低评论切入口。",
        ],
        "decision_hint": "不要混在标准款里看；作为升级路线单独算成本、售价和样品测试。",
    },
    {
        "route_id": "scenario_specialized",
        "route_name": "场景款：明确使用场景 / 人群",
        "route_type": "场景",
        "priority": 30,
        "always_consider": True,
        "match_terms": (
            "户外",
            "旅行",
            "车载",
            "厨房",
            "浴室",
            "儿童",
            "宠物",
            "露营",
            "办公",
            "outdoor",
            "travel",
            "car",
            "shower",
            "kitchen",
            "camping",
            "office",
        ),
        "competitor_terms": ("outdoor", "travel", "car", "shower", "kitchen", "camping", "office"),
        "review_terms": ("outdoor", "travel", "car", "shower", "kitchen", "场景", "户外", "旅行", "汽车", "浴室"),
        "route_search_terms": ["{candidate_name} 场景款", "{candidate_name} 户外", "{candidate_name} 家用"],
        "seller_sprite_exports": [
            "按场景词补搜索结果，不和泛品类词混在一起看。",
            "为每个高潜场景挑 2-3 个代表 ASIN 做关键词反查。",
        ],
        "sorftime_checks": [
            "keyword_detail：场景词 + 品类词。",
            "product_traffic_terms：场景款代表 ASIN，确认它是否真靠场景词成交。",
        ],
        "opportunity": "场景款能避开纯泛词竞争，适合寻找更清晰的人群、用途和页面卖点。",
        "risks": "场景不清会把不同需求混在一起，导致 VOC、关键词和竞品判断互相拉偏。",
        "validation_actions": [
            "确认这个场景有独立关键词、独立竞品和独立评论痛点。",
            "样品要按真实使用场景测试，而不是只看标题是否写了场景词。",
        ],
        "decision_gate": [
            "场景词有搜索量或竞品流量支撑。",
            "评论证据能证明该场景存在未满足需求。",
            "页面和评论证据能解释该场景为什么需要不同结构、材质或包装方案。",
        ],
        "decision_hint": "适合作为副主线观察；若证据强，可升级为主推路线。",
    },
    {
        "route_id": "bundle_or_set",
        "route_name": "组合/套装款：多件套 / 可替换配件",
        "route_type": "组合",
        "priority": 40,
        "always_consider": True,
        "match_terms": (
            "套装",
            "组合",
            "多件套",
            "两件套",
            "三件套",
            "替换",
            "配件",
            "set",
            "kit",
            "combo",
            "bundle",
            "replacement",
            "2 in 1",
            "3 in 1",
            "二合一",
            "三合一",
        ),
        "competitor_terms": ("set", "kit", "combo", "bundle", "replacement", "2 in 1", "3 in 1"),
        "review_terms": ("set", "kit", "replacement", "parts", "bundle", "套装", "替换", "配件", "组合"),
        "route_search_terms": ["{candidate_name} 套装", "{candidate_name} 组合", "{candidate_name} 替换件"],
        "seller_sprite_exports": [
            "用 kit / set / replacement 等组合词补搜索结果和关键词反查。",
            "把套装款和单品款分开看价格带、评论门槛和退货风险。",
        ],
        "sorftime_checks": [
            "keyword_detail：套装/组合/替换件长尾词。",
            "product_traffic_terms：套装代表 ASIN，确认套装是否带来独立流量。",
        ],
        "opportunity": "组合/套装有机会提高客单价或降低同质化，但必须确认买家是真的需要整套，而不是随便打包。",
        "risks": "套装会增加重量、缺件、包装和退货风险；不能只看套装看起来更丰富。",
        "validation_actions": [
            "单独看套装款代表 ASIN 的价格带、评论门槛和关键词入口。",
            "从评论里确认缺件、包装保护、替换件兼容性和说明书是否是高频风险。",
        ],
        "decision_gate": [
            "套装有独立需求词或评论痛点支撑。",
            "套装价格带有销量，并且低评论样本不是偶然个案。",
            "评论和竞品证据能证明整套配件有真实需求。",
        ],
        "decision_hint": "不要只因看起来更丰富就选套装；先把成本和缺件风险算清。",
    },
    {
        "route_id": "feature_material_upgrade",
        "route_name": "功能/材质升级：安全、耐用、专业化卖点",
        "route_type": "功能升级",
        "priority": 50,
        "always_consider": True,
        "match_terms": (
            "防滑",
            "防水",
            "防摔",
            "反光",
            "可伸缩",
            "折叠",
            "旋转",
            "加固",
            "耐用",
            "铝合金",
            "不锈钢",
            "硅胶",
            "微纤维",
            "waterproof",
            "non slip",
            "reflective",
            "foldable",
            "extendable",
            "telescopic",
            "rotating",
            "reinforced",
            "stainless",
            "microfiber",
        ),
        "competitor_terms": ("waterproof", "reflective", "foldable", "extendable", "reinforced", "stainless", "microfiber"),
        "review_terms": ("durable", "sturdy", "waterproof", "slip", "break", "耐用", "结实", "防滑", "断", "坏"),
        "route_search_terms": ["{candidate_name} 加强", "{candidate_name} 防滑", "{candidate_name} 耐用"],
        "seller_sprite_exports": [
            "不用一开始单独拉大盘，先放进主线/升级款竞品反查里看功能词。",
            "若功能词有明显流量，再单独补搜索结果和关键词反查。",
        ],
        "sorftime_checks": [
            "keyword_extends：查功能/材质长尾词。",
            "similar_product_feature：选定主路线后再看热销品共有功能点。",
        ],
        "opportunity": "功能/材质升级能转成页面卖点，也能解释为什么比低价款贵。",
        "risks": "这些升级如果只停留在标题词，样品不达标反而更容易被差评打回来。",
        "validation_actions": [
            "把功能/材质升级写成可验证规格，并回到代表 ASIN、评论和页面卖点核对。",
            "按差评痛点设计后续验证问题，确认升级点不是标题装饰词。",
        ],
        "decision_gate": [
            "功能升级能承接真实 VOC 痛点。",
            "升级点有图片/视频/样品证据，而不是标题词。",
            "升级后成本、重量和售后风险可控。",
        ],
        "decision_hint": "适合作为基础/升级路线的必验卖点，证据强时再独立成路线。",
    },
    {
        "route_id": "adjacent_or_watch",
        "route_name": "旁支观察：相近形态 / 混池候选",
        "route_type": "观察",
        "priority": 90,
        "match_terms": ("旁支", "混池", "相近", "待确认", "不明确", "其他", "adjacent", "similar"),
        "competitor_terms": (),
        "review_terms": (),
        "route_search_terms": ["{candidate_name} 相似款", "{candidate_name} 替代款"],
        "seller_sprite_exports": [
            "只在主线/升级路线证据不足时补旁支数据。",
            "旁支候选必须单独标记，不能混进主推款评分。",
        ],
        "sorftime_checks": [
            "keyword_extends：确认旁支词是否只是混池，还是有独立需求。",
        ],
        "opportunity": "可能有可借鉴结构、低价供给或备用方向，可留作观察。",
        "risks": "相近不等于目标产品，混进去会拉偏 VOC、关键词和竞品判断。",
        "validation_actions": [
            "打开详情确认它和目标形态的关键差异。",
            "证据不足时只留观察，不进入主推评分。",
        ],
        "decision_gate": [
            "确认它不是主线/升级路线的低质量混池。",
            "若要升级为主线，必须补独立需求、关键词、竞品和 VOC 证据。",
        ],
        "decision_hint": "先观察，不抢主线资源；证据变强后再升级。",
    },
)

def build_research_package(
    candidate_pool: dict[str, Any],
    candidate_id: str | None,
    voc_package: dict[str, Any] | None = None,
    route_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from packages.research_core.pipeline.build_research_data_packet import build_research_data_packet

    data_packet = build_research_data_packet(candidate_pool, candidate_id, voc_package, route_profile)
    candidate = data_packet["normalized_tables"]["candidate"]
    competitor_candidates = candidate.get("competitor_candidates", {})
    status = candidate.get("status", "观察")
    voc_analysis = _build_voc_analysis(voc_package)
    effective_voc_package = _with_effective_voc_findings(voc_package, voc_analysis)
    voc_opportunities = _build_voc_opportunities(voc_package, candidate.get("candidate_id"))
    voc_summary_line = _voc_summary_line(voc_package)
    entry_barriers = _build_entry_barriers(candidate)
    go_nogo_scorecard = _build_go_nogo_scorecard(candidate, entry_barriers, effective_voc_package)
    decision_review = _build_decision_review(candidate, voc_package, go_nogo_scorecard)
    product_route_matrix = _build_product_route_matrix(candidate)
    route_deep_dive_plan = _build_route_deep_dive_plan(candidate, product_route_matrix, voc_package)
    ai_analysis = _build_ai_analysis_brief(
        candidate,
        voc_package,
        go_nogo_scorecard,
        product_route_matrix,
        route_deep_dive_plan,
    )

    package = {
        **data_packet,
        "voc_analysis": voc_analysis,
        "competitor_selection_logic": _build_competitor_selection_logic(candidate),
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
        "competitor_deep_dive": _build_competitor_deep_dive(
            competitor_candidates,
            candidate.get("demand_evidence", {}).get("sorftime_traffic_terms", {}) if isinstance(candidate.get("demand_evidence"), dict) else {},
        ),
        "report_summary": {
            "bullets": [
                candidate.get("reason", "待补"),
                f"当前状态：{status}",
                "正式结论聚焦市场机会：需要补齐小类、关键词、竞品和评论证据后再决定是否继续深挖。",
                _market_boundary_summary_line(candidate),
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
    validate_research_package_chapters(package)
    return package


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
    voc_summary = _voc_summary(voc_package)
    data_source_scope = [
        "卖家精灵：先看市场大不大、头部强不强、价格好不好打",
        "Sorftime：看实时词和竞品流量，别只信一份历史表",
        "评价插件：看买家到底在吐槽什么",
        "路线矩阵：看大类、小类、关键词和代表 ASIN 是否指向同一个机会",
    ]
    gating = go_nogo_scorecard.get("gating_reasons") if isinstance(go_nogo_scorecard.get("gating_reasons"), list) else []
    review_count = _positive_count(voc_summary.get("review_count"))
    low_rating_count = _positive_count(voc_summary.get("low_rating_count"))
    asin_count = _positive_count(voc_summary.get("asin_count"))
    top_keyword = _top_sorftime_keyword_summary(candidate)
    route_summary = _product_route_plain_summary(product_route_matrix or [])

    return {
        "persona": "资深亚马逊运营专家",
        "role_scope": "先说人话结论，再看证据：这块就是先告诉你能不能继续、还差什么、卡在哪。",
        "data_source_scope": data_source_scope,
        "decision_principle": "数据越多越好，但不是拿来堆字。本报告只判断市场机会和继续研究优先级，不输出采购或上架结论。",
        "thesis": {
            "title": _expert_thesis_title(go_nogo_scorecard),
            "body": _expert_thesis_body(review_count, product_route_matrix or [], gating),
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
                "label": "小类和竞品是否对齐",
                "title": "先确认市场边界，再谈产品方案",
                "body": _route_evidence_plain_summary(product_route_matrix or []),
            },
            {
                "label": "现在卡哪",
                "title": "现在还差几块拼图",
                "body": _gating_plain_summary(gating),
            },
        ],
        "product_spec_actions": _product_spec_actions(product_route_matrix),
        "market_validation_actions": [
            "先把主线、升级、场景和套装路线分开看，不要混在一个泛词里判断。",
            "每条保留路线至少补 2-3 个代表 ASIN、关键词反查和评论样本。",
            "对混池词单独标记排除原因，避免把旁支销量误当主线机会。",
            "把评论痛点转成后续产品验证问题，但本阶段不做后置落地判断。",
        ],
        "next_operator_actions": [
            "补齐目标小类 Top100 明细，确认大类和小类不是混池。",
            "对主推路线补关键词反查和代表 ASIN 流量词。",
            "按路线抓评论 VOC，确认痛点是否可转成产品验证问题。",
        ],
        "product_route_matrix": product_route_matrix or [],
        "route_deep_dive_plan": route_deep_dive_plan or [],
    }


def _expert_thesis_title(go_nogo_scorecard: dict[str, Any]) -> str:
    decision = str(go_nogo_scorecard.get("decision") or "WAIT").upper()
    if decision == "GO":
        return "市场机会可以继续深挖，但不是采购或上架结论。"
    if decision == "NO-GO":
        return "暂不建议立项，先止损或换方向。"
    return "继续看，但不要直接立项。"


def _expert_thesis_body(review_count: int, routes: list[dict[str, Any]], gating: list[Any]) -> str:
    evidence = [
        f"评价样本 {review_count} 条" if review_count else "",
        f"路线矩阵 {len(routes)} 条" if routes else "",
    ]
    gating_text = "；".join(map(str, gating[:3])) if gating else "大类、小类、关键词、竞品和 VOC 证据需要继续交叉验证"
    return _join_text(
        "我的判断是：可以继续看，但结论只停在市场机会层。",
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


def _route_evidence_plain_summary(routes: list[dict[str, Any]]) -> str:
    if not routes:
        return "路线矩阵还没形成，下一步先按大类、小类、关键词和代表 ASIN 拆路线。"
    strong = [route for route in routes if _positive_count(route.get("competitor_count")) or _positive_count(route.get("candidate_count"))]
    return f"已拆出 {len(routes)} 条路线，其中 {len(strong)} 条有代表竞品或市场样本；下一步按路线补关键词和 VOC，而不是用一个泛词判断全部市场。"


def _gating_plain_summary(gating: list[Any]) -> str:
    if not gating:
        return "继续交叉验证小类、关键词、竞品和 VOC，再决定是否进入更深一轮市场研究。"
    friendly = []
    for item in gating[:4]:
        text = str(item)
        friendly.append(text)
    return "；".join(friendly) + "。这些没补齐前，最多是继续看，不是进入采购或上架判断。"


def _product_spec_actions(product_route_matrix: list[dict[str, Any]] | None) -> list[str]:
    routes = product_route_matrix or []
    actions: list[str] = []
    for route in routes:
        if not isinstance(route, dict):
            continue
        route_name = str(route.get("route_name") or "这条路线")
        validation_actions = route.get("validation_actions") if isinstance(route.get("validation_actions"), list) else []
        if validation_actions:
            actions.append(f"{route_name}：{validation_actions[0]}")
        elif route.get("decision_hint"):
            actions.append(f"{route_name}：{route.get('decision_hint')}")
        if len(actions) >= 4:
            break
    actions.extend(
        [
            "把差评里的问题写成后续验证清单，逐条确认是否值得转成产品规格。",
            "页面卖点必须对应样品证据，别只把标题词堆上去。",
            "基础款和升级款分开测，别用最低配样品替高配路线做判断。",
        ]
    )
    return _dedupe_strings(actions)[:6]


def _build_product_route_matrix(candidate: dict[str, Any]) -> list[dict[str, Any]]:
    review: dict[str, Any] = {}
    profile = _route_profile(candidate, review)
    context = _build_product_context(candidate, review, profile)
    definitions = [
        _route_definition_with_context(definition, context, profile, candidate)
        for definition in PRODUCT_ROUTE_DEFINITIONS
    ]
    route_buckets = {definition["route_id"]: [] for definition in PRODUCT_ROUTE_DEFINITIONS}
    for group_key, group_label in (("priority_candidates", "优先联系"), ("watchlist_candidates", "观察待核")):
        items = review.get(group_key)
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            item_with_group = {**item, "route_source_group": group_label}
            for route_id in _classify_market_route(item_with_group, definitions):
                route_buckets.setdefault(route_id, []).append(item_with_group)

    if not any(route_buckets.values()):
        for item in _market_route_reference_items(candidate):
            item_route_ids = _classify_market_route(item, definitions)
            for route_id in item_route_ids:
                route_buckets.setdefault(route_id, []).append(item)

    routes: list[dict[str, Any]] = []
    for definition in definitions:
        items = route_buckets.get(definition["route_id"], [])
        if not items and not definition.get("always_consider"):
            continue
        price_min, price_max = _route_price_range(_route_price_items(items))
        priority_count = sum(1 for item in items if item.get("route_source_group") == "优先联系")
        watchlist_count = sum(1 for item in items if item.get("route_source_group") == "观察待核")
        route_keywords = _route_keyword_hints(candidate, definition)
        routes.append(
            {
                "route_id": definition["route_id"],
                "route_name": definition["route_name"],
                "route_type": definition["route_type"],
                "route_profile": context.get("profile_id", "runtime"),
                "product_context": context,
                "route_keywords": route_keywords,
                "always_consider": bool(definition.get("always_consider")),
                "match_terms": list(definition.get("match_terms", [])),
                "require_any_terms": list(definition.get("require_any_terms", [])),
                "competitor_terms": list(definition.get("competitor_terms", [])),
                "review_terms": list(definition.get("review_terms", [])),
                "seller_sprite_exports": list(definition.get("seller_sprite_exports", [])),
                "sorftime_checks": list(definition.get("sorftime_checks", [])),
                "route_search_terms": list(definition.get("route_search_terms", [])),
                "decision_gate": list(definition.get("decision_gate", [])),
                "candidate_count": len(items),
                "competitor_count": len(items),
                "priority_count": priority_count,
                "watchlist_count": watchlist_count,
                "price_usd_min": price_min,
                "price_usd_max": price_max,
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


def _route_profile(candidate: dict[str, Any], review: dict[str, Any], route_signal: dict[str, Any] | None = None) -> dict[str, Any]:
    profile_sources = [
        candidate.get("product_route_profile"),
        candidate.get("route_profile"),
        (candidate.get("product_context") or {}).get("route_profile") if isinstance(candidate.get("product_context"), dict) else None,
        (route_signal or {}).get("product_route_profile") if isinstance(route_signal, dict) else None,
        review.get("product_route_profile") if isinstance(review, dict) else None,
    ]
    for profile in profile_sources:
        if isinstance(profile, dict):
            return profile
    return {"profile_id": "runtime_inferred", "route_overrides": {}}


def _route_definition_with_context(
    definition: dict[str, Any],
    context: dict[str, Any],
    profile: dict[str, Any],
    candidate: dict[str, Any],
) -> dict[str, Any]:
    route_id = str(definition.get("route_id") or "")
    overrides = profile.get("route_overrides") if isinstance(profile.get("route_overrides"), dict) else {}
    override = overrides.get(route_id) if isinstance(overrides.get(route_id), dict) else {}
    merged: dict[str, Any] = dict(definition)
    inferred = _inferred_route_overrides(route_id, context)
    for key, value in inferred.items():
        merged[key] = value
    for key, value in override.items():
        if key in {"match_terms", "require_any_terms", "competitor_terms", "review_terms", "route_search_terms"}:
            merged[key] = _dedupe_strings([str(item) for item in value]) if isinstance(value, (list, tuple)) else value
        else:
            merged[key] = value
    merged["route_search_terms"] = _format_route_terms(merged.get("route_search_terms", []), candidate)
    return merged


def _route_definition_index(route_id: str) -> int:
    for index, definition in enumerate(PRODUCT_ROUTE_DEFINITIONS):
        if definition.get("route_id") == route_id:
            return index
    return 0


def _build_product_context(
    candidate: dict[str, Any],
    review: dict[str, Any],
    profile: dict[str, Any],
) -> dict[str, Any]:
    explicit = candidate.get("product_context") if isinstance(candidate.get("product_context"), dict) else {}
    demand = candidate.get("demand_evidence", {}) if isinstance(candidate.get("demand_evidence"), dict) else {}
    core_terms = _context_terms_from_values(
        explicit.get("core_terms"),
        explicit.get("product_terms"),
        candidate.get("name"),
        demand.get("top_keyword"),
        demand.get("aba_top_search_term"),
    )
    route_terms = {
        "base_core": _context_terms_from_values(explicit.get("base_terms"), explicit.get("standard_terms")),
        "upgraded_core": _context_terms_from_values(explicit.get("upgrade_terms"), explicit.get("premium_terms")),
        "scenario_specialized": _context_terms_from_values(explicit.get("scenario_terms"), explicit.get("audience_terms")),
        "bundle_or_set": _context_terms_from_values(explicit.get("bundle_terms"), explicit.get("set_terms")),
        "feature_material_upgrade": _context_terms_from_values(explicit.get("feature_terms"), explicit.get("material_terms")),
        "adjacent_or_watch": _context_terms_from_values(explicit.get("adjacent_terms"), explicit.get("exclude_terms")),
    }
    for item in _route_source_items(candidate, review):
        text = _route_item_text(item)
        for route_id in route_terms:
            terms = _extract_route_terms_from_text(route_id, text)
            if terms:
                route_terms[route_id].extend(terms)
        title = item.get("title")
        if title:
            core_terms.extend(_meaningful_title_terms(str(title), limit=4))
    for item in _competitor_source_items(candidate):
        title = str(item.get("title") or "")
        for route_id in route_terms:
            terms = _extract_route_terms_from_text(route_id, title.lower())
            if terms:
                route_terms[route_id].extend(terms)
    profile_terms = profile.get("route_terms") if isinstance(profile.get("route_terms"), dict) else {}
    for route_id, terms in profile_terms.items():
        route_terms.setdefault(str(route_id), []).extend(_context_terms_from_values(terms))
    core_terms = _dedupe_strings([term for term in core_terms if _is_meaningful_context_term(term)])[:8]
    if not core_terms:
        core_terms = ["目标产品"]
    clean_route_terms = {
        route_id: _dedupe_strings([term for term in terms if _is_meaningful_context_term(term)])[:8]
        for route_id, terms in route_terms.items()
    }
    return {
        "profile_id": str(profile.get("profile_id") or "runtime_inferred"),
        "core_terms": core_terms,
        "route_terms": clean_route_terms,
        "exclude_terms": _context_terms_from_values(explicit.get("exclude_terms"), profile.get("exclude_terms")),
    }


def _inferred_route_overrides(route_id: str, context: dict[str, Any]) -> dict[str, Any]:
    core_terms = _context_route_terms(context, "core_terms")
    route_terms = _context_route_terms(context, route_id)
    evidence_terms = _dedupe_strings(route_terms or (core_terms if route_id == "base_core" else []))
    if not core_terms:
        core_terms = ["目标产品"]
    title = _route_name_from_context(route_id, core_terms, route_terms)
    search_terms = _route_search_terms(route_id, core_terms, route_terms)
    checks = _route_sorftime_checks(route_id, core_terms, route_terms)
    exports = _route_seller_sprite_exports(route_id, core_terms, route_terms)
    result: dict[str, Any] = {
        "route_name": title,
        "match_terms": _dedupe_strings(list(PRODUCT_ROUTE_DEFINITIONS[_route_definition_index(route_id)].get("match_terms", ())) + route_terms),
        "competitor_terms": evidence_terms,
        "review_terms": evidence_terms,
        "route_search_terms": search_terms,
        "seller_sprite_exports": exports,
        "sorftime_checks": checks,
    }
    return result


def _context_terms_from_values(*values: Any) -> list[str]:
    terms: list[str] = []
    for value in values:
        if value in (None, ""):
            continue
        if isinstance(value, dict):
            terms.extend(_context_terms_from_values(*value.values()))
            continue
        if isinstance(value, (list, tuple, set)):
            terms.extend(_context_terms_from_values(*value))
            continue
        text = re.sub(r"\s+", " ", str(value)).strip()
        if not text:
            continue
        parts = re.split(r"[,，;；、\n\t|]+", text)
        for part in parts:
            clean = part.strip(" -_/")
            if clean:
                terms.append(clean)
    return _dedupe_strings(terms)


def _route_source_items(candidate: dict[str, Any], review: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for key in ("priority_candidates", "watchlist_candidates", "visual_review_queue"):
        value = review.get(key)
        if isinstance(value, list):
            items.extend(item for item in value if isinstance(item, dict))
    return items[:30]


def _competitor_source_items(candidate: dict[str, Any]) -> list[dict[str, Any]]:
    groups = candidate.get("competitor_candidates", {})
    if not isinstance(groups, dict):
        return []
    items: list[dict[str, Any]] = []
    for key in ("top10", "recent_winners", "structure_supplement"):
        value = groups.get(key)
        if isinstance(value, list):
            items.extend(item for item in value if isinstance(item, dict))
    return items[:30]


def _extract_route_terms_from_text(route_id: str, text: str) -> list[str]:
    definition = PRODUCT_ROUTE_DEFINITIONS[_route_definition_index(route_id)]
    terms = []
    for term in definition.get("match_terms", ()):
        clean = str(term).strip()
        if clean and clean.lower() in text.lower():
            terms.append(clean)
    return _dedupe_strings(terms)


def _meaningful_title_terms(text: str, limit: int = 4) -> list[str]:
    raw_parts = re.split(r"[,，;；、\n\t|()（）\\[\\]{}]+", text)
    parts: list[str] = []
    stopwords = {
        "new",
        "hot",
        "sale",
        "amazon",
        "cross",
        "border",
        "factory",
        "wholesale",
        "for",
        "and",
        "with",
        "the",
        "a",
        "an",
        "新品",
        "跨境",
        "亚马逊",
        "批发",
        "厂家",
        "现货",
    }
    for raw in raw_parts:
        chunk = re.sub(r"\s+", " ", raw).strip(" -_/")
        if not chunk:
            continue
        tokens = chunk.split()
        if len(tokens) > 1:
            phrase = " ".join(token for token in tokens if token.lower() not in stopwords)
            if _is_meaningful_context_term(phrase):
                parts.append(phrase)
            continue
        if chunk.lower() not in stopwords and _is_meaningful_context_term(chunk):
            parts.append(chunk)
    return _dedupe_strings(parts)[:limit]


def _is_meaningful_context_term(term: Any) -> bool:
    text = re.sub(r"\s+", " ", str(term or "")).strip()
    if len(text) < 2 or len(text) > 80:
        return False
    if re.fullmatch(r"[\d\s._-]+", text):
        return False
    return True


def _context_route_terms(context: dict[str, Any], route_id: str) -> list[str]:
    if route_id == "core_terms":
        value = context.get("core_terms")
        return list(value) if isinstance(value, list) else []
    routes = context.get("route_terms")
    if isinstance(routes, dict):
        value = routes.get(route_id)
        return list(value) if isinstance(value, list) else []
    return []


def _route_name_from_context(route_id: str, core_terms: list[str], route_terms: list[str]) -> str:
    term_text = _short_route_term_text(route_terms or core_terms[:1])
    if route_id == "base_core":
        return f"基础款：{term_text} / 标准配置"
    if route_id == "upgraded_core":
        return f"升级款：{term_text or '更高客单价 / 更强功能配置'}"
    if route_id == "scenario_specialized":
        return f"场景款：{term_text or '明确使用场景 / 人群'}"
    if route_id == "bundle_or_set":
        return f"组合/套装款：{term_text or '多件套 / 可替换配件'}"
    if route_id == "feature_material_upgrade":
        return f"功能/材质升级：{term_text or '安全、耐用、专业化卖点'}"
    if route_id == "adjacent_or_watch":
        return f"旁支观察：{term_text or '相近形态 / 混池候选'}"
    return term_text or str(route_id)


def _short_route_term_text(terms: list[str]) -> str:
    clean = [str(term).strip() for term in terms if _is_meaningful_context_term(term)]
    return " + ".join(clean[:3])


def _route_search_terms(route_id: str, core_terms: list[str], route_terms: list[str]) -> list[str]:
    suffix = {
        "base_core": "基础款",
        "upgraded_core": "升级款",
        "scenario_specialized": "场景款",
        "bundle_or_set": "套装",
        "feature_material_upgrade": "加强",
        "adjacent_or_watch": "相似款",
    }.get(route_id, "")
    terms: list[str] = []
    for core in core_terms[:3]:
        if suffix:
            terms.append(f"{core} {suffix}")
        for route_term in route_terms[:3]:
            if route_term.lower() not in core.lower():
                terms.append(f"{core} {route_term}")
    if not terms:
        terms = [f"{core_terms[0]} {suffix}".strip()]
    return _dedupe_strings(terms)[:6]


def _route_seller_sprite_exports(route_id: str, core_terms: list[str], route_terms: list[str]) -> list[str]:
    route_label = _route_name_from_context(route_id, core_terms, route_terms)
    keyword_hint = " / ".join(_dedupe_strings(route_terms[:2] + core_terms[:2])) or "主关键词"
    return [
        f"用 {keyword_hint} 导出搜索结果、市场分析 Top100 和 ABA。",
        f"为「{route_label}」挑 3-5 个代表 ASIN 做关键词反查，不和其它路线混在同一批判断。",
    ]


def _route_sorftime_checks(route_id: str, core_terms: list[str], route_terms: list[str]) -> list[str]:
    keyword_hint = "、".join(_dedupe_strings(route_terms[:2] + core_terms[:2])) or "主关键词"
    return [
        f"keyword_detail：{keyword_hint}。",
        "product_traffic_terms：该路线代表 ASIN，确认真实成交流量词。",
        "competitor_product_keywords：看这条路线是否避开泛词低价竞争。",
    ]


def _format_route_terms(terms: Any, candidate: dict[str, Any]) -> list[str]:
    if not isinstance(terms, (list, tuple)):
        return []
    name = str(candidate.get("name") or "目标产品").strip() or "目标产品"
    clean_name = re.sub(r"[_\\-]+", " ", name).strip()
    result = []
    for term in terms:
        text = str(term).strip()
        if not text:
            continue
        result.append(text.replace("{candidate_name}", clean_name))
    return _dedupe_strings(result)


def _route_keyword_hints(candidate: dict[str, Any], definition: dict[str, Any]) -> list[str]:
    hints: list[str] = []
    demand = candidate.get("demand_evidence", {}) if isinstance(candidate.get("demand_evidence"), dict) else {}
    for value in (
        demand.get("top_keyword"),
        demand.get("aba_top_search_term"),
        candidate.get("name"),
    ):
        if value:
            hints.append(str(value))
    for term in definition.get("route_search_terms", [])[:2]:
        hints.append(str(term))
    return _dedupe_strings(hints)[:5]


def _classify_market_route(item: dict[str, Any], definitions: list[dict[str, Any]]) -> list[str]:
    text = _route_item_text(item)
    routes: list[str] = []
    for definition in definitions:
        route_id = str(definition.get("route_id") or "")
        if not route_id:
            continue
        terms = tuple(str(term).lower() for term in definition.get("match_terms", ()) if term)
        if terms and _contains_any(text, terms) and _route_requirements_met(text, definition):
            routes.append(route_id)
    if routes:
        return _dedupe_strings(routes)
    if _looks_like_core_candidate(text):
        routes.append("base_core")
    else:
        routes.append("adjacent_or_watch")
    return _dedupe_strings(routes)


def _route_requirements_met(text: str, definition: dict[str, Any]) -> bool:
    required = tuple(str(term).lower() for term in definition.get("require_any_terms", ()) if term)
    if not required:
        return True
    return _contains_any(text, required)


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
    for key in ("sku_texts", "sku_options", "risk_notes"):
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


def _contains_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(needle.lower() in text for needle in needles)


def _looks_like_core_candidate(text: str) -> bool:
    if not text.strip():
        return False
    adjacent_terms = ("配件", "替换", "accessory", "replacement")
    if _contains_any(text, adjacent_terms):
        return False
    return True


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
            item.get("price_usd"),
            item.get("price"),
        )
        high = _first_numeric(
            item.get("price_usd"),
            item.get("price"),
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
        return "价格待补"
    if low is not None and high is not None and low != high:
        return f"¥{_compact_number(low)}-{_compact_number(high)}"
    value = low if low is not None else high
    return f"${_compact_number(value)}"


def _compact_number(value: Any) -> str:
    if isinstance(value, (int, float)):
        return str(int(value)) if float(value).is_integer() else f"{float(value):.2f}".rstrip("0").rstrip(".")
    return str(value)


def _route_item_summary(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "asin": item.get("asin"),
        "title": item.get("title") or "未命名商品",
        "url": item.get("url"),
        "price_text": _route_item_price_text(item),
        "status": item.get("route_source_group") or item.get("status_label") or "待确认",
        "rationale": item.get("rationale") or item.get("detail_summary") or "",
    }


def _route_item_price_text(item: dict[str, Any]) -> str:
    low = _first_numeric(item.get("price_usd"), item.get("price"))
    high = _first_numeric(item.get("price_usd"), item.get("price"))
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
    anchors = _market_anchor_terms(candidate)
    result: list[dict[str, Any]] = []
    for item in tagged:
        if not isinstance(item, dict):
            continue
        relevance = _competitor_market_relevance(item, anchors)
        if relevance["status"] == "剔除":
            continue
        result.append(
            {
                "title": item.get("title"),
                "url": item.get("url"),
                "route_source_group": "市场样本",
                "price_usd": item.get("price_usd") or item.get("price"),
                "asin": item.get("asin"),
                "market_boundary_status": relevance["status"],
                "rationale": "卖家精灵 Top 商品样本，用于路线级市场证据验证。"
                + (f" 边界状态：{relevance['status']}，{relevance['reason']}" if relevance["status"] != "相关" else ""),
            }
        )
        if len(result) >= limit:
            break
    return result


def _product_route_plain_summary(routes: list[dict[str, Any]]) -> str:
    if not routes:
        return "产品路线还没拆开，下一步先按基础款、升级款、场景款、组合/套装和旁支观察分组。"
    parts = []
    for route in routes[:4]:
        name = str(route.get("route_name") or "未命名路线")
        count = _positive_count(route.get("candidate_count"))
        route_type = str(route.get("route_type") or "路线")
        if count:
            parts.append(f"{name}有 {count} 个候选，属于{route_type}，要单独补证据")
        elif route.get("always_consider"):
            parts.append(f"{name}暂时证据不足，但仍要主动补数，避免漏掉潜在路线")
    if not parts:
        parts.append("目前只有旁支或待确认候选，先补路线标签、关键词和代表竞品证据。")
    parts.append("不要只盯一个看起来最像的商品，先逐路线小深挖再决定主推。")
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
    route_type = str(route.get("route_type") or "路线")
    candidate_count = _positive_count(route.get("candidate_count"))
    priority_count = _positive_count(route.get("priority_count"))
    representative_items = route.get("representative_items") if isinstance(route.get("representative_items"), list) else []
    competitor_asins = _route_competitor_asins(candidate, route)
    review_summary = _route_review_evidence_summary(voc_package, route)
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
        "seller_sprite_exports": _route_list(route, "seller_sprite_exports"),
        "sorftime_checks": _route_list(route, "sorftime_checks"),
        "review_voc_asin_plan": competitor_asins,
        "review_coverage": review_summary,
        "route_search_terms": _route_list(route, "route_search_terms"),
        "decision_gate": _route_list(route, "decision_gate") or _default_route_decision_gate(route),
        "data_gaps": data_gap,
        "next_step": _route_next_step(recommended_depth, data_gap, route),
        "representative_market_items": representative_items[:3],
        "sort_priority": _route_plan_priority(route_type, recommended_depth, route_id),
    }


def _route_list(route: dict[str, Any], key: str) -> list[Any]:
    value = route.get(key)
    return list(value) if isinstance(value, list) else []


def _route_recommended_depth(
    route_type: str,
    candidate_count: int,
    priority_count: int,
    competitor_asins: list[dict[str, Any]],
) -> str:
    if route_type in {"主线", "升级", "场景", "组合"}:
        if candidate_count or competitor_asins:
            return "必须路线小深挖"
        return "必须主动补数"
    if route_type == "功能升级":
        return "小深挖观察" if candidate_count or competitor_asins else "作为规格维度验证"
    if route_type == "旁支":
        return "小深挖观察" if candidate_count or competitor_asins else "低优先补数"
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
        gaps.append("这条路线还没有明确市场样本，需要补代表 ASIN 或关键词结果。")
    if not competitor_asins:
        gaps.append("还缺这条路线的代表 ASIN，评价和 Sorftime 流量词无法单独判断。")
    matched_review_count = _positive_count(review_summary.get("matched_review_count"))
    matched_asins = review_summary.get("matched_asins") if isinstance(review_summary.get("matched_asins"), list) else []
    if matched_review_count < 30:
        gaps.append("评价样本还不够，至少补到 30 条以上再归纳痛点。")
    if route_type in {"主线", "升级", "场景", "组合"} and len(matched_asins) < 2:
        gaps.append("VOC 覆盖的 ASIN 太少，容易把单个竞品问题当成整条路线问题。")
    return gaps


def _route_plan_why(
    route: dict[str, Any],
    recommended_depth: str,
    competitor_asins: list[dict[str, Any]],
) -> str:
    route_name = str(route.get("route_name") or "这条路线")
    count = _positive_count(route.get("candidate_count"))
    price = str(route.get("price_text") or "价格待补")
    if "必须" in recommended_depth:
        return f"{route_name}不能混在大方向里看；现在有 {count} 个市场样本、价格 {price}，还要单独看竞品、评价和关键词入口。"
    if competitor_asins:
        return f"{route_name}已有可参考 ASIN，但还要确认它是主线机会还是旁支需求。"
    return f"{route_name}先保留观察，不要因为关键词相近就直接放进主推判断。"


def _route_next_step(recommended_depth: str, data_gaps: list[str], route: dict[str, Any]) -> str:
    if data_gaps:
        return data_gaps[0]
    if "规格维度" in recommended_depth:
        return "把这条路线的功能点写进基础款/升级款样品检查表。"
    if "必须" in recommended_depth:
        return "先补路线专属 ASIN、评价和关键词反查，再决定是否进完整深挖。"
    return str(route.get("decision_hint") or "先作为旁支观察，等证据变强再升级。")


def _route_plan_priority(route_type: str, recommended_depth: str, route_id: str) -> int:
    if "必须" in recommended_depth:
        return 10 + _route_priority(route_id)
    if route_type in {"场景", "组合"}:
        return 120 + _route_priority(route_id)
    if route_type == "功能升级":
        return 200 + _route_priority(route_id)
    if route_type == "旁支":
        return 300 + _route_priority(route_id)
    return 500 + _route_priority(route_id)


def _route_competitor_asins(candidate: dict[str, Any], route: dict[str, Any], limit: int = 5) -> list[dict[str, Any]]:
    route_id = str(route.get("route_id") or "")
    terms = _route_competitor_terms(route)
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
                    "reason": _route_competitor_reason(route, title),
                    "url": item.get("url"),
                }
            )
            if len(result) >= limit:
                return result
    return result


def _route_by_id(candidate: dict[str, Any], route_id: str) -> dict[str, Any]:
    profile = _route_profile(candidate, {})
    context = _build_product_context(candidate, {}, {}, profile)
    for definition in PRODUCT_ROUTE_DEFINITIONS:
        if definition.get("route_id") == route_id:
            return _route_definition_with_context(definition, context, profile, candidate)
    return {"route_id": route_id, "route_name": route_id}


def _route_competitor_terms(route: dict[str, Any]) -> tuple[str, ...]:
    terms = route.get("competitor_terms")
    if isinstance(terms, (list, tuple)):
        return tuple(str(term).lower() for term in terms if term)
    route_keywords = route.get("route_keywords")
    if isinstance(route_keywords, list):
        return tuple(str(term).lower() for term in route_keywords if term)
    return ()


def _route_competitor_match(title: str, route_id: str, terms: tuple[str, ...]) -> bool:
    text = title.lower()
    return bool(terms and any(term in text for term in terms))


def _route_competitor_reason(route: dict[str, Any], title: str) -> str:
    route_name = str(route.get("route_name") or "路线")
    return f"标题与「{route_name}」关键词匹配，适合单独进入路线级 VOC 或流量词验证：{title[:60]}"


def _route_review_evidence_summary(voc_package: dict[str, Any] | None, route: dict[str, Any]) -> dict[str, Any]:
    terms = tuple(str(term).lower() for term in route.get("review_terms", ()) if term)
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
        "这条路线有独立竞品、独立需求词和可追溯评论证据。",
        "评论痛点能转成明确产品规格或后续验证动作。",
        "该路线所在价格带有销量，并且不是被头部品牌完全锁死。",
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


def _decision_missing_inputs(candidate: dict[str, Any], voc_package: dict[str, Any] | None) -> list[str]:
    missing = list(candidate.get("missing_data", []))
    if voc_package:
        missing = [item for item in missing if "评论" not in item and "VOC" not in item]
    required_items = ["小类 Top100 明细", "关键词反查", "代表竞品 ASIN", "评论 VOC 证据"]
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
    audit = candidate.get("market_boundary_audit", {}) if isinstance(candidate.get("market_boundary_audit"), dict) else {}
    actions: list[str] = []
    if audit.get("broad_keyword") or _positive_count(audit.get("excluded_competitor_count")):
        actions.append("先清洗市场边界：剔除非同类 ASIN，并把泛词拆成可验证的小类词。")
    actions.append("把识别到的产品路线分开拉 Top100 和关键词反查。")
    actions.append("每条保留路线补 2-3 个强相关代表 ASIN，再看 Sorftime product_traffic_terms。")
    if voc_package and not voc_package.get("pain_points"):
        actions.append("把已接入评论按真实原文归纳成 VOC 痛点，并保留 review_id、ASIN、评分和原文证据。")
    elif not voc_package:
        actions.append("接入评论 VOC 后再判断痛点能否转成产品规格。")
    actions.append("清洗后重新计算评分卡，再决定是否继续深挖。")
    return _dedupe_strings(actions)[:6]


def _decision_risk_matrix(candidate: dict[str, Any], voc_package: dict[str, Any] | None) -> list[dict[str, str]]:
    competition = candidate.get("competition_structure", {})
    return_risk = candidate.get("return_risk", {})
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
            "dimension": "小类边界",
            "level": "待补",
            "basis": "需要确认大类、小类、关键词和代表 ASIN 是否指向同一市场。",
        },
        {
            "dimension": "数据质量",
            "level": str(data_quality.get("level", "待确认")),
            "basis": _market_structure_summary_line(candidate) or "Top 商品明细待补",
        },
    ]


def _status_next_step(decision_review: dict[str, Any], candidate: dict[str, Any]) -> str:
    actions = decision_review.get("action_items") if isinstance(decision_review.get("action_items"), list) else []
    if actions:
        return str(actions[0])
    return "先清洗小类边界、代表竞品和评论 VOC，再重新判断市场机会。"


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


def _with_effective_voc_findings(
    voc_package: dict[str, Any] | None,
    voc_analysis: dict[str, Any],
) -> dict[str, Any] | None:
    if not voc_package:
        return None
    merged = dict(voc_package)
    if isinstance(voc_analysis.get("pain_points"), list):
        merged["pain_points"] = voc_analysis["pain_points"]
    if isinstance(voc_analysis.get("highlights"), list):
        merged["highlights"] = voc_analysis["highlights"]
    return merged


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


_BOUNDARY_STOPWORDS = {
    "for",
    "and",
    "with",
    "the",
    "a",
    "an",
    "of",
    "to",
    "in",
    "on",
    "by",
    "from",
    "home",
    "household",
    "amazon",
    "product",
    "products",
    "item",
    "items",
    "tool",
    "tools",
    "kit",
    "set",
    "pack",
    "accessory",
    "accessories",
    "supplies",
    "cleaning",
    "cleaner",
    "用品",
    "工具",
    "套装",
    "配件",
    "清洁",
}

_BROAD_KEYWORD_PATTERNS = (
    "accessories",
    "supplies",
    "home goods",
    "household",
    "car accessories",
    "bathroom accessories",
    "cleaning supplies",
)

_MARKET_NOISE_TERMS = (
    "wet wipes",
    "flushable wipes",
    "adult wipes",
    "baby wipes",
    "wipe",
    "wipes",
    "battery",
    "batteries",
    "aa alkaline",
    "coffee scented",
    "menthol",
    "floor scrubber machine",
    "ride-on",
    "commercial floor scrubber",
)


def _apply_market_boundary_quality(candidate: dict[str, Any]) -> dict[str, Any]:
    cleaned = dict(candidate)
    audit = _build_market_boundary_audit(cleaned)
    cleaned["competitor_candidates"] = _filtered_competitor_candidates(cleaned, audit)
    cleaned["next_review_voc_asins"] = _filtered_review_voc_asins(cleaned, audit)
    cleaned["market_boundary_audit"] = audit
    return cleaned


def _build_market_boundary_audit(candidate: dict[str, Any]) -> dict[str, Any]:
    anchors = _market_anchor_terms(candidate)
    groups = candidate.get("competitor_candidates", {}) if isinstance(candidate.get("competitor_candidates"), dict) else {}
    total_count = 0
    excluded: list[dict[str, Any]] = []
    suspect: list[dict[str, Any]] = []
    relevant_count = 0
    for group_key, items in groups.items():
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            total_count += 1
            relevance = _competitor_market_relevance(item, anchors)
            row = {
                "asin": item.get("asin"),
                "title": item.get("title"),
                "group": group_key,
                "status": relevance["status"],
                "reason": relevance["reason"],
                "matched_terms": relevance["matched_terms"],
            }
            if relevance["status"] == "剔除":
                excluded.append(row)
            elif relevance["status"] == "需复核":
                suspect.append(row)
            else:
                relevant_count += 1
    top_keyword = str((candidate.get("demand_evidence", {}) or {}).get("top_keyword") or "").strip()
    broad_keyword = top_keyword if _is_broad_market_keyword(top_keyword) else ""
    notes: list[str] = []
    if broad_keyword:
        notes.append(f"核心词「{broad_keyword}」过宽，不能作为目标小类成交词。")
    if excluded:
        notes.append(f"竞品池剔除 {len(excluded)} 个明显非同类样本。")
    if suspect:
        notes.append(f"仍有 {len(suspect)} 个边界样本需要运营复核。")
    quality_status = "待清洗" if excluded or broad_keyword else ("需复核" if suspect else "通过")
    return {
        "quality_status": quality_status,
        "anchor_terms": anchors["phrases"][:12],
        "anchor_tokens": anchors["tokens"][:12],
        "broad_keyword": broad_keyword,
        "total_competitor_count": total_count,
        "relevant_competitor_count": relevant_count,
        "suspect_competitor_count": len(suspect),
        "excluded_competitor_count": len(excluded),
        "excluded_samples": excluded[:12],
        "suspect_samples": suspect[:12],
        "notes": notes,
    }


def _filtered_competitor_candidates(candidate: dict[str, Any], audit: dict[str, Any]) -> dict[str, Any]:
    anchors = {
        "phrases": audit.get("anchor_terms", []),
        "tokens": audit.get("anchor_tokens", []),
    }
    groups = candidate.get("competitor_candidates", {}) if isinstance(candidate.get("competitor_candidates"), dict) else {}
    cleaned: dict[str, Any] = {}
    for group_key, items in groups.items():
        if not isinstance(items, list):
            cleaned[group_key] = items
            continue
        kept: list[dict[str, Any]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            relevance = _competitor_market_relevance(item, anchors)
            if relevance["status"] == "剔除":
                continue
            kept.append(
                {
                    **item,
                    "market_boundary_status": relevance["status"],
                    "market_boundary_reason": relevance["reason"],
                    "market_boundary_terms": relevance["matched_terms"],
                }
            )
        cleaned[group_key] = kept
    return cleaned


def _filtered_review_voc_asins(candidate: dict[str, Any], audit: dict[str, Any]) -> list[dict[str, Any]]:
    items = candidate.get("next_review_voc_asins")
    if not isinstance(items, list):
        return []
    anchors = {
        "phrases": audit.get("anchor_terms", []),
        "tokens": audit.get("anchor_tokens", []),
    }
    result: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        relevance = _competitor_market_relevance(item, anchors)
        if relevance["status"] == "剔除":
            continue
        result.append(
            {
                **item,
                "market_boundary_status": relevance["status"],
                "market_boundary_reason": relevance["reason"],
                "market_boundary_terms": relevance["matched_terms"],
            }
        )
    return result


def _market_anchor_terms(candidate: dict[str, Any]) -> dict[str, list[str]]:
    demand = candidate.get("demand_evidence", {}) if isinstance(candidate.get("demand_evidence"), dict) else {}
    raw_terms: list[str] = []
    for key in ("aba_top_search_term", "top_keyword"):
        value = demand.get(key)
        if value and not _is_broad_market_keyword(str(value)):
            raw_terms.append(str(value))
    aba_signal = demand.get("aba_keyword_signal", {}) if isinstance(demand.get("aba_keyword_signal"), dict) else {}
    top_keywords = aba_signal.get("top_keywords") if isinstance(aba_signal.get("top_keywords"), list) else []
    for item in top_keywords[:10]:
        if isinstance(item, dict) and item.get("keyword"):
            raw_terms.append(str(item.get("keyword")))
    sf_keywords = demand.get("sorftime_keyword_verification") if isinstance(demand.get("sorftime_keyword_verification"), list) else []
    for item in sf_keywords[:10]:
        if isinstance(item, dict) and item.get("keyword"):
            raw_terms.append(str(item.get("keyword")))
    category = demand.get("sorftime_category_report", {}) if isinstance(demand.get("sorftime_category_report"), dict) else {}
    if category.get("category_name"):
        raw_terms.append(str(category.get("category_name")))
    title_token_counts: dict[str, int] = {}
    title_sources = []
    market_structure = candidate.get("market_structure", {}) if isinstance(candidate.get("market_structure"), dict) else {}
    for source in (candidate.get("top_products"), market_structure.get("tagged_products")):
        if isinstance(source, list):
            title_sources.extend(item for item in source[:120] if isinstance(item, dict))
    for item in title_sources:
        title = _normalize_market_text(item.get("title") or item.get("Title") or "")
        for token in re.findall(r"[a-z0-9]+", title):
            if len(token) >= 4 and token not in _BOUNDARY_STOPWORDS and token not in _MARKET_NOISE_TERMS:
                title_token_counts[token] = title_token_counts.get(token, 0) + 1

    phrases: list[str] = []
    tokens: list[str] = []
    for term in raw_terms:
        clean = _normalize_market_text(term)
        if not clean or _is_broad_market_keyword(clean):
            continue
        if len(clean) >= 4:
            phrases.append(clean)
        for token in re.findall(r"[a-z0-9]+", clean.lower()):
            if len(token) >= 4 and token not in _BOUNDARY_STOPWORDS:
                tokens.append(token)
    frequent_title_tokens = [
        token
        for token, count in sorted(title_token_counts.items(), key=lambda item: (-item[1], item[0]))
        if count >= 2
    ]
    tokens.extend(frequent_title_tokens[:12])
    return {
        "phrases": _dedupe_strings(phrases)[:16],
        "tokens": _dedupe_strings(tokens)[:16],
    }


def _competitor_market_relevance(item: dict[str, Any], anchors: dict[str, list[str]]) -> dict[str, Any]:
    text = _normalize_market_text(
        " ".join(str(item.get(key) or "") for key in ("title", "brand", "note", "seller"))
    )
    phrases = [str(term).lower() for term in anchors.get("phrases", []) if term]
    tokens = [str(term).lower() for term in anchors.get("tokens", []) if term]
    matched_phrases = [term for term in phrases if term and term in text]
    matched_tokens = [term for term in tokens if term and re.search(rf"\b{re.escape(term)}\b", text)]
    noise_hits = [term for term in _MARKET_NOISE_TERMS if term in text]
    if matched_phrases or len(matched_tokens) >= 2:
        status = "相关"
    elif matched_tokens and not noise_hits:
        status = "需复核"
    else:
        status = "剔除"
    if noise_hits and not matched_phrases and len(matched_tokens) < 2:
        status = "剔除"
    reason = "；".join(
        part
        for part in (
            f"命中锚点：{', '.join((matched_phrases + matched_tokens)[:5])}" if matched_phrases or matched_tokens else "",
            f"疑似噪音词：{', '.join(noise_hits[:4])}" if noise_hits else "",
            "未命中目标小类锚点" if status == "剔除" and not matched_phrases and not matched_tokens else "",
        )
        if part
    )
    return {
        "status": status,
        "reason": reason or "需要运营复核是否属于目标小类",
        "matched_terms": _dedupe_strings(matched_phrases + matched_tokens)[:8],
        "noise_terms": noise_hits[:6],
    }


def _normalize_market_text(value: Any) -> str:
    text = re.sub(r"[_/\\-]+", " ", str(value or "").lower())
    text = re.sub(r"[^a-z0-9\u4e00-\u9fff\s]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _is_broad_market_keyword(value: str) -> bool:
    text = _normalize_market_text(value)
    if not text:
        return False
    return text in _BROAD_KEYWORD_PATTERNS or any(pattern == text for pattern in _BROAD_KEYWORD_PATTERNS)


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
    price_context = candidate.get("price_band_context", {}) if isinstance(candidate.get("price_band_context"), dict) else {}
    category_report = demand.get("sorftime_category_report", {})
    parts = []
    if price_context.get("top_price_band_by_units"):
        parts.append(f"销量集中价格带 {price_context.get('top_price_band_by_units')} USD")
    if price_context.get("top_price_band_units_share") is not None:
        parts.append(f"该价格带销量占比 {_fmt_percent(price_context.get('top_price_band_units_share'))}")
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
    pain_points = _trim_findings(voc_package.get("pain_points", []), finding_limit=8, evidence_limit=5)
    highlights = _trim_findings(voc_package.get("highlights", []), finding_limit=6, evidence_limit=5)
    if not pain_points:
        pain_points = _derive_voc_findings_from_reviews(voc_package)
    return {
        "summary": summary,
        "source_scope": {
            "entry_site": summary.get("primary_entry_site", ""),
            "primary_review_region": summary.get("primary_review_region", ""),
            "entry_site_distribution": summary.get("entry_site_distribution", []),
            "review_region_distribution": summary.get("review_region_distribution", []),
            "note": summary.get("source_scope_note", ""),
        },
        "pain_points": pain_points,
        "highlights": highlights,
        "opportunity_hypotheses": voc_package.get("opportunity_hypotheses", [])[:8],
        "evidence_policy": "评论结论必须追溯到 review_id、ASIN、评分和评论链接；自动归纳只作初筛，需运营复核。",
    }


def _derive_voc_findings_from_reviews(voc_package: dict[str, Any], limit: int = 6) -> list[dict[str, Any]]:
    reviews = [item for item in voc_package.get("normalized_reviews", []) if isinstance(item, dict)]
    if not reviews:
        return []
    rated_reviews = [review for review in reviews if review_rating_sort_key(review) < 9]
    low_rating_reviews = [review for review in rated_reviews if review_rating_sort_key(review) <= 3]
    if not low_rating_reviews:
        return []
    average_rating = sum(review_rating_sort_key(review) for review in rated_reviews) / len(rated_reviews) if rated_reviews else 0.0
    low_rating_share = len(low_rating_reviews) / len(rated_reviews) if rated_reviews else 0.0
    evidence = []
    for review in sorted(low_rating_reviews, key=review_rating_sort_key)[:limit]:
        evidence.append(
            {
                "review_id": review.get("review_id"),
                "asin": review.get("asin"),
                "rating": review.get("rating"),
                "snippet": review_snippet(review),
                "url": review.get("url"),
                "site": review.get("site"),
                "review_region": review.get("review_region"),
                "review_date": review.get("review_date"),
            }
        )
    return [
        {
            "name": "低分评论概览",
            "review_count": len(low_rating_reviews),
            "severity": "高" if low_rating_share >= 0.25 else "中",
            "description": (
                f"已接入 {len(rated_reviews)} 条可评分评论，平均评分 {average_rating:.1f}，"
                f"低分评论占比 {low_rating_share:.1%}；脚本不自动分配品类主题，需由分析层阅读原文归纳痛点。"
            ),
            "evidence": evidence,
        }
    ]


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
    if rows:
        return rows
    groups = candidate.get("competitor_candidates", {})
    if not isinstance(groups, dict):
        return []
    for group_key, competitor_type in (
        ("top10", "Top10 标杆"),
        ("recent_winners", "近半年新品"),
        ("structure_supplement", "结构补充"),
    ):
        items = groups.get(group_key)
        if not isinstance(items, list):
            continue
        for item in items[:4]:
            if not isinstance(item, dict):
                continue
            rows.append(
                {
                    "asin": item.get("asin"),
                    "brand": item.get("brand"),
                    "title": item.get("title"),
                    "price_usd": item.get("price"),
                    "monthly_units": item.get("monthly_units"),
                    "rating": item.get("rating"),
                    "rating_count": item.get("rating_count"),
                    "competitor_type": competitor_type,
                    "coverage_dimensions": item.get("coverage_dimensions", [competitor_type]),
                    "market_boundary_status": item.get("market_boundary_status", "相关"),
                    "selection_reason": _competitor_selection_reason(item, competitor_type),
                }
            )
    if rows:
        return rows
    top_products = candidate.get("top_products", [])
    if not isinstance(top_products, list):
        top_products = candidate.get("market_structure", {}).get("tagged_products", [])
    if not isinstance(top_products, list):
        return []
    for item in top_products[:6]:
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "asin": item.get("asin"),
                "brand": item.get("brand"),
                "title": item.get("title"),
                "price_usd": item.get("price"),
                "monthly_units": item.get("monthly_units") or item.get("monthly_sales"),
                "rating": item.get("rating"),
                "rating_count": item.get("rating_count"),
                "competitor_type": "Top100 样本",
                "coverage_dimensions": ["Top100 样本"],
                "market_boundary_status": item.get("market_boundary_status", "待复核"),
                "selection_reason": "Top100 商品样本兜底进入竞品选择逻辑，待运营补充竞品角色。",
            }
        )
    if not rows:
        rows.append(
            {
                "asin": "",
                "brand": "",
                "title": candidate.get("name"),
                "price_usd": None,
                "monthly_units": None,
                "rating": None,
                "rating_count": None,
                "competitor_type": "待补竞品",
                "coverage_dimensions": ["待补竞品"],
                "selection_reason": "候选池尚未提供可用竞品明细，需运营补充 Top10/新品/结构补充 ASIN。",
            }
        )
    return rows


def _competitor_selection_reason(item: dict[str, Any], competitor_type: str) -> str:
    parts = [str(item.get("note") or f"{competitor_type}样本，作为竞品选择逻辑兜底行。")]
    if item.get("market_boundary_status") == "需复核":
        parts.append(f"边界待复核：{item.get('market_boundary_reason')}")
    return "；".join(part for part in parts if part)


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


def _market_boundary_summary_line(candidate: dict[str, Any]) -> str:
    audit = candidate.get("market_boundary_audit", {}) if isinstance(candidate.get("market_boundary_audit"), dict) else {}
    if not audit:
        return ""
    parts: list[str] = []
    if audit.get("broad_keyword"):
        parts.append(f"核心词「{audit.get('broad_keyword')}」过宽")
    excluded = _positive_count(audit.get("excluded_competitor_count"))
    if excluded:
        parts.append(f"已剔除 {excluded} 个非同类竞品样本")
    suspect = _positive_count(audit.get("suspect_competitor_count"))
    if suspect:
        parts.append(f"{suspect} 个边界样本待复核")
    return "市场边界审计：" + "；".join(parts) if parts else ""


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

def _build_competitor_deep_dive(competitor_candidates: dict[str, Any], sorftime_traffic: dict[str, Any] | None = None) -> list[dict[str, Any]]:
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
            "market_boundary_status": item.get("market_boundary_status", "相关"),
            "market_boundary_reason": item.get("market_boundary_reason", ""),
            "traffic_keywords": _traffic_keywords_for_asin(sorftime_traffic, asin),
            "traffic_mixed_warnings": _traffic_warnings_for_asin(sorftime_traffic, asin),
        })

    for item in (competitor_candidates.get("top10") or [])[:3]:
        add_card(item, "标杆老品")
    for item in (competitor_candidates.get("recent_winners") or [])[:2]:
        add_card(item, "近半年新品")

    return cards


def _traffic_keywords_for_asin(sorftime_traffic: dict[str, Any] | None, asin: str) -> list[dict[str, Any]]:
    traffic = _traffic_item_for_asin(sorftime_traffic, asin)
    if not traffic:
        return []
    words = traffic.get("top_traffic_words") if isinstance(traffic.get("top_traffic_words"), list) else []
    return [item for item in words if isinstance(item, dict)][:8]


def _traffic_warnings_for_asin(sorftime_traffic: dict[str, Any] | None, asin: str) -> list[str]:
    traffic = _traffic_item_for_asin(sorftime_traffic, asin)
    if not traffic:
        return []
    warnings = traffic.get("mixed_pool_warning") if isinstance(traffic.get("mixed_pool_warning"), list) else []
    return [str(item) for item in warnings if item][:8]


def _traffic_item_for_asin(sorftime_traffic: dict[str, Any] | None, asin: str) -> dict[str, Any]:
    if not isinstance(sorftime_traffic, dict) or not asin:
        return {}
    if str(sorftime_traffic.get("asin") or "") == asin:
        return sorftime_traffic
    items = sorftime_traffic.get("asins") if isinstance(sorftime_traffic.get("asins"), list) else []
    for item in items:
        if isinstance(item, dict) and str(item.get("asin") or "") == asin:
            return item
    return {}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a minimal research package from one candidate in a candidate pool.")
    parser.add_argument("candidate_pool_json")
    parser.add_argument("output_json")
    parser.add_argument("candidate_id", nargs="?", default=None)
    parser.add_argument("--voc-package", default="", help="Optional review_voc_package.json from review plugin exports.")
    parser.add_argument("--route-profile", default="", help="Optional JSON product route profile. Keeps category terms outside production code.")
    parser.add_argument("--dimension-rules", default="", help="Optional Top100 dimension rules JSON path.")
    parser.add_argument("--cross-config", default="", help="Optional Top100 cross-analysis config JSON path.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    pool_path = Path(args.candidate_pool_json)
    output_path = Path(args.output_json)
    voc_package = json.loads(Path(args.voc_package).read_text(encoding="utf-8")) if args.voc_package else None
    route_profile = json.loads(Path(args.route_profile).read_text(encoding="utf-8")) if args.route_profile else None
    candidate_pool = json.loads(pool_path.read_text(encoding="utf-8"))
    if args.dimension_rules:
        candidate_pool.setdefault("metadata", {})["top100_dimension_rules_path"] = str(Path(args.dimension_rules).resolve())
    if args.cross_config:
        candidate_pool.setdefault("metadata", {})["top100_cross_config_path"] = str(Path(args.cross_config).resolve())
    package = build_research_package(candidate_pool, args.candidate_id, voc_package, route_profile)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(package, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
