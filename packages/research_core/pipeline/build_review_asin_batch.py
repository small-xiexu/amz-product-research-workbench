#!/usr/bin/env python3
"""Build P5 VOC review ASIN batch plan — generates the ASIN collection list for review plugins.

Pure data tool: reads P4 artifacts, assigns ASIN roles by route coverage and competitor type.
Does NOT do pain point analysis, gate decisions, or report generation.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from packages.research_core.contracts import (
    P4_STAGE_ID,
    validate_candidate_pool,
    validate_p4_evidence_packet,
    validate_workflow_state,
)
from packages.research_core.pipeline._utils import as_list, first_text, load_json, numeric_value, _run_id


P5_SCHEMA_VERSION = "p5-voc-gate-v1"
REVIEW_VOC_DIR = "review_voc"
ASIN_BATCH_NAME = "review_asin_batch.json"

P5_ASIN_BATCH_INPUT_ARTIFACTS = [
    "workflow_state.json",
    "candidate_pool.json",
    "route_matrix_confirm.json",
    "progress.json",
    "market_structure/market_structure_evidence_packet.json",
    "search_demand/search_demand_evidence_packet.json",
    "conflict_review/deep_data_completeness_check.json",
    "conflict_review/conflict_resolution_packet.json",
]
P5_ASIN_BATCH_OUTPUT_ARTIFACTS = [
    f"{REVIEW_VOC_DIR}/{ASIN_BATCH_NAME}",
]

ASIN_ROLES = (
    "primary_reference",
    "high_sales_benchmark",
    "target_price_band_sample",
    "new_release_sample",
    "premium_benchmark",
    "painpoint_reference",
    "excluded_reference",
)

PRIORITY_ORDER = (
    "primary_reference",
    "high_sales_benchmark",
    "painpoint_reference",
    "target_price_band_sample",
    "new_release_sample",
    "premium_benchmark",
    "excluded_reference",
)


class P5AsinBatchError(Exception):
    """Raised when the ASIN batch cannot be built."""


def run_review_asin_batch(run_dir: Path | str) -> dict[str, Path]:
    """Generate review_asin_batch.json from P4 artifacts.

    If zero ASINs can be extracted from all P4 sources, this is a hard block:
    no batch file is written, progress is updated to blocked/needs_user, and
    the caller receives only the progress path.
    """
    run_path = Path(run_dir).expanduser().resolve()
    _validate_inputs(run_path)

    workflow_state = load_json(run_path / "workflow_state.json")
    candidate_pool = load_json(run_path / "candidate_pool.json")
    route_matrix = load_json(run_path / "route_matrix_confirm.json")
    progress = load_json(run_path / "progress.json")
    market_packet = load_json(run_path / "market_structure" / "market_structure_evidence_packet.json")
    search_packet = load_json(run_path / "search_demand" / "search_demand_evidence_packet.json")
    completeness_check = load_json(run_path / "conflict_review" / "deep_data_completeness_check.json")
    conflict_packet = load_json(run_path / "conflict_review" / "conflict_resolution_packet.json")

    batch = build_asin_batch(
        workflow_state,
        candidate_pool,
        route_matrix,
        market_packet,
        search_packet,
        completeness_check,
        conflict_packet,
        run_path,
    )

    # Zero ASINs → hard block: no batch file, progress-only with needs_user
    if not batch.get("asin_items"):
        progress_path = run_path / "progress.json"
        updated_progress = _update_progress_blocked(progress, workflow_state, run_path)
        progress_path.write_text(json.dumps(updated_progress, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return {"progress": progress_path}

    output_dir = run_path / REVIEW_VOC_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    batch_path = output_dir / ASIN_BATCH_NAME
    batch_path.write_text(json.dumps(batch, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # 自动创建 inputs/reviews/ 目录及导出说明
    reviews_input_dir = run_path / "inputs" / "reviews"
    reviews_input_dir.mkdir(parents=True, exist_ok=True)
    _write_export_readme(reviews_input_dir, batch)

    progress_path = run_path / "progress.json"
    updated_progress = _update_progress(progress, workflow_state, batch, batch_path)
    progress_path.write_text(json.dumps(updated_progress, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return {
        "asin_batch": batch_path,
        "progress": progress_path,
    }


def build_asin_batch(
    workflow_state: dict[str, Any],
    candidate_pool: dict[str, Any],
    route_matrix: dict[str, Any],
    market_packet: dict[str, Any],
    search_packet: dict[str, Any],
    completeness_check: dict[str, Any],
    conflict_packet: dict[str, Any],
    run_path: Path | None = None,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    run_id = _run_id(workflow_state, run_path)
    site = _site(workflow_state)

    selected_routes = _extract_selected_routes(route_matrix)
    rejected_routes = _extract_rejected_routes(route_matrix)

    # Extract all ASIN candidates from multiple sources
    pool_asins = _extract_pool_asins(candidate_pool)
    market_asins = _extract_evidence_asins(market_packet)
    search_asins = _extract_evidence_asins(search_packet)

    all_asins: dict[str, dict[str, Any]] = {}
    _merge_asin(pool_asins, all_asins, "candidate_pool")
    _merge_asin(market_asins, all_asins, "seller_sprite")
    _merge_asin(search_asins, all_asins, "sorftime")

    # Assign roles and routes
    warnings = _collect_warnings(completeness_check, conflict_packet)
    asin_items = _assign_roles(all_asins, selected_routes, rejected_routes)
    route_coverage = _build_route_coverage(asin_items, selected_routes, rejected_routes)
    data_gaps = _build_data_gaps(asin_items, selected_routes, route_coverage)

    return {
        "schema_version": P5_SCHEMA_VERSION,
        "batch_id": "review_asin_batch",
        "run_id": run_id,
        "generated_at": now,
        "source_route_matrix": "route_matrix_confirm.json",
        "source_candidate_pool": "candidate_pool.json",
        "source_evidence_packets": [
            "market_structure/market_structure_evidence_packet.json",
            "search_demand/search_demand_evidence_packet.json",
        ],
        "source_completeness_check": "conflict_review/deep_data_completeness_check.json",
        "source_conflict_packet": "conflict_review/conflict_resolution_packet.json",
        "site": site,
        "selected_routes": selected_routes,
        "p4_warnings": warnings,
        "asin_items": asin_items,
        "route_coverage": route_coverage,
        "operator_instruction": _operator_instruction(run_path, site),
        "data_gaps": data_gaps,
        "next_required_action": _next_action(data_gaps, warnings),
        "evidence_refs": [
            "candidate_pool.json",
            "route_matrix_confirm.json",
            "market_structure/market_structure_evidence_packet.json#evidence_items",
            "search_demand/search_demand_evidence_packet.json#evidence_items",
        ],
    }


def _validate_inputs(run_path: Path) -> None:
    for artifact in P5_ASIN_BATCH_INPUT_ARTIFACTS:
        path = run_path / artifact
        if not path.exists():
            raise P5AsinBatchError(f"required input not found: {artifact}")


# ── ASIN extraction ────────────────────────────────────────────────────

def _extract_pool_asins(candidate_pool: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    candidates = as_list(candidate_pool.get("candidates") or candidate_pool.get("items"))
    for entry in candidates:
        if not isinstance(entry, dict):
            continue
        asin = _normalize_asin(entry.get("asin") or entry.get("ASIN"))
        if not asin:
            continue
        result[asin] = {
            "asin": asin,
            "price": numeric_value(entry.get("price") or entry.get("Price")),
            "rating": numeric_value(entry.get("rating") or entry.get("Rating") or entry.get("avgRating")),
            "ratings": numeric_value(entry.get("ratings") or entry.get("reviews") or entry.get("Ratings")),
            "monthly_sales": numeric_value(entry.get("monthly_sales") or entry.get("totalUnits") or entry.get("MonthlySales")),
            "brand": first_text(entry.get("brand") or entry.get("Brand")),
            "seller": first_text(entry.get("seller") or entry.get("sellerName") or entry.get("Seller")),
            "category": first_text(entry.get("category") or entry.get("nodeIdPath")),
            "route_ref": first_text(entry.get("route_ref") or entry.get("route")),
            "is_mixed_pool": bool(entry.get("is_mixed_pool") or entry.get("mixed_pool")),
        }
    return result


def _extract_evidence_asins(packet: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    evidence_items = as_list(packet.get("evidence_items"))
    for item in evidence_items:
        if not isinstance(item, dict):
            continue
        item_type = first_text(item.get("item_type"))
        if item_type not in ("competitor_structure", "asin_operating_data"):
            continue
        facts = item.get("facts", {}) if isinstance(item.get("facts"), dict) else {}
        raw = facts.get("raw_value", {}) if isinstance(facts, dict) else {}
        normalized = facts.get("normalized_value", {}) if isinstance(facts, dict) else {}
        rows = _evidence_rows(raw, normalized)
        for row in rows:
            asin = _normalize_asin(row.get("asin") or row.get("ASIN"))
            if not asin:
                continue
            result[asin] = {
                "asin": asin,
                "price": numeric_value(row.get("price") or row.get("Price")),
                "rating": numeric_value(row.get("rating") or row.get("Rating")),
                "ratings": numeric_value(row.get("ratings") or row.get("reviews") or row.get("Ratings")),
                "monthly_sales": numeric_value(row.get("totalUnits") or row.get("total_units") or row.get("monthlySales")),
                "brand": first_text(row.get("brand") or row.get("Brand") or row.get("sellerName")),
                "seller": first_text(row.get("seller") or row.get("sellerName") or row.get("Seller")),
            }
    # Fallback: if no evidence_items, scan agent free-form facts structure
    if not result:
        result = _scan_facts_for_asins(packet.get("facts", {}))
    return result


def _scan_facts_for_asins(facts: Any) -> dict[str, dict[str, Any]]:
    """Scan agent free-form facts dict for any nested ASIN entries (e.g. facts.top100_basic, reference_asin_pool)."""
    result: dict[str, dict[str, Any]] = {}
    if not isinstance(facts, dict):
        return result

    def _scan(obj: Any) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        if isinstance(obj, dict):
            if _normalize_asin(obj.get("asin") or obj.get("ASIN")):
                rows.append(obj)
            for value in obj.values():
                rows.extend(_scan(value))
        elif isinstance(obj, list):
            for item in obj:
                if isinstance(item, dict):
                    if _normalize_asin(item.get("asin") or item.get("ASIN")):
                        rows.append(item)
                    else:
                        rows.extend(_scan(item))
        return rows

    for row in _scan(facts):
        asin = _normalize_asin(row.get("asin") or row.get("ASIN"))
        if not asin:
            continue
        result[asin] = {
            "asin": asin,
            "price": numeric_value(row.get("price") or row.get("Price")),
            "rating": numeric_value(row.get("rating") or row.get("Rating")),
            "ratings": numeric_value(row.get("ratings") or row.get("reviews") or row.get("Ratings")),
            "monthly_sales": numeric_value(row.get("monthly_sales") or row.get("totalUnits") or row.get("monthlySales")),
            "brand": first_text(row.get("brand") or row.get("Brand") or row.get("sellerName")),
            "seller": first_text(row.get("seller") or row.get("sellerName") or row.get("Seller")),
        }
    return result


def _evidence_rows(raw: Any, normalized: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict):
                rows.append(item)
    elif isinstance(raw, dict):
        for key in ("items", "rows", "items_sample", "rows_sample", "data", "products"):
            value = raw.get(key)
            if isinstance(value, list):
                rows.extend([item for item in value if isinstance(item, dict)])
        if not rows and raw:
            rows.append(raw)
    if not rows and normalized:
        rows.append(normalized)
    return rows


def _normalize_asin(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip().upper()
    if not text or text == "NONE" or len(text) < 5:
        return ""
    return text


def _merge_asin(
    source: dict[str, dict[str, Any]],
    target: dict[str, dict[str, Any]],
    source_name: str,
) -> None:
    for asin, info in source.items():
        if asin in target:
            existing = target[asin]
            for key in ("price", "rating", "ratings", "monthly_sales", "brand", "seller", "category"):
                if existing.get(key) is None and info.get(key) is not None:
                    existing[key] = info[key]
            sources = set(existing.get("_sources", []))
            sources.add(source_name)
            existing["_sources"] = list(sources)
        else:
            info["_sources"] = [source_name]
            target[asin] = info


# ── Role assignment ────────────────────────────────────────────────────

def _assign_roles(
    all_asins: dict[str, dict[str, Any]],
    selected_routes: list[str],
    rejected_routes: list[str],
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    exclude_asins: set[str] = set()

    # First pass: associate ASINs with routes based on candidate_pool route_ref
    for asin, info in all_asins.items():
        route_ref = info.get("route_ref", "")
        if route_ref and any(r in route_ref for r in rejected_routes):
            exclude_asins.add(asin)
            items.append(_make_item(asin, info, "excluded_reference", route_ref, "marked as excluded or mixed-pool route in candidate_pool"))
        elif route_ref:
            if route_ref not in [""]:
                items.append(_make_item(asin, info, _infer_role(info), route_ref, _infer_reason(info, route_ref)))

    # Second pass: assign unassigned ASINs to best-matching selected route
    assigned = {item["asin"] for item in items}
    for asin, info in all_asins.items():
        if asin in assigned:
            continue
        route_ref = selected_routes[0] if selected_routes else "<unknown_route>"
        items.append(_make_item(asin, info, _infer_role(info), route_ref, _infer_reason(info, route_ref)))

    # Sort by priority
    role_rank = {role: i for i, role in enumerate(PRIORITY_ORDER)}
    items.sort(key=lambda item: (role_rank.get(item.get("asin_role", ""), 99), first_text(item.get("asin"))))
    return items


def _infer_role(info: dict[str, Any]) -> str:
    sales = info.get("monthly_sales")
    ratings_count = info.get("ratings")
    rating = info.get("rating")
    if info.get("is_mixed_pool"):
        return "excluded_reference"
    if rating is not None and rating < 4.0:
        return "painpoint_reference"
    if ratings_count is not None and ratings_count < 50 and sales is not None and (sales or 0) > 0:
        return "new_release_sample"
    if sales is not None and (sales or 0) > 1000:
        return "high_sales_benchmark"
    if rating is not None and rating >= 4.5 and ratings_count is not None and ratings_count > 100:
        return "primary_reference"
    return "target_price_band_sample"


def _infer_reason(info: dict[str, Any], route_ref: str) -> str:
    sales = info.get("monthly_sales")
    ratings_count = info.get("ratings")
    rating = info.get("rating")
    price = info.get("price")
    parts: list[str] = []
    if info.get("is_mixed_pool"):
        parts.append("mixed-pool or excluded route ASIN for comparison baseline")
    elif rating is not None and rating < 4.0:
        parts.append(f"low rating ({rating}) suggests pain points worth investigating")
    elif ratings_count is not None and ratings_count < 50 and sales is not None and (sales or 0) > 0:
        parts.append(f"low review count ({int(ratings_count)}) with active sales — new release pattern")
    elif sales is not None and (sales or 0) > 1000:
        parts.append(f"high monthly sales ({int(sales)}) — volume benchmark")
    elif rating is not None and rating >= 4.5 and ratings_count is not None and ratings_count > 100:
        parts.append(f"strong rating ({rating}) with high review volume — primary reference")
    else:
        parts.append("representative price-band sample")
    if info.get("brand"):
        parts.append(f"brand: {info['brand']}")
    if price is not None:
        parts.append(f"price: {price:.2f}")
    return "；".join(parts)


def _make_item(asin: str, info: dict[str, Any], role: str, route_ref: str, reason: str) -> dict[str, Any]:
    sales = info.get("monthly_sales")
    ratings_count = info.get("ratings")
    rating = info.get("rating")
    price = info.get("price")
    return {
        "asin": asin,
        "asin_role": role,
        "route_ref": route_ref,
        "selection_reason": reason,
        "source": info.get("_sources", ["unknown"])[0] if info.get("_sources") else "unknown",
        "source_refs": info.get("_sources", []),
        "site": "US",
        "priority": _role_rank(role),
        "expected_review_focus": _review_focus(role),
        "metrics": {
            "monthly_sales": sales,
            "rating": rating,
            "ratings_count": int(ratings_count) if ratings_count is not None else None,
            "price": price,
            "brand": info.get("brand"),
        },
        "notes": _role_notes(role, sales, ratings_count, rating),
    }


def _role_rank(role: str) -> int:
    try:
        return PRIORITY_ORDER.index(role) + 1
    except ValueError:
        return 99


def _review_focus(role: str) -> str:
    focus = {
        "primary_reference": "main-route competitor review analysis — identify satisfaction drivers and differentiation gaps",
        "high_sales_benchmark": "high-volume seller review patterns — identify why customers choose this product",
        "target_price_band_sample": "price-band representative — understand value perception at this price point",
        "new_release_sample": "new-release traction signals — early adopter feedback and launch lessons",
        "premium_benchmark": "premium-tier quality expectations — identify what customers pay more for",
        "painpoint_reference": "low-rating pain point harvest — systematic negative feedback extraction",
        "excluded_reference": "mixed-pool or excluded baseline — confirm these are truly different use cases",
    }
    return focus.get(role, "general review analysis")


def _role_notes(role: str, sales: Any, ratings_count: Any, rating: Any) -> str:
    parts: list[str] = []
    if role == "painpoint_reference" and rating is not None:
        parts.append(f"low rating ({rating:.1f}) — prioritize negative review extraction")
    if role == "new_release_sample" and ratings_count is not None:
        parts.append(f"low review count ({int(ratings_count)}) — may not have enough reviews for confident pain point analysis")
    if role == "high_sales_benchmark" and sales is not None:
        parts.append(f"high volume ({int(sales):,}/mo) — reviews provide volume-weighted perspective")
    if role == "excluded_reference":
        parts.append("do not mix into primary route conclusions")
    return "；".join(parts) if parts else ""


# ── Route coverage ─────────────────────────────────────────────────────

def _build_route_coverage(
    asin_items: list[dict[str, Any]],
    selected_routes: list[str],
    rejected_routes: list[str],
) -> list[dict[str, Any]]:
    all_routes = list(selected_routes) + list(rejected_routes)
    coverage: dict[str, dict[str, Any]] = {}
    for route in all_routes:
        coverage[route] = {"route_ref": route, "asin_count": 0, "roles_covered": [], "missing_roles": []}
    for item in asin_items:
        route = item.get("route_ref", "")
        if route in coverage:
            coverage[route]["asin_count"] += 1
            role = item.get("asin_role", "")
            if role and role not in coverage[route]["roles_covered"]:
                coverage[route]["roles_covered"].append(role)
    for route, info in coverage.items():
        info["roles_covered"] = sorted(set(info["roles_covered"]))
        info["missing_roles"] = sorted(set(ASIN_ROLES) - set(info["roles_covered"]))
    return list(coverage.values())


def _build_data_gaps(
    asin_items: list[dict[str, Any]],
    selected_routes: list[str],
    route_coverage: list[dict[str, Any]],
) -> list[dict[str, str]]:
    gaps: list[dict[str, str]] = []
    if not asin_items:
        gaps.append({"gap_type": "no_asins", "description": "no ASINs found across all data sources", "impact": "cannot generate VOC batch"})
    for rc in route_coverage:
        if rc["asin_count"] == 0 and rc["route_ref"] in selected_routes:
            gaps.append({
                "gap_type": "route_no_coverage",
                "route_ref": rc["route_ref"],
                "description": f"route '{rc['route_ref']}' has zero ASIN coverage from P4 evidence packets and candidate pool",
                "impact": "VOC analysis for this route will be incomplete",
            })
        missing = rc.get("missing_roles", [])
        critical_roles = {"primary_reference", "painpoint_reference"}
        missing_critical = missing and critical_roles & set(missing)
        if missing_critical:
            gaps.append({
                "gap_type": "route_missing_critical_roles",
                "route_ref": rc["route_ref"],
                "description": f"route '{rc['route_ref']}' missing critical roles: {', '.join(sorted(critical_roles & set(missing)))}",
                "impact": "VOC conclusions may lack reference benchmarks",
            })
    return gaps


# ── Warnings and next actions ──────────────────────────────────────────

def _collect_warnings(
    completeness_check: dict[str, Any],
    conflict_packet: dict[str, Any],
) -> list[dict[str, str]]:
    warnings: list[dict[str, str]] = []
    if completeness_check.get("completeness_level") in ("warning", "blocker"):
        warnings.append({
            "source": "deep_data_completeness_check",
            "level": completeness_check.get("completeness_level", "unknown"),
            "description": f"data completeness is {completeness_check.get('completeness_level')} — review blocking_gaps before trusting ASIN selection",
        })
    if conflict_packet.get("conflict_level") in ("warning", "blocker"):
        warnings.append({
            "source": "conflict_resolution_packet",
            "level": conflict_packet.get("conflict_level", "unknown"),
            "description": f"P4 conflict level is {conflict_packet.get('conflict_level')} — cross-source ASIN metrics may be inconsistent",
        })
    return warnings


def _next_action(data_gaps: list[dict[str, str]], warnings: list[dict[str, str]]) -> dict[str, Any]:
    if not data_gaps:
        return {
            "action": "proceed_to_operator_export",
            "description": "ASIN batch is complete — give operator the ASIN list for review plugin export",
            "stage_id": "stage_7_voc_gate",
            "substage": "P5-2",
        }
    critical_gaps = [g for g in data_gaps if "no_asins" in g.get("gap_type", "") or "route_no_coverage" in g.get("gap_type", "")]
    if critical_gaps:
        return {
            "action": "review_gaps_before_export",
            "description": "critical ASIN coverage gaps found — operator may still export available ASINs, but coverage will be marked incomplete",
            "stage_id": "stage_7_voc_gate",
            "substage": "P5-2",
            "critical_gaps": [g.get("description") for g in critical_gaps],
        }
    return {
        "action": "proceed_to_operator_export",
        "description": "ASIN batch is complete with minor gaps — give operator the ASIN list for review plugin export",
        "stage_id": "stage_7_voc_gate",
        "substage": "P5-2",
    }


def _operator_instruction(run_path: Path | None, site: str) -> dict[str, Any]:
    run_dir = str(run_path) if run_path else "<run_dir>"
    return {
        "site": site,
        "entry_point": "评论慢速采集助手",
        "put_dir": f"{run_dir}/inputs/reviews/",
        "file_naming": f"{site}_review_voc_<batch>_<date>.xlsx",
        "import_command": f"python3 scripts/build_review_voc_package.py {run_dir} {run_dir}/inputs/reviews/<export_file>",
        "operator_note": "只需将下方 ASIN 清单粘贴到评论插件的 ASIN 输入框（一行一个），选择建议站点，点击开始采集后导出 Excel。如有 HTML 报告或 JSON 工作台导出也一并保存。",
    }


# ── Route extraction ───────────────────────────────────────────────────

def _extract_selected_routes(route_matrix: dict[str, Any]) -> list[str]:
    routes: list[str] = []
    for item in as_list(route_matrix.get("selected_routes")):
        if isinstance(item, dict):
            name = first_text(item.get("route_name") or item.get("name") or item.get("id"))
            if name:
                routes.append(name)
        elif isinstance(item, str):
            routes.append(item)
    return routes if routes else ["<primary_route>"]


def _extract_rejected_routes(route_matrix: dict[str, Any]) -> list[str]:
    routes: list[str] = []
    for item in as_list(route_matrix.get("rejected_routes")):
        if isinstance(item, dict):
            name = first_text(item.get("route_name") or item.get("name") or item.get("id"))
            if name:
                routes.append(name)
        elif isinstance(item, str):
            routes.append(item)
    return routes


# ── Progress ───────────────────────────────────────────────────────────

def _update_progress(
    progress: dict[str, Any],
    workflow_state: dict[str, Any],
    batch: dict[str, Any],
    batch_path: Path,
) -> dict[str, Any]:
    run_dir = batch_path.parent.parent
    rel_batch = str(batch_path.relative_to(run_dir)) if run_dir else str(batch_path)
    stages = dict(progress.get("stages", {}))
    stage_7 = dict(stages.get("stage_7_voc_gate", {}))
    stage_7["status"] = "running"
    stage_7["updated_at"] = batch.get("generated_at", "")
    stages["stage_7_voc_gate"] = stage_7

    completed = list(progress.get("completed_artifacts", []))
    if rel_batch not in completed:
        completed.append(rel_batch)

    return {
        **progress,
        "current_stage": "stage_7_voc_gate",
        "stages": stages,
        "completed_artifacts": completed,
        "updated_at": batch.get("generated_at", ""),
        "next_action": {
            "type": "wait_operator_export",
            "description": "等待运营按 ASIN 清单完成评论导出",
            "stage_id": "stage_7_voc_gate",
            "next_substage": "P5-2",
            "batch_asin_count": batch.get("asin_items", []).__len__(),
        },
    }


def _update_progress_blocked(
    progress: dict[str, Any],
    workflow_state: dict[str, Any],
    run_path: Path,
) -> dict[str, Any]:
    """Update progress when zero ASINs are available — stage is blocked, not running."""
    now = datetime.now(timezone.utc).isoformat()
    stages = dict(progress.get("stages", {}))
    stage_7 = dict(stages.get("stage_7_voc_gate", {}))
    stage_7["status"] = "blocked"
    stage_7["blocked_reason"] = "zero_asins_extracted"
    stage_7["blocked_detail"] = "P4 evidence packets and candidate pool contain no extractable ASINs — cannot form review ASIN batch."
    stage_7["updated_at"] = now
    stages["stage_7_voc_gate"] = stage_7

    return {
        **progress,
        "current_stage": "stage_7_voc_gate",
        "stages": stages,
        "completed_artifacts": progress.get("completed_artifacts", []),
        "updated_at": now,
        "next_action": {
            "type": "needs_user",
            "description": "无可用 ASIN — 请运营在评论插件中手动输入目标 ASIN 清单，或确认 P4 候选池和证据包中有可提取的竞品 ASIN。补抓后重新运行 P5-1。",
            "stage_id": "stage_7_voc_gate",
            "next_substage": "P5-1",
            "user_action_required": True,
            "user_guidance": "检查 candidate_pool.json 和 P4 evidence packets 中是否包含至少 1 个有效 ASIN。如无，请手动提供参考竞品 ASIN 清单。",
        },
        "warnings": progress.get("warnings", []) + [
            "P5-1 blocked: zero ASINs extracted from P4 artifacts — review_asin_batch.json was NOT written.",
        ],
    }


# ── Helpers ────────────────────────────────────────────────────────────



def _site(workflow_state: dict[str, Any]) -> str:
    known = workflow_state.get("known_inputs") if isinstance(workflow_state, dict) else {}
    site = first_text(workflow_state.get("site") or (known.get("site") if isinstance(known, dict) else ""))
    return site or "US"


def _write_export_readme(reviews_dir: Path, batch: dict[str, Any]) -> None:
    """在 inputs/reviews/ 下写入导出说明，告诉运营怎么导出评论。"""
    asin_items = as_list(batch.get("asin_items", []))
    site = batch.get("site", "US")
    asin_lines = []
    for item in asin_items:
        asin = item.get("asin", "")
        role = item.get("asin_role", "")
        route = item.get("route_ref", "")
        label = f"{asin}  # {role} [{route}]" if role else asin
        asin_lines.append(label)

    asin_block = "\n".join(asin_lines[:30]) if asin_lines else "（无 ASIN，请检查 review_asin_batch.json）"
    if len(asin_lines) > 30:
        asin_block += f"\n... 共 {len(asin_lines)} 个 ASIN，完整列表见 review_voc/review_asin_batch.json"

    readme = f"""# 评论导出说明

