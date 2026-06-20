#!/usr/bin/env python3
"""Build a minimal research package from one candidate in a candidate pool."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
import argparse

from packages.research_core.contracts import validate_research_package_chapters

from packages.research_core.pipeline.shared import _select_candidate
from packages.research_core.pipeline.scoring import _build_entry_barriers, _build_go_nogo_scorecard
from packages.research_core.pipeline.route_matrix import (
    _build_product_route_matrix, _build_route_deep_dive_plan,
)
from packages.research_core.pipeline.decision_review import (
    _build_ai_analysis_brief, _build_decision_review, _status_next_step,
)
from packages.research_core.pipeline.market_boundary import _apply_market_boundary_quality
from packages.research_core.pipeline.market_text import _positive_count
from packages.research_core.pipeline.competitor_analysis import (
    _build_competitor_deep_dive, _competitor_items,
)
from packages.research_core.pipeline.voc_analysis import (
    _append_sentence, _build_voc_analysis,
    _build_voc_opportunities, _voc_dashboard_card,
    _voc_summary_line,
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
