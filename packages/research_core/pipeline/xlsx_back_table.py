#!/usr/bin/env python3
"""Generate XLSX back-table sheets from report_data.json."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from packages.research_core.pipeline._utils import (
    _report_value, as_list, join_text,
)

def xlsx_sheets_from_report_data(report_data_path: Path) -> list[tuple[str, list[list[object]]]]:
    """从 AI 手写的 report_data.json 重建 XLSX，保证与 HTML 数据一致。"""
    rd = json.loads(report_data_path.read_text(encoding="utf-8"))
    hero = rd.get("hero") or {}
    verdict = hero.get("verdict", "")
    if isinstance(verdict, dict):
        verdict = verdict.get("value", verdict.get("label", str(verdict)))

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

    def _rv(val: Any) -> Any:
        return _report_value(val)

    lead_analysis = hero.get("lead_analysis", hero.get("one_sentence", ""))
    lead_analysis = _rv(lead_analysis)
    cp = rd.get("category_panorama") or {}
    categories = _as_list(cp.get("categories") or cp.get("category_landscape"))
    cat = categories[0] if categories else (cp.get("selected_category") or {})
    sub = cp.get("sub_market") or {}
    health = cp.get("market_health") or {}
    season = cp.get("seasonality") or {}
    cat_name = _rv(cat.get("category_name", cat.get("name", ""))) if isinstance(cat, dict) else ""
    cat_node_id = _rv(cat.get("node_id", "")) if isinstance(cat, dict) else ""
    cat_monthly_sales = _rv(cat.get("top100_monthly_sales", cat.get("monthly_units", ""))) if isinstance(cat, dict) else ""
    cat_monthly_revenue = _rv(cat.get("top100_monthly_revenue", cat.get("monthly_revenue", ""))) if isinstance(cat, dict) else ""
    cat_avg_price = _rv(cat.get("avg_price", cat.get("average_price", ""))) if isinstance(cat, dict) else ""
    cat_avg_rating = _rv(cat.get("avg_rating", "")) if isinstance(cat, dict) else ""

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
                (s.get("title", s.get("action", s.get("step", ""))) if isinstance(s, dict) else str(s))
                for s in steps[:3]
            )
        return "联系供应商打样 → 样品实测 → 准备Listing"

    # 1. Summary
    summary = [
        ["field", "value"],
        ["run_id", rd.get("run_id", "")],
        ["verdict", verdict],
        ["confidence", hero.get("confidence", "")],
        ["one_sentence_conclusion", lead_analysis],
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
        ["summary", cat_name, "", f"node_id={cat_node_id}", "", ""],
        ["step", "类目选择", str(cat_name) + " (" + str(cat_node_id) + ")", str(cat_monthly_sales) + " units, $" + str(cat_avg_price), "主战场", "category_panorama.categories[0]"],
        ["step", "子市场", str(sub.get("product_form", "")), str(sub.get("estimated_monthly_units", "")), "聚焦细分", "category_panorama.sub_market"],
        ["step", "健康度", "Top3:" + str(health.get("top3_brand_share", "")) + " 中国:" + str(health.get("china_seller_share", "")) + " 新品:" + str(health.get("new_3m_share", "")), str(health.get("concentration_note", "")), "", "category_panorama.market_health"],
        ["step", "季节性", "旺季:" + ", ".join(season.get("peak_months", [])) + " 淡季:" + ", ".join(season.get("trough_months", [])), str(season.get("peak_trough_ratio", "")), "", "category_panorama.seasonality"],
    ]

    # 4. Category Candidates
    cat_candidates = [
        ["category_name", "node_id", "category_path", "category_role", "matched_asin_count", "evidence_strength", "recommended_use", "risk_tags"],
    ]
    for ci, c_cat in enumerate(categories):
        if isinstance(c_cat, dict):
            cat_candidates.append([
                _rv(c_cat.get("category_name", "")),
                _rv(c_cat.get("node_id", "")),
                _rv(c_cat.get("category_path", "")),
                _rv(c_cat.get("category_role", "")),
                _rv(c_cat.get("product_count_in_category", "")),
                "high" if ci == 0 else "medium",
                _rv(c_cat.get("category_role", "主战场" if ci == 0 else "")) or ("主战场" if ci == 0 else ""),
                "",
            ])

    # 5. Reference ASINs
    ref_asins = [
        ["asin", "route_ref", "role", "similarity_reason", "category_path", "price", "monthly_sales", "rating_count"],
    ]
    for c in _as_list(rd.get("competitors")):
        if isinstance(c, dict):
            ref_asins.append([
                _rv(c.get("asin", "")),
                _rv(c.get("route", c.get("route_ref", ""))),
                _rv(c.get("asin_role", c.get("role", "primary_reference"))),
                c.get("judgment", c.get("positioning", c.get("similarity_reason", ""))),
                "",
                _rv(c.get("price", "")),
                _rv(c.get("monthly_sales", "")),
                _rv(c.get("rating_count", "")),
            ])

    # 6. Market Opportunity
    market_opp = [
        ["type", "field_1", "field_2", "field_3", "field_4", "field_5"],
        ["primary_market", "category_name", cat_name, "", "", ""],
        ["primary_market", "node_id", cat_node_id, "", "", ""],
        ["primary_market", "monthly_units", cat_monthly_sales, "", "", ""],
        ["primary_market", "monthly_revenue_usd", cat_monthly_revenue, "", "", ""],
        ["primary_market", "avg_price_usd", cat_avg_price, "", "", ""],
        ["primary_market", "avg_rating", cat_avg_rating, "", "", ""],
    ]
    for pb in _as_list(rd.get("price_bands")):
        if isinstance(pb, dict):
            market_opp.append([
                "price_band",
                _rv(pb.get("label", pb.get("range", pb.get("band", "")))),
                _rv(pb.get("unit_share", pb.get("sales_share", ""))),
                str(_rv(pb.get("product_count", ""))),
                _rv(pb.get("opportunity_level", "")),
                pb.get("judgment", pb.get("reason", pb.get("recommendation", ""))),
            ])

    # 7. Keyword Pool
    kw_pool = [
        ["role", "keyword", "monthly_search_volume", "cpc", "competitor_count", "mix_pool_score", "mix_pool_risk_level", "reason", "recommended_action"],
    ]
    for kw in _as_list(rd.get("keywords")):
        if isinstance(kw, dict):
            kw_pool.append([
                kw.get("role", ""),
                _rv(kw.get("keyword", "")),
                _rv(kw.get("monthly_search_volume", "")),
                _rv(kw.get("cpc", "")),
                _rv(kw.get("competitor_count", "")),
                "",
                "",
                kw.get("strategy", ""),
                "",
            ])

    # 8. VOC
    voc = [
        ["dimension", "issue", "review_count", "spec_requirement", "evidence", "next_check"],
    ]
    for pp in _as_list(rd.get("pain_points")):
        if isinstance(pp, dict):
            voc.append([
                _rv(pp.get("dimension", "")),
                pp.get("issue_description", pp.get("issue", "")),
                _rv(pp.get("review_count", "")),
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
            route = _rv(c.get("route", c.get("route_ref", "")))
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
                "[" + str(r.get("severity", "")) + "] " + str(r.get("description", r.get("title", ""))),
                r.get("evidence_basis", r.get("detail", "")),
                r.get("mitigation", ""),
            ])
    for adv in _as_list(rd.get("advantages")):
        if isinstance(adv, dict):
            risks_next.append([
                "boundary",
                "优势",
                adv.get("description", adv.get("title", "")),
                adv.get("evidence_basis", adv.get("detail", "")),
                "",
            ])
    for cond in _as_list(rd.get("gonogo_conditions")):
        if isinstance(cond, dict):
            risks_next.append([
                "next_condition",
                cond.get("current_status", cond.get("status", "")),
                cond.get("condition", ""),
                cond.get("go_threshold", cond.get("detail", "")),
                cond.get("source_path", ""),
            ])
    for ns in _as_list(rd.get("next_steps")):
        if isinstance(ns, dict):
            risks_next.append([
                "next_step",
                "行动计划",
                ns.get("title", ns.get("action", ns.get("step", ""))),
                ns.get("description", ns.get("detail", "")),
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
