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
from .product_research_workflow import WorkflowConfig, WorkflowResult, run_research_workflow

__all__ = [
    "DecisionRecord",
    "EvidenceRef",
    "NextActionCard",
    "NextActionOption",
    "RecommendedAction",
    "WorkflowState",
    "WorkflowConfig",
    "WorkflowResult",
    "advance_stage",
    "create_initial_state",
    "plan_next_action",
    "run_research_workflow",
    "workflow_state_from_dict",
]
