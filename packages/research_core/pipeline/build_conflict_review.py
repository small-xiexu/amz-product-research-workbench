#!/usr/bin/env python3
"""Build P4 conflict review artifacts — data normalization and conflict resolution."""

from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

from packages.research_core.contracts import (
    ContractValidationError,
    P4ContractError,
    P4_SCHEMA_VERSION,
    P4_STAGE_ID,
    validate_conflict_resolution_packet,
    validate_deep_data_completeness_check,
    validate_metric_basis_comparable,
    validate_p4_evidence_packet,
    validate_p4_preconditions,
)
from packages.research_core.contracts.p0_contracts import P0_SCHEMA_VERSION
from packages.research_core.pipeline._utils import as_list, first_text, load_json, numeric_value, _dedupe_dicts, _now_iso, _run_id, _write_json
from packages.research_core.pipeline.quick_market_check import validate_progress


CONFLICT_REVIEW_DIR = "conflict_review"
COMPLETENESS_CHECK_NAME = "deep_data_completeness_check.json"
CONFLICT_PACKET_NAME = "conflict_resolution_packet.json"

P4_CONFLICT_INPUT_ARTIFACTS = [
    "candidate_pool.json",
    "route_matrix_confirm.json",
    "data_completeness_check.json",
    "progress.json",
    "mcp_snapshots/sellersprite_deep_snapshot.json",
    "mcp_snapshots/sorftime_deep_snapshot.json",
    "market_structure/market_structure_evidence_packet.json",
    "search_demand/search_demand_evidence_packet.json",
]
P4_CONFLICT_OUTPUT_ARTIFACTS = [
    f"{CONFLICT_REVIEW_DIR}/{COMPLETENESS_CHECK_NAME}",
    f"{CONFLICT_REVIEW_DIR}/{CONFLICT_PACKET_NAME}",
]

MARKET_STRUCTURE_PACKET = "market_structure/market_structure_evidence_packet.json"
SEARCH_DEMAND_PACKET = "search_demand/search_demand_evidence_packet.json"
SELLERSPRITE_SNAPSHOT = "mcp_snapshots/sellersprite_deep_snapshot.json"
SORFTIME_SNAPSHOT = "mcp_snapshots/sorftime_deep_snapshot.json"

COMPARABLE_PAIRS: tuple[dict[str, Any], ...] = (
    {
        "pair_id": "market_capacity",
        "primary_source": "sellersprite",
        "primary_item_type": "market_capacity",
        "secondary_source": "sorftime",
        "secondary_item_type": "category_search",
        "comparison_basis_overrides": {
            "metric_unit": "units",
            "sample_scope": "category_monthly_sales",
            "aggregation_unit": "category",
            "collection_method": "deep_snapshot_cross_check",
            "currency": "USD",
            "parent_child_basis": "unknown",
        },
        "field_mappings": (
            {"primary_field": "totalUnits", "secondary_fields": ("Top100产品月销量",), "threshold": 0.20, "label": "monthly_sales_units"},
            {"primary_field": "avgPrice", "secondary_fields": ("平均价格",), "threshold": 0.10, "label": "average_price"},
        ),
    },
    {
        "pair_id": "price_band",
        "primary_source": "sellersprite",
        "primary_item_type": "price_band",
        "secondary_source": "sorftime",
        "secondary_item_type": "category_top100",
        "comparison_basis_overrides": {
            "metric_unit": "currency",
            "sample_scope": "category_price_level",
            "aggregation_unit": "category",
            "collection_method": "deep_snapshot_cross_check",
            "currency": "USD",
            "parent_child_basis": "unknown",
        },
        "field_mappings": (
            {"primary_field": "avgPrice", "secondary_fields": ("average_price", "median_price", "平均价格"), "threshold": 0.10, "label": "price_level"},
        ),
    },
    {
        "pair_id": "seller_concentration",
        "primary_source": "sellersprite",
        "primary_item_type": "seller_concentration",
        "secondary_source": "sorftime",
        "secondary_item_type": "category_top100",
        "comparison_basis_overrides": {
            "metric_unit": "percent",
            "sample_scope": "category_top3_seller_share",
            "aggregation_unit": "category",
            "collection_method": "deep_snapshot_cross_check",
            "currency": "USD",
            "parent_child_basis": "unknown",
        },
        "field_mappings": (
            {"primary_field": "totalUnitsRatio", "secondary_fields": ("销量前3的卖家月销量占比", "top3_seller_sales_volume_share"), "threshold": 0.20, "label": "top3_seller_share"},
        ),
    },
    {
        "pair_id": "review_threshold",
        "primary_source": "sellersprite",
        "primary_item_type": "review_threshold",
        "secondary_source": "sorftime",
        "secondary_item_type": "category_top100",
        "comparison_basis_overrides": {
            "metric_unit": "rating_count",
            "sample_scope": "category_review_threshold",
            "aggregation_unit": "category",
            "collection_method": "deep_snapshot_cross_check",
            "currency": "USD",
            "parent_child_basis": "unknown",
        },
        "field_mappings": (
            {"primary_field": "avgRatings", "secondary_fields": ("平均评价数量",), "threshold": 0.15, "label": "avg_ratings_count"},
            {"primary_field": "avgRating", "secondary_fields": ("平均星级",), "threshold": 0.30, "label": "avg_rating", "is_rating": True},
        ),
    },
    {
        "pair_id": "category_boundary",
        "primary_source": "sellersprite",
        "primary_item_type": "category_boundary",
        "secondary_source": "sorftime",
        "secondary_item_type": "category_search",
        "comparison_basis_overrides": {
            "metric_unit": "category_node",
            "sample_scope": "node_mapping_cross_check",
            "aggregation_unit": "category",
            "collection_method": "deep_snapshot_cross_check",
            "currency": "USD",
            "parent_child_basis": "unknown",
        },
        "field_mappings": (
            {"primary_field": "nodeIdPath", "secondary_fields": ("nodeid", "nodeId"), "threshold": None, "label": "category_node", "is_identity": True},
        ),
    },
    {
        "pair_id": "competitor_sample",
        "primary_source": "sellersprite",
        "primary_item_type": "competitor_structure",
        "secondary_source": "sorftime",
        "secondary_item_type": "keyword_search_results",
        "comparison_basis_overrides": {
            "metric_unit": "asin_identity",
            "sample_scope": "competitor_sample_cross_check",
            "aggregation_unit": "asin",
            "collection_method": "deep_snapshot_cross_check",
            "currency": "USD",
            "parent_child_basis": "unknown",
        },
        "field_mappings": (
            {"primary_field": "asin", "secondary_fields": ("ASIN",), "threshold": None, "label": "representative_asin", "is_identity": True},
            {"primary_field": "brand", "secondary_fields": ("品牌",), "threshold": None, "label": "brand_overlap", "is_identity": True},
        ),
    },
    {
        "pair_id": "asin_operating_data",
        "primary_source": "sellersprite",
        "primary_item_type": "asin_operating_data",
        "secondary_source": "sorftime",
        "secondary_item_type": "product_detail",
        "comparison_basis_overrides": {
            "metric_unit": "mixed",
            "sample_scope": "representative_asin_cross_check",
            "aggregation_unit": "asin",
            "collection_method": "deep_snapshot_cross_check",
            "currency": "USD",
            "parent_child_basis": "unknown",
        },
        "field_mappings": (
            {"primary_field": "price", "secondary_fields": ("price", "价格"), "threshold": 0.10, "label": "asin_price"},
            {"primary_field": "rating", "secondary_fields": ("rating", "星级"), "threshold": 0.30, "label": "asin_rating", "is_rating": True},
            {"primary_field": "ratings", "secondary_fields": ("ratings", "评价数"), "threshold": 0.15, "label": "asin_ratings_count"},
        ),
    },
)


