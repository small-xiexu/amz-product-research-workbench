#!/usr/bin/env python3
"""Build a Stage 7 market precheck report from market, search and VOC evidence."""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import re
from typing import Any


from packages.report_renderer.xlsx_writer import write_xlsx
from packages.research_core.pipeline.audit_run_status import audit_run_status


ALLOWED_VERDICTS = {"继续看", "谨慎继续", "暂缓"}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Stage 7 market precheck report.")
    parser.add_argument("run_dir", help="Run directory, for example runs/<run_id>.")
    return parser.parse_args(argv)


def seed_report_data_from_analysis(analysis: dict[str, Any]) -> dict[str, Any]:
    """从脚本分析 dict 生成初始 report_data.json，供 AI 增强。"""
    run_id = analysis.get("run_id", "")
    verdict_raw = analysis.get("verdict", "")
    confidence = analysis.get("confidence", "")
    one_sentence = analysis.get("one_sentence_conclusion", "")
    market = analysis.get("seller_sprite_validation") or {}
    cat_opp = analysis.get("category_opportunity") or {}
    voc_spec = analysis.get("voc_spec_translation") or {}
    kw_pool = analysis.get("keyword_pool") or {}
    synthesis = analysis.get("market_synthesis") or {}
    primary = market.get("primary_market") or {}
    price_bands_raw = cat_opp.get("price_band_opportunity") or []
    cat_candidates = cat_opp.get("category_candidates") or []
    gaps = analysis.get("blocking_gaps") or []
    next_conditions = analysis.get("next_stage_entry_conditions") or []

    # Category
    top_cat = cat_candidates[0] if cat_candidates else {}
    overview = primary.get("overview_all") or {}

    # Price bands
    price_bands = []
    for pb in price_bands_raw:
        price_bands.append({
            "band": pb.get("price_band", ""),
            "label": pb.get("price_band", ""),
            "unit_share": pb.get("sales_share", ""),
            "product_count": pb.get("product_count", ""),
            "opportunity_level": pb.get("opportunity_level", ""),
            "reason": pb.get("reason", ""),
            "recommendation": "",
            "source_path": "analysis.category_opportunity.price_band_opportunity",
        })

    # Competitors
    competitors = []
    for asin in analysis.get("reference_asin_pool") or []:
        competitors.append({
            "asin": asin.get("asin", ""),
            "route": asin.get("route_ref", ""),
            "brand": asin.get("brand", ""),
            "price": asin.get("price", ""),
            "monthly_sales": asin.get("monthly_sales", ""),
            "rating": asin.get("rating", ""),
            "rating_count": asin.get("rating_count", ""),
            "positioning": asin.get("similarity_reason", ""),
            "source_path": "analysis.reference_asin_pool",
        })

    # Pain points
    pain_points = []
    for pp in voc_spec.get("pain_points") or []:
        pain_points.append({
            "priority": pp.get("priority", "P1"),
            "dimension": pp.get("dimension", ""),
            "review_count": pp.get("review_count", ""),
            "asins_affected": pp.get("asins_affected", ""),
            "issue": pp.get("issue", ""),
            "spec_requirement": pp.get("spec_requirement", ""),
            "source_path": "analysis.voc_spec_translation",
        })

    # Keywords
    keywords = []
    roles = kw_pool.get("roles") or {}
    if isinstance(roles, dict):
        for role, items in roles.items():
            for item in (items if isinstance(items, list) else [items]):
                if isinstance(item, dict):
                    keywords.append({
                        "keyword": item.get("keyword", item.get("term", "")),
                        "monthly_searches": item.get("monthly_search_volume", ""),
                        "cpc": item.get("cpc", ""),
                        "intent": role,
                        "route": "",
                        "source_path": "analysis.keyword_pool",
                    })

    # Risks
    risks = []
    for gap in gaps:
        risks.append({
            "severity": "medium",
            "title": gap.get("gap", ""),
            "detail": gap.get("impact", ""),
            "mitigation": "",
            "source_path": "analysis.blocking_gaps",
        })

    # Advantages (placeholder)
    advantages = [{"title": "待AI分析补充", "detail": "", "source_path": ""}]

    # Go/No-Go
    gonogo = []
    for cond in next_conditions:
        gonogo.append({
            "condition": cond.get("condition", ""),
            "status": cond.get("status", "must"),
            "detail": cond.get("why", ""),
            "source_path": "analysis.next_stage_entry_conditions",
        })

    # Next steps
    next_steps = [{"step": "联系供应商打样，基于VOC痛点制定品质标准", "detail": voc_spec.get("summary", ""), "source_path": ""}]

    # Hero metrics
    metrics = {
        "target_market": {"label": "目标市场", "value": primary.get("category_name", top_cat.get("category_name", "")), "source_path": "analysis.seller_sprite_validation.primary_market"},
        "monthly_demand": {"label": "月销", "value": f"{primary.get('avg_monthly_units', '')} units", "source_path": "analysis.seller_sprite_validation.primary_market"},
        "core_search_volume": {"label": "核心词月搜", "value": "待补", "source_path": ""},
        "avg_price": {"label": "均价", "value": f"${primary.get('avg_price_usd', '')}", "source_path": "analysis.seller_sprite_validation.primary_market"},
        "recommended_price": {"label": "推荐定价", "value": "待补", "source_path": ""},
        "avg_rating": {"label": "类目均分", "value": primary.get("avg_rating", ""), "source_path": "analysis.seller_sprite_validation.primary_market"},
    }

    return {
        "run_id": run_id,
        "snapshot_date": analysis.get("created_at", ""),
        "hero": {
            "verdict": verdict_raw,
            "one_sentence": one_sentence,
            "metrics": metrics,
            "confidence": confidence,
            "data_freshness": "Sorftime实时 + 卖家精灵30天滚动",
        },
        "category_panorama": {
            "selected_category": {
                "name": top_cat.get("category_name", ""),
                "node_id": top_cat.get("node_id", ""),
                "monthly_units": primary.get("avg_monthly_units", ""),
                "monthly_revenue": primary.get("avg_monthly_revenue_usd", ""),
                "avg_price": primary.get("avg_price_usd", ""),
                "avg_rating": primary.get("avg_rating", ""),
                "return_rate": primary.get("return_rate", ""),
                "source_path": "analysis.seller_sprite_validation.primary_market",
            },
            "sub_market": {"product_form": top_cat.get("category_path", ""), "estimated_monthly_units": "待补", "estimated_monthly_revenue": "待补", "source_path": ""},
            "market_health": {"top3_brand_share": "待补", "china_seller_share": "待补", "new_3m_share": "待补", "concentration_note": "待补", "source_path": ""},
            "seasonality": {"peak_months": [], "trough_months": [], "peak_trough_ratio": "待补", "source_path": ""},
            "insights": [
                {"type": "good", "title": "待AI分析", "body": "", "source_path": ""},
                {"type": "warn", "title": "待AI分析", "body": "", "source_path": ""},
            ],
        },
        "competitors": competitors,
        "pain_points": pain_points,
        "price_bands": price_bands,
        "keywords": keywords,
        "risks": risks,
        "advantages": advantages,
        "gonogo_conditions": gonogo,
        "next_steps": next_steps,
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    run_dir = Path(args.run_dir).expanduser().resolve()
    if not run_dir.exists():
        raise FileNotFoundError(f"run_dir not found: {run_dir}")

    packets = load_packets(run_dir)
    analysis = build_analysis_packet(run_dir, packets)
    analysis_dir = run_dir / "analysis"
    analysis_dir.mkdir(parents=True, exist_ok=True)

    product_name = _extract_product_name(run_dir)
    report_data_path = analysis_dir / "report_data.json"
    html_path = analysis_dir / f"{product_name}_分析报告.html"
    xlsx_path = analysis_dir / f"{product_name}_数据回表.xlsx"
    qa_path = analysis_dir / "delivery_qa_result.json"

    # report_data.json 是唯一数据中枢。HTML 和 XLSX 均从此文件生成。
    if not report_data_path.exists():
        seed = seed_report_data_from_analysis(analysis)
        report_data_path.write_text(json.dumps(seed, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Wrote seed {report_data_path} (待 AI 增强后重跑脚本同步 XLSX)")
    write_xlsx(xlsx_path, xlsx_sheets_from_report_data(report_data_path))
    qa = run_delivery_qa(report_data_path, html_path, xlsx_path, analysis)
    qa_path.write_text(json.dumps(qa, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Wrote {report_data_path}")
    print(f"Wrote {xlsx_path}")
    print(f"Wrote {qa_path}")
    if html_path.exists():
        print(f"HTML exists (AI-written): {html_path}")
    else:
        print(f"HTML MISSING — AI must write: {html_path}")
    return 0 if qa.get("status") == "pass" else 1


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


def load_json(path: Path, required: bool = True) -> dict[str, Any]:
    if not path.exists():
        if required:
            raise FileNotFoundError(path)
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"JSON root must be object: {path}")
    return data


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
    reference_asin_pool = build_reference_asin_pool(search, market, route_matrix)
    category_opportunity = build_category_opportunity(search, market)
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
            "label": primary_market.get("market_label") or "目标市场",
            "sample_count": overview.get("样本商品数", ""),
            "avg_monthly_units": overview.get("月均销量", ""),
            "avg_monthly_revenue_usd": overview.get("月均销售额($)", ""),
            "avg_price_usd": overview.get("平均价格($)", ""),
            "avg_rating_count": overview.get("平均评分数", ""),
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


def build_category_opportunity(search: dict[str, Any], market: dict[str, Any]) -> dict[str, Any]:
    category_candidates = normalize_category_candidates(search, market)
    price_band_opportunity = normalize_price_band_opportunity(market)
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


def normalize_price_band_opportunity(market: dict[str, Any]) -> list[dict[str, Any]]:
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
        "long_tail": [],
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
    return {"roles": roles, "mix_pool_summary": summarize_mix_pool(roles), "source": "search.keyword_demand / market.aba_keywords"}


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


def xlsx_sheets_from_report_data(report_data_path: Path) -> list[tuple[str, list[list[object]]]]:
    """从 AI 手写的 report_data.json 重建 XLSX，保证与 HTML 数据一致。"""
    rd = json.loads(report_data_path.read_text(encoding="utf-8"))
    hero = rd.get("hero") or {}
    verdict = hero.get("verdict", "")
    if isinstance(verdict, dict):
        verdict = verdict.get("value", verdict.get("label", str(verdict)))
    one_sentence = hero.get("one_sentence", "")
    if isinstance(one_sentence, dict):
        one_sentence = one_sentence.get("value", str(one_sentence))
    cp = rd.get("category_panorama") or {}
    cat = cp.get("selected_category") or {}
    sub = cp.get("sub_market") or {}
    health = cp.get("market_health") or {}
    season = cp.get("seasonality") or {}

    def _as_list(val: Any) -> list[Any]:
        if val is None:
            return []
        if isinstance(val, list):
            return val
        if isinstance(val, dict):
            # dict-of-lists pattern: {"main_attack": [...], "testable": [...]}
            if any(isinstance(v, list) for v in val.values()):
                result = []
                for v in val.values():
                    if isinstance(v, list):
                        result.extend(v)
                return result
            # wrapper pattern: {"market": "...", "list": [...]}
            if "list" in val:
                inner = val["list"]
                return inner if isinstance(inner, list) else [inner]
            # data-as-values pattern: {"step1": {...}, "step2": {...}}
            return list(val.values())
        return [val]

    def _next_move() -> str:
        steps = rd.get("next_steps") or {}
        if isinstance(steps, dict):
            inner = steps.get("steps") or steps.get("list") or []
            if isinstance(inner, list):
                steps = inner
            else:
                steps = list(steps.values())
        if isinstance(steps, list) and steps:
            return " → ".join(
                (s.get("action", s.get("step", "")) if isinstance(s, dict) else str(s))
                for s in steps[:3]
            )
        return "联系供应商打样 → 样品实测 → 准备Listing"

    # 1. Summary
    summary = [
        ["field", "value"],
        ["run_id", rd.get("run_id", "")],
        ["verdict", verdict],
        ["confidence", hero.get("confidence", "")],
        ["one_sentence_conclusion", one_sentence],
        ["next_move", _next_move()],
    ]

    # 2. Source Packets
    source_packets = [
        ["name", "exists", "packet_id", "confidence", "path"],
        ["Search Demand / Sorftime", "True", "search_demand_evidence", "medium", "search_demand/search_demand_evidence_packet.json"],
        ["Market Structure / 卖家精灵", "True", "market_structure_evidence", "medium", "market_structure/market_structure_evidence_packet.json"],
        ["VOC Evidence", "True", "voc_evidence", "high", "review_voc/voc_evidence_packet.json"],
        ["Route Matrix", "True", "route_matrix_confirm", "", "route_matrix_confirm.json"],
    ]

    # 3. Category Derivation
    cat_derivation = [
        ["section", "step", "evidence", "implication", "decision", "lineage"],
        ["summary", cat.get("name", ""), "", f"node_id={cat.get('node_id', '')}", "", ""],
        ["step", "类目选择", str(cat.get("name", "")) + " (" + str(cat.get("node_id", "")) + ")", str(cat.get("monthly_units", "")) + " units, $" + str(cat.get("avg_price", "")), "主战场", "category_panorama.selected_category"],
        ["step", "子市场", str(sub.get("product_form", "")), str(sub.get("estimated_monthly_units", "")), "聚焦细分", "category_panorama.sub_market"],
        ["step", "健康度", "Top3:" + str(health.get("top3_brand_share", "")) + " 中国:" + str(health.get("china_seller_share", "")) + " 新品:" + str(health.get("new_3m_share", "")), str(health.get("concentration_note", "")), "", "category_panorama.market_health"],
        ["step", "季节性", "旺季:" + ", ".join(season.get("peak_months", [])) + " 淡季:" + ", ".join(season.get("trough_months", [])), str(season.get("peak_trough_ratio", "")), "", "category_panorama.seasonality"],
    ]

    # 4. Category Candidates
    cat_candidates = [
        ["category_name", "node_id", "category_path", "category_role", "matched_asin_count", "evidence_strength", "recommended_use", "risk_tags"],
        [cat.get("name", ""), cat.get("node_id", ""), "", "primary", "", "high", "主战场", ""],
    ]

    # 5. Reference ASINs
    ref_asins = [
        ["asin", "route_ref", "role", "similarity_reason", "category_path", "price", "monthly_sales", "rating_count"],
    ]
    for c in _as_list(rd.get("competitors")):
        if isinstance(c, dict):
            ref_asins.append([
                c.get("asin", ""),
                c.get("route", c.get("route_ref", "")),
                c.get("role", "primary_reference"),
                c.get("positioning", c.get("similarity_reason", "")),
                "",
                c.get("price", ""),
                c.get("monthly_sales", ""),
                c.get("rating_count", ""),
            ])

    # 6. Market Opportunity
    market_opp = [
        ["type", "field_1", "field_2", "field_3", "field_4", "field_5"],
        ["primary_market", "category_name", cat.get("name", ""), "", "", ""],
        ["primary_market", "node_id", cat.get("node_id", ""), "", "", ""],
        ["primary_market", "monthly_units", cat.get("monthly_units", ""), "", "", ""],
        ["primary_market", "monthly_revenue_usd", cat.get("monthly_revenue", ""), "", "", ""],
        ["primary_market", "avg_price_usd", cat.get("avg_price", ""), "", "", ""],
        ["primary_market", "avg_rating", cat.get("avg_rating", ""), "", "", ""],
    ]
    for pb in _as_list(rd.get("price_bands")):
        if isinstance(pb, dict):
            market_opp.append([
                "price_band",
                pb.get("label", pb.get("range", pb.get("band", ""))),
                pb.get("unit_share", pb.get("sales_share", "")),
                str(pb.get("product_count", "")),
                pb.get("opportunity_level", ""),
                pb.get("reason", pb.get("recommendation", "")),
            ])

    # 7. Keyword Pool
    kw_pool = [
        ["role", "keyword", "monthly_search_volume", "cpc", "competitor_count", "mix_pool_score", "mix_pool_risk_level", "reason", "recommended_action"],
    ]
    for kw in _as_list(rd.get("keywords")):
        if isinstance(kw, dict):
            intent = kw.get("intent", kw.get("category", kw.get("role", "")))
            role = "main_traffic" if "主攻" in str(intent) else "test_traffic"
            action = kw.get("intent", kw.get("category", ""))
            kw_pool.append([
                role,
                kw.get("keyword", ""),
                kw.get("monthly_searches", kw.get("monthly_search_volume", "")),
                kw.get("cpc", ""),
                kw.get("competitor_count", ""),
                "",
                "",
                kw.get("reason", kw.get("strategy_notes", "")),
                action,
            ])

    # 8. VOC
    voc = [
        ["dimension", "issue", "review_count", "spec_requirement", "evidence", "next_check"],
    ]
    for pp in _as_list(rd.get("pain_points")):
        if isinstance(pp, dict):
            voc.append([
                pp.get("dimension", ""),
                pp.get("issue", ""),
                pp.get("review_count", ""),
                pp.get("spec_requirement", ""),
                pp.get("source_path", ""),
                "",
            ])

    # 9. Route Judgment
    route_judgment = [
        ["route_name", "role", "market_signal", "keyword_signal", "voc_signal", "risk_note", "next_check"],
    ]
    routes_seen = set()
    for c in _as_list(rd.get("competitors")):
        if isinstance(c, dict):
            route = c.get("route", c.get("route_ref", ""))
            if route and route not in routes_seen:
                routes_seen.add(route)
                route_judgment.append([route, "primary", "", "", "", "", ""])
    if not routes_seen:
        route_judgment.append(["主路线", "primary", "", "", "", "", ""])

    # 10. Risks And Next
    risks_next = [
        ["type", "source", "item", "detail", "next"],
    ]
    for r in _as_list(rd.get("risks")):
        if isinstance(r, dict):
            risks_next.append([
                "gap",
                "风险",
                "[" + str(r.get("severity", "")) + "] " + str(r.get("title", "")),
                r.get("detail", ""),
                r.get("mitigation", ""),
            ])
    for adv in _as_list(rd.get("advantages")):
        if isinstance(adv, dict):
            risks_next.append([
                "boundary",
                "优势",
                adv.get("title", ""),
                adv.get("detail", ""),
                "",
            ])
    for cond in _as_list(rd.get("gonogo_conditions")):
        if isinstance(cond, dict):
            risks_next.append([
                "next_condition",
                cond.get("status", ""),
                cond.get("condition", ""),
                cond.get("detail", ""),
                cond.get("source_path", ""),
            ])
    for ns in _as_list(rd.get("next_steps")):
        if isinstance(ns, dict):
            risks_next.append([
                "next_step",
                "行动计划",
                ns.get("action", ns.get("step", "")),
                ns.get("detail", ""),
                "",
            ])

    return [
        ("Summary", summary),
        ("Source Packets", source_packets),
        ("Category Derivation", cat_derivation),
        ("Category Candidates", cat_candidates),
        ("Reference ASINs", ref_asins),
        ("Market Opportunity", market_opp),
        ("Keyword Pool", kw_pool),
        ("VOC", voc),
        ("Route Judgment", route_judgment),
        ("Risks And Next", risks_next),
    ]

def build_workbook_sheets(analysis: dict[str, Any]) -> list[tuple[str, list[list[object]]]]:
    return [
        ("Summary", summary_rows(analysis)),
        ("Source Packets", source_packet_rows(analysis)),
        ("Category Derivation", category_derivation_rows(analysis)),
        ("Category Candidates", category_candidate_rows(analysis)),
        ("Reference ASINs", reference_asin_rows(analysis)),
        ("Market Opportunity", market_opportunity_rows(analysis)),
        ("Keyword Pool", keyword_pool_rows(analysis)),
        ("VOC", voc_rows(analysis)),
        ("Route Judgment", route_rows(analysis)),
        ("Risks And Next", risk_next_rows(analysis)),
    ]


def summary_rows(analysis: dict[str, Any]) -> list[list[object]]:
    return [
        ["field", "value"],
        ["run_id", analysis.get("run_id", "")],
        ["verdict", analysis.get("verdict", "")],
        ["confidence", analysis.get("confidence", "")],
        ["one_sentence_conclusion", analysis.get("one_sentence_conclusion", "")],
        ["next_move", (analysis.get("market_synthesis") or {}).get("next_move", "")],
    ]


def source_packet_rows(analysis: dict[str, Any]) -> list[list[object]]:
    rows = [["name", "exists", "packet_id", "confidence", "path"]]
    for packet in as_list(analysis.get("source_packets")):
        rows.append([packet.get("name", ""), packet.get("exists", ""), packet.get("packet_id", ""), packet.get("confidence", ""), packet.get("path", "")])
    return rows


def category_derivation_rows(analysis: dict[str, Any]) -> list[list[object]]:
    rows = [["section", "step", "evidence", "implication", "decision", "lineage"]]
    derivation = analysis.get("category_selection_derivation") or {}
    rows.append(["summary", derivation.get("selected_category", ""), "", f"confidence={derivation.get('confidence', '')}", "", ""])
    for item in as_list(derivation.get("steps")):
        rows.append(["step", item.get("name", ""), join_text(item.get("evidence")), item.get("implication", ""), item.get("decision", ""), join_text(item.get("lineage"))])
    for item in as_list(derivation.get("rejected_alternatives")):
        rows.append(["rejected", item.get("name", ""), item.get("reason", ""), "", item.get("decision", ""), ""])
    for item in as_list(derivation.get("disconfirming_evidence")):
        rows.append(["disconfirming", item.get("risk", ""), item.get("current_signal", ""), item.get("would_change_decision_if", ""), item.get("next_check", ""), ""])
    return rows


def category_candidate_rows(analysis: dict[str, Any]) -> list[list[object]]:
    rows = [["category_name", "node_id", "category_path", "category_role", "matched_asin_count", "evidence_strength", "recommended_use", "risk_tags"]]
    for item in as_list((analysis.get("category_opportunity") or {}).get("category_candidates")):
        rows.append([item.get("category_name", ""), item.get("node_id", ""), item.get("category_path", ""), item.get("category_role", ""), item.get("matched_asin_count", ""), item.get("evidence_strength", ""), item.get("recommended_use", ""), item.get("risk_tags", "")])
    return rows


def reference_asin_rows(analysis: dict[str, Any]) -> list[list[object]]:
    rows = [["asin", "route_ref", "role", "similarity_reason", "category_path", "price", "monthly_sales", "rating_count"]]
    for item in as_list(analysis.get("reference_asin_pool")):
        rows.append([item.get("asin", ""), item.get("route_ref", ""), item.get("asin_role", ""), item.get("similarity_reason", ""), item.get("category_path", ""), item.get("price", ""), item.get("monthly_sales", ""), item.get("rating_count", "")])
    return rows


def market_opportunity_rows(analysis: dict[str, Any]) -> list[list[object]]:
    rows = [["type", "field_1", "field_2", "field_3", "field_4", "field_5"]]
    market = analysis.get("seller_sprite_validation") or {}
    primary = market.get("primary_market") or {}
    for key, value in primary.items():
        rows.append(["primary_market", key, value, "", "", ""])
    for item in as_list((analysis.get("category_opportunity") or {}).get("price_band_opportunity")):
        rows.append(["price_band", item.get("price_band", ""), item.get("sales_share", ""), item.get("revenue_share", ""), item.get("opportunity_level", ""), item.get("reason", "")])
    for item in as_list((analysis.get("category_opportunity") or {}).get("new_release_opportunity")):
        rows.append(["new_release", item.get("category_ref", item.get("price_band", "")), item.get("new_release_count", ""), item.get("new_release_sales_share", ""), item.get("new_release_opportunity_level", ""), item.get("score_reason", "")])
    return rows


def keyword_pool_rows(analysis: dict[str, Any]) -> list[list[object]]:
    rows = [["role", "keyword", "monthly_search_volume", "cpc", "competitor_count", "mix_pool_score", "mix_pool_risk_level", "reason", "recommended_action"]]
    roles = ((analysis.get("keyword_pool") or {}).get("roles") or {})
    if isinstance(roles, dict):
        for role, items in roles.items():
            for item in as_list(items):
                rows.append([
                    role,
                    item.get("keyword", item.get("term", "")),
                    item.get("monthly_search_volume", ""),
                    item.get("cpc", ""),
                    item.get("competitor_count", ""),
                    item.get("mix_pool_score", ""),
                    item.get("mix_pool_risk_level", ""),
                    item.get("reason", item.get("route_relevance", "")),
                    item.get("recommended_action", ""),
                ])
    return rows


def voc_rows(analysis: dict[str, Any]) -> list[list[object]]:
    rows = [["dimension", "issue", "review_count", "spec_requirement", "evidence", "next_check"]]
    for item in as_list((analysis.get("voc_spec_translation") or {}).get("pain_points")):
        rows.append([item.get("dimension", ""), item.get("issue", ""), item.get("review_count", ""), item.get("spec_requirement", ""), item.get("evidence", ""), item.get("next_check", "")])
    return rows


def route_rows(analysis: dict[str, Any]) -> list[list[object]]:
    rows = [["route_name", "role", "market_signal", "keyword_signal", "voc_signal", "risk_note", "next_check"]]
    for item in as_list(analysis.get("route_judgment")):
        rows.append([item.get("route_name", ""), item.get("role", ""), item.get("market_signal", ""), item.get("keyword_signal", ""), item.get("voc_signal", ""), item.get("risk_note", ""), item.get("next_check", "")])
    return rows


def risk_next_rows(analysis: dict[str, Any]) -> list[list[object]]:
    rows = [["type", "source", "item", "detail", "next"]]
    for item in as_list(analysis.get("blocking_gaps")):
        rows.append(["gap", item.get("source", ""), item.get("gap", ""), item.get("impact", ""), ""])
    for item in as_list(analysis.get("evidence_boundaries")):
        rows.append(["boundary", item.get("source", ""), item.get("boundary", ""), "", item.get("action", "")])
    for item in as_list(analysis.get("next_stage_entry_conditions")):
        rows.append(["next_condition", item.get("status", ""), item.get("condition", ""), item.get("why", ""), ""])
    return rows


def run_delivery_qa(report_data_path: Path, html_path: Path, xlsx_path: Path, analysis: dict[str, Any] | None = None) -> dict[str, Any]:
    run_dir = html_path.parent.parent
    packets = _load_packets_for_qa(run_dir, analysis)
    source_result = _validate_report_data_sources(report_data_path, packets)
    has_data = _report_data_has_required_sections(report_data_path)
    forbidden_result = _has_no_forbidden_html_patterns(html_path)
    checks = {
        "report_data_exists": report_data_path.exists(),
        "html_exists": html_path.exists(),
        "xlsx_exists": xlsx_path.exists(),
        "report_data_has_required_sections": has_data,
        "has_no_removed_legacy_sections": _has_no_removed_legacy_sections(html_path),
        "has_inline_style": _has_inline_style(html_path),
        "has_8_sections": _has_8_sections(html_path),
        "has_gonogo_class": _has_gonogo_class(html_path),
        "report_data_sources_valid": source_result["pass"],
        "has_no_forbidden_html_patterns": forbidden_result["pass"],
    }
    if forbidden_result.get("hits"):
        checks["forbidden_html_hits"] = forbidden_result["hits"]
    if source_result.get("reason"):
        checks["report_data_sources_note"] = source_result["reason"]
    failures = [name for name, passed in checks.items() if not passed and name != "report_data_sources_note"]
    return {"status": "pass" if not failures else "fail", "checks": checks, "failures": failures}


def _load_packets_for_qa(run_dir: Path, analysis: dict[str, Any] | None = None) -> dict[str, Any]:
    """Load evidence packets for source_path validation."""
    paths = {
        "market_structure": run_dir / "market_structure" / "market_structure_evidence_packet.json",
        "search_demand": run_dir / "search_demand" / "search_demand_evidence_packet.json",
        "voc": run_dir / "review_voc" / "voc_evidence_packet.json",
        "route_matrix": run_dir / "route_matrix_confirm.json",
    }
    packets: dict[str, Any] = {}
    for key, path in paths.items():
        try:
            if path.exists():
                packets[key] = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, ValueError):
            pass
    if analysis:
        packets["analysis"] = analysis
    return packets


def _has_no_removed_legacy_sections(html_path: Path) -> bool:
    if not html_path.exists():
        return False
    html = html_path.read_text(encoding="utf-8")
    removed_section_markers = (
        "legacy_source_collection_section",
        "legacy_fillback_stage_section",
        "legacy_cost_review_section",
    )
    return not any(marker in html for marker in removed_section_markers)


FORBIDDEN_HTML_PATTERNS = [
    # 抽象路线标签：运营看不懂"路线A/B"是什么意思
    (r"路线[A-Z0-9]", "抽象路线标签（如路线A/路线B/路线1），必须用业务描述词（如吊扇除尘/纯钢丝刷）"),
    # 内部执行术语：不能暴露给运营
    (r"\bAgent\b", "内部术语 Agent，HTML 中不得出现"),
    (r"\bMCP\b", "内部术语 MCP，HTML 中不得出现（数据来源写 Sorftime 即可）"),
    (r"\bpacket\b", "内部术语 packet，HTML 中不得出现"),
    (r"\bpipeline\b", "内部术语 pipeline，HTML 中不得出现"),
    (r"\bspawn\b", "内部术语 spawn，HTML 中不得出现"),
    (r"\bevidence_packet\b", "内部术语 evidence_packet，HTML 中不得出现"),
    (r"\bsource_path\b", "内部术语 source_path，HTML 中不得出现"),
    # 虚假宣传常用措辞
    (r"保证.*月销[0-9万kK]+", "虚假承诺类措辞，不得出现'保证月销X万'"),
    (r"绝对.*爆款", "虚假宣传措辞，不得出现'绝对爆款'"),
    (r"100%.*成功", "虚假宣传措辞，不得出现'100%成功'"),
    (r"零风险", "虚假宣传措辞，不得出现'零风险'"),
    (r"稳赚", "虚假宣传措辞，不得出现'稳赚'"),
    (r"包赚", "虚假宣传措辞，不得出现'包赚'"),
]


def _has_no_forbidden_html_patterns(html_path: Path) -> dict:
    """扫描 HTML 中的禁止模式：抽象路线标签、内部术语、虚假宣传措辞。"""
    if not html_path.exists():
        return {"pass": False, "hits": ["HTML 文件不存在"]}
    html = html_path.read_text(encoding="utf-8")
    hits = []
    for pattern, description in FORBIDDEN_HTML_PATTERNS:
        matches = re.findall(pattern, html)
        if matches:
            unique_matches = list(set(matches))[:5]
            hits.append(f"{description}（匹配: {', '.join(unique_matches)}）")
    return {"pass": len(hits) == 0, "hits": hits}


def _has_inline_style(html_path: Path) -> bool:
    """HTML 必须内嵌 <style>（内容来自 report_template.css），不能使用外部 <link>。"""
    if not html_path.exists():
        return False
    html = html_path.read_text(encoding="utf-8")
    has_inline_style = '<style>' in html
    import re
    has_link = bool(re.search(r'<link[^>]*report_template\.css', html))
    return has_inline_style and not has_link


REQUIRED_SECTION_MARKERS = (
    "类目全景",
    "数据来源与口径",
    "核心竞品",
    "用户痛点",
    "价格带分布",
    "关键词与流量策略",
    "风险与下一步",
)


def _has_8_sections(html_path: Path) -> bool:
    if not html_path.exists():
        return False
    html = html_path.read_text(encoding="utf-8")
    return all(marker in html for marker in REQUIRED_SECTION_MARKERS)


def _has_gonogo_class(html_path: Path) -> bool:
    if not html_path.exists():
        return False
    html = html_path.read_text(encoding="utf-8")
    return 'class="go-nogo"' in html or "class='go-nogo'" in html


VOC_REQUIRED_EVIDENCE_FIELDS = ("review_id", "quote", "rating", "asin")


def _has_voc_evidence_refs(analysis_json: Path) -> bool:
    """VOC 痛点必须有 evidence_refs，且每个 ref 包含 review_id/quote/rating/asin 四字段。"""
    if not analysis_json.exists():
        return False
    data = json.loads(analysis_json.read_text(encoding="utf-8"))
    voc = data.get("voc_spec_translation") or {}
    pain_points = voc.get("pain_points") or []
    if not pain_points:
        # 没有痛点时不扣分（可能评论样本不足）
        return True
    return all(
        isinstance(pp.get("evidence_refs"), list)
        and len(pp["evidence_refs"]) > 0
        and all(
            isinstance(ref, dict)
            and all(ref.get(field) for field in VOC_REQUIRED_EVIDENCE_FIELDS)
            for ref in pp["evidence_refs"]
        )
        for pp in pain_points
    )


REQUIRED_REPORT_DATA_SECTIONS = (
    "hero",
    "category_panorama",
    "competitors",
    "pain_points",
    "price_bands",
    "keywords",
    "risks",
    "advantages",
    "gonogo_conditions",
    "next_steps",
)


def _report_data_has_required_sections(report_data_path: Path) -> bool:
    """report_data.json 必须包含所有必要的板块数据。"""
    if not report_data_path.exists():
        return False
    try:
        data = json.loads(report_data_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, ValueError):
        return False
    return all(section in data for section in REQUIRED_REPORT_DATA_SECTIONS)


def _validate_report_data_sources(report_data_path: Path, packets: dict[str, Any]) -> dict:
    """校验 report_data.json 中 source_path 能否在证据包中找到对应字段。

    返回 dict 包含 pass/fail 和解析明细。阈值：
    - 未解析率 > 5% → block（pass=False）
    - 未解析率 > 2% → warning（pass=True，但记录）
    - 未解析率 ≤ 2% → pass
    """
    if not report_data_path.exists():
        return {"pass": False, "total": 0, "resolved": 0, "vague": 0, "unresolved": 0, "unresolved_pct": 0.0, "reason": "report_data.json 不存在"}
    try:
        data = json.loads(report_data_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, ValueError):
        return {"pass": False, "total": 0, "resolved": 0, "vague": 0, "unresolved": 0, "unresolved_pct": 0.0, "reason": "report_data.json 解析失败"}

    source_paths = _extract_source_paths(data)
    unresolved: list[dict] = []
    resolved = 0
    vague = 0

    for item in source_paths:
        sp = item["source_path"].strip()
        if not sp or sp == "N/A" or sp == "—":
            continue

        result = _try_resolve_path(sp, packets)
        if result["status"] == "unresolved":
            unresolved.append({"path": sp, "key": item.get("parent_key", ""), "reason": result["reason"]})
        elif result["status"] == "ok" and "模糊" in result.get("reason", ""):
            vague += 1
        else:
            resolved += 1

    total = len(source_paths)
    # 只计算有效 source_path（排除空/N/A）
    effective = resolved + vague + len(unresolved)
    unresolved_pct = len(unresolved) / max(effective, 1)

    passed = unresolved_pct <= 0.05
    reason = ""
    if unresolved_pct > 0.05:
        reason = f"未解析率 {unresolved_pct:.0%} 超过 5% 阈值，共 {len(unresolved)}/{effective} 条路径无法溯源"
    elif unresolved_pct > 0.02:
        reason = f"未解析率 {unresolved_pct:.0%} 在 2%-5% 之间，共 {len(unresolved)}/{effective} 条路径无法溯源（不阻断）"

    return {
        "pass": passed,
        "total": total,
        "resolved": resolved,
        "vague": vague,
        "unresolved": len(unresolved),
        "unresolved_pct": unresolved_pct,
        "reason": reason,
        "unresolved_paths": unresolved,
    }


def _extract_source_paths(obj: Any, parent_key: str = "") -> list[dict]:
    """递归提取 report_data.json 中所有 source_path 及其上下文。"""
    results: list[dict] = []
    if isinstance(obj, dict):
        for key, val in obj.items():
            if key == "source_path" and isinstance(val, str):
                results.append({"source_path": val, "parent_key": parent_key})
            else:
                results.extend(_extract_source_paths(val, parent_key=key))
    elif isinstance(obj, list):
        for item in obj:
            results.extend(_extract_source_paths(item, parent_key=parent_key))
    return results


def _try_resolve_path(source_path: str, packets: dict[str, Any]) -> dict:
    """尝试在证据包中解析一个 source_path。

    支持的路径格式：
    - packet.field.subfield (如 market_structure.market_size.primary_market)
    - packet.array_id.field (如 search_demand.f8.value.top100_monthly_units)
    - packet.array[index].field (如 voc.pain_points_by_dimension[0].review_count)
    - packet.field (模糊溯源，如 market_structure)
    """
    # 匹配包名前缀
    packet_key = None
    rest = source_path
    for pkey in ("market_structure", "search_demand", "voc", "route_matrix", "analysis", "seller_sprite"):
        if source_path.startswith(pkey):
            packet_key = pkey
            rest = source_path[len(pkey):].lstrip(".")
            break

    if not packet_key:
        return {"status": "unresolved", "reason": f"无法识别包名前缀: {source_path}"}

    # Alias: seller_sprite -> market_structure
    if packet_key == "seller_sprite":
        packet_key = "market_structure"

    packet = packets.get(packet_key)
    if not packet:
        return {"status": "unresolved", "reason": f"证据包未加载: {packet_key}"}

    if not rest:
        # 只有包名无字段路径 —— 模糊溯源
        return {"status": "ok", "reason": "包级模糊溯源（无字段路径）"}

    # 剥离结尾的描述性文字（空格后跟中文说明、加总等）
    stripped = rest
    for sep in [" 月销额加总", " 月销额:", " 月销额计算:", " 竞品数对比", " 竞品数", " 加总", " + "]:
        if sep in stripped:
            idx = stripped.index(sep)
            stripped = stripped[:idx]
            break
    # 多引用复合路径（如 facts[f8,f9,f10]）→ 无法单点解析，跳过
    if "][" in stripped or (stripped.count("[") >= 2 and "," in stripped):
        return {"status": "ok", "reason": "复合引用（多源加总），无法单点解析"}

    # 分割路径
    parts = _split_path(stripped)
    if not parts:
        return {"status": "unresolved", "reason": f"路径解析后为空: {rest}"}

    # 导航 JSON
    current: Any = packet
    for part in parts:
        current = _navigate(current, part)
        if current is _NOT_FOUND:
            return {"status": "unresolved", "reason": f"路径段 '{part}' 在 '{packet_key}' 中未找到"}

    return {"status": "ok", "reason": "已解析"}


_NOT_FOUND = object()


def _split_path(path: str) -> list[str]:
    """将点分隔的路径拆分为段，处理数组索引。"""
    parts: list[str] = []
    for segment in path.split("."):
        segment = segment.strip()
        if not segment:
            continue
        # 处理 array[index] 格式
        if "[" in segment and "]" in segment:
            base = segment[: segment.index("[")]
            idx_str = segment[segment.index("[") + 1 : segment.index("]")]
            if base:
                parts.append(base)
            parts.append(f"[{idx_str}]")
        else:
            parts.append(segment)
    return parts


def _navigate(current: Any, part: str) -> Any:
    """在 JSON 结构中导航一个路径段。"""
    if current is _NOT_FOUND:
        return _NOT_FOUND

    # 数组索引: [0], [1], 或 id 查找: [f2], [biothane]
    if part.startswith("[") and part.endswith("]"):
        idx_str = part[1:-1]
        if isinstance(current, list):
            # 先尝试整数索引
            try:
                idx = int(idx_str)
                if 0 <= idx < len(current):
                    return current[idx]
            except ValueError:
                pass
            # 非整数 → 按 id/name/keyword 查找
            for item in current:
                if isinstance(item, dict):
                    if item.get("id") == idx_str or item.get("name") == idx_str or item.get("keyword") == idx_str:
                        return item
        # 尝试在 dict 的数组值中查找
        if isinstance(current, dict):
            for key, val in current.items():
                if isinstance(val, list):
                    for item in val:
                        if isinstance(item, dict) and item.get("id") == idx_str:
                            return item
        return _NOT_FOUND

    # 对象键查找（先精确匹配）
    if isinstance(current, dict):
        if part in current:
            return current[part]
        # 尝试模糊匹配（key 中包含该字符串）
        for key in current:
            if part in key:
                return current[key]
        # 深层搜索：当前 dict 中的每个数组里查找 id 匹配（如 f8 → facts[].id）
        for key, val in current.items():
            if isinstance(val, list):
                for item in val:
                    if isinstance(item, dict) and item.get("id") == part:
                        return item
            # 也搜索嵌套 dict 的第一层（如 price_band → primary_market_distribution_grouped → under_8）
            elif isinstance(val, dict) and part in val:
                return val[part]

    # facts 数组按 id 查找（如 f8, f2, f10）
    if isinstance(current, list) and part.startswith("f") and len(part) <= 4:
        for item in current:
            if isinstance(item, dict) and item.get("id") == part:
                return item

    # 通用数组按 id、name、keyword 或 dimension 查找
    if isinstance(current, list):
        for item in current:
            if isinstance(item, dict):
                if item.get("id") == part or item.get("name") == part or item.get("keyword") == part or item.get("dimension") == part:
                    return item
        # 数组中的 dict 嵌套搜索
        for item in current:
            if isinstance(item, dict):
                for key, val in item.items():
                    if isinstance(val, dict) and part in val:
                        return val[part]

    return _NOT_FOUND


def first_text(*values: Any) -> str:
    for value in values:
        if value is None:
            continue
        if isinstance(value, str) and value.strip():
            return value.strip()
        if not isinstance(value, (str, list, dict)) and value:
            return str(value)
    return ""


def first_dict(*values: Any) -> dict[str, Any]:
    for value in values:
        if isinstance(value, dict) and value:
            return value
    return {}


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def compact_list(values: list[Any]) -> list[str]:
    return [text for text in (public_text(value) for value in values) if text]


def join_text(value: Any, sep: str = "；") -> str:
    if isinstance(value, list):
        return sep.join(public_text(item) for item in value if public_text(item))
    if isinstance(value, dict):
        return sep.join(f"{key}: {public_text(val)}" for key, val in value.items() if public_text(val))
    return public_text(value)


def public_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, list):
        return join_text(value)
    if isinstance(value, dict):
        return join_text(value)
    return str(value).strip()


def first_row_text(rows: list[Any], key: str) -> str:
    for row in rows:
        if isinstance(row, dict) and row.get(key):
            return str(row.get(key))
    return ""


def numeric_value(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.replace(",", "").replace("%", "").strip()
        try:
            number = float(text)
        except ValueError:
            return None
        if "%" in value:
            return number / 100
        return number
    return None


def fmt_number(value: Any) -> str:
    number = numeric_value(value)
    if number is None:
        return str(value or "待补")
    if abs(number) >= 1000:
        return f"{number:,.0f}"
    if number == int(number):
        return str(int(number))
    return f"{number:.2f}".rstrip("0").rstrip(".")


def fmt_percent(value: Any) -> str:
    number = numeric_value(value)
    if number is None:
        return str(value or "待补")
    if abs(number) <= 1:
        number *= 100
    return f"{number:.1f}%"


def dedupe_rows(rows: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    seen: set[str] = set()
    result = []
    for row in rows:
        marker = str(row.get(key, "")).strip()
        if marker and marker in seen:
            continue
        if marker:
            seen.add(marker)
        result.append(row)
    return result


if __name__ == "__main__":
    raise SystemExit(main())

