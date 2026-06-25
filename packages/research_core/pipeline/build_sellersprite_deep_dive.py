#!/usr/bin/env python3
"""Build P4 SellerSprite market-structure deep-dive artifacts."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from packages.research_core.contracts import (
    P4ContractError,
    P4_SCHEMA_VERSION,
    P4_STAGE_ID,
    validate_deep_snapshot,
    validate_p4_evidence_packet,
    validate_p4_preconditions,
)
from packages.research_core.contracts.p0_contracts import P0_SCHEMA_VERSION
from packages.research_core.pipeline._utils import as_list, first_text, load_json, numeric_value
from packages.research_core.pipeline.quick_market_check import validate_progress


SNAPSHOT_DIR = "mcp_snapshots"
MARKET_STRUCTURE_DIR = "market_structure"
SELLERSPRITE_SNAPSHOT_NAME = "sellersprite_deep_snapshot.json"
MARKET_STRUCTURE_PACKET_NAME = "market_structure_evidence_packet.json"
SELLERSPRITE_SOURCE_NAME = "sellersprite"

P4_SELLERSPRITE_INPUT_ARTIFACTS = [
    "candidate_pool.json",
    "route_matrix_confirm.json",
    "data_completeness_check.json",
    "progress.json",
]
P4_SELLERSPRITE_OUTPUT_ARTIFACTS = [
    f"{SNAPSHOT_DIR}/{SELLERSPRITE_SNAPSHOT_NAME}",
    f"{MARKET_STRUCTURE_DIR}/{MARKET_STRUCTURE_PACKET_NAME}",
]

EVIDENCE_SPECS: tuple[dict[str, Any], ...] = (
    {
        "item_type": "market_capacity",
        "tools": ("market_research", "market_research_statistics"),
        "metric_unit": "units",
        "aggregation_unit": "category",
        "sample_scope": "category_market",
        "expected_fields": ("totalUnits", "total_units", "units", "totalAmount", "total_amount", "avgPrice", "avgRatings", "avgRating"),
    },
    {
        "item_type": "price_band",
        "tools": ("market_price_distribution", "market_research", "product_research", "asin_detail"),
        "metric_unit": "currency",
        "aggregation_unit": "category",
        "sample_scope": "category_price_distribution",
        "expected_fields": ("priceRange", "price_range", "products", "units", "revenue", "unitsRatio", "avgPrice", "price"),
    },
    {
        "item_type": "seller_concentration",
        "tools": ("market_seller_concentration",),
        "metric_unit": "percent",
        "aggregation_unit": "seller",
        "sample_scope": "category_seller_distribution",
        "expected_fields": ("sellerName", "products", "totalUnits", "totalRevenue", "totalUnitsRatio", "totalRevenueRatio"),
    },
    {
        "item_type": "competitor_structure",
        "tools": ("product_research", "competitor_lookup", "market_product_concentration", "market_brand_concentration"),
        "metric_unit": "mixed",
        "aggregation_unit": "asin",
        "sample_scope": "competitor_pool",
        "expected_fields": ("asin", "brand", "sellerName", "price", "ratings", "rating", "totalUnits", "total_units"),
    },
    {
        "item_type": "asin_operating_data",
        "tools": ("asin_detail", "competitor_lookup"),
        "metric_unit": "mixed",
        "aggregation_unit": "asin",
        "sample_scope": "representative_asin",
        "expected_fields": ("asin", "price", "rating", "ratings", "reviews", "sellerName", "brand", "nodeIdPath", "parentAsin", "variations", "fulfillment"),
    },
    {
        "item_type": "review_threshold",
        "tools": ("market_ratings_count", "market_rating_distribution", "market_research", "asin_detail"),
        "metric_unit": "rating_count",
        "aggregation_unit": "category",
        "sample_scope": "category_review_threshold",
        "expected_fields": ("avgRatings", "avgRating", "ratings", "rating", "reviews"),
    },
    {
        "item_type": "category_boundary",
        "tools": ("market_research", "asin_detail", "product_research", "competitor_lookup"),
        "metric_unit": "category_node",
        "aggregation_unit": "category",
        "sample_scope": "node_mapping_input",
        "expected_fields": ("nodeIdPath", "nodeId", "category", "categoryPath", "product_node"),
    },
)


class P4SellerSpriteError(ValueError):
    """Raised when P4-2 SellerSprite artifacts cannot be built."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build P4 SellerSprite market-structure deep-dive artifacts.")
    parser.add_argument("run_dir", type=Path, help="Path to runs/<run_id> directory")
    parser.add_argument(
        "--snapshot-source",
        type=Path,
        help="Optional P4 deep snapshot or SellerSprite probe raw JSON to reuse.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        run_sellersprite_deep_dive(args.run_dir, snapshot_source=args.snapshot_source)
    except Exception as exc:  # pragma: no cover - CLI guard
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


def run_sellersprite_deep_dive(
    run_dir: Path | str,
    *,
    snapshot_source: Path | str | None = None,
) -> dict[str, Path]:
    """Generate SellerSprite deep snapshot and market-structure evidence packet."""
    run_path = Path(run_dir).expanduser().resolve()
    if not run_path.exists():
        raise P4SellerSpriteError(f"run_dir not found: {run_path}")

    progress_path = run_path / "progress.json"
    try:
        validate_p4_preconditions(run_path)
        workflow_state = load_json(run_path / "workflow_state.json")
        route_matrix = load_json(run_path / "route_matrix_confirm.json")
        candidate_pool = load_json(run_path / "candidate_pool.json")
        progress = load_json(progress_path)

        snapshot_path = ensure_sellersprite_deep_snapshot(
            run_path,
            workflow_state,
            route_matrix,
            candidate_pool,
            snapshot_source=Path(snapshot_source).expanduser().resolve() if snapshot_source else None,
        )
        snapshot = load_json(snapshot_path)
        validate_deep_snapshot(snapshot, expected_source_name=SELLERSPRITE_SOURCE_NAME)

        evidence_packet = build_market_structure_evidence_packet(
            snapshot,
            workflow_state,
            route_matrix,
            candidate_pool,
            run_path,
        )
        validate_p4_evidence_packet(evidence_packet, expected_primary_source=SELLERSPRITE_SOURCE_NAME)

        packet_path = run_path / MARKET_STRUCTURE_DIR / MARKET_STRUCTURE_PACKET_NAME
        _write_json(packet_path, evidence_packet)

        progress = build_sellersprite_success_progress(progress, workflow_state, evidence_packet)
        validate_progress(progress)
        _write_json(progress_path, progress)

        return {
            "sellersprite_deep_snapshot": snapshot_path,
            "market_structure_evidence_packet": packet_path,
            "progress": progress_path,
        }
    except Exception as exc:
        _write_failure_progress(run_path, progress_path, str(exc))
        raise P4SellerSpriteError(str(exc)) from exc


def ensure_sellersprite_deep_snapshot(
    run_path: Path,
    workflow_state: dict[str, Any],
    route_matrix: dict[str, Any],
    candidate_pool: dict[str, Any],
    *,
    snapshot_source: Path | None = None,
) -> Path:
    target = run_path / SNAPSHOT_DIR / SELLERSPRITE_SNAPSHOT_NAME
    if target.exists():
        snapshot = load_json(target)
        validate_deep_snapshot(snapshot, expected_source_name=SELLERSPRITE_SOURCE_NAME)
        return target
    if snapshot_source is None:
        raise P4SellerSpriteError(f"missing SellerSprite deep snapshot: {target}")
    if not snapshot_source.exists():
        raise P4SellerSpriteError(f"snapshot source not found: {snapshot_source}")

    source = load_json(snapshot_source)
    if _looks_like_p4_snapshot(source):
        snapshot = deepcopy(source)
        snapshot["run_id"] = _run_id(workflow_state, run_path)
        _ensure_route_lineage(snapshot, route_matrix)
        validate_deep_snapshot(snapshot, expected_source_name=SELLERSPRITE_SOURCE_NAME)
    else:
        snapshot = normalize_sellersprite_probe_snapshot(source, workflow_state, route_matrix, candidate_pool, run_path)
        validate_deep_snapshot(snapshot, expected_source_name=SELLERSPRITE_SOURCE_NAME)

    _write_json(target, snapshot)
    return target


def normalize_sellersprite_probe_snapshot(
    probe: dict[str, Any],
    workflow_state: dict[str, Any],
    route_matrix: dict[str, Any],
    candidate_pool: dict[str, Any],
    run_path: Path,
) -> dict[str, Any]:
    now = _now_iso()
    route_refs, selected_routes = _route_lineage(route_matrix)
    probe_inputs = probe.get("probe_inputs") if isinstance(probe.get("probe_inputs"), dict) else {}
    tool_records = [item for item in as_list(probe.get("tool_calls")) if isinstance(item, dict)]
    if not tool_records:
        raise P4SellerSpriteError("SellerSprite probe snapshot must include tool_calls")

    tool_calls: list[dict[str, Any]] = []
    tool_results: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    data_gaps: list[dict[str, Any]] = []
    for index, record in enumerate(tool_records):
        base_tool_name = _base_tool_name(record.get("tool_name"))
        status = _normalize_tool_status(record.get("status"))
        call_id = f"sellersprite-deep-call-{index + 1}"
        params = record.get("request") if isinstance(record.get("request"), dict) else {}
        tool_calls.append(
            {
                "call_id": call_id,
                "tool_name": base_tool_name,
                "params": params,
                "status": status,
                "started_at": first_text(record.get("tested_at"), probe.get("created_at"), now),
                "finished_at": first_text(record.get("tested_at"), probe.get("created_at"), now),
                "source_probe_tool_name": record.get("tool_name", ""),
            }
        )
        raw_result = _probe_raw_result(record)
        result: dict[str, Any] = {
            "result_id": f"sellersprite-deep-result-{index + 1}",
            "call_id": call_id,
            "tool_name": base_tool_name,
            "status": status,
        }
        if raw_result is not None:
            result["raw_result"] = raw_result
        else:
            result["normalized_preview"] = {
                "available_fields": record.get("available_fields") or [],
                "missing_or_unstable_fields": record.get("missing_or_unstable_fields") or [],
                "field_notes": record.get("field_notes") or [],
            }
        tool_results.append(result)

        if status == "error":
            error = record.get("error") if isinstance(record.get("error"), dict) else {}
            errors.append(
                {
                    "type": first_text(error.get("type"), "tool_error"),
                    "tool_name": base_tool_name,
                    "message": first_text(error.get("message"), "SellerSprite tool call failed."),
                    "params_summary": params,
                }
            )
            data_gaps.append(
                {
                    "type": "tool_call_failed",
                    "tool_name": base_tool_name,
                    "severity": "warning",
                    "impact": "This SellerSprite evidence source is unavailable for P4-2 and must be cross-checked later.",
                }
            )
        for field in as_list(record.get("missing_or_unstable_fields")):
            if first_text(field):
                data_gaps.append(
                    {
                        "type": "missing_or_unstable_field",
                        "tool_name": base_tool_name,
                        "field": first_text(field),
                        "severity": "warning",
                    }
                )

    return {
        "schema_version": P4_SCHEMA_VERSION,
        "snapshot_id": f"{_run_id(workflow_state, run_path)}-sellersprite-deep",
        "run_id": _run_id(workflow_state, run_path),
        "source_name": SELLERSPRITE_SOURCE_NAME,
        "source_doc_refs": [
            "docs/sellersprite_mcp_tools_reference.md#seller-sprite-tools",
            "docs/references/p4_mcp_capability_mapping.md#sellersprite",
        ],
        "route_refs": route_refs,
        "selected_routes": selected_routes,
        "tool_calls": tool_calls,
        "tool_results": tool_results,
        "errors": errors,
        "data_gaps": _dedupe_dicts(data_gaps),
        "created_at": first_text(probe.get("created_at"), now),
        "retry_policy": {
            "max_attempts": 1,
            "reuse_existing_snapshot": True,
            "allow_network_call": False,
        },
        "force_refresh": False,
        "input_lineage": {
            "workflow_ref": _run_id(workflow_state, run_path),
            "route_refs": route_refs,
            "selected_routes": selected_routes,
            "source_candidate_pool": "candidate_pool.json",
            "site": first_text(workflow_state.get("site"), probe_inputs.get("site"), "US"),
            "nodeIdPath": first_text(probe_inputs.get("node_id_path"), probe_inputs.get("nodeIdPath")),
            "candidate_pool_ref": candidate_pool.get("workflow_ref", ""),
        },
    }


def build_market_structure_evidence_packet(
    snapshot: dict[str, Any],
    workflow_state: dict[str, Any],
    route_matrix: dict[str, Any],
    candidate_pool: dict[str, Any],
    run_path: Path,
) -> dict[str, Any]:
    route_refs, selected_routes = _route_lineage(route_matrix)
    call_index_by_id = {
        str(call.get("call_id")): index
        for index, call in enumerate(snapshot.get("tool_calls") or [])
        if isinstance(call, dict)
    }
    results = [item for item in as_list(snapshot.get("tool_results")) if isinstance(item, dict)]
    data_gaps = list(as_list(snapshot.get("data_gaps")))
    errors = list(as_list(snapshot.get("errors")))
    evidence_items: list[dict[str, Any]] = []
    metric_basis: dict[str, dict[str, Any]] = {}
    derived_metrics: dict[str, dict[str, Any]] = {}

    for spec in EVIDENCE_SPECS:
        result_index, result = _find_result(results, spec["tools"])
        result_ref = f"{SNAPSHOT_DIR}/{SELLERSPRITE_SNAPSHOT_NAME}#tool_results[{result_index}]" if result_index >= 0 else f"{SNAPSHOT_DIR}/{SELLERSPRITE_SNAPSHOT_NAME}#tool_results[0]"
        call_ref = _call_ref(result, call_index_by_id)
        basis_id = f"sellersprite_{spec['item_type']}_basis"
        tool_name = _base_tool_name(result.get("tool_name") if isinstance(result, dict) else first_text(spec["tools"][0]))
        rows = _extract_rows(_result_payload(result))
        normalized = _normalize_evidence_value(rows, spec["expected_fields"])
        item_gaps = _field_gaps(spec, result, rows, normalized, result_ref)
        data_gaps.extend(item_gaps)
        node_lineage = _extract_node_lineage(result, rows, snapshot, route_matrix, candidate_pool)

        metric_basis[basis_id] = _metric_basis(
            source_name=SELLERSPRITE_SOURCE_NAME,
            tool_name=tool_name,
            metric_unit=spec["metric_unit"],
            aggregation_unit=spec["aggregation_unit"],
            sample_scope=spec["sample_scope"],
            workflow_state=workflow_state,
            snapshot=snapshot,
            result=result,
            route_refs=route_refs,
            selected_routes=selected_routes,
            node_lineage=node_lineage,
        )
        evidence_items.append(
            {
                "item_id": f"sellersprite_{spec['item_type']}",
                "item_type": spec["item_type"],
                "facts": {
                    "tool_name": tool_name,
                    "raw_value": _result_payload(result),
                    "normalized_value": normalized,
                    "node_mapping_input": node_lineage,
                    "expected_fields": list(spec["expected_fields"]),
                    "source_status": result.get("status", "missing") if isinstance(result, dict) else "missing",
                },
                "metric_basis_ref": basis_id,
                "evidence_refs": [result_ref],
                "source_refs": [call_ref],
            }
        )
        derived_metrics[f"{spec['item_type']}_signal"] = {
            "value": _first_metric_value(normalized),
            "raw_value": _result_payload(result),
            "normalized_value": normalized,
            "metric_basis_ref": basis_id,
            "evidence_refs": [result_ref],
        }

    if errors:
        data_gaps.extend(_error_gaps(errors))

    packet = {
        "schema_version": P4_SCHEMA_VERSION,
        "packet_id": "market_structure_evidence_packet",
        "run_id": _run_id(workflow_state, run_path),
        "primary_source": SELLERSPRITE_SOURCE_NAME,
        "cross_check_sources": ["sorftime"],
        "source_snapshot_refs": [f"{SNAPSHOT_DIR}/{SELLERSPRITE_SNAPSHOT_NAME}#snapshot"],
        "route_refs": route_refs,
        "selected_routes": selected_routes,
        "evidence_items": evidence_items,
        "derived_metrics": derived_metrics,
        "metric_basis": metric_basis,
        "data_gaps": _dedupe_dicts(data_gaps),
        "blocking_gaps": [],
        "confidence": _packet_confidence(data_gaps),
        "source_refs": _unique_texts(
            [f"{SNAPSHOT_DIR}/{SELLERSPRITE_SNAPSHOT_NAME}#snapshot"]
            + [ref for item in evidence_items for ref in item.get("evidence_refs", [])]
        ),
        "created_at": _now_iso(),
        "generation_provenance": {
            "execution_mode": "script_generated",
            "source_stage": "p4_sellersprite_market_structure",
            "source_snapshot_path": f"{SNAPSHOT_DIR}/{SELLERSPRITE_SNAPSHOT_NAME}",
            "source_candidate_pool": "candidate_pool.json",
            "route_matrix_ref": "route_matrix_confirm.json",
            "does_not_complete_stage_6": True,
        },
    }
    return packet


def build_sellersprite_success_progress(
    progress: dict[str, Any],
    workflow_state: dict[str, Any],
    evidence_packet: dict[str, Any],
) -> dict[str, Any]:
    now = _now_iso()
    progress = _progress_template(progress, workflow_state)
    completed = list(progress.get("completed_artifacts") or [])
    for artifact in P4_SELLERSPRITE_OUTPUT_ARTIFACTS:
        if artifact not in completed:
            completed.append(artifact)

    stages = deepcopy(progress.get("stages") or {})
    previous_stage = stages.get(P4_STAGE_ID) if isinstance(stages.get(P4_STAGE_ID), dict) else {}
    stages[P4_STAGE_ID] = {
        "status": "running",
        "attempts": int(previous_stage.get("attempts", 0) or 0) + 1,
        "input_artifacts": P4_SELLERSPRITE_INPUT_ARTIFACTS,
        "output_artifacts": P4_SELLERSPRITE_OUTPUT_ARTIFACTS,
        "validation_checks": [
            {"name": "p4_preconditions", "pass": True, "detail": "P3 route matrix is confirmed."},
            {"name": "sellersprite_deep_snapshot_schema", "pass": True, "detail": "Snapshot passed P4 deep snapshot contract."},
            {"name": "market_structure_evidence_schema", "pass": True, "detail": f"confidence={evidence_packet.get('confidence')}"},
            {"name": "p4_scope_no_downstream_artifacts", "pass": True, "detail": "P4-2 only builds SellerSprite market-structure artifacts."},
        ],
        "last_error": "",
        "next_required_user_action": "",
        "resume_policy": {
            "reuse_existing_artifacts": True,
            "allow_repeat_mcp_call": False,
            "force_refresh": False,
        },
    }

    progress.update(
        {
            "schema_version": P0_SCHEMA_VERSION,
            "current_stage": P4_STAGE_ID,
            "updated_at": now,
            "global_blockers": [],
            "next_action": {
                "type": "run_stage",
                "stage_id": P4_STAGE_ID,
                "description": "SellerSprite market structure evidence is ready; run P4-3 Sorftime search demand deep dive next.",
                "next_substage": "P4-3",
            },
            "completed_artifacts": completed,
            "stages": stages,
            "workflow_ref": progress.get("workflow_ref") or workflow_state.get("workflow_id") or workflow_state.get("run_id") or "",
        }
    )
    return progress


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
        "input_artifacts": P4_SELLERSPRITE_INPUT_ARTIFACTS,
        "output_artifacts": P4_SELLERSPRITE_OUTPUT_ARTIFACTS,
        "validation_checks": [{"name": "p4_sellersprite_deep_dive", "pass": False, "detail": error}],
        "last_error": error,
        "next_required_user_action": "Fix P4-2 inputs or rerun P3 confirmation before SellerSprite deep dive.",
        "resume_policy": {
            "reuse_existing_artifacts": True,
            "allow_repeat_mcp_call": False,
            "force_refresh": False,
        },
    }
    progress.update(
        {
            "schema_version": P0_SCHEMA_VERSION,
            "current_stage": P4_STAGE_ID,
            "updated_at": now,
            "global_blockers": [{"stage_id": P4_STAGE_ID, "error": error}],
            "next_action": {
                "type": "fix_stage_error" if status == "failed" else "blocked",
                "stage_id": P4_STAGE_ID,
                "description": "Resolve P4-2 preconditions or SellerSprite snapshot schema before rerunning SellerSprite deep dive.",
            },
            "stages": stages,
        }
    )
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
                "description": "Run P4 SellerSprite market-structure deep dive.",
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