class P4ConflictReviewError(ContractValidationError):
    """Raised when P4-4 conflict review artifacts cannot be built."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build P4 conflict review artifacts.")
    parser.add_argument("run_dir", type=Path, help="Path to runs/<run_id> directory")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        run_conflict_review(args.run_dir)
    except Exception as exc:  # pragma: no cover - CLI guard
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


def run_conflict_review(run_dir: Path | str) -> dict[str, Path]:
    run_path = Path(run_dir).expanduser().resolve()
    if not run_path.exists():
        raise P4ConflictReviewError(f"run_dir not found: {run_path}")

    progress_path = run_path / "progress.json"
    try:
        validate_p4_preconditions(run_path)
        _validate_p4_deep_artifacts_present(run_path)

        workflow_state = load_json(run_path / "workflow_state.json")
        route_matrix = load_json(run_path / "route_matrix_confirm.json")
        candidate_pool = load_json(run_path / "candidate_pool.json")
        data_completeness = load_json(run_path / "data_completeness_check.json")
        progress = load_json(progress_path)

        ss_snapshot = load_json(run_path / SELLERSPRITE_SNAPSHOT, required=False)
        sf_snapshot = load_json(run_path / SORFTIME_SNAPSHOT, required=False)
        snapshot_unavailable = not ss_snapshot or not sf_snapshot
        market_packet = load_json(run_path / MARKET_STRUCTURE_PACKET)
        search_packet = load_json(run_path / SEARCH_DEMAND_PACKET)

        completeness_check = build_deep_data_completeness_check(
            workflow_state,
            route_matrix,
            candidate_pool,
            data_completeness,
            ss_snapshot or {},
            sf_snapshot or {},
            market_packet,
            search_packet,
            run_path,
        )
        if snapshot_unavailable:
            completeness_check.setdefault("data_gaps", [])
            completeness_check["data_gaps"].append("snapshot_unavailable")
            completeness_check["snapshot_unavailable"] = True

        validate_deep_data_completeness_check(completeness_check)

        conflict_packet = build_conflict_resolution_packet(
            workflow_state,
            route_matrix,
            market_packet,
            search_packet,
            ss_snapshot or {},
            sf_snapshot or {},
            completeness_check,
            run_path,
        )
        validate_conflict_resolution_packet(conflict_packet)

        conflict_dir = run_path / CONFLICT_REVIEW_DIR
        _write_json(conflict_dir / COMPLETENESS_CHECK_NAME, completeness_check)
        _write_json(conflict_dir / CONFLICT_PACKET_NAME, conflict_packet)

        if completeness_check.get("completeness_level") == "blocker":
            _write_blocked_progress(run_path, progress_path, workflow_state, progress,
                                    "deep_data_completeness_check is blocker; cannot mark stage_6 done.")
            raise P4ConflictReviewError("deep_data_completeness_check.level is blocker")

        if conflict_packet.get("conflict_level") == "blocker":
            _write_blocked_progress(run_path, progress_path, workflow_state, progress,
                                    "conflict_resolution_packet.level is blocker; cannot mark stage_6 done.")
            raise P4ConflictReviewError("conflict_resolution_packet.level is blocker")

        progress = build_conflict_success_progress(progress, workflow_state, completeness_check, conflict_packet)
        validate_progress(progress)
        _write_json(progress_path, progress)

        return {
            "deep_data_completeness_check": conflict_dir / COMPLETENESS_CHECK_NAME,
            "conflict_resolution_packet": conflict_dir / CONFLICT_PACKET_NAME,
            "progress": progress_path,
        }
    except Exception as exc:
        _write_failure_progress(run_path, progress_path, str(exc))
        raise P4ConflictReviewError(str(exc)) from exc


def build_deep_data_completeness_check(
    workflow_state: dict[str, Any],
    route_matrix: dict[str, Any],
    candidate_pool: dict[str, Any],
    p3_completeness: dict[str, Any],
    ss_snapshot: dict[str, Any],
    sf_snapshot: dict[str, Any],
    market_packet: dict[str, Any],
    search_packet: dict[str, Any],
    run_path: Path,
) -> dict[str, Any]:
    now = _now_iso()
    route_refs, selected_routes = _route_lineage(route_matrix)

    route_checks = _build_route_checks(route_matrix, market_packet, search_packet)
    source_coverage = _build_source_coverage(ss_snapshot, sf_snapshot, market_packet, search_packet)
    metric_coverage = _build_metric_coverage(market_packet, search_packet)
    node_mapping_status = _build_node_mapping_status(market_packet, search_packet, route_matrix, candidate_pool)
    data_gaps, blocking_gaps = _collect_completeness_gaps(
        ss_snapshot, sf_snapshot, market_packet, search_packet, route_checks, source_coverage, metric_coverage
    )

    completeness_level = _determine_completeness_level(route_checks, source_coverage, metric_coverage, blocking_gaps)

    return {
        "schema_version": P4_SCHEMA_VERSION,
        "packet_id": "deep_data_completeness_check",
        "run_id": _run_id(workflow_state, run_path),
        "source_packets": [
            f"{MARKET_STRUCTURE_PACKET}#packet",
            f"{SEARCH_DEMAND_PACKET}#packet",
        ],
        "source_snapshots": [
            f"{SELLERSPRITE_SNAPSHOT}#snapshot",
            f"{SORFTIME_SNAPSHOT}#snapshot",
        ],
        "route_checks": route_checks,
        "source_coverage": source_coverage,
        "metric_coverage": metric_coverage,
        "node_mapping_status": node_mapping_status,
        "completeness_level": completeness_level,
        "data_gaps": data_gaps,
        "blocking_gaps": blocking_gaps,
        "required_next_actions": _completeness_next_actions(completeness_level, blocking_gaps),
        "evidence_refs": [
            f"{MARKET_STRUCTURE_PACKET}#evidence_items",
            f"{SEARCH_DEMAND_PACKET}#evidence_items",
            f"{SELLERSPRITE_SNAPSHOT}#tool_results",
            f"{SORFTIME_SNAPSHOT}#tool_results",
        ],
        "created_at": now,
    }


def build_conflict_resolution_packet(
    workflow_state: dict[str, Any],
    route_matrix: dict[str, Any],
    market_packet: dict[str, Any],
    search_packet: dict[str, Any],
    ss_snapshot: dict[str, Any],
    sf_snapshot: dict[str, Any],
    completeness_check: dict[str, Any],
    run_path: Path,
) -> dict[str, Any]:
    now = _now_iso()
    route_refs, selected_routes = _route_lineage(route_matrix)

    market_items = _evidence_items_by_type(market_packet)
    search_items = _evidence_items_by_type(search_packet)
    market_basis = market_packet.get("metric_basis") if isinstance(market_packet.get("metric_basis"), dict) else {}
    search_basis = search_packet.get("metric_basis") if isinstance(search_packet.get("metric_basis"), dict) else {}

    metric_basis_checks: list[dict[str, Any]] = []
    comparable_conflicts: list[dict[str, Any]] = []
    non_comparable_items: list[dict[str, Any]] = []
    basis_mismatches: list[dict[str, Any]] = []
    all_data_gaps: list[dict[str, Any]] = []
    blocking_gaps: list[dict[str, Any]] = []

    check_index = 0
    for pair in COMPARABLE_PAIRS:
        primary_item = market_items.get(pair["primary_item_type"])
        secondary_item = search_items.get(pair["secondary_item_type"])

        if primary_item is None and secondary_item is None:
            non_comparable_items.append({
                "metric_name": pair["pair_id"],
                "reason": f"both evidence items missing: {pair['primary_item_type']}/{pair['secondary_item_type']}",
                "primary_item_type": pair["primary_item_type"],
                "secondary_item_type": pair["secondary_item_type"],
            })
            continue
        if primary_item is None:
            non_comparable_items.append({
                "metric_name": pair["pair_id"],
                "reason": f"primary evidence item missing: {pair['primary_item_type']}",
                "primary_item_type": pair["primary_item_type"],
                "secondary_item_type": pair["secondary_item_type"],
            })
            continue
        if secondary_item is None:
            non_comparable_items.append({
                "metric_name": pair["pair_id"],
                "reason": f"secondary evidence item missing: {pair['secondary_item_type']}",
                "primary_item_type": pair["primary_item_type"],
                "secondary_item_type": pair["secondary_item_type"],
            })
            continue

        primary_basis_ref = primary_item.get("metric_basis_ref", "")
        secondary_basis_ref = secondary_item.get("metric_basis_ref", "")
        primary_basis_obj = market_basis.get(primary_basis_ref) if primary_basis_ref else None
        secondary_basis_obj = search_basis.get(secondary_basis_ref) if secondary_basis_ref else None

        if primary_basis_obj is None or secondary_basis_obj is None:
            basis_mismatches.append({
                "metric_name": pair["pair_id"],
                "field": "metric_basis",
                "mismatches": [{
                    "field": "metric_basis_ref",
                    "primary": primary_basis_ref or "missing",
                    "secondary": secondary_basis_ref or "missing",
                }],
            })
            continue

        overrides = pair.get("comparison_basis_overrides") if isinstance(pair.get("comparison_basis_overrides"), dict) else {}
        primary_basis_norm = _normalize_basis_for_comparison(primary_basis_obj, overrides)
        secondary_basis_norm = _normalize_basis_for_comparison(secondary_basis_obj, overrides)

        comparability = validate_metric_basis_comparable(primary_basis_norm, secondary_basis_norm)
        check_entry: dict[str, Any] = {
            "check_id": f"basis-check-{check_index}",
            "metric_name": pair["pair_id"],
            "comparable": comparability["comparable"],
            "primary_basis": primary_basis_norm,
            "secondary_basis": secondary_basis_norm,
            "primary_basis_raw": primary_basis_obj,
            "secondary_basis_raw": secondary_basis_obj,
            "comparison_overrides": overrides,
            "comparability": comparability,
        }
        metric_basis_checks.append(check_entry)
        check_index += 1

        if not comparability["comparable"]:
            basis_mismatches.append({
                "metric_name": pair["pair_id"],
                "field": "metric_basis",
                "mismatches": comparability["mismatches"],
                "missing_fields": comparability["missing_fields"],
                "primary_item_type": pair["primary_item_type"],
                "secondary_item_type": pair["secondary_item_type"],
            })
            continue

        primary_norm = _normalized_from_item(primary_item)
        secondary_norm = _normalized_from_item(secondary_item)

        for mapping in pair["field_mappings"]:
            primary_val = _find_normalized_value(primary_norm, mapping["primary_field"])
            secondary_val = _find_normalized_value(secondary_norm, mapping["secondary_fields"])

            if primary_val is None and secondary_val is None:
                all_data_gaps.append({
                    "type": "missing_comparable_field",
                    "pair_id": pair["pair_id"],
                    "field": mapping["label"],
                    "primary_field": mapping["primary_field"],
                    "secondary_fields": list(mapping["secondary_fields"]),
                    "severity": "warning",
                })
                continue

            if primary_val is None:
                all_data_gaps.append({
                    "type": "missing_primary_field",
                    "pair_id": pair["pair_id"],
                    "field": mapping["label"],
                    "primary_field": mapping["primary_field"],
                    "severity": "warning",
                })
                continue

            if secondary_val is None:
                all_data_gaps.append({
                    "type": "missing_secondary_field",
                    "pair_id": pair["pair_id"],
                    "field": mapping["label"],
                    "secondary_fields": list(mapping["secondary_fields"]),
                    "severity": "warning",
                })
                continue

            p_num = numeric_value(primary_val)
            s_num = numeric_value(secondary_val)
            if p_num is None or s_num is None:
                non_comparable_items.append({
                    "metric_name": f"{pair['pair_id']}.{mapping['label']}",
                    "reason": "cannot parse numeric values",
                    "primary_value": primary_val,
                    "secondary_value": secondary_val,
                })
                continue

            if mapping.get("is_identity"):
                if str(primary_val).strip().casefold() == str(secondary_val).strip().casefold():
                    continue
                non_comparable_items.append({
                    "metric_name": f"{pair['pair_id']}.{mapping['label']}",
                    "reason": "identity mismatch — different nodes or ASINs",
                    "primary_value": str(primary_val),
                    "secondary_value": str(secondary_val),
                })
                continue

            threshold = mapping.get("threshold")
            if threshold is None:
                continue

            if mapping.get("is_rating"):
                numeric_delta = abs(p_num - s_num)
                relative_delta = numeric_delta
                severity = "blocking" if numeric_delta > threshold else ("material" if numeric_delta > threshold * 0.5 else "minor")
            elif s_num == 0:
                numeric_delta = abs(p_num)
                relative_delta = 1.0 if p_num != 0 else 0.0
                severity = "material"
            else:
                numeric_delta = abs(p_num - s_num)
                relative_delta = numeric_delta / abs(s_num)
                if relative_delta > threshold:
                    severity = "blocking" if relative_delta > threshold * 2 else "material"
                else:
                    severity = "minor"

            conflict_entry: dict[str, Any] = {
                "conflict_id": f"conflict-{pair['pair_id']}-{mapping['label']}",
                "metric_name": f"{pair['pair_id']}.{mapping['label']}",
                "field": mapping["label"],
                "severity": severity,
                "status": "needs_review" if severity in ("material", "blocking") else "accepted",
                "primary_value": p_num,
                "secondary_value": s_num,
                "numeric_delta": numeric_delta,
                "relative_delta": relative_delta,
                "metric_basis_check_id": check_entry["check_id"],
                "primary_basis": primary_basis_norm,
                "secondary_basis": secondary_basis_norm,
                "evidence_refs": [
                    f"{MARKET_STRUCTURE_PACKET}#evidence_items[{pair['primary_item_type']}]",
                    f"{SEARCH_DEMAND_PACKET}#evidence_items[{pair['secondary_item_type']}]",
                    f"conflict_review/conflict_resolution_packet.json#metric_basis_checks[{check_index - 1}]",
                ],
            }
            comparable_conflicts.append(conflict_entry)

    source_errors = list(as_list(ss_snapshot.get("errors"))) + list(as_list(sf_snapshot.get("errors")))
    for err in source_errors:
        if isinstance(err, dict):
            all_data_gaps.append({
                "type": "snapshot_error",
                "source_name": err.get("source_name", ""),
                "tool_name": first_text(err.get("tool_name"), "unknown"),
                "message": first_text(err.get("message"), ""),
                "severity": "warning",
            })

    packet_gaps = list(as_list(market_packet.get("data_gaps"))) + list(as_list(search_packet.get("data_gaps")))
    all_data_gaps.extend(packet_gaps)

    conflict_level = _determine_conflict_level(comparable_conflicts, basis_mismatches, all_data_gaps)
    if conflict_level == "blocker":
        blocking_gaps = [
            gap for gap in all_data_gaps
            if isinstance(gap, dict) and gap.get("severity") in ("blocker", "blocking")
        ]
        blocking_conflicts = [c for c in comparable_conflicts if c.get("severity") == "blocking"]
        if blocking_conflicts:
            blocking_gaps.extend([
                {"type": "blocking_conflict", "conflict_id": c["conflict_id"], "metric_name": c.get("metric_name", "")}
                for c in blocking_conflicts
            ])

    return {
        "schema_version": P4_SCHEMA_VERSION,
        "packet_id": "conflict_resolution_packet",
        "run_id": _run_id(workflow_state, run_path),
        "source_packets": [
            f"{MARKET_STRUCTURE_PACKET}#packet",
            f"{SEARCH_DEMAND_PACKET}#packet",
        ],
        "source_snapshots": [
            f"{SELLERSPRITE_SNAPSHOT}#snapshot",
            f"{SORFTIME_SNAPSHOT}#snapshot",
        ],
        "metric_basis_checks": metric_basis_checks,
        "comparable_conflicts": comparable_conflicts,
        "non_comparable_items": non_comparable_items,
        "basis_mismatches": basis_mismatches,
        "conflict_level": conflict_level,
        "blocking_gaps": _dedupe_dicts(blocking_gaps),
        "required_next_actions": _conflict_next_actions(conflict_level, comparable_conflicts, basis_mismatches),
        "evidence_refs": [
            f"{CONFLICT_REVIEW_DIR}/{CONFLICT_PACKET_NAME}#metric_basis_checks",
            f"{CONFLICT_REVIEW_DIR}/{COMPLETENESS_CHECK_NAME}#route_checks",
            f"{MARKET_STRUCTURE_PACKET}#evidence_items",
            f"{SEARCH_DEMAND_PACKET}#evidence_items",
        ],
        "created_at": now,
    }


def build_conflict_success_progress(
    progress: dict[str, Any],
    workflow_state: dict[str, Any],
    completeness_check: dict[str, Any],
    conflict_packet: dict[str, Any],
) -> dict[str, Any]:
    now = _now_iso()
    progress = _progress_template(progress, workflow_state)
    completed = list(progress.get("completed_artifacts") or [])
    for artifact in P4_CONFLICT_OUTPUT_ARTIFACTS:
        if artifact not in completed:
            completed.append(artifact)

    stages = deepcopy(progress.get("stages") or {})
    previous_stage = stages.get(P4_STAGE_ID) if isinstance(stages.get(P4_STAGE_ID), dict) else {}

    all_outputs = list(dict.fromkeys(
        previous_stage.get("output_artifacts", []) + P4_CONFLICT_OUTPUT_ARTIFACTS
    ))

    stages[P4_STAGE_ID] = {
        "status": "done",
        "attempts": int(previous_stage.get("attempts", 0) or 0) + 1,
        "input_artifacts": P4_CONFLICT_INPUT_ARTIFACTS,
        "output_artifacts": all_outputs,
        "validation_checks": [
            {"name": "p4_preconditions", "pass": True, "detail": "P3 route matrix is confirmed."},
            {"name": "deep_data_completeness_check", "pass": True,
             "detail": f"completeness_level={completeness_check.get('completeness_level')}"},
            {"name": "conflict_resolution_packet", "pass": True,
             "detail": f"conflict_level={conflict_packet.get('conflict_level')}"},
            {"name": "metric_basis_normalization", "pass": True,
             "detail": f"{len(conflict_packet.get('comparable_conflicts', []))} comparable conflicts, "
                       f"{len(conflict_packet.get('basis_mismatches', []))} basis mismatches"},
            {"name": "p4_scope_no_downstream_artifacts", "pass": True,
             "detail": "P4-4 only builds conflict review; no VOC/evaluations/report/HTML/XLSX."},
        ],
        "last_error": "",
        "next_required_user_action": "",
        "resume_policy": {
            "reuse_existing_artifacts": True,
            "allow_repeat_mcp_call": False,
            "force_refresh": False,
        },
    }

    progress.update({
        "schema_version": P0_SCHEMA_VERSION,
        "current_stage": P4_STAGE_ID,
        "updated_at": now,
        "global_blockers": [],
        "next_action": {
            "type": "next_stage",
            "stage_id": "stage_7_voc_gate",
            "description": "P4 deep dive complete; proceed to P5/P7 VOC gate.",
        },
        "completed_artifacts": completed,
        "stages": stages,
        "workflow_ref": progress.get("workflow_ref") or workflow_state.get("workflow_id") or workflow_state.get("run_id") or "",
    })
    return progress


# ---- internal helpers ----

def _validate_p4_deep_artifacts_present(run_path: Path) -> None:
    for rel in (
        SELLERSPRITE_SNAPSHOT,
        SORFTIME_SNAPSHOT,
        MARKET_STRUCTURE_PACKET,
        SEARCH_DEMAND_PACKET,
    ):
        path = run_path / rel
        if not path.exists():
            raise P4ConflictReviewError(f"required P4 deep artifact missing: {rel}")
        data = load_json(path)
        if rel.endswith("_snapshot.json"):
            from packages.research_core.contracts import validate_deep_snapshot
            source_name = "sellersprite" if "sellersprite" in rel else "sorftime"
            validate_deep_snapshot(data, expected_source_name=source_name)
        elif "evidence_packet" in rel:
            from packages.research_core.contracts import validate_p4_evidence_packet
            primary_source = "sellersprite" if "market_structure" in rel else "sorftime"
            validate_p4_evidence_packet(data, expected_primary_source=primary_source)


def _build_route_checks(
    route_matrix: dict[str, Any],
    market_packet: dict[str, Any],
    search_packet: dict[str, Any],
) -> list[dict[str, Any]]:
    route_refs, selected_routes = _route_lineage(route_matrix)
    market_routes = set(market_packet.get("selected_routes") or [])
    search_routes = set(search_packet.get("selected_routes") or [])

    checks: list[dict[str, Any]] = []
    for index, route in enumerate(selected_routes):
        in_market = route in market_routes
        in_search = route in search_routes

        if in_market and in_search:
            status, gap_level = "covered", "acceptable"
        elif in_market or in_search:
            status, gap_level = "partial", "warning"
        else:
            status, gap_level = "missing", "blocker"

        checks.append({
            "route_ref": route_refs[index] if index < len(route_refs) else f"selected_routes[{index}]",
            "route_id": route,
            "status": status,
            "gap_level": gap_level,
            "market_structure_covered": in_market,
            "search_demand_covered": in_search,
            "data_gaps": [] if status == "covered" else [
                f"{'market_structure' if not in_market else ''}{' and ' if not in_market and not in_search else ''}{'search_demand' if not in_search else ''} not covering route"
            ],
            "evidence_refs": [
                f"{MARKET_STRUCTURE_PACKET}#selected_routes",
                f"{SEARCH_DEMAND_PACKET}#selected_routes",
            ],
        })
    return checks


def _build_source_coverage(
    ss_snapshot: dict[str, Any],
    sf_snapshot: dict[str, Any],
    market_packet: dict[str, Any],
    search_packet: dict[str, Any],
) -> dict[str, Any]:
    def _snapshot_coverage(snapshot: dict[str, Any], label: str) -> dict[str, Any]:
        tool_calls = as_list(snapshot.get("tool_calls"))
        success = sum(1 for c in tool_calls if isinstance(c, dict) and c.get("status") == "success")
        errors = sum(1 for c in tool_calls if isinstance(c, dict) and c.get("status") == "error")
        total = len(tool_calls)
        return {
            "source_name": label,
            "total_tool_calls": total,
            "success_count": success,
            "error_count": errors,
            "has_errors": bool(snapshot.get("errors")),
            "has_data_gaps": bool(snapshot.get("data_gaps")),
        }

    return {
        "sellersprite": {
            **_snapshot_coverage(ss_snapshot, "sellersprite"),
            "evidence_packet_confidence": market_packet.get("confidence", "unknown"),
        },
        "sorftime": {
            **_snapshot_coverage(sf_snapshot, "sorftime"),
            "evidence_packet_confidence": search_packet.get("confidence", "unknown"),
        },
    }


def _build_metric_coverage(
    market_packet: dict[str, Any],
    search_packet: dict[str, Any],
) -> dict[str, Any]:
    coverage: dict[str, Any] = {}
    for label, packet in (("market_structure", market_packet), ("search_demand", search_packet)):
        items = as_list(packet.get("evidence_items"))
        item_types = [item.get("item_type", "unknown") for item in items if isinstance(item, dict)]
        metrics = packet.get("derived_metrics") if isinstance(packet.get("derived_metrics"), dict) else {}
        coverage[label] = {
            "evidence_item_count": len(items),
            "item_types": item_types,
            "derived_metric_count": len(metrics),
        }
    coverage["comparable_pairs_defined"] = len(COMPARABLE_PAIRS)
    return coverage


def _build_node_mapping_status(
    market_packet: dict[str, Any],
    search_packet: dict[str, Any],
    route_matrix: dict[str, Any],
    candidate_pool: dict[str, Any],
) -> dict[str, Any]:
    def _extract_nodes(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        nodes: list[dict[str, Any]] = []
        for item in items:
            node_input = (item.get("facts") or {}).get("node_mapping_input")
            if isinstance(node_input, dict):
                nodes.append(node_input)
        return nodes

    market_nodes = _extract_nodes(as_list(market_packet.get("evidence_items")))
    search_nodes = _extract_nodes(as_list(search_packet.get("evidence_items")))

    market_node_ids = {n.get("nodeId", "") for n in market_nodes if n.get("nodeId")}
    search_node_ids = {n.get("nodeId", "") for n in search_nodes if n.get("nodeId")}
    market_paths = {n.get("nodeIdPath", "") for n in market_nodes if n.get("nodeIdPath")}
    search_paths = {n.get("nodeIdPath", "") for n in search_nodes if n.get("nodeIdPath")}

    shared_nodes = market_node_ids & search_node_ids
    shared_paths = market_paths & search_paths

    status = "mapped"
    if not shared_nodes and not shared_paths:
        status = "unmapped"
    elif not shared_nodes:
        status = "partial_path_only"

    return {
        "status": status,
        "market_structure_node_ids": sorted(market_node_ids),
        "search_demand_node_ids": sorted(search_node_ids),
        "shared_node_ids": sorted(shared_nodes),
        "shared_node_paths": sorted(shared_paths),
        "market_structure_node_mapping_statuses": [
            n.get("node_mapping_status", "unknown") for n in market_nodes
        ],
        "search_demand_node_mapping_statuses": [
            n.get("node_mapping_status", "unknown") for n in search_nodes
        ],
    }


def _collect_completeness_gaps(
    ss_snapshot: dict[str, Any],
    sf_snapshot: dict[str, Any],
    market_packet: dict[str, Any],
    search_packet: dict[str, Any],
    route_checks: list[dict[str, Any]],
    source_coverage: dict[str, Any],
    metric_coverage: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    data_gaps: list[dict[str, Any]] = []
    blocking_gaps: list[dict[str, Any]] = []

    for check in route_checks:
        if check.get("gap_level") == "blocker":
            blocking_gaps.append({
                "type": "route_not_covered",
                "route_id": check.get("route_id", ""),
                "detail": check.get("data_gaps", []),
            })
        elif check.get("gap_level") == "warning":
            data_gaps.append({
                "type": "route_partial_coverage",
                "route_id": check.get("route_id", ""),
                "detail": check.get("data_gaps", []),
            })

    for source_key in ("sellersprite", "sorftime"):
        cov = source_coverage.get(source_key, {})
        if isinstance(cov, dict):
            if cov.get("error_count", 0) > 0:
                data_gaps.append({
                    "type": "snapshot_errors",
                    "source": source_key,
                    "error_count": cov["error_count"],
                })
            if cov.get("has_errors"):
                data_gaps.append({
                    "type": "snapshot_has_errors",
                    "source": source_key,
                })

    for label, packet in (("market_structure", market_packet), ("search_demand", search_packet)):
        packet_gaps = as_list(packet.get("data_gaps"))
        data_gaps.extend(packet_gaps)
        blocking = as_list(packet.get("blocking_gaps"))
        blocking_gaps.extend(blocking)

    snapshot_gaps = list(as_list(ss_snapshot.get("data_gaps"))) + list(as_list(sf_snapshot.get("data_gaps")))
    data_gaps.extend(snapshot_gaps)

    return _dedupe_dicts(data_gaps), _dedupe_dicts(blocking_gaps)


def _determine_completeness_level(
    route_checks: list[dict[str, Any]],
    source_coverage: dict[str, Any],
    metric_coverage: dict[str, Any],
    blocking_gaps: list[dict[str, Any]],
) -> str:
    if blocking_gaps:
        return "blocker"
    if any(check.get("gap_level") == "blocker" for check in route_checks):
        return "blocker"
    for key in ("sellersprite", "sorftime"):
        cov = source_coverage.get(key, {})
        if isinstance(cov, dict):
            if cov.get("confidence") == "low" or cov.get("evidence_packet_confidence") == "low":
                return "blocker"
    if any(check.get("gap_level") == "warning" for check in route_checks):
        return "warning"
    for key in ("market_structure", "search_demand"):
        mc = metric_coverage.get(key, {})
        if isinstance(mc, dict) and mc.get("evidence_item_count", 0) == 0:
            return "blocker"
    return "acceptable"


def _determine_conflict_level(
    comparable_conflicts: list[dict[str, Any]],
    basis_mismatches: list[dict[str, Any]],
    data_gaps: list[dict[str, Any]],
) -> str:
    if any(c.get("severity") == "blocking" for c in comparable_conflicts):
        return "blocker"
    if any(g.get("severity") in ("blocker", "blocking") for g in data_gaps if isinstance(g, dict)):
        return "blocker"
    if any(c.get("severity") == "material" for c in comparable_conflicts):
        return "warning"
    if basis_mismatches:
        return "warning"
    if comparable_conflicts:
        return "warning"
    return "none"


def _completeness_next_actions(level: str, blocking_gaps: list[dict[str, Any]]) -> list[str]:
    if level == "blocker":
        actions = ["补齐 P4 深挖数据缺口后重跑 deep_data_completeness_check"]
        for gap in blocking_gaps[:3]:
            if isinstance(gap, dict):
                actions.append(f"解决阻断缺口: {first_text(gap.get('type'), gap.get('route_id', ''))}")
        return actions
    if level == "warning":
        return ["部分数据覆盖有缺口，进入冲突复核时需标记为 warning", "继续 P4-4 冲突复核"]
    return ["继续 P4-4 冲突复核"]


def _conflict_next_actions(
    level: str,
    comparable_conflicts: list[dict[str, Any]],
    basis_mismatches: list[dict[str, Any]],
) -> list[str]:
    actions: list[str] = []
    if level == "blocker":
        actions.append("存在阻断性冲突，需人工确认口径对齐或补齐数据后重跑 conflict_resolution_packet")
        blocking = [c for c in comparable_conflicts if c.get("severity") == "blocking"]
        for c in blocking[:3]:
            actions.append(f"解决 blocking conflict: {c.get('metric_name', c.get('conflict_id', ''))}")
        return actions
    if level == "warning":
        material = [c for c in comparable_conflicts if c.get("severity") == "material"]
        if material:
            actions.append(f"{len(material)} 个 material 冲突需在 P5 前确认")
        if basis_mismatches:
            actions.append(f"{len(basis_mismatches)} 个 basis_mismatch 需在归一化阶段对齐口径")
        actions.append("继续推进 P5 VOC Gate，携带 P4 conflict 上下文")
        return actions
    actions.append("继续推进 P5 VOC Gate")
    return actions


def _normalize_basis_for_comparison(
    basis: dict[str, Any],
    overrides: dict[str, Any],
) -> dict[str, Any]:
    """Normalize a metric_basis for cross-source comparison by applying overrides."""
    normalized = dict(basis)
    for field, value in overrides.items():
        normalized[field] = value
    return normalized


def _evidence_items_by_type(packet: dict[str, Any]) -> dict[str, dict[str, Any]]:
    items = as_list(packet.get("evidence_items"))
    result: dict[str, dict[str, Any]] = {}
    for item in items:
        if isinstance(item, dict):
            item_type = first_text(item.get("item_type"))
            if item_type:
                result[item_type] = item
    return result


def _normalized_from_item(item: dict[str, Any]) -> dict[str, Any]:
    facts = item.get("facts") if isinstance(item.get("facts"), dict) else {}
    norm = facts.get("normalized_value")
    if isinstance(norm, dict):
        return norm
    return {}


def _find_normalized_value(normalized: dict[str, Any], fields: tuple[str, ...] | str) -> Any:
    field_values = normalized.get("field_values") if isinstance(normalized, dict) else {}
    numeric_values = normalized.get("numeric_values") if isinstance(normalized, dict) else {}

    search_fields = (fields,) if isinstance(fields, str) else fields
    for field in search_fields:
        if field in field_values and field_values[field] not in (None, "", []):
            return field_values[field]
        if field in numeric_values:
            return numeric_values[field]
    for field in search_fields:
        folded = field.casefold()
        for key, val in field_values.items():
            if str(key).casefold() == folded and val not in (None, "", []):
                return val
        for key, val in numeric_values.items():
            if str(key).casefold() == folded:
                return val
    return None


def _write_blocked_progress(
    run_path: Path,
    progress_path: Path,
    workflow_state: dict[str, Any],
    progress: dict[str, Any],
    reason: str,
) -> None:
    now = _now_iso()
    progress = _progress_template(progress, workflow_state)
    stages = deepcopy(progress.get("stages") or {})
    previous_stage = stages.get(P4_STAGE_ID) if isinstance(stages.get(P4_STAGE_ID), dict) else {}
    stages[P4_STAGE_ID] = {
        "status": "blocked",
        "attempts": int(previous_stage.get("attempts", 0) or 0) + 1,
        "input_artifacts": P4_CONFLICT_INPUT_ARTIFACTS,
        "output_artifacts": P4_CONFLICT_OUTPUT_ARTIFACTS,
        "validation_checks": [{"name": "p4_conflict_review", "pass": False, "detail": reason}],
        "last_error": reason,
        "next_required_user_action": "补齐 P4 深挖数据或解决阻断冲突后重跑 conflict review.",
        "resume_policy": {
            "reuse_existing_artifacts": True,
            "allow_repeat_mcp_call": False,
            "force_refresh": False,
        },
    }
    progress.update({
        "schema_version": P0_SCHEMA_VERSION,
        "current_stage": P4_STAGE_ID,
        "updated_at": now,
        "global_blockers": [{"stage_id": P4_STAGE_ID, "error": reason}],
        "next_action": {
            "type": "blocked",
            "stage_id": P4_STAGE_ID,
            "description": "Resolve P4 conflict review blockers before proceeding.",
        },
        "stages": stages,
    })
    try:
        validate_progress(progress)
        _write_json(progress_path, progress)
    except Exception:
        pass


def _write_failure_progress(run_path: Path, progress_path: Path, error: str) -> None:
    now = _now_iso()
    workflow_state = load_json(run_path / "workflow_state.json", required=False)
    progress = _progress_template(load_json(progress_path, required=False), workflow_state)
    status = _failure_status(error)
    stages = deepcopy(progress.get("stages") or {})
    previous_stage = stages.get(P4_STAGE_ID) if isinstance(stages.get(P4_STAGE_ID), dict) else {}
    stages[P4_STAGE_ID] = {
        "status": status,
        "attempts": int(previous_stage.get("attempts", 0) or 0) + 1,
        "input_artifacts": P4_CONFLICT_INPUT_ARTIFACTS,
        "output_artifacts": P4_CONFLICT_OUTPUT_ARTIFACTS,
        "validation_checks": [{"name": "p4_conflict_review", "pass": False, "detail": error}],
        "last_error": error,
        "next_required_user_action": "Fix P4-4 inputs or rerun P4-2/P4-3 before conflict review.",
        "resume_policy": {
            "reuse_existing_artifacts": True,
            "allow_repeat_mcp_call": False,
            "force_refresh": False,
        },
    }
    progress.update({
        "schema_version": P0_SCHEMA_VERSION,
        "current_stage": P4_STAGE_ID,
        "updated_at": now,
        "global_blockers": [{"stage_id": P4_STAGE_ID, "error": error}],
        "next_action": {
            "type": "fix_stage_error" if status == "failed" else "blocked",
            "stage_id": P4_STAGE_ID,
            "description": "Resolve P4-4 preconditions before rerunning conflict review.",
        },
        "stages": stages,
    })
    try:
        validate_progress(progress)
        _write_json(progress_path, progress)
    except Exception:
        pass


def _progress_template(progress: dict[str, Any], workflow_state: dict[str, Any]) -> dict[str, Any]:
    now = _now_iso()
    if not isinstance(progress, dict) or not progress:
        return {
            "schema_version": P0_SCHEMA_VERSION,
            "current_stage": P4_STAGE_ID,
            "updated_at": now,
            "global_blockers": [],
            "next_action": {
                "type": "run_stage",
                "stage_id": P4_STAGE_ID,
                "description": "Run P4 conflict review — normalization and conflict detection.",
            },
            "completed_artifacts": [],
            "stages": {},
            "workflow_ref": workflow_state.get("workflow_id") or workflow_state.get("run_id") or "",
        }
    progress.setdefault("schema_version", P0_SCHEMA_VERSION)
    progress.setdefault("current_stage", P4_STAGE_ID)
    progress.setdefault("updated_at", now)
    progress.setdefault("global_blockers", [])
    progress.setdefault("next_action", {})
    progress.setdefault("completed_artifacts", [])
    progress.setdefault("stages", {})
    progress["workflow_ref"] = progress.get("workflow_ref") or workflow_state.get("workflow_id") or workflow_state.get("run_id") or ""
    return progress


def _route_lineage(route_matrix: dict[str, Any]) -> tuple[list[str], list[str]]:
    selected = [item for item in as_list(route_matrix.get("selected_routes")) if isinstance(item, dict)]
    route_refs = [f"route_matrix_confirm.json#selected_routes[{index}]" for index, _ in enumerate(selected)]
    selected_routes = [
        first_text(route.get("route_id"), route.get("candidate_id"), route.get("route_name"), route.get("label"), f"route_{index + 1}")
        for index, route in enumerate(selected)
    ]
    if not route_refs:
        raise P4ConflictReviewError("route_matrix_confirm.selected_routes must not be empty")
    return route_refs, selected_routes


def _failure_status(error: str) -> str:
    text = error.lower()
    if "decision must be confirm" in text or "overall_level must not be blocker" in text:
        return "blocked"
    if "missing" in text and ("snapshot" in text or "evidence_packet" in text or "artifact" in text):
        return "blocked"
    if "blocker" in text:
        return "blocked"
    return "failed"




