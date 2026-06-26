#!/usr/bin/env python3
"""Generate report_data.json seed from analysis_packet — the AI enhancement canvas."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from packages.research_core.pipeline._utils import (
    _report_value, _source_packet_ref, _contract_verdict, _lead_analysis,
    as_list, numeric_value,
)

def _evidence_sources_from_analysis(analysis: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        _source_packet_ref(row, index)
        for index, row in enumerate(analysis.get("source_packets") or [])
        if isinstance(row, dict)
    ]


def _data_sources_from_analysis(analysis: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_packets": _evidence_sources_from_analysis(analysis),
        "critical_inputs": {
            "route_matrix": "route_matrix_confirm.json",
            "workflow_state": "workflow_state.json",
        },
        "data_gaps": analysis.get("blocking_gaps") or [],
        "freshness_note": "以 Evidence Packet 和关键输入文件的生成时间为准；缺失口径必须写入 data_gaps。",
    }


def _core_search_volume_estimate(kw_pool: dict[str, Any]) -> str:
    """从关键词池聚合估计核心词月搜索量。"""
    roles = kw_pool.get("roles") if isinstance(kw_pool.get("roles"), dict) else {}
    # 优先取 main_traffic 角色的关键词月搜总和
    head = as_list(roles.get("main_traffic") or roles.get("head") or roles.get("主攻词") or [])
    total = 0
    for kw in head:
        if isinstance(kw, dict):
            vol = numeric_value(kw.get("monthly_search_volume"))
            if vol:
                total += int(vol)
    if total > 0:
        return f"~{total // 1000}K" if total >= 1000 else str(total)
    # Fallback: check all role keywords
    for role_kws in roles.values():
        for kw in as_list(role_kws):
            if isinstance(kw, dict):
                vol = numeric_value(kw.get("monthly_search_volume"))
                if vol:
                    total += int(vol)
    if total > 0:
        return f"~{total // 1000}K" if total >= 1000 else str(total)
    return "待补"


def _recommended_price_from_routes(route_judgment: list[dict[str, Any]]) -> str:
    """从路线判断中提取推荐定价区间。优先取主线的 price_range，其次取第一条路线的。"""
    for rj in route_judgment:
        if not isinstance(rj, dict):
            continue
        role = rj.get("role", "")
        price = rj.get("price_range", "")
        if role == "主线候选" and price:
            return price
    # Fallback: take first available price_range
    for rj in route_judgment:
        price = rj.get("price_range", "") if isinstance(rj, dict) else ""
        if price:
            return price
    return "待补"



def seed_report_data_from_analysis(analysis: dict[str, Any]) -> dict[str, Any]:
    """从脚本分析 dict 生成初始 report_data.json，供 AI 增强。"""
    run_id = analysis.get("run_id", "")
    verdict_raw = analysis.get("verdict", "")
    confidence = analysis.get("confidence", "")
    one_sentence = analysis.get("one_sentence_conclusion", "")
    market = analysis.get("seller_sprite_validation") or {}
    cat_opp = analysis.get("category_opportunity") or {}
    cat_seasonality = cat_opp.get("category_seasonality") or {}
    voc_spec = analysis.get("voc_spec_translation") or {}
    kw_pool = analysis.get("keyword_pool") or {}
    synthesis = analysis.get("market_synthesis") or {}
    primary = market.get("primary_market") or {}
    price_bands_raw = cat_opp.get("price_band_opportunity") or []
    cat_candidates = cat_opp.get("category_candidates") or []
    gaps = analysis.get("blocking_gaps") or []
    next_conditions = analysis.get("next_stage_entry_conditions") or []
    source_packets = analysis.get("source_packets") or []
    report_verdict = _contract_verdict(verdict_raw)
    lead_analysis = _lead_analysis(one_sentence, verdict_raw, report_verdict)

    # Category
    top_cat = cat_candidates[0] if cat_candidates else {}
    overview = primary.get("overview_all") or {}

    # Price bands
    price_bands = []
    for index, pb in enumerate(price_bands_raw):
        source_base = f"analysis.category_opportunity.price_band_opportunity[{index}]"
        price_bands.append({
            "band": {"value": pb.get("price_band", ""), "source_path": f"{source_base}.price_band"},
            "unit_share": {"value": pb.get("sales_share", ""), "source_path": f"{source_base}.sales_share"},
            "product_count": {"value": pb.get("product_count", ""), "source_path": f"{source_base}.product_count"},
            "opportunity_level": {"value": pb.get("opportunity_level", ""), "source_path": f"{source_base}.opportunity_level"},
            "bar_height": {
                "value": pb.get("bar_height", 0),
                "source_path": f"{source_base}.bar_height",
            },
            "judgment": pb.get("reason", ""),
            "source_path": source_base,
        })

    # Competitors
    competitors = []
    for index, asin in enumerate(analysis.get("reference_asin_pool") or []):
        source_base = f"analysis.reference_asin_pool[{index}]"
        brand_val = asin.get("brand", "")
        rating_val = asin.get("rating", "")
        competitors.append({
            "asin": {"value": asin.get("asin", ""), "source_path": f"{source_base}.asin"},
            "route": {"value": asin.get("route_ref", ""), "source_path": f"{source_base}.route_ref"},
            "brand": {"value": brand_val, "source_path": f"{source_base}.brand"},
            "price": {"value": asin.get("price", ""), "source_path": f"{source_base}.price"},
            "monthly_sales": {"value": asin.get("monthly_sales", ""), "source_path": f"{source_base}.monthly_sales"},
            "rating": {"value": rating_val, "source_path": f"{source_base}.rating"},
            "rating_count": {"value": asin.get("rating_count", ""), "source_path": f"{source_base}.rating_count"},
            "asin_role": {"value": asin.get("asin_role", ""), "source_path": f"{source_base}.asin_role"},
            "judgment": asin.get("similarity_reason", ""),
            "source_path": source_base,
        })

    # Pain points
    pain_points = []
    for index, pp in enumerate(voc_spec.get("pain_points") or []):
        source_base = f"analysis.voc_spec_translation.pain_points[{index}]"
        pain_points.append({
            "priority": pp.get("priority", "P1"),
            "dimension": {"value": pp.get("dimension", ""), "source_path": f"{source_base}.dimension"},
            "review_count": {"value": pp.get("review_count", ""), "source_path": f"{source_base}.review_count"},
            "asins_affected_count": {"value": pp.get("asins_affected", ""), "source_path": f"{source_base}"},
            "issue_description": pp.get("issue", ""),
            "spec_requirement": pp.get("spec_requirement", ""),
            "source_path": source_base,
        })

    # Keywords
    keywords = []
    roles = kw_pool.get("roles") or {}
    if isinstance(roles, dict):
        for role, items in roles.items():
            for index, item in enumerate(items if isinstance(items, list) else [items]):
                if isinstance(item, dict):
                    source_base = f"analysis.keyword_pool.roles.{role}[{index}]"
                    ms_vol = item.get("monthly_search_volume", "")
                    cpc_val = item.get("cpc", "")
                    comp_cnt = item.get("competitor_count", "")
                    keywords.append({
                        "role": role,
                        "keyword": {"value": item.get("keyword", item.get("term", "")), "source_path": f"{source_base}.keyword"},
                        "monthly_search_volume": {
                            "value": ms_vol,
                            "source_path": f"{source_base}.monthly_search_volume",
                        },
                        "cpc": {
                            "value": cpc_val,
                            "source_path": f"{source_base}.cpc",
                        },
                        "competitor_count": {
                            "value": comp_cnt,
                            "source_path": f"{source_base}.competitor_count",
                        },
                        "strategy": item.get("reason", item.get("recommended_action", "")),
                        "source_path": source_base,
                    })

    # Risks
    risks = []
    for gap in gaps:
        risks.append({
            "severity": "medium",
            "description": gap.get("gap", ""),
            "evidence_basis": gap.get("impact", ""),
            "mitigation": "",
            "source_path": "analysis.blocking_gaps",
        })

    # Advantages（AI 判断填充，脚本不生成分析文字）
    advantages = [{"severity": "待评估", "description": "待AI分析补充", "evidence_basis": "", "source_path": "__ai_judgment__"}]

    # Go/No-Go
    gonogo = []
    for cond in next_conditions:
        gonogo.append({
            "condition": cond.get("condition", ""),
            "go_threshold": cond.get("why", ""),
            "nogo_threshold": "",
            "current_status": cond.get("status", "must"),
            "source_path": "analysis.next_stage_entry_conditions",
        })

    # Next steps（AI 判断填充，脚本只放占位）
    next_steps = [{"order": 1, "title": "联系供应商打样，基于VOC痛点制定品质标准", "description": voc_spec.get("summary", ""), "source_path": "__ai_judgment__"}]

    # 派生值：写入 analysis._derived 以便 source_path 落到标量字段
    derived = analysis.setdefault("_derived", {})
    derived["core_search_volume"] = _core_search_volume_estimate(kw_pool)
    derived["recommended_price"] = _recommended_price_from_routes(analysis.get("route_judgment") or [])

    # Hero metrics
    metrics = {
        "target_market": {"label": "目标市场", "value": primary.get("label", top_cat.get("category_name", "")), "source_path": "analysis.seller_sprite_validation.primary_market.label"},
        "monthly_demand": {"label": "月销", "value": f"{primary.get('avg_monthly_units', '')} units", "source_path": "analysis.seller_sprite_validation.primary_market.avg_monthly_units"},
        "core_search_volume": {"label": "核心词月搜", "value": derived["core_search_volume"], "source_path": "analysis._derived.core_search_volume"},
        "avg_price": {"label": "均价", "value": f"${primary.get('avg_price_usd', '')}", "source_path": "analysis.seller_sprite_validation.primary_market.avg_price_usd"},
        "recommended_price": {"label": "推荐定价", "value": derived["recommended_price"], "source_path": "analysis._derived.recommended_price"},
        "avg_rating": {"label": "类目均分", "value": primary.get("avg_rating", "待补"), "source_path": "analysis.seller_sprite_validation.primary_market.avg_rating"},
    }

    representative_asins = []
    for index, asin in enumerate((analysis.get("reference_asin_pool") or [])[:5]):
        representative_asins.append({
            "asin": asin.get("asin", ""),
            "monthly_sales": asin.get("monthly_sales", ""),
            "source_path": f"analysis.reference_asin_pool[{index}]",
        })

    categories = []
    category_rows = cat_candidates or [top_cat]
    for index, category in enumerate(category_rows[:8]):
        source_base = f"analysis.category_opportunity.category_candidates[{index}]"
        has_candidate = bool(cat_candidates)
        category_name = category.get("category_name") or primary.get("label", "")
        categories.append({
            "category_name": {
                "value": category_name,
                "source_path": f"{source_base}.category_name" if has_candidate and category.get("category_name") else "analysis.seller_sprite_validation.primary_market.label",
            },
            "node_id": {
                "value": category.get("node_id", ""),
                "source_path": f"{source_base}.node_id" if has_candidate and category.get("node_id") else "analysis.seller_sprite_validation.primary_market.label",
            },
            "category_path": {
                "value": category.get("category_path", ""),
                "source_path": f"{source_base}.category_path" if has_candidate and category.get("category_path") else "analysis.seller_sprite_validation.primary_market.label",
            },
            "top100_monthly_sales": {
                "value": category.get("top100_monthly_sales", primary.get("avg_monthly_units", "")),
                "source_path": f"{source_base}.top100_monthly_sales" if has_candidate and category.get("top100_monthly_sales") else "analysis.seller_sprite_validation.primary_market.avg_monthly_units",
            },
            "top100_monthly_revenue": {
                "value": category.get("top100_monthly_revenue", primary.get("avg_monthly_revenue_usd", "")),
                "source_path": f"{source_base}.top100_monthly_revenue" if has_candidate and category.get("top100_monthly_revenue") else "analysis.seller_sprite_validation.primary_market.avg_monthly_revenue_usd",
            },
            "product_count_in_category": {
                "value": category.get("product_count_in_category", category.get("matched_asin_count", primary.get("sample_count", ""))),
                "source_path": f"{source_base}.matched_asin_count" if has_candidate and category.get("matched_asin_count") else "analysis.seller_sprite_validation.primary_market.sample_count",
            },
            "representative_asins": representative_asins,
            "avg_price": {
                "value": category.get("avg_price", category.get("average_price", primary.get("avg_price_usd", ""))),
                "source_path": f"{source_base}.avg_price" if has_candidate and category.get("avg_price") else "analysis.seller_sprite_validation.primary_market.avg_price_usd",
            },
            "category_role": {
                "value": category.get("category_role") or category.get("category_fit", ""),
                "source_path": f"{source_base}.category_role" if has_candidate and category.get("category_role") else "analysis.seller_sprite_validation.primary_market.label",
            },
            "reason": category.get("reason") or category.get("recommended_use") or category.get("risk_tags") or "待AI结合 ASIN、类目和关键词证据补充判断理由。",
            "lineage": [source_base if has_candidate else "analysis.seller_sprite_validation.primary_market"],
        })

    return {
        "schema_version": "report-data-v1",
        "packet_id": "report_data",
        "run_id": run_id,
        "generated_at": analysis.get("created_at", ""),
        "snapshot_date": analysis.get("created_at", ""),
        "evidence_sources": _evidence_sources_from_analysis(analysis),
        "hero": {
            "verdict": report_verdict,
            "lead_analysis": lead_analysis,
            "evidence_sources": [
                row.get("name", "")
                for row in source_packets
                if isinstance(row, dict) and row.get("name")
            ],
            "metrics": metrics,
            "confidence": confidence,
            "data_freshness": "Sorftime实时 + 卖家精灵30天滚动",
        },
        "category_panorama": {
            "categories": categories,
            "sub_market": {
                "product_form": primary.get("label", top_cat.get("category_path", "")),
                "estimated_monthly_units": f"{primary.get('avg_monthly_units', '')} units" if primary.get("avg_monthly_units") else "待补",
                "estimated_monthly_revenue": f"${primary.get('avg_monthly_revenue_usd', '')}" if primary.get("avg_monthly_revenue_usd") else "待补",
                "source_path": "analysis.seller_sprite_validation.primary_market",
            },
            "market_health": {
                "top3_brand_share": primary.get("top3_brand_share", "待补"),
                "china_seller_share": primary.get("china_seller_share", "待补"),
                "new_3m_share": "待补",
                "concentration_note": "Top100 样本统计口径，不代表全类目。",
                "source_path": "analysis.seller_sprite_validation.primary_market",
            },
            "seasonality": {
                "peak_months": cat_seasonality.get("peak_months", []),
                "trough_months": cat_seasonality.get("trough_months", []),
                "peak_trough_ratio": cat_seasonality.get("peak_trough_ratio", "待补"),
                "source_path": "analysis.category_opportunity.category_seasonality",
            },
            "insights": [
                {"type": "good", "title": "类目市场信号", "body": "基于 Top100 样本数据分析，具体数值见下表。", "source_path": "__ai_judgment__"},
                {"type": "warn", "title": "关注点", "body": "样本统计口径为 Top100 产品，不代表全部市场情况。", "source_path": "__ai_judgment__"},
            ],
        },
        "data_sources": _data_sources_from_analysis(analysis),
        "competitors": competitors,
        "pain_points": pain_points,
        "price_bands": price_bands,
        "keywords": keywords,
        "risks": risks,
        "advantages": advantages,
        "gonogo_conditions": gonogo,
        "next_steps": next_steps,
    }


