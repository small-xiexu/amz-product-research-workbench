"""Decision review and AI analysis — final judgment and operator-facing text."""

from __future__ import annotations

from typing import Any

from packages.research_core.pipeline.market_text import (
    _brand_concentration_text, _fmt_number, _fmt_percent, _join_text,
    _market_size_text, _market_structure_summary_line, _new_listing_text,
    _positive_count, _price_band_text, _return_rate_text,
)
from packages.research_core.pipeline.voc_analysis import (
    _append_sentence, _voc_risk_basis, _voc_scope_text, _voc_summary,
)
from packages.research_core.pipeline.route_matrix import _product_route_plain_summary, _route_evidence_plain_summary
from packages.research_core.pipeline.shared import _dedupe_strings

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
