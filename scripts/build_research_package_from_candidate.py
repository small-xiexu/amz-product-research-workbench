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
    status = candidate.get("status", "观察")
    voc_analysis = _build_voc_analysis(voc_package)
    voc_review_sources = _build_review_sources(voc_package)
    voc_opportunities = _build_voc_opportunities(voc_package, candidate.get("candidate_id"))
    voc_summary_line = _voc_summary_line(voc_package)
    decision_review = _build_decision_review(candidate, voc_package)

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
            "voc_evidence": _collect_voc_evidence(voc_package),
        },
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
    return {
        "package_id": metadata.get("package_id"),
        "source_type": metadata.get("source_type"),
        "source_files": metadata.get("source_files", []),
        "generated_at": metadata.get("generated_at"),
        "summary": voc_package.get("summary", {}),
        "ai_report_reference": voc_package.get("ai_report_reference", {}),
    }


def _build_decision_review(candidate: dict[str, Any], voc_package: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "status_explanation": _status_explanation(candidate, voc_package),
        "facts": _decision_facts(candidate, voc_package),
        "inferences": _decision_inferences(candidate, voc_package),
        "missing_inputs": _decision_missing_inputs(candidate, voc_package),
        "action_items": _decision_action_items(candidate, voc_package),
        "risk_matrix": _decision_risk_matrix(candidate, voc_package),
    }


def _status_explanation(candidate: dict[str, Any], voc_package: dict[str, Any] | None) -> str:
    status = candidate.get("status", "观察")
    if status in ("继续看", "试做"):
        base = "当前可以继续深挖，但不能直接进入打样或采购决策。"
    elif status == "观察":
        base = "当前需要先补关键缺口，再判断是否进入深挖。"
    else:
        base = "当前不建议进入深挖，除非出现新的证据或明确改品方案。"
    first_pain = _first_pain_name(voc_package)
    if first_pain:
        return f"{base} 评论 VOC 首要痛点为「{first_pain}」，需要在供应链和 Listing 方案中优先验证。"
    return base


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
        facts.append(
            f"评论 VOC：已接入 {summary.get('review_count', 0)} 条评论，覆盖 {summary.get('asin_count', 0)} 个 ASIN，低分评论 {summary.get('low_rating_count', 0)} 条。"
        )
    return [item for item in facts if item and "待填" not in item]


def _decision_inferences(candidate: dict[str, Any], voc_package: dict[str, Any] | None) -> list[str]:
    competition = candidate.get("competition_structure", {})
    new_listing = candidate.get("new_listing_opportunity", {})
    return_risk = candidate.get("return_risk", {})
    inferences = []
    top10_share = competition.get("top10_product_units_share")
    if isinstance(top10_share, (int, float)) and top10_share >= 0.5:
        inferences.append("Top10 商品销量占比较高，进入时需要明确差异化，不适合只做同款低价。")
    top_brand_share = competition.get("top_brand_units_share")
    if isinstance(top_brand_share, (int, float)) and top_brand_share >= 0.3:
        inferences.append("头部品牌存在明显领先，需评估品牌壁垒和内容门槛。")
    if new_listing.get("new_listing_count_6m"):
        inferences.append("近半年仍有新品获得销量，说明并非完全封闭市场，但要验证新品增长是否来自广告或低价。")
    market_return = return_risk.get("market_return_rate")
    category_return = return_risk.get("category_return_rate")
    if isinstance(market_return, (int, float)) and isinstance(category_return, (int, float)) and market_return > category_return:
        inferences.append("市场退货率高于同类目平均，产品硬伤和预期落差需要前置复核。")
    first_pain = _first_pain_name(voc_package)
    if first_pain:
        inferences.append(f"评论首要痛点为「{first_pain}」，改品方案必须能解释这个问题如何被缓解。")
    return inferences or ["当前数据能支持继续看，但还不足以形成进入结论。"]


def _decision_missing_inputs(candidate: dict[str, Any], voc_package: dict[str, Any] | None) -> list[str]:
    missing = list(candidate.get("missing_data", []))
    if voc_package:
        missing = [item for item in missing if "评论" not in item and "VOC" not in item]
    for item in ["建议售价", "采购价", "FBA费用", "头程费用", "入库配置费", "商标/专利复核", "合规认证复核"]:
        if item not in missing:
            missing.append(item)
    return missing


def _decision_action_items(candidate: dict[str, Any], voc_package: dict[str, Any] | None) -> list[str]:
    actions = [
        "补利润复核字段：建议售价、采购价、FBA费用、头程、入库配置费。",
        "基于 Top10 标杆组核对主卖点、价格带、图片/A+、评论门槛和变体口径。",
        "基于近半年新品组判断新品放量原因：广告、低价、功能差异还是类目自然增长。",
        "做商标/专利/合规初筛，只保留待复核结论，不写最终法律判断。",
    ]
    first_pain = _first_pain_name(voc_package)
    if first_pain:
        actions.insert(2, f"把「{first_pain}」作为供应商问询和样品测试的第一优先级。")
    if candidate.get("return_risk", {}).get("level") in ("中", "高"):
        actions.append("结合评论痛点和卖家精灵退货率，判断退货是否来自可改问题。")
    return actions


