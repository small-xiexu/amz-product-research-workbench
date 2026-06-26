"""P4 contract validators for the dual-MCP deep-dive stage."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .validators import (
    ContractValidationError,
    validate_candidate_pool,
    validate_workflow_state,
    _require_fields as _shared_require_fields,
    _require_dict as _shared_require_dict,
    _require_list as _shared_require_list,
    _require_string_list as _shared_require_string_list,
    _require_non_empty_text as _shared_require_non_empty_text,
    _require_bool as _shared_require_bool,
    _require_confidence as _shared_require_confidence,
)


P4_SCHEMA_VERSION = "p4-deep-contract-v1"
P4_STAGE_ID = "stage_6_deep_dive"
P4_ALLOWED_SOURCE_NAMES = {"sellersprite", "sorftime"}
P4_ALLOWED_PRIMARY_SOURCES = {"sellersprite", "sorftime"}
P4_ALLOWED_COMPLETENESS_LEVELS = {"acceptable", "warning", "blocker"}
P4_ALLOWED_CONFLICT_LEVELS = {"none", "warning", "blocker"}
P4_ALLOWED_CONFLICT_SEVERITIES = {"minor", "material", "blocking", "basis_mismatch"}
P4_REQUIRED_METRIC_BASIS_FIELDS = (
    "source_name",
    "tool_name",
    "site",
    "marketplace",
    "currency",
    "time_window",
    "data_window",
    "sample_scope",
    "metric_unit",
    "aggregation_unit",
    "parent_child_basis",
    "collection_method",
    "collected_at",
    "input_lineage",
)
P4_COMPARABLE_METRIC_BASIS_FIELDS = (
    "site",
    "marketplace",
    "currency",
    "time_window",
    "data_window",
    "sample_scope",
    "metric_unit",
    "aggregation_unit",
    "parent_child_basis",
    "collection_method",
)


class P4ContractError(ContractValidationError):
    """Raised when a P4 handoff package misses required structure."""


def validate_deep_snapshot(snapshot: dict[str, Any], expected_source_name: str | None = None) -> None:
    _require_dict(snapshot, "deep_snapshot")
    _require_fields(
        snapshot,
        [
            "schema_version",
            "snapshot_id",
            "run_id",
            "source_name",
            "source_doc_refs",
            "route_refs",
            "selected_routes",
            "tool_calls",
            "tool_results",
            "errors",
            "data_gaps",
            "created_at",
            "retry_policy",
            "force_refresh",
            "input_lineage",
        ],
        "deep_snapshot",
    )
    if snapshot.get("schema_version") != P4_SCHEMA_VERSION:
        raise P4ContractError(f"deep_snapshot.schema_version must be {P4_SCHEMA_VERSION}")

    source_name = _require_non_empty_text(snapshot.get("source_name"), "deep_snapshot.source_name")
    if source_name not in P4_ALLOWED_SOURCE_NAMES:
        raise P4ContractError("deep_snapshot.source_name must be sellersprite or sorftime")
    if expected_source_name and source_name != expected_source_name:
        raise P4ContractError(
            f"deep_snapshot.source_name must be {expected_source_name} for this snapshot"
        )

    _require_string_list(snapshot.get("source_doc_refs"), "deep_snapshot.source_doc_refs", min_items=1)
    _require_string_list(snapshot.get("route_refs"), "deep_snapshot.route_refs", min_items=1)
    _require_string_list(snapshot.get("selected_routes"), "deep_snapshot.selected_routes", min_items=1)
    tool_calls = _require_list(snapshot.get("tool_calls"), "deep_snapshot.tool_calls", min_items=1)
    tool_results = _require_list(snapshot.get("tool_results"), "deep_snapshot.tool_results", min_items=1)
    _require_list(snapshot.get("errors"), "deep_snapshot.errors")
    _require_list(snapshot.get("data_gaps"), "deep_snapshot.data_gaps")
    _require_dict(snapshot.get("retry_policy"), "deep_snapshot.retry_policy")
    _require_bool(snapshot.get("force_refresh"), "deep_snapshot.force_refresh")
    _require_dict(snapshot.get("input_lineage"), "deep_snapshot.input_lineage")

    for index, call in enumerate(tool_calls):
        path = f"deep_snapshot.tool_calls[{index}]"
        _require_dict(call, path)
        _require_fields(call, ["call_id", "tool_name", "params", "status", "started_at", "finished_at"], path)
        _require_non_empty_text(call.get("call_id"), f"{path}.call_id")
        _require_non_empty_text(call.get("tool_name"), f"{path}.tool_name")
        _require_dict(call.get("params"), f"{path}.params")
        _require_non_empty_text(call.get("status"), f"{path}.status")
        if call.get("status") not in {"success", "empty", "error"}:
            raise P4ContractError(f"{path}.status is invalid")

    for index, result in enumerate(tool_results):
        path = f"deep_snapshot.tool_results[{index}]"
        _require_dict(result, path)
        _require_fields(result, ["result_id", "call_id", "tool_name", "status"], path)
        _require_non_empty_text(result.get("result_id"), f"{path}.result_id")
        _require_non_empty_text(result.get("call_id"), f"{path}.call_id")
        _require_non_empty_text(result.get("tool_name"), f"{path}.tool_name")
        _require_non_empty_text(result.get("status"), f"{path}.status")
        if result.get("status") not in {"success", "empty", "error"}:
            raise P4ContractError(f"{path}.status is invalid")
        if not any(
            key in result and result.get(key) not in (None, "", [])
            for key in ("raw_result_ref", "raw_result", "normalized_preview")
        ):
            raise P4ContractError(
                f"{path} must include raw_result_ref, raw_result, or normalized_preview"
            )


def validate_p4_evidence_packet(
    packet: dict[str, Any],
    expected_primary_source: str | None = None,
) -> None:
    _require_dict(packet, "p4_evidence_packet")
    _require_fields(
        packet,
        [
            "schema_version",
            "packet_id",
            "run_id",
            "primary_source",
            "cross_check_sources",
            "source_snapshot_refs",
            "route_refs",
            "selected_routes",
            "evidence_items",
            "derived_metrics",
            "metric_basis",
            "data_gaps",
            "blocking_gaps",
            "confidence",
            "source_refs",
            "created_at",
        ],
        "p4_evidence_packet",
    )
    if packet.get("schema_version") != P4_SCHEMA_VERSION:
        raise P4ContractError(f"p4_evidence_packet.schema_version must be {P4_SCHEMA_VERSION}")

    packet_id = _require_non_empty_text(packet.get("packet_id"), "p4_evidence_packet.packet_id")
    primary_source = _require_non_empty_text(packet.get("primary_source"), "p4_evidence_packet.primary_source")
    if primary_source not in P4_ALLOWED_PRIMARY_SOURCES:
        raise P4ContractError("p4_evidence_packet.primary_source must be sellersprite or sorftime")
    if expected_primary_source and primary_source != expected_primary_source:
        raise P4ContractError(
            f"p4_evidence_packet.primary_source must be {expected_primary_source} for this packet"
        )

    if packet_id == "market_structure_evidence_packet" and primary_source != "sellersprite":
        raise P4ContractError("market_structure_evidence_packet.primary_source must be sellersprite")
    if packet_id == "search_demand_evidence_packet" and primary_source != "sorftime":
        raise P4ContractError("search_demand_evidence_packet.primary_source must be sorftime")

    cross_check_sources = _require_string_list(
        packet.get("cross_check_sources"),
        "p4_evidence_packet.cross_check_sources",
        min_items=1,
    )
    if primary_source in {str(source).strip() for source in cross_check_sources}:
        raise P4ContractError("p4_evidence_packet.cross_check_sources must not include primary_source")

    _require_string_list(packet.get("source_snapshot_refs"), "p4_evidence_packet.source_snapshot_refs", min_items=1)
    _require_string_list(packet.get("route_refs"), "p4_evidence_packet.route_refs", min_items=1)
    _require_string_list(packet.get("selected_routes"), "p4_evidence_packet.selected_routes", min_items=1)
    evidence_items = _require_list(packet.get("evidence_items"), "p4_evidence_packet.evidence_items", min_items=1)
    derived_metrics = _require_dict(packet.get("derived_metrics"), "p4_evidence_packet.derived_metrics")
    metric_basis = _require_dict(packet.get("metric_basis"), "p4_evidence_packet.metric_basis")
    if not metric_basis:
        raise P4ContractError("p4_evidence_packet.metric_basis must not be empty")
    _require_list(packet.get("data_gaps"), "p4_evidence_packet.data_gaps")
    _require_list(packet.get("blocking_gaps"), "p4_evidence_packet.blocking_gaps")
    _require_string_list(packet.get("source_refs"), "p4_evidence_packet.source_refs", min_items=1)
    _require_non_empty_text(packet.get("created_at"), "p4_evidence_packet.created_at")
    _require_confidence(packet.get("confidence"), "p4_evidence_packet.confidence")

    for basis_id, basis in metric_basis.items():
        _validate_metric_basis_object(basis, f"p4_evidence_packet.metric_basis.{basis_id}")

    for index, item in enumerate(evidence_items):
        path = f"p4_evidence_packet.evidence_items[{index}]"
        _validate_evidence_item(item, metric_basis, path)

    for metric_name, metric in derived_metrics.items():
        path = f"p4_evidence_packet.derived_metrics.{metric_name}"
        _validate_metric_entry(metric, metric_basis, path)


def validate_deep_data_completeness_check(check: dict[str, Any]) -> None:
    _require_dict(check, "deep_data_completeness_check")
    _require_fields(
        check,
        [
            "schema_version",
            "packet_id",
            "run_id",
            "source_packets",
            "source_snapshots",
            "route_checks",
            "source_coverage",
            "metric_coverage",
            "node_mapping_status",
            "completeness_level",
            "data_gaps",
            "blocking_gaps",
            "required_next_actions",
            "evidence_refs",
            "created_at",
        ],
        "deep_data_completeness_check",
    )
    if check.get("schema_version") != P4_SCHEMA_VERSION:
        raise P4ContractError(f"deep_data_completeness_check.schema_version must be {P4_SCHEMA_VERSION}")
    if check.get("packet_id") != "deep_data_completeness_check":
        raise P4ContractError("deep_data_completeness_check.packet_id must be deep_data_completeness_check")
    _require_string_list(check.get("source_packets"), "deep_data_completeness_check.source_packets", min_items=1)
    _require_string_list(check.get("source_snapshots"), "deep_data_completeness_check.source_snapshots", min_items=1)
    route_checks = _require_list(check.get("route_checks"), "deep_data_completeness_check.route_checks", min_items=1)
    _require_dict(check.get("source_coverage"), "deep_data_completeness_check.source_coverage")
    _require_dict(check.get("metric_coverage"), "deep_data_completeness_check.metric_coverage")
    _require_dict(check.get("node_mapping_status"), "deep_data_completeness_check.node_mapping_status")
    completeness_level = _require_non_empty_text(
        check.get("completeness_level"),
        "deep_data_completeness_check.completeness_level",
    )
    if completeness_level not in P4_ALLOWED_COMPLETENESS_LEVELS:
        raise P4ContractError("deep_data_completeness_check.completeness_level is invalid")
    _require_list(check.get("data_gaps"), "deep_data_completeness_check.data_gaps")
    _require_list(check.get("blocking_gaps"), "deep_data_completeness_check.blocking_gaps")
    _require_string_list(
        check.get("required_next_actions"),
        "deep_data_completeness_check.required_next_actions",
        min_items=1,
    )
    _require_string_list(check.get("evidence_refs"), "deep_data_completeness_check.evidence_refs", min_items=1)
    _require_non_empty_text(check.get("created_at"), "deep_data_completeness_check.created_at")

    for index, route_check in enumerate(route_checks):
        path = f"deep_data_completeness_check.route_checks[{index}]"
        _require_dict(route_check, path)
        if not any(key in route_check for key in ("route_ref", "candidate_ref", "route_id")):
            raise P4ContractError(f"{path} must include route_ref, candidate_ref, or route_id")
        if not any(key in route_check for key in ("status", "check_result", "gap_level")):
            raise P4ContractError(f"{path} must include status, check_result, or gap_level")


def validate_conflict_resolution_packet(packet: dict[str, Any]) -> None:
    _require_dict(packet, "conflict_resolution_packet")
    _require_fields(
        packet,
        [
            "schema_version",
            "packet_id",
            "run_id",
            "source_packets",
            "source_snapshots",
            "metric_basis_checks",
            "comparable_conflicts",
            "non_comparable_items",
            "basis_mismatches",
            "conflict_level",
            "blocking_gaps",
            "required_next_actions",
            "evidence_refs",
            "created_at",
        ],
        "conflict_resolution_packet",
    )
    if packet.get("schema_version") != P4_SCHEMA_VERSION:
        raise P4ContractError(f"conflict_resolution_packet.schema_version must be {P4_SCHEMA_VERSION}")
    if packet.get("packet_id") != "conflict_resolution_packet":
        raise P4ContractError("conflict_resolution_packet.packet_id must be conflict_resolution_packet")
    source_packets = _require_string_list(packet.get("source_packets"), "conflict_resolution_packet.source_packets", min_items=1)
    _require_string_list(packet.get("source_snapshots"), "conflict_resolution_packet.source_snapshots", min_items=1)
    metric_basis_checks = _require_list(
        packet.get("metric_basis_checks"),
        "conflict_resolution_packet.metric_basis_checks",
        min_items=1,
    )
    comparable_conflicts = _require_list(
        packet.get("comparable_conflicts"),
        "conflict_resolution_packet.comparable_conflicts",
    )
    non_comparable_items = _require_list(
        packet.get("non_comparable_items"),
        "conflict_resolution_packet.non_comparable_items",
    )
    basis_mismatches = _require_list(
        packet.get("basis_mismatches"),
        "conflict_resolution_packet.basis_mismatches",
    )
    _require_list(packet.get("blocking_gaps"), "conflict_resolution_packet.blocking_gaps")
    _require_string_list(
        packet.get("required_next_actions"),
        "conflict_resolution_packet.required_next_actions",
        min_items=1,
    )
    _require_string_list(packet.get("evidence_refs"), "conflict_resolution_packet.evidence_refs", min_items=1)
    _require_non_empty_text(packet.get("created_at"), "conflict_resolution_packet.created_at")
    conflict_level = _require_non_empty_text(packet.get("conflict_level"), "conflict_resolution_packet.conflict_level")
    if conflict_level not in P4_ALLOWED_CONFLICT_LEVELS:
        raise P4ContractError("conflict_resolution_packet.conflict_level is invalid")

    metric_basis_check_map: dict[str, dict[str, Any]] = {}
    for index, check in enumerate(metric_basis_checks):
        path = f"conflict_resolution_packet.metric_basis_checks[{index}]"
        _require_dict(check, path)
        metric_name = _require_non_empty_text(check.get("metric_name"), f"{path}.metric_name")
        primary_basis = _require_dict(check.get("primary_basis"), f"{path}.primary_basis")
        secondary_basis = _require_dict(check.get("secondary_basis"), f"{path}.secondary_basis")
        comparison = validate_metric_basis_comparable(primary_basis, secondary_basis)
        check["comparability"] = comparison
        metric_basis_check_map[metric_name] = comparison
        if check.get("comparable") is False or check.get("comparable") == "false":
            if comparison["comparable"]:
                raise P4ContractError(f"{path}.comparable contradicts basis comparison result")
        elif not comparison["comparable"]:
            raise P4ContractError(
                "metric_basis_checks that are not comparable must be marked comparable=false and moved out of comparable_conflicts"
            )

    if comparable_conflicts and not metric_basis_checks:
        raise P4ContractError("conflict_resolution_packet.metric_basis_checks must not be empty when comparable_conflicts exist")

    if any(not check["comparability"]["comparable"] for check in metric_basis_checks):
        mismatch_metrics = {
            check["metric_name"]
            for check in metric_basis_checks
            if not check["comparability"]["comparable"]
        }
        comparable_metrics = {
            str(conflict.get("metric_name"))
            for conflict in comparable_conflicts
            if isinstance(conflict, dict) and conflict.get("metric_name")
        }
        if mismatch_metrics & comparable_metrics:
            raise P4ContractError(
                "metric_basis 不可比时，不允许进入 comparable_conflicts，只能进入 basis_mismatches 或 non_comparable_items"
            )
        if not basis_mismatches and not non_comparable_items:
            raise P4ContractError("metric_basis not comparable must be represented in basis_mismatches or non_comparable_items")

    for index, conflict in enumerate(comparable_conflicts):
        path = f"conflict_resolution_packet.comparable_conflicts[{index}]"
        _validate_conflict_item(conflict, path)
        if any(key in conflict for key in ("primary_value", "secondary_value", "numeric_delta", "relative_delta")) and not metric_basis_checks:
            raise P4ContractError(f"{path} numeric comparison requires metric_basis_checks")

    for index, item in enumerate(non_comparable_items):
        path = f"conflict_resolution_packet.non_comparable_items[{index}]"
        _require_dict(item, path)
        if not any(key in item for key in ("metric_name", "field", "reason")):
            raise P4ContractError(f"{path} must include metric_name, field, or reason")

    for index, item in enumerate(basis_mismatches):
        path = f"conflict_resolution_packet.basis_mismatches[{index}]"
        _require_dict(item, path)
        if not any(key in item for key in ("metric_name", "field", "mismatches")):
            raise P4ContractError(f"{path} must include metric_name, field, or mismatches")

    if conflict_level == "blocker" and not packet.get("required_next_actions"):
        raise P4ContractError("blocking conflicts must include required_next_actions")


def validate_metric_basis_comparable(
    primary_basis: dict[str, Any],
    secondary_basis: dict[str, Any],
) -> dict[str, Any]:
    _require_dict(primary_basis, "metric_basis.primary")
    _require_dict(secondary_basis, "metric_basis.secondary")
    missing_fields: list[str] = []
    mismatches: list[dict[str, Any]] = []
    for field in P4_REQUIRED_METRIC_BASIS_FIELDS:
        primary_value = _basis_value(primary_basis.get(field))
        secondary_value = _basis_value(secondary_basis.get(field))
        if primary_value is None or secondary_value is None:
            missing_fields.append(field)
            continue
    for field in P4_COMPARABLE_METRIC_BASIS_FIELDS:
        primary_value = _basis_value(primary_basis.get(field))
        secondary_value = _basis_value(secondary_basis.get(field))
        if primary_value is None or secondary_value is None:
            continue
        if primary_value != secondary_value:
            mismatches.append(
                {
                    "field": field,
                    "primary": primary_value,
                    "secondary": secondary_value,
                }
            )
    comparable = not missing_fields and not mismatches
    return {
        "comparable": comparable,
        "missing_fields": missing_fields,
        "mismatches": mismatches,
        "required_fields": list(P4_REQUIRED_METRIC_BASIS_FIELDS),
        "compared_fields": list(P4_COMPARABLE_METRIC_BASIS_FIELDS),
    }


def validate_p4_preconditions(run_dir: Path | str) -> None:
    run_path = Path(run_dir).expanduser().resolve()
    if not run_path.exists():
        raise P4ContractError(f"run_dir not found: {run_path}")

    workflow_state = _load_json(run_path / "workflow_state.json")
    validate_workflow_state(workflow_state)

    candidate_pool_path = run_path / "candidate_pool.json"
    route_matrix_path = run_path / "route_matrix_confirm.json"
    p3_completeness_path = run_path / "data_completeness_check.json"
    progress_path = run_path / "progress.json"

    _assert_exists(candidate_pool_path, "candidate_pool.json")
    _assert_exists(route_matrix_path, "route_matrix_confirm.json")
    _assert_exists(p3_completeness_path, "data_completeness_check.json")
    _assert_exists(progress_path, "progress.json")

    candidate_pool = _load_json(candidate_pool_path)
    validate_candidate_pool(candidate_pool)
    route_matrix = _load_json(route_matrix_path)
    p3_completeness = _load_json(p3_completeness_path)
    progress = _load_json(progress_path)

    _validate_p3_route_matrix(route_matrix)
    _validate_p3_data_completeness(p3_completeness)
    _validate_progress_base(progress)

    if route_matrix.get("decision") != "confirm":
        raise P4ContractError("route_matrix_confirm.decision must be confirm before P4 deep dive")
    if p3_completeness.get("overall_level") == "blocker":
        raise P4ContractError("data_completeness_check.overall_level must not be blocker before P4 deep dive")

    stage_5 = _stage_state(progress, "stage_5_route_matrix")
    if stage_5.get("status") != "done":
        raise P4ContractError("progress.stages.stage_5_route_matrix.status must be done before P4 deep dive")

    stage_6 = _stage_state(progress, P4_STAGE_ID)
    if stage_6.get("status") == "done":
        deep_completeness = _load_json(run_path / "conflict_review" / "deep_data_completeness_check.json")
        conflict_packet = _load_json(run_path / "conflict_review" / "conflict_resolution_packet.json")
        validate_p4_progress_state(progress, deep_completeness, conflict_packet)


def validate_p4_progress_state(
    progress: dict[str, Any],
    deep_data_completeness_check: dict[str, Any] | None = None,
    conflict_resolution_packet: dict[str, Any] | None = None,
) -> None:
    """Validate that P4 blockers are reflected before later stages can proceed."""
    _validate_progress_base(progress)
    stage_6 = _stage_state(progress, P4_STAGE_ID)
    if stage_6.get("status") != "done":
        return

    if deep_data_completeness_check is None:
        raise P4ContractError("deep_data_completeness_check is required when stage_6_deep_dive is done")
    if conflict_resolution_packet is None:
        raise P4ContractError("conflict_resolution_packet is required when stage_6_deep_dive is done")

    validate_deep_data_completeness_check(deep_data_completeness_check)
    validate_conflict_resolution_packet(conflict_resolution_packet)
    if deep_data_completeness_check.get("completeness_level") == "blocker":
        raise P4ContractError(
            "deep_data_completeness_check.completeness_level must not be blocker when stage_6_deep_dive is done"
        )
    if conflict_resolution_packet.get("conflict_level") == "blocker":
        raise P4ContractError(
            "conflict_resolution_packet.conflict_level must not be blocker when stage_6_deep_dive is done"
        )


def _validate_p3_route_matrix(route_matrix: dict[str, Any]) -> None:
    _require_dict(route_matrix, "route_matrix_confirm")
    _require_fields(
        route_matrix,
        [
            "schema_version",
            "packet_id",
            "run_id",
            "source_candidate_pool",
            "route_options",
            "selected_routes",
            "rejected_routes",
            "decision",
            "decision_reason",
            "required_next_actions",
            "evidence_refs",
            "voc_readiness",
            "data_completeness_ref",
        ],
        "route_matrix_confirm",
    )
    if route_matrix.get("packet_id") != "route_matrix_confirm":
        raise P4ContractError("route_matrix_confirm.packet_id must be route_matrix_confirm")
    if route_matrix.get("decision") not in {"confirm", "revise_candidate_pool", "stop"}:
        raise P4ContractError("route_matrix_confirm.decision is invalid")
    _require_list(route_matrix.get("route_options"), "route_matrix_confirm.route_options", min_items=1)
    _require_list(route_matrix.get("selected_routes"), "route_matrix_confirm.selected_routes")
    _require_list(route_matrix.get("rejected_routes"), "route_matrix_confirm.rejected_routes")
    _require_list(route_matrix.get("required_next_actions"), "route_matrix_confirm.required_next_actions", min_items=1)
    _require_list(route_matrix.get("evidence_refs"), "route_matrix_confirm.evidence_refs", min_items=1)
    _require_dict(route_matrix.get("voc_readiness"), "route_matrix_confirm.voc_readiness")


def _validate_p3_data_completeness(p3_completeness: dict[str, Any]) -> None:
    _require_dict(p3_completeness, "data_completeness_check")
    _require_fields(
        p3_completeness,
        [
            "schema_version",
            "packet_id",
            "run_id",
            "source_candidate_pool",
            "overall_level",
            "route_checks",
            "required_next_actions",
            "evidence_refs",
        ],
        "data_completeness_check",
    )
    if p3_completeness.get("packet_id") != "data_completeness_check":
        raise P4ContractError("data_completeness_check.packet_id must be data_completeness_check")
    if p3_completeness.get("overall_level") not in {"acceptable", "warning", "blocker"}:
        raise P4ContractError("data_completeness_check.overall_level is invalid")
    _require_list(p3_completeness.get("route_checks"), "data_completeness_check.route_checks", min_items=1)
    _require_list(p3_completeness.get("required_next_actions"), "data_completeness_check.required_next_actions", min_items=1)
    _require_list(p3_completeness.get("evidence_refs"), "data_completeness_check.evidence_refs", min_items=1)


def _validate_progress_base(progress: dict[str, Any]) -> None:
    _require_dict(progress, "progress")
    _require_fields(
        progress,
        ["schema_version", "current_stage", "stages", "updated_at", "global_blockers", "next_action", "completed_artifacts"],
        "progress",
    )
    if not isinstance(progress.get("stages"), dict):
        raise P4ContractError("progress.stages must be an object")
    next_action = progress.get("next_action")
    if not isinstance(next_action, dict) or not next_action.get("type") or not next_action.get("description"):
        raise P4ContractError("progress.next_action must include type and description")


def _stage_state(progress: dict[str, Any], stage_id: str) -> dict[str, Any]:
    stages = progress.get("stages") if isinstance(progress, dict) else {}
    stage = stages.get(stage_id) if isinstance(stages, dict) else {}
    return stage if isinstance(stage, dict) else {}


def _validate_evidence_item(
    item: Any,
    metric_basis: dict[str, Any],
    path: str,
) -> None:
    _require_dict(item, path)
    _require_fields(item, ["item_id", "item_type", "facts", "evidence_refs", "source_refs"], path)
    _require_non_empty_text(item.get("item_id"), f"{path}.item_id")
    _require_non_empty_text(item.get("item_type"), f"{path}.item_type")
    _require_dict(item.get("facts"), f"{path}.facts")
    _require_list(item.get("evidence_refs"), f"{path}.evidence_refs", min_items=1)
    _require_list(item.get("source_refs"), f"{path}.source_refs", min_items=1)
    metric_basis_ref = item.get("metric_basis_ref")
    item_metric_basis = item.get("metric_basis")
    if metric_basis_ref:
        _require_non_empty_text(metric_basis_ref, f"{path}.metric_basis_ref")
        if metric_basis_ref not in metric_basis:
            raise P4ContractError(f"{path}.metric_basis_ref must resolve to an entry in metric_basis")
    if item_metric_basis:
        _validate_metric_basis_object(item_metric_basis, f"{path}.metric_basis")
    if not metric_basis_ref and not item_metric_basis:
        raise P4ContractError(f"{path} must include metric_basis_ref or metric_basis")


def _validate_metric_entry(metric: Any, metric_basis: dict[str, Any], path: str) -> None:
    _require_dict(metric, path)
    _require_fields(metric, ["value"], path)
    if "metric_basis_ref" in metric and metric.get("metric_basis_ref"):
        _require_non_empty_text(metric.get("metric_basis_ref"), f"{path}.metric_basis_ref")
        if metric.get("metric_basis_ref") not in metric_basis:
            raise P4ContractError(f"{path}.metric_basis_ref must resolve to an entry in metric_basis")
    if "metric_basis" in metric and metric.get("metric_basis"):
        _validate_metric_basis_object(metric.get("metric_basis"), f"{path}.metric_basis")
    if not metric.get("metric_basis_ref") and not metric.get("metric_basis"):
        raise P4ContractError(f"{path} must include metric_basis_ref or metric_basis")


def _validate_metric_basis_object(basis: Any, path: str) -> None:
    _require_dict(basis, path)
    for field in P4_REQUIRED_METRIC_BASIS_FIELDS:
        if field == "input_lineage":
            _require_dict(basis.get(field), f"{path}.{field}")
        else:
            _require_non_empty_text(basis.get(field), f"{path}.{field}")


def _validate_conflict_item(conflict: Any, path: str) -> None:
    _require_dict(conflict, path)
    _require_fields(conflict, ["conflict_id", "field", "severity", "status"], path)
    _require_non_empty_text(conflict.get("conflict_id"), f"{path}.conflict_id")
    _require_non_empty_text(conflict.get("field"), f"{path}.field")
    severity = _require_non_empty_text(conflict.get("severity"), f"{path}.severity")
    if severity not in P4_ALLOWED_CONFLICT_SEVERITIES:
        raise P4ContractError(f"{path}.severity is invalid")
    _require_non_empty_text(conflict.get("status"), f"{path}.status")
    if conflict.get("primary_basis") and conflict.get("secondary_basis"):
        comparison = validate_metric_basis_comparable(conflict["primary_basis"], conflict["secondary_basis"])
        if not comparison["comparable"]:
            raise P4ContractError(
                "metric_basis 不可比时，不允许进入 comparable_conflicts，只能进入 basis_mismatches 或 non_comparable_items"
            )
    if any(key in conflict for key in ("primary_value", "secondary_value", "numeric_delta", "relative_delta")):
        if not conflict.get("metric_basis_check_id") and not conflict.get("metric_basis_ref"):
            raise P4ContractError(f"{path} numeric comparison requires metric_basis_checks")


def _load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise P4ContractError(f"failed to load JSON: {path}") from exc
    if not isinstance(data, dict):
        raise P4ContractError(f"{path} must contain a JSON object")
    return data


def _assert_exists(path: Path, label: str) -> None:
    if not path.exists():
        raise P4ContractError(f"{label} is required for P4 deep dive")


def _require_fields(value: dict[str, Any], fields: list[str], path: str) -> None:
    _shared_require_fields(value, fields, path, error_cls=P4ContractError)


def _require_dict(value: Any, path: str) -> dict[str, Any]:
    return _shared_require_dict(value, path, error_cls=P4ContractError)


def _require_list(value: Any, path: str, *, min_items: int = 0) -> list[Any]:
    return _shared_require_list(value, path, min_items=min_items, error_cls=P4ContractError)


def _require_string_list(value: Any, path: str, *, min_items: int = 0) -> list[str]:
    return _shared_require_string_list(value, path, min_items=min_items, error_cls=P4ContractError)


def _require_non_empty_text(value: Any, path: str) -> str:
    return _shared_require_non_empty_text(value, path, error_cls=P4ContractError)


def _require_bool(value: Any, path: str) -> None:
    _shared_require_bool(value, path, error_cls=P4ContractError)


def _require_confidence(value: Any, path: str) -> None:
    _shared_require_confidence(value, path, error_cls=P4ContractError)


def _basis_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value).strip() or None
