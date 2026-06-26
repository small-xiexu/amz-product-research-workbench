"""P6 contract validators for Multi-Evaluation stage."""

from __future__ import annotations

from typing import Any

from .validators import (
    ContractValidationError,
    _require_field as _shared_require_field,
    _require_fields as _shared_require_fields,
    _require_dict as _shared_require_dict,
    _require_list as _shared_require_list,
    _require_non_empty_text as _shared_require_non_empty_text,
)


P6_SCHEMA_VERSION = "p6-evaluation-v1"
P6_STAGE_ID = "stage_8_evaluation"
P6_EVALUATION_DIMENSIONS = (
    "market_demand",
    "competition",
    "price_profit",
    "voc_opportunity",
    "risk",
    "data_quality",
)
P6_CORE_DIMENSIONS = frozenset({"market_demand", "competition", "price_profit", "data_quality"})
P6_ALLOWED_RATINGS = frozenset({"strong", "watch", "weak", "blocked"})
P6_ALLOWED_CONFIDENCE = frozenset({"high", "medium", "low"})
P6_ALLOWED_VERDICTS = frozenset({"go", "watch", "no_go", "blocked"})
P6_REQUIRED_EVALUATION_FIELDS = (
    "schema_version",
    "packet_id",
    "stage",
    "score",
    "rating",
    "confidence",
    "key_reasons",
    "risks",
    "required_followups",
    "evidence_refs",
    "execution_provenance",
)
P6_REQUIRED_SUMMARY_FIELDS = (
    "schema_version",
    "packet_id",
    "stage",
    "dimension_results",
    "blocked_dimensions",
    "low_confidence_dimensions",
    "cross_dimension_tensions",
    "operator_judgment_constraints",
    "recommended_final_verdict_range",
)


class P6ContractError(ContractValidationError):
    """Raised when a P6 evaluation or summary misses required structure."""


def validate_evaluation_packet(packet: dict[str, Any], dimension: str) -> None:
    """Validate a single P6 evaluation packet for the given dimension."""
    _require_dict(packet, f"{dimension}_evaluation")
    _require_fields(packet, P6_REQUIRED_EVALUATION_FIELDS, f"{dimension}_evaluation")

    if packet.get("schema_version") != P6_SCHEMA_VERSION:
        raise P6ContractError(
            f"{dimension}_evaluation.schema_version must be {P6_SCHEMA_VERSION}"
        )

    expected_packet_id = f"{dimension}_evaluation"
    if packet.get("packet_id") != expected_packet_id:
        raise P6ContractError(
            f"{dimension}_evaluation.packet_id must be {expected_packet_id}"
        )

    if packet.get("stage") != "evaluation":
        raise P6ContractError(f"{dimension}_evaluation.stage must be 'evaluation'")

    score = packet.get("score")
    if not isinstance(score, (int, float)) or score < 0 or score > 100:
        raise P6ContractError(
            f"{dimension}_evaluation.score must be a number 0-100"
        )

    rating = _require_non_empty_text(packet.get("rating"), f"{dimension}_evaluation.rating")
    if rating not in P6_ALLOWED_RATINGS:
        raise P6ContractError(
            f"{dimension}_evaluation.rating must be one of: {', '.join(sorted(P6_ALLOWED_RATINGS))}"
        )

    confidence = _require_non_empty_text(packet.get("confidence"), f"{dimension}_evaluation.confidence")
    if confidence not in P6_ALLOWED_CONFIDENCE:
        raise P6ContractError(
            f"{dimension}_evaluation.confidence must be one of: {', '.join(sorted(P6_ALLOWED_CONFIDENCE))}"
        )

    _require_list(packet.get("key_reasons"), f"{dimension}_evaluation.key_reasons", min_items=1)
    _require_list(packet.get("risks"), f"{dimension}_evaluation.risks")
    _require_list(packet.get("required_followups"), f"{dimension}_evaluation.required_followups")
    _require_list(packet.get("evidence_refs"), f"{dimension}_evaluation.evidence_refs", min_items=1)

    provenance = _require_dict(packet.get("execution_provenance"), f"{dimension}_evaluation.execution_provenance")
    _require_field(provenance, "executed_by_agent", f"{dimension}_evaluation.execution_provenance")
    _require_field(provenance, "agent_role", f"{dimension}_evaluation.execution_provenance")
    _require_field(provenance, "execution_mode", f"{dimension}_evaluation.execution_provenance")


