"""Profit rules for the first version of the research package."""

from __future__ import annotations

from dataclasses import dataclass


DEFAULT_COMMISSION_RATE = 0.15
DEFAULT_STORAGE_FEE_RATE = 0.03
DEFAULT_AD_RATE = 0.20

FIRST_LEG_RATE_CNY_PER_KG = {
    "US_MATSON": 11.0,
    "US_STANDARD_SEA": 6.0,
    "CA_EXPRESS": 22.0,
    "CA_TRUCK_SEA": 9.0,
}


@dataclass
class ProfitInputs:
    sale_price: float
    purchase_cost: float
    fba_fee: float
    inbound_placement_fee: float | None
    first_leg_shipping: float | None = None
    actual_weight_g: float | None = None
    volume_weight_g: float | None = None
    first_leg_channel: str | None = None
    commission_rate: float = DEFAULT_COMMISSION_RATE
    storage_fee: float | None = None
    ad_rate: float = DEFAULT_AD_RATE
    return_rate: float = 0.0


def calc_storage_fee(sale_price: float, storage_fee: float | None = None) -> float:
    """Early simplified storage estimate: sale price * 3% unless manually provided."""
    if storage_fee is not None:
        return storage_fee
    return sale_price * DEFAULT_STORAGE_FEE_RATE


def calc_billable_weight_g(actual_weight_g: float, volume_weight_g: float) -> float:
    """First-leg billable weight uses the larger of actual and volume weight."""
    return max(actual_weight_g, volume_weight_g)


def calc_first_leg_shipping(billable_weight_g: float, rate_cny_per_kg: float) -> float:
    return billable_weight_g / 1000 * rate_cny_per_kg


def calc_first_leg_shipping_by_channel(
    actual_weight_g: float,
    volume_weight_g: float,
    first_leg_channel: str,
) -> float:
    if first_leg_channel not in FIRST_LEG_RATE_CNY_PER_KG:
        raise ValueError(f"Unsupported first-leg channel: {first_leg_channel}")
    billable_weight_g = calc_billable_weight_g(actual_weight_g, volume_weight_g)
    return calc_first_leg_shipping(billable_weight_g, FIRST_LEG_RATE_CNY_PER_KG[first_leg_channel])


def calc_base_fba_gross_profit(inputs: ProfitInputs) -> float:
    """Base FBA gross profit before ads and returns."""
    first_leg_shipping = _resolve_first_leg_shipping(inputs)
    inbound_placement_fee = _required_number(
        inputs.inbound_placement_fee,
        "inbound_placement_fee is required. Mark as pending instead of defaulting to 0.",
    )
    storage_fee = calc_storage_fee(inputs.sale_price, inputs.storage_fee)
    commission = inputs.sale_price * inputs.commission_rate
    return (
        inputs.sale_price
        - inputs.purchase_cost
        - first_leg_shipping
        - inputs.fba_fee
        - commission
        - storage_fee
        - inbound_placement_fee
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


def _resolve_first_leg_shipping(inputs: ProfitInputs) -> float:
    if inputs.first_leg_shipping is not None:
        return inputs.first_leg_shipping
    if (
        inputs.actual_weight_g is not None
        and inputs.volume_weight_g is not None
        and inputs.first_leg_channel is not None
    ):
        return calc_first_leg_shipping_by_channel(
            inputs.actual_weight_g,
            inputs.volume_weight_g,
            inputs.first_leg_channel,
        )
    raise ValueError(
        "first_leg_shipping is required, or provide actual_weight_g, volume_weight_g, and first_leg_channel."
    )


def _required_number(value: float | None, message: str) -> float:
    if value is None:
        raise ValueError(message)
    return value
