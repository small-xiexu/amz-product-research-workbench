#!/usr/bin/env python3
"""Build analysis_packet from evidence packets — the intermediate traceability layer
between raw evidence and report_data.json."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from packages.research_core.pipeline.audit_run_status import audit_run_status
from packages.research_core.pipeline.constants import (
    REPORT_VERDICT_LABELS, ALLOWED_VERDICTS,
)
from packages.research_core.pipeline._utils import (
    _report_value, _source_packet_ref, load_json,
    first_text, first_dict, as_list, compact_list, join_text,
    public_text, first_row_text, numeric_value, fmt_number, fmt_percent, dedupe_rows,
)

def _find_product_excel(run_dir: Path) -> Path | None:
    """在 seller_sprite 输入目录中查找 Product Top100 Excel 文件。"""
    ss_dir = run_dir / "inputs" / "seller_sprite"
    if not ss_dir.exists():
        return None
    candidates = sorted(ss_dir.glob("Product-*.xlsx"))
    return candidates[0] if candidates else None


def _parse_product_top100(excel_path: Path) -> list[dict[str, Any]]:
    """从卖家精灵 Product Excel 解析 Top100 产品数据。"""
    try:
        import openpyxl
    except ImportError:
        return []
    try:
        wb = openpyxl.load_workbook(excel_path, read_only=True, data_only=True)
        ws = wb.active
        rows_iter = ws.iter_rows(values_only=True)
        headers = [str(c) if c else "" for c in next(rows_iter)]
        col_idx = {h: i for i, h in enumerate(headers)}
        products = []
        seen_asins: set[str] = set()
        for row in rows_iter:
            if not row or not row[0]:
                continue
            asin = str(row[col_idx.get("ASIN", 0)] or "").strip()
            if not asin or asin in seen_asins:
                continue
            seen_asins.add(asin)
            products.append({
                "asin": asin,
                "brand": str(row[col_idx.get("品牌", 3)] or "").strip(),
                "title": str(row[col_idx.get("商品标题", 5)] or "").strip(),
                "price": row[col_idx.get("价格($)", 22)],
                "monthly_units": row[col_idx.get("月销量", 16)],
                "monthly_revenue": row[col_idx.get("月销售额($)", 18)],
                "rating": row[col_idx.get("评分", 28)],
                "rating_count": row[col_idx.get("评分数", 26)],
                "listing_days": row[col_idx.get("上架天数", 34)],
                "bsr": row[col_idx.get("大类BSR", 11)],
                "seller": str(row[col_idx.get("卖家信息", 42)] or "").strip(),
                "delivery": str(row[col_idx.get("配送方式", 35)] or "").strip(),
            })
        wb.close()
        return products
    except Exception:
        return []


def _compute_price_bands(products: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """从产品列表按价格分段计算分布（价格带机会）。"""
    if not products:
        return []
    bands_def = [
        ("$0-10", 0, 10), ("$10-15", 10, 15), ("$15-20", 15, 20),
        ("$20-25", 20, 25), ("$25-30", 25, 30), ("$30+", 30, float("inf")),
    ]
    total_units = sum(p.get("monthly_units") or 0 for p in products)
    total_revenue = sum(p.get("monthly_revenue") or 0 for p in products)
    results = []
    for label, lo, hi in bands_def:
        band_products = [
            p for p in products
            if (p.get("price") or 0) >= lo and (p.get("price") or 0) < hi
        ]
        count = len(band_products)
        units = sum(p.get("monthly_units") or 0 for p in band_products)
        revenue = sum(p.get("monthly_revenue") or 0 for p in band_products)
        avg_reviews = (
            sum(p.get("rating_count") or 0 for p in band_products) / count
            if count > 0 else 0
        )
        unit_share = round(units / total_units, 4) if total_units else 0
        opportunity = "strong" if unit_share >= 0.20 else ("watch" if unit_share >= 0.10 else "weak")
        results.append({
            "price_band": label,
            "product_count": count,
            "sales_share": unit_share,
            "revenue_share": round(revenue / total_revenue, 4) if total_revenue else 0,
            "median_rating_count": round(avg_reviews),
            "opportunity_level": opportunity,
            "reason": f"{label} 价格段：{count}个产品，销量占比{round(unit_share*100, 1)}%",
        })
    # 添加柱高度（最高 = 100，CSS 中用作 px 值）
    max_count = max((b["product_count"] for b in results), default=1)
    for b in results:
        b["bar_height"] = round(b["product_count"] / max_count * 100) if max_count else 0
    return results

def load_packets(run_dir: Path) -> dict[str, Any]:
    paths = {
        "search_demand": run_dir / "search_demand" / "search_demand_evidence_packet.json",
        "market_structure": run_dir / "market_structure" / "market_structure_evidence_packet.json",
        "voc": run_dir / "review_voc" / "voc_evidence_packet.json",
        "route_matrix": run_dir / "route_matrix_confirm.json",
        "workflow_state": run_dir / "workflow_state.json",
    }
    packets: dict[str, Any] = {"paths": paths}
    for key, path in paths.items():
        packets[key] = load_json(path, required=key in {"search_demand", "market_structure"})
    if not packets.get("route_matrix"):
        packets["route_matrix"] = build_route_matrix_fallback(
            packets.get("workflow_state") or {},
            packets.get("market_structure") or {},
            packets.get("search_demand") or {},
        )
    return packets


def _extract_product_name(run_dir: Path) -> str:
    """从 run 目录名提取中文品名，用于报告文件命名。

    run 目录命名规范为 yyyymmdd_中文品类方向，去掉日期前缀即得品名。
    """
    return re.sub(r'^\d{8}_', '', run_dir.name)


def build_analysis_packet(run_dir: Path, packets: dict[str, Any]) -> dict[str, Any]:
    search = packets.get("search_demand") or {}
    market = packets.get("market_structure") or {}
    voc = packets.get("voc") or {}
    route_matrix = packets.get("route_matrix") or {}
    workflow_state = packets.get("workflow_state") or {}
    paths = packets["paths"]

    source_packets = [
        source_packet_row("Search Demand / Sorftime", paths["search_demand"], search),
        source_packet_row("Market Structure / 卖家精灵", paths["market_structure"], market),
        source_packet_row("VOC Evidence", paths["voc"], voc),
        source_packet_row("Route Matrix", paths["route_matrix"], route_matrix),
    ]
    search_validation = build_search_validation(search)
    market_validation = build_market_validation(market)
    _fill_market_validation_from_excel_if_empty(market_validation, run_dir)
    reference_asin_pool = build_reference_asin_pool(search, market, route_matrix)
    if not reference_asin_pool:
        reference_asin_pool = _build_reference_asin_pool_from_excel(run_dir)
    category_opportunity = build_category_opportunity(search, market, run_dir)
    keyword_pool = build_keyword_pool(search, market)
    voc_translation = build_voc_translation(voc)
    route_judgment = build_route_judgment(market, route_matrix, search)
    category_selection_derivation = build_category_selection_derivation(
        search,
        market,
        route_matrix,
        reference_asin_pool,
        category_opportunity,
        keyword_pool,
        workflow_state,
    )
    blocking_gaps = build_blocking_gaps(search, market, voc)
    verdict = decide_verdict(search_validation, market_validation, voc_translation, blocking_gaps)
    market_synthesis = build_market_synthesis(
        verdict,
        search_validation,
        market_validation,
        voc_translation,
        route_judgment,
        blocking_gaps,
    )
    analysis = {
        "packet_id": "analysis_packet",
        "packet_version": "market-precheck-v2",
        "stage": "market_precheck",
        "run_id": run_dir.name,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "verdict": verdict,
        "one_sentence_conclusion": one_sentence_conclusion(verdict, market_synthesis),
        "confidence": confidence_level(reference_asin_pool, keyword_pool, category_opportunity, voc_translation),
        "source_packets": source_packets,
        "independent_subagent_reviews": {},
        "category_selection_derivation": category_selection_derivation,
        "reference_asin_pool": reference_asin_pool,
        "category_opportunity": category_opportunity,
        "keyword_pool": keyword_pool,
        "search_market_validation": search_validation,
        "seller_sprite_validation": market_validation,
        "voc_spec_translation": voc_translation,
        "route_judgment": route_judgment,
        "market_synthesis": market_synthesis,
        "human_review_focus": build_human_review_focus(voc_translation, route_judgment, keyword_pool),
        "evidence_boundaries": build_evidence_boundaries(search, market, voc),
        "blocking_gaps": blocking_gaps,
        "next_stage_entry_conditions": build_next_stage_conditions(),
        "lineage": {
            "run_dir": str(run_dir),
            "source_packet_paths": {key: str(path) for key, path in paths.items()},
            "output_paths": {
                "report_data_seed": str(run_dir / "analysis" / "report_data.seed.json"),
                "report_data": str(run_dir / "analysis" / "report_data.json"),
                "html": str(run_dir / "analysis" / f"{_extract_product_name(run_dir)}_分析报告.html"),
                "xlsx": str(run_dir / "analysis" / f"{_extract_product_name(run_dir)}_数据回表.xlsx"),
                "qa": str(run_dir / "analysis" / "delivery_qa_result.json"),
            },
        },
    }
    analysis["run_status_audit"] = audit_run_status(run_dir)
    return analysis


def source_packet_row(name: str, path: Path, packet: dict[str, Any]) -> dict[str, Any]:
    provenance = packet.get("execution_provenance") if isinstance(packet.get("execution_provenance"), dict) else {}
    return {
        "name": name,
        "path": str(path),
        "exists": path.exists(),
        "packet_id": packet.get("packet_id", ""),
        "confidence": packet.get("confidence", packet.get("confidence_rationale", "")),
        "execution_mode": provenance.get("execution_mode", ""),
        "provenance_note": provenance.get("note") or provenance.get("subagent_note") or "",
    }


def build_route_matrix_fallback(workflow_state: dict[str, Any], market: dict[str, Any], search: dict[str, Any]) -> dict[str, Any]:
    known_inputs = workflow_state.get("known_inputs") if isinstance(workflow_state.get("known_inputs"), dict) else {}
    selected_route = first_text(
        known_inputs.get("confirmed_boundary"),
        known_inputs.get("confirmed_stage0_route"),
        market.get("summary"),
        search.get("summary"),
    )
    route_rows = as_list(market.get("route_market_fit"))
    return {
        "packet_id": "route_matrix_confirm_fallback",
        "selected_route": selected_route,
        "recommended_mainline": selected_route,
        "route_matrix": route_rows,
        "data_boundary": "route_matrix_confirm.json 缺失时的报告生成 fallback；正式交付建议补齐路线确认文件。",
    }


def build_search_validation(search: dict[str, Any]) -> dict[str, Any]:
    facts = as_list(search.get("facts"))
    keyword_rows = []
    traffic_rows = []
    feature_rows = []
    for fact in facts:
        source = str(fact.get("source", ""))
        row = {
            "id": fact.get("id", ""),
            "source": source,
            "subject": fact.get("subject", ""),
            "metric": fact.get("metric", ""),
            "value": fact.get("value", ""),
            "note": fact.get("note", ""),
        }
        if source.endswith("keyword_detail") or "keyword" in source:
            keyword_rows.append(row)
        elif "traffic" in source:
            traffic_rows.append(row)
        elif "feature" in source:
            feature_rows.append(row)
    keyword_demand = build_keyword_demand_rows(search, keyword_rows)
    return {
        "keyword_rows": keyword_rows,
        "traffic_rows": traffic_rows,
        "feature_rows": feature_rows,
        "keyword_demand": keyword_demand,
        "category_background": build_category_background_rows(search),
        "traffic_term_groups": build_traffic_term_groups(search, traffic_rows),
        "trend_signal": search.get("trend_signal") or {},
        "derived_metrics": as_list(search.get("derived_metrics")),
        "insights": as_list(search.get("insights_for_handoff")),
        "data_gaps": as_list(search.get("data_gaps")),
        "summary": search_summary(keyword_demand, search.get("derived_metrics"), search.get("insights_for_handoff")),
    }


def build_keyword_demand_rows(search: dict[str, Any], fallback_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for item in as_list(search.get("keyword_demand")):
        rows.append(
            {
                "keyword": item.get("keyword", ""),
                "monthly_search_volume": item.get("monthly_search_volume", ""),
                "cpc": item.get("cpc", ""),
                "competitor_count": item.get("competitor_count", ""),
                "seasonality": item.get("seasonality", ""),
                "route_relevance": item.get("route_relevance", item.get("interpretation", "")),
            }
        )
    if rows:
        return rows
    return [
        {
            "keyword": row.get("subject", ""),
            "monthly_search_volume": row.get("value", ""),
            "cpc": "",
            "competitor_count": "",
            "seasonality": "",
            "route_relevance": row.get("note", ""),
        }
        for row in fallback_rows
    ]


def build_category_background_rows(search: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for fact in as_list((search.get("category_match") or {}).get("facts")):
        value = fact.get("value") if isinstance(fact.get("value"), dict) else {}
        rows.append(
            {
                "category": fact.get("subject", ""),
                "node_id": value.get("nodeId", value.get("nodeid", "")),
                "top100_monthly_units": value.get("top100_monthly_units", value.get("Top100产品月销量", "")),
                "average_price_usd": value.get("average_price_usd", value.get("average_price", "")),
                "top3_share": value.get("top3_product_sales_volume_share", value.get("top3_product_units_share", "")),
                "low_review_share": value.get("low_reviews_sales_volume_share", ""),
                "interpretation": fact.get("interpretation", ""),
            }
        )
    return rows


def build_traffic_term_groups(search: dict[str, Any], fallback_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups = []
    for group in as_list(search.get("traffic_terms")):
        groups.append(
            {
                "route_id": group.get("route_id", ""),
                "traffic_read": group.get("traffic_read", ""),
                "asins": as_list(group.get("asins")),
            }
        )
    if groups:
        return groups
    return [
        {
            "route_id": row.get("subject", ""),
            "traffic_read": row.get("note", ""),
            "asins": [],
        }
        for row in fallback_rows
    ]


def search_summary(keyword_rows: list[dict[str, Any]], derived_metrics: Any, insights: Any) -> str:
    ranked = sorted(
        [row for row in keyword_rows if numeric_value(row.get("monthly_search_volume")) is not None],
        key=lambda row: numeric_value(row.get("monthly_search_volume")) or 0,
        reverse=True,
    )
    top = ranked[0] if ranked else (keyword_rows[0] if keyword_rows else {})
    cleaner_metric = next(
        (
            item
            for item in as_list(derived_metrics)
            if "quality" in str(item.get("name", "")).lower() or "keyword" in str(item.get("name", "")).lower()
        ),
        {},
    )
    insight = first_row_text(as_list(insights), "text")
    if top and cleaner_metric:
        return (
            f"Sorftime 显示核心词「{top.get('keyword')}」月搜约 {fmt_number(top.get('monthly_search_volume'))}；"
            f"关键词质量判断为：{cleaner_metric.get('value')}。{cleaner_metric.get('explanation') or top.get('route_relevance', '')}"
        )
    if top:
        return f"Sorftime 显示核心词「{top.get('keyword')}」月搜约 {fmt_number(top.get('monthly_search_volume'))}；{top.get('route_relevance', '')}"
    return insight or "Sorftime 已完成搜索需求复核，详见关键词、流量词和 data gaps。"


def build_market_validation(market: dict[str, Any]) -> dict[str, Any]:
    primary_market = ((market.get("market_size") or {}).get("primary_market") or {})
    # 回退：证据包可能把 category_name 放在顶层 market.primary_market
    top_pm = market.get("primary_market") or {}
    overview = primary_market.get("overview_all") or {}
    price_band = market.get("price_band") or {}
    grouped_price = price_band.get("primary_market_distribution_grouped") or {}
    review_metric = next(
        (
            metric
            for metric in as_list(market.get("derived_metrics"))
            if metric.get("id") == "dm_primary_review_threshold"
        ),
        {},
    )
    route_rows = as_list(market.get("route_market_fit"))
    return {
        "primary_market": {
            "label": primary_market.get("market_label") or primary_market.get("category_name") or top_pm.get("category_name") or "目标市场",
            "sample_count": overview.get("样本商品数", ""),
            "avg_monthly_units": overview.get("月均销量", ""),
            "avg_monthly_revenue_usd": overview.get("月均销售额($)", ""),
            "avg_price_usd": overview.get("平均价格($)", ""),
            "avg_rating": overview.get("平均星级", overview.get("平均评分", "")),
            "avg_rating_count": overview.get("平均评分数", ""),
            "return_rate": overview.get("同类目退货率", overview.get("退货率", "")),
        },
        "price_band": grouped_price,
        "review_threshold": (review_metric.get("values") or {}),
        "new_product_signal": market.get("new_product_signal") or {},
        "route_market_fit": route_rows,
        "keyword_competitor_validation": market.get("keyword_competitor_validation") or {},
        "derived_metrics": as_list(market.get("derived_metrics")),
        "insights": as_list(market.get("insights_for_handoff")),
        "data_gaps": as_list(market.get("data_gaps")),
        "summary": market_summary(overview, grouped_price, review_metric, route_rows),
    }


def market_summary(overview: dict[str, Any], grouped_price: dict[str, Any], review_metric: dict[str, Any], route_rows: list[dict[str, Any]]) -> str:
    under_15 = fmt_percent((grouped_price.get("under_15") or {}).get("unit_share"))
    over_30 = fmt_percent((grouped_price.get("30_plus") or {}).get("unit_share"))
    review_500 = fmt_percent(((review_metric.get("values") or {}).get("500_plus_reviews") or {}).get("unit_share"))
    return (
        f"卖家精灵主市场样本 {fmt_number(overview.get('样本商品数'))} 个，均价约 ${fmt_number(overview.get('平均价格($)'))}；"
        f"<$15 贡献销量 {under_15}，$30+ 贡献销量 {over_30}，500+ 评论商品贡献销量 {review_500}。"
        f"已按 {len(route_rows)} 条路线拆开看价格、销量和评论门槛。"
    )


def build_reference_asin_pool(search: dict[str, Any], market: dict[str, Any], route_matrix: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in as_list(market.get("reference_asin_pool")) + as_list(search.get("reference_asin_inputs")):
        if not isinstance(item, dict):
            continue
        asin = item.get("asin")
        if not asin:
            continue
        rows.append(
            {
                "asin": asin,
                "route_ref": item.get("route_ref") or item.get("route_id") or item.get("route_name", ""),
                "asin_role": item.get("asin_role") or item.get("role", ""),
                "similarity_reason": item.get("similarity_reason") or item.get("reason", ""),
                "category_path": item.get("category_path", ""),
                "price": item.get("price", item.get("price_usd", "")),
                "monthly_sales": item.get("monthly_sales", item.get("avg_monthly_units", "")),
                "rating_count": item.get("rating_count", item.get("reviews", "")),
            }
        )
    if rows:
        return dedupe_rows(rows, "asin")[:30]
    for route in as_list(market.get("route_market_fit")) + as_list(route_matrix.get("route_matrix")):
        for asin in as_list(route.get("representative_asins")):
            rows.append(
                {
                    "asin": asin,
                    "route_ref": route.get("route_name") or route.get("route_id", ""),
                    "asin_role": route.get("role_from_route_matrix", route.get("role", "代表样本")),
                    "similarity_reason": route.get("why", route.get("operator_read", "路线代表 ASIN")),
                    "category_path": "",
                    "price": "",
                    "monthly_sales": route.get("avg_monthly_units", ""),
                    "rating_count": route.get("median_rating_count", ""),
                }
            )
    return dedupe_rows(rows, "asin")[:30]


def _build_reference_asin_pool_from_excel(run_dir: Path) -> list[dict[str, Any]]:
    """从卖家精灵 Product Excel 中提取Top竞品作为参考ASIN池回退方案。"""
    product_path = _find_product_excel(run_dir)
    if not product_path:
        return []
    products = _parse_product_top100(product_path)
    if not products:
        return []
    # 按月销量降序排列，取前20个
    sorted_products = sorted(
        products, key=lambda p: p.get("monthly_units") or 0, reverse=True
    )
    rows = []
    for p in sorted_products[:20]:
        asin = p.get("asin", "")
        if not asin:
            continue
        monthly = p.get("monthly_units") or 0
        rating_count = p.get("rating_count") or 0
        role = "标杆老品" if rating_count >= 500 else ("近期新品" if (p.get("listing_days") or 999) <= 180 else "参考竞品")
        rows.append({
            "asin": asin,
            "route_ref": "",
            "asin_role": role,
            "similarity_reason": f"月销{monthly}，评论{rating_count}",
            "category_path": "",
            "price": p.get("price", ""),
            "monthly_sales": monthly,
            "rating_count": rating_count,
            "brand": p.get("brand", ""),
            "rating": p.get("rating", ""),
        })
    return rows


def _fill_market_validation_from_excel_if_empty(market_validation: dict[str, Any], run_dir: Path | None) -> None:
    """当证据包中 primary_market 数据为空时，从 Product Excel 回退计算。"""
    if not run_dir:
        return
    pm = market_validation.get("primary_market") or {}
    if pm.get("avg_price_usd") or pm.get("avg_monthly_units"):
        return

    product_path = _find_product_excel(run_dir)
    if not product_path:
        return
    products = _parse_product_top100(product_path)
    if not products:
        return

    prices = [p["price"] for p in products if p.get("price")]
    ratings = [p["rating"] for p in products if p.get("rating")]
    monthly_units = [p["monthly_units"] for p in products if p.get("monthly_units")]
    rating_counts = [p["rating_count"] for p in products if p.get("rating_count")]

    if monthly_units:
        pm["avg_monthly_units"] = int(sum(monthly_units))
        pm["sample_count"] = len(products)
    if prices:
        avg_p = sum(prices) / len(prices)
        pm["avg_price_usd"] = f"{avg_p:.2f}"
        if monthly_units and len(prices) == len(monthly_units):
            pm["avg_monthly_revenue_usd"] = f"{sum(p * u for p, u in zip(prices, monthly_units)) / len(products):.2f}"
    if ratings:
        pm["avg_rating"] = round(sum(ratings) / len(ratings), 1)
    if rating_counts:
        pm["avg_rating_count"] = int(sum(rating_counts) / len(rating_counts))
    if not pm.get("label") or pm["label"] == "目标市场":
        pm["label"] = "目标市场"


def build_category_opportunity(search: dict[str, Any], market: dict[str, Any], run_dir: Path | None = None) -> dict[str, Any]:
    category_candidates = normalize_category_candidates(search, market)
    price_band_opportunity = normalize_price_band_opportunity(market, run_dir)
    new_release_opportunity = score_new_release_opportunities(
        as_list(market.get("new_release_opportunity")) or as_list(market.get("new_product_signal"))
    )
    return {
        "category_candidates": category_candidates,
        "asin_category_mapping": as_list(market.get("asin_category_mapping")),
        "price_band_opportunity": price_band_opportunity,
        "new_release_opportunity": new_release_opportunity,
        "category_seasonality": normalize_category_seasonality(search, market),
        "summary": category_opportunity_summary(category_candidates, price_band_opportunity, new_release_opportunity),
    }


def normalize_category_candidates(search: dict[str, Any], market: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in as_list(market.get("category_candidates")) + as_list(search.get("category_candidates")):
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "category_name": item.get("category_name") or item.get("name") or item.get("category", ""),
                "node_id": item.get("node_id") or item.get("nodeId") or item.get("nodeid", ""),
                "category_path": item.get("category_path", ""),
                "category_role": item.get("category_role") or item.get("role", ""),
                "source_type": item.get("source_type", ""),
                "matched_asin_count": item.get("matched_asin_count", ""),
                "evidence_strength": item.get("evidence_strength", item.get("confidence", "")),
                "recommended_use": item.get("recommended_use", ""),
                "risk_tags": join_text(item.get("risk_tags")),
            }
        )
    if rows:
        return rows
    for fact in as_list((search.get("category_match") or {}).get("facts")):
        value = fact.get("value") if isinstance(fact.get("value"), dict) else {}
        rows.append(
            {
                "category_name": fact.get("subject", ""),
                "node_id": value.get("nodeId", value.get("nodeid", "")),
                "category_path": "",
                "category_role": "candidate",
                "source_type": "category_match",
                "matched_asin_count": "",
                "evidence_strength": "",
                "recommended_use": "needs_review",
                "risk_tags": "",
            }
        )
    return rows


def normalize_price_band_opportunity(market: dict[str, Any], run_dir: Path | None = None) -> list[dict[str, Any]]:
    rows = as_list(market.get("price_band_opportunity"))
    if rows:
        return rows
    grouped = ((market.get("price_band") or {}).get("primary_market_distribution_grouped") or {})
    normalized: list[dict[str, Any]] = []
    for band, value in grouped.items():
        if not isinstance(value, dict):
            continue
        normalized.append(
            {
                "category_ref": "primary_market",
                "price_band": band,
                "product_count": value.get("product_count", ""),
                "sales_share": value.get("unit_share", ""),
                "revenue_share": value.get("revenue_share", ""),
                "median_rating_count": value.get("median_rating_count", ""),
                "new_release_count": value.get("new_release_count", ""),
                "low_review_winner_count": value.get("low_review_winner_count", ""),
                "opportunity_level": value.get("opportunity_level", "watch"),
                "reason": value.get("reason", "价格带机会待结合竞品和关键词复核"),
            }
        )
    if not normalized and run_dir is not None:
        product_path = _find_product_excel(run_dir)
        if product_path:
            products = _parse_product_top100(product_path)
            normalized = _compute_price_bands(products)
    return normalized


def score_new_release_opportunities(rows: list[Any]) -> list[dict[str, Any]]:
    scored: list[dict[str, Any]] = []
    for raw in rows:
        if not isinstance(raw, dict):
            continue
        item = dict(raw)
        score = 0
        if numeric_value(item.get("new_release_count")) and numeric_value(item.get("new_release_count")) >= 3:
            score += 25
        if numeric_value(item.get("new_release_sales_share")) and numeric_value(item.get("new_release_sales_share")) >= 0.05:
            score += 30
        low_review_count = numeric_value(item.get("low_review_winner_count"))
        if low_review_count and low_review_count >= 2:
            score += 30
        item["new_release_opportunity_score"] = min(score, 100)
        item["new_release_opportunity_level"] = "strong" if score >= 65 else "watch" if score >= 30 else "weak"
        scored.append(item)
    return scored


def normalize_category_seasonality(search: dict[str, Any], market: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in as_list(search.get("category_seasonality")) + as_list(market.get("category_seasonality")):
        if isinstance(item, dict):
            rows.append(item)
    trend = search.get("trend_signal") if isinstance(search.get("trend_signal"), dict) else {}
    if trend and not rows:
        rows.append(
            {
                "category_ref": trend.get("category_ref", "category_trend"),
                "trend_source": "trend_signal",
                "peak_months": join_text(trend.get("peak_months")),
                "low_months": join_text(trend.get("low_months")),
                "seasonality_level": trend.get("seasonality_level", ""),
                "trend_direction": trend.get("trend_direction", ""),
                "category_seasonality_note": trend.get("summary", trend.get("handoff_read", "")),
            }
        )
    return rows


def category_opportunity_summary(categories: list[dict[str, Any]], price_bands: list[dict[str, Any]], new_release: list[dict[str, Any]]) -> str:
    subcats = [row for row in categories if str(row.get("category_role")) in {"subcategory_market", "小类"}]
    mixed = [row for row in categories if str(row.get("category_role")) in {"mixed_pool", "混池", "excluded", "排除"}]
    strong_bands = [row for row in price_bands if str(row.get("opportunity_level")) == "strong"]
    return (
        f"候选类目 {len(categories)} 个，其中小类候选 {len(subcats)} 个、混池/排除 {len(mixed)} 个；"
        f"价格带机会 {len(price_bands)} 段，强机会 {len(strong_bands)} 段；新品机会记录 {len(new_release)} 条。"
    )


def build_keyword_pool(search: dict[str, Any], market: dict[str, Any]) -> dict[str, Any]:
    explicit = search.get("keyword_pool") or search.get("keyword_pool_by_role")
    if isinstance(explicit, dict):
        roles = explicit.get("roles") if isinstance(explicit.get("roles"), dict) else explicit
        roles = normalize_keyword_roles(roles)
        return {"roles": roles, "mix_pool_summary": summarize_mix_pool(roles), "source": "search.keyword_pool"}
    roles: dict[str, list[dict[str, Any]]] = {
        "main_traffic": [],
        "conversion_quality": [],
        "precise_long_tail": [],
        "mixed_or_excluded": [],
    }
    for row in as_list(search.get("keyword_demand")) + as_list(market.get("aba_keywords")):
        if not isinstance(row, dict):
            continue
        keyword = row.get("keyword") or row.get("term") or row.get("关键词")
        if not keyword:
            continue
        role = str(row.get("role") or row.get("keyword_role") or "").lower()
        risk = str(row.get("risk") or row.get("mix_pool_risk") or "").lower()
        target = "mixed_or_excluded" if "mix" in role or "exclude" in role or risk in {"high", "高"} else "main_traffic"
        roles[target].append(
            {
                "keyword": keyword,
                "monthly_search_volume": row.get("monthly_search_volume", row.get("月搜索量", "")),
                "cpc": row.get("cpc", ""),
                "competitor_count": row.get("competitor_count", ""),
                "reason": row.get("reason", row.get("interpretation", "")),
                "recommended_action": row.get("recommended_action", ""),
            }
        )
    # Fallback: 从 core_keywords 结构中提取关键词
    core_kws = search.get("core_keywords") or {}
    if isinstance(core_kws, dict):
        for kw in as_list(core_kws.get("head_terms")):
            if isinstance(kw, dict) and kw.get("keyword"):
                roles["main_traffic"].append({
                    "keyword": kw.get("keyword", ""),
                    "monthly_search_volume": kw.get("search_volume", kw.get("monthly_search_volume", "")),
                    "cpc": kw.get("cpc", ""),
                    "competitor_count": kw.get("competitor_count", ""),
                    "reason": kw.get("route_relevance", ""),
                })
        for kw in as_list(core_kws.get("scenario_words")):
            if isinstance(kw, dict) and kw.get("keyword"):
                roles["conversion_quality"].append({
                    "keyword": kw.get("keyword", ""),
                    "monthly_search_volume": kw.get("search_volume", kw.get("monthly_search_volume", "")),
                    "cpc": kw.get("cpc", ""),
                    "reason": kw.get("route_relevance", "场景词"),
                })
        for kw in as_list(core_kws.get("competitor_words")):
            if isinstance(kw, dict) and kw.get("keyword"):
                roles["mixed_or_excluded"].append({
                    "keyword": kw.get("keyword", ""),
                    "monthly_search_volume": kw.get("search_volume", kw.get("monthly_search_volume", "")),
                    "cpc": kw.get("cpc", ""),
                    "reason": "竞品品牌词，排除",
                })
    return {"roles": roles, "mix_pool_summary": summarize_mix_pool(roles), "source": "search.keyword_demand / core_keywords"}


def normalize_keyword_roles(roles: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    normalized: dict[str, list[dict[str, Any]]] = {}
    for role, items in roles.items():
        role_key = str(role)
        rows: list[dict[str, Any]] = []
        for item in as_list(items):
            if not isinstance(item, dict):
                continue
            row = dict(item)
            if role_key == "mixed_or_excluded":
                row.setdefault("mix_pool_score", 80)
                row.setdefault("mix_pool_risk_level", "high")
                if "mix_pool_tags" in row and not row.get("risk_tags"):
                    row["risk_tags"] = row.get("mix_pool_tags")
            rows.append(row)
        normalized[role_key] = rows
    return normalized


def summarize_mix_pool(roles: dict[str, Any]) -> dict[str, int]:
    mixed = as_list(roles.get("mixed_or_excluded")) if isinstance(roles, dict) else []
    high = [row for row in mixed if "高" in join_text(row.get("risk_tags")) or str(row.get("risk", "")).lower() == "high"]
    return {"mixed_or_excluded_count": len(mixed), "high_risk_count": len(high), "medium_risk_count": max(0, len(mixed) - len(high))}


def build_voc_translation(voc: dict[str, Any]) -> dict[str, Any]:
    pain_rows = as_list(voc.get("pain_points_by_dimension"))
    if not pain_rows:
        # 回退：从 product_type_voc.*.top_pain_points 提取痛点
        ptv = voc.get("product_type_voc") or {}
        for _ptype, pdata in ptv.items():
            if not isinstance(pdata, dict):
                continue
            for pp in as_list(pdata.get("top_pain_points")):
                severity = pp.get("severity", "")
                priority = "P0" if severity == "critical" else ("P1" if severity == "high" else "P2")
                # 动态查找 implication_* 字段（字段名随产品变化）
                implication = ""
                for key, val in pp.items():
                    if key.startswith("implication_") and val:
                        implication = str(val)
                        break
                pain_rows.append({
                    "dimension": pp.get("pain", ""),
                    "issue": implication,
                    "review_count": pp.get("frequency", ""),
                    "spec_requirement": implication,
                    "evidence": pp.get("frequency", ""),
                    "priority": priority,
                })
    summary = voc.get("summary") if isinstance(voc.get("summary"), dict) else {}
    rows = []
    for item in pain_rows:
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "dimension": item.get("dimension", ""),
                "issue": item.get("issue") or item.get("pain_point") or item.get("summary", ""),
                "review_count": item.get("review_count", item.get("count", "")),
                "spec_requirement": join_text(item.get("spec_requirement")),
                "evidence": join_text(item.get("evidence_quotes") or item.get("evidence")),
                "evidence_refs": as_list(item.get("evidence_refs")),
                "next_check": join_text(item.get("next_check")),
                "priority": item.get("priority", ""),
            }
        )
    return {
        "review_count": summary.get("review_count") or (voc.get("review_scope") or {}).get("review_count", 0),
        "asin_count": summary.get("asin_count") or (voc.get("review_scope") or {}).get("asin_count", 0),
        "pain_points": rows,
        "summary": voc.get("summary_text") or voc_summary(rows, summary),
        "data_gaps": as_list(voc.get("data_gaps")),
    }


def voc_summary(rows: list[dict[str, Any]], summary: dict[str, Any]) -> str:
    if not rows:
        return "评论 VOC 尚未形成结构化痛点，只能先用市场和关键词做预审。"
    top = rows[0]
    return (
        f"VOC 覆盖 {fmt_number(summary.get('review_count'))} 条评论、{fmt_number(summary.get('asin_count'))} 个 ASIN；"
        f"高频痛点包括：{top.get('dimension') or top.get('issue')}。"
    )


def build_route_judgment(market: dict[str, Any], route_matrix: dict[str, Any], search: dict[str, Any]) -> list[dict[str, Any]]:
    rows = as_list(route_matrix.get("route_matrix")) or as_list(market.get("route_market_fit")) or as_list(search.get("route_market_fit"))
    result: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        role = row.get("recommended_role") or row.get("role") or ("主线候选" if index == 0 else "观察")
        result.append(
            {
                "route_name": row.get("route_name") or row.get("name") or row.get("category_name") or f"路线 {index + 1}",
                "role": role,
                "price_range": row.get("price_range", ""),
                "market_signal": row.get("market_signal") or row.get("operator_read") or row.get("why", ""),
                "keyword_signal": row.get("keyword_signal") or row.get("traffic_read", ""),
                "voc_signal": row.get("voc_signal") or row.get("voc_read", ""),
                "risk_note": row.get("risk_note") or row.get("risk", ""),
                "next_check": row.get("next_check") or "继续补齐该路线的类目 Top100、代表 ASIN、关键词和 VOC 样本。",
            }
        )
    return result[:12]


def build_category_selection_derivation(
    search: dict[str, Any],
    market: dict[str, Any],
    route_matrix: dict[str, Any],
    reference_asins: list[dict[str, Any]],
    category_opportunity: dict[str, Any],
    keyword_pool: dict[str, Any],
    workflow_state: dict[str, Any],
) -> dict[str, Any]:
    explicit = first_dict(
        search.get("category_selection_derivation"),
        market.get("category_selection_derivation"),
        route_matrix.get("category_selection_derivation"),
    )
    if explicit:
        return {
            "selected_category": first_text(explicit.get("selected_category"), explicit.get("selected_route"), explicit.get("mainline"), explicit.get("category")),
            "confidence": explicit.get("confidence", "medium"),
            "steps": as_list(explicit.get("steps")),
            "rejected_alternatives": as_list(explicit.get("rejected_alternatives")),
            "disconfirming_evidence": as_list(explicit.get("disconfirming_evidence")),
            "source_refs": as_list(explicit.get("source_refs")),
        }

    known_inputs = workflow_state.get("known_inputs") if isinstance(workflow_state.get("known_inputs"), dict) else {}
    categories = as_list(category_opportunity.get("category_candidates"))
    primary_categories = [
        row for row in categories
        if str(row.get("category_role") or row.get("role")).lower() not in {"mixed_pool", "excluded", "排除", "混池"}
    ]
    rejected_categories = [
        row for row in categories
        if str(row.get("category_role") or row.get("role")).lower() in {"mixed_pool", "excluded", "排除", "混池"}
    ]
    keyword_roles = keyword_pool.get("roles") if isinstance(keyword_pool.get("roles"), dict) else {}
    keyword_count = sum(len(as_list(rows)) for rows in keyword_roles.values())
    main_keywords = as_list(keyword_roles.get("main_traffic")) + as_list(keyword_roles.get("conversion_quality"))
    mixed_keywords = as_list(keyword_roles.get("mixed_or_excluded"))
    selected_category = first_text(
        route_matrix.get("selected_route"),
        route_matrix.get("recommended_mainline"),
        known_inputs.get("confirmed_boundary"),
        known_inputs.get("confirmed_stage0_route"),
        category_opportunity.get("summary"),
    )
    steps = [
        derivation_step(
            "用户约束",
            compact_list([
                known_inputs.get("scenario"),
                known_inputs.get("site"),
                join_text(known_inputs.get("constraints")),
                known_inputs.get("price_preference"),
            ]),
            "先限定站点、场景、禁区和偏好，避免从泛词直接跳到结论。",
            "只保留符合本轮边界的产品路线。",
            ["workflow_state.known_inputs"],
        ),
        derivation_step(
            "类目候选",
            [f"候选类目 {len(categories)} 个", f"可用/观察类目 {len(primary_categories)} 个", f"混池/排除类目 {len(rejected_categories)} 个"],
            "类目需要由参考 ASIN、nodeId 和市场结构共同确认。",
            "优先分析有代表 ASIN 和 Top100 结构支撑的小类。",
            ["category_opportunity.category_candidates"],
        ),
        derivation_step(
            "参考 ASIN",
            [f"参考 ASIN {len(reference_asins)} 个"],
            "相似竞品证明这个方向不是抽象关键词。",
            "用参考 ASIN 反推类目、价格带、评论门槛和关键词池。",
            ["reference_asin_pool"],
        ),
        derivation_step(
            "关键词交叉",
            [f"关键词池 {keyword_count} 条", f"主/转化词 {len(main_keywords)} 条", f"混池/排除词 {len(mixed_keywords)} 条"],
            "关键词用于验证需求入口和污染边界，不单独定义市场。",
            "把词拆成主词、转化词、长尾词和混池/排除词。",
            ["keyword_pool.roles"],
        ),
        derivation_step(
            "市场收敛",
            compact_list([category_opportunity.get("summary"), market.get("summary"), search.get("summary")]),
            "只有类目、ASIN、关键词和市场结构能互相解释时，才升级为主线。",
            "保留当前最完整路线，同时列出反证和待补项。",
            ["category_opportunity.summary", "market.summary", "search.summary"],
        ),
    ]
    return {
        "selected_category": selected_category or "待确认",
        "confidence": confidence_from_counts(reference_asins, primary_categories, main_keywords, mixed_keywords),
        "steps": steps,
        "rejected_alternatives": build_rejected_alternative_rows(rejected_categories, mixed_keywords),
        "disconfirming_evidence": build_disconfirming_evidence(reference_asins, primary_categories, main_keywords, mixed_keywords),
        "source_refs": ["workflow_state.known_inputs", "category_opportunity.category_candidates", "reference_asin_pool", "keyword_pool.roles"],
    }


def derivation_step(name: str, evidence: list[str], implication: str, decision: str, lineage: list[str]) -> dict[str, Any]:
    evidence = compact_list(evidence)
    return {
        "name": name,
        "evidence": evidence,
        "implication": implication,
        "decision": decision,
        "lineage": lineage,
        "evidence_points": [
            {"fact": fact, "meaning": implication, "action": decision, "lineage": lineage}
            for fact in evidence[:4]
        ],
    }


def build_rejected_alternative_rows(categories: list[Any], mixed_keywords: list[Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in categories[:6]:
        if isinstance(item, dict):
            rows.append(
                {
                    "name": item.get("category_name") or item.get("name") or item.get("category") or "混池类目",
                    "reason": item.get("recommended_use") or item.get("risk_tags") or "类目角色被标为混池或排除。",
                    "decision": "不作为主线，只作对照或排除。",
                }
            )
    for item in mixed_keywords[:6]:
        if isinstance(item, dict):
            rows.append(
                {
                    "name": item.get("keyword") or item.get("term") or "混池关键词",
                    "reason": item.get("reason") or item.get("mix_pool_tags") or "关键词意图较宽或指向非目标产品形态。",
                    "decision": item.get("recommended_action") or "不作为主市场词。",
                }
            )
    return rows[:10]


def build_disconfirming_evidence(reference_asins: list[dict[str, Any]], categories: list[Any], main_keywords: list[Any], mixed_keywords: list[Any]) -> list[dict[str, str]]:
    return [
        {
            "risk": "参考 ASIN 代表性不足",
            "would_change_decision_if": "核心 ASIN 的类目、产品形态或使用场景与主线不相似。",
            "next_check": "补 Top5/Top10 代表 ASIN 并重新反推类目和词表。",
            "current_signal": f"当前参考 ASIN {len(reference_asins)} 个。",
        },
        {
            "risk": "候选类目不收敛",
            "would_change_decision_if": "候选小类分散、nodeId 冲突或主要销量来自混池类目。",
            "next_check": "用 ASIN 类目路径、BSR、SellerSprite 选市场和 Sorftime category_report 交叉确认。",
            "current_signal": f"当前可用类目 {len(categories)} 个。",
        },
        {
            "risk": "主词被混池污染",
            "would_change_decision_if": "主流量词自然位主要由非目标形态、耗材、液体、配件或强品牌占据。",
            "next_check": "保留混池词为排除证据，改用更干净的场景词/形态词验证。",
            "current_signal": f"主/转化词 {len(main_keywords)} 条，混池/排除词 {len(mixed_keywords)} 条。",
        },
        {
            "risk": "VOC 不能解释市场机会",
            "would_change_decision_if": "差评痛点与目标路线无关，或痛点无法转成可验证的规格要求。",
            "next_check": "补路线级 VOC 样本，确认痛点、卖点和规格验证项是否一致。",
            "current_signal": "Stage 7 只做市场预审，不直接输出下单判断。",
        },
    ]


def build_blocking_gaps(search: dict[str, Any], market: dict[str, Any], voc: dict[str, Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []

    def add_gap(source: str, gap: Any, impact: Any = "") -> None:
        text = public_text(gap)
        if not text:
            return
        rows.append({"source": source, "gap": text, "impact": public_text(impact) or "会影响市场判断置信度。"})

    for gap in as_list(search.get("data_gaps"))[:8]:
        add_gap("搜索需求", gap.get("gap", gap) if isinstance(gap, dict) else gap, gap.get("impact", "") if isinstance(gap, dict) else "")
    for gap in as_list(market.get("data_gaps"))[:8]:
        add_gap("市场结构", gap.get("gap", gap) if isinstance(gap, dict) else gap, gap.get("impact", "") if isinstance(gap, dict) else "")
    for gap in as_list(voc.get("data_gaps"))[:8]:
        add_gap("VOC", gap.get("gap", gap) if isinstance(gap, dict) else gap, gap.get("impact", "") if isinstance(gap, dict) else "")
    if not as_list((voc.get("summary") or {}).get("review_count")) and not (voc.get("review_scope") or {}).get("review_count"):
        add_gap("VOC", "路线级评论样本不足或未接入", "无法判断真实痛点是否能支撑产品规格机会。")
    return dedupe_rows(rows, "gap")[:16]


def build_evidence_boundaries(search: dict[str, Any], market: dict[str, Any], voc: dict[str, Any]) -> list[dict[str, str]]:
    boundaries = [
        {
            "source": "市场结构",
            "boundary": "大类和小类市场分析只能说明体量、集中度、价格带和新品友好度。",
            "action": "是否进入产品定义，需要继续结合代表 ASIN、关键词和 VOC。",
        },
        {
            "source": "搜索需求",
            "boundary": "关键词搜索量不等于可做市场，泛词和工具词可能混池。",
            "action": "主词必须被类目、ASIN 和自然位共同解释。",
        },
        {
            "source": "VOC",
            "boundary": "评论痛点只代表样本商品的真实反馈，不自动等于全部市场需求。",
            "action": "痛点要转成规格假设，再用更多竞品和样品验证。",
        },
    ]
    for packet_name, packet in (("搜索需求", search), ("市场结构", market), ("VOC", voc)):
        for gap in as_list(packet.get("data_gaps"))[:3]:
            boundaries.append(
                {
                    "source": packet_name,
                    "boundary": public_text(gap.get("gap", gap) if isinstance(gap, dict) else gap),
                    "action": public_text(gap.get("next_step", gap.get("impact", "")) if isinstance(gap, dict) else "") or "作为数据边界保留。",
                }
            )
    return boundaries[:12]


def build_next_stage_conditions() -> list[dict[str, str]]:
    return [
        {"condition": "大类市场规模、集中度、价格带和新品样本已复核", "status": "必需", "why": "先判断赛道是否值得继续，不把单个 SKU 问题提前放大。"},
        {"condition": "候选小类的 Top100 和代表 ASIN 路径能互相解释", "status": "必需", "why": "确认小类机会和混池边界。"},
        {"condition": "主词、转化词、长尾词和排除词分层清楚", "status": "必需", "why": "避免用泛词或混池词做市场规模判断。"},
        {"condition": "VOC 样本能转成明确规格假设", "status": "建议", "why": "把用户痛点转成可验证的产品方向。"},
    ]


def build_human_review_focus(voc_translation: dict[str, Any], route_judgment: list[dict[str, Any]], keyword_pool: dict[str, Any]) -> list[dict[str, str]]:
    focuses = [
        {
            "focus": "先确认主路线和候选小类是否一致",
            "why": "路线名、类目节点和代表 ASIN 不一致时，后面的销量和关键词会被拉偏。",
            "evidence": "看品类推导链路、类目候选和参考 ASIN 池。",
        },
        {
            "focus": "检查混池/排除词是否过宽",
            "why": "如果主词首页主要是非目标形态，就不能把该词全部搜索量算给本方向。",
            "evidence": f"当前混池/排除词 {len(as_list((keyword_pool.get('roles') or {}).get('mixed_or_excluded')))} 条。",
        },
    ]
    if voc_translation.get("pain_points"):
        top = voc_translation["pain_points"][0]
        focuses.append(
            {
                "focus": f"把 VOC 痛点「{top.get('dimension') or top.get('issue')}」转成规格假设",
                "why": "只有能变成可验证规格，VOC 才是机会，不只是吐槽。",
                "evidence": top.get("spec_requirement") or top.get("evidence") or "VOC 结构化痛点。",
            }
        )
    if route_judgment:
        focuses.append(
            {
                "focus": f"优先复核「{route_judgment[0].get('route_name')}」路线",
                "why": "当前路线级证据相对集中，适合作为下一轮小类市场分析入口。",
                "evidence": route_judgment[0].get("market_signal") or route_judgment[0].get("keyword_signal") or "",
            }
        )
    return focuses[:8]


def decide_verdict(search_validation: dict[str, Any], market_validation: dict[str, Any], voc_translation: dict[str, Any], gaps: list[dict[str, str]]) -> str:
    market_has_primary = bool((market_validation.get("primary_market") or {}).get("sample_count"))
    keyword_count = len(as_list(search_validation.get("keyword_demand")))
    review_count = numeric_value(voc_translation.get("review_count")) or 0
    high_gap_count = sum(1 for gap in gaps if any(word in gap.get("gap", "") for word in ("缺失", "不足", "未接入", "不收敛")))
    if not market_has_primary or keyword_count == 0:
        return "暂缓"
    if high_gap_count >= 2 or review_count == 0:
        return "谨慎继续"
    return "继续看"


def build_market_synthesis(
    verdict: str,
    search_validation: dict[str, Any],
    market_validation: dict[str, Any],
    voc_translation: dict[str, Any],
    route_judgment: list[dict[str, Any]],
    gaps: list[dict[str, str]],
) -> dict[str, Any]:
    top_route = route_judgment[0] if route_judgment else {}
    top_gap = gaps[0] if gaps else {}
    has_gaps = bool(gaps)
    return {
        "verdict": verdict,
        "market_read": market_validation.get("summary", ""),
        "demand_read": search_validation.get("summary", ""),
        "voc_read": voc_translation.get("summary", ""),
        "route_read": top_route.get("market_signal") or top_route.get("keyword_signal") or "路线判断待补。",
        "key_risk": top_gap.get("gap", "当前无硬阻塞，数据支撑充分。") if has_gaps else "当前无硬阻塞，数据支撑充分。",
        "next_move": next_move_for_verdict(verdict, has_gaps),
        "analysis_cards": [
            {"title": "市场是否值得继续看", "body": market_validation.get("summary", "")},
            {"title": "需求入口是否成立", "body": search_validation.get("summary", "")},
            {"title": "产品机会在哪里", "body": voc_translation.get("summary", "")},
            {"title": "还需什么才能推进产品",
             "body": top_gap.get("gap", "市场证据充分，下一步需供应商打样验证核心痛点是否可解决。") if has_gaps
             else "市场证据充分，下一步需供应商打样验证核心痛点是否可解决。"},
        ],
    }


def next_move_for_verdict(verdict: str, has_gaps: bool = True) -> str:
    if verdict == "继续看":
        if has_gaps:
            return "补齐剩余数据缺口后，可进入产品定义阶段。"
        return "市场预审完成，建议运营审阅报告后决定是否启动供应商打样和产品定义。"
    if verdict == "谨慎继续":
        return "先补齐缺口，再决定是否进入小类深挖。"
    return "暂停推进，优先修正类目、关键词或代表 ASIN 边界。"


def one_sentence_conclusion(verdict: str, synthesis: dict[str, Any]) -> str:
    return f"{verdict}：{synthesis.get('market_read', '')} {synthesis.get('key_risk', '')}".strip()


def confidence_level(reference_asins: list[dict[str, Any]], keyword_pool: dict[str, Any], category_opportunity: dict[str, Any], voc_translation: dict[str, Any]) -> str:
    roles = keyword_pool.get("roles") if isinstance(keyword_pool.get("roles"), dict) else {}
    keyword_count = sum(len(as_list(rows)) for rows in roles.values())
    category_count = len(as_list(category_opportunity.get("category_candidates")))
    review_count = numeric_value(voc_translation.get("review_count")) or 0
    score = int(len(reference_asins) >= 5) + int(keyword_count >= 8) + int(category_count >= 2) + int(review_count >= 50)
    if score >= 3:
        return "high"
    if score >= 2:
        return "medium"
    return "low"


def confidence_from_counts(reference_asins: list[dict[str, Any]], categories: list[Any], main_keywords: list[Any], mixed_keywords: list[Any]) -> str:
    score = int(len(reference_asins) >= 5) + int(bool(categories)) + int(bool(main_keywords)) + int(bool(mixed_keywords))
    if score >= 4:
        return "high"
    if score >= 2:
        return "medium"
    return "low"
