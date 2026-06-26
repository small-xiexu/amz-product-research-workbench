#!/usr/bin/env python3
"""Build P3 route-matrix confirmation artifacts from candidate pool evidence."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from packages.research_core.contracts import validate_candidate_pool, validate_workflow_state
from packages.research_core.contracts.p0_contracts import P0_SCHEMA_VERSION
from packages.research_core.pipeline._utils import as_list, compact_list, first_dict, first_text, join_text, load_json, numeric_value, public_text, _now_iso, _write_json, _unique_texts
from packages.research_core.pipeline.build_mcp_candidate_pool import QUICK_CHECK_DIR, SOURCE_CONFIG
from packages.research_core.pipeline.quick_market_check import validate_progress, validate_quick_gate, validate_quick_packet


P3_SCHEMA_VERSION = "p3-route-matrix-confirm-v1"
P3_STAGE_ID = "stage_5_route_matrix"
P3_CANDIDATE_STAGE_ID = "stage_4_candidate_pool"
ROUTE_MATRIX_OUTPUT_NAME = "route_matrix_confirm.json"
DATA_COMPLETENESS_OUTPUT_NAME = "data_completeness_check.json"
ALLOWED_DECISIONS = {"confirm", "revise_candidate_pool", "stop"}
COMPLETENESS_LEVELS = ("acceptable", "warning", "blocker")


class P3ContractError(ValueError):
    """Raised when route-matrix confirmation artifacts violate the frozen contract."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build P3 route matrix confirmation artifacts.")
    parser.add_argument("run_dir", type=Path, help="Path to runs/<run_id> directory")
    parser.add_argument("--force-confirm", action="store_true",
                        help="Bypass needs_user_review checks; treat all non-blocker routes as confirmed")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        run_route_matrix_confirmation(args.run_dir, force_confirm=args.force_confirm)
    except Exception as exc:  # pragma: no cover - CLI guard
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


def run_route_matrix_confirmation(run_dir: Path | str, force_confirm: bool = False) -> dict[str, Path]:
    run_path = Path(run_dir).expanduser().resolve()
    if not run_path.exists():
        raise P3ContractError(f"run_dir not found: {run_path}")

    progress_path = run_path / "progress.json"
    candidate_pool_path = run_path / "candidate_pool.json"

    try:
        if not candidate_pool_path.exists():
            raise P3ContractError("candidate_pool.json is required for P3 route matrix confirmation")
        workflow_state = load_json(run_path / "workflow_state.json")
        validate_workflow_state(workflow_state)
        candidate_pool = load_json(candidate_pool_path)
        validate_candidate_pool(candidate_pool)
        progress = load_json(progress_path, required=False)
        quick_packets = _load_quick_packets(run_path)
        quick_gate, quick_gate_present = _load_quick_gate(run_path)

        route_packet, completeness, progress = build_route_matrix_confirmation_bundle(
            run_path,
            workflow_state,
            candidate_pool,
            quick_packets,
            quick_gate,
            quick_gate_present,
            progress,
            force_confirm=force_confirm,
        )
        validate_route_matrix_confirm(route_packet)
        validate_data_completeness_check(completeness)
        validate_progress(progress)

        route_matrix_path = run_path / ROUTE_MATRIX_OUTPUT_NAME
        data_completeness_path = run_path / DATA_COMPLETENESS_OUTPUT_NAME
        _write_json(route_matrix_path, route_packet)
        _write_json(data_completeness_path, completeness)
        _write_json(progress_path, progress)

        return {
            "route_matrix_confirm": route_matrix_path,
            "data_completeness_check": data_completeness_path,
            "progress": progress_path,
        }
    except Exception as exc:
        _write_failure_progress(run_path, progress_path, str(exc))
        raise P3ContractError(str(exc)) from exc


def build_route_matrix_confirm(run_dir: Path | str) -> dict[str, Any]:
    """Return the P3 route-matrix packet from candidate_pool.json."""
    run_path = Path(run_dir).expanduser().resolve()
    candidate_pool_path = run_path / "candidate_pool.json"
    if not candidate_pool_path.exists():
        raise P3ContractError("candidate_pool.json is required for P3 route matrix confirmation")
    workflow_state = load_json(run_path / "workflow_state.json")
    validate_workflow_state(workflow_state)
    candidate_pool = load_json(candidate_pool_path)
    validate_candidate_pool(candidate_pool)
    quick_packets = _load_quick_packets(run_path)
    quick_gate, quick_gate_present = _load_quick_gate(run_path)
    route_packet, _, _ = build_route_matrix_confirmation_bundle(
        run_path,
        workflow_state,
        candidate_pool,
        quick_packets,
        quick_gate,
        quick_gate_present,
        load_json(run_path / "progress.json", required=False),
    )
    return route_packet


def write_route_matrix_confirm(run_dir: Path | str) -> Path:
    outputs = run_route_matrix_confirmation(run_dir)
    return outputs["route_matrix_confirm"]