def _looks_like_p4_snapshot(data: dict[str, Any]) -> bool:
    return data.get("schema_version") == P4_SCHEMA_VERSION and data.get("source_name") == SELLERSPRITE_SOURCE_NAME


def _ensure_route_lineage(snapshot: dict[str, Any], route_matrix: dict[str, Any]) -> None:
    route_refs, selected_routes = _route_lineage(route_matrix)
    snapshot["route_refs"] = route_refs
    snapshot["selected_routes"] = selected_routes
    lineage = snapshot.get("input_lineage") if isinstance(snapshot.get("input_lineage"), dict) else {}
    lineage.update({"route_refs": route_refs, "selected_routes": selected_routes})
    snapshot["input_lineage"] = lineage


def _route_lineage(route_matrix: dict[str, Any]) -> tuple[list[str], list[str]]:
    selected = [item for item in as_list(route_matrix.get("selected_routes")) if isinstance(item, dict)]
    route_refs = [f"route_matrix_confirm.json#selected_routes[{index}]" for index, _ in enumerate(selected)]
    selected_routes = [
        first_text(route.get("route_id"), route.get("candidate_id"), route.get("route_name"), route.get("label"), f"route_{index + 1}")
        for index, route in enumerate(selected)
    ]
    if not route_refs:
        raise P4SellerSpriteError("route_matrix_confirm.selected_routes must not be empty")
    return route_refs, selected_routes


