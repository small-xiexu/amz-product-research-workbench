"""P7 contract validators for integrated operator judgment stage."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .validators import ContractValidationError


P7_SCHEMA_VERSION = "p7-judgment-v2"
P7_STAGE_ID = "stage_9_report"
P7_ALLOWED_VERDICTS = {"go", "watch", "no_go", "blocked"}
P7_ALLOWED_CONFIDENCE = {"high", "medium", "low"}


class P7ContractError(ContractValidationError):
    """Raised when a P7 handoff package misses required structure."""


def _require_field(obj: dict[str, Any], field: str, path: str) -> Any:
    if field not in obj:
        raise P7ContractError(f"{path} missing required field: {field}")
    return obj[field]


def _require_fields(obj: dict[str, Any], fields: list[str], path: str) -> None:
    missing = [f for f in fields if f not in obj]
    if missing:
        raise P7ContractError(f"{path} missing required fields: {', '.join(missing)}")


def _require_dict(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise P7ContractError(f"{path} must be an object")
    return value


def _require_list(value: Any, path: str, *, min_items: int = 0) -> list[Any]:
    if not isinstance(value, list):
        raise P7ContractError(f"{path} must be a list")
    if len(value) < min_items:
        raise P7ContractError(f"{path} must contain at least {min_items} item(s)")
    return value


def _require_non_empty_text(value: Any, path: str) -> str:
    if value is None:
        raise P7ContractError(f"{path} must not be empty")
    text = str(value).strip()
    if not text:
        raise P7ContractError(f"{path} must not be empty")
    return text


def validate_integrated_judgment(packet: dict[str, Any]) -> None:
    _require_dict(packet, "integrated_operator_judgment")
    _require_fields(
        packet,
        [
            "schema_version",
            "packet_id",
            "stage",
            "run_id",
            "final_verdict",
            "verdict_reason",
            "recommended_route",
            "rejected_routes",
            "biggest_opportunity",
            "biggest_risk",
            "required_next_actions",
            "constraints_applied",
            "evidence_refs",
            "confidence",
            "execution_provenance",
            "generated_at",
            # v2 深度运营分析字段
            "route_recommendation",
            "route_tradeoff",
            "competitor_benchmark",
            "competitor_weakness_map",
            "cold_start_estimate",
            "price_band_analysis",
            "voc_to_spec",
            "keyword_strategy",
            "risk_mitigation",
            "validation_roadmap",
        ],
        "integrated_operator_judgment",
    )
    if packet.get("schema_version") != P7_SCHEMA_VERSION:
        raise P7ContractError(
            f"integrated_operator_judgment.schema_version must be {P7_SCHEMA_VERSION}"
        )
    if packet.get("packet_id") != "integrated_operator_judgment":
        raise P7ContractError(
            "integrated_operator_judgment.packet_id must be integrated_operator_judgment"
        )
    if packet.get("stage") != P7_STAGE_ID:
        raise P7ContractError(
            f"integrated_operator_judgment.stage must be {P7_STAGE_ID}"
        )

    _require_non_empty_text(packet.get("run_id"), "integrated_operator_judgment.run_id")
    _require_non_empty_text(packet.get("generated_at"), "integrated_operator_judgment.generated_at")

    verdict = _require_non_empty_text(
        packet.get("final_verdict"), "integrated_operator_judgment.final_verdict"
    )
    if verdict not in P7_ALLOWED_VERDICTS:
        raise P7ContractError(
            f"integrated_operator_judgment.final_verdict must be one of {sorted(P7_ALLOWED_VERDICTS)}"
        )

    _require_non_empty_text(
        packet.get("verdict_reason"), "integrated_operator_judgment.verdict_reason"
    )

    confidence = _require_non_empty_text(
        packet.get("confidence"), "integrated_operator_judgment.confidence"
    )
    if confidence not in P7_ALLOWED_CONFIDENCE:
        raise P7ContractError(
            f"integrated_operator_judgment.confidence must be one of {sorted(P7_ALLOWED_CONFIDENCE)}"
        )

    _require_non_empty_text(
        packet.get("recommended_route") if isinstance(packet.get("recommended_route"), str) else (packet.get("recommended_route") or {}).get("name", ""),
        "integrated_operator_judgment.recommended_route",
    )

    _require_list(
        packet.get("rejected_routes"),
        "integrated_operator_judgment.rejected_routes",
    )
    _require_list(
        packet.get("required_next_actions"),
        "integrated_operator_judgment.required_next_actions",
        min_items=1,
    )
    _require_list(
        packet.get("constraints_applied"),
        "integrated_operator_judgment.constraints_applied",
        min_items=1,
    )
    _require_list(
        packet.get("evidence_refs"),
        "integrated_operator_judgment.evidence_refs",
        min_items=1,
    )

    provenance = _require_dict(
        packet.get("execution_provenance"),
        "integrated_operator_judgment.execution_provenance",
    )
    _require_fields(
        provenance,
        ["executed_by_agent", "agent_role", "execution_mode"],
        "integrated_operator_judgment.execution_provenance",
    )
    if not isinstance(provenance.get("executed_by_agent"), bool):
        raise P7ContractError(
            "integrated_operator_judgment.execution_provenance.executed_by_agent must be boolean"
        )
    _require_non_empty_text(
        provenance.get("agent_role"),
        "integrated_operator_judgment.execution_provenance.agent_role",
    )
    _require_non_empty_text(
        provenance.get("execution_mode"),
        "integrated_operator_judgment.execution_provenance.execution_mode",
    )

    # v2 深度运营分析字段校验（脚本生成骨架，Agent 填充内容，允许空数组）
    route_rec = _require_dict(
        packet.get("route_recommendation"),
        "integrated_operator_judgment.route_recommendation",
    )
    _require_list(
        route_rec.get("routes"),
        "integrated_operator_judgment.route_recommendation.routes",
        min_items=1,
    )

    _require_list(
        packet.get("competitor_benchmark"),
        "integrated_operator_judgment.competitor_benchmark",
        min_items=0,
    )

    _require_list(
        packet.get("price_band_analysis"),
        "integrated_operator_judgment.price_band_analysis",
        min_items=0,
    )

    _require_list(
        packet.get("voc_to_spec"),
        "integrated_operator_judgment.voc_to_spec",
        min_items=0,
    )

    kw_strategy = _require_dict(
        packet.get("keyword_strategy"),
        "integrated_operator_judgment.keyword_strategy",
    )

    _require_list(
        packet.get("risk_mitigation"),
        "integrated_operator_judgment.risk_mitigation",
        min_items=0,
    )

    # v2.1 新增深度分析字段（脚本生成骨架，Agent 填充后再做完整性检查）
    _require_list(
        packet.get("route_tradeoff"),
        "integrated_operator_judgment.route_tradeoff",
        min_items=0,
    )

    _require_list(
        packet.get("competitor_weakness_map"),
        "integrated_operator_judgment.competitor_weakness_map",
        min_items=0,
    )

    cold_start = _require_dict(
        packet.get("cold_start_estimate"),
        "integrated_operator_judgment.cold_start_estimate",
    )
    if cold_start.get("budget_range"):
        _require_non_empty_text(
            cold_start.get("budget_range"),
            "integrated_operator_judgment.cold_start_estimate.budget_range",
        )

    _require_list(
        packet.get("validation_roadmap"),
        "integrated_operator_judgment.validation_roadmap",
        min_items=0,
    )
