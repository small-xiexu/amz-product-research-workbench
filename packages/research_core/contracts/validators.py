"""Validate core workflow data packages before downstream rendering.

These validators intentionally check the stable handoff contract, not every
business field. Formal delivery completeness is still handled by
``scripts/validate_research_outputs.py`` after files are rendered.
"""

from __future__ import annotations

from typing import Any


class ContractValidationError(ValueError):
    """Raised when a workflow handoff package misses required structure."""


# ── Public validators ────────────────────────────────────────────────────

def validate_import_manifest(manifest: dict[str, Any]) -> None:
    """LEGACY: validate import_manifest.json structure. 仅用于 MCP 不可用时的 fallback 路径。"""
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


# ── Shared validators (parameterized on error class) ─────────────────────
# Each per-stage contract module imports these and calls with error_cls=ItsError.
# The error_cls default (ContractValidationError) keeps existing callers working.

def _require_field(value: dict[str, Any], field: str, path: str, *, error_cls: type[Exception] = ContractValidationError) -> Any:
    if field not in value:
        raise error_cls(f"{path} missing required field: {field}")
    return value[field]


def _require_fields(value: dict[str, Any], fields: list[str] | tuple[str, ...], path: str, *, error_cls: type[Exception] = ContractValidationError) -> None:
    missing = [field for field in fields if field not in value]
    if missing:
        raise error_cls(f"{path} missing required fields: {', '.join(missing)}")


def _require_dict(value: Any, path: str, *, error_cls: type[Exception] = ContractValidationError) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise error_cls(f"{path} must be an object")
    return value


def _require_list(value: Any, path: str, *, min_items: int = 0, error_cls: type[Exception] = ContractValidationError) -> list[Any]:
    if not isinstance(value, list):
        raise error_cls(f"{path} must be a list")
    if len(value) < min_items:
        raise error_cls(f"{path} must contain at least {min_items} item(s)")
    return value


def _require_non_empty(value: Any, path: str, *, error_cls: type[Exception] = ContractValidationError) -> None:
    if value is None or (isinstance(value, str) and not value.strip()):
        raise error_cls(f"{path} must not be empty")


def _require_non_empty_text(value: Any, path: str, *, error_cls: type[Exception] = ContractValidationError) -> str:
    if value is None:
        raise error_cls(f"{path} must not be empty")
    text = str(value).strip()
    if not text:
        raise error_cls(f"{path} must not be empty")
    return text


def _require_bool(value: Any, path: str, *, error_cls: type[Exception] = ContractValidationError) -> None:
    if not isinstance(value, bool):
        raise error_cls(f"{path} must be a boolean")


def _require_confidence(value: Any, path: str, *, error_cls: type[Exception] = ContractValidationError) -> None:
    confidence = _require_non_empty_text(value, path, error_cls=error_cls)
    if confidence not in {"high", "medium", "low"}:
        raise error_cls(f"{path} must be high, medium, or low")


def _require_string_list(value: Any, path: str, *, min_items: int = 0, error_cls: type[Exception] = ContractValidationError) -> list[str]:
    items = _require_list(value, path, min_items=min_items, error_cls=error_cls)
    result: list[str] = []
    for index, item in enumerate(items):
        text = _require_non_empty_text(item, f"{path}[{index}]", error_cls=error_cls)
        result.append(text)
    return result


def _require_enum(value: Any, allowed: set[str] | frozenset[str], path: str, *, error_cls: type[Exception] = ContractValidationError) -> None:
    if value not in allowed:
        raise error_cls(f"{path} must be one of {', '.join(sorted(allowed))}")