def build_route_matrix_confirmation_bundle(
    run_path: Path,
    workflow_state: dict[str, Any],
    candidate_pool: dict[str, Any],
    quick_packets: dict[str, dict[str, Any] | None],
    quick_gate: dict[str, Any],
    quick_gate_present: bool,
    progress: dict[str, Any] | None,
    force_confirm: bool = False,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    now = _now_iso()
    progress = _progress_template(workflow_state, progress)
    candidates = [item for item in as_list(candidate_pool.get("candidates")) if isinstance(item, dict)]
    route_options: list[dict[str, Any]] = []
    route_checks: list[dict[str, Any]] = []
    evidence_refs = _unique_texts(
        [
            f"{ROUTE_MATRIX_OUTPUT_NAME}#route_options",
            f"{DATA_COMPLETENESS_OUTPUT_NAME}#route_checks",
            "candidate_pool.json#candidates",
            "candidate_pool.json#evidence_refs",
        ]
    )

    for candidate in candidates:
        route_check = _assess_route_completeness(candidate, candidate_pool, quick_packets, quick_gate, quick_gate_present, force_confirm)
        route_option = _build_route_option(candidate, candidate_pool, route_check)
        route_checks.append(route_check)
        route_options.append(route_option)
        evidence_refs.extend(_collect_refs(route_option.get("evidence_refs")))
        evidence_refs.extend(_collect_refs(route_check.get("evidence_refs")))

    completeness = _build_data_completeness_check(
        run_path,
        workflow_state,
        candidate_pool,
        quick_packets,
        quick_gate,
        quick_gate_present,
        route_checks,
    )
    decision = _decide_route_matrix(candidate_pool, route_checks, completeness, force_confirm)
    selected_routes = [route for route in route_options if route.get("selection_status") == "selected"]
    rejected_routes = [route for route in route_options if route.get("selection_status") != "selected"]
    voc_readiness = _build_voc_readiness(selected_routes, route_checks, decision, completeness)
    decision_reason = _decision_reason(decision, selected_routes, route_checks, completeness)
    required_next_actions = _required_next_actions(decision, selected_routes, route_checks, completeness)

    route_packet = {
        "schema_version": P3_SCHEMA_VERSION,
        "packet_id": "route_matrix_confirm",
        "packet_version": "stage5-route-matrix-confirm-p3-v1",
        "created_at": now,
        "run_id": workflow_state.get("workflow_id") or workflow_state.get("run_id") or run_path.name,
        "workflow_ref": workflow_state.get("workflow_id") or workflow_state.get("run_id") or run_path.name,
        "source_candidate_pool": {
            "path": "candidate_pool.json",
            "pool_status": candidate_pool.get("pool_status", ""),
            "candidate_count": len(candidates),
            "summary": candidate_pool.get("summary") or {},
        },
        "route_options": route_options,
        "route_matrix": route_options,
        "selected_routes": selected_routes,
        "rejected_routes": rejected_routes,
        "selected_route": first_text(*(route.get("route_name") for route in selected_routes)),
        "recommended_mainline": first_text(*(route.get("route_name") for route in selected_routes)),
        "decision": decision,
        "decision_reason": decision_reason,
        "required_next_actions": required_next_actions,
        "evidence_refs": _unique_texts(
            evidence_refs
            + [
                f"{ROUTE_MATRIX_OUTPUT_NAME}#selected_routes",
                f"{ROUTE_MATRIX_OUTPUT_NAME}#rejected_routes",
                f"{DATA_COMPLETENESS_OUTPUT_NAME}#route_checks",
                f"{DATA_COMPLETENESS_OUTPUT_NAME}#overall_level",
                "quick_check/sellersprite_quick_evidence_packet.json#packet",
                "quick_check/sorftime_quick_evidence_packet.json#packet",
                "quick_check/quick_market_gate.json#gate_result",
            ]
        ),
        "voc_readiness": voc_readiness,
        "data_completeness_ref": DATA_COMPLETENESS_OUTPUT_NAME,
        "confirmed_boundary": _build_confirmed_boundary(selected_routes, candidate_pool),
        "category_selection_derivation": _build_category_selection_derivation(workflow_state, candidate_pool, selected_routes, route_checks, completeness),
        "source_refs": _source_refs(candidate_pool, quick_packets),
        "data_boundary": "路线矩阵确认由 P2 候选池和 P1 快验证据生成；若存在 blocker，则先回退候选池或停止。",
    }

    _update_progress(
        progress,
        workflow_state,
        candidate_pool,
        completeness,
        decision,
        route_packet,
        quick_gate,
        now,
    )
    return route_packet, completeness, progress


def validate_route_matrix_confirm(route_packet: dict[str, Any]) -> None:
    required = [
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
    ]
    _require_fields(route_packet, required, "route_matrix_confirm")
    if route_packet.get("packet_id") != "route_matrix_confirm":
        raise P3ContractError("route_matrix_confirm.packet_id must be route_matrix_confirm")
    if route_packet.get("schema_version") != P3_SCHEMA_VERSION:
        raise P3ContractError(f"route_matrix_confirm.schema_version must be {P3_SCHEMA_VERSION}")
    if route_packet.get("decision") not in ALLOWED_DECISIONS:
        raise P3ContractError("route_matrix_confirm.decision is invalid")
    if not isinstance(route_packet.get("route_options"), list) or not route_packet["route_options"]:
        raise P3ContractError("route_matrix_confirm.route_options must not be empty")
    if not isinstance(route_packet.get("evidence_refs"), list) or not route_packet["evidence_refs"]:
        raise P3ContractError("route_matrix_confirm.evidence_refs must not be empty")
    if not isinstance(route_packet.get("voc_readiness"), dict):
        raise P3ContractError("route_matrix_confirm.voc_readiness must be an object")


def validate_data_completeness_check(check: dict[str, Any]) -> None:
    required = [
        "schema_version",
        "packet_id",
        "run_id",
        "source_candidate_pool",
        "overall_level",
        "route_checks",
        "required_next_actions",
        "evidence_refs",
    ]
    _require_fields(check, required, "data_completeness_check")
    if check.get("schema_version") != P3_SCHEMA_VERSION:
        raise P3ContractError(f"data_completeness_check.schema_version must be {P3_SCHEMA_VERSION}")
    if check.get("packet_id") != "data_completeness_check":
        raise P3ContractError("data_completeness_check.packet_id must be data_completeness_check")
    if check.get("overall_level") not in COMPLETENESS_LEVELS:
        raise P3ContractError("data_completeness_check.overall_level is invalid")
    if not isinstance(check.get("route_checks"), list) or not check["route_checks"]:
        raise P3ContractError("data_completeness_check.route_checks must not be empty")
    if not isinstance(check.get("evidence_refs"), list) or not check["evidence_refs"]:
        raise P3ContractError("data_completeness_check.evidence_refs must not be empty")


def _assess_route_completeness(
    candidate: dict[str, Any],
    candidate_pool: dict[str, Any],
    quick_packets: dict[str, dict[str, Any] | None],
    quick_gate: dict[str, Any],
    quick_gate_present: bool,
    force_confirm: bool = False,
) -> dict[str, Any]:
    candidate_id = first_text(candidate.get("candidate_id"), candidate.get("name"))
    route_name = first_text(candidate.get("name"), candidate_id)
    support_level = first_text(candidate.get("support_level"), "unknown")
    demand_signal_level = first_text(candidate.get("demand_signal_level"), "unknown")
    mixed_pool_level = first_text(_nested_lookup(candidate, "competition_structure.mixed_pool_level"), "unknown")
    price_band_health = first_text(_nested_lookup(candidate, "competition_structure.price_band_health"), "unknown")
    category_boundary_clarity = first_text(_nested_lookup(candidate, "competition_structure.category_boundary_clarity"), "unknown")
    readiness_status = first_text(candidate.get("readiness_status"), "needs_user_review")
    candidate_status = first_text(candidate.get("status"), "")
    candidate_pool_status = first_text(candidate_pool.get("pool_status"), "needs_user_review")
    data_gaps = _flatten_list(candidate.get("data_gaps")) + _flatten_list(candidate_pool.get("data_gaps"))
    required_deep_dive = _flatten_list(candidate.get("required_deep_dive")) + _flatten_list(candidate_pool.get("required_deep_dive"))
    evidence_refs = _unique_texts(_flatten_list(candidate.get("evidence_refs")) + _flatten_list(candidate.get("source_refs")))
    packet_refs = _source_packet_refs(candidate)
    route_packet_refs = _quick_packet_refs(quick_packets)
    quick_packet_gaps = _collect_quick_packet_gaps(quick_packets)
    source_support_count = len(
        {
            "sellersprite"
            if "sellersprite_quick_evidence_packet" in ref
            else "sorftime"
            if "sorftime_quick_evidence_packet" in ref
            else "other"
            for ref in packet_refs
        }
        - {"other"}
    )
    source_count = len([packet for packet in quick_packets.values() if packet])
    gap_level = "acceptable"
    gap_reasons: list[str] = []

    if source_count < 2:
        gap_level = "blocker"
        gap_reasons.append("缺少 SellerSprite 或 Sorftime 快验证据。")
    if not evidence_refs:
        gap_level = "blocker"
        gap_reasons.append("candidate_pool.evidence_refs 为空。")
    if candidate_pool_status == "excluded" or candidate_status == "先放弃":
        gap_level = "blocker"
        gap_reasons.append("候选池已被标记为停止。")
    if not quick_gate_present or not first_text(quick_gate.get("gate_result"), ""):
        gap_level = "blocker"
        gap_reasons.append("缺少 quick gate 输入。")
    if source_support_count < 2:
        gap_level = "warning" if gap_level != "blocker" else gap_level
        gap_reasons.append("当前候选路线尚未被 SellerSprite 与 Sorftime 两源同时支撑。")
    if _contains_blocking_gap(data_gaps) or _contains_blocking_gap(quick_packet_gaps) or _contains_blocking_gap(_flatten_list(quick_gate.get("blocking_gaps"))) or _contains_blocking_gap(_flatten_list(quick_gate.get("data_gaps"))):
        gap_level = "blocker"
        gap_reasons.append("存在阻塞级数据缺口。")
    if support_level == "negative" or demand_signal_level == "negative":
        gap_level = "blocker"
        gap_reasons.append("快验支持信号为 negative。")
    if category_boundary_clarity == "blocking" or mixed_pool_level == "blocking":
        gap_level = "blocker"
        gap_reasons.append("路线边界或混池判断为 blocking。")

    if gap_level != "blocker":
        warning_triggers = [
            readiness_status == "needs_user_review",
            candidate_pool_status == "needs_user_review",
            support_level in {"weak", "unknown"},
            demand_signal_level in {"weak", "unknown"},
            category_boundary_clarity in {"weak", "unknown"},
            mixed_pool_level in {"mild", "material", "unknown"},
            bool(data_gaps),
            bool(required_deep_dive),
        ]
        if any(warning_triggers):
            gap_level = "warning"
            if readiness_status == "needs_user_review":
                gap_reasons.append("候选路线仍需用户确认。")
            if bool(data_gaps):
                gap_reasons.append("候选路线存在待补缺口。")
            if mixed_pool_level in {"mild", "material"}:
                gap_reasons.append("混池信号仍需复核。")

    needs_voc_validation = gap_level != "acceptable" or support_level != "strong" or readiness_status != "ready_for_route_matrix"
    route_signal = first_text(candidate.get("summary_note"), candidate.get("reason"), "")
    keyword_signal = first_text(demand_signal_level, candidate.get("demand_evidence", {}).get("confidence"), "")
    next_check = _route_next_check(candidate, gap_level, data_gaps, required_deep_dive)
    price_range = first_text(_nested_lookup(candidate, "competition_structure.price_band"), _route_price_hint(candidate), "待补")

    return {
        "candidate_id": candidate_id,
        "route_id": candidate_id,
        "route_name": route_name,
        "route_type": _route_type_label(candidate.get("candidate_type")),
        "candidate_type": first_text(candidate.get("candidate_type"), "route_seed"),
        "candidate_status": candidate_status,
        "readiness_status": readiness_status,
        "source_support_count": source_support_count,
        "support_level": support_level,
        "demand_signal_level": demand_signal_level,
        "mixed_pool_level": mixed_pool_level,
        "price_band_health": price_band_health,
        "category_boundary_clarity": category_boundary_clarity,
        "confidence": first_text(candidate.get("confidence"), "medium"),
        "gap_level": gap_level,
        "gap_reasons": gap_reasons,
        "requires_voc_validation": needs_voc_validation,
        "source_agents": _flatten_texts(candidate.get("source_agents")),
        "source_refs": _unique_texts(_flatten_list(candidate.get("source_refs")) + packet_refs + route_packet_refs),
        "evidence_refs": _unique_texts(_flatten_list(candidate.get("evidence_refs")) + packet_refs + route_packet_refs),
        "data_gaps": data_gaps,
        "required_deep_dive": required_deep_dive,
        "quick_packet_gaps": quick_packet_gaps,
        "price_range": price_range,
        "market_signal": route_signal,
        "keyword_signal": keyword_signal,
        "voc_signal": "needs_voc_validation" if needs_voc_validation else "light_prepared",
        "role": _route_role(candidate, gap_level, readiness_status),
        "recommended_role": _route_role(candidate, gap_level, readiness_status),
        "selection_status": _selection_status(candidate, gap_level, force_confirm),
        "selection_reason": _selection_reason(candidate, gap_level, gap_reasons),
        "next_check": next_check,
        "top_products": [],
        "route_summary": candidate.get("summary_note") or candidate.get("reason") or "",
    }


def _build_data_completeness_check(
    run_path: Path,
    workflow_state: dict[str, Any],
    candidate_pool: dict[str, Any],
    quick_packets: dict[str, dict[str, Any] | None],
    quick_gate: dict[str, Any],
    quick_gate_present: bool,
    route_checks: list[dict[str, Any]],
) -> dict[str, Any]:
    levels = [str(route.get("gap_level") or "warning") for route in route_checks]
    if "blocker" in levels:
        overall_level = "blocker"
    elif "warning" in levels:
        overall_level = "warning"
    else:
        overall_level = "acceptable"
    summary = {
        "route_count": len(route_checks),
        "selected_count": sum(1 for route in route_checks if route.get("selection_status") == "selected"),
        "warning_count": sum(1 for route in route_checks if route.get("gap_level") == "warning"),
        "blocker_count": sum(1 for route in route_checks if route.get("gap_level") == "blocker"),
        "acceptable_count": sum(1 for route in route_checks if route.get("gap_level") == "acceptable"),
    }
    required_next_actions = _required_next_actions(
        _decide_route_matrix(candidate_pool, route_checks, {"overall_level": overall_level}),
        [],
        route_checks,
        {"overall_level": overall_level},
    )
    evidence_refs = _unique_texts(
        [
            "candidate_pool.json#candidates",
            "quick_check/sellersprite_quick_evidence_packet.json#packet",
            "quick_check/sorftime_quick_evidence_packet.json#packet",
            "quick_check/quick_market_gate.json#gate_result",
            "progress.json#stages.stage_5_route_matrix",
        ]
        + [ref for route in route_checks for ref in _flatten_list(route.get("evidence_refs"))]
    )
    return {
        "schema_version": P3_SCHEMA_VERSION,
        "packet_id": "data_completeness_check",
        "packet_version": "stage5-data-completeness-v1",
        "created_at": _now_iso(),
        "run_id": workflow_state.get("workflow_id") or workflow_state.get("run_id") or run_path.name,
        "workflow_ref": workflow_state.get("workflow_id") or workflow_state.get("run_id") or run_path.name,
        "source_candidate_pool": {
            "path": "candidate_pool.json",
            "pool_status": candidate_pool.get("pool_status", ""),
            "candidate_count": len(as_list(candidate_pool.get("candidates"))),
            "summary": candidate_pool.get("summary") or {},
        },
        "overall_level": overall_level,
        "summary": summary,
        "route_checks": route_checks,
        "required_next_actions": required_next_actions,
        "evidence_refs": evidence_refs,
        "quick_packet_refs": _quick_packet_refs(quick_packets),
        "quick_gate_ref": "quick_check/quick_market_gate.json",
        "quick_gate_present": quick_gate_present,
        "missing_artifacts": _missing_quick_artifacts(quick_packets),
        "data_gaps": _unique_texts(_collect_data_gaps(route_checks) + _collect_quick_packet_gaps(quick_packets)),
        "blocking_gaps": [route.get("gap_reasons") for route in route_checks if route.get("gap_level") == "blocker"],
    }


def _build_voc_readiness(
    selected_routes: list[dict[str, Any]],
    route_checks: list[dict[str, Any]],
    decision: str,
    completeness: dict[str, Any],
) -> dict[str, Any]:
    if decision != "confirm" or not selected_routes:
        return {
            "status": "not_ready",
            "needs_voc_validation": False,
            "routes": [],
            "sample_requirements": [],
            "competitor_scope": [],
            "pain_point_hypotheses": [],
            "notes": "当前阶段只做轻量准备，不进入正式 VOC。",
        }

    routes: list[dict[str, Any]] = []
    competitor_scope: list[str] = []
    hypotheses: list[str] = []
    for route in selected_routes:
        route_name = first_text(route.get("route_name"), route.get("candidate_id"))
        route_type = first_text(route.get("route_type"), route.get("candidate_type"))
        competitor_scope.append(route_name)
        hypotheses.append(route.get("market_signal") or route.get("next_check") or "")
        routes.append(
            {
                "route_id": route.get("route_id"),
                "route_name": route_name,
                "route_type": route_type,
                "needs_voc_validation": True,
                "sample_requirements": [
                    "主推路线代表 ASIN 评论样本",
                    "竞争对照 ASIN 评论样本",
                    "低分评论样本",
                    "场景或形态差异样本",
                ],
                "candidate_count": 1,
                "coverage_note": "仅做轻量准备，不生成正式 VOC 产物。",
            }
        )
    return {
        "status": "light_prepared",
        "needs_voc_validation": True,
        "routes": routes,
        "sample_requirements": [
            "按确认路线准备评论样本，不先生成正式 VOC 包。",
            "优先覆盖主推、竞争对照、低分痛点和边界样本。",
        ],
        "competitor_scope": _unique_texts(competitor_scope),
        "pain_point_hypotheses": _unique_texts(hypotheses),
        "notes": "VOC 仅做后续覆盖准备，不生成正式评论产物。",
    }


def _build_category_selection_derivation(
    workflow_state: dict[str, Any],
    candidate_pool: dict[str, Any],
    selected_routes: list[dict[str, Any]],
    route_checks: list[dict[str, Any]],
    completeness: dict[str, Any],
) -> dict[str, Any]:
    known_inputs = workflow_state.get("known_inputs") if isinstance(workflow_state.get("known_inputs"), dict) else {}
    selected_names = [route.get("route_name") for route in selected_routes if route.get("route_name")]
    rejected_names = [route.get("route_name") for route in route_checks if route.get("gap_level") == "blocker"]
    return {
        "selected_category": first_text(*(selected_names or [candidate_pool.get("source_brief", {}).get("search_scope", {}).get("direction")]), "待确认"),
        "confidence": first_text(candidate_pool.get("confidence"), "medium"),
        "steps": [
            {
                "name": "候选池筛选",
                "evidence": compact_list([
                    candidate_pool.get("summary", {}).get("total_candidates"),
                    candidate_pool.get("pool_status"),
                    known_inputs.get("direction"),
                ]),
                "decision": "先用候选池判断哪些路线值得继续看，再按路线确认进入下一阶段。",
                "lineage": ["candidate_pool.json", "workflow_state.json"],
            },
            {
                "name": "路线完整性",
                "evidence": compact_list([
                    completeness.get("overall_level"),
                    completeness.get("summary", {}).get("blocker_count"),
                    completeness.get("summary", {}).get("warning_count"),
                ]),
                "decision": "存在 blocker 时不确认路线；warning 可确认但需保留后续复核动作。",
                "lineage": ["data_completeness_check.json"],
            },
            {
                "name": "确认路线",
                "evidence": selected_names or ["无确认路线"],
                "decision": "只保留可进入深挖的路线，未确认路线先回退。",
                "lineage": ["route_matrix_confirm.json"],
            },
        ],
        "rejected_alternatives": [
            {
                "name": name,
                "decision": "不进入下一阶段",
                "reason": "路线完整性不足或候选池需要回退。",
            }
            for name in _unique_texts(rejected_names)
        ],
        "disconfirming_evidence": [
            {
                "risk": "候选池无法收敛",
                "would_change_decision_if": "所有候选路线都被标记为 blocker 或 excluded。",
                "next_check": "回补候选池或停止当前方向。",
            },
            {
                "risk": "路线需要 VOC 才能继续判断",
                "would_change_decision_if": "路线虽可确认，但仍缺少评论样本来验证痛点假设。",
                "next_check": "保留 VOC 准备，不提前进入正式 VOC。",
            },
        ],
        "source_refs": ["candidate_pool.json", "data_completeness_check.json"],
    }


def _build_confirmed_boundary(selected_routes: list[dict[str, Any]], candidate_pool: dict[str, Any]) -> dict[str, Any]:
    route_names = [route.get("route_name") for route in selected_routes if route.get("route_name")]
    return {
        "mainline": first_text(*route_names),
        "keep_routes": _unique_texts(route_names),
        "exclude_routes": _unique_texts(
            [
                candidate.get("name")
                for candidate in as_list(candidate_pool.get("candidates"))
                if isinstance(candidate, dict) and candidate.get("name") and candidate.get("name") not in route_names
            ]
        ),
    }


def _decide_route_matrix(
    candidate_pool: dict[str, Any],
    route_checks: list[dict[str, Any]],
    completeness: dict[str, Any],
    force_confirm: bool = False,
) -> str:
    overall_level = first_text(completeness.get("overall_level"), "warning")
    selected = [route for route in route_checks if route.get("selection_status") == "selected"]
    candidate_statuses = [first_text(route.get("candidate_status")) for route in route_checks]
    pool_status = first_text(candidate_pool.get("pool_status"), "needs_user_review")

    if overall_level == "blocker":
        if pool_status == "excluded" or all(status == "先放弃" for status in candidate_statuses):
            return "stop"
        return "revise_candidate_pool"
    if selected:
        return "confirm"
    if force_confirm and pool_status not in ("excluded",):
        if not all(status == "先放弃" for status in candidate_statuses):
            return "confirm"
    if pool_status == "excluded" or not route_checks or all(status == "先放弃" for status in candidate_statuses):
        return "stop"
    return "revise_candidate_pool"


def _decision_reason(
    decision: str,
    selected_routes: list[dict[str, Any]],
    route_checks: list[dict[str, Any]],
    completeness: dict[str, Any],
) -> str:
    if decision == "confirm":
        names = "、".join(route.get("route_name") for route in selected_routes if route.get("route_name")) or "候选路线"
        return f"{names} 的快验证据完整，且没有 blocker，可以进入下一阶段。"
    blocker_count = sum(1 for route in route_checks if route.get("gap_level") == "blocker")
    if decision == "revise_candidate_pool":
        if blocker_count:
            return f"存在 {blocker_count} 个 blocker，当前候选池需要回退补数后再确认。"
        return "当前候选路线还不足以确认，需要回退候选池或继续补证据。"
    return "候选路线全部不成立或已被停止，当前方向不进入下一阶段。"


def _required_next_actions(
    decision: str,
    selected_routes: list[dict[str, Any]],
    route_checks: list[dict[str, Any]],
    completeness: dict[str, Any],
) -> list[str]:
    if decision == "confirm":
        return [
            "进入双 MCP 深挖前，按已确认路线继续补强正式证据包。",
            "VOC 仅做轻量准备，不在本阶段生成正式 VOC 产物。",
        ]
    if decision == "revise_candidate_pool":
        blockers = [route for route in route_checks if route.get("gap_level") == "blocker"]
        if blockers:
            return [
                "先回补缺失的快验或证据引用，再重新生成候选池。",
                "阻塞未清除前，不进入双 MCP 深挖。",
            ]
        return [
            "回退候选池，调整路线边界后再重新确认。",
            "未确认路线不能进入双 MCP 深挖。",
        ]
    return [
        "暂停该方向，保留 route_matrix_confirm / data_completeness_check 供复盘。",
        "切换方向或补齐阻塞问题后再重新开始。",
    ]


def _route_role(candidate: dict[str, Any], gap_level: str, readiness_status: str) -> str:
    if gap_level == "blocker":
        return "排除"
    if readiness_status == "ready_for_route_matrix" and first_text(candidate.get("support_level"), "") in {"strong", "moderate"}:
        return "标准款候选"
    if readiness_status == "needs_user_review":
        return "待确认"
    return "观察"


def _selection_status(candidate: dict[str, Any], gap_level: str, force_confirm: bool = False) -> str:
    if gap_level == "blocker":
        return "rejected"
    if force_confirm:
        # With --force-confirm, treat needs_user_review as ready when support is strong/moderate
        support = first_text(candidate.get("support_level"), "")
        if support in {"strong", "moderate"} and first_text(candidate.get("status"), "") != "先放弃":
            return "selected"
    if first_text(candidate.get("readiness_status"), "") != "ready_for_route_matrix":
        return "rejected"
    if first_text(candidate.get("support_level"), "") not in {"strong", "moderate"}:
        return "rejected"
    if first_text(candidate.get("status"), "") == "先放弃":
        return "rejected"
    return "selected"


def _selection_reason(candidate: dict[str, Any], gap_level: str, gap_reasons: list[str]) -> str:
    if gap_level == "blocker":
        return first_text(*gap_reasons, "存在 blocker，不能进入下一阶段。")
    if first_text(candidate.get("readiness_status"), "") != "ready_for_route_matrix":
        return "候选池仍需用户确认，先回退补证据。"
    if first_text(candidate.get("support_level"), "") not in {"strong", "moderate"}:
        return "快验支持信号不足，先不进入下一阶段。"
    return "路线完整性满足要求，可进入下一阶段。"


def _route_type_label(candidate_type: Any) -> str:
    mapping = {
        "category": "类目路线",
        "keyword": "关键词路线",
        "direction": "方向路线",
        "asin": "ASIN 路线",
        "route_seed": "路线种子",
    }
    return mapping.get(first_text(candidate_type, "route_seed"), "路线种子")


def _route_price_hint(candidate: dict[str, Any]) -> str:
    price_band = _nested_lookup(candidate, "price_band_context.price_band")
    if price_band:
        return first_text(price_band)
    return "待补"


def _route_next_check(candidate: dict[str, Any], gap_level: str, data_gaps: list[Any], required_deep_dive: list[Any]) -> str:
    if gap_level == "blocker":
        return "先补齐 blocker 对应的快验或候选池信息。"
    if first_text(candidate.get("readiness_status"), "") != "ready_for_route_matrix":
        return "先回退候选池，补齐边界与缺口后再确认。"
    if data_gaps:
        return "保留数据缺口并继续观察，不直接进入正式 VOC。"
    if required_deep_dive:
        return "进入下一阶段前，按候选路线补齐深挖计划。"
    return "可进入下一阶段的正式深挖。"


def _build_route_option(
    candidate: dict[str, Any],
    candidate_pool: dict[str, Any],
    route_check: dict[str, Any],
) -> dict[str, Any]:
    route_option = dict(route_check)
    route_option.update(
        {
            "source_candidate_pool": "candidate_pool.json",
            "source_candidate_pool_status": first_text(candidate_pool.get("pool_status"), ""),
            "summary_note": candidate.get("summary_note") or candidate.get("reason") or "",
            "source_refs": _unique_texts(_flatten_list(candidate.get("source_refs"))),
            "evidence_refs": _unique_texts(_flatten_list(candidate.get("evidence_refs"))),
            "route_matrix_ref": f"{ROUTE_MATRIX_OUTPUT_NAME}#route_options",
            "data_completeness_ref": DATA_COMPLETENESS_OUTPUT_NAME,
        }
    )
    return route_option


def _progress_template(workflow_state: dict[str, Any], progress: dict[str, Any] | None) -> dict[str, Any]:
    now = _now_iso()
    if not isinstance(progress, dict) or not progress:
        return {
            "schema_version": P0_SCHEMA_VERSION,
            "current_stage": P3_STAGE_ID,
            "updated_at": now,
            "global_blockers": [],
            "next_action": {
                "type": "run_stage",
                "stage_id": P3_STAGE_ID,
                "description": "Generate route_matrix_confirm.json and data_completeness_check.json from candidate_pool.json.",
            },
            "completed_artifacts": [],
            "stages": {},
            "workflow_ref": workflow_state.get("workflow_id") or workflow_state.get("run_id") or "",
        }
    progress.setdefault("schema_version", P0_SCHEMA_VERSION)
    progress.setdefault("global_blockers", [])
    progress.setdefault("completed_artifacts", [])
    progress.setdefault("stages", {})
    progress.setdefault("next_action", {})
    progress.setdefault("current_stage", P3_STAGE_ID)
    progress.setdefault("updated_at", now)
    progress["workflow_ref"] = progress.get("workflow_ref") or workflow_state.get("workflow_id") or workflow_state.get("run_id") or ""
    return progress


def _update_progress(
    progress: dict[str, Any],
    workflow_state: dict[str, Any],
    candidate_pool: dict[str, Any],
    completeness: dict[str, Any],
    decision: str,
    route_packet: dict[str, Any],
    quick_gate: dict[str, Any],
    now: str,
) -> None:
    stage_4_status = {"confirm": "done", "revise_candidate_pool": "needs_user", "stop": "blocked"}[decision]
    stage_5_status = {"confirm": "done", "revise_candidate_pool": "needs_user", "stop": "blocked"}[decision]
    completed = list(progress.get("completed_artifacts") or [])
    for artifact in (ROUTE_MATRIX_OUTPUT_NAME, DATA_COMPLETENESS_OUTPUT_NAME):
        if artifact not in completed:
            completed.append(artifact)
    if decision == "stop":
        blockers = _collect_blockers(completeness, quick_gate)
    elif decision == "revise_candidate_pool":
        blockers = _collect_blockers(completeness, quick_gate)
    else:
        blockers = []
    progress.update(
        {
            "schema_version": P0_SCHEMA_VERSION,
            "current_stage": P3_STAGE_ID,
            "updated_at": now,
            "global_blockers": blockers,
            "next_action": _next_action(decision, route_packet),
            "completed_artifacts": completed,
            "stages": _merge_stage_states(
                progress.get("stages"),
                candidate_pool,
                completeness,
                decision,
                route_packet,
                quick_gate,
                now,
                stage_4_status,
                stage_5_status,
            ),
        }
    )


def _merge_stage_states(
    existing_stages: Any,
    candidate_pool: dict[str, Any],
    completeness: dict[str, Any],
    decision: str,
    route_packet: dict[str, Any],
    quick_gate: dict[str, Any],
    now: str,
    stage_4_status: str,
    stage_5_status: str,
) -> dict[str, Any]:
    stages = json.loads(json.dumps(existing_stages)) if isinstance(existing_stages, dict) else {}
    stage_4 = dict(stages.get(P3_CANDIDATE_STAGE_ID) or {})
    stage_4.update(
        {
            "status": stage_4_status,
            "attempts": int(stage_4.get("attempts", 0) or 0) + 1,
            "input_artifacts": stage_4.get("input_artifacts")
            or [
                "workflow_state.json",
                "candidate_pool.json",
                "quick_check/sellersprite_quick_evidence_packet.json",
                "quick_check/sorftime_quick_evidence_packet.json",
                "quick_check/quick_market_gate.json",
            ],
            "output_artifacts": stage_4.get("output_artifacts") or ["candidate_pool.json"],
            "validation_checks": stage_4.get("validation_checks")
            or [
                {"name": "candidate_pool_schema", "pass": True, "detail": "candidate_pool.json satisfied the P2 contract."},
            ],
            "last_error": stage_4.get("last_error", ""),
            "next_required_user_action": _stage_4_user_action(decision, completeness),
            "resume_policy": stage_4.get("resume_policy")
            or {
                "reuse_existing_artifacts": True,
                "allow_repeat_mcp_call": False,
                "force_refresh": False,
            },
        }
    )
    stage_5 = {
        "status": stage_5_status,
        "attempts": int((stages.get(P3_STAGE_ID, {}) or {}).get("attempts", 0)) + 1,
        "input_artifacts": [
            "candidate_pool.json",
            "quick_check/sellersprite_quick_evidence_packet.json",
            "quick_check/sorftime_quick_evidence_packet.json",
            "quick_check/quick_market_gate.json",
        ],
        "output_artifacts": [ROUTE_MATRIX_OUTPUT_NAME, DATA_COMPLETENESS_OUTPUT_NAME],
        "validation_checks": _stage_5_checks(route_packet, completeness, decision, quick_gate),
        "last_error": "",
        "next_required_user_action": _stage_5_user_action(decision, route_packet),
        "resume_policy": {
            "reuse_existing_artifacts": True,
            "allow_repeat_mcp_call": False,
            "force_refresh": False,
        },
    }
    stages[P3_CANDIDATE_STAGE_ID] = stage_4
    stages[P3_STAGE_ID] = stage_5
    return stages


def _stage_5_checks(route_packet: dict[str, Any], completeness: dict[str, Any], decision: str, quick_gate: dict[str, Any]) -> list[dict[str, Any]]:
    blocker_exists = completeness.get("overall_level") == "blocker"
    return [
        {
            "name": "route_matrix_schema",
            "pass": route_packet.get("schema_version") == P3_SCHEMA_VERSION and bool(route_packet.get("route_options")),
            "detail": f"decision={decision}",
        },
        {
            "name": "data_completeness_schema",
            "pass": completeness.get("schema_version") == P3_SCHEMA_VERSION and bool(completeness.get("route_checks")),
            "detail": f"overall_level={completeness.get('overall_level')}",
        },
        {
            "name": "no_confirm_with_blocker",
            "pass": not (decision == "confirm" and blocker_exists),
            "detail": "blocker must prevent confirm",
        },
        {
            "name": "quick_gate_consistency",
            "pass": quick_gate.get("gate_result") in {"continue", "watch", "stop"},
            "detail": f"gate_result={quick_gate.get('gate_result')}",
        },
    ]


def _stage_4_user_action(decision: str, completeness: dict[str, Any]) -> str:
    if decision == "confirm":
        return "路线矩阵已确认，可进入下一阶段。"
    if decision == "revise_candidate_pool":
        return "先回退候选池，补齐缺口后重新确认路线矩阵。"
    return "当前方向建议停止，先切换或补齐阻塞问题。"


def _stage_5_user_action(decision: str, route_packet: dict[str, Any]) -> str:
    if decision == "confirm":
        return "等待进入下一阶段的深挖指令。"
    if decision == "revise_candidate_pool":
        return "回退候选池并重新生成路线矩阵确认。"
    return "暂停该方向，等待运营确认是否切换赛道。"


def _next_action(decision: str, route_packet: dict[str, Any]) -> dict[str, str]:
    if decision == "confirm":
        return {
            "type": "ready_for_p4",
            "stage_id": "stage_6_deep_dive",
            "description": "路线矩阵已确认，可进入双 MCP 深挖。",
        }
    if decision == "revise_candidate_pool":
        return {
            "type": "needs_user",
            "stage_id": P3_CANDIDATE_STAGE_ID,
            "description": "路线矩阵仍需回退候选池或补齐证据后再确认。",
        }
    return {
        "type": "blocked",
        "stage_id": P3_STAGE_ID,
        "description": "当前候选路线不成立，先停止进入深挖并保留复盘材料。",
    }


def _collect_blockers(completeness: dict[str, Any], quick_gate: dict[str, Any]) -> list[Any]:
    blockers: list[Any] = []
    if completeness.get("overall_level") == "blocker":
        blockers.append({"type": "data_completeness", "detail": completeness.get("route_checks", [])})
    if not completeness.get("quick_gate_present", True):
        blockers.append({"type": "quick_gate_missing", "detail": "quick_market_gate.json is missing"})
    elif quick_gate.get("gate_result") == "stop":
        blockers.append({"type": "quick_gate_stop", "detail": quick_gate.get("gate_reasons") or []})
    return blockers


def _source_refs(candidate_pool: dict[str, Any], quick_packets: dict[str, dict[str, Any] | None]) -> list[str]:
    refs = [
        "candidate_pool.json",
        "candidate_pool.json#candidates",
        "quick_check/quick_market_gate.json",
    ]
    refs.extend(_quick_packet_refs(quick_packets))
    refs.extend(_flatten_list(candidate_pool.get("evidence_refs")))
    return _unique_texts(refs)


def _load_quick_packets(run_path: Path) -> dict[str, dict[str, Any] | None]:
    packets: dict[str, dict[str, Any] | None] = {}
    for source_name, config in SOURCE_CONFIG.items():
        packet_path = run_path / QUICK_CHECK_DIR / config["packet_name"]
        if not packet_path.exists():
            packets[source_name] = None
            continue
        packet = load_json(packet_path)
        validate_quick_packet(packet, source_name)
        packets[source_name] = packet if isinstance(packet, dict) else None
    return packets


def _load_quick_gate(run_path: Path) -> tuple[dict[str, Any], bool]:
    gate_path = run_path / QUICK_CHECK_DIR / "quick_market_gate.json"
    if not gate_path.exists():
        return {}, False
    gate = load_json(gate_path)
    if isinstance(gate, dict):
        try:
            validate_quick_gate(gate)
        except Exception:
            return gate, True
        return gate, True
    return {}, True


def _quick_packet_refs(quick_packets: dict[str, dict[str, Any] | None]) -> list[str]:
    refs: list[str] = []
    for source_name, config in SOURCE_CONFIG.items():
        if quick_packets.get(source_name):
            refs.append(f"{QUICK_CHECK_DIR}/{config['packet_name']}#packet")
    return refs


def _missing_quick_artifacts(quick_packets: dict[str, dict[str, Any] | None]) -> list[str]:
    missing = []
    for source_name, config in SOURCE_CONFIG.items():
        if not quick_packets.get(source_name):
            missing.append(f"{QUICK_CHECK_DIR}/{config['packet_name']}")
    return missing


def _collect_quick_packet_gaps(quick_packets: dict[str, dict[str, Any] | None]) -> list[Any]:
    gaps: list[Any] = []
    for packet in quick_packets.values():
        if not isinstance(packet, dict):
            continue
        gaps.extend(_flatten_list(packet.get("blocking_gaps")))
        gaps.extend(_flatten_list(packet.get("data_gaps")))
    return _unique_any(gaps)


def _route_packet_refs(candidate: dict[str, Any]) -> list[str]:
    refs = []
    refs.extend(_flatten_list(candidate.get("source_refs")))
    refs.extend(_flatten_list(candidate.get("evidence_refs")))
    return [str(ref) for ref in refs if str(ref).strip()]


def _source_packet_refs(candidate: dict[str, Any]) -> list[str]:
    refs: list[str] = []
    for ref in _route_packet_refs(candidate):
        if "quick_check/" in ref and "#packet" not in ref:
            refs.append(ref)
    return _unique_texts(refs)


def _nested_lookup(data: dict[str, Any], dotted_path: str) -> Any:
    current: Any = data
    for segment in dotted_path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(segment)
    return current


def _flatten_list(value: Any) -> list[Any]:
    result: list[Any] = []
    if isinstance(value, list):
        for item in value:
            result.extend(_flatten_list(item))
        return result
    if value not in (None, "", []):
        result.append(value)
    return result


def _flatten_texts(value: Any) -> list[str]:
    return _unique_texts(_flatten_list(value))


def _collect_data_gaps(route_checks: list[dict[str, Any]]) -> list[str]:
    rows: list[str] = []
    for route in route_checks:
        rows.extend(_flatten_texts(route.get("data_gaps")))
        rows.extend(_flatten_texts(route.get("required_deep_dive")))
        rows.extend(_flatten_texts(route.get("gap_reasons")))
    return _unique_texts(rows)


def _contains_blocking_gap(value: Any) -> bool:
    for item in _flatten_list(value):
        text = public_text(item).lower()
        if not text:
            continue
        if any(token in text for token in ("blocking", "缺失", "缺口", "missing", "stop", "阻塞")):
            return True
        if isinstance(item, dict):
            severity = first_text(item.get("severity"), item.get("level"), item.get("status")).lower()
            if severity in {"blocking", "blocker"}:
                return True
    return False


def _collect_refs(value: Any) -> list[str]:
    return [str(item) for item in _flatten_list(value) if str(item).strip()]


def _unique_any(values: list[Any]) -> list[Any]:
    seen: set[str] = set()
    result: list[Any] = []
    for value in values:
        key = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
        if key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result


def _require_fields(data: dict[str, Any], fields: list[str], name: str) -> None:
    for field in fields:
        if field not in data:
            raise P3ContractError(f"{name}.{field} is required")


def _write_failure_progress(run_path: Path, progress_path: Path, error: str) -> None:
    now = _now_iso()
    workflow_state = load_json(run_path / "workflow_state.json", required=False)
    progress = _progress_template(workflow_state if isinstance(workflow_state, dict) else {}, load_json(progress_path, required=False))
    progress.update(
        {
            "schema_version": P0_SCHEMA_VERSION,
            "current_stage": P3_STAGE_ID,
            "updated_at": now,
            "global_blockers": [{"stage_id": P3_STAGE_ID, "error": error}],
            "next_action": {
                "type": "fix_stage_error",
                "stage_id": P3_STAGE_ID,
                "description": "Fix P3 route matrix inputs or schema, then rerun route matrix confirmation.",
            },
            "stages": {
                **(progress.get("stages") or {}),
                P3_STAGE_ID: {
                    "status": "failed",
                    "attempts": int(((progress.get("stages") or {}).get(P3_STAGE_ID, {}) or {}).get("attempts", 0)) + 1,
                    "input_artifacts": [
                        "candidate_pool.json",
                        "quick_check/sellersprite_quick_evidence_packet.json",
                        "quick_check/sorftime_quick_evidence_packet.json",
                        "quick_check/quick_market_gate.json",
                    ],
                    "output_artifacts": [ROUTE_MATRIX_OUTPUT_NAME, DATA_COMPLETENESS_OUTPUT_NAME],
                    "validation_checks": [{"name": "p3_contract_validation", "pass": False, "detail": error}],
                    "last_error": error,
                    "next_required_user_action": "",
                    "resume_policy": {
                        "reuse_existing_artifacts": True,
                        "allow_repeat_mcp_call": False,
                        "force_refresh": False,
                    },
                },
            },
        }
    )
    try:
        validate_progress(progress)
        _write_json(progress_path, progress)
    except Exception:
        pass


if __name__ == "__main__":
    raise SystemExit(main())
