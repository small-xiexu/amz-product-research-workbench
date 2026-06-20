#!/usr/bin/env python3
"""Build a Stage 7 market precheck report from market, search and VOC evidence."""

from __future__ import annotations

import argparse
from datetime import datetime
from html import escape
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.report_renderer.xlsx_writer import write_xlsx
from packages.research_core.pipeline.audit_run_status import audit_run_status


ALLOWED_VERDICTS = {"继续看", "谨慎继续", "暂缓"}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Stage 7 market precheck report.")
    parser.add_argument("run_dir", help="Run directory, for example runs/<run_id>.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    run_dir = Path(args.run_dir).expanduser().resolve()
    if not run_dir.exists():
        raise FileNotFoundError(f"run_dir not found: {run_dir}")

    packets = load_packets(run_dir)
    analysis = build_analysis_packet(run_dir, packets)
    analysis_dir = run_dir / "analysis"
    analysis_dir.mkdir(parents=True, exist_ok=True)

    analysis_json = analysis_dir / "analysis_evidence_packet.json"
    html_path = analysis_dir / "analysis_report.html"
    xlsx_path = analysis_dir / "analysis_report.xlsx"
    qa_path = analysis_dir / "delivery_qa_result.json"

    analysis_json.write_text(json.dumps(analysis, ensure_ascii=False, indent=2), encoding="utf-8")
    html_path.write_text(render_html_report(analysis), encoding="utf-8")
    write_xlsx(xlsx_path, build_workbook_sheets(analysis))
    qa = run_delivery_qa(analysis, analysis_json, html_path, xlsx_path)
    qa_path.write_text(json.dumps(qa, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Wrote {analysis_json}")
    print(f"Wrote {html_path}")
    print(f"Wrote {xlsx_path}")
    print(f"Wrote {qa_path}")
    return 0 if qa.get("status") == "pass" else 1


def load_packets(run_dir: Path) -> dict[str, Any]:
    paths = {
        "search_demand": run_dir / "search_demand" / "search_demand_evidence_packet.json",
        "market_structure": run_dir / "market_structure" / "market_structure_evidence_packet.json",
        "voc": run_dir / "review_voc" / "voc_evidence_packet.json",
        "route_matrix": run_dir / "route_matrix_confirm.json",
        "workflow_state": run_dir / "workflow_state.json",
        "report_writer_narrative": run_dir / "analysis" / "report_writer_narrative.json",
        "search_demand_subagent_review": run_dir / "search_demand" / "search_demand_subagent_review.json",
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
        "packet_id": "analysis_evidence_packet",
        "packet_version": "stage7-market-precheck-v2",
        "stage": "market_precheck",
        "run_id": run_dir.name,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "verdict": verdict,
        "one_sentence_conclusion": one_sentence_conclusion(verdict, market_synthesis),
        "confidence": confidence_level(reference_asin_pool, keyword_pool, category_opportunity, voc_translation),
        "source_packets": source_packets,
        "independent_subagent_reviews": {
            "search_demand": packets.get("search_demand_subagent_review") or {},
        },
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
                "analysis_json": str(run_dir / "analysis" / "analysis_evidence_packet.json"),
                "html": str(run_dir / "analysis" / "analysis_report.html"),
                "xlsx": str(run_dir / "analysis" / "analysis_report.xlsx"),
                "qa": str(run_dir / "analysis" / "delivery_qa_result.json"),
            },
        },
    }
    analysis["run_status_audit"] = audit_run_status(run_dir, analysis)
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
    return {
        "verdict": verdict,
        "market_read": market_validation.get("summary", ""),
        "demand_read": search_validation.get("summary", ""),
        "voc_read": voc_translation.get("summary", ""),
        "route_read": top_route.get("market_signal") or top_route.get("keyword_signal") or "路线判断待补。",
        "key_risk": top_gap.get("gap", "当前没有硬阻塞，但仍需按小类继续核验。"),
        "next_move": next_move_for_verdict(verdict),
        "analysis_cards": [
            {"title": "市场是否值得继续看", "body": market_validation.get("summary", "")},
            {"title": "需求入口是否成立", "body": search_validation.get("summary", "")},
            {"title": "产品机会在哪里", "body": voc_translation.get("summary", "")},
            {"title": "为什么还不能直接立项", "body": top_gap.get("gap", "仍需完成小类市场、关键词边界和 VOC 规格复核。")},
        ],
    }


def next_move_for_verdict(verdict: str) -> str:
    if verdict == "继续看":
        return "进入小类市场分析：围绕主路线补 Top100、代表 ASIN、关键词自然位和 VOC 规格验证。"
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


def render_html_report(analysis: dict[str, Any]) -> str:
    title = analysis.get("category_selection_derivation", {}).get("selected_category") or analysis.get("run_id", "Stage 7")
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(str(title))} / 市场预审</title>
  <style>
    :root {{
      --bg: #eef3f7;
      --panel: #ffffff;
      --ink: #17212f;
      --muted: #657286;
      --line: #d8e1ec;
      --soft: #f7fafc;
      --accent: #0f8178;
      --accent-soft: #dff6f2;
      --warn: #9a5b00;
      --warn-soft: #fff4dc;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
      font-size: 16px;
      line-height: 1.65;
      letter-spacing: 0;
    }}
    .page {{ max-width: 1500px; margin: 0 auto; padding: 28px 32px 56px; }}
    .section {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 30px;
      margin: 0 0 28px;
      min-width: 0;
      break-inside: avoid;
    }}
    .eyebrow {{
      margin: 0 0 8px;
      color: var(--accent);
      font-size: 14px;
      font-weight: 800;
      letter-spacing: .06em;
      text-transform: uppercase;
    }}
    h1, h2, h3 {{ line-height: 1.2; letter-spacing: 0; }}
    h1 {{ margin: 0 0 14px; font-size: 42px; }}
    h2 {{ margin: 0 0 18px; font-size: 28px; }}
    h3 {{ margin: 22px 0 12px; font-size: 20px; }}
    p {{ margin: 0 0 14px; }}
    .lead {{ color: var(--muted); font-size: 19px; max-width: 980px; }}
    .summary-grid {{ display: grid; grid-template-columns: 1.4fr .8fr; gap: 24px; align-items: start; }}
    .metric-grid {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; margin-top: 22px; }}
    .metric {{
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--soft);
      padding: 18px;
      min-height: 112px;
    }}
    .metric span {{ display: block; color: var(--muted); font-size: 14px; margin-bottom: 8px; }}
    .metric strong {{ display: block; font-size: 26px; line-height: 1.25; }}
    .chips {{ display: flex; flex-wrap: wrap; gap: 10px; margin-top: 18px; }}
    .chip {{
      border-radius: 999px;
      background: var(--accent-soft);
      color: #075f59;
      padding: 8px 13px;
      font-weight: 700;
      font-size: 14px;
    }}
    .pill-warn {{ background: var(--warn-soft); color: var(--warn); }}
    .card-grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 18px; }}
    .card {{
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 22px;
      background: #fff;
    }}
    .card h3 {{ margin-top: 0; color: #08786f; }}
    .fact-list {{ display: grid; gap: 12px; }}
    .fact-row {{
      display: grid;
      grid-template-columns: 86px 1fr;
      gap: 14px;
      border-top: 1px solid #e7edf4;
      padding-top: 12px;
    }}
    .tag {{
      display: inline-block;
      width: fit-content;
      min-width: 52px;
      text-align: center;
      border-radius: 6px;
      background: var(--accent-soft);
      color: #075f59;
      font-weight: 800;
      padding: 4px 8px;
    }}
    .table-wrap {{
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: hidden;
      margin-top: 14px;
      background: #fff;
      min-width: 0;
      max-width: 100%;
    }}
    .table-scroll {{ overflow-x: auto; }}
    table {{ width: 100%; border-collapse: collapse; table-layout: fixed; }}
    .wide-table table {{ min-width: max(1180px, 100%); table-layout: auto; }}
    th, td {{
      padding: 14px 16px;
      border-bottom: 1px solid var(--line);
      text-align: left;
      vertical-align: top;
      overflow-wrap: anywhere;
    }}
    th {{ background: var(--soft); color: #344154; font-weight: 800; }}
    tr:last-child td {{ border-bottom: 0; }}
    .section-note {{
      border-left: 4px solid var(--accent);
      background: #f2fbf9;
      padding: 14px 18px;
      border-radius: 0 8px 8px 0;
      color: #2a3a48;
      margin: 16px 0 0;
    }}
    @media (max-width: 900px) {{
      .page {{ padding: 18px; }}
      .section {{ padding: 22px; }}
      h1 {{ font-size: 32px; }}
      .summary-grid, .card-grid, .metric-grid {{ grid-template-columns: 1fr; }}
      .fact-row {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <main class="page">
    {render_hero(analysis)}
    {render_synthesis_section(analysis)}
    {render_derivation_section(analysis)}
    {render_market_section(analysis)}
    {render_keyword_section(analysis)}
    {render_voc_section(analysis)}
    {render_route_section(analysis)}
    {render_risk_next_section(analysis)}
    {render_source_section(analysis)}
  </main>
</body>
</html>"""


def render_hero(analysis: dict[str, Any]) -> str:
    derivation = analysis.get("category_selection_derivation") or {}
    search = analysis.get("search_market_validation") or {}
    market = analysis.get("seller_sprite_validation") or {}
    voc = analysis.get("voc_spec_translation") or {}
    return f"""
<section class="section">
  <p class="eyebrow">选品预审报告 / 市场分析版</p>
  <div class="summary-grid">
    <div>
      <h1>{escape(str(derivation.get("selected_category") or analysis.get("run_id") or "市场预审"))}</h1>
      <p class="lead">{escape(str(analysis.get("one_sentence_conclusion") or ""))}</p>
      <div class="chips">
        <span class="chip">{escape(str(analysis.get("verdict", "")))}</span>
        <span class="chip">证据强度 {escape(str(analysis.get("confidence", "")))}</span>
        <span class="chip">市场 + 搜索 + VOC</span>
      </div>
    </div>
    <div class="metric-grid" style="grid-template-columns: 1fr 1fr;">
      <div class="metric"><span>参考 ASIN</span><strong>{len(as_list(analysis.get("reference_asin_pool")))}</strong></div>
      <div class="metric"><span>候选小类</span><strong>{len(as_list((analysis.get("category_opportunity") or {}).get("category_candidates")))}</strong></div>
      <div class="metric"><span>关键词池</span><strong>{keyword_total(analysis)}</strong></div>
      <div class="metric"><span>VOC 评论</span><strong>{fmt_number(voc.get("review_count"))}</strong></div>
    </div>
  </div>
  <div class="section-note">{escape(str(search.get("summary", "")))} {escape(str(market.get("summary", "")))}</div>
</section>"""


def render_synthesis_section(analysis: dict[str, Any]) -> str:
    synthesis = analysis.get("market_synthesis") or {}
    cards = synthesis.get("analysis_cards") if isinstance(synthesis.get("analysis_cards"), list) else []
    return f"""
<section class="section">
  <p class="eyebrow">综合判断</p>
  <h2>先回答：这个市场是否值得继续研究</h2>
  <div class="card-grid">
    {''.join(render_analysis_card(card) for card in cards)}
  </div>
  <div class="section-note"><b>下一步：</b>{escape(str(synthesis.get("next_move", "")))}</div>
</section>"""


def render_analysis_card(card: dict[str, Any]) -> str:
    return f"""<div class="card"><h3>{escape(str(card.get("title", "")))}</h3><p>{escape(str(card.get("body", "")))}</p></div>"""


def render_derivation_section(analysis: dict[str, Any]) -> str:
    derivation = analysis.get("category_selection_derivation") or {}
    rows = []
    for idx, step in enumerate(as_list(derivation.get("steps")), start=1):
        rows.append(
            [
                str(idx),
                step.get("name", ""),
                join_text(step.get("evidence")),
                step.get("implication", ""),
                step.get("decision", ""),
            ]
        )
    rejected = as_list(derivation.get("rejected_alternatives"))
    disconfirming = as_list(derivation.get("disconfirming_evidence"))
    return f"""
<section class="section">
  <p class="eyebrow">品类选择推导链路</p>
  <h2>为什么收敛到当前主线</h2>
  {render_table(["步骤", "环节", "证据", "含义", "动作"], rows)}
  <h3>被排除或降级的候选</h3>
  {render_table(["候选项", "原因", "处理"], [[r.get("name", ""), r.get("reason", ""), r.get("decision", "")] for r in rejected] or [["暂无", "暂无明确排除项", "继续观察"]])}
  <h3>什么证据会推翻当前判断</h3>
  {render_table(["风险", "触发条件", "下一步检查", "当前信号"], [[r.get("risk", ""), r.get("would_change_decision_if", ""), r.get("next_check", ""), r.get("current_signal", "")] for r in disconfirming])}
</section>"""


def render_market_section(analysis: dict[str, Any]) -> str:
    market = analysis.get("seller_sprite_validation") or {}
    primary = market.get("primary_market") or {}
    category = analysis.get("category_opportunity") or {}
    seasonality_rows = [
        [
            row.get("category_ref", ""),
            row.get("trend_source", ""),
            row.get("peak_months", ""),
            row.get("low_months", ""),
            row.get("seasonality_level", ""),
            row.get("trend_direction", ""),
            row.get("category_seasonality_note", ""),
        ]
        for row in as_list(category.get("category_seasonality"))
    ]
    return f"""
<section class="section">
  <p class="eyebrow">大类 / 小类市场分析</p>
  <h2>市场结构和机会窗口</h2>
  <div class="metric-grid">
    <div class="metric"><span>市场样本</span><strong>{escape(fmt_number(primary.get("sample_count")))}</strong></div>
    <div class="metric"><span>月均销量</span><strong>{escape(fmt_number(primary.get("avg_monthly_units")))}</strong></div>
    <div class="metric"><span>均价</span><strong>${escape(fmt_number(primary.get("avg_price_usd")))}</strong></div>
    <div class="metric"><span>平均评论数</span><strong>{escape(fmt_number(primary.get("avg_rating_count")))}</strong></div>
  </div>
  <h3>候选类目</h3>
  {render_table(["类目", "Node", "角色", "ASIN覆盖", "证据强度", "建议"], [[r.get("category_name", ""), r.get("node_id", ""), r.get("category_role", ""), r.get("matched_asin_count", ""), r.get("evidence_strength", ""), r.get("recommended_use", "")] for r in as_list(category.get("category_candidates"))], wide=True)}
  <h3>价格带机会</h3>
  {render_table(["价格带", "商品数", "销量占比", "收入占比", "低评论样本", "机会等级", "原因"], [[r.get("price_band", ""), r.get("product_count", ""), fmt_percent(r.get("sales_share")), fmt_percent(r.get("revenue_share")), r.get("low_review_winner_count", ""), r.get("opportunity_level", ""), r.get("reason", "")] for r in as_list(category.get("price_band_opportunity"))], wide=True)}
  <h3>类目淡旺季</h3>
  {render_table(["类目", "来源", "旺季", "淡季", "季节性", "趋势", "说明"], seasonality_rows, wide=True)}
</section>"""


def render_keyword_section(analysis: dict[str, Any]) -> str:
    pool = analysis.get("keyword_pool") or {}
    roles = pool.get("roles") if isinstance(pool.get("roles"), dict) else {}
    rows = []
    for role, items in roles.items():
        for item in as_list(items):
            rows.append(
                [
                    role,
                    item.get("keyword") or item.get("term") or "",
                    fmt_number(item.get("monthly_search_volume")),
                    item.get("cpc", ""),
                    fmt_number(item.get("competitor_count")),
                    item.get("reason") or item.get("route_relevance") or "",
                    item.get("recommended_action", ""),
                ]
            )
    return f"""
<section class="section">
  <p class="eyebrow">关键词与需求信号</p>
  <h2>主词、转化词、长尾词和混池词</h2>
  {render_table(["角色", "关键词", "月搜", "CPC", "竞争量", "判断", "动作"], rows, wide=True)}
</section>"""


def render_voc_section(analysis: dict[str, Any]) -> str:
    voc = analysis.get("voc_spec_translation") or {}
    rows = [
        [r.get("dimension", ""), r.get("issue", ""), r.get("review_count", ""), r.get("spec_requirement", ""), r.get("next_check", "")]
        for r in as_list(voc.get("pain_points"))
    ]
    return f"""
<section class="section">
  <p class="eyebrow">VOC 与产品机会</p>
  <h2>评论痛点如何转成规格假设</h2>
  <p class="lead">{escape(str(voc.get("summary", "")))}</p>
  {render_table(["痛点维度", "问题", "评论数", "规格假设", "下一步检查"], rows)}
</section>"""


def render_route_section(analysis: dict[str, Any]) -> str:
    rows = [
        [r.get("route_name", ""), r.get("role", ""), r.get("market_signal", ""), r.get("keyword_signal", ""), r.get("voc_signal", ""), r.get("next_check", "")]
        for r in as_list(analysis.get("route_judgment"))
    ]
    return f"""
<section class="section">
  <p class="eyebrow">路线判断</p>
  <h2>主线、旁支和观察路线</h2>
  {render_table(["路线", "角色", "市场信号", "关键词信号", "VOC 信号", "下一步"], rows, wide=True)}
</section>"""


def render_risk_next_section(analysis: dict[str, Any]) -> str:
    gaps = analysis.get("blocking_gaps") or []
    boundaries = analysis.get("evidence_boundaries") or []
    next_conditions = analysis.get("next_stage_entry_conditions") or []
    focus = analysis.get("human_review_focus") or []
    return f"""
<section class="section">
  <p class="eyebrow">风险 / 缺口 / 下一步</p>
  <h2>现在还缺什么，下一步怎么补</h2>
  <div class="card-grid">
    <div class="card">
      <h3>阻塞与缺口</h3>
      {render_table(["来源", "缺口", "影响"], [[r.get("source", ""), r.get("gap", ""), r.get("impact", "")] for r in gaps])}
    </div>
    <div class="card">
      <h3>人工 review 重点</h3>
      <div class="fact-list">
        {''.join(render_fact_row(item.get("focus", ""), item.get("why", "")) for item in focus)}
      </div>
    </div>
  </div>
  <h3>证据边界</h3>
  {render_table(["来源", "边界", "动作"], [[r.get("source", ""), r.get("boundary", ""), r.get("action", "")] for r in boundaries])}
  <h3>进入下一阶段的条件</h3>
  {render_table(["条件", "状态", "原因"], [[r.get("condition", ""), r.get("status", ""), r.get("why", "")] for r in next_conditions])}
</section>"""


def render_source_section(analysis: dict[str, Any]) -> str:
    source_rows = [
        [r.get("name", ""), "是" if r.get("exists") else "否", r.get("packet_id", ""), r.get("confidence", ""), r.get("path", "")]
        for r in as_list(analysis.get("source_packets"))
    ]
    audit = analysis.get("run_status_audit") or {}
    next_actions = [
        [r.get("stage", ""), r.get("label", ""), r.get("reason", ""), r.get("next_step", "")]
        for r in as_list(audit.get("next_actions"))
    ]
    return f"""
<section class="section">
  <p class="eyebrow">来源与状态</p>
  <h2>证据引用与运行状态</h2>
  {render_table(["来源", "存在", "Packet", "置信度", "路径"], source_rows, wide=True)}
  <h3>建议下一步动作</h3>
  {render_table(["阶段", "动作", "原因", "下一步"], next_actions)}
</section>"""


def render_fact_row(label: str, value: str) -> str:
    return f"""<div class="fact-row"><span class="tag">{escape(label[:8] or "动作")}</span><div>{escape(value)}</div></div>"""


def render_table(headers: list[str], rows: list[list[Any]], wide: bool = False) -> str:
    if not rows:
        rows = [["暂无数据"] + [""] * (len(headers) - 1)]
    cls = "table-wrap table-scroll wide-table" if wide else "table-wrap"
    header_html = "".join(f"<th>{escape(str(header))}</th>" for header in headers)
    row_html = ""
    for row in rows:
        padded = list(row) + [""] * max(0, len(headers) - len(row))
        row_html += "<tr>" + "".join(f"<td>{escape(public_text(cell))}</td>" for cell in padded[: len(headers)]) + "</tr>"
    return f"""<div class="{cls}"><table><thead><tr>{header_html}</tr></thead><tbody>{row_html}</tbody></table></div>"""


def keyword_total(analysis: dict[str, Any]) -> int:
    roles = ((analysis.get("keyword_pool") or {}).get("roles") or {})
    return sum(len(as_list(rows)) for rows in roles.values()) if isinstance(roles, dict) else 0


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


def run_delivery_qa(analysis: dict[str, Any], analysis_json: Path, html_path: Path, xlsx_path: Path) -> dict[str, Any]:
    checks = {
        "analysis_json_exists": analysis_json.exists(),
        "html_exists": html_path.exists(),
        "xlsx_exists": xlsx_path.exists(),
        "has_category_derivation": bool(analysis.get("category_selection_derivation")),
        "has_market_validation": bool(analysis.get("seller_sprite_validation")),
        "has_keyword_pool": bool((analysis.get("keyword_pool") or {}).get("roles")),
        "has_no_removed_legacy_sections": _has_no_removed_legacy_sections(html_path),
    }
    failures = [name for name, passed in checks.items() if not passed]
    return {"status": "pass" if not failures else "fail", "checks": checks, "failures": failures}


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
