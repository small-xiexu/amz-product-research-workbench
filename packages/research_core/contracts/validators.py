"""Validate core workflow data packages before downstream rendering.

These validators intentionally check the stable handoff contract, not every
business field. Formal delivery completeness is still handled by
``scripts/validate_research_outputs.py`` after files are rendered.
"""

from __future__ import annotations

from typing import Any


class ContractValidationError(ValueError):
    """Raised when a workflow handoff package misses required structure."""


def validate_import_manifest(manifest: dict[str, Any]) -> None:
    _require_dict(manifest, "import_manifest")
    _require_dict(manifest.get("metadata"), "import_manifest.metadata")
    _require_list(manifest.get("files"), "import_manifest.files")
    _require_dict(manifest.get("data_quality"), "import_manifest.data_quality")

    metadata = manifest["metadata"]
    _require_non_empty(metadata.get("site"), "import_manifest.metadata.site")
    _require_non_empty(metadata.get("task_name"), "import_manifest.metadata.task_name")

    data_quality = manifest["data_quality"]
    _require_list(data_quality.get("available_source_types"), "import_manifest.data_quality.available_source_types")
    _require_list(data_quality.get("missing_source_types"), "import_manifest.data_quality.missing_source_types")


def validate_candidate_pool(candidate_pool: dict[str, Any]) -> None:
    _require_dict(candidate_pool, "candidate_pool")
    _require_dict(candidate_pool.get("metadata"), "candidate_pool.metadata")
    _require_dict(candidate_pool.get("source_brief"), "candidate_pool.source_brief")
    candidates = _require_list(candidate_pool.get("candidates"), "candidate_pool.candidates")
    if not candidates:
        raise ContractValidationError("candidate_pool.candidates must not be empty")

    for index, candidate in enumerate(candidates):
        path = f"candidate_pool.candidates[{index}]"
        _require_dict(candidate, path)
        _require_non_empty(candidate.get("candidate_id"), f"{path}.candidate_id")
        _require_non_empty(candidate.get("name"), f"{path}.name")
        _require_non_empty(candidate.get("status"), f"{path}.status")
        _require_dict(candidate.get("demand_evidence"), f"{path}.demand_evidence")
        _require_dict(candidate.get("competition_structure"), f"{path}.competition_structure")
        _require_list(candidate.get("top_products"), f"{path}.top_products")


def validate_review_voc_package(voc_package: dict[str, Any] | None) -> None:
    if voc_package is None:
        return
    _require_dict(voc_package, "review_voc_package")
    _require_dict(voc_package.get("metadata"), "review_voc_package.metadata")
    _require_dict(voc_package.get("summary"), "review_voc_package.summary")
    _require_list(voc_package.get("normalized_reviews"), "review_voc_package.normalized_reviews")


def validate_research_package(research_package: dict[str, Any]) -> None:
    _require_dict(research_package, "research_package")
    _require_dict(research_package.get("metadata"), "research_package.metadata")
    _require_dict(research_package.get("normalized_tables"), "research_package.normalized_tables")
    _require_dict(research_package.get("market_structure"), "research_package.market_structure")
    _require_dict(research_package.get("decision_review"), "research_package.decision_review")
    _require_dict(research_package.get("status_card"), "research_package.status_card")

    metadata = research_package["metadata"]
    _require_non_empty(metadata.get("candidate_id"), "research_package.metadata.candidate_id")

    normalized_tables = research_package["normalized_tables"]
    _require_dict(normalized_tables.get("candidate"), "research_package.normalized_tables.candidate")
    _require_list(normalized_tables.get("top100"), "research_package.normalized_tables.top100")

    decision_review = research_package["decision_review"]
    _require_dict(decision_review.get("go_nogo_scorecard"), "research_package.decision_review.go_nogo_scorecard")


def validate_workflow_state(workflow_state: dict[str, Any]) -> None:
    _require_dict(workflow_state, "workflow_state")
    _require_non_empty(workflow_state.get("workflow_id"), "workflow_state.workflow_id")
    _require_non_empty(workflow_state.get("mode"), "workflow_state.mode")
    _require_non_empty(workflow_state.get("stage"), "workflow_state.stage")
    _require_non_empty(workflow_state.get("initial_intent"), "workflow_state.initial_intent")
    _require_non_empty(workflow_state.get("site"), "workflow_state.site")
    _require_dict(workflow_state.get("known_inputs", {}), "workflow_state.known_inputs")
    _require_list(workflow_state.get("missing_inputs", []), "workflow_state.missing_inputs")
    _require_list(workflow_state.get("next_actions", []), "workflow_state.next_actions")
    _require_list(workflow_state.get("evidence_refs", []), "workflow_state.evidence_refs")
    _require_list(workflow_state.get("decision_log", []), "workflow_state.decision_log")

    for index, action in enumerate(workflow_state.get("next_actions", [])):
        path = f"workflow_state.next_actions[{index}]"
        _require_dict(action, path)
        _require_non_empty(action.get("stage"), f"{path}.stage")
        _require_dict(action.get("recommended_action"), f"{path}.recommended_action")

    for index, decision in enumerate(workflow_state.get("decision_log", [])):
        path = f"workflow_state.decision_log[{index}]"
        _require_dict(decision, path)
        _require_non_empty(decision.get("decision_id"), f"{path}.decision_id")
        _require_non_empty(decision.get("stage"), f"{path}.stage")
        _require_non_empty(decision.get("actor"), f"{path}.actor")
        _require_non_empty(decision.get("decision"), f"{path}.decision")


def _require_dict(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ContractValidationError(f"{path} must be an object")
    return value


def _require_list(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list):
        raise ContractValidationError(f"{path} must be a list")
    return value


def _require_non_empty(value: Any, path: str) -> None:
    if value is None or (isinstance(value, str) and not value.strip()):
        raise ContractValidationError(f"{path} must not be empty")