def _find_result(results: list[dict[str, Any]], tool_names: tuple[str, ...]) -> tuple[int, dict[str, Any]]:
    for index, result in enumerate(results):
        base_name = _base_tool_name(result.get("tool_name"))
        if base_name in tool_names:
            return index, result
    for index, result in enumerate(results):
        base_name = _base_tool_name(result.get("tool_name"))
        if any(name in base_name or base_name in name for name in tool_names):
            return index, result
    if results:
        return 0, results[0]
    raise P4SellerSpriteError("sellersprite deep snapshot must include tool_results")


def _call_ref(result: dict[str, Any], call_index_by_id: dict[str, int]) -> str:
    call_id = str(result.get("call_id") or "")
    index = call_index_by_id.get(call_id, 0)
    return f"{SNAPSHOT_DIR}/{SELLERSPRITE_SNAPSHOT_NAME}#tool_calls[{index}]"


def _probe_raw_result(record: dict[str, Any]) -> Any:
    for key in ("raw_result_sample", "raw_result", "response", "data"):
        if key in record and record.get(key) not in (None, "", []):
            return record.get(key)
    return None


def _result_payload(result: dict[str, Any]) -> Any:
    if not isinstance(result, dict):
        return {}
    for key in ("raw_result", "normalized_preview"):
        if key in result and result.get(key) not in (None, "", []):
            return result.get(key)
    return {}


