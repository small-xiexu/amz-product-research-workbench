#!/usr/bin/env python3
"""Build P5 VOC evidence packet and gate — data-organized evidence from review exports.

Responsibility split:
  - Script (this module): data organization, normalization, evidence wrapping.
    Populates review_scope, asin_coverage, mixed_pool_signals, review_quality_gaps,
    confidence, data_gaps. Does NOT do pain point attribution, spec mapping, or
    opportunity analysis.
  - VOC Evidence Agent (separate agent boundary): reads the evidence packet
    skeleton and fills pain_points_by_dimension, unmet_needs,
    differentiation_opportunities with traceable evidence_refs.
  - build_gate(): orchestrator that reads the evidence packet + P4 conflict
    artifacts and produces the rule-based voc_gate.json decision.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from packages.research_core.contracts.validators import ContractValidationError
from packages.research_core.pipeline._utils import as_list, load_json, _run_id, _validate_artifacts
from packages.research_core.pipeline.constants import VOC_MIN_REVIEW_THRESHOLD


P5_SCHEMA_VERSION = "p5-voc-gate-v1"
P5_STAGE_ID = "stage_7_voc_gate"
REVIEW_VOC_DIR = "review_voc"

P5_GATE_INPUT_ARTIFACTS = [
    "workflow_state.json",
    "progress.json",
    "review_voc/review_asin_batch.json",
    "conflict_review/deep_data_completeness_check.json",
    "conflict_review/conflict_resolution_packet.json",
]
P5_GATE_OUTPUT_ARTIFACTS = [
    "review_voc/voc_evidence_packet.json",
    "review_voc/voc_gate.json",
]


class P5GateError(ContractValidationError):
    """Raised when the VOC gate cannot be generated."""


# ── Main entry ─────────────────────────────────────────────────────────

def run_voc_gate(run_dir: Path | str) -> dict[str, Path]:
    """Run full P5-3: generate voc_evidence_packet.json and voc_gate.json.

    review_voc_package.json is optional at this stage — the gate only requires
    review_asin_batch.json. If voc_package is missing, the evidence packet is
    generated as a skeleton and the gate defaults to 'need_more_reviews'.
    """
    run_path = Path(run_dir).expanduser().resolve()
    _validate_inputs(run_path)

    voc_package_path = run_path / REVIEW_VOC_DIR / "review_voc_package.json"
    voc_package = load_json(voc_package_path) if voc_package_path.exists() else {}
    asin_batch = load_json(run_path / REVIEW_VOC_DIR / "review_asin_batch.json")
    completeness = load_json(run_path / "conflict_review" / "deep_data_completeness_check.json")
    conflict = load_json(run_path / "conflict_review" / "conflict_resolution_packet.json")
    workflow_state = load_json(run_path / "workflow_state.json")
    progress = load_json(run_path / "progress.json")

    evidence_packet = build_evidence_packet(voc_package, asin_batch, completeness, conflict, workflow_state, run_path)
    gate = build_gate(evidence_packet, voc_package, asin_batch, completeness, conflict)

    output_dir = run_path / REVIEW_VOC_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    evidence_path = output_dir / "voc_evidence_packet.json"
    evidence_path.write_text(json.dumps(evidence_packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    gate_path = output_dir / "voc_gate.json"
    gate_path.write_text(json.dumps(gate, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    updated_progress = _update_progress(progress, evidence_packet, gate, run_path)
    progress_path = run_path / "progress.json"
    progress_path.write_text(json.dumps(updated_progress, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return {
        "evidence_packet": evidence_path,
        "gate": gate_path,
        "progress": progress_path,
    }


# ── Evidence Packet Builder ────────────────────────────────────────────

def build_evidence_packet(
    voc_package: dict[str, Any],
    asin_batch: dict[str, Any],
    completeness: dict[str, Any],
    conflict: dict[str, Any],
    workflow_state: dict[str, Any],
    run_path: Path,
) -> dict[str, Any]:
    """Build a structured voc_evidence_packet skeleton from data artifacts.

    This function handles data organization only: review_scope, asin_coverage,
    mixed_pool_signals, review_quality_gaps, confidence. Pain point attribution,
    spec mapping, and opportunity analysis are left to the VOC Evidence Agent.
    """
    now = datetime.now(timezone.utc).isoformat()
    run_id = _run_id(workflow_state, run_path)
    normalized = list(voc_package.get("normalized_reviews", []))
    stats = voc_package.get("stats", {})
    batch_items = as_list(asin_batch.get("asin_items", []))

    review_scope = _build_review_scope(normalized, stats)
    asin_coverage = _build_asin_coverage(normalized, batch_items)
    route_refs = _collect_route_refs(asin_batch)

    mixed_signals = _build_mixed_signals(normalized, batch_items, run_id)
    quality_gaps = _build_quality_gaps(normalized, batch_items, asin_coverage, completeness, conflict)
    confidence = _assess_confidence(normalized, completeness, conflict)

    input_refs = [
        {"type": "file", "path": "review_voc/review_voc_package.json"},
        {"type": "file", "path": "review_voc/review_asin_batch.json"},
        {"type": "file", "path": "conflict_review/conflict_resolution_packet.json"},
        {"type": "file", "path": "conflict_review/deep_data_completeness_check.json"},
    ]

    return {
        "packet_id": "voc_evidence",
        "packet_version": P5_SCHEMA_VERSION,
        "run_id": run_id,
        "agent_role": "VOC Evidence Agent",
        "source_scope": ["review_plugin_export"],
        "created_at": now,
        "input_refs": input_refs,
        "execution_provenance": {
            "executed_by_agent": False,
            "agent_role": "VOC Evidence Agent",
            "execution_mode": "serial_fallback",
            "subagent_id": "",
            "note": "脚本负责数据组织（review_scope, asin_coverage, mixed_pool_signals, review_quality_gaps, confidence）。痛点归因、规格映射、机会提炼必须由 VOC Evidence Agent 独立完成。当前标记为 serial_fallback 表示尚未 spawn 真实子 Agent。",
        },
        "route_refs": route_refs,
        "review_scope": review_scope,
        "asin_coverage": asin_coverage,
        "pain_points_by_dimension": [],
        "unmet_needs": [],
        "differentiation_opportunities": [],
        "mixed_pool_signals": mixed_signals,
        "review_quality_gaps": quality_gaps,
        "confidence": confidence,
        "data_gaps": [],
        "evidence_refs": [
            "review_voc/review_voc_package.json",
        ],
        "lineage": [],
    }


def _build_review_scope(normalized: list[dict[str, Any]], stats: dict[str, Any]) -> dict[str, Any]:
    dates = [r.get("review_date", "") for r in normalized if r.get("review_date")]
    return {
        "total_reviews": len(normalized),
        "total_asins": stats.get("asin_count", len(set(r.get("asin", "") for r in normalized if r.get("asin")))),
        "low_rating_count": stats.get("low_rating_count", sum(1 for r in normalized if _rating(r) <= 3)),
        "date_range": {"start": min(dates) if dates else "", "end": max(dates) if dates else ""},
        "site": stats.get("primary_entry_site", "US"),
        "review_region_primary": stats.get("primary_review_region", "US"),
    }


def _build_asin_coverage(
    normalized: list[dict[str, Any]],
    batch_items: list[dict[str, Any]],
) -> dict[str, Any]:
    route_reviews: dict[str, list[dict[str, Any]]] = {}
    asin_to_role: dict[str, str] = {}
    asin_to_route: dict[str, str] = {}

    for item in batch_items:
        asin = item.get("asin", "")
        route = item.get("route_ref", "")
        role = item.get("asin_role", "")
        if asin:
            asin_to_role[asin] = role
            asin_to_route[asin] = route

    for r in normalized:
        asin = r.get("asin", "")
        route = asin_to_route.get(asin, "")
        if route:
            route_reviews.setdefault(route, []).append(r)

    all_routes = sorted(set(item.get("route_ref", "") for item in batch_items if item.get("route_ref")))
    by_route = []
    for route in all_routes:
        route_revs = route_reviews.get(route, [])
        low_count = sum(1 for r in route_revs if _rating(r) <= 3)
        by_route.append({
            "route_ref": route,
            "asin_count": len(set(r.get("asin", "") for r in route_revs)),
            "review_count": len(route_revs),
            "low_rating_count": low_count,
            "meets_minimum_threshold": len(route_revs) >= VOC_MIN_REVIEW_THRESHOLD,
        })

    by_role: dict[str, dict[str, int]] = {}
    for r in normalized:
        role = asin_to_role.get(r.get("asin", ""), "")
        if role:
            entry = by_role.setdefault(role, {"asin_count": 0, "review_count": 0})
            entry["review_count"] += 1

    for item in batch_items:
        role = item.get("asin_role", "")
        asin = item.get("asin", "")
        if role and role not in by_role:
            by_role[role] = {"asin_count": 0, "review_count": 0}
        if role and asin and role in by_role:
            covered_asins = set(r.get("asin", "") for r in normalized)
            if asin in covered_asins and by_role[role]["asin_count"] == 0:
                by_role[role]["asin_count"] = 1
            # Recompute asin_count properly
    for role in by_role:
        role_asins = {item.get("asin", "") for item in batch_items if item.get("asin_role") == role}
        covered = {r.get("asin", "") for r in normalized}
        by_role[role]["asin_count"] = len(role_asins & covered)

    all_roles = {"primary_reference", "high_sales_benchmark", "target_price_band_sample",
                 "new_release_sample", "premium_benchmark", "painpoint_reference"}
    covered_roles = set(by_role.keys()) & all_roles
    uncovered_roles = sorted(all_roles - covered_roles)

    return {
        "covered_routes": len(by_route),
        "total_routes": len(all_routes),
        "by_route": by_route,
        "by_asin_role": by_role,
        "uncovered_roles": uncovered_roles,
    }


def _collect_route_refs(asin_batch: dict[str, Any]) -> list[str]:
    routes: set[str] = set()
    for item in as_list(asin_batch.get("asin_items", [])):
        ref = item.get("route_ref", "")
        if ref:
            routes.add(ref)
    return sorted(routes)


def _build_mixed_signals(
    normalized: list[dict[str, Any]],
    batch_items: list[dict[str, Any]],
    run_id: str,
) -> list[dict[str, Any]]:
    """Flag reviews from excluded_reference / mixed-pool ASINs."""
    excluded_asins = {item.get("asin", "") for item in batch_items
                      if item.get("asin_role") in ("excluded_reference",) or item.get("is_mixed_pool_control")}
    if not excluded_asins:
        return []

    mixed_reviews = [r for r in normalized if r.get("asin", "") in excluded_asins]
    if not mixed_reviews:
        return []

    return [{
        "signal": f"{len(mixed_reviews)} 条评论来自 excluded_reference 或混池对照 ASIN",
        "affected_review_count": len(mixed_reviews),
        "affected_asins": sorted(set(r.get("asin", "") for r in mixed_reviews)),
        "assessment": "这些评论已标记排除，不与主推路线混算。如果占比高，需关注混池规模。",
        "evidence_refs": [
            {
                "review_id": r.get("review_id", ""),
                "asin": r.get("asin", ""),
                "rating": r.get("rating"),
                "quote": (r.get("review_text_zh", "") or r.get("review_text", ""))[:200],
                "source_path": "review_voc/review_voc_package.json",
            }
            for r in mixed_reviews[:3]
        ],
    }]


def _build_quality_gaps(
    normalized: list[dict[str, Any]],
    batch_items: list[dict[str, Any]],
    asin_coverage: dict[str, Any],
    completeness: dict[str, Any],
    conflict: dict[str, Any],
) -> list[dict[str, Any]]:
    gaps: list[dict[str, Any]] = []

    if len(normalized) < VOC_MIN_REVIEW_THRESHOLD:
        gaps.append({
            "gap_type": "low_review_count",
            "route_ref": "all",
            "description": f"仅 {len(normalized)} 条评论（最低要求 {VOC_MIN_REVIEW_THRESHOLD} 条），VOC 结论置信度不足。",
            "recommended_action": f"补抓至少 {VOC_MIN_REVIEW_THRESHOLD - len(normalized)} 条评论。",
        })

    low_count = sum(1 for r in normalized if _rating(r) <= 3)
    if low_count < 10 and len(normalized) > 0:
        gaps.append({
            "gap_type": "low_negative_review_count",
            "route_ref": "all",
            "description": f"仅 {low_count} 条低分评论（<=3星），痛点信号可能不足。",
            "recommended_action": f"补抓至少 {10 - low_count} 条低分评论。",
        })

    uncovered = asin_coverage.get("uncovered_roles", [])
    if uncovered:
        gaps.append({
            "gap_type": "uncovered_asin_roles",
            "route_ref": "all",
            "description": f"缺少 ASIN 角色覆盖：{', '.join(uncovered)}",
            "recommended_action": f"补抓 {', '.join(uncovered)} 角色的 ASIN 评论。",
        })

    uncovered_routes = [
        route["route_ref"] for route in asin_coverage.get("by_route", [])
        if route.get("review_count", 0) == 0
    ]
    if uncovered_routes:
        gaps.append({
            "gap_type": "uncovered_routes",
            "route_ref": ", ".join(uncovered_routes),
            "description": f"以下路线无评论覆盖：{', '.join(uncovered_routes)}",
            "recommended_action": f"补抓路线 {', '.join(uncovered_routes)} 的 ASIN 评论。",
        })

    completeness_level = str(completeness.get("completeness_level", "") or "").lower()
    if completeness_level == "blocker":
        gaps.append({
            "gap_type": "p4_completeness_blocker",
            "route_ref": "all",
            "description": "P4 数据完整性为 blocker，VOC 证据包可靠性受影响。",
            "recommended_action": "解决 P4 数据完整性问题后再做 VOC Gate 决策。",
        })

    return gaps


def _assess_confidence(
    normalized: list[dict[str, Any]],
    completeness: dict[str, Any],
    conflict: dict[str, Any],
) -> str:
    completeness_level = str(completeness.get("completeness_level", "") or "").lower()
    conflict_level = str(conflict.get("conflict_level", "") or "").lower()

    if completeness_level == "blocker" or conflict_level == "blocker":
        return "low"
    if len(normalized) < VOC_MIN_REVIEW_THRESHOLD:
        return "low"
    low_count = sum(1 for r in normalized if _rating(r) <= 3)
    if low_count < 10:
        return "medium"
    if len(normalized) >= 100 and low_count >= 20:
        return "high"
    return "medium"


# ── Gate Builder ───────────────────────────────────────────────────────

def build_gate(
    evidence_packet: dict[str, Any],
    voc_package: dict[str, Any],
    asin_batch: dict[str, Any],
    completeness: dict[str, Any],
    conflict: dict[str, Any],
) -> dict[str, Any]:
    """Build voc_gate.json with rule-based decision logic."""
    now = datetime.now(timezone.utc).isoformat()
    run_id = evidence_packet.get("run_id", "")
    normalized = list(voc_package.get("normalized_reviews", []))
    review_scope = evidence_packet.get("review_scope", {})
    asin_coverage = evidence_packet.get("asin_coverage", {})

    conflict_level = str(conflict.get("conflict_level", "none") or "none").lower()
    completeness_level = str(completeness.get("completeness_level", "none") or "none").lower()
    total_reviews = review_scope.get("total_reviews", len(normalized))
    low_rating_count = review_scope.get("low_rating_count", 0)
    all_routes_covered = all(
        route.get("review_count", 0) > 0
        for route in asin_coverage.get("by_route", [])
    )

    # Threshold checks
    min_review_met = total_reviews >= VOC_MIN_REVIEW_THRESHOLD
    low_rating_met = low_rating_count >= 10
    route_coverage_complete = all_routes_covered
    asin_role_coverage_complete = len(asin_coverage.get("uncovered_roles", [])) == 0
    mixed_pool_separated = True  # P5-1 already separates excluded ASINs

    checks = {
        "p4_conflict_level": conflict_level,
        "p4_completeness_level": completeness_level,
        "min_review_threshold_met": min_review_met,
        "low_rating_threshold_met": low_rating_met,
        "route_coverage_complete": route_coverage_complete,
        "asin_role_coverage_complete": asin_role_coverage_complete,
        "mixed_pool_separated": mixed_pool_separated,
    }

    thresholds = {
        "min_total_reviews": VOC_MIN_REVIEW_THRESHOLD,
        "min_low_rating_reviews": 10,
        "current_total_reviews": total_reviews,
        "current_low_rating_reviews": low_rating_count,
    }

    # Inherited warnings from P4
    inherited_warnings = []
    if conflict_level == "warning":
        inherited_warnings.append({
            "source": "conflict_resolution_packet",
            "level": "warning",
            "description": "P4 冲突复核为 warning，VOC Gate 继承此警告。",
            "conflict_details": conflict.get("conflicts", []),
        })

    # Blockers
    blockers = []
    if completeness_level == "blocker":
        blockers.append({
            "source": "deep_data_completeness_check",
            "level": "blocker",
            "description": "P4 数据完整性检查为 blocker，VOC 证据包可靠性不足。",
            "impact": "VOC Gate 决策可能基于不完整数据。",
        })
    if conflict_level == "blocker":
        blockers.append({
            "source": "conflict_resolution_packet",
            "level": "blocker",
            "description": "P4 冲突复核为 blocker，核心数据源之间存在不可调和的分歧。",
            "impact": "VOC 分析无法在冲突解决前给出 continue 决策。",
        })

    # Decision
    decision, decision_reason, required_actions = _decide_gate(
        completeness_level, conflict_level, min_review_met, low_rating_met,
        route_coverage_complete, asin_role_coverage_complete, total_reviews, low_rating_count,
        blockers, inherited_warnings, asin_coverage,
    )

    return {
        "schema_version": P5_SCHEMA_VERSION,
        "gate_id": "voc_gate",
        "run_id": run_id,
        "generated_at": now,
        "input_refs": [
            "review_voc/voc_evidence_packet.json",
            "review_voc/review_voc_package.json",
            "review_voc/review_asin_batch.json",
            "conflict_review/conflict_resolution_packet.json",
            "conflict_review/deep_data_completeness_check.json",
        ],
        "decision": decision,
        "decision_reason": decision_reason,
        "inherited_warnings": inherited_warnings,
        "blockers": blockers,
        "checks": checks,
        "thresholds": thresholds,
        "required_next_actions": required_actions,
        "evidence_refs": [
            "review_voc/voc_evidence_packet.json",
            "conflict_review/conflict_resolution_packet.json",
            "conflict_review/deep_data_completeness_check.json",
        ],
    }


def _decide_gate(
    completeness_level: str,
    conflict_level: str,
    min_review_met: bool,
    low_rating_met: bool,
    route_coverage_complete: bool,
    asin_role_coverage_complete: bool,
    total_reviews: int,
    low_rating_count: int,
    blockers: list[dict[str, Any]],
    inherited_warnings: list[dict[str, Any]],
    asin_coverage: dict[str, Any],
) -> tuple[str, str, list[str]]:
    """Apply decision rules per P5 contract section 5."""
    reasons: list[str] = []
    actions: list[str] = []

    # P4 completeness blocker → stop
    if completeness_level == "blocker":
        reasons.append("P4 数据完整性为 blocker，无法基于不完整数据做 VOC 判断。")
        actions.append("解决 P4 deep_data_completeness_check 中的阻断问题后重新运行 P5 流程。")
        return "stop", "；".join(reasons), actions

    # P4 conflict blocker → stop (not continue, not watch)
    if conflict_level == "blocker":
        reasons.append("P4 冲突复核为 blocker，核心数据源之间存在不可调和的分歧。")
        actions.append("解决 P4 conflict_resolution_packet 中的 blocker 冲突后重新评估。")
        return "stop", "；".join(reasons), actions

    # No reviews at all
    if total_reviews == 0:
        reasons.append("无任何评论数据，无法进行 VOC 分析。")
        actions.append("按 review_asin_batch.json 的 operator_instruction 完成评论导出后重新运行。")
        return "need_more_reviews", "；".join(reasons), actions

    # Insufficient reviews → need_more_reviews
    if not min_review_met:
        reasons.append(f"有效评论仅 {total_reviews} 条（最低要求 {VOC_MIN_REVIEW_THRESHOLD} 条），样本不足以支撑 VOC 结论。")
        actions.append(f"补抓至少 {VOC_MIN_REVIEW_THRESHOLD - total_reviews} 条评论，优先覆盖主推路线的 primary_reference ASIN。")

        uncovered = asin_coverage.get("uncovered_roles", [])
        if uncovered:
            actions.append(f"补抓 ASIN 角色：{', '.join(uncovered)}")
        return "need_more_reviews", "；".join(reasons), actions

    # No route coverage → need_more_reviews
    if not route_coverage_complete:
        uncovered_routes = [
            route["route_ref"] for route in asin_coverage.get("by_route", [])
            if route.get("review_count", 0) == 0
        ]
        reasons.append(f"以下路线无评论覆盖：{', '.join(uncovered_routes)}。")
        actions.append(f"补抓路线 {', '.join(uncovered_routes)} 的 ASIN 评论。")
        return "need_more_reviews", "；".join(reasons), actions

    # Low rating insufficient → at least watch
    if not low_rating_met:
        reasons.append(f"低分评论（<=3星）仅 {low_rating_count} 条（最低要求 10 条），痛点信号可能不足。")
        actions.append(f"补抓至少 {10 - low_rating_count} 条低分评论以增强痛点信号。")

        if conflict_level == "warning":
            reasons.append("P4 冲突复核为 warning，叠加低分样本不足。")
            actions.append("人工复核 P4 冲突项并决定是否可以接受低分样本不足的风险。")
        # Don't return here — continue to check other conditions

    # ASIN role coverage incomplete → watch
    if not asin_role_coverage_complete:
        uncovered = asin_coverage.get("uncovered_roles", [])
        reasons.append(f"ASIN 角色覆盖不完整，缺少：{', '.join(uncovered)}。")
        actions.append(f"补抓 {', '.join(uncovered)} 角色的 ASIN 评论。")

        # If both low rating AND role incomplete → watch (even without P4 warnings)
        if not low_rating_met:
            reasons.append("叠加低分样本不足，风险较高。")
            return "watch", "；".join(reasons), actions

    # P4 conflict warning → warn but can continue
    if conflict_level == "warning":
        reasons.append("P4 冲突复核为 warning，VOC Gate 可继续但需人工复核。")
        actions.append("人工复核 P4 conflict warning 中的冲突项。")
        actions.append("在后续阶段中标注 inherited_warnings。")

    # All good → continue
    if min_review_met and low_rating_met and route_coverage_complete and asin_role_coverage_complete and conflict_level == "none":
        reasons.append(f"VOC 证据充分：{total_reviews} 条评论，{low_rating_count} 条低分评论，路线覆盖完整。")
        reasons.append("P4 无 blocker 或 warning，可进入下一阶段。")
        actions.append("进入 stage_8_evaluation 六维评价阶段。")
        return "continue", "；".join(reasons), actions

    # Mixed signals — if we got here with warnings/incomplete, default to watch
    if conflict_level == "warning" or not low_rating_met or not asin_role_coverage_complete:
        return "watch", "；".join(reasons), actions

    # Fallback
    return "watch", "；".join(reasons) if reasons else "存在未明确的阻断因素，建议 watch。", actions


# ── Progress ───────────────────────────────────────────────────────────

def _update_progress(
    progress: dict[str, Any],
    evidence_packet: dict[str, Any],
    gate: dict[str, Any],
    run_path: Path,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    decision = gate.get("decision", "watch")
    stages = dict(progress.get("stages", {}))
    stage_7 = dict(stages.get(P5_STAGE_ID, {}))
    stage_7["status"] = "done"
    stage_7["updated_at"] = now
    stages[P5_STAGE_ID] = stage_7

    completed = list(progress.get("completed_artifacts", []))
    for artifact in ["review_voc/voc_evidence_packet.json", "review_voc/voc_gate.json"]:
        if artifact not in completed:
            completed.append(artifact)

    next_action: dict[str, Any]
    if decision == "stop":
        next_action = {
            "type": "stop",
            "description": "VOC Gate 判定为 stop，流程终止。需解决阻断条件后重新评估。",
            "stage_id": P5_STAGE_ID,
        }
    elif decision == "need_more_reviews":
        next_action = {
            "type": "need_more_reviews",
            "description": "VOC Gate 判定样本不足，需补抓评论后重新运行 P5-2 和 P5-3。",
            "stage_id": P5_STAGE_ID,
        }
    elif decision == "watch":
        next_action = {
            "type": "proceed_with_warnings",
            "description": "VOC Gate 判定为 watch — 可进入下一阶段但需标注所有警告。",
            "stage_id": P5_STAGE_ID,
        }
    else:
        next_action = {
            "type": "generate_report",
            "description": "VOC Gate 判定为 continue — 进入下一阶段正式报告生成。",
            "stage_id": P5_STAGE_ID,
        }

    return {
        **progress,
        "current_stage": P5_STAGE_ID,
        "stages": stages,
        "completed_artifacts": completed,
        "updated_at": now,
        "next_action": next_action,
    }


# ── Helpers ────────────────────────────────────────────────────────────

def _validate_inputs(run_path: Path) -> None:
    _validate_artifacts(run_path, P5_GATE_INPUT_ARTIFACTS, P5GateError)




def _rating(review: dict[str, Any]) -> float:
    r = review.get("rating")
    if isinstance(r, (int, float)):
        return float(r)
    if isinstance(r, str):
        try:
            return float(r)
        except (ValueError, TypeError):
            pass
    return 0.0


def _extract_chinese_ngrams(text: str, min_len: int = 2, max_len: int = 4) -> list[str]:
    """Extract meaningful Chinese character n-grams from review text.
    This is data-driven frequency analysis — not keyword-rule matching."""
    if not text:
        return []
    # Keep Chinese characters and alphanumeric only
    cleaned = re.sub(r'[^一-鿿\w]', '', text)
    if len(cleaned) < min_len:
        return []

    # Skip common stop characters
    stop_chars = {'的', '了', '是', '我', '不', '在', '有', '和', '就', '都',
                  '也', '很', '个', '这', '那', '但', '与', '或', '及', '之',
                  '而', '且', '其', '为', '以', '到', '从', '对', '被', '把',
                  '让', '要', '会', '能', '可', '可以', '没有', '不是', '一个',
                  '一下', '一些', '一种', '什么', '怎么', '这个', '那个', '还是',
                  '不过', '因为', '所以', '如果', '虽然', '但是', '然后', '而且'}

    ngrams: list[str] = []
    for n in range(min_len, max_len + 1):
        for i in range(len(cleaned) - n + 1):
            gram = cleaned[i:i + n]
            if all(c in stop_chars for c in gram):
                continue
            if len(gram.strip()) < min_len:
                continue
            ngrams.append(gram)

    return ngrams




# ── CLI ────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build P5 VOC evidence packet and gate from review data."
    )
    parser.add_argument("run_dir", help="Path to the run directory.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        outputs = run_voc_gate(args.run_dir)
        evidence = json.loads(outputs["evidence_packet"].read_text(encoding="utf-8"))
        gate = json.loads(outputs["gate"].read_text(encoding="utf-8"))
        print(f"evidence_packet: {outputs['evidence_packet']}")
        print(f"gate: {outputs['gate']}")
        print(f"progress: {outputs['progress']}")
        print(f"decision: {gate['decision']}")
        print(f"reviews: {gate['thresholds'].get('current_total_reviews', 0)}")
        print(f"low_rating: {gate['thresholds'].get('current_low_rating_reviews', 0)}")
    except P5GateError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
