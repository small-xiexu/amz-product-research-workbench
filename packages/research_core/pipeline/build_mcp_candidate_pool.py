#!/usr/bin/env python3
"""Build P2 MCP candidate pool from P1 quick packets and quick gate."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import OrderedDict
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from packages.research_core.contracts import validate_candidate_pool, validate_workflow_state
from packages.research_core.contracts.p0_contracts import P0_SCHEMA_VERSION
from packages.research_core.contracts.validators import ContractValidationError
from packages.research_core.pipeline._utils import as_list, first_text, load_json, public_text, _now_iso, _write_json, _unique_texts
from packages.research_core.pipeline.quick_market_check import (
    SOURCE_CONFIG,
    validate_quick_gate,
    validate_quick_packet,
)


P2_SCHEMA_VERSION = "p2-mcp-candidate-pool-v1"
STAGE_ID_CANDIDATE_POOL = "stage_4_candidate_pool"
QUICK_CHECK_DIR = "quick_check"


class P2ContractError(ContractValidationError):
    """Raised when P2 candidate-pool artifacts violate the frozen contract."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build P2 candidate pool from P1 quick artifacts.")
    parser.add_argument("run_dir", type=Path, help="Path to runs/<run_id> directory")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        run_candidate_pool(args.run_dir)
    except Exception as exc:  # pragma: no cover - CLI guard
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


def run_candidate_pool(run_dir: Path | str) -> dict[str, Path]:
    """Generate candidate_pool.json and update progress.json for P2."""
    run_path = Path(run_dir).expanduser().resolve()
    if not run_path.exists():
        raise P2ContractError(f"run_dir not found: {run_path}")

    progress_path = run_path / "progress.json"
    try:
        workflow_state = load_json(run_path / "workflow_state.json")
        validate_workflow_state(workflow_state)
        _write_running_progress(run_path, workflow_state, progress_path)

        packets = {
            source_name: _load_quick_packet(run_path, source_name)
            for source_name in SOURCE_CONFIG
        }
        gate = _load_quick_gate(run_path)

        candidate_pool = build_candidate_pool(workflow_state, packets, gate, run_path)
        validate_candidate_pool(candidate_pool)
        validate_candidate_pool_contract(candidate_pool)

        candidate_pool_path = run_path / "candidate_pool.json"
        _write_json(candidate_pool_path, candidate_pool)

        progress = build_success_progress(
            workflow_state,
            packets,
            gate,
            candidate_pool,
            progress_path,
            run_path,
        )
        _write_json(progress_path, progress)

        return {
            "candidate_pool": candidate_pool_path,
            "progress": progress_path,
        }
    except Exception as exc:
        _write_failure_progress(run_path, workflow_state=locals().get("workflow_state"), progress_path=progress_path, error=str(exc))
        raise P2ContractError(str(exc)) from exc


def build_candidate_pool(
    workflow_state: dict[str, Any],
    packets: dict[str, dict[str, Any]],
    gate: dict[str, Any],
    run_path: Path,
) -> dict[str, Any]:
    seller_packet = packets["sellersprite"]
    sorftime_packet = packets["sorftime"]
    gate_result = str(gate.get("gate_result") or "watch").strip()
    pool_status = _pool_status_from_gate(gate_result)
    now = _now_iso()

    seed_rows = _collect_seed_rows(packets, gate)
    candidate_rows = _build_candidates(seed_rows, workflow_state, gate, run_path)
    summary = _build_summary(candidate_rows, gate, workflow_state)
    source_refs = _unique_texts(
        [
            "quick_check/sellersprite_quick_evidence_packet.json#packet",
            "quick_check/sorftime_quick_evidence_packet.json#packet",
            "quick_check/quick_market_gate.json#gate_result",
            "quick_check/quick_market_gate.json#candidate_seeds",
            *gate.get("evidence_refs", []),
            *seller_packet.get("evidence_refs", []),
            *sorftime_packet.get("evidence_refs", []),
        ]
    )
    data_sources = _unique_texts(
        [
            seller_packet.get("source_type", "sellersprite_mcp"),
            sorftime_packet.get("source_type", "sorftime_mcp"),
            "quick_market_gate",
        ]
    )
    known_inputs = workflow_state.get("known_inputs") if isinstance(workflow_state.get("known_inputs"), dict) else {}
    workflow_ref = first_text(workflow_state.get("workflow_id"), workflow_state.get("run_id"), run_path.name)
    site = first_text(workflow_state.get("site"), known_inputs.get("site"), seller_packet.get("metric_basis", {}).get("marketplace"), "US")

    candidate_pool = {
        "schema_version": P2_SCHEMA_VERSION,
        "workflow_ref": workflow_ref,
        "source_stage": "market_quick_check",
        "pool_status": pool_status,
        "confidence": gate.get("confidence", "medium"),
        "data_gaps": _merge_gate_packet_lists(packets, gate, "data_gaps"),
        "excluded_directions": _merge_gate_packet_lists(packets, gate, "excluded_directions"),
        "required_deep_dive": _merge_gate_packet_lists(packets, gate, "required_deep_dive"),
        "candidate_seeds": _normalize_seed_export(seed_rows),
        "evidence_refs": source_refs,
        "generation_provenance": {
            "execution_mode": "script_generated",
            "source_stage": "market_quick_check",
            "workflow_ref": workflow_ref,
            "site": site,
            "pool_status": pool_status,
            "source_packet_paths": [
                f"{QUICK_CHECK_DIR}/{SOURCE_CONFIG['sellersprite']['packet_name']}",
                f"{QUICK_CHECK_DIR}/{SOURCE_CONFIG['sorftime']['packet_name']}",
            ],
            "source_gate_path": f"{QUICK_CHECK_DIR}/quick_market_gate.json",
            "ready_for_p3": pool_status == "ready_for_route_matrix",
            "build_strategy": "merge_quick_gate_and_quick_packets",
        },
        "metadata": {
            "pool_id": f"p2-mcp-{_slugify(workflow_ref)}-{_timestamp_compact(now)}",
            "site": site,
            "generated_at": now,
            "discovery_mode": "mcp",
            "data_sources": data_sources,
        },
        "source_brief": _build_source_brief(workflow_state, gate, packets),
        "summary": summary,
        "candidates": candidate_rows,
    }
    return candidate_pool


