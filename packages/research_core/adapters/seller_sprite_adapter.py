"""SellerSprite data adapter — converts manifest-parsed records to NormalizedProduct."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from packages.research_core.adapters.base_adapter import BaseDataAdapter, ADAPTER_REGISTRY
from packages.research_core.ingestion.seller_sprite_reader import to_float, to_int, clean_cell
from packages.research_core.schema import NormalizedProduct, NormalizedKeyword, FieldSource


class SellerSpriteAdapter(BaseDataAdapter):
    """将卖家精灵导出记录（已由 seller_sprite_reader 解析）转为规范化 Schema。

    输入：
      - search_records: seller_sprite_search_results 解析后的 dict 列表
      - concentration_records: product_concentration 解析后的 dict 列表（可选）
      - data_freshness: 导出日期（ISO 格式字符串），来自 manifest metadata
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

    def fetch_products(self) -> list[NormalizedProduct]:
        seen: set[str] = set()
        products: list[NormalizedProduct] = []

        # 搜索结果明细优先（字段更完整）
        for record in self._search_records:
            asin = str(record.get("ASIN") or "").strip()
            if not asin or asin in seen:
                continue
            seen.add(asin)
            products.append(self._from_search_record(record))

        # 补充集中度数据中有但搜索结果没有的 ASIN
        for record in self._concentration_records:
            asin = str(record.get("ASIN") or "").strip()
            if not asin or asin in seen:
                continue
            seen.add(asin)
            products.append(self._from_concentration_record(record))

        return products

    def fetch_keywords(self) -> list[NormalizedKeyword]:
        return []

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


ADAPTER_REGISTRY["seller_sprite"] = SellerSpriteAdapter
