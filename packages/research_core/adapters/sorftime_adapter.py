"""Sorftime MCP data adapter — converts Sorftime snapshot JSON to NormalizedProduct/Keyword/Category.

Supports two input paths:
  1. Legacy flat snapshot dict (category_trend / keyword_data / product_list keys)
  2. MCP snapshot via from_mcp_snapshot() — reads tool_calls[].normalized_preview
"""

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

# Sorftime MCP 工具名 → 数据类别
_CATEGORY_TOOLS = {"category_trend", "category_report", "category_report_from_history"}
_KEYWORD_TOOLS = {
    "keyword_detail", "keyword_list", "keyword_extends", "keyword_trend",
    "keyword_search_results", "keyword_list_from_history", "category_keywords",
    "competitor_product_keywords", "product_traffic_terms",
}
_PRODUCT_TOOLS = {
    "product_search", "product_detail", "product_report",
    "product_search_from_history", "product_ranking_trend_by_keyword",
}


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
        self._depth: str | None = snapshot.get("depth")

    # ── MCP 快照入口 ────────────────────────────────────────────

    @classmethod
    def from_mcp_snapshot(cls, snapshot: dict[str, Any]) -> SorftimeAdapter:
        """从 MCP 快照构建适配器。

        遍历 tool_calls[]，按工具名将 normalized_preview 分入
        category_trend / keyword_data / product_list 三类。
        """
        if snapshot.get("source_type") != "sorftime_mcp":
            raise ValueError(
                f"source_type 不匹配: 期望 sorftime_mcp, "
                f"得到 {snapshot.get('source_type')}"
            )

        category_trend: dict[str, Any] | None = None
        keyword_data: list[dict[str, Any]] = []
        product_list: list[dict[str, Any]] = []

        for tc in snapshot.get("tool_calls", []):
            if tc.get("status") != "success":
                continue
            preview = tc.get("normalized_preview")
            if preview is None:
                continue
            tool_name = tc.get("tool_name", "")

            if tool_name in _CATEGORY_TOOLS:
                cat = _extract_single(preview)
                if cat and category_trend is None:
                    category_trend = cat
            elif tool_name in _KEYWORD_TOOLS:
                keyword_data.extend(_extract_list(preview))
            elif tool_name in _PRODUCT_TOOLS:
                product_list.extend(_extract_list(preview))
            else:
                # 未知工具：尝试按内容结构推断
                items = _extract_list(preview)
                if items:
                    first = items[0]
                    if "keyword" in first:
                        keyword_data.extend(items)
                    elif "asin" in first:
                        product_list.extend(items)

        return cls({
            "fetched_at": snapshot.get("collected_at"),
            "depth": snapshot.get("depth"),
            "category_trend": category_trend or {},
            "keyword_data": keyword_data,
            "product_list": product_list,
        })

    # ── 数据获取 ────────────────────────────────────────────────

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
                parent_asin=_str(item.get("parent_asin")),
                category=_str(item.get("category")),
                price=to_float(item.get("price")),
                monthly_units=to_float(item.get("monthly_units") or item.get("monthly_sales")),
                monthly_revenue_usd=to_float(item.get("monthly_revenue") or item.get("monthly_revenue_usd")),
                rating=to_float(item.get("rating") or item.get("review_rating")),
                rating_count=to_float(item.get("rating_count") or item.get("review_count")),
                listing_date=_str(item.get("listing_date")),
                fulfillment=_str(item.get("fulfillment")),
                seller=_str(item.get("seller")),
                seller_location=_str(item.get("seller_location")),
                url=_str(item.get("url")),
                data_freshness=self._fetched_at,
                note="Sorftime 产品列表",
                _field_sources={
                    f: source for f in (
                        "asin", "title", "brand", "price",
                        "monthly_units", "monthly_revenue_usd",
                        "rating", "rating_count",
                    )
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


def _extract_list(preview: Any) -> list[dict[str, Any]]:
    """从 normalized_preview 中提取 dict 列表。"""
    if isinstance(preview, list):
        return [item for item in preview if isinstance(item, dict)]
    if isinstance(preview, dict):
        for key in ("products", "items", "results", "keywords", "list"):
            if key in preview and isinstance(preview[key], list):
                return [item for item in preview[key] if isinstance(item, dict)]
    return []


def _extract_single(preview: Any) -> dict[str, Any] | None:
    """从 normalized_preview 中提取单条 dict。"""
    if isinstance(preview, dict):
        return preview
    if isinstance(preview, list) and preview:
        first = preview[0]
        if isinstance(first, dict):
            return first
    return None


SortimeAdapter = SorftimeAdapter

ADAPTER_REGISTRY["sorftime"] = SorftimeAdapter
