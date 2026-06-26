#!/usr/bin/env python3
"""Generate XLSX decision workbook (5 sheets) from report_data.json + integrated_operator_judgment.json.

Sheet structure per report_design_spec.md Section 6:
  1. 路线计分卡 — route × 6 dimensions + one-line judgment
  2. 竞品拆解 — full competitor profile with weakness/counter
  3. 关键词矩阵 — keyword × intent × search volume × CPC
  4. 样品检查表 — VOC pain point → test item → pass criteria
  5. 冷启动预算 — cost item × estimate (operator fills actual)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from packages.research_core.pipeline._utils import (
    _report_value, as_list,
)


def xlsx_sheets_from_report_data(
    report_data_path: Path,
    judgment_path: Path | None = None,
) -> list[tuple[str, list[list[object]]]]:
    rd = json.loads(report_data_path.read_text(encoding="utf-8"))
    judgment = None
    if judgment_path and judgment_path.exists():
        judgment = json.loads(judgment_path.read_text(encoding="utf-8"))

    def _rv(val: Any) -> Any:
        return _report_value(val)

    sheets: list[tuple[str, list[list[object]]]] = []

    # ── Sheet 1: 路线计分卡 ─────────────────────────────────────────────
    sheets.append(("路线计分卡", _route_scorecard(rd, judgment, _rv)))

    # ── Sheet 2: 竞品拆解 ───────────────────────────────────────────────
    sheets.append(("竞品拆解", _competitor_breakdown(rd, judgment, _rv)))

    # ── Sheet 3: 关键词矩阵 ─────────────────────────────────────────────
    sheets.append(("关键词矩阵", _keyword_matrix(rd, _rv)))

    # ── Sheet 4: 样品检查表 ─────────────────────────────────────────────
    sheets.append(("样品检查表", _sample_checklist(rd, _rv)))

    # ── Sheet 5: 冷启动预算 ─────────────────────────────────────────────
    sheets.append(("冷启动预算", _cold_start_budget(judgment, _rv)))

    return sheets


def _route_scorecard(rd: dict, judgment: dict | None, _rv) -> list[list[object]]:
    """路线计分卡：每条路线 × 6 维度评分 + 一句话判断。运营可改权重重新排序。"""
    header = [
        "路线名", "市场需求", "竞争结构", "价格利润", "VOC机会",
        "风险", "数据质量", "综合判断", "tradeoff_得到什么",
        "tradeoff_放弃什么", "tradeoff_适合谁", "tradeoff_不适合谁",
    ]
    rows = [header]

    # Try to get route breakdowns from judgment first, then fall back to evaluation summary
    route_recs = []
    if judgment:
        route_recs = judgment.get("route_recommendation") or []
        if isinstance(route_recs, dict):
            route_recs = list(route_recs.values())

    tradeoffs = {}
    if judgment:
        to_list = judgment.get("route_tradeoff") or []
        if isinstance(to_list, dict):
            to_list = list(to_list.values())
        for t in as_list(to_list):
            if isinstance(t, dict):
                tradeoffs[t.get("route_name", "")] = t

    if not route_recs:
        # Fallback: extract routes from competitors
        routes_seen = set()
        for c in as_list(rd.get("competitors")):
            if isinstance(c, dict):
                rn = _rv(c.get("route", c.get("route_ref", "")))
                if rn and rn not in routes_seen:
                    routes_seen.add(rn)
                    rows.append([rn, "", "", "", "", "", "", "", "", "", "", ""])
        return rows

    for rec in as_list(route_recs):
        if not isinstance(rec, dict):
            continue
        rn = rec.get("route_name", rec.get("name", ""))
        to = tradeoffs.get(rn, {})
        rows.append([
            rn,
            _rv(rec.get("market_demand", rec.get("demand_score", ""))),
            _rv(rec.get("competition", rec.get("competition_score", ""))),
            _rv(rec.get("price_profit", rec.get("profit_score", ""))),
            _rv(rec.get("voc_opportunity", rec.get("voc_score", ""))),
            _rv(rec.get("risk", rec.get("risk_score", ""))),
            _rv(rec.get("data_quality", rec.get("data_score", ""))),
            _rv(rec.get("judgment", rec.get("one_line_judgment", rec.get("verdict", "")))),
            _rv(to.get("gain", "")),
            _rv(to.get("lose", "")),
            _rv(to.get("best_for", "")),
            _rv(to.get("worst_for", "")),
        ])
    return rows


def _competitor_breakdown(rd: dict, judgment: dict | None, _rv) -> list[list[object]]:
    """竞品拆解：每个核心竞品的完整画像，含致命弱点和反击方案。"""
    header = [
        "ASIN", "品牌", "月销", "价格", "评分", "评论数", "上架时间",
        "路线", "致命弱点_VOC原文", "可抄的优点", "我的反击方案", "反击难度",
    ]
    rows = [header]

    weakness_map = {}
    if judgment:
        wm_list = judgment.get("competitor_weakness_map") or []
        if isinstance(wm_list, dict):
            wm_list = list(wm_list.values())
        for w in as_list(wm_list):
            if isinstance(w, dict):
                asin = w.get("asin", "")
                if asin:
                    weakness_map[asin] = w

    benchmark = {}
    if judgment:
        bm_list = judgment.get("competitor_benchmark") or []
        if isinstance(bm_list, dict):
            bm_list = list(bm_list.values())
        for b in as_list(bm_list):
            if isinstance(b, dict):
                asin = b.get("asin", "")
                if asin:
                    benchmark[asin] = b

    for c in as_list(rd.get("competitors")):
        if not isinstance(c, dict):
            continue
        asin = _rv(c.get("asin", ""))
        w = weakness_map.get(asin, {})
        b = benchmark.get(asin, {})
        rows.append([
            asin,
            _rv(c.get("brand", "")),
            _rv(c.get("monthly_sales", c.get("monthly_units", ""))),
            _rv(c.get("price", "")),
            _rv(c.get("rating", "")),
            _rv(c.get("rating_count", c.get("reviews", ""))),
            _rv(c.get("available_date", c.get("date_listed", ""))),
            _rv(c.get("route", c.get("route_ref", ""))),
            _rv(w.get("voc_evidence", w.get("fatal_weakness", ""))),
            _rv(b.get("strength", b.get("advantage", ""))),
            _rv(w.get("my_counter", "")),
            _rv(w.get("counter_difficulty", "")),
        ])
    return rows


def _keyword_matrix(rd: dict, _rv) -> list[list[object]]:
    """关键词矩阵：运营可以直接拿去建广告组。"""
    header = [
        "关键词", "意图分类", "月搜量", "CPC", "竞品数", "策略说明",
    ]
    rows = [header]

    keywords = rd.get("keywords") or {}
    if isinstance(keywords, dict):
        # Try dict-of-lists pattern (intent → keywords)
        if any(isinstance(v, list) for v in keywords.values()):
            for intent, kw_list in keywords.items():
                for kw in as_list(kw_list):
                    if isinstance(kw, dict):
                        rows.append([
                            _rv(kw.get("keyword", kw.get("term", ""))),
                            intent,
                            _rv(kw.get("monthly_search_volume", kw.get("search_volume", ""))),
                            _rv(kw.get("cpc", "")),
                            _rv(kw.get("competitor_count", "")),
                            _rv(kw.get("strategy", kw.get("recommended_action", ""))),
                        ])
        else:
            for kw in as_list(keywords):
                if isinstance(kw, dict):
                    rows.append([
                        _rv(kw.get("keyword", kw.get("term", ""))),
                        _rv(kw.get("role", kw.get("intent", ""))),
                        _rv(kw.get("monthly_search_volume", kw.get("search_volume", ""))),
                        _rv(kw.get("cpc", "")),
                        _rv(kw.get("competitor_count", "")),
                        _rv(kw.get("strategy", kw.get("recommended_action", ""))),
                    ])
    return rows


def _sample_checklist(rd: dict, _rv) -> list[list[object]]:
    """样品检查表：VOC 痛点 → 测试项 → 通过标准。运营填实际结果。"""
    header = [
        "痛点维度", "优先级", "竞品问题描述", "测试项", "通过标准",
        "实际结果_运营填", "是否通过_运营填",
    ]
    rows = [header]

    for pp in as_list(rd.get("pain_points")):
        if not isinstance(pp, dict):
            continue
        rows.append([
            _rv(pp.get("dimension", "")),
            _rv(pp.get("priority", pp.get("severity", ""))),
            _rv(pp.get("issue_description", pp.get("issue", ""))),
            _rv(pp.get("test_item", pp.get("spec_requirement", ""))),
            _rv(pp.get("pass_criteria", pp.get("spec_target", ""))),
            "",  # 运营填写
            "",  # 运营填写
        ])
    return rows


def _cold_start_budget(judgment: dict | None, _rv) -> list[list[object]]:
    """冷启动预算：数量级估算 + 运营填实际数字。"""
    header = [
        "费用项", "预估金额_数量级", "实际金额_运营填", "备注",
    ]
    rows = [header]

    if not judgment:
        rows.append(["无冷启动估算数据", "", "", "请先运行 Stage 10 Lead Operator Agent"])
        return rows

    cs = judgment.get("cold_start_estimate") or {}
    confidence_note = _rv(cs.get("confidence_note", "以上为数量级估算，实际取决于产品力、Listing质量和广告效率"))

    # Standard line items
    items = [
        ("广告费（前3个月）", cs.get("ad_budget", cs.get("budget_range", ""))),
        ("Vine评论计划", "$200（亚马逊官方费用）"),
        ("样品打样费", cs.get("sample_cost", "")),
        ("FBA物流（前3个月）", cs.get("fba_cost", "")),
        ("采购库存（首批）", cs.get("inventory_cost", "")),
        ("Listing拍摄/A+制作", cs.get("listing_cost", "$300-800（拍摄+A+设计）")),
        ("商标/品牌注册", cs.get("brand_registry_cost", "$225-600（视国家）")),
    ]

    total_est = ""
    for label, value in items:
        display_value = _rv(value) if value else "待估算"
        if label == "广告费（前3个月）" and cs.get("budget_range"):
            display_value = _rv(cs["budget_range"])
        rows.append([label, display_value, "", ""])

    # Total row
    if cs.get("budget_range"):
        total_est = _rv(cs["budget_range"])
    rows.append(["合计（数量级）", total_est, "", confidence_note])

    # Key metrics for reference
    metrics = [
        ("评论门槛", cs.get("review_threshold", "")),
        ("CPC预估", cs.get("cpc_estimate", "")),
        ("冷启动周期", cs.get("timeline", "")),
    ]
    for label, value in metrics:
        if value:
            rows.append([f"参考：{label}", _rv(value), "", ""])

    return rows


# ── Legacy API compatibility ──────────────────────────────────────────────

def build_workbook_sheets(analysis: dict[str, Any]) -> list[tuple[str, list[list[object]]]]:
    """Legacy wrapper — used by build_analysis_packet flow (not decision workbook)."""
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
        rows.append(["step", item.get("name", ""), item.get("evidence", ""), item.get("implication", ""), item.get("decision", ""), item.get("lineage", "")])
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
