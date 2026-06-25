"""P5 contract validators for VOC Gate stage."""

from __future__ import annotations

from typing import Any

from .validators import ContractValidationError


P5_SCHEMA_VERSION = "p5-voc-gate-v1"
P5_STAGE_ID = "stage_7_voc_gate"
P5_ALLOWED_ASIN_ROLES = {
    "primary_reference",
    "high_sales_benchmark",
    "target_price_band_sample",
    "new_release_sample",
    "premium_benchmark",
    "painpoint_reference",
    "excluded_reference",
}
P5_ALLOWED_GATE_DECISIONS = {"continue", "watch", "stop", "need_more_reviews"}


class P5ContractError(ContractValidationError):
    """Raised when a P5 handoff package misses required structure."""


def validate_review_asin_batch(batch: dict[str, Any]) -> None:
    _require_dict(batch, "review_asin_batch")
    _require_fields(
        batch,
        [
            "schema_version",
            "batch_id",
            "run_id",
            "site",
            "asin_items",
            "route_coverage",
            "operator_instruction",
            "data_gaps",
            "evidence_refs",
        ],
        "review_asin_batch",
    )
    if batch.get("schema_version") != P5_SCHEMA_VERSION:
        raise P5ContractError(f"review_asin_batch.schema_version must be {P5_SCHEMA_VERSION}")
    if batch.get("batch_id") != "review_asin_batch":
        raise P5ContractError("review_asin_batch.batch_id must be review_asin_batch")
    _require_non_empty_text(batch.get("run_id"), "review_asin_batch.run_id")
    _require_non_empty_text(batch.get("site"), "review_asin_batch.site")

    asin_items = _require_list(batch.get("asin_items"), "review_asin_batch.asin_items", min_items=1)
    for index, item in enumerate(asin_items):
        path = f"review_asin_batch.asin_items[{index}]"
        _validate_asin_batch_item(item, path)

    route_coverage = _require_list(batch.get("route_coverage"), "review_asin_batch.route_coverage", min_items=1)
    for index, rc in enumerate(route_coverage):
        path = f"review_asin_batch.route_coverage[{index}]"
        _require_dict(rc, path)
        _require_non_empty_text(rc.get("route_ref"), f"{path}.route_ref")

    _require_dict(batch.get("operator_instruction"), "review_asin_batch.operator_instruction")
    _require_list(batch.get("data_gaps"), "review_asin_batch.data_gaps")
    _require_list(batch.get("evidence_refs"), "review_asin_batch.evidence_refs", min_items=1)

    covered_asins = {item["asin"] for item in asin_items if item.get("asin")}
    if len(covered_asins) != len(asin_items):
        raise P5ContractError("review_asin_batch.asin_items contains duplicate ASINs")


def validate_review_voc_package_p5(voc_package: dict[str, Any]) -> None:
    """Extended validator for P5 VOC package (superset of existing validator)."""
    _require_dict(voc_package, "review_voc_package")
    _require_dict(voc_package.get("metadata"), "review_voc_package.metadata")
    _require_dict(voc_package.get("stats"), "review_voc_package.stats")
    _require_list(voc_package.get("normalized_reviews"), "review_voc_package.normalized_reviews")

    if voc_package.get("schema_version") and voc_package.get("schema_version") != P5_SCHEMA_VERSION:
        raise P5ContractError(f"review_voc_package.schema_version must be {P5_SCHEMA_VERSION}")

    metadata = voc_package["metadata"]
    _require_non_empty_text(metadata.get("run_id"), "review_voc_package.metadata.run_id")

    stats = voc_package["stats"]
    _require_field(stats, "review_count", "review_voc_package.stats")
    _require_field(stats, "asin_count", "review_voc_package.stats")
    _require_list(stats.get("asins", []), "review_voc_package.stats.asins")

    for index, review in enumerate(voc_package.get("normalized_reviews", [])):
        path = f"review_voc_package.normalized_reviews[{index}]"
        _require_dict(review, path)
        if not review.get("review_id") and not review.get("review_text") and not review.get("review_text_zh"):
            raise P5ContractError(f"{path} must have review_id or review_text")


def validate_voc_evidence_packet(packet: dict[str, Any]) -> None:
    _require_dict(packet, "voc_evidence_packet")
    _require_fields(
        packet,
        [
            "packet_id",
            "packet_version",
            "run_id",
            "agent_role",
            "source_scope",
            "input_refs",
            "execution_provenance",
            "route_refs",
            "review_scope",
            "asin_coverage",
            "pain_points_by_dimension",
            "confidence",
            "data_gaps",
            "evidence_refs",
        ],
        "voc_evidence_packet",
    )
    if packet.get("packet_id") != "voc_evidence":
        raise P5ContractError("voc_evidence_packet.packet_id must be voc_evidence")
    _require_non_empty_text(packet.get("run_id"), "voc_evidence_packet.run_id")
    _require_non_empty_text(packet.get("agent_role"), "voc_evidence_packet.agent_role")
    _require_dict(packet.get("execution_provenance"), "voc_evidence_packet.execution_provenance")
    _require_dict(packet.get("review_scope"), "voc_evidence_packet.review_scope")
    _require_dict(packet.get("asin_coverage"), "voc_evidence_packet.asin_coverage")
    _require_list(packet.get("pain_points_by_dimension"), "voc_evidence_packet.pain_points_by_dimension")
    _require_list(packet.get("route_refs"), "voc_evidence_packet.route_refs")
    _require_list(packet.get("input_refs"), "voc_evidence_packet.input_refs", min_items=1)
    _require_list(packet.get("source_scope"), "voc_evidence_packet.source_scope", min_items=1)
    _require_list(packet.get("data_gaps"), "voc_evidence_packet.data_gaps")
    _require_list(packet.get("evidence_refs"), "voc_evidence_packet.evidence_refs")

    confidence = _require_non_empty_text(packet.get("confidence"), "voc_evidence_packet.confidence")
    if confidence not in {"high", "medium", "low"}:
        raise P5ContractError("voc_evidence_packet.confidence must be high, medium, or low")

    for index, pp in enumerate(packet.get("pain_points_by_dimension", [])):
        path = f"voc_evidence_packet.pain_points_by_dimension[{index}]"
        _require_dict(pp, path)
        evidence_refs = _require_list(pp.get("evidence_refs"), f"{path}.evidence_refs", min_items=1)
        for ei, er in enumerate(evidence_refs):
            _require_dict(er, f"{path}.evidence_refs[{ei}]")
            _require_non_empty_text(er.get("review_id"), f"{path}.evidence_refs[{ei}].review_id")


