#!/usr/bin/env python3
"""Build P1 quick market-check artifacts from reusable MCP snapshots."""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any

from packages.research_core.contracts import decide_quick_gate
from packages.research_core.contracts.p0_contracts import P0_SCHEMA_VERSION
from packages.research_core.pipeline._utils import load_json


STAGE_ID_MARKET_QUICK_CHECK = "stage_2_market_quick_check"
STAGE_ID_QUICK_GATE = "stage_3_quick_gate"
SNAPSHOT_DIR = "mcp_snapshots"
QUICK_CHECK_DIR = "quick_check"

SOURCE_CONFIG = {
    "sellersprite": {
        "source_type": "sellersprite_mcp",
        "snapshot_name": "sellersprite_quick_snapshot.json",
        "packet_name": "sellersprite_quick_evidence_packet.json",
        "packet_id": "sellersprite_quick_evidence_packet",
        "agent_role": "SellerSprite 快验",
        "aggregation_unit": "category",
    },
    "sorftime": {
        "source_type": "sorftime_mcp",
        "snapshot_name": "sorftime_quick_snapshot.json",
        "packet_name": "sorftime_quick_evidence_packet.json",
        "packet_id": "sorftime_quick_evidence_packet",
        "agent_role": "Sorftime 快验",
        "aggregation_unit": "keyword",
    },
}

SUPPORT_LEVELS = {"strong", "moderate", "weak", "negative", "unknown"}
MIXED_POOL_LEVELS = {"none", "mild", "material", "blocking", "unknown"}
DEMAND_SIGNAL_LEVELS = {"strong", "moderate", "weak", "negative", "blocking", "unknown"}
PRICE_BAND_HEALTH = {"strong", "moderate", "weak", "blocking", "unknown"}
CATEGORY_BOUNDARY_CLARITY = {"clear", "moderate", "weak", "blocking", "unknown"}
CONFIDENCE_LEVELS = {"high", "medium", "low"}
EXECUTION_MODES = {"real_subagent_spawn", "serial_simulation", "script_generated", "legacy_fallback"}


