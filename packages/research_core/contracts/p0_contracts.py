"""P0 contract helpers for the dual-MCP product research workflow."""

from __future__ import annotations

from typing import Any


P0_SCHEMA_VERSION = "p0-contract-v1"

QUICK_SIGNAL_FIELDS = (
    "support_level",
    "mixed_pool_level",
    "demand_signal_level",
    "price_band_health",
    "category_boundary_clarity",
)

CORE_EVALUATION_DIMENSIONS = {
    "market_demand",
    "competition",
    "price_profit",
    "data_quality",
}

DEFAULT_CONFLICT_THRESHOLDS = {
    "price": 0.10,
    "review_count": 0.15,
    "monthly_units": 0.20,
    "monthly_revenue": 0.20,
    "rating": 0.30,
}

COMPARABLE_BASIS_FIELDS = (
    "marketplace",
    "currency",
    "data_window",
    "aggregation_unit",
    "sample_scope",
)


def decide_quick_gate(
    sellersprite_packet: dict[str, Any],
    sorftime_packet: dict[str, Any],
) -> dict[str, Any]:
    """Apply the P0 Quick Gate rule order to two quick evidence packets."""
    packets = {
        "sellersprite": sellersprite_packet or {},
        "sorftime": sorftime_packet or {},
    }
    rule_hits: list[str] = []
    reasons: list[str] = []

    if any(_blocking_gaps(packet) for packet in packets.values()):
        rule_hits.append("blocking_gaps")
        reasons.append("存在阻塞级数据缺口。")
        result = "stop"
    elif all(_signal(packet, "support_level") == "negative" for packet in packets.values()):
        rule_hits.append("both_negative")
        reasons.append("两个 quick packet 均为 negative。")
        result = "stop"
    elif any(_has_blocking_signal(packet) for packet in packets.values()):
        rule_hits.append("blocking_signal")
        reasons.append("至少一个 quick packet 出现 blocking 级信号。")
        result = "stop"
    elif _both_missing_core_fields(packets):
        rule_hits.append("missing_core_fields")
        reasons.append("两个 quick packet 均缺少核心门控字段。")
        result = "stop"
    elif any(_signal(packet, "mixed_pool_level") == "material" for packet in packets.values()):
        rule_hits.append("material_mixed_pool")
        reasons.append("存在 material 混池风险，进入观察。")
        result = "watch"
    elif any(_price_weak_without_strong_demand(packet) for packet in packets.values()):
        rule_hits.append("weak_price_without_strong_demand")
        reasons.append("价格带健康度偏弱，且需求信号不强。")
        result = "watch"
    elif _one_strong_without_negative(packets) and any(_has_unknown_signal(packet) for packet in packets.values()):
        rule_hits.append("strong_plus_unknown")
        reasons.append("一源强支持，但仍有 unknown 字段。")
        result = "watch"
    elif all(_signal(packet, "support_level") in {"strong", "moderate"} for packet in packets.values()):
        rule_hits.append("both_supported")
        reasons.append("两个 quick packet 均支持继续。")
        result = "continue"
    else:
        rule_hits.append("default_watch")
        reasons.append("未命中 continue 或 stop，默认进入观察。")
        result = "watch"

    return {
        "schema_version": P0_SCHEMA_VERSION,
        "packet_id": "quick_market_gate",
        "stage": "market_quick_check",
        "gate_result": result,
        "support_summary": {
            name: {field: _signal(packet, field) for field in QUICK_SIGNAL_FIELDS}
            for name, packet in packets.items()
        },
        "rule_hits": rule_hits,
        "gate_reasons": reasons,
        "next_action": _quick_gate_next_action(result),
        "evidence_refs": _combined_evidence_refs(packets.values()),
    }


def classify_numeric_conflict(
    metric_name: str,
    primary_value: float | int | None,
    secondary_value: float | int | None,
    primary_basis: dict[str, Any] | None,
    secondary_basis: dict[str, Any] | None,
) -> dict[str, Any]:
    """Classify a numeric conflict after metric_basis comparability is checked."""
    basis_result = metric_basis_comparable(primary_basis or {}, secondary_basis or {})
    if not basis_result["comparable"]:
        return {
            "metric_name": metric_name,
            "severity": "basis_mismatch",
            "status": "needs_normalization",
            "basis_mismatches": basis_result["mismatches"],
            "blocks_delivery": False,
        }
    if primary_value is None or secondary_value is None:
        return {
            "metric_name": metric_name,
            "severity": "blocking",
            "status": "needs_data",
            "basis_mismatches": [],
            "blocks_delivery": True,
        }

    if metric_name == "rating":
        delta = abs(float(primary_value) - float(secondary_value))
        threshold = DEFAULT_CONFLICT_THRESHOLDS["rating"]
        severity = "material" if delta > threshold else "minor"
        diff = {"absolute_delta": round(delta, 4), "threshold": threshold}
    else:
        threshold = DEFAULT_CONFLICT_THRESHOLDS.get(metric_name, 0.20)
        denominator = max(abs(float(primary_value)), 1.0)
        ratio = abs(float(primary_value) - float(secondary_value)) / denominator
        severity = "material" if ratio > threshold else "minor"
        diff = {"relative_delta": round(ratio, 4), "threshold": threshold}

    return {
        "metric_name": metric_name,
        "severity": severity,
        "status": "needs_review" if severity == "material" else "resolved",
        "basis_mismatches": [],
        "diff": diff,
        "blocks_delivery": False,
    }


