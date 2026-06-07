"""Profit rules for the first version of the research package."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ProfitInputs:
    sale_price: float
    purchase_cost: float
    first_leg_shipping: float
    fba_fee: float
    commission_rate: float = 0.15
    storage_fee: float = 0.0
    inbound_placement_fee: float = 0.0
    ad_rate: float = 0.20
    return_rate: float = 0.0


def calc_base_fba_gross_profit(inputs: ProfitInputs) -> float:
    """Base FBA gross profit before ads and returns."""
    commission = inputs.sale_price * inputs.commission_rate
    return (
        inputs.sale_price
        - inputs.purchase_cost
        - inputs.first_leg_shipping
        - inputs.fba_fee
        - commission
        - inputs.storage_fee
        - inputs.inbound_placement_fee
    )


def calc_post_ads_returns_gross_profit(inputs: ProfitInputs) -> float:
    """Gross profit after ad and return assumptions."""
    base = calc_base_fba_gross_profit(inputs)
    ad_cost = inputs.sale_price * inputs.ad_rate
    return_loss = inputs.sale_price * inputs.return_rate
    return base - ad_cost - return_loss


def calc_margin(profit: float, sale_price: float) -> float:
    if sale_price == 0:
        return 0.0
    return profit / sale_price