def validate_candidate_pool_contract(candidate_pool: dict[str, Any]) -> None:
    if candidate_pool.get("source_stage") != "market_quick_check":
        raise P2ContractError("candidate_pool.source_stage must be market_quick_check")
    if candidate_pool.get("schema_version") != P2_SCHEMA_VERSION:
        raise P2ContractError(f"candidate_pool.schema_version must be {P2_SCHEMA_VERSION}")
    if not isinstance(candidate_pool.get("evidence_refs"), list) or not candidate_pool["evidence_refs"]:
        raise P2ContractError("candidate_pool.evidence_refs must not be empty")
    if not isinstance(candidate_pool.get("generation_provenance"), dict):
        raise P2ContractError("candidate_pool.generation_provenance must be an object")
    if candidate_pool.get("pool_status") not in {"ready_for_route_matrix", "needs_user_review", "excluded"}:
        raise P2ContractError("candidate_pool.pool_status is invalid")


def build_success_progress(
    workflow_state: dict[str, Any],
    packets: dict[str, dict[str, Any]],
    gate: dict[str, Any],
    candidate_pool: dict[str, Any],
    progress_path: Path,
    run_path: Path,
) -> dict[str, Any]:
    progress = _load_progress_template(workflow_state, progress_path)
    pool_status = candidate_pool.get("pool_status", "needs_user_review")
    now = _now_iso()
    stage_status = {
        "ready_for_route_matrix": "done",
        "needs_user_review": "needs_user",
        "excluded": "blocked",
    }[pool_status]
    next_action = _progress_next_action(pool_status)
    completed = list(progress.get("completed_artifacts") or [])
    if "candidate_pool.json" not in completed:
        completed.append("candidate_pool.json")

    stage_checks = [
        {
            "name": "workflow_state_schema",
            "pass": True,
            "detail": "workflow_state.json satisfied the frozen contract.",
        },
        {
            "name": "quick_gate_schema",
            "pass": True,
            "detail": f"gate_result={gate.get('gate_result')}",
        },
        {
            "name": "candidate_pool_schema",
            "pass": True,
            "detail": f"pool_status={pool_status}",
        },
        {
            "name": "route_matrix_artifact_absent",
            "pass": not (run_path / "route_matrix_confirm.json").exists(),
            "detail": "P2 does not enter P3 route matrix.",
        },
        {
            "name": "p3_entry_ready",
            "pass": pool_status == "ready_for_route_matrix",
            "detail": "Candidate pool can enter P3 only when quick gate continues.",
        },
    ]

    progress.update(
        {
            "schema_version": P0_SCHEMA_VERSION,
            "current_stage": STAGE_ID_CANDIDATE_POOL,
            "updated_at": now,
            "global_blockers": [] if pool_status != "excluded" else list(gate.get("gate_reasons") or []),
            "next_action": next_action,
            "completed_artifacts": completed,
            "workflow_ref": progress.get("workflow_ref") or first_text(workflow_state.get("workflow_id"), workflow_state.get("run_id"), ""),
            "stages": _merge_stage_states(
                progress.get("stages"),
                workflow_state,
                candidate_pool,
                stage_status,
                stage_checks,
                gate,
                now,
            ),
        }
    )
    validate_progress_contract(progress)
    return progress


def validate_progress_contract(progress: dict[str, Any]) -> None:
    _validate_progress(progress)
    stage = progress["stages"].get(STAGE_ID_CANDIDATE_POOL)
    if not isinstance(stage, dict):
        raise P2ContractError("progress.stages.stage_4_candidate_pool must exist")
    if stage.get("status") not in {"done", "needs_user", "blocked", "failed"}:
        raise P2ContractError("progress.stages.stage_4_candidate_pool.status is invalid")


def _validate_progress(progress: dict[str, Any]) -> None:
    from packages.research_core.pipeline.quick_market_check import validate_progress as validate_p1_progress

    validate_p1_progress(progress)


