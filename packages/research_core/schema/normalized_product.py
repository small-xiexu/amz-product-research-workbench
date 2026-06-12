"""Normalized product schema shared across all data adapters."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class FieldSource:
    source: str          # "seller_sprite" | "sorftime" | "manual"
    confidence: str      # "high" | "medium" | "low"
    note: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"source": self.source, "confidence": self.confidence, "note": self.note}


@dataclass
class NormalizedProduct:
    # ── 身份字段 ──────────────────────────────────────────────
    asin: str
    title: str | None = None
    brand: str | None = None
    parent_asin: str | None = None     # SS: 直接；SF: 无
    category: str | None = None

    # ── 价格 ──────────────────────────────────────────────────
    price: float | None = None          # 两源都有，精度相近

    # ── 销量（SS 精确，SF 为估算）────────────────────────────
    monthly_units: float | None = None
    monthly_revenue_usd: float | None = None

    # ── 评价 ──────────────────────────────────────────────────
    rating: float | None = None
    rating_count: float | None = None

    # ── Listing 特征 ──────────────────────────────────────────
    listing_date: str | None = None     # ISO date string
    listing_days: float | None = None   # SS: 直接；SF: 无
    fulfillment: str | None = None
    lqs: float | None = None            # SS 专有，SF 无此字段
    variant_count: float | None = None
    has_a_plus: str | None = None       # SS 专有
    has_video: str | None = None        # SS 专有
    bullet_points: str | None = None    # SS: 导出包含；SF: 需额外调用

    # ── 物流尺寸（SS 专有）──────────────────────────────────
    bsr: int | None = None
    seller: str | None = None
    seller_location: str | None = None
    weight: str | None = None
    size: str | None = None
    package_weight: str | None = None
    package_size: str | None = None
    url: str | None = None

    # ── 元数据 ────────────────────────────────────────────────
    data_freshness: str | None = None   # ISO date string，数据快照日期
    note: str | None = None
    _field_sources: dict[str, FieldSource] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """转为与现有脚本完全兼容的 dict，字段名与现有 product dict 一致。"""
        return {
            "asin": self.asin,
            "title": self.title,
            "brand": self.brand,
            "parent_asin": self.parent_asin,
            "category": self.category,
            "price": self.price,
            "monthly_units": self.monthly_units,
            "monthly_revenue_usd": self.monthly_revenue_usd,
            "rating": self.rating,
            "rating_count": self.rating_count,
            "listing_date": self.listing_date,
            "listing_days": self.listing_days,
            "fulfillment": self.fulfillment,
            "lqs": self.lqs,
            "variant_count": self.variant_count,
            "has_a_plus": self.has_a_plus,
            "has_video": self.has_video,
            "bullet_points": self.bullet_points,
            "bsr": self.bsr,
            "seller": self.seller,
            "seller_location": self.seller_location,
            "weight": self.weight,
            "size": self.size,
            "package_weight": self.package_weight,
            "package_size": self.package_size,
            "url": self.url,
            "data_freshness": self.data_freshness,
            "note": self.note,
            "_field_sources": {k: v.to_dict() for k, v in self._field_sources.items()},
        }
