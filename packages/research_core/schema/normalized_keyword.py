"""Normalized keyword schema shared across all data adapters."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .normalized_product import FieldSource


@dataclass
class NormalizedKeyword:
    keyword: str

    # ── 两源都有 ──────────────────────────────────────────────
    monthly_search_volume: int | None = None
    weekly_search_volume: int | None = None

    # ── Sorftime 独有 ─────────────────────────────────────────
    cpc: float | None = None
    trend_direction: str | None = None   # "增长" | "衰退" | "均衡" | "季节性"
    trend_24m: list[dict[str, Any]] | None = None  # [{month, search_volume}, ...]
    seasonality: str | None = None
    competitor_count: int | None = None  # 首页竞品数

    # ── 卖家精灵 ABA 独有 ─────────────────────────────────────
    aba_rank: int | None = None
    click_share_top1: float | None = None

    # ── 元数据 ────────────────────────────────────────────────
    data_freshness: str | None = None
    _field_sources: dict[str, FieldSource] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "keyword": self.keyword,
            "monthly_search_volume": self.monthly_search_volume,
            "weekly_search_volume": self.weekly_search_volume,
            "cpc": self.cpc,
            "trend_direction": self.trend_direction,
            "trend_24m": self.trend_24m,
            "seasonality": self.seasonality,
            "competitor_count": self.competitor_count,
            "aba_rank": self.aba_rank,
            "click_share_top1": self.click_share_top1,
            "data_freshness": self.data_freshness,
            "_field_sources": {k: v.to_dict() for k, v in self._field_sources.items()},
        }
