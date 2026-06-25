"""SellerSprite data adapter — converts manifest-parsed records or MCP snapshots to NormalizedProduct."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from packages.research_core.adapters.base_adapter import BaseDataAdapter, ADAPTER_REGISTRY
from packages.research_core.ingestion.seller_sprite_reader import to_float, to_int, clean_cell
from packages.research_core.schema import NormalizedProduct, NormalizedKeyword, FieldSource

# 卖家精灵 MCP 工具名 → 数据类型映射
_PRODUCT_TOOLS = {
    "product_research", "market_research", "competitor_lookup",
    "keyword_research", "traffic_listing", "traffic_keyword",
}
_CONCENTRATION_TOOLS = {
    "market_product_concentration", "market_brand_concentration",
    "market_seller_concentration", "market_seller_type_concentration",
}


class SellerSpriteAdapter(BaseDataAdapter):
    """将卖家精灵数据转为规范化 Schema。

    支持两条输入路径：
      1. 旧 manifest 路径：search_records + concentration_records（中文列名）
      2. MCP 快照路径：from_mcp_snapshot() 读取 tool_calls[].normalized_preview
    """

    source_type = "seller_sprite"

    def __init__(
        self,
        search_records: list[dict[str, Any]] | None = None,
        concentration_records: list[dict[str, Any]] | None = None,
        data_freshness: str | None = None,
    ) -> None:
        self._search_records = search_records or []
        self._concentration_records = concentration_records or []
        self._data_freshness = data_freshness

    # ── MCP 快照入口 ────────────────────────────────────────────

    @classmethod
    def from_mcp_snapshot(cls, snapshot: dict[str, Any]) -> SellerSpriteAdapter:
        """从 MCP 快照构建适配器。

        遍历 tool_calls[]，从成功的调用中提取 normalized_preview 的产品列表。
        product_research / market_research 等归入 search_records；
        market_*_concentration 归入 concentration_records。
        """
        if snapshot.get("source_type") != "sellersprite_mcp":
            raise ValueError(
                f"source_type 不匹配: 期望 sellersprite_mcp, "
                f"得到 {snapshot.get('source_type')}"
            )

        search_records: list[dict[str, Any]] = []
        concentration_records: list[dict[str, Any]] = []

        for tc in snapshot.get("tool_calls", []):
            if tc.get("status") != "success":
                continue
            preview = tc.get("normalized_preview")
            if preview is None:
                continue

            records = _extract_records(preview)
            if not records:
                continue

            tool_name = tc.get("tool_name", "")
            if tool_name in _CONCENTRATION_TOOLS:
                concentration_records.extend(records)
            elif tool_name in _PRODUCT_TOOLS:
                search_records.extend(records)
            else:
                # 未知工具默认按搜索结果处理
                search_records.extend(records)

        return cls(
            search_records=search_records,
            concentration_records=concentration_records,
            data_freshness=snapshot.get("collected_at"),
        )

    # ── 数据获取 ────────────────────────────────────────────────

    def fetch_products(self) -> list[NormalizedProduct]:
        seen: set[str] = set()
        products: list[NormalizedProduct] = []

        for record in self._search_records:
            asin = _resolve_asin(record)
            if not asin or asin in seen:
                continue
            seen.add(asin)
            products.append(self._from_record(record, note="卖家精灵搜索结果明细"))

        for record in self._concentration_records:
            asin = _resolve_asin(record)
            if not asin or asin in seen:
                continue
            seen.add(asin)
            products.append(self._from_record(record, note="Top 商品集中度"))

        return products

    def fetch_keywords(self) -> list[NormalizedKeyword]:
        return []

    # ── 记录 → NormalizedProduct ────────────────────────────────

    def _from_record(self, record: dict[str, Any], note: str = "") -> NormalizedProduct:
        """统一入口：自动识别中文列名（旧 manifest）或英文列名（MCP normalized_preview）。"""
        if "ASIN" in record or "商品标题" in record:
            return self._from_search_record(record)
        return self._from_normalized_record(record, note=note)

    def _from_search_record(self, record: dict[str, Any]) -> NormalizedProduct:
        source = FieldSource(source="seller_sprite", confidence="high")
        listing_days = to_int(record.get("上架天数"))
        listing_date = _listing_date(record.get("上架时间"), listing_days)
        return NormalizedProduct(
            asin=str(record.get("ASIN") or "").strip(),
            title=clean_cell(record.get("商品标题")),
            brand=clean_cell(record.get("品牌")),
            parent_asin=clean_cell(record.get("父ASIN")),
            category=clean_cell(record.get("小类目")),
            price=to_float(record.get("价格($)")),
            monthly_units=to_float(record.get("月销量")),
            monthly_revenue_usd=to_float(record.get("月销售额($)")),
            rating=to_float(record.get("评分")),
            rating_count=to_float(record.get("评分数")),
            listing_date=listing_date,
            listing_days=float(listing_days) if listing_days is not None else None,
            fulfillment=clean_cell(record.get("配送方式")),
            lqs=to_float(record.get("LQS")),
            variant_count=to_float(record.get("变体数")),
            has_a_plus=clean_cell(record.get("A+页面")),
            has_video=clean_cell(record.get("视频介绍")),
            bsr=to_int(record.get("小类BSR")),
            seller=clean_cell(record.get("Buybox卖家")),
            seller_location=clean_cell(record.get("卖家所属地")),
            weight=clean_cell(record.get("商品重量（单位换算）") or record.get("商品重量")),
            size=clean_cell(record.get("商品尺寸（单位换算）") or record.get("商品尺寸")),
            package_weight=clean_cell(record.get("包装重量（单位换算）") or record.get("包装重量")),
            package_size=clean_cell(record.get("包装尺寸（单位换算）") or record.get("包装尺寸")),
            url=clean_cell(record.get("商品详情页链接")),
            data_freshness=self._data_freshness,
            note="卖家精灵搜索结果明细",
            _field_sources={
                f: source for f in (
                    "asin", "title", "brand", "price", "monthly_units",
                    "monthly_revenue_usd", "rating", "rating_count",
                    "listing_days", "lqs", "has_a_plus", "has_video",
                )
            },
        )

    def _from_normalized_record(self, record: dict[str, Any], note: str = "") -> NormalizedProduct:
        """从 MCP normalized_preview 记录构建 NormalizedProduct（英文列名）。"""
        source = FieldSource(source="seller_sprite", confidence="high")
        return NormalizedProduct(
            asin=_resolve_asin(record) or "",
            title=_str(record.get("title")),
            brand=_str(record.get("brand")),
            parent_asin=_str(record.get("parent_asin")),
            category=_str(record.get("category")),
            price=to_float(record.get("price")),
            monthly_units=to_float(record.get("monthly_units") or record.get("monthly_sales")),
            monthly_revenue_usd=to_float(record.get("monthly_revenue_usd") or record.get("monthly_revenue")),
            rating=to_float(record.get("rating") or record.get("review_rating")),
            rating_count=to_float(record.get("rating_count") or record.get("review_count")),
            listing_date=_str(record.get("listing_date")),
            listing_days=to_float(record.get("listing_days")),
            fulfillment=_str(record.get("fulfillment")),
            lqs=to_float(record.get("lqs")),
            variant_count=to_float(record.get("variant_count")),
            has_a_plus=_str(record.get("has_a_plus")),
            has_video=_str(record.get("has_video")),
            bsr=to_int(record.get("bsr")),
            seller=_str(record.get("seller")),
            seller_location=_str(record.get("seller_location")),
            weight=_str(record.get("weight")),
            size=_str(record.get("size")),
            url=_str(record.get("url")),
            data_freshness=self._data_freshness,
            note=note or "卖家精灵 MCP",
            _field_sources={
                f: source for f in (
                    "asin", "title", "brand", "price", "monthly_units",
                    "monthly_revenue_usd", "rating", "rating_count",
                )
            },
        )

    def _from_concentration_record(self, record: dict[str, Any]) -> NormalizedProduct:
        source = FieldSource(source="seller_sprite", confidence="high")
        return NormalizedProduct(
            asin=str(record.get("ASIN") or "").strip(),
            title=clean_cell(record.get("商品标题")),
            brand=clean_cell(record.get("品牌")),
            seller=clean_cell(record.get("卖家")),
            fulfillment=clean_cell(record.get("配送方式")),
            price=to_float(record.get("价格($)")),
            monthly_units=to_float(record.get("月销量")),
            monthly_revenue_usd=to_float(record.get("月销售额($)")),
            rating=to_float(record.get("星级")),
            rating_count=to_float(record.get("评分数")),
            data_freshness=self._data_freshness,
            note="Top 商品集中度",
            _field_sources={
                f: source for f in (
                    "asin", "title", "brand", "price", "monthly_units",
                    "monthly_revenue_usd", "rating", "rating_count",
                )
            },
        )


def _listing_date(raw_date: Any, listing_days: int | None) -> str | None:
    """卖家精灵上架时间字段转 ISO 日期字符串。"""
    if raw_date is not None:
        if hasattr(raw_date, "strftime"):
            return raw_date.strftime("%Y-%m-%d")
        text = str(raw_date).strip()
        if text:
            return text
    if listing_days is not None:
        try:
            d = date.fromordinal(date.today().toordinal() - listing_days)
            return d.isoformat()
        except Exception:
            pass
    return None


def _extract_records(preview: Any) -> list[dict[str, Any]]:
    """从 normalized_preview 中提取产品记录列表。"""
    if isinstance(preview, list):
        return [item for item in preview if isinstance(item, dict)]
    if isinstance(preview, dict):
        # 可能包裹在 products / items / results 键中
        for key in ("products", "items", "results", "list"):
            if key in preview and isinstance(preview[key], list):
                return [item for item in preview[key] if isinstance(item, dict)]
        # 单条记录
        if "asin" in preview:
            return [preview]
    return []


def _resolve_asin(record: dict[str, Any]) -> str:
    """从记录中提取 ASIN，兼容中文和英文列名。"""
    for key in ("asin", "ASIN", "Asin"):
        val = record.get(key)
        if val:
            return str(val).strip()
    return ""


def _str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


ADAPTER_REGISTRY["seller_sprite"] = SellerSpriteAdapter