class P1ContractError(ValueError):
    """Raised when P1 quick market-check artifacts violate the frozen contract."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run P1 dual-MCP quick market check from snapshots.")
    parser.add_argument("run_dir", type=Path, help="Path to runs/<run_id> directory")
    parser.add_argument(
        "--snapshot-source-dir",
        type=Path,
        help="Optional directory containing reusable sellersprite/sorftime quick snapshots.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        run_quick_market_check(args.run_dir, snapshot_source_dir=args.snapshot_source_dir)
    except Exception as exc:  # pragma: no cover - CLI guard
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


def run_quick_market_check(
    run_dir: Path | str,
    *,
    snapshot_source_dir: Path | str | None = None,
) -> dict[str, Path]:
    """Generate P1 quick snapshots, quick packets, quick gate, and progress."""
    run_path = Path(run_dir).expanduser().resolve()
    source_dir = Path(snapshot_source_dir).expanduser().resolve() if snapshot_source_dir else None
    if not run_path.exists():
        raise P1ContractError(f"run_dir not found: {run_path}")

    try:
        workflow_state = load_json(run_path / "workflow_state.json")
        _write_running_progress(run_path, workflow_state)

        snapshots: dict[str, dict[str, Any]] = {}
        packets: dict[str, dict[str, Any]] = {}
        snapshot_paths: dict[str, Path] = {}
        packet_paths: dict[str, Path] = {}

        for source_name in SOURCE_CONFIG:
            snapshot_path = ensure_quick_snapshot(run_path, source_name, source_dir)
            snapshot = load_json(snapshot_path)
            validate_mcp_snapshot(snapshot, source_name)
            snapshots[source_name] = snapshot
            snapshot_paths[source_name] = snapshot_path

        quick_check_dir = run_path / QUICK_CHECK_DIR
        quick_check_dir.mkdir(parents=True, exist_ok=True)
        for source_name, snapshot in snapshots.items():
            packet = build_quick_packet(snapshot, source_name)
            validate_quick_packet(packet, source_name)
            packet_path = quick_check_dir / SOURCE_CONFIG[source_name]["packet_name"]
            _write_json(packet_path, packet)
            packets[source_name] = packet
            packet_paths[source_name] = packet_path

        gate = build_quick_market_gate(
            packets["sellersprite"],
            packets["sorftime"],
        )
        validate_quick_gate(gate)
        gate_path = quick_check_dir / "quick_market_gate.json"
        _write_json(gate_path, gate)

        progress = build_success_progress(
            workflow_state,
            packets,
            gate,
        )
        validate_progress(progress)
        _write_json(run_path / "progress.json", progress)

        return {
            "sellersprite_snapshot": snapshot_paths["sellersprite"],
            "sorftime_snapshot": snapshot_paths["sorftime"],
            "sellersprite_packet": packet_paths["sellersprite"],
            "sorftime_packet": packet_paths["sorftime"],
            "quick_market_gate": gate_path,
            "progress": run_path / "progress.json",
        }
    except Exception as exc:
        _write_failure_progress(run_path, str(exc))
        raise


def ensure_quick_snapshot(
    run_dir: Path,
    source_name: str,
    snapshot_source_dir: Path | None = None,
) -> Path:
    config = SOURCE_CONFIG[source_name]
    target = run_dir / SNAPSHOT_DIR / config["snapshot_name"]
    if target.exists():
        return target
    if snapshot_source_dir:
        source = _find_source_snapshot(snapshot_source_dir, config["snapshot_name"])
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        return target
    raise P1ContractError(f"missing quick snapshot: {target}")


def build_quick_packet(snapshot: dict[str, Any], source_name: str) -> dict[str, Any]:
    config = SOURCE_CONFIG[source_name]
    signals = _extract_quick_signals(snapshot)
    tool_calls = snapshot.get("tool_calls") or []
    data_gaps = _combined_data_gaps(snapshot, signals)
    blocking_gaps = _blocking_gaps(snapshot, data_gaps)
    collected_at = _string_value(snapshot.get("collected_at")) or _now_iso()
    data_window = _string_value(signals.get("data_window") or snapshot.get("data_window")) or "unknown"
    facts = dict(signals.get("facts") or {})
    facts.setdefault("source_snapshot_id", snapshot.get("snapshot_id", ""))
    facts.setdefault("tool_call_statuses", [call.get("status", "unknown") for call in tool_calls if isinstance(call, dict)])

    metric_basis = dict(signals.get("metric_basis") or {})
    metric_basis.setdefault("marketplace", _string_value(snapshot.get("marketplace")) or "unknown")
    metric_basis.setdefault("currency", _string_value(snapshot.get("currency")) or "unknown")
    metric_basis.setdefault("data_window", data_window)
    metric_basis.setdefault("aggregation_unit", config["aggregation_unit"])
    metric_basis.setdefault("sample_scope", _string_value(snapshot.get("sample_scope")) or "quick_probe")
    metric_basis.setdefault("collected_at", collected_at)

    execution_mode = _normalize_execution_mode(snapshot.get("execution_mode") or signals.get("execution_mode"))
    packet = {
        "schema_version": P0_SCHEMA_VERSION,
        "packet_id": config["packet_id"],
        "stage": "market_quick_check",
        "depth": "quick",
        "source_type": config["source_type"],
        "collected_at": collected_at,
        "data_window": data_window,
        "confidence": _normalize_confidence(signals.get("confidence")),
        "support_level": _normalize_signal("support_level", signals.get("support_level")),
        "blocking_gaps": blocking_gaps,
        "mixed_pool_level": _normalize_signal("mixed_pool_level", signals.get("mixed_pool_level")),
        "demand_signal_level": _normalize_signal("demand_signal_level", signals.get("demand_signal_level")),
        "price_band_health": _normalize_signal("price_band_health", signals.get("price_band_health")),
        "category_boundary_clarity": _normalize_signal(
            "category_boundary_clarity",
            signals.get("category_boundary_clarity"),
        ),
        "facts": facts,
        "derived_metrics": dict(signals.get("derived_metrics") or {}),
        "metric_basis": metric_basis,
        "data_gaps": data_gaps,
        "evidence_refs": [
            f"{SNAPSHOT_DIR}/{config['snapshot_name']}#tool_calls[{index}]"
            for index, call in enumerate(tool_calls)
            if isinstance(call, dict)
        ],
        "execution_provenance": {
            "execution_mode": execution_mode,
            "agent_role": config["agent_role"],
            "tool_names": [
                str(call.get("tool_name"))
                for call in tool_calls
                if isinstance(call, dict) and call.get("tool_name")
            ],
            "source_snapshot_paths": [f"{SNAPSHOT_DIR}/{config['snapshot_name']}"],
        },
    }
    if packet["support_level"] == "unknown":
        packet["data_gaps"].append(
            {
                "type": "missing_quick_signal",
                "field": "support_level",
                "impact": "Quick Gate will not treat this source as supporting continue.",
            }
        )
    return packet


def build_quick_market_gate(
    sellersprite_packet: dict[str, Any],
    sorftime_packet: dict[str, Any],
) -> dict[str, Any]:
    gate = decide_quick_gate(sellersprite_packet, sorftime_packet)
    packets = [sellersprite_packet, sorftime_packet]
    gate.update(
        {
            "candidate_seeds": _combined_fact_list(packets, "candidate_seeds"),
            "excluded_directions": _combined_fact_list(packets, "excluded_directions"),
            "required_deep_dive": _combined_fact_list(packets, "required_deep_dive"),
            "data_gaps": _combined_packet_list(packets, "data_gaps"),
            "confidence": _combined_confidence(packets),
            "execution_provenance": {
                "execution_mode": "script_generated",
                "source_packet_paths": [
                    f"{QUICK_CHECK_DIR}/sellersprite_quick_evidence_packet.json",
                    f"{QUICK_CHECK_DIR}/sorftime_quick_evidence_packet.json",
                ],
            },
        }
    )
    return gate


def build_success_progress(
    workflow_state: dict[str, Any],
    packets: dict[str, dict[str, Any]],
    gate: dict[str, Any],
) -> dict[str, Any]:
    now = _now_iso()
    completed = [
        "mcp_snapshots/sellersprite_quick_snapshot.json",
        "mcp_snapshots/sorftime_quick_snapshot.json",
        "quick_check/sellersprite_quick_evidence_packet.json",
        "quick_check/sorftime_quick_evidence_packet.json",
        "quick_check/quick_market_gate.json",
    ]
    next_action = _progress_next_action(gate.get("gate_result"))
    return {
        "schema_version": P0_SCHEMA_VERSION,
        "current_stage": STAGE_ID_QUICK_GATE,
        "updated_at": now,
        "global_blockers": [] if gate.get("gate_result") != "stop" else gate.get("gate_reasons", []),
        "next_action": next_action,
        "completed_artifacts": completed,
        "stages": {
            STAGE_ID_MARKET_QUICK_CHECK: {
                "status": "done",
                "attempts": 1,
                "input_artifacts": ["workflow_state.json"],
                "output_artifacts": completed[:4],
                "validation_checks": [
                    {"name": "snapshot_files_exist", "pass": True, "detail": "Both quick snapshots are reusable."},
                    {"name": "quick_packets_schema", "pass": True, "detail": "Both quick packets satisfy P0 quick packet contract."},
                ],
                "last_error": "",
                "next_required_user_action": "",
                "resume_policy": {
                    "reuse_existing_artifacts": True,
                    "allow_repeat_mcp_call": False,
                    "force_refresh": False,
                },
            },
            STAGE_ID_QUICK_GATE: {
                "status": "done",
                "attempts": 1,
                "input_artifacts": completed[2:4],
                "output_artifacts": completed[4:],
                "validation_checks": [
                    {"name": "quick_gate_schema", "pass": True, "detail": f"gate_result={gate.get('gate_result')}"},
                    {"name": "p2_not_started", "pass": True, "detail": "candidate_pool.json is outside P1 scope."},
                ],
                "last_error": "",
                "next_required_user_action": _next_required_user_action(gate),
                "resume_policy": {
                    "reuse_existing_artifacts": True,
                    "allow_repeat_mcp_call": False,
                    "force_refresh": False,
                },
            },
        },
        "workflow_ref": workflow_state.get("workflow_id") or workflow_state.get("run_id") or "",
    }


def validate_mcp_snapshot(snapshot: dict[str, Any], source_name: str) -> None:
    config = SOURCE_CONFIG[source_name]
    _require_fields(
        snapshot,
        [
            "schema_version",
            "snapshot_id",
            "stage",
            "depth",
            "source_type",
            "marketplace",
            "collected_at",
            "tool_calls",
            "data_gaps",
        ],
        "mcp_snapshot",
    )
    if snapshot.get("stage") != "market_quick_check":
        raise P1ContractError("mcp_snapshot.stage must be market_quick_check")
    if snapshot.get("depth") != "quick":
        raise P1ContractError("mcp_snapshot.depth must be quick")
    if snapshot.get("source_type") != config["source_type"]:
        raise P1ContractError(f"mcp_snapshot.source_type must be {config['source_type']}")
    tool_calls = snapshot.get("tool_calls")
    if not isinstance(tool_calls, list) or not tool_calls:
        raise P1ContractError("mcp_snapshot.tool_calls must be a non-empty list")
    for index, call in enumerate(tool_calls):
        if not isinstance(call, dict):
            raise P1ContractError(f"mcp_snapshot.tool_calls[{index}] must be an object")
        _require_fields(
            call,
            ["call_id", "tool_name", "params", "status", "started_at", "finished_at"],
            f"mcp_snapshot.tool_calls[{index}]",
        )
        if call.get("status") not in {"success", "empty", "error"}:
            raise P1ContractError(f"mcp_snapshot.tool_calls[{index}].status is invalid")


def validate_quick_packet(packet: dict[str, Any], source_name: str) -> None:
    config = SOURCE_CONFIG[source_name]
    _require_fields(
        packet,
        [
            "schema_version",
            "packet_id",
            "stage",
            "depth",
            "source_type",
            "support_level",
            "blocking_gaps",
            "mixed_pool_level",
            "demand_signal_level",
            "price_band_health",
            "category_boundary_clarity",
            "facts",
            "metric_basis",
            "evidence_refs",
            "confidence",
            "data_gaps",
            "execution_provenance",
        ],
        "quick_packet",
    )
    if packet.get("packet_id") != config["packet_id"]:
        raise P1ContractError(f"quick_packet.packet_id must be {config['packet_id']}")
    if packet.get("stage") != "market_quick_check" or packet.get("depth") != "quick":
        raise P1ContractError("quick_packet must be market_quick_check / quick")
    if packet.get("source_type") != config["source_type"]:
        raise P1ContractError(f"quick_packet.source_type must be {config['source_type']}")
    _require_enum(packet.get("support_level"), SUPPORT_LEVELS, "quick_packet.support_level")
    _require_enum(packet.get("mixed_pool_level"), MIXED_POOL_LEVELS, "quick_packet.mixed_pool_level")
    _require_enum(packet.get("demand_signal_level"), DEMAND_SIGNAL_LEVELS, "quick_packet.demand_signal_level")
    _require_enum(packet.get("price_band_health"), PRICE_BAND_HEALTH, "quick_packet.price_band_health")
    _require_enum(
        packet.get("category_boundary_clarity"),
        CATEGORY_BOUNDARY_CLARITY,
        "quick_packet.category_boundary_clarity",
    )
    _require_enum(packet.get("confidence"), CONFIDENCE_LEVELS, "quick_packet.confidence")
    _require_metric_basis(packet.get("metric_basis"))
    if not isinstance(packet.get("evidence_refs"), list) or not all("#" in str(ref) for ref in packet["evidence_refs"]):
        raise P1ContractError("quick_packet.evidence_refs must use path#fragment format")
    provenance = packet.get("execution_provenance")
    if not isinstance(provenance, dict) or provenance.get("execution_mode") not in EXECUTION_MODES:
        raise P1ContractError("quick_packet.execution_provenance.execution_mode is invalid")


def validate_quick_gate(gate: dict[str, Any]) -> None:
    _require_fields(
        gate,
        [
            "schema_version",
            "packet_id",
            "stage",
            "gate_result",
            "support_summary",
            "rule_hits",
            "gate_reasons",
            "next_action",
            "evidence_refs",
        ],
        "quick_gate",
    )
    if gate.get("packet_id") != "quick_market_gate":
        raise P1ContractError("quick_gate.packet_id must be quick_market_gate")
    if gate.get("stage") != "market_quick_check":
        raise P1ContractError("quick_gate.stage must be market_quick_check")
    _require_enum(gate.get("gate_result"), {"continue", "watch", "stop"}, "quick_gate.gate_result")
    summary = gate.get("support_summary")
    if not isinstance(summary, dict) or "sellersprite" not in summary or "sorftime" not in summary:
        raise P1ContractError("quick_gate.support_summary must include sellersprite and sorftime")
    if not isinstance(gate.get("evidence_refs"), list) or not all("#" in str(ref) for ref in gate["evidence_refs"]):
        raise P1ContractError("quick_gate.evidence_refs must use path#fragment format")


def validate_progress(progress: dict[str, Any]) -> None:
    _require_fields(
        progress,
        ["schema_version", "current_stage", "stages", "updated_at", "global_blockers", "next_action", "completed_artifacts"],
        "progress",
    )
    if not isinstance(progress.get("stages"), dict):
        raise P1ContractError("progress.stages must be an object")
    next_action = progress.get("next_action")
    if not isinstance(next_action, dict) or not next_action.get("type") or not next_action.get("description"):
        raise P1ContractError("progress.next_action must include type and description")
    for stage_id, stage in progress["stages"].items():
        if not isinstance(stage, dict):
            raise P1ContractError(f"progress.stages.{stage_id} must be an object")
        _require_fields(
            stage,
            ["status", "attempts", "input_artifacts", "output_artifacts", "validation_checks", "resume_policy"],
            f"progress.stages.{stage_id}",
        )
        _require_enum(
            stage.get("status"),
            {"pending", "running", "done", "blocked", "failed", "needs_user"},
            f"progress.stages.{stage_id}.status",
        )
        policy = stage.get("resume_policy")
        if not isinstance(policy, dict) or "reuse_existing_artifacts" not in policy or "allow_repeat_mcp_call" not in policy:
            raise P1ContractError(f"progress.stages.{stage_id}.resume_policy is incomplete")


def _write_running_progress(run_dir: Path, workflow_state: dict[str, Any]) -> None:
    now = _now_iso()
    progress = {
        "schema_version": P0_SCHEMA_VERSION,
        "current_stage": STAGE_ID_MARKET_QUICK_CHECK,
        "updated_at": now,
        "global_blockers": [],
        "next_action": {
            "type": "run_stage",
            "stage_id": STAGE_ID_MARKET_QUICK_CHECK,
            "description": "Generate or reuse quick MCP snapshots, then build quick packets.",
        },
        "completed_artifacts": [],
        "stages": {
            STAGE_ID_MARKET_QUICK_CHECK: {
                "status": "running",
                "attempts": 1,
                "input_artifacts": ["workflow_state.json"],
                "output_artifacts": [
                    "mcp_snapshots/sellersprite_quick_snapshot.json",
                    "mcp_snapshots/sorftime_quick_snapshot.json",
                    "quick_check/sellersprite_quick_evidence_packet.json",
                    "quick_check/sorftime_quick_evidence_packet.json",
                ],
                "validation_checks": [],
                "last_error": "",
                "next_required_user_action": "",
                "resume_policy": {
                    "reuse_existing_artifacts": True,
                    "allow_repeat_mcp_call": False,
                    "force_refresh": False,
                },
            },
            STAGE_ID_QUICK_GATE: {
                "status": "pending",
                "attempts": 0,
                "input_artifacts": [
                    "quick_check/sellersprite_quick_evidence_packet.json",
                    "quick_check/sorftime_quick_evidence_packet.json",
                ],
                "output_artifacts": ["quick_check/quick_market_gate.json"],
                "validation_checks": [],
                "last_error": "",
                "next_required_user_action": "",
                "resume_policy": {
                    "reuse_existing_artifacts": True,
                    "allow_repeat_mcp_call": False,
                    "force_refresh": False,
                },
            },
        },
        "workflow_ref": workflow_state.get("workflow_id") or workflow_state.get("run_id") or "",
    }
    _write_json(run_dir / "progress.json", progress)


def _write_failure_progress(run_dir: Path, error: str) -> None:
    now = _now_iso()
    progress = {
        "schema_version": P0_SCHEMA_VERSION,
        "current_stage": STAGE_ID_MARKET_QUICK_CHECK,
        "updated_at": now,
        "global_blockers": [{"stage_id": STAGE_ID_MARKET_QUICK_CHECK, "error": error}],
        "next_action": {
            "type": "fix_stage_error",
            "stage_id": STAGE_ID_MARKET_QUICK_CHECK,
            "description": "Fix P1 quick-check inputs or snapshot schema, then rerun market quick check.",
        },
        "completed_artifacts": [],
        "stages": {
            STAGE_ID_MARKET_QUICK_CHECK: {
                "status": "failed",
                "attempts": 1,
                "input_artifacts": ["workflow_state.json"],
                "output_artifacts": [
                    "mcp_snapshots/sellersprite_quick_snapshot.json",
                    "mcp_snapshots/sorftime_quick_snapshot.json",
                    "quick_check/sellersprite_quick_evidence_packet.json",
                    "quick_check/sorftime_quick_evidence_packet.json",
                ],
                "validation_checks": [
                    {"name": "p1_contract_validation", "pass": False, "detail": error},
                ],
                "last_error": error,
                "next_required_user_action": "",
                "resume_policy": {
                    "reuse_existing_artifacts": True,
                    "allow_repeat_mcp_call": False,
                    "force_refresh": False,
                },
            },
            STAGE_ID_QUICK_GATE: {
                "status": "pending",
                "attempts": 0,
                "input_artifacts": [
                    "quick_check/sellersprite_quick_evidence_packet.json",
                    "quick_check/sorftime_quick_evidence_packet.json",
                ],
                "output_artifacts": ["quick_check/quick_market_gate.json"],
                "validation_checks": [],
                "last_error": "",
                "next_required_user_action": "",
                "resume_policy": {
                    "reuse_existing_artifacts": True,
                    "allow_repeat_mcp_call": False,
                    "force_refresh": False,
                },
            },
        },
    }
    try:
        validate_progress(progress)
        _write_json(run_dir / "progress.json", progress)
    except Exception:
        pass


def _find_source_snapshot(source_dir: Path, filename: str) -> Path:
    candidates = [
        source_dir / filename,
        source_dir / SNAPSHOT_DIR / filename,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise P1ContractError(f"source snapshot not found: {filename} under {source_dir}")


def _extract_quick_signals(snapshot: dict[str, Any]) -> dict[str, Any]:
    signals: dict[str, Any] = {}
    for candidate in (snapshot.get("quick_signals"), snapshot.get("normalized_preview")):
        _merge_signals(signals, candidate)
    for call in snapshot.get("tool_calls") or []:
        if isinstance(call, dict):
            _merge_signals(signals, call.get("normalized_preview"))
    return signals


def _merge_signals(target: dict[str, Any], candidate: Any) -> None:
    if not isinstance(candidate, dict):
        return
    if isinstance(candidate.get("quick_signals"), dict):
        candidate = candidate["quick_signals"]
    for key, value in candidate.items():
        if value not in (None, "", []):
            target[key] = value


def _combined_data_gaps(snapshot: dict[str, Any], signals: dict[str, Any]) -> list[Any]:
    gaps: list[Any] = []
    gaps.extend(snapshot.get("data_gaps") or [])
    gaps.extend(signals.get("data_gaps") or [])
    for call in snapshot.get("tool_calls") or []:
        if not isinstance(call, dict):
            continue
        if call.get("status") == "empty":
            gaps.append(
                {
                    "type": "empty_tool_result",
                    "tool_name": call.get("tool_name", ""),
                    "impact": "This source contributes no positive quick evidence from the call.",
                }
            )
        for error in call.get("errors") or []:
            gaps.append(error)
    return gaps


def _blocking_gaps(snapshot: dict[str, Any], data_gaps: list[Any]) -> list[Any]:
    gaps: list[Any] = []
    if snapshot.get("errors"):
        gaps.extend(snapshot.get("errors") or [])
    for call in snapshot.get("tool_calls") or []:
        if isinstance(call, dict) and call.get("status") == "error":
            gaps.append(
                {
                    "type": "tool_call_error",
                    "tool_name": call.get("tool_name", ""),
                    "impact": "Quick packet cannot support continue until this call is fixed.",
                }
            )
    for gap in data_gaps:
        if isinstance(gap, dict) and (gap.get("severity") == "blocking" or gap.get("blocking") is True):
            gaps.append(gap)
    return gaps


def _normalize_signal(field: str, value: Any) -> str:
    raw = str(value or "unknown").strip().lower()
    aliases = {
        "price_band_health": {
            "healthy": "strong",
            "watch": "moderate",
        },
        "category_boundary_clarity": {
            "partial": "moderate",
            "unclear": "weak",
        },
    }
    raw = aliases.get(field, {}).get(raw, raw)
    allowed = {
        "support_level": SUPPORT_LEVELS,
        "mixed_pool_level": MIXED_POOL_LEVELS,
        "demand_signal_level": DEMAND_SIGNAL_LEVELS,
        "price_band_health": PRICE_BAND_HEALTH,
        "category_boundary_clarity": CATEGORY_BOUNDARY_CLARITY,
    }[field]
    return raw if raw in allowed else "unknown"


def _normalize_confidence(value: Any) -> str:
    raw = str(value or "medium").strip().lower()
    return raw if raw in CONFIDENCE_LEVELS else "medium"


def _normalize_execution_mode(value: Any) -> str:
    raw = str(value or "script_generated").strip()
    return raw if raw in EXECUTION_MODES else "script_generated"


def _combined_confidence(packets: list[dict[str, Any]]) -> str:
    levels = [str(packet.get("confidence") or "medium") for packet in packets]
    if "low" in levels:
        return "low"
    if all(level == "high" for level in levels):
        return "high"
    return "medium"


def _combined_fact_list(packets: list[dict[str, Any]], key: str) -> list[Any]:
    rows: list[Any] = []
    for packet in packets:
        facts = packet.get("facts") if isinstance(packet.get("facts"), dict) else {}
        value = facts.get(key)
        if isinstance(value, list):
            rows.extend(value)
        elif value:
            rows.append(value)
    return rows


def _combined_packet_list(packets: list[dict[str, Any]], key: str) -> list[Any]:
    rows: list[Any] = []
    for packet in packets:
        value = packet.get(key)
        if isinstance(value, list):
            rows.extend(value)
        elif value:
            rows.append(value)
    return rows


def _progress_next_action(gate_result: Any) -> dict[str, str]:
    if gate_result == "continue":
        return {
            "type": "ready_for_p2",
            "stage_id": "stage_4_candidate_pool",
            "description": "P1 quick check completed; wait for explicit P2 start before generating candidate_pool.json.",
        }
    if gate_result == "watch":
        return {
            "type": "needs_user",
            "stage_id": STAGE_ID_QUICK_GATE,
            "description": "P1 quick check completed with watch; review boundary gaps before P2.",
        }
    return {
        "type": "stop",
        "stage_id": STAGE_ID_QUICK_GATE,
        "description": "P1 quick check recommends stopping this direction.",
    }


def _next_required_user_action(gate: dict[str, Any]) -> str:
    if gate.get("gate_result") == "watch":
        return "确认是否补边界/关键缺口，或明确允许进入 P2。"
    if gate.get("gate_result") == "continue":
        return "等待明确 P2 指令后再生成候选池。"
    return ""


def _require_fields(data: dict[str, Any], fields: list[str], label: str) -> None:
    if not isinstance(data, dict):
        raise P1ContractError(f"{label} must be an object")
    missing = [field for field in fields if field not in data]
    if missing:
        raise P1ContractError(f"{label} missing required fields: {', '.join(missing)}")


def _require_enum(value: Any, allowed: set[str], path: str) -> None:
    if value not in allowed:
        raise P1ContractError(f"{path} must be one of {', '.join(sorted(allowed))}")


def _require_metric_basis(value: Any) -> None:
    if not isinstance(value, dict):
        raise P1ContractError("quick_packet.metric_basis must be an object")
    _require_fields(
        value,
        ["marketplace", "currency", "data_window", "aggregation_unit", "sample_scope", "collected_at"],
        "quick_packet.metric_basis",
    )
    _require_enum(
        value.get("aggregation_unit"),
        {"asin", "parent_asin", "keyword", "category", "route", "review", "mixed"},
        "quick_packet.metric_basis.aggregation_unit",
    )


def _string_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float, bool)):
        return str(value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