def metric_basis_comparable(
    primary_basis: dict[str, Any],
    secondary_basis: dict[str, Any],
) -> dict[str, Any]:
    mismatches = []
    for field in COMPARABLE_BASIS_FIELDS:
        if primary_basis.get(field) != secondary_basis.get(field):
            mismatches.append(
                {
                    "field": field,
                    "primary": primary_basis.get(field),
                    "secondary": secondary_basis.get(field),
                }
            )
    return {"comparable": not mismatches, "mismatches": mismatches}


def summarize_evaluation_constraints(
    evaluation_summary: dict[str, Any],
) -> dict[str, Any]:
    """Convert evaluation_summary into hard constraints for final judgment."""
    dimension_results = evaluation_summary.get("dimension_results") or {}
    blocked_dimensions = set(evaluation_summary.get("blocked_dimensions") or [])
    low_confidence_dimensions = set(evaluation_summary.get("low_confidence_dimensions") or [])
    blockers: list[str] = []

    for dimension, result in dimension_results.items():
        if not isinstance(result, dict):
            continue
        if result.get("rating") == "blocked":
            blocked_dimensions.add(str(dimension))
        if result.get("confidence") == "low":
            low_confidence_dimensions.add(str(dimension))

    if "data_quality" in blocked_dimensions:
        blockers.append("data_quality blocked")
    core_blocked = blocked_dimensions & CORE_EVALUATION_DIMENSIONS
    if core_blocked:
        blockers.append("core dimension blocked: " + ", ".join(sorted(core_blocked)))

    return {
        "schema_version": P0_SCHEMA_VERSION,
        "blocked_dimensions": sorted(blocked_dimensions),
        "low_confidence_dimensions": sorted(low_confidence_dimensions),
        "operator_judgment_constraints": blockers,
        "recommended_final_verdict_range": ["blocked"] if "data_quality" in blocked_dimensions else ["watch", "no_go"] if core_blocked else ["go", "watch", "no_go"],
        "can_direct_go": not blockers,
    }


def should_reuse_existing_artifacts(
    stage_state: dict[str, Any],
    existing_artifacts: set[str] | None = None,
) -> bool:
    """Return whether a finished stage can be resumed without repeat MCP calls."""
    existing_artifacts = existing_artifacts or set()
    output_artifacts = set(stage_state.get("output_artifacts") or [])
    checks = stage_state.get("validation_checks") or []
    resume_policy = stage_state.get("resume_policy") or {}
    checks_pass = all(bool(check.get("pass")) for check in checks if isinstance(check, dict))
    return (
        stage_state.get("status") == "done"
        and bool(output_artifacts)
        and output_artifacts.issubset(existing_artifacts)
        and checks_pass
        and bool(resume_policy.get("reuse_existing_artifacts", True))
        and not bool(resume_policy.get("force_refresh", False))
    )


def _signal(packet: dict[str, Any], field: str) -> str:
    value = packet.get(field)
    if value is None and isinstance(packet.get("facts"), dict):
        value = packet["facts"].get(field)
    return str(value or "unknown")


def _blocking_gaps(packet: dict[str, Any]) -> list[Any]:
    gaps = packet.get("blocking_gaps")
    if not gaps:
        return []
    if not isinstance(gaps, list):
        return []
    return [gap for gap in gaps if gap]


def _has_blocking_signal(packet: dict[str, Any]) -> bool:
    return any(_signal(packet, field) == "blocking" for field in QUICK_SIGNAL_FIELDS)


def _both_missing_core_fields(packets: dict[str, dict[str, Any]]) -> bool:
    return all(all(_signal(packet, field) == "unknown" for field in QUICK_SIGNAL_FIELDS) for packet in packets.values())


def _has_unknown_signal(packet: dict[str, Any]) -> bool:
    return any(_signal(packet, field) == "unknown" for field in QUICK_SIGNAL_FIELDS)


def _price_weak_without_strong_demand(packet: dict[str, Any]) -> bool:
    return _signal(packet, "price_band_health") == "weak" and _signal(packet, "demand_signal_level") != "strong"


def _one_strong_without_negative(packets: dict[str, dict[str, Any]]) -> bool:
    support_levels = [_signal(packet, "support_level") for packet in packets.values()]
    return "strong" in support_levels and "negative" not in support_levels


def _quick_gate_next_action(gate_result: str) -> str:
    return {
        "continue": "生成候选池和路线矩阵。",
        "watch": "先补边界或关键缺口，再决定是否进入深挖。",
        "stop": "暂停该方向，保留证据包供复盘。",
    }[gate_result]


def _combined_evidence_refs(packets: Any) -> list[str]:
    refs: list[str] = []
    for packet in packets:
        if isinstance(packet, dict):
            refs.extend(str(ref) for ref in packet.get("evidence_refs") or [] if ref)
    return refs
