"""Decision rules for V1 market-opportunity status."""

from __future__ import annotations

from dataclasses import dataclass


VALID_STATUSES = ("继续看", "试做", "观察", "先放弃")


@dataclass
class DecisionInput:
    market_ok: bool
    opportunity_ok: bool
    risk_acceptable: bool
    data_complete: bool


def decide_status(inputs: DecisionInput) -> str:
    """Very small V1 decision helper."""
    if not inputs.data_complete:
        return "观察"
    if inputs.market_ok and inputs.opportunity_ok and inputs.risk_acceptable:
        return "继续看"
    if inputs.market_ok and inputs.opportunity_ok:
        return "试做"
    if inputs.market_ok:
        return "观察"
    return "先放弃"
