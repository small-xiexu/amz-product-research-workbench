"""Normalized category schema shared across all data adapters."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .normalized_product import FieldSource


@dataclass
class NormalizedCategory:
    category_name: str
    category_id: str | None = None

    # ── Sorftime 独有（来自 category_trend）─────────────────
    trend_direction: str | None = None        # "增长" | "衰退" | "均衡" | "季节性"
    monthly_sales_24m: list[dict[str, Any]] | None = None
    top3_concentration_trend: str | None = None   # "集中" | "分散" | "恶化"
    new_product_share_trend: str | None = None    # "上升" | "下降" | "均衡"

    # ── 卖家精灵（来自市场分析导出）──────────────────────────
    market_monthly_units: float | None = None
    market_monthly_revenue_usd: float | None = None
    avg_price: float | None = None
    avg_rating: float | None = None
    avg_rating_count: float | None = None

    # ── 元数据 ───────────────────────────────────────────────
    data_freshness: str | None = None
    _field_sources: dict[str, FieldSource] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "category_name": self.category_name,
            "category_id": self.category_id,
            "trend_direction": self.trend_direction,
            "monthly_sales_24m": self.monthly_sales_24m,
            "top3_concentration_trend": self.top3_concentration_trend,
            "new_product_share_trend": self.new_product_share_trend,
            "market_monthly_units": self.market_monthly_units,
            "market_monthly_revenue_usd": self.market_monthly_revenue_usd,
            "avg_price": self.avg_price,
            "avg_rating": self.avg_rating,
            "avg_rating_count": self.avg_rating_count,
            "data_freshness": self.data_freshness,
            "_field_sources": {k: v.to_dict() for k, v in self._field_sources.items()},
        }
