"""Sorftime MCP data adapter — converts Sorftime snapshot JSON to NormalizedProduct/Keyword/Category."""

from __future__ import annotations

from typing import Any

from packages.research_core.adapters.base_adapter import BaseDataAdapter, ADAPTER_REGISTRY
from packages.research_core.ingestion.seller_sprite_reader import to_float, to_int
from packages.research_core.schema import (
    NormalizedProduct,
    NormalizedKeyword,
    NormalizedCategory,
    FieldSource,
)


class SorftimeAdapter(BaseDataAdapter):
    """将 Sorftime MCP 快照 JSON 转为规范化 Schema。

    输入：manifest v2 的 sorftime_snapshot 字段，结构：
    {
      "fetched_at": "2026-06-12T10:30:00Z",
      "category_trend": { ... },          # 来自 category_trend 工具
      "keyword_data": [ ... ],            # 来自 keyword_detail / keyword_trend 工具
      "product_list": [ ... ],            # 来自 product_search / category_report 工具
    }
    """

    source_type = "sorftime"

    def __init__(self, snapshot: dict[str, Any]) -> None:
        self._snapshot = snapshot or {}
        self._fetched_at: str | None = snapshot.get("fetched_at")

    def fetch_products(self) -> list[NormalizedProduct]:
        product_list = self._snapshot.get("product_list") or []
        source = FieldSource(source="sorftime", confidence="medium",
                             note="Sorftime 估算值，月销量精度低于卖家精灵")
        products: list[NormalizedProduct] = []
        seen: set[str] = set()
        for item in product_list:
            asin = str(item.get("asin") or "").strip()
            if not asin or asin in seen:
                continue
            seen.add(asin)
            products.append(NormalizedProduct(
                asin=asin,
                title=_str(item.get("title")),
                brand=_str(item.get("brand")),
                category=_str(item.get("category")),
                price=to_float(item.get("price")),
                monthly_units=to_float(item.get("monthly_units") or item.get("monthly_sales")),
                monthly_revenue_usd=to_float(item.get("monthly_revenue") or item.get("monthly_revenue_usd")),
                rating=to_float(item.get("rating") or item.get("review_rating")),
                rating_count=to_float(item.get("rating_count") or item.get("review_count")),
                fulfillment=_str(item.get("fulfillment")),
                url=_str(item.get("url")),
                data_freshness=self._fetched_at,
                note="Sorftime 产品列表",
                _field_sources={
                    f: source for f in (
                        "asin", "title", "brand", "price",
                        "monthly_units", "monthly_revenue_usd",
                        "rating", "rating_count",
                    )
                    if getattr(NormalizedProduct(asin=asin), f, None) is not None
                       or item.get(f) is not None
                },
            ))
        return products

    def fetch_keywords(self) -> list[NormalizedKeyword]:
        keyword_data = self._snapshot.get("keyword_data") or []
        source = FieldSource(source="sorftime", confidence="high")
        keywords: list[NormalizedKeyword] = []
        for item in keyword_data:
            kw = _str(item.get("keyword"))
            if not kw:
                continue
            keywords.append(NormalizedKeyword(
                keyword=kw,
                monthly_search_volume=to_int(
                    item.get("monthly_search_volume") or item.get("search_volume_monthly")
                ),
                weekly_search_volume=to_int(
                    item.get("weekly_search_volume") or item.get("search_volume_weekly")
                ),
                cpc=to_float(item.get("cpc")),
                trend_direction=_str(item.get("trend_direction")),
                trend_24m=item.get("trend_24m") or item.get("monthly_trend"),
                seasonality=_str(item.get("seasonality")),
                competitor_count=to_int(item.get("competitor_count") or item.get("result_count")),
                data_freshness=self._fetched_at,
                _field_sources={
                    f: source for f in (
                        "keyword", "monthly_search_volume", "weekly_search_volume",
                        "cpc", "trend_direction", "seasonality", "competitor_count",
                    )
                },
            ))
        return keywords

    def fetch_category(self) -> NormalizedCategory | None:
        ct = self._snapshot.get("category_trend")
        if not ct:
            return None
        source = FieldSource(source="sorftime", confidence="high")
        return NormalizedCategory(
            category_name=_str(ct.get("category_name") or ct.get("name") or ""),
            category_id=_str(ct.get("category_id") or ct.get("node_id")),
            trend_direction=_str(ct.get("trend_direction")),
            monthly_sales_24m=ct.get("monthly_sales_24m") or ct.get("monthly_trend"),
            top3_concentration_trend=_str(ct.get("top3_concentration_trend")),
            new_product_share_trend=_str(ct.get("new_product_share_trend")),
            data_freshness=self._fetched_at,
            _field_sources={
                f: source for f in (
                    "trend_direction", "monthly_sales_24m",
                    "top3_concentration_trend", "new_product_share_trend",
                )
            },
        )


def _str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


SortimeAdapter = SorftimeAdapter

ADAPTER_REGISTRY["sorftime"] = SorftimeAdapter