def _merge_stage_states(
    existing_stages: Any,
    workflow_state: dict[str, Any],
    candidate_pool: dict[str, Any],
    stage_status: str,
    stage_checks: list[dict[str, Any]],
    gate: dict[str, Any],
    now: str,
) -> dict[str, Any]:
    stages = deepcopy(existing_stages) if isinstance(existing_stages, dict) else {}
    stages[STAGE_ID_CANDIDATE_POOL] = {
        "status": stage_status,
        "attempts": int((stages.get(STAGE_ID_CANDIDATE_POOL, {}) or {}).get("attempts", 0)) + 1,
        "input_artifacts": [
            "workflow_state.json",
            f"{QUICK_CHECK_DIR}/sellersprite_quick_evidence_packet.json",
            f"{QUICK_CHECK_DIR}/sorftime_quick_evidence_packet.json",
            f"{QUICK_CHECK_DIR}/quick_market_gate.json",
        ],
        "output_artifacts": ["candidate_pool.json"],
        "validation_checks": stage_checks,
        "last_error": "",
        "next_required_user_action": _next_required_user_action(stage_status, gate),
        "resume_policy": {
            "reuse_existing_artifacts": True,
            "allow_repeat_mcp_call": False,
            "force_refresh": False,
        },
    }
    if STAGE_ID_CANDIDATE_POOL not in stages:
        stages[STAGE_ID_CANDIDATE_POOL]["attempts"] = 1
    return stages


def _load_progress_template(workflow_state: dict[str, Any], progress_path: Path) -> dict[str, Any]:
    existing = load_json(progress_path, required=False)
    if not isinstance(existing, dict) or not existing:
        now = _now_iso()
        workflow_ref = first_text(workflow_state.get("workflow_id"), workflow_state.get("run_id"), "")
        return {
            "schema_version": P0_SCHEMA_VERSION,
            "current_stage": "stage_3_quick_gate",
            "updated_at": now,
            "global_blockers": [],
            "next_action": {
                "type": "ready_for_p2",
                "stage_id": STAGE_ID_CANDIDATE_POOL,
                "description": "P1 quick check completed; wait for explicit P2 start before generating candidate_pool.json.",
            },
            "completed_artifacts": [
                "mcp_snapshots/sellersprite_quick_snapshot.json",
                "mcp_snapshots/sorftime_quick_snapshot.json",
                "quick_check/sellersprite_quick_evidence_packet.json",
                "quick_check/sorftime_quick_evidence_packet.json",
                "quick_check/quick_market_gate.json",
            ],
            "stages": {
                "stage_2_market_quick_check": {
                    "status": "done",
                    "attempts": 1,
                    "input_artifacts": ["workflow_state.json"],
                    "output_artifacts": [
                        "mcp_snapshots/sellersprite_quick_snapshot.json",
                        "mcp_snapshots/sorftime_quick_snapshot.json",
                        "quick_check/sellersprite_quick_evidence_packet.json",
                        "quick_check/sorftime_quick_evidence_packet.json",
                    ],
                    "validation_checks": [
                        {"name": "snapshot_files_exist", "pass": True, "detail": "Both quick snapshots are reusable."},
                        {"name": "quick_packets_schema", "pass": True, "detail": "Both quick packets satisfy the P1 contract."},
                    ],
                    "last_error": "",
                    "next_required_user_action": "",
                    "resume_policy": {
                        "reuse_existing_artifacts": True,
                        "allow_repeat_mcp_call": False,
                        "force_refresh": False,
                    },
                },
                "stage_3_quick_gate": {
                    "status": "done",
                    "attempts": 1,
                    "input_artifacts": [
                        "quick_check/sellersprite_quick_evidence_packet.json",
                        "quick_check/sorftime_quick_evidence_packet.json",
                    ],
                    "output_artifacts": ["quick_check/quick_market_gate.json"],
                    "validation_checks": [
                        {"name": "quick_gate_schema", "pass": True, "detail": "Gate satisfied the P1 contract."},
                        {"name": "p2_not_started", "pass": True, "detail": "candidate_pool.json is outside P1 scope."},
                    ],
                    "last_error": "",
                    "next_required_user_action": "等待明确 P2 指令后再生成候选池。",
                    "resume_policy": {
                        "reuse_existing_artifacts": True,
                        "allow_repeat_mcp_call": False,
                        "force_refresh": False,
                    },
                },
            },
            "workflow_ref": workflow_ref,
        }
    progress = deepcopy(existing)
    progress.setdefault("schema_version", P0_SCHEMA_VERSION)
    progress.setdefault("global_blockers", [])
    progress.setdefault("completed_artifacts", [])
    progress.setdefault("stages", {})
    progress.setdefault("next_action", {})
    progress.setdefault("current_stage", "stage_3_quick_gate")
    progress.setdefault("updated_at", _now_iso())
    progress["workflow_ref"] = progress.get("workflow_ref") or first_text(workflow_state.get("workflow_id"), workflow_state.get("run_id"), "")
    return progress


def _load_quick_gate(run_path: Path) -> dict[str, Any]:
    gate_path = run_path / QUICK_CHECK_DIR / "quick_market_gate.json"
    gate = load_json(gate_path)
    validate_quick_gate(gate)
    return gate