def validate_voc_gate(gate: dict[str, Any]) -> None:
    _require_dict(gate, "voc_gate")
    _require_fields(
        gate,
        [
            "schema_version",
            "gate_id",
            "run_id",
            "decision",
            "decision_reason",
            "checks",
            "thresholds",
            "required_next_actions",
            "evidence_refs",
        ],
        "voc_gate",
    )
    if gate.get("schema_version") != P5_SCHEMA_VERSION:
        raise P5ContractError(f"voc_gate.schema_version must be {P5_SCHEMA_VERSION}")
    if gate.get("gate_id") != "voc_gate":
        raise P5ContractError("voc_gate.gate_id must be voc_gate")
    _require_non_empty_text(gate.get("run_id"), "voc_gate.run_id")

    decision = _require_non_empty_text(gate.get("decision"), "voc_gate.decision")
    if decision not in P5_ALLOWED_GATE_DECISIONS:
        raise P5ContractError(f"voc_gate.decision must be one of: {', '.join(sorted(P5_ALLOWED_GATE_DECISIONS))}")

    _require_non_empty_text(gate.get("decision_reason"), "voc_gate.decision_reason")
    _require_dict(gate.get("checks"), "voc_gate.checks")
    _require_dict(gate.get("thresholds"), "voc_gate.thresholds")
    _require_list(gate.get("required_next_actions"), "voc_gate.required_next_actions", min_items=1)
    _require_list(gate.get("evidence_refs"), "voc_gate.evidence_refs", min_items=1)

    if gate.get("decision") == "continue":
        checks = gate["checks"]
        if checks.get("min_review_threshold_met") is False:
            raise P5ContractError("voc_gate cannot be continue when min_review_threshold_met is false")
        p4_conflict = checks.get("p4_conflict_level", "")
        if p4_conflict == "blocker":
            raise P5ContractError("voc_gate cannot be continue when P4 conflict level is blocker")
        thresholds = gate["thresholds"]
        current = thresholds.get("current_total_reviews", 0)
        minimum = thresholds.get("min_total_reviews", 30)
        if isinstance(current, (int, float)) and isinstance(minimum, (int, float)) and current < minimum:
            raise P5ContractError(f"voc_gate cannot be continue with {current} reviews (minimum {minimum})")

    _require_list(gate.get("inherited_warnings", []), "voc_gate.inherited_warnings")
    _require_list(gate.get("blockers", []), "voc_gate.blockers")


def _validate_asin_batch_item(item: Any, path: str) -> None:
    _require_dict(item, path)
    _require_fields(item, ["asin", "asin_role", "route_ref", "selection_reason", "source", "priority"], path)
    asin = _require_non_empty_text(item.get("asin"), f"{path}.asin")
    if len(asin) < 5:
        raise P5ContractError(f"{path}.asin is too short")
    role = _require_non_empty_text(item.get("asin_role"), f"{path}.asin_role")
    if role not in P5_ALLOWED_ASIN_ROLES:
        raise P5ContractError(f"{path}.asin_role must be one of: {', '.join(sorted(P5_ALLOWED_ASIN_ROLES))}")
    _require_non_empty_text(item.get("route_ref"), f"{path}.route_ref")
    _require_non_empty_text(item.get("selection_reason"), f"{path}.selection_reason")
    _require_non_empty_text(item.get("source"), f"{path}.source")
    if not isinstance(item.get("priority"), (int, float)):
        raise P5ContractError(f"{path}.priority must be a number")


def _require_field(value: dict[str, Any], field: str, path: str) -> None:
    if field not in value:
        raise P5ContractError(f"{path} missing required field: {field}")


def _require_fields(value: dict[str, Any], fields: list[str], path: str) -> None:
    missing = [field for field in fields if field not in value]
    if missing:
        raise P5ContractError(f"{path} missing required fields: {', '.join(missing)}")


def _require_dict(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise P5ContractError(f"{path} must be an object")
    return value


def _require_list(value: Any, path: str, *, min_items: int = 0) -> list[Any]:
    if not isinstance(value, list):
        raise P5ContractError(f"{path} must be a list")
    if len(value) < min_items:
        raise P5ContractError(f"{path} must contain at least {min_items} item(s)")
    return value


def _require_non_empty_text(value: Any, path: str) -> str:
    if value is None:
        raise P5ContractError(f"{path} must not be empty")
    text = str(value).strip()
    if not text:
        raise P5ContractError(f"{path} must not be empty")
    return text