def _decision_risk_matrix(candidate: dict[str, Any], voc_package: dict[str, Any] | None) -> list[dict[str, str]]:
    competition = candidate.get("competition_structure", {})
    return_risk = candidate.get("return_risk", {})
    ip_risk = candidate.get("ip_compliance_risk", {})
    top10_share = competition.get("top10_product_units_share")
    first_pain = _first_pain_name(voc_package)
    return [
        {
            "dimension": "市场容量",
            "level": "中",
            "basis": _market_size_text(candidate),
            "next_check": "继续用 Top100 和关键词数据确认需求稳定性。",
        },
        {
            "dimension": "竞争集中度",
            "level": "高" if isinstance(top10_share, (int, float)) and top10_share >= 0.5 else "中",
            "basis": _brand_concentration_text(candidate),
            "next_check": "确认头部是否靠品牌、广告、低价或历史评论门槛领先。",
        },
        {
            "dimension": "新品机会",
            "level": "中",
            "basis": _new_listing_text(candidate),
            "next_check": "拆解近半年新品是否真实放量，以及是否可复制。",
        },
        {
            "dimension": "评论/VOC",
            "level": "高" if first_pain else "待补",
            "basis": f"首要痛点：{first_pain}" if first_pain else "未接入评论 VOC",
            "next_check": "把高频差评转成供应商测试项和 Listing 避坑项。",
        },
        {
            "dimension": "退货风险",
            "level": str(return_risk.get("level", "待确认")),
            "basis": _return_rate_text(candidate),
            "next_check": "判断退货来自产品硬伤、误购、质量波动还是使用门槛。",
        },
        {
            "dimension": "利润不确定性",
            "level": "待补",
            "basis": "采购价、FBA、头程和入库配置费仍未补齐。",
            "next_check": "按内部口径补字段后再算毛利率。",
        },
        {
            "dimension": "知产/合规",
            "level": str(ip_risk.get("level", "待确认")),
            "basis": str(ip_risk.get("notes", "待复核")),
            "next_check": "做商标、外观/结构专利和品类合规入口初筛。",
        },
    ]


def _status_next_step(decision_review: dict[str, Any], candidate: dict[str, Any]) -> str:
    action_items = decision_review.get("action_items", [])
    if action_items:
        return str(action_items[0])
    return str(candidate.get("next_step", "待补"))


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
        parts.append(f"市场月均销售额 ${_fmt_number(demand.get('market_avg_monthly_revenue_usd'))}")
    if competition.get("top10_avg_monthly_units") is not None:
        parts.append(f"Top10 月均销量 {_fmt_number(competition.get('top10_avg_monthly_units'))}")
    return "；".join(parts) if parts else "待填"


def _price_band_text(candidate: dict[str, Any]) -> str:
    demand = candidate.get("demand_evidence", {})
    profit = candidate.get("preliminary_profit_space", {})
    parts = []
    if profit.get("top_price_band_by_units"):
        parts.append(f"销量集中价格带 {profit.get('top_price_band_by_units')} 美元")
    if profit.get("top_price_band_units_share") is not None:
        parts.append(f"该价格带销量占比 {_fmt_percent(profit.get('top_price_band_units_share'))}")
    if demand.get("market_avg_price_usd") is not None:
        parts.append(f"市场平均价 ${_fmt_number(demand.get('market_avg_price_usd'))}")
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
    return {
        "summary": voc_package.get("summary", {}),
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
    return rows


def _voc_summary_line(voc_package: dict[str, Any] | None) -> str:
    if not voc_package:
        return ""
    summary = voc_package.get("summary", {})
    pain_points = voc_package.get("pain_points", [])
    first_pain = pain_points[0].get("name") if pain_points else "待补"
    return (
        f"评论 VOC 已接入：共 {summary.get('review_count', 0)} 条评论、"
        f"{summary.get('asin_count', 0)} 个 ASIN，首要痛点为「{first_pain}」。"
    )


def _voc_dashboard_card(voc_package: dict[str, Any] | None) -> dict[str, Any] | None:
    if not voc_package:
        return None
    summary = voc_package.get("summary", {})
    pain_points = voc_package.get("pain_points", [])
    highlights = voc_package.get("highlights", [])
    return {
        "title": "评论 VOC",
        "status": "已接入",
        "review_count": summary.get("review_count", 0),
        "first_pain_point": pain_points[0].get("name") if pain_points else "待补",
        "first_highlight": highlights[0].get("name") if highlights else "待补",
    }


def _append_sentence(base: str, sentence: str) -> str:
    if not sentence:
        return base
    return f"{base} {sentence}"


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