def validate_evaluation_summary(summary: dict[str, Any]) -> None:
    """Validate the P6 evaluation_summary."""
    _require_dict(summary, "evaluation_summary")
    _require_fields(summary, P6_REQUIRED_SUMMARY_FIELDS, "evaluation_summary")

    if summary.get("schema_version") != P6_SCHEMA_VERSION:
        raise P6ContractError(
            f"evaluation_summary.schema_version must be {P6_SCHEMA_VERSION}"
        )
    if summary.get("packet_id") != "evaluation_summary":
        raise P6ContractError("evaluation_summary.packet_id must be evaluation_summary")
    if summary.get("stage") != "evaluation_summary":
        raise P6ContractError("evaluation_summary.stage must be 'evaluation_summary'")

    dimension_results = _require_dict(summary.get("dimension_results"), "evaluation_summary.dimension_results")
    if not dimension_results:
        raise P6ContractError("evaluation_summary.dimension_results must not be empty")

    expected_dims = set(P6_EVALUATION_DIMENSIONS)
    actual_dims = set(dimension_results.keys())
    missing = expected_dims - actual_dims
    if missing:
        raise P6ContractError(
            f"evaluation_summary.dimension_results missing dimensions: {', '.join(sorted(missing))}"
        )

    for dim, result in dimension_results.items():
        _require_dict(result, f"evaluation_summary.dimension_results.{dim}")
        _require_field(result, "score", f"evaluation_summary.dimension_results.{dim}")
        _require_field(result, "rating", f"evaluation_summary.dimension_results.{dim}")
        _require_field(result, "confidence", f"evaluation_summary.dimension_results.{dim}")

    _require_list(summary.get("blocked_dimensions"), "evaluation_summary.blocked_dimensions")
    _require_list(summary.get("low_confidence_dimensions"), "evaluation_summary.low_confidence_dimensions")
    _require_list(summary.get("cross_dimension_tensions"), "evaluation_summary.cross_dimension_tensions")
    _require_list(summary.get("operator_judgment_constraints"), "evaluation_summary.operator_judgment_constraints", min_items=1)

    verdict_range = _require_list(
        summary.get("recommended_final_verdict_range"),
        "evaluation_summary.recommended_final_verdict_range",
        min_items=1,
    )
    for v in verdict_range:
        if v not in P6_ALLOWED_VERDICTS:
            raise P6ContractError(
                f"evaluation_summary.recommended_final_verdict_range contains invalid verdict: {v}"
            )


def validate_all_evaluations(evaluations: dict[str, dict[str, Any]]) -> None:
    """Validate all 6 evaluation packets are present and individually valid."""
    for dim in P6_EVALUATION_DIMENSIONS:
        packet = evaluations.get(dim)
        if packet is None:
            raise P6ContractError(f"Missing evaluation for dimension: {dim}")
        validate_evaluation_packet(packet, dim)


def _require_field(value: dict[str, Any], field: str, path: str) -> None:
    _shared_require_field(value, field, path, error_cls=P6ContractError)


def _require_fields(value: dict[str, Any], fields: tuple[str, ...], path: str) -> None:
    _shared_require_fields(value, fields, path, error_cls=P6ContractError)


def _require_dict(value: Any, path: str) -> dict[str, Any]:
    return _shared_require_dict(value, path, error_cls=P6ContractError)


def _require_list(value: Any, path: str, *, min_items: int = 0) -> list[Any]:
    return _shared_require_list(value, path, min_items=min_items, error_cls=P6ContractError)


def _require_non_empty_text(value: Any, path: str) -> str:
    return _shared_require_non_empty_text(value, path, error_cls=P6ContractError)