def _extract_rows(payload: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if isinstance(payload, list):
        for item in payload:
            rows.extend(_extract_rows(item))
        return rows
    if not isinstance(payload, dict):
        return rows
    for key in ("items", "rows", "items_sample", "rows_sample", "products", "asins"):
        value = payload.get(key)
        if isinstance(value, list):
            rows.extend([item for item in value if isinstance(item, dict)])
    data = payload.get("data")
    if isinstance(data, list):
        rows.extend([item for item in data if isinstance(item, dict)])
    elif isinstance(data, dict):
        rows.append(data)
    if not rows and payload:
        rows.append(payload)
    return rows


def _normalize_evidence_value(rows: list[dict[str, Any]], fields: tuple[str, ...]) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for field in fields:
        value = _first_field(rows, field)
        if value not in (None, "", []):
            values[field] = value
    numeric_values = {
        key: number
        for key, value in values.items()
        if (number := numeric_value(value)) is not None
    }
    return {
        "field_values": values,
        "numeric_values": numeric_values,
        "sample_count": len(rows),
    }


def _field_gaps(
    spec: dict[str, Any],
    result: dict[str, Any],
    rows: list[dict[str, Any]],
    normalized: dict[str, Any],
    result_ref: str,
) -> list[dict[str, Any]]:
    gaps: list[dict[str, Any]] = []
    tool_name = _base_tool_name(result.get("tool_name") if isinstance(result, dict) else "")
    status = result.get("status") if isinstance(result, dict) else "missing"
    if status in {"error", "empty", "missing"}:
        gaps.append(
            {
                "type": "tool_result_unavailable",
                "tool_name": tool_name or first_text(spec["tools"][0]),
                "evidence_type": spec["item_type"],
                "severity": "warning",
                "evidence_ref": result_ref,
            }
        )
    if not rows:
        gaps.append(
            {
                "type": "empty_tool_result",
                "tool_name": tool_name or first_text(spec["tools"][0]),
                "evidence_type": spec["item_type"],
                "severity": "warning",
                "evidence_ref": result_ref,
            }
        )
    present = set((normalized.get("field_values") or {}).keys())
    missing = [field for field in spec["expected_fields"] if field not in present]
    if missing:
        gaps.append(
            {
                "type": "empty_or_missing_fields",
                "tool_name": tool_name or first_text(spec["tools"][0]),
                "evidence_type": spec["item_type"],
                "fields": missing,
                "severity": "warning",
                "evidence_ref": result_ref,
            }
        )
    return gaps


def _error_gaps(errors: list[Any]) -> list[dict[str, Any]]:
    gaps = []
    for error in errors:
        if not isinstance(error, dict):
            continue
        gaps.append(
            {
                "type": "snapshot_error",
                "tool_name": first_text(error.get("tool_name"), "unknown"),
                "message": first_text(error.get("message"), error.get("type"), "SellerSprite snapshot error."),
                "severity": "warning",
            }
        )
    return gaps


def _metric_basis(
    *,
    source_name: str,
    tool_name: str,
    metric_unit: str,
    aggregation_unit: str,
    sample_scope: str,
    workflow_state: dict[str, Any],
    snapshot: dict[str, Any],
    result: dict[str, Any],
    route_refs: list[str],
    selected_routes: list[str],
    node_lineage: dict[str, Any],
) -> dict[str, Any]:
    params = _call_params_for_result(snapshot, result)
    site = first_text(params.get("marketplace"), params.get("site"), workflow_state.get("site"), snapshot.get("input_lineage", {}).get("site"), "US")
    data_window = first_text(params.get("month"), snapshot.get("data_window"), "30d")
    return {
        "source_name": source_name,
        "tool_name": tool_name,
        "site": site,
        "marketplace": site,
        "currency": first_text(snapshot.get("currency"), workflow_state.get("currency"), "unknown"),
        "time_window": data_window,
        "data_window": data_window,
        "sample_scope": sample_scope,
        "metric_unit": metric_unit,
        "aggregation_unit": aggregation_unit,
        "parent_child_basis": first_text(params.get("variation"), node_lineage.get("parent_child_basis"), "unknown"),
        "collection_method": "sellersprite_deep_snapshot",
        "collected_at": first_text(snapshot.get("created_at"), _now_iso()),
        "input_lineage": {
            "route_refs": route_refs,
            "selected_routes": selected_routes,
            "params": params,
            "nodeId": node_lineage.get("nodeId", ""),
            "nodeIdPath": node_lineage.get("nodeIdPath", ""),
            "source_snapshot": f"{SNAPSHOT_DIR}/{SELLERSPRITE_SNAPSHOT_NAME}",
        },
    }


def _call_params_for_result(snapshot: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    call_id = result.get("call_id") if isinstance(result, dict) else ""
    for call in as_list(snapshot.get("tool_calls")):
        if isinstance(call, dict) and call.get("call_id") == call_id and isinstance(call.get("params"), dict):
            return call["params"]
    return {}


def _extract_node_lineage(
    result: dict[str, Any],
    rows: list[dict[str, Any]],
    snapshot: dict[str, Any],
    route_matrix: dict[str, Any],
    candidate_pool: dict[str, Any],
) -> dict[str, Any]:
    params = _call_params_for_result(snapshot, result)
    lineage = snapshot.get("input_lineage") if isinstance(snapshot.get("input_lineage"), dict) else {}
    node_path = first_text(
        params.get("nodeIdPath"),
        params.get("nodeIdPaths"),
        _first_field(rows, "nodeIdPath"),
        lineage.get("nodeIdPath"),
        _nested_first(route_matrix, ("confirmed_boundary", "nodeIdPath")),
        _nested_first(candidate_pool, ("summary", "nodeIdPath")),
    )
    node_id = first_text(params.get("nodeId"), _first_field(rows, "nodeId"), lineage.get("nodeId"))
    return {
        "nodeId": node_id,
        "nodeIdPath": node_path,
        "node_mapping_status": "pending_cross_check" if node_path or node_id else "missing",
        "parent_child_basis": first_text(params.get("variation"), "unknown"),
    }


def _first_field(rows: list[dict[str, Any]], field: str) -> Any:
    for row in rows:
        value = _case_insensitive_get(row, field)
        if value not in (None, "", []):
            return value
    return None


def _case_insensitive_get(data: dict[str, Any], field: str) -> Any:
    if field in data:
        return data[field]
    folded = field.casefold()
    for key, value in data.items():
        if str(key).casefold() == folded:
            return value
    return None


def _nested_first(data: dict[str, Any], path: tuple[str, ...]) -> Any:
    current: Any = data
    for part in path:
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def _first_metric_value(normalized: dict[str, Any]) -> Any:
    numeric_values = normalized.get("numeric_values") if isinstance(normalized, dict) else {}
    if isinstance(numeric_values, dict) and numeric_values:
        return next(iter(numeric_values.values()))
    field_values = normalized.get("field_values") if isinstance(normalized, dict) else {}
    if isinstance(field_values, dict) and field_values:
        return next(iter(field_values.values()))
    return None


def _packet_confidence(data_gaps: list[Any]) -> str:
    severe_count = sum(1 for gap in data_gaps if isinstance(gap, dict) and gap.get("type") in {"tool_result_unavailable", "tool_call_failed"})
    if severe_count >= 2:
        return "low"
    if data_gaps:
        return "medium"
    return "high"


def _failure_status(error: str) -> str:
    text = error.lower()
    if "decision must be confirm" in text or "overall_level must not be blocker" in text or "stage_5_route_matrix.status must be done" in text:
        return "blocked"
    return "failed"


def _run_id(workflow_state: dict[str, Any], run_path: Path) -> str:
    return first_text(workflow_state.get("workflow_id"), workflow_state.get("run_id"), run_path.name)


def _base_tool_name(value: Any) -> str:
    text = first_text(value)
    if "." in text:
        text = text.rsplit(".", 1)[-1]
    if "__" in text:
        text = text.rsplit("__", 1)[-1]
    return text or "unknown_tool"


def _normalize_tool_status(value: Any) -> str:
    text = first_text(value).lower()
    if "fail" in text or "error" in text:
        return "error"
    if "empty" in text:
        return "empty"
    return "success"


def _unique_texts(values: list[Any]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = first_text(value)
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _dedupe_dicts(values: list[Any]) -> list[Any]:
    seen: set[str] = set()
    result: list[Any] = []
    for value in values:
        key = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
        if key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
