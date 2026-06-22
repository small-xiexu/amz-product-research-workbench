"""Application-level workflow orchestration for product research."""

from .interactive_workflow import (
    DecisionRecord,
    EvidenceRef,
    NextActionCard,
    NextActionOption,
    RecommendedAction,
    WorkflowState,
    advance_stage,
    create_initial_state,
    plan_next_action,
    workflow_state_from_dict,
)
__all__ = [
    "DecisionRecord",
    "EvidenceRef",
    "NextActionCard",
    "NextActionOption",
    "RecommendedAction",
    "WorkflowState",
    "advance_stage",
    "create_initial_state",
    "plan_next_action",
    "workflow_state_from_dict",
]