def _collect_seed_rows(
    packets: dict[str, dict[str, Any]],
    gate: dict[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for source_name, packet in packets.items():
        rows.extend(_seed_rows_from_packet(source_name, packet))
    rows.extend(_seed_rows_from_gate(gate))
    return rows


def _seed_rows_from_packet(source_name: str, packet: dict[str, Any]) -> list[dict[str, Any]]:
    config = SOURCE_CONFIG[source_name]
    facts = packet.get("facts") if isinstance(packet.get("facts"), dict) else {}
    seeds = as_list(facts.get("candidate_seeds"))
    required_deep_dive = as_list(facts.get("required_deep_dive"))
    data_gaps = _normalize_any_list(packet.get("data_gaps"))
    support_level = str(packet.get("support_level") or "unknown")
    demand_level = str(packet.get("demand_signal_level") or "unknown")
    confidence = str(packet.get("confidence") or "medium")
    source_ref = f"{QUICK_CHECK_DIR}/{config['packet_name']}#facts.candidate_seeds"
    if not seeds:
        seeds = [_fallback_seed_from_packet(source_name, packet)]
    rows: list[dict[str, Any]] = []
    for index, seed in enumerate(seeds):
        normalized = _normalize_seed(seed)
        rows.append(
            {
                "candidate_type": normalized["candidate_type"],
                "label": normalized["label"],
                "source_name": source_name,
                "source_agent": config["agent_role"],
                "source_packet_path": f"{QUICK_CHECK_DIR}/{config['packet_name']}",
                "source_ref": source_ref,
                "evidence_ref": f"{source_ref}[{index}]",
                "confidence": confidence,
                "support_level": support_level,
                "demand_signal_level": demand_level,
                "data_gaps": data_gaps,
                "required_deep_dive": _normalize_any_list(required_deep_dive),
                "source_seed": normalized,
            }
        )
    return rows


def _seed_rows_from_gate(gate: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    gate_rows = as_list(gate.get("candidate_seeds"))
    if not gate_rows:
        return rows
    for index, seed in enumerate(gate_rows):
        normalized = _normalize_seed(seed)
        rows.append(
            {
                "candidate_type": normalized["candidate_type"],
                "label": normalized["label"],
                "source_name": "quick_gate",
                "source_agent": "Quick Gate",
                "source_packet_path": f"{QUICK_CHECK_DIR}/quick_market_gate.json",
                "source_ref": f"{QUICK_CHECK_DIR}/quick_market_gate.json#candidate_seeds",
                "evidence_ref": f"{QUICK_CHECK_DIR}/quick_market_gate.json#candidate_seeds[{index}]",
                "confidence": str(gate.get("confidence") or "medium"),
                "support_level": _gate_support_level(str(gate.get("gate_result") or "watch")),
                "demand_signal_level": _gate_demand_level(str(gate.get("gate_result") or "watch")),
                "data_gaps": _normalize_any_list(gate.get("data_gaps")),
                "required_deep_dive": _normalize_any_list(gate.get("required_deep_dive")),
                "source_seed": normalized,
            }
        )
    return rows


def _fallback_seed_from_packet(source_name: str, packet: dict[str, Any]) -> dict[str, Any]:
    facts = packet.get("facts") if isinstance(packet.get("facts"), dict) else {}
    seed_label = first_text(
        _first_seed_text(facts.get("candidate_seeds")),
        packet.get("source_type"),
        source_name,
        "candidate",
    )
    seed_type = "category" if source_name == "sellersprite" else "keyword"
    return {"candidate_type": seed_type, "label": seed_label}


def _build_candidates(
    seed_rows: list[dict[str, Any]],
    workflow_state: dict[str, Any],
    gate: dict[str, Any],
    run_path: Path,
) -> list[dict[str, Any]]:
    if not seed_rows:
        seed_rows = [
            {
                "candidate_type": "route_seed",
                "label": first_text(workflow_state.get("initial_intent"), "candidate"),
                "source_name": "workflow_state",
                "source_agent": "workflow_state",
                "source_packet_path": "workflow_state.json",
                "source_ref": "workflow_state.json#initial_intent",
                "evidence_ref": "workflow_state.json#initial_intent",
                "confidence": "medium",
                "support_level": "unknown",
                "demand_signal_level": "unknown",
                "data_gaps": [],
                "required_deep_dive": [],
                "source_seed": {"candidate_type": "route_seed", "label": first_text(workflow_state.get("initial_intent"), "candidate")},
            }
        ]

    grouped: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    for row in seed_rows:
        key = _candidate_key(row["candidate_type"], row["label"])
        bucket = grouped.setdefault(
            key,
            {
                "candidate_type": row["candidate_type"],
                "label": row["label"],
                "rows": [],
            },
        )
        bucket["rows"].append(row)

    candidates: list[dict[str, Any]] = []
    gate_result = str(gate.get("gate_result") or "watch").strip()
    for index, bucket in enumerate(grouped.values(), start=1):
        rows = bucket["rows"]
        candidates.append(_build_candidate(index, bucket["candidate_type"], bucket["label"], rows, gate_result, gate, run_path))
    return candidates


def _build_candidate(
    index: int,
    candidate_type: str,
    label: str,
    rows: list[dict[str, Any]],
    gate_result: str,
    gate: dict[str, Any],
    run_path: Path,
) -> dict[str, Any]:
    source_agents = _unique_texts([row.get("source_agent") for row in rows])
    source_refs = _unique_texts([row.get("source_ref") for row in rows])
    evidence_refs = _unique_texts([row.get("evidence_ref") for row in rows] + [f"{QUICK_CHECK_DIR}/quick_market_gate.json#candidate_seeds"])
    data_gaps = _unique_any([row.get("data_gaps", []) for row in rows], gate.get("data_gaps"))
    required_deep_dive = _unique_any([row.get("required_deep_dive", []) for row in rows], gate.get("required_deep_dive"))
    confidence = _combine_confidence([str(row.get("confidence") or "medium") for row in rows] + [str(gate.get("confidence") or "medium")])
    support_level = _combine_support_level([str(row.get("support_level") or "unknown") for row in rows], gate_result)
    demand_signal_level = _combine_demand_level([str(row.get("demand_signal_level") or "unknown") for row in rows], gate_result)
    readiness_status, chinese_status, next_step = _readiness_from_gate_result(gate_result)
    reason = _candidate_reason(gate_result, source_agents, gate)
    candidate = {
        "candidate_id": f"p2-{index:02d}-{candidate_type}-{_slugify(label)}",
        "name": label,
        "candidate_type": candidate_type,
        "status": chinese_status,
        "readiness_status": readiness_status,
        "reason": reason,
        "appearance_reason": _appearance_reasons(rows, gate_result),
        "source_agents": source_agents,
        "source_refs": source_refs,
        "evidence_refs": evidence_refs,
        "confidence": confidence,
        "support_level": support_level,
        "demand_signal_level": demand_signal_level,
        "risk_flags": _risk_flags(rows, gate),
        "data_gaps": data_gaps,
        "required_deep_dive": required_deep_dive,
        "top_products": [],
        "missing_data": _missing_data_strings(data_gaps, required_deep_dive),
        "next_step": next_step,
        "demand_evidence": {
            "support_level": support_level,
            "demand_signal_level": demand_signal_level,
            "confidence": confidence,
            "source_refs": source_refs,
            "evidence_refs": evidence_refs,
            "metric_basis": _candidate_metric_basis(rows, run_path),
            "data_gaps": data_gaps,
        },
        "competition_structure": {
            "mixed_pool_level": _combine_mixed_pool_level([row.get("source_seed", {}) for row in rows], gate_result),
            "price_band_health": _combine_price_band_health([row.get("source_seed", {}) for row in rows], gate_result),
            "category_boundary_clarity": _combine_boundary_clarity([row.get("source_seed", {}) for row in rows], gate_result),
            "source_refs": source_refs,
            "evidence_refs": evidence_refs,
            "notes": _competition_notes(gate_result, source_agents),
        },
        "summary_note": reason,
    }
    return candidate


def _build_summary(candidates: list[dict[str, Any]], gate: dict[str, Any], workflow_state: dict[str, Any]) -> dict[str, Any]:
    counts = {"继续看": 0, "试做": 0, "观察": 0, "先放弃": 0}
    for candidate in candidates:
        status = str(candidate.get("status") or "")
        if status in counts:
            counts[status] += 1
    gaps = _unique_any(gate.get("data_gaps", []), [candidate.get("data_gaps", []) for candidate in candidates])
    return {
        "total_candidates": len(candidates),
        "continue_count": counts["继续看"],
        "trial_count": counts["试做"],
        "watch_count": counts["观察"],
        "drop_count": counts["先放弃"],
        "key_gaps": _missing_data_strings(gaps, []),
        "gate_result": gate.get("gate_result"),
        "workflow_stage": workflow_state.get("stage"),
    }


def _build_source_brief(workflow_state: dict[str, Any], gate: dict[str, Any], packets: dict[str, dict[str, Any]]) -> dict[str, Any]:
    known_inputs = workflow_state.get("known_inputs") if isinstance(workflow_state.get("known_inputs"), dict) else {}
    search_scope = {
        "workflow_id": first_text(workflow_state.get("workflow_id"), workflow_state.get("run_id"), ""),
        "site": first_text(workflow_state.get("site"), known_inputs.get("site"), ""),
        "initial_intent": first_text(workflow_state.get("initial_intent"), ""),
        "direction": first_text(known_inputs.get("direction"), known_inputs.get("scenario"), ""),
        "keyword": first_text(known_inputs.get("keyword"), known_inputs.get("seed_keyword"), ""),
        "asin": first_text(known_inputs.get("asin"), known_inputs.get("reference_asin"), ""),
        "exclusions": _string_list(known_inputs.get("exclusions") or known_inputs.get("constraints")),
        "preferences": known_inputs.get("preferences") or {},
    }
    exclusion_rules = _string_list(gate.get("excluded_directions")) + _string_list(known_inputs.get("exclusions") or known_inputs.get("constraints"))
    return {
        "brief_id": f"brief-{_slugify(search_scope['workflow_id'] or workflow_state.get('initial_intent') or 'p2')}",
        "site": search_scope["site"] or "US",
        "search_scope": search_scope,
        "exclusion_rules": _unique_texts(exclusion_rules),
        "preference_rules": search_scope["preferences"],
        "gate_result": gate.get("gate_result"),
        "source_packets": [
            {
                "name": source_name,
                "path": f"{QUICK_CHECK_DIR}/{config['packet_name']}",
                "packet_id": packet.get("packet_id"),
                "confidence": packet.get("confidence"),
                "execution_mode": packet.get("execution_provenance", {}).get("execution_mode", ""),
                "provenance_note": packet.get("execution_provenance", {}).get("agent_role", ""),
            }
            for source_name, config in SOURCE_CONFIG.items()
            for packet in [packets[source_name]]
        ],
    }


def _write_running_progress(run_path: Path, workflow_state: dict[str, Any], progress_path: Path) -> None:
    progress = _load_progress_template(workflow_state, progress_path)
    progress["current_stage"] = STAGE_ID_CANDIDATE_POOL
    progress["updated_at"] = _now_iso()
    progress["next_action"] = {
        "type": "run_stage",
        "stage_id": STAGE_ID_CANDIDATE_POOL,
        "description": "Generate candidate_pool.json from quick gate and quick packets.",
    }
    stages = deepcopy(progress.get("stages") or {})
    stages.setdefault(
        STAGE_ID_CANDIDATE_POOL,
        {
            "status": "running",
            "attempts": 0,
            "input_artifacts": [
                "workflow_state.json",
                f"{QUICK_CHECK_DIR}/sellersprite_quick_evidence_packet.json",
                f"{QUICK_CHECK_DIR}/sorftime_quick_evidence_packet.json",
                f"{QUICK_CHECK_DIR}/quick_market_gate.json",
            ],
            "output_artifacts": ["candidate_pool.json"],
            "validation_checks": [],
            "last_error": "",
            "next_required_user_action": "",
            "resume_policy": {
                "reuse_existing_artifacts": True,
                "allow_repeat_mcp_call": False,
                "force_refresh": False,
            },
        },
    )
    progress["stages"] = stages
    from packages.research_core.pipeline.quick_market_check import validate_progress as validate_p1_progress

    validate_p1_progress(progress)
    _write_json(progress_path, progress)


def _write_failure_progress(
    run_path: Path,
    *,
    workflow_state: dict[str, Any] | None,
    progress_path: Path,
    error: str,
) -> None:
    now = _now_iso()
    workflow_ref = ""
    if isinstance(workflow_state, dict):
        workflow_ref = first_text(workflow_state.get("workflow_id"), workflow_state.get("run_id"), "")
    progress = _load_progress_template(workflow_state or {}, progress_path)
    progress.update(
        {
            "schema_version": P0_SCHEMA_VERSION,
            "current_stage": STAGE_ID_CANDIDATE_POOL,
            "updated_at": now,
            "global_blockers": [{"stage_id": STAGE_ID_CANDIDATE_POOL, "error": error}],
            "next_action": {
                "type": "fix_stage_error",
                "stage_id": STAGE_ID_CANDIDATE_POOL,
                "description": "Fix P2 candidate-pool inputs or schema, then rerun candidate pool build.",
            },
            "completed_artifacts": [item for item in (progress.get("completed_artifacts") or []) if item != "candidate_pool.json"],
            "workflow_ref": workflow_ref,
            "stages": _failure_stage_states(progress.get("stages"), error),
        }
    )
    try:
        from packages.research_core.pipeline.quick_market_check import validate_progress as validate_p1_progress

        validate_p1_progress(progress)
        _write_json(progress_path, progress)
    except Exception:
        pass


def _failure_stage_states(existing_stages: Any, error: str) -> dict[str, Any]:
    stages = deepcopy(existing_stages) if isinstance(existing_stages, dict) else {}
    stages[STAGE_ID_CANDIDATE_POOL] = {
        "status": "failed",
        "attempts": int((stages.get(STAGE_ID_CANDIDATE_POOL, {}) or {}).get("attempts", 0)) + 1,
        "input_artifacts": [
            "workflow_state.json",
            f"{QUICK_CHECK_DIR}/sellersprite_quick_evidence_packet.json",
            f"{QUICK_CHECK_DIR}/sorftime_quick_evidence_packet.json",
            f"{QUICK_CHECK_DIR}/quick_market_gate.json",
        ],
        "output_artifacts": ["candidate_pool.json"],
        "validation_checks": [{"name": "p2_contract_validation", "pass": False, "detail": error}],
        "last_error": error,
        "next_required_user_action": "",
        "resume_policy": {
            "reuse_existing_artifacts": True,
            "allow_repeat_mcp_call": False,
            "force_refresh": False,
        },
    }
    return stages


def _progress_next_action(pool_status: str) -> dict[str, str]:
    if pool_status == "ready_for_route_matrix":
        return {
            "type": "ready_for_p3",
            "stage_id": "stage_5_route_matrix",
            "description": "candidate_pool.json 已就绪，等待明确 P3 路线矩阵确认指令。",
        }
    if pool_status == "needs_user_review":
        return {
            "type": "needs_user",
            "stage_id": STAGE_ID_CANDIDATE_POOL,
            "description": "候选池已生成但仍需用户确认缺口与路线边界后再进入 P3。",
        }
    return {
        "type": "blocked",
        "stage_id": STAGE_ID_CANDIDATE_POOL,
        "description": "当前方向存在阻塞级缺口，先停止进入 P3 并补齐关键问题。",
    }


def _next_required_user_action(pool_status: str, gate: dict[str, Any]) -> str:
    if pool_status == "ready_for_route_matrix":
        return "等待明确 P3 指令后进入路线矩阵确认。"
    if pool_status == "needs_user_review":
        return "先补齐候选池缺口，或确认是否继续进入 P3。"
    if pool_status == "excluded":
        return first_text(*_string_list(gate.get("gate_reasons"))) or "当前方向建议停止，先切换或补齐阻塞缺口。"
    return ""


def _pool_status_from_gate(gate_result: str) -> str:
    if gate_result == "continue":
        return "ready_for_route_matrix"
    if gate_result == "watch":
        return "needs_user_review"
    return "excluded"


def _readiness_from_gate_result(gate_result: str) -> tuple[str, str, str]:
    if gate_result == "continue":
        return "ready_for_route_matrix", "继续看", "等待 P3 路线矩阵确认。"
    if gate_result == "watch":
        return "needs_user_review", "观察", "先补齐缺口，再决定是否进入 P3。"
    return "excluded", "先放弃", "当前方向建议停止，先切换或补齐阻塞缺口。"


def _candidate_reason(gate_result: str, source_agents: list[str], gate: dict[str, Any]) -> str:
    agents = "、".join(source_agents) if source_agents else "快验数据源"
    if gate_result == "continue":
        return f"{agents} 均给出正向种子，保留为候选方向，待路线矩阵确认。"
    if gate_result == "watch":
        return f"{agents} 保留为待确认候选方向，但仍存在边界或缺口，需要先补齐再进入 P3。"
    return f"{agents} 命中阻塞级缺口，先停止进入 P3。"


def _appearance_reasons(rows: list[dict[str, Any]], gate_result: str) -> list[str]:
    notes: list[str] = []
    for row in rows:
        seed = row.get("source_seed") if isinstance(row.get("source_seed"), dict) else {}
        seed_label = first_text(seed.get("label"), row.get("label"), row.get("candidate_type"))
        source_name = first_text(row.get("source_name"), "")
        notes.append(f"{source_name}:{seed_label}")
    notes.append(f"quick_gate:{gate_result}")
    return _unique_texts(notes)


def _risk_flags(rows: list[dict[str, Any]], gate: dict[str, Any]) -> list[str]:
    flags = []
    for row in rows:
        flags.extend(_string_list(row.get("data_gaps")))
    flags.extend(_string_list(gate.get("gate_reasons")))
    return _unique_texts(flags)


def _competition_notes(gate_result: str, source_agents: list[str]) -> str:
    agents = "、".join(source_agents) if source_agents else "快验数据源"
    if gate_result == "continue":
        return f"{agents} 的候选池边界清晰，可进入下一阶段。"
    if gate_result == "watch":
        return f"{agents} 的候选池边界仍需复核，先补缺口。"
    return f"{agents} 当前存在阻塞级缺口，不进入下一阶段。"


def _candidate_metric_basis(rows: list[dict[str, Any]], run_path: Path) -> dict[str, Any]:
    first_row = rows[0] if rows else {}
    first_packet = first_row.get("source_packet_path", "")
    packet_basis = {}
    if first_packet:
        packet_path = run_path / first_packet
        packet = load_json(packet_path, required=False)
        if isinstance(packet.get("metric_basis"), dict):
            packet_basis = dict(packet["metric_basis"])
    return {
        "marketplace": packet_basis.get("marketplace", "unknown"),
        "currency": packet_basis.get("currency", "unknown"),
        "data_window": packet_basis.get("data_window", "unknown"),
        "aggregation_unit": packet_basis.get("aggregation_unit", "mixed"),
        "sample_scope": packet_basis.get("sample_scope", "quick_pool"),
        "collected_at": packet_basis.get("collected_at", _now_iso()),
    }


def _combine_confidence(values: list[str]) -> str:
    cleaned = [str(value or "medium").strip().lower() for value in values if value]
    if not cleaned:
        return "medium"
    if "low" in cleaned:
        return "low"
    if all(value == "high" for value in cleaned):
        return "high"
    return "medium"


def _gate_support_level(gate_result: str) -> str:
    if gate_result == "continue":
        return "strong"
    if gate_result == "watch":
        return "moderate"
    return "negative"


def _gate_demand_level(gate_result: str) -> str:
    if gate_result == "continue":
        return "strong"
    if gate_result == "watch":
        return "moderate"
    return "negative"


def _combine_support_level(values: list[str], gate_result: str) -> str:
    if gate_result == "excluded":
        return "negative"
    cleaned = [str(value or "unknown").strip().lower() for value in values if value]
    if "strong" in cleaned:
        return "strong"
    if "moderate" in cleaned:
        return "moderate"
    if "weak" in cleaned:
        return "weak"
    if "negative" in cleaned:
        return "negative"
    return "unknown"


def _combine_demand_level(values: list[str], gate_result: str) -> str:
    if gate_result == "excluded":
        return "negative"
    cleaned = [str(value or "unknown").strip().lower() for value in values if value]
    if "strong" in cleaned:
        return "strong"
    if "moderate" in cleaned:
        return "moderate"
    if "weak" in cleaned:
        return "weak"
    if "negative" in cleaned:
        return "negative"
    return "unknown"


def _combine_mixed_pool_level(seed_rows: list[dict[str, Any]], gate_result: str) -> str:
    if gate_result == "excluded":
        return "blocking"
    values = [str(seed_row.get("mixed_pool_level") or "unknown").strip().lower() for seed_row in seed_rows if isinstance(seed_row, dict)]
    if "blocking" in values:
        return "blocking"
    if "material" in values:
        return "material"
    if "mild" in values:
        return "mild"
    if "none" in values:
        return "none"
    return "unknown"


def _combine_price_band_health(seed_rows: list[dict[str, Any]], gate_result: str) -> str:
    if gate_result == "excluded":
        return "blocking"
    values = [str(seed_row.get("price_band_health") or "unknown").strip().lower() for seed_row in seed_rows if isinstance(seed_row, dict)]
    if "blocking" in values:
        return "blocking"
    if "strong" in values:
        return "strong"
    if "moderate" in values:
        return "moderate"
    if "weak" in values:
        return "weak"
    return "unknown"


def _combine_boundary_clarity(seed_rows: list[dict[str, Any]], gate_result: str) -> str:
    if gate_result == "excluded":
        return "blocking"
    values = [str(seed_row.get("category_boundary_clarity") or "unknown").strip().lower() for seed_row in seed_rows if isinstance(seed_row, dict)]
    if "blocking" in values:
        return "blocking"
    if "clear" in values:
        return "clear"
    if "moderate" in values:
        return "moderate"
    if "weak" in values:
        return "weak"
    return "unknown"


def _normalize_seed(seed: Any) -> dict[str, Any]:
    if not isinstance(seed, dict):
        text = first_text(seed, "candidate")
        return {"candidate_type": "route_seed", "label": text}
    candidate_type = _normalize_candidate_type(
        first_text(seed.get("type"), seed.get("candidate_type"), seed.get("seed_type"), "route_seed")
    )
    label = first_text(
        seed.get("label"),
        seed.get("name"),
        seed.get("target"),
        seed.get("keyword"),
        seed.get("asin"),
        seed.get("category"),
        seed.get("route"),
        seed.get("direction"),
        candidate_type,
    )
    return {"candidate_type": candidate_type, "label": label}


def _normalize_candidate_type(raw_type: str) -> str:
    text = str(raw_type or "route_seed").strip().lower()
    mapping = {
        "market_structure": "category",
        "search_demand": "keyword",
        "route": "route_seed",
        "direction": "direction",
        "category": "category",
        "keyword": "keyword",
        "asin": "asin",
        "route_seed": "route_seed",
    }
    return mapping.get(text, "route_seed")


def _normalize_seed_export(seed_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for row in seed_rows:
        rows.append(
            {
                "candidate_type": row.get("candidate_type", "route_seed"),
                "label": row.get("label", ""),
                "source_name": row.get("source_name", ""),
                "source_agent": row.get("source_agent", ""),
                "source_ref": row.get("source_ref", ""),
                "evidence_ref": row.get("evidence_ref", ""),
            }
        )
    return rows


def _candidate_key(candidate_type: str, label: str) -> str:
    return f"{candidate_type}|{_slugify(label)}"


def _slugify(text: Any) -> str:
    slug = re.sub(r"[^0-9A-Za-z]+", "_", public_text(text)).strip("_").lower()
    return slug or "candidate"


def _timestamp_compact(text: str) -> str:
    return re.sub(r"[^0-9]", "", text)[:14] or datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")


def _first_seed_text(value: Any) -> str:
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                return first_text(item.get("label"), item.get("target"), item.get("keyword"), item.get("asin"), item.get("category"))
            text = first_text(item)
            if text:
                return text
    if isinstance(value, dict):
        return first_text(value.get("label"), value.get("target"), value.get("keyword"), value.get("asin"), value.get("category"))
    return first_text(value)


def _string_list(value: Any) -> list[str]:
    rows = []
    for item in as_list(value):
        text = first_text(item)
        if text:
            rows.append(text)
    return rows


def _normalize_any_list(value: Any) -> list[Any]:
    rows: list[Any] = []
    for item in as_list(value):
        if item not in (None, "", []):
            rows.append(item)
    return rows


def _unique_any(*values: Any) -> list[Any]:
    seen: set[str] = set()
    result: list[Any] = []
    for value in values:
        for item in as_list(value):
            key = json.dumps(item, ensure_ascii=False, sort_keys=True, default=str)
            if key in seen:
                continue
            seen.add(key)
            result.append(item)
    return result


def _merge_gate_packet_lists(
    packets: dict[str, dict[str, Any]],
    gate: dict[str, Any],
    field: str,
) -> list[Any]:
    rows: list[Any] = []
    for packet in packets.values():
        rows.extend(_normalize_any_list(packet.get(field)))
    rows.extend(_normalize_any_list(gate.get(field)))
    return _unique_any(rows)


def _missing_data_strings(data_gaps: list[Any], required_deep_dive: list[Any]) -> list[str]:
    rows: list[str] = []
    for item in _unique_any(data_gaps, required_deep_dive):
        text = first_text(
            item.get("type") if isinstance(item, dict) else "",
            item.get("field") if isinstance(item, dict) else "",
            item.get("target") if isinstance(item, dict) else "",
            item.get("reason") if isinstance(item, dict) else "",
            item,
        )
        if text:
            rows.append(text)
    return rows


def _load_json(path: Path, required: bool = True) -> dict[str, Any]:
    data = load_json(path, required=required)
    return data if isinstance(data, dict) else {}


def _load_quick_packet(run_path: Path, source_name: str) -> dict[str, Any]:
    packet_path = run_path / QUICK_CHECK_DIR / SOURCE_CONFIG[source_name]["packet_name"]
    packet = _load_json(packet_path)
    validate_quick_packet(packet, source_name)
    return packet


def _load_quick_gate(run_path: Path) -> dict[str, Any]:
    gate_path = run_path / QUICK_CHECK_DIR / "quick_market_gate.json"
    gate = _load_json(gate_path)
    validate_quick_gate(gate)
    return gate


if __name__ == "__main__":
    raise SystemExit(main())