## 当前站点
{site}

## 导出要求
- 每个 ASIN 至少导出 30 条评论（含低分评论 <=3星 至少 10 条）
- 支持的格式：CSV / XLSX
- 命名建议：{{ASIN}}_reviews.csv（如 B0EXAMPLE1_reviews.csv）

## ASIN 清单
{asin_block}

## 导出步骤
1. 打开评论采集插件（评论慢速采集助手 / Review Export Tool）
2. 将上方 ASIN 逐行粘贴到 ASIN 输入框
3. 选择站点：{site}
4. 开始采集 → 导出为 CSV 或 XLSX
5. 将导出文件放入此目录：inputs/reviews/

## 导出完成后
告知 AI 继续，AI 会自动运行：
  python3 scripts/build_review_voc_package.py <run_dir> <导出文件路径>
  python3 scripts/build_voc_gate.py <run_dir>
"""
    readme_path = reviews_dir / "README.txt"
    readme_path.write_text(readme, encoding="utf-8")


# ── CLI ────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build P5 VOC review ASIN batch plan from P4 artifacts.")
    parser.add_argument("run_dir", help="Path to the run directory containing P4 artifacts.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        outputs = run_review_asin_batch(args.run_dir)
        print(f"batch: {outputs['asin_batch']}")
        print(f"progress: {outputs['progress']}")
    except P5AsinBatchError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
