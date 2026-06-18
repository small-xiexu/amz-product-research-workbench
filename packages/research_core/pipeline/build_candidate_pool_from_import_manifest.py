#!/usr/bin/env python3
"""Build a first candidate_pool from inspected manual export files."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


from packages.research_core.rules.market_structure_rules import build_market_structure_analysis
from packages.research_core.adapters import SellerSpriteAdapter, SorftimeAdapter
from packages.research_core.adapters.merge_strategy import merge_products, sorftime_only_warnings

from packages.research_core.ingestion.seller_sprite_reader import (
    clean_cell, to_float, to_int, slugify, contains_chinese, display_keyword,
    clean_task_name, derive_market_name, read_records,
    file_entry, file_entries, sheet_entry, sheet_entries, load_role_records,
    first_by_value, best_by_value, first_by_source_and_value,
    sum_top, top_record, top_records,
)

def product_from_concentration(record: dict[str, Any], note: str = "") -> dict[str, Any]:
    return {
        "asin": record.get("ASIN"),
        "title": record.get("商品标题"),
        "brand": record.get("品牌"),
        "seller": record.get("卖家"),
        "fulfillment": record.get("配送方式"),
        "price": to_float(record.get("价格($)")),
        "monthly_units": to_float(record.get("月销量")),
        "monthly_revenue_usd": to_float(record.get("月销售额($)")),
        "units_share": to_float(record.get("月销量占比")),
        "revenue_share": to_float(record.get("月销售额占比")),
        "rating": to_float(record.get("星级")),
        "rating_count": to_int(record.get("评分数")),
        "review_count": to_int(record.get("评论数")),
        "listing_date": record.get("上架时间"),
        "note": note,
    }


def product_from_search_result(record: dict[str, Any], note: str = "") -> dict[str, Any]:
    return {
        "asin": record.get("ASIN"),
        "title": record.get("商品标题"),
        "brand": record.get("品牌"),
        "seller": record.get("Buybox卖家"),
        "seller_location": record.get("卖家所属地"),
        "fulfillment": record.get("配送方式"),
        "price": to_float(record.get("价格($)")),
        "monthly_units": to_float(record.get("月销量")),
        "monthly_revenue_usd": to_float(record.get("月销售额($)")),
        "rating": to_float(record.get("评分")),
        "rating_count": to_int(record.get("评分数")),
        "bsr": to_int(record.get("小类BSR")),
        "category": record.get("小类目"),
        "listing_date": record.get("上架时间"),
        "listing_days": to_int(record.get("上架天数")),
        "parent_asin": record.get("父ASIN"),
        "variant_count": to_int(record.get("变体数")),
        "lqs": to_int(record.get("LQS")),
        "has_a_plus": record.get("A+页面"),
        "has_video": record.get("视频介绍"),
        "weight": record.get("商品重量（单位换算）") or record.get("商品重量"),
        "size": record.get("商品尺寸（单位换算）") or record.get("商品尺寸"),
        "package_weight": record.get("包装重量（单位换算）") or record.get("包装重量"),
        "package_size": record.get("包装尺寸（单位换算）") or record.get("包装尺寸"),
        "url": record.get("商品详情页链接"),
        "note": note,
    }


def top_products(product_concentration: list[dict[str, Any]], limit: int = 10) -> list[dict[str, Any]]:
    return [
        product_from_concentration(record, "Top 商品集中度")
        for record in product_concentration[:limit]
        if record.get("ASIN")
    ]


def top_products_from_search_results(search_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    seen: set[str] = set()
    for record in search_records:
        asin = str(record.get("ASIN") or "").strip()
        if not asin or asin in seen:
            continue
        seen.add(asin)
        result.append(product_from_search_result(record, "卖家精灵搜索结果明细"))
    return result


def search_result_quality(search_records: list[dict[str, Any]]) -> dict[str, Any]:
    asin_values = [str(record.get("ASIN") or "").strip() for record in search_records if str(record.get("ASIN") or "").strip()]
    duplicates = sorted({asin for asin in asin_values if asin_values.count(asin) > 1})
    source_files = sorted({str(record.get("__source_file") or "") for record in search_records if record.get("__source_file")})
    row_count = len(search_records)
    unique_count = len(set(asin_values))
    notes: list[str] = []
    if row_count > unique_count:
        notes.append(f"搜索结果共有 {row_count} 行展示记录，去重后 {unique_count} 个唯一 ASIN。集中度和候选池按唯一 ASIN 看。")
    else:
        notes.append(f"搜索结果共有 {row_count} 行，唯一 ASIN {unique_count} 个。")
    if len(source_files) > 1:
        notes.append(f"当前合并了 {len(source_files)} 个搜索结果文件，适合看候选池并集，但需注意不同关键词混池。")
    return {
        "display_row_count": row_count,
        "unique_asin_count": unique_count,
        "duplicate_asin_count": len(duplicates),
        "duplicate_asin_examples": duplicates[:20],
        "source_file_count": len(source_files),
        "source_files": source_files,
        "notes": notes,
    }


def recent_winners(search_records: list[dict[str, Any]], limit: int = 10) -> list[dict[str, Any]]:
    recent = [
        record
        for record in search_records
        if record.get("ASIN") and (to_int(record.get("上架天数")) or 999999) <= 180 and (to_float(record.get("月销量")) or 0) > 0
    ]
    recent.sort(key=lambda item: (to_float(item.get("月销量")) or 0, to_float(item.get("月销售额($)")) or 0), reverse=True)
    result = []
    seen: set[str] = set()
    for record in recent:
        asin = str(record.get("ASIN") or "")
        if not asin or asin in seen:
            continue
        seen.add(asin)
        result.append(product_from_search_result(record, "近半年上架且有销量"))
        if len(result) >= limit:
            break
    return result


def structure_supplements(search_records: list[dict[str, Any]], limit: int = 8) -> list[dict[str, Any]]:
    candidates: list[tuple[str, dict[str, Any]]] = []
    priced = [record for record in search_records if record.get("ASIN") and to_float(record.get("价格($)")) is not None]
    rated = [record for record in search_records if record.get("ASIN") and to_float(record.get("评分")) is not None]
    reviewed = [record for record in search_records if record.get("ASIN") and to_int(record.get("评分数")) is not None]
    if priced:
        candidates.append(("低价结构样本", min(priced, key=lambda item: to_float(item.get("价格($)")) or 0)))
        candidates.append(("高价结构样本", max(priced, key=lambda item: to_float(item.get("价格($)")) or 0)))
    if rated:
        candidates.append(("高评分结构样本", max(rated, key=lambda item: to_float(item.get("评分")) or 0)))
        low_rated = [record for record in rated if (to_float(record.get("评分")) or 0) < 4]
        if low_rated:
            candidates.append(("低评分风险样本", min(low_rated, key=lambda item: to_float(item.get("评分")) or 0)))
    if reviewed:
        candidates.append(("高评论门槛样本", max(reviewed, key=lambda item: to_int(item.get("评分数")) or 0)))

    seen: set[str] = set()
    result = []
    for note, record in candidates:
        asin = str(record.get("ASIN") or "")
        if not asin or asin in seen:
            continue
        seen.add(asin)
        result.append(product_from_search_result(record, note))
        if len(result) >= limit:
            break
    return result


def _new_listing_friendliness(
    new_listing_count_6m: int | None,
    recent_6m_units_share: float | None,
    sample_product_count: int | None,
    has_recent_winners: bool,
) -> dict[str, Any]:
    # new listing ratio in top100 (fraction 0-1)
    if new_listing_count_6m is not None and sample_product_count:
        ratio = new_listing_count_6m / max(sample_product_count, 1)
    else:
        ratio = None

    # units share: normalize to 0-1 fraction
    if recent_6m_units_share is not None:
        share = recent_6m_units_share / 100 if recent_6m_units_share > 1 else recent_6m_units_share
    else:
        share = None

    def light(value: float | None, green: float, yellow: float) -> str:
        if value is None:
            return "待确认"
        return "绿" if value >= green else ("黄" if value >= yellow else "红")

    i1 = light(ratio, 0.10, 0.05)
    i2 = light(share, 0.10, 0.05)
    i3 = "黄" if has_recent_winners else "红"

    lights = [i for i in (i1, i2, i3) if i != "待确认"]
    if "红" in lights:
        overall = "红"
    elif all(i == "绿" for i in lights):
        overall = "绿"
    else:
        overall = "黄"

    return {
        "overall": overall,
        "indicators": {
            "new_listing_ratio_in_top100": {
                "value": round(ratio * 100, 1) if ratio is not None else None,
                "unit": "%",
                "light": i1,
            },
            "new_listing_units_share": {
                "value": round(share * 100, 1) if share is not None else None,
                "unit": "%",
                "light": i2,
            },
            "has_recent_winner_sample": {
                "value": has_recent_winners,
                "light": i3,
            },
        },
        "note": "评级自动估算，需结合竞品结构人工复核。",
    }


def keyword_intent(keyword: str, seed_keywords: list[str] | None = None) -> str:
    text = keyword.lower()
    if seed_keywords:
        for seed in seed_keywords:
            if any(word in text for word in seed.lower().split() if len(word) > 2):
                return "目标相关"
    return "待判断"


def aba_keyword_row(record: dict[str, Any], seed_keywords: list[str] | None = None) -> dict[str, Any]:
    keyword = str(record.get("关键词") or record.get("搜索词") or "").strip()
    return {
        "keyword": keyword,
        "translation": record.get("关键词翻译"),
        "monthly_searches": to_int(record.get("月搜索量")),
        "current_rank": to_int(record.get("现排名")),
        "ppc_usd": to_float(record.get("PPC价格")),
        "impressions": to_int(record.get("展示量")),
        "clicks": to_int(record.get("点击量")),
        "spr": to_int(record.get("SPR")),
        "intent": keyword_intent(keyword, seed_keywords),
        "source_file": record.get("__source_file"),
    }


def build_aba_keyword_signal(aba_trends: list[dict[str, Any]], seed_keyword: str = "") -> dict[str, Any]:
    seed_keywords = [w.strip() for w in seed_keyword.split() if len(w.strip()) > 2] if seed_keyword else []
    rows = [aba_keyword_row(record, seed_keywords) for record in top_records(aba_trends, "月搜索量", 30) if record.get("关键词")]
    target_rows = [row for row in rows if row["intent"] == "目标相关"]

    top = rows[0] if rows else {}
    top_target = target_rows[0] if target_rows else {}
    signal = "ABA 数据待补"
    if top:
        signal = f"ABA 最高搜索词「{top['keyword']}」月搜索量 {_plain_number(top.get('monthly_searches'))}"
        if top_target and top_target.get("keyword") != top.get("keyword"):
            signal += f"；目标相关词「{top_target['keyword']}」月搜索量 {_plain_number(top_target.get('monthly_searches'))}"

    return {
        "top_keywords": rows[:8],
        "target_keywords": target_rows[:6],
        "mixed_keywords": [],
        "signal": signal,
    }


def _plain_number(value: Any) -> str:
    number = to_float(value)
    if number is None:
        return "待补"
    return f"{number:,.0f}"


def _first_value(data: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        value = data.get(key)
        if value not in (None, ""):
            return value
    return None


def _extract_records(data: Any, keys: tuple[str, ...]) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if not isinstance(data, dict):
        return []
    for key in keys:
        value = data.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        if isinstance(value, dict):
            nested = _extract_records(value, keys)
            if nested:
                return nested
    return []


def _number_from_any(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if value is None:
        return None
    text = str(value).replace(",", "").strip()
    if not text:
        return None
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    return float(match.group(0)) if match else None


def _price_high_from_range(low: float | None, high: float | None) -> float | None:
    if high is not None:
        return high
    return low


def _category_report_data(sorftime_verification: dict[str, Any]) -> Any:
    return (
        sorftime_verification.get("category_report_snapshot")
        or sorftime_verification.get("category_report")
        or sorftime_verification.get("category_report_result")
        or {}
    )


def _normalize_category_report_product(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "asin": _first_value(item, ("asin", "ASIN")),
        "title": _first_value(item, ("title", "标题", "商品标题", "product_name", "productName", "name")),
        "brand": _first_value(item, ("brand", "品牌")),
        "price": _number_from_any(_first_value(item, ("price", "price_usd", "价格", "价格($)", "sale_price"))),
        "monthly_units": _number_from_any(
            _first_value(item, ("monthly_units", "monthly_sales", "month_sales_volume", "sales_volume", "月销量"))
        ),
        "monthly_revenue_usd": _number_from_any(
            _first_value(item, ("monthly_revenue_usd", "monthly_revenue", "month_sales_amount", "月销额", "月销售额($)", "月销售额"))
        ),
        "rating": _number_from_any(_first_value(item, ("rating", "review_rating", "评分", "星级"))),
        "rating_count": _number_from_any(_first_value(item, ("rating_count", "review_count", "评分数", "评价数量", "评论数"))),
        "listing_days": _number_from_any(_first_value(item, ("listing_days", "上架天数"))),
        "listing_date": _first_value(item, ("listing_date", "listed_at", "上架日期", "上架时间")),
        "url": _first_value(item, ("url", "商品详情页链接")),
    }


def _listing_within_180_days(product: dict[str, Any]) -> bool:
    days = product.get("listing_days")
    if isinstance(days, (int, float)):
        return days <= 180
    raw_date = str(product.get("listing_date") or "").strip()
    if not raw_date:
        return False
    for pattern in ("%Y-%m-%d", "%Y/%m/%d"):
        try:
            parsed = datetime.strptime(raw_date[:10], pattern)
            return (datetime.now(timezone.utc).replace(tzinfo=None) - parsed).days <= 180
        except ValueError:
            continue
    return False


def _category_report_summary(sorftime_verification: dict[str, Any]) -> dict[str, Any]:
    report = _category_report_data(sorftime_verification)
    records = _extract_records(report, ("products", "product_list", "Top100产品", "top100", "items", "records", "data"))
    products = [
        product
        for product in (_normalize_category_report_product(item) for item in records)
        if product.get("asin") or product.get("title")
    ]
    stats = report.get("类目统计报告", {}) if isinstance(report, dict) and isinstance(report.get("类目统计报告"), dict) else {}
    if not products and not stats:
        return {}

    units = [item["monthly_units"] for item in products if isinstance(item.get("monthly_units"), (int, float))]
    revenues = [item["monthly_revenue_usd"] for item in products if isinstance(item.get("monthly_revenue_usd"), (int, float))]
    prices = [item["price"] for item in products if isinstance(item.get("price"), (int, float))]
    top10 = products[:10]
    top10_units = sum(item.get("monthly_units") or 0 for item in top10)
    total_units = sum(units) if units else None
    total_revenue = sum(revenues) if revenues else None

    brand_units: dict[str, float] = {}
    for item in products:
        brand = str(item.get("brand") or "").strip()
        if not brand:
            continue
        brand_units[brand] = brand_units.get(brand, 0.0) + float(item.get("monthly_units") or 0)
    top_brand = max(brand_units, key=brand_units.get) if brand_units else ""
    recent_products = [item for item in products if _listing_within_180_days(item)]
    recent_units = sum(item.get("monthly_units") or 0 for item in recent_products)

    category_name = _first_value(report, ("category_name", "categoryName", "name", "类目名称")) if isinstance(report, dict) else None
    node_id = _first_value(report, ("node_id", "nodeid", "nodeId", "category_id", "类目节点")) if isinstance(report, dict) else None
    if stats:
        category_name = category_name or _first_value(stats, ("category_name", "categoryName", "name", "类目名称"))
        node_id = node_id or _first_value(stats, ("node_id", "nodeid", "nodeId", "category_id", "类目节点"))
    stats_total_units = _number_from_any(_first_value(stats, ("top100产品月销量", "total_monthly_units", "month_sales_volume")))
    stats_total_revenue = _number_from_any(_first_value(stats, ("top100产品月销额", "total_monthly_revenue_usd", "month_sales_amount")))
    stats_avg_price = _number_from_any(_first_value(stats, ("average_price", "平均价格", "销量前的80%产品平均价格")))
    stats_product_count = _number_from_any(_first_value(stats, ("product_count", "top100_product_count", "样本产品数")))
    if stats_total_units is not None:
        total_units = stats_total_units
    if stats_total_revenue is not None:
        total_revenue = stats_total_revenue
    top3_product_share = _number_from_any(_first_value(stats, ("top3_product_sales_volume_share", "销量前3的产品月销量占比")))
    top3_brand_share = _number_from_any(_first_value(stats, ("top3_brands_sales_volume_share", "销量前三的品牌月销量占比")))
    first_brand = _first_value(stats, ("first_brand", "销量最大品牌"))
    if isinstance(first_brand, str) and ":" in first_brand:
        first_brand = first_brand.split(":", 1)[1]
    summary = {
        "source_tool": "category_report",
        "category_name": category_name,
        "node_id": node_id,
        "product_count": int(stats_product_count) if stats_product_count is not None else len(products),
        "total_monthly_units": total_units,
        "total_monthly_revenue_usd": total_revenue,
        "avg_monthly_units": round(total_units / len(units), 2) if total_units is not None and units else None,
        "avg_monthly_revenue_usd": round(total_revenue / len(revenues), 2) if total_revenue is not None and revenues else None,
        "avg_price_usd": round(stats_avg_price, 2) if stats_avg_price is not None else (round(sum(prices) / len(prices), 2) if prices else None),
        "top10_units_share": round(top10_units / total_units, 4) if total_units else None,
        "top3_product_units_share": round(top3_product_share / 100, 4) if top3_product_share is not None else None,
        "top_brand": first_brand or top_brand,
        "top_brand_units_share": round(top3_brand_share / 100, 4) if top3_brand_share is not None else (round(brand_units[top_brand] / total_units, 4) if top_brand and total_units else None),
        "new_product_count_6m": len(recent_products),
        "new_product_units_share": round(recent_units / total_units, 4) if total_units else None,
        "sample_asins": [str(item.get("asin")) for item in products[:10] if item.get("asin")],
    }
    return {key: value for key, value in summary.items() if value not in (None, "", [])}


def _supply_chain_data(sorftime_verification: dict[str, Any]) -> Any:
    return (
        sorftime_verification.get("ali1688_similar_product")
        or sorftime_verification.get("ali1688_snapshot")
        or sorftime_verification.get("supply_chain_signal")
        or {}
    )


def _supply_chain_url(item: dict[str, Any]) -> str:
    return str(_first_value(item, ("url", "Url", "link", "Link", "detail_url", "product_url", "source_url", "链接")) or "").strip()


def _is_1688_url(value: Any) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    parts = urlsplit(text if "://" in text else f"https://{text.lstrip('/')}")
    host = (parts.netloc or "").split("@")[-1].split(":")[0].lower()
    return host == "1688.com" or host.endswith(".1688.com")


def _currency_text(item: dict[str, Any]) -> str:
    value = _first_value(
        item,
        (
            "quote_currency",
            "currency",
            "currency_code",
            "price_currency",
            "Currency",
            "币种",
            "货币",
        ),
    )
    return str(value or "").strip()


def _price_text_values(item: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for key in ("price_cny", "Price", "price", "price_range", "min_price", "max_price", "价格", "报价"):
        value = item.get(key)
        if value not in (None, ""):
            values.append(str(value))
    wholesale_ranges = _first_value(item, ("WholesalePriceRange", "wholesale_price_range", "price_tiers", "阶梯价"))
    if isinstance(wholesale_ranges, list):
        for tier in wholesale_ranges:
            if isinstance(tier, dict):
                value = _first_value(tier, ("Price", "price", "price_cny", "价格"))
                if value not in (None, ""):
                    values.append(str(value))
            elif tier not in (None, ""):
                values.append(str(tier))
    return values


def _is_rmb_currency_text(value: str) -> bool:
    text = value.strip().lower()
    if not text:
        return False
    return text in {"rmb", "cny", "人民币", "¥", "￥", "元"} or "人民币" in text


def _has_non_rmb_price_marker(values: list[str]) -> bool:
    text = " ".join(values).lower()
    return any(marker in text for marker in ("usd", "us$", "$", "美元", "美金", "eur", "€"))


def _validate_supply_chain_record(item: dict[str, Any], parent_source_url: str = "") -> tuple[bool, list[str], str]:
    reasons: list[str] = []
    item_url = _supply_chain_url(item)
    source_url = item_url or parent_source_url
    if not _is_1688_url(source_url):
        reasons.append("非1688中国站链接")

    currency = _currency_text(item)
    price_text_values = _price_text_values(item)
    if currency and not _is_rmb_currency_text(currency):
        reasons.append("币种不是RMB/CNY")
    elif _has_non_rmb_price_marker(price_text_values):
        reasons.append("价格字段疑似非人民币")

    low, high = _price_range_cny(item)
    if low is None and high is None:
        reasons.append("缺少有效人民币价格")

    quote_currency = "RMB" if not reasons else (currency or "")
    return not reasons, reasons, quote_currency


def _filter_supply_chain_records(records: list[dict[str, Any]], parent_source_url: str = "") -> tuple[list[dict[str, Any]], list[str]]:
    valid_records: list[dict[str, Any]] = []
    rejection_reasons: list[str] = []
    for item in records:
        ok, reasons, quote_currency = _validate_supply_chain_record(item, parent_source_url)
        if ok:
            if not _currency_text(item):
                item = {**item, "quote_currency": quote_currency}
            valid_records.append(item)
        else:
            rejection_reasons.extend(reasons)
    return valid_records, sorted(set(rejection_reasons))


def _price_range_cny(item: dict[str, Any]) -> tuple[float | None, float | None]:
    low = _number_from_any(_first_value(item, ("min_price_cny", "price_cny_min", "min_price", "price_min", "最低价")))
    high = _number_from_any(_first_value(item, ("max_price_cny", "price_cny_max", "max_price", "price_max", "最高价")))
    if low is not None or high is not None:
        return low, high

    wholesale_ranges = _first_value(item, ("WholesalePriceRange", "wholesale_price_range", "price_tiers", "阶梯价"))
    if isinstance(wholesale_ranges, list):
        tier_prices = [
            _number_from_any(
                _first_value(tier, ("Price", "price", "price_cny", "价格"))
                if isinstance(tier, dict)
                else tier
            )
            for tier in wholesale_ranges
        ]
        tier_prices = [price for price in tier_prices if price is not None]
        if tier_prices:
            return min(tier_prices), max(tier_prices)

    text = _first_value(item, ("price_cny", "Price", "price", "price_range", "价格", "报价"))
    if text is None:
        return None, None
    numbers = [float(match) for match in re.findall(r"\d+(?:\.\d+)?", str(text).replace(",", ""))]
    if not numbers:
        return None, None
    if len(numbers) == 1:
        return numbers[0], numbers[0]
    return min(numbers), max(numbers)


def _normalize_supply_chain_sample_product(item: dict[str, Any]) -> dict[str, Any]:
    low, high = _price_range_cny(item)
    return {
        "title": _first_value(item, ("title", "Title", "name", "product_name", "商品标题", "名称")),
        "price_cny_min": low,
        "price_cny_max": high,
        "conservative_price_cny": _price_high_from_range(low, high),
        "quote_currency": _currency_text(item) or "RMB",
        "supplier": _first_value(item, ("supplier", "supplier_name", "StoreName", "store_name", "shop_name", "供应商", "店铺")),
        "url": _supply_chain_url(item),
    }


def _supply_chain_signal_summary(sorftime_verification: dict[str, Any]) -> dict[str, Any]:
    existing_summary = sorftime_verification.get("supply_chain_signal")
    data = _supply_chain_data(sorftime_verification)
    parent_source_url = (
        str(_first_value(data, ("source_url", "sourceUrl", "url")) or "").strip()
        if isinstance(data, dict)
        else str(_first_value(existing_summary, ("source_url", "sourceUrl", "url")) or "").strip()
        if isinstance(existing_summary, dict)
        else ""
    )
    records = _extract_records(data, ("products", "product_list", "items", "records", "data", "suppliers"))
    valid_records, rejection_reasons = _filter_supply_chain_records(records, parent_source_url)
    ranges = [_price_range_cny(item) for item in valid_records]
    lows = [low for low, _ in ranges if low is not None]
    highs = [high for _, high in ranges if high is not None]
    conservative_prices = [
        _price_high_from_range(low, high)
        for low, high in ranges
        if _price_high_from_range(low, high) is not None
    ]
    if not records and not lows and not highs and isinstance(existing_summary, dict):
        existing_source_url = str(_first_value(existing_summary, ("source_url", "sourceUrl", "url")) or "https://www.1688.com/").strip()
        existing_currency = str(_first_value(existing_summary, ("quote_currency", "currency", "currency_code")) or "RMB").strip()
        sample_products = [
            _normalize_supply_chain_sample_product(item)
            for item in _filter_supply_chain_records(
                [
                    {
                        **item,
                        "quote_currency": item.get("quote_currency") or existing_currency,
                        "url": item.get("url") or existing_source_url,
                    }
                    for item in (existing_summary.get("sample_products") or existing_summary.get("top_samples") or [])
                    if isinstance(item, dict)
                ],
                existing_source_url,
            )[0]
        ]
        summary_rejection_reasons = _filter_supply_chain_records(
            [
                {
                    **item,
                    "quote_currency": item.get("quote_currency") or existing_currency,
                    "url": item.get("url") or existing_source_url,
                }
                for item in (existing_summary.get("sample_products") or existing_summary.get("top_samples") or [])
                if isinstance(item, dict)
            ],
            existing_source_url,
        )[1]
        raw_sample_count = len(
            [
                item
                for item in (existing_summary.get("sample_products") or existing_summary.get("top_samples") or [])
                if isinstance(item, dict)
            ]
        )
        rejected_sample_count = int(_number_from_any(existing_summary.get("rejected_sample_count")) or 0)
        if raw_sample_count:
            rejected_sample_count = max(rejected_sample_count, raw_sample_count - len(sample_products))
        existing_exchange_rate = _number_from_any(_first_value(existing_summary, ("exchange_rate", "usd_cny_rate", "cny_per_usd")))
        existing_conservative_cny = _number_from_any(
            _first_value(existing_summary, ("conservative_purchase_price_cny", "conservative_price_cny"))
        ) or max(
            [
                item["conservative_price_cny"]
                for item in sample_products
                if item.get("conservative_price_cny") is not None
            ],
            default=None,
        )
        existing_conservative_usd = _number_from_any(
            _first_value(existing_summary, ("conservative_purchase_price_usd", "conservative_price_usd"))
        )
        if existing_conservative_usd is None and existing_conservative_cny is not None and existing_exchange_rate:
            existing_conservative_usd = round(existing_conservative_cny / existing_exchange_rate, 2)
        summary = {
            "source_tool": existing_summary.get("source_tool") or "ali1688_similar_product",
            "source_site": existing_summary.get("source_site") or "1688中国站",
            "source_url": existing_source_url,
            "quote_currency": "RMB" if _is_rmb_currency_text(existing_currency) else existing_currency,
            "search_name": _first_value(existing_summary, ("search_name", "searchName", "keyword", "query")),
            "raw_supplier_count": _number_from_any(_first_value(existing_summary, ("raw_supplier_count", "rawSupplierCount"))),
            "supplier_count": _number_from_any(_first_value(existing_summary, ("supplier_count", "supplierCount"))),
            "relevant_supplier_count": _number_from_any(
                _first_value(existing_summary, ("relevant_supplier_count", "relevantSupplierCount"))
            ),
            "rejected_sample_count": rejected_sample_count,
            "rejection_reasons": sorted(set(existing_summary.get("rejection_reasons", []) + summary_rejection_reasons))
            if isinstance(existing_summary.get("rejection_reasons", []), list)
            else summary_rejection_reasons,
            "purchase_price_cny_min": _number_from_any(
                _first_value(existing_summary, ("purchase_price_cny_min", "price_cny_min"))
            ),
            "purchase_price_cny_max": _number_from_any(
                _first_value(existing_summary, ("purchase_price_cny_max", "price_cny_max"))
            ),
            "purchase_price_cny_avg": _number_from_any(
                _first_value(existing_summary, ("purchase_price_cny_avg", "price_cny_avg"))
            ),
            "purchase_price_cny_median": _number_from_any(
                _first_value(existing_summary, ("purchase_price_cny_median", "price_cny_median"))
            ),
            "conservative_purchase_price_cny": existing_conservative_cny,
            "conservative_purchase_price_usd": existing_conservative_usd,
            "conservative_purchase_price_basis": existing_summary.get("conservative_purchase_price_basis")
            or "1688区间报价按上限做保守估算；利润复核默认使用该字段，不使用最低SKU价。",
            "purchase_price_usd_avg": _number_from_any(
                _first_value(existing_summary, ("purchase_price_usd_avg", "price_usd_avg"))
            ),
            "exchange_rate": existing_exchange_rate,
            "confidence": existing_summary.get("confidence") or "粗估，仅供早期筛选",
            "note": existing_summary.get("note") or "1688中国站人民币报价不含头程、关税、质检、包装和损耗，不替代利润模板。",
            "sample_products": [item for item in sample_products if any(value not in (None, "") for value in item.values())],
        }
        return {key: value for key, value in summary.items() if value not in (None, "", [])}
    if records and not lows and not highs:
        summary = {
            "source_tool": "ali1688_similar_product",
            "source_site": "1688中国站",
            "source_url": parent_source_url or "https://www.1688.com/",
            "quote_currency": "RMB",
            "search_name": (
                _first_value(data, ("search_name", "searchName", "keyword", "query"))
                if isinstance(data, dict)
                else _first_value(existing_summary, ("search_name", "searchName", "keyword", "query"))
                if isinstance(existing_summary, dict)
                else None
            ),
            "raw_supplier_count": len(records),
            "supplier_count": 0,
            "rejected_sample_count": len(records),
            "rejection_reasons": rejection_reasons,
            "confidence": "无有效1688中国站人民币样本",
            "note": "未找到可纳入采购价区间的1688中国站人民币报价样本；禁止用Alibaba国际站USD报价替代。",
        }
        return {key: value for key, value in summary.items() if value not in (None, "", [])}
    if not valid_records and not lows and not highs:
        return {}
    exchange_rate = None
    if isinstance(data, dict):
        exchange_rate = _number_from_any(_first_value(data, ("exchange_rate", "usd_cny_rate", "cny_per_usd")))
    if exchange_rate is None and isinstance(existing_summary, dict):
        exchange_rate = _number_from_any(_first_value(existing_summary, ("exchange_rate", "usd_cny_rate", "cny_per_usd")))
    avg_low = sum(lows) / len(lows) if lows else None
    avg_high = sum(highs) / len(highs) if highs else None
    avg_cny = None
    if avg_low is not None and avg_high is not None:
        avg_cny = (avg_low + avg_high) / 2
    elif avg_low is not None:
        avg_cny = avg_low
    elif avg_high is not None:
        avg_cny = avg_high
    existing_samples = []
    if isinstance(existing_summary, dict):
        existing_samples = [
            item
            for item in (existing_summary.get("sample_products") or existing_summary.get("top_samples") or [])
            if isinstance(item, dict)
        ]
    sample_source = existing_samples or valid_records[:5]
    if existing_samples:
        fallback_url = _supply_chain_url(valid_records[0]) if valid_records else parent_source_url
        sample_source = _filter_supply_chain_records(
            [
                {
                    **item,
                    "quote_currency": item.get("quote_currency") or "RMB",
                    "url": item.get("url") or fallback_url,
                }
                for item in existing_samples
            ],
            parent_source_url,
        )[0]
    sample_products = [_normalize_supply_chain_sample_product(item) for item in sample_source]
    relevant_supplier_count = (
        _number_from_any(_first_value(existing_summary, ("relevant_supplier_count", "relevantSupplierCount")))
        if isinstance(existing_summary, dict)
        else None
    )
    if relevant_supplier_count is not None:
        relevant_supplier_count = min(relevant_supplier_count, float(len(valid_records)))
    conservative_cny = round(max(conservative_prices), 2) if conservative_prices else None
    conservative_usd = round(conservative_cny / exchange_rate, 2) if conservative_cny is not None and exchange_rate else None
    summary = {
        "source_tool": "ali1688_similar_product",
        "source_site": "1688中国站",
        "source_url": parent_source_url or "https://www.1688.com/",
        "quote_currency": "RMB",
        "search_name": (
            _first_value(data, ("search_name", "searchName", "keyword", "query"))
            if isinstance(data, dict)
            else _first_value(existing_summary, ("search_name", "searchName", "keyword", "query"))
            if isinstance(existing_summary, dict)
            else None
        ),
        "raw_supplier_count": len(records),
        "supplier_count": len(valid_records),
        "relevant_supplier_count": relevant_supplier_count,
        "rejected_sample_count": len(records) - len(valid_records),
        "rejection_reasons": rejection_reasons,
        "purchase_price_cny_min": round(min(lows), 2) if lows else None,
        "purchase_price_cny_max": round(max(highs), 2) if highs else None,
        "purchase_price_cny_avg": round(avg_cny, 2) if avg_cny is not None else None,
        "purchase_price_cny_median": _number_from_any(
            _first_value(existing_summary, ("purchase_price_cny_median", "price_cny_median"))
        )
        if isinstance(existing_summary, dict)
        else None,
        "conservative_purchase_price_cny": conservative_cny,
        "conservative_purchase_price_usd": conservative_usd,
        "conservative_purchase_price_basis": "1688区间报价按上限做保守估算；利润复核默认使用该字段，不使用最低SKU价。",
        "purchase_price_usd_avg": (
            round(avg_cny / exchange_rate, 2)
            if avg_cny is not None and exchange_rate
            else _number_from_any(_first_value(existing_summary, ("purchase_price_usd_avg", "price_usd_avg")))
            if isinstance(existing_summary, dict)
            else None
        ),
        "exchange_rate": exchange_rate,
        "confidence": "粗估，仅供早期筛选",
        "note": "1688中国站人民币报价不含头程、关税、质检、包装和损耗，不替代利润模板。",
        "sample_products": [item for item in sample_products if any(value not in (None, "") for value in item.values())],
    }
    return {key: value for key, value in summary.items() if value not in (None, "", [])}


def product_identity(item: dict[str, Any]) -> str:
    return str(item.get("asin") or item.get("ASIN") or "").strip()


def product_for_review_batch(product: dict[str, Any], reason: str) -> dict[str, Any]:
    coverage = competitor_coverage_dimensions(product, reason)
    return {
        "asin": product.get("asin"),
        "brand": product.get("brand"),
        "title": product.get("title"),
        "price_usd": product.get("price"),
        "monthly_units": product.get("monthly_units"),
        "rating": product.get("rating"),
        "rating_count": product.get("rating_count"),
        "competitor_type": competitor_type_from_reason(reason),
        "coverage_dimensions": coverage,
        "reason": reason,
        "selection_reason": selection_reason(product, reason, coverage),
    }


def competitor_type_from_reason(reason: str) -> str:
    if "Top10" in reason or "标杆" in reason:
        return "量级标杆"
    if "新品" in reason:
        return "近半年新品"
    if "低价" in reason or "高价" in reason or "价格" in reason:
        return "价格带覆盖"
    if "低评分" in reason or "争议" in reason or "风险" in reason:
        return "痛点参考"
    return "功能差异代表"


def competitor_coverage_dimensions(product: dict[str, Any], reason: str) -> list[str]:
    dimensions = [competitor_type_from_reason(reason)]
    if product.get("price") is not None:
        dimensions.append("价格带")
    if product.get("monthly_units") is not None:
        dimensions.append("销量量级")
    if product.get("rating") is not None or product.get("rating_count") is not None:
        dimensions.append("评分/评论门槛")
    title = str(product.get("title") or "").lower()
    if any(token in title for token in ["extendable", "telescopic", "pole", "hands free", "2 in 1", "3 in 1", "combo", "kit", "set"]):
        dimensions.append("功能/形态差异")
    return list(dict.fromkeys(dimensions))


def selection_reason(product: dict[str, Any], reason: str, coverage: list[str]) -> str:
    parts = [reason]
    if product.get("monthly_units") is not None:
        parts.append(f"月销量 {_plain_number(product.get('monthly_units'))}")
    if product.get("rating") is not None and product.get("rating_count") is not None:
        parts.append(f"评分 {product.get('rating')} / 评论 {_plain_number(product.get('rating_count'))}")
    if product.get("price") is not None:
        parts.append(f"价格 USD {_plain_number(product.get('price'))}")
    parts.append("覆盖：" + "、".join(coverage))
    return "；".join(parts)


def build_review_voc_asin_batch(
    product_concentration: list[dict[str, Any]],
    search_records: list[dict[str, Any]],
    limit: int = 16,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    candidates.extend(product_for_review_batch(item, "Top10 标杆") for item in top_products(product_concentration, limit=10))
    candidates.extend(product_for_review_batch(item, "近半年新品") for item in recent_winners(search_records, limit=6))
    candidates.extend(product_for_review_batch(item, item.get("note") or "结构样本") for item in structure_supplements(search_records, limit=8))

    low_rating_records = [
        product_from_search_result(record, "低评分/争议样本")
        for record in search_records
        if record.get("ASIN")
        and (to_float(record.get("评分")) or 5) < 4.2
        and (to_int(record.get("评分数")) or 0) >= 20
    ]
    low_rating_records.sort(key=lambda item: (item.get("rating") or 5, -(item.get("monthly_units") or 0)))
    candidates.extend(product_for_review_batch(item, "低评分/争议样本") for item in low_rating_records[:6])

    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in candidates:
        asin = product_identity(item)
        if not asin or asin in seen:
            continue
        seen.add(asin)
        result.append(item)
        if len(result) >= limit:
            break
    return result


def build_candidate_boundary_review(market_name: str, seed_keyword: str, aba_keyword_signal: dict[str, Any]) -> dict[str, Any]:
    mainline = market_name or seed_keyword or "当前候选方向"
    return {
        "checkpoint": "候选池预审后 / 评论 VOC 前",
        "recommended_mainline": mainline,
    }


def direction_key_from_text(text: str) -> str:
    return "mainline"


def direction_meta(market_name: str, seed_keyword: str) -> dict[str, str]:
    return {
        "name": market_name or seed_keyword or "当前主线方向",
        "role": "推荐主线",
        "status": "继续看",
        "product_form": "根据当前导出数据归入主线，后续需要人工确认产品形态。",
        "default_risk": "当前分类规则为通用规则，需靠真实标题、类目和运营判断进一步拆分。",
    }


def unique_products_from_search_records(search_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    products = top_products_from_search_results(search_records)
    return sorted(products, key=lambda item: item.get("monthly_units") or 0, reverse=True)


def build_direction_cards(
    market_name: str,
    seed_keyword: str,
    search_records: list[dict[str, Any]],
    aba_keyword_signal: dict[str, Any],
) -> list[dict[str, Any]]:
    grouped_products: dict[str, list[dict[str, Any]]] = {}
    for product in unique_products_from_search_records(search_records):
        text = " ".join(str(product.get(field) or "") for field in ("title", "brand", "category"))
        key = direction_key_from_text(text)
        grouped_products.setdefault(key, []).append(product)

    grouped_keywords: dict[str, list[dict[str, Any]]] = {}
    for item in aba_keyword_signal.get("top_keywords", []) + aba_keyword_signal.get("mixed_keywords", []):
        if not isinstance(item, dict):
            continue
        keyword = str(item.get("keyword") or "")
        key = direction_key_from_text(keyword)
        grouped_keywords.setdefault(key, []).append(item)

    keys = sorted(
        set(grouped_products) | set(grouped_keywords),
        key=lambda key: (
            {"优先深挖": 0, "继续看": 1, "保留参考": 2, "谨慎参考": 3, "先排除": 4}.get(
                direction_meta(market_name, seed_keyword)["status"],
                9,
            ),
            -sum(product.get("monthly_units") or 0 for product in grouped_products.get(key, [])),
        ),
    )
    cards: list[dict[str, Any]] = []
    for key in keys:
        products = grouped_products.get(key, [])
        keywords = grouped_keywords.get(key, [])
        meta = direction_meta(market_name, seed_keyword)
        total_units = sum(product.get("monthly_units") or 0 for product in products)
        avg_price = avg_number(product.get("price") for product in products)
        top_products_for_card = products[:5]
        evidence = [
            f"唯一商品数：{len(products)}" if products else "商品样本待补",
            f"合计月销量：{_plain_number(total_units)}" if products else "",
            f"均价：USD {_plain_number(avg_price)}" if avg_price is not None else "",
        ]
        if keywords:
            evidence.append(
                "关联关键词：" + "；".join(
                    f"{item.get('keyword')}（月搜 {_plain_number(item.get('monthly_searches'))}）"
                    for item in keywords[:4]
                    if item.get("keyword")
                )
            )
        if top_products_for_card:
            evidence.append(
                "代表 ASIN：" + "；".join(
                    f"{item.get('asin')} / {item.get('brand') or '未知品牌'} / 月销 {_plain_number(item.get('monthly_units'))}"
                    for item in top_products_for_card[:3]
                    if item.get("asin")
                )
            )
        risks = [meta["default_risk"]]
        if products and len(products) < 5:
            risks.append("样本数偏少，只能作为线索，不能单独形成方向结论。")
        cards.append(
            {
                "direction_id": key,
                "name": meta["name"],
                "role": meta["role"],
                "status": meta["status"],
                "product_form": meta["product_form"],
                "matched_keywords": keywords[:8],
                "product_count": len(products),
                "total_monthly_units": total_units,
                "avg_price_usd": avg_price,
                "representative_products": [
                    {
                        "asin": item.get("asin"),
                        "brand": item.get("brand"),
                        "title": item.get("title"),
                        "price_usd": item.get("price"),
                        "monthly_units": item.get("monthly_units"),
                        "rating": item.get("rating"),
                        "rating_count": item.get("rating_count"),
                    }
                    for item in top_products_for_card
                ],
                "evidence": [item for item in evidence if item],
                "risks": risks,
                "ai_recommendation": meta.get("recommendation", ""),
                "operator_options": ["选择此方向深挖", "保留为旁支参考", "排除该方向", "让 AI 按证据默认选择"],
                "next_action": "若选择该方向，下一步按代表 ASIN 抓评论 VOC，并补利润/合规复核。"
                if meta["status"] in {"优先深挖", "继续看", "保留参考", "谨慎参考"}
                else "本轮先不深挖，仅作为混池/排除依据记录。",
            }
        )
    return cards[:6]


def avg_number(values: Any) -> float | None:
    numbers = [to_float(value) for value in values]
    numbers = [value for value in numbers if value is not None]
    if not numbers:
        return None
    return round(sum(numbers) / len(numbers), 2)


def extract_seed_keyword(manifest: dict[str, Any]) -> str:
    search_file = file_entry(manifest, "seller_sprite_search_results")
    if search_file:
        match = re.search(r"Search\((.*?)\)", search_file.get("file_name", ""))
        if match:
            return match.group(1).replace("-", " ")
    aba_records = load_role_records(manifest, "amazon_aba_keywords", "aba_keywords")
    if aba_records:
        return str(aba_records[0].get("搜索词", "")).strip()
    return manifest.get("metadata", {}).get("task_name", "")


def _apply_sorftime_enrichment(
    candidate: dict[str, Any],
    sf_keywords: list,
    sf_category: Any,
) -> None:
    """将 Sorftime 规范化数据写入 candidate 的 demand_evidence / competition_structure。"""
    demand = candidate.get("demand_evidence") or {}
    competition = candidate.get("competition_structure") or {}

    if sf_category:
        parts = []
        if sf_category.trend_direction:
            parts.append(f"类目趋势：{sf_category.trend_direction}")
        if sf_category.new_product_share_trend:
            parts.append(f"新品占比趋势：{sf_category.new_product_share_trend}")
        if sf_category.top3_concentration_trend:
            parts.append(f"头部集中度趋势：{sf_category.top3_concentration_trend}")
        if parts:
            demand["trend_signal"] = "；".join(parts) + "（Sorftime category_trend）"
        demand["sorftime_category_trend"] = sf_category.to_dict()

    if sf_keywords:
        top_kw = sf_keywords[0]
        if top_kw.monthly_search_volume and not demand.get("search_signal"):
            demand["search_signal"] = (
                f"「{top_kw.keyword}」月搜索量 {_plain_number(top_kw.monthly_search_volume)}"
                + (f"，CPC {top_kw.cpc}" if top_kw.cpc else "")
                + "（Sorftime keyword_detail）"
            )
        if top_kw.competitor_count and not competition.get("keyword_competitor_count"):
            competition["keyword_competitor_count"] = top_kw.competitor_count
        demand["sorftime_keyword_verification"] = [k.to_dict() for k in sf_keywords]

    candidate["demand_evidence"] = demand
    candidate["competition_structure"] = competition


def _apply_sorftime_verification_signals(candidate: dict[str, Any], sorftime_verification: dict[str, Any]) -> None:
    demand = candidate.get("demand_evidence") or {}
    competition = candidate.get("competition_structure") or {}
    profit_space = candidate.get("preliminary_profit_space") or {}
    data_quality = candidate.get("data_quality") or {}

    category_report = _category_report_summary(sorftime_verification)
    if category_report:
        demand["sorftime_category_report"] = category_report
        if demand.get("market_avg_monthly_units") is None and category_report.get("avg_monthly_units") is not None:
            demand["market_avg_monthly_units"] = category_report.get("avg_monthly_units")
        if demand.get("market_avg_monthly_revenue_usd") is None and category_report.get("avg_monthly_revenue_usd") is not None:
            demand["market_avg_monthly_revenue_usd"] = category_report.get("avg_monthly_revenue_usd")
        if demand.get("market_avg_price_usd") is None and category_report.get("avg_price_usd") is not None:
            demand["market_avg_price_usd"] = category_report.get("avg_price_usd")
        if competition.get("sample_product_count") is None and category_report.get("product_count") is not None:
            competition["sample_product_count"] = category_report.get("product_count")
        if competition.get("top10_product_units_share") is None and category_report.get("top10_units_share") is not None:
            competition["top10_product_units_share"] = category_report.get("top10_units_share")
        if not competition.get("top_brand") and category_report.get("top_brand"):
            competition["top_brand"] = category_report.get("top_brand")
        if competition.get("top_brand_units_share") is None and category_report.get("top_brand_units_share") is not None:
            competition["top_brand_units_share"] = category_report.get("top_brand_units_share")
        data_quality["sorftime_category_report"] = {
            "enabled": True,
            "product_count": category_report.get("product_count"),
            "source_tool": "category_report",
        }

    supply_chain_signal = _supply_chain_signal_summary(sorftime_verification)
    if supply_chain_signal:
        profit_space["supply_chain_signal"] = supply_chain_signal
        conservative_cny = supply_chain_signal.get("conservative_purchase_price_cny") or supply_chain_signal.get("purchase_price_cny_max")
        conservative_text = f"；保守估算按 RMB {conservative_cny}" if conservative_cny is not None else ""
        profit_space["cogs_signal"] = (
            f"1688中国站人民币采购价区间 RMB {supply_chain_signal.get('purchase_price_cny_min', '待补')}"
            f"-{supply_chain_signal.get('purchase_price_cny_max', '待补')}；"
            f"{conservative_text.lstrip('；') if conservative_text else '保守估算价待补'}；"
            f"有效样本 {supply_chain_signal.get('supplier_count', 0)} 个供应商"
        )
        if supply_chain_signal.get("conservative_purchase_price_usd") is not None:
            profit_space["estimated_purchase_cost_usd"] = supply_chain_signal.get("conservative_purchase_price_usd")
        elif supply_chain_signal.get("purchase_price_usd_avg") is not None:
            profit_space["estimated_purchase_cost_usd"] = supply_chain_signal.get("purchase_price_usd_avg")
        data_quality["supply_chain_signal"] = {
            "enabled": True,
            "source_tool": "ali1688_similar_product",
            "supplier_count": supply_chain_signal.get("supplier_count"),
        }

    candidate["demand_evidence"] = demand
    candidate["competition_structure"] = competition
    candidate["preliminary_profit_space"] = profit_space
    candidate["data_quality"] = data_quality


def build_candidate(manifest: dict[str, Any]) -> dict[str, Any]:
    overview_records = load_role_records(manifest, "seller_sprite_market_analysis", "market_overview")
    product_concentration = load_role_records(manifest, "seller_sprite_market_analysis", "product_concentration")
    brand_concentration = load_role_records(manifest, "seller_sprite_market_analysis", "brand_concentration")
    seller_location = load_role_records(manifest, "seller_sprite_market_analysis", "seller_location_distribution")
    demand_signal = load_role_records(manifest, "seller_sprite_market_analysis", "market_demand_signal")
    price_distribution = load_role_records(manifest, "seller_sprite_market_analysis", "price_distribution")
    listing_age = load_role_records(manifest, "seller_sprite_market_analysis", "listing_age_distribution")
    search_records = load_role_records(manifest, "seller_sprite_search_results", "product_candidates")
    reverse_keywords = load_role_records(manifest, "seller_sprite_reverse_asin_keywords", "reverse_asin_keywords")
    aba_keywords = load_role_records(manifest, "amazon_aba_keywords", "aba_keywords")
    aba_keyword_trends = load_role_records(manifest, "amazon_aba_keywords", "aba_keyword_trend")

    demand_12m = first_by_value(demand_signal, "范围", "12个月")
    top_brand = brand_concentration[0] if brand_concentration else {}
    top_product = product_concentration[0] if product_concentration else {}
    top_location = top_record(seller_location, "月销量") if seller_location else {}
    top_price_band = top_record(price_distribution, "月销量") if price_distribution else {}
    recent_listing = first_by_value(listing_age, "上架时间", "半年") if listing_age else {}
    top_keyword = top_record(reverse_keywords, "月搜索量") if reverse_keywords else {}
    top_aba = aba_keywords[0] if aba_keywords else {}
    seed_keyword = extract_seed_keyword(manifest)
    aba_keyword_signal = build_aba_keyword_signal(aba_keyword_trends, seed_keyword)
    market_name = derive_market_name(manifest, seed_keyword)
    candidate_id = "cand-" + slugify(seed_keyword or market_name)
    all_products = best_by_value(overview_records, "样品分类", "全部商品", "月均销售额($)")
    primary_market_source = all_products.get("__source_file")
    top10 = first_by_source_and_value(overview_records, primary_market_source, "样品分类", "前10商品")
    new_products = first_by_source_and_value(overview_records, primary_market_source, "样品分类", "6个月内上架")
    market_return_rate = to_float(demand_12m.get("市场退货率"))
    category_return_rate = to_float(demand_12m.get("同类目退货率"))
    return_level = "待确认"
    if market_return_rate is not None and category_return_rate is not None:
        return_level = "中" if market_return_rate > category_return_rate else "低"
    # ── Adapter 层：规范化产品列表 + 可选 Sorftime 合并（M2-P1/P3）──
    _data_freshness = manifest.get("metadata", {}).get("generated_at")
    _ss_adapter = SellerSpriteAdapter(
        search_records=search_records,
        concentration_records=product_concentration,
        data_freshness=_data_freshness,
    )
    _ss_products = _ss_adapter.fetch_products()
    _sorftime_snapshot = manifest.get("sorftime_snapshot")
    _sf_warnings: list[str] = []
    _sf_keywords: list = []
    _sf_category = None
    if _sorftime_snapshot:
        _sf_adapter = SorftimeAdapter(_sorftime_snapshot)
        _sf_products = _sf_adapter.fetch_products()
        _sf_keywords = _sf_adapter.fetch_keywords()
        _sf_category = _sf_adapter.fetch_category()
        _merged = merge_products(_ss_products, _sf_products)
        if not _ss_products:
            _sf_warnings = sorftime_only_warnings(_sf_products)
    else:
        _merged = _ss_products
    top_product_rows = [p.to_dict() for p in _merged]
    search_quality = search_result_quality(search_records)
    market_structure = build_market_structure_analysis(top_product_rows, expected_count=100)
    boundary_review = build_candidate_boundary_review(market_name, seed_keyword, aba_keyword_signal)
    direction_cards = build_direction_cards(market_name, seed_keyword, search_records, aba_keyword_signal)

    source_refs = [
        f"manual_export:{item['file_name']}"
        for item in manifest.get("files", [])
        if item.get("parse_status") == "parsed" and item.get("source_type") != "system_file"
    ]

    result = {
        "candidate_id": candidate_id,
        "name": market_name,
        "candidate_type": "market_direction",
        "status": "继续看",
        "reason": "卖家精灵手动导出数据已覆盖市场分析、搜索结果和关键词反查，具备进入候选池初筛的基础证据。",
        "appearance_reason": [
            f"搜索入口：{seed_keyword}" if seed_keyword else "来自卖家精灵手动导出样例",
            f"市场样本商品数：{to_int(all_products.get('样本商品数'))}" if all_products else "市场样本数据待补",
            f"6个月内新品数量：{to_int(new_products.get('样本商品数'))}" if new_products else "新品数据待补",
        ],
        "demand_evidence": {
            "market_avg_monthly_units": to_float(all_products.get("月均销量")),
            "market_avg_monthly_revenue_usd": to_float(all_products.get("月均销售额($)")),
            "market_avg_price_usd": to_float(all_products.get("平均价格($)")),
            "top_keyword": top_keyword.get("关键词"),
            "top_keyword_monthly_searches": to_int(top_keyword.get("月搜索量")),
            "aba_top_search_term": top_aba.get("搜索词"),
            "aba_top_clicked_asin": top_aba.get("点击量最高的商品 #1：ASIN"),
            "aba_keyword_signal": aba_keyword_signal,
        },
        "competition_structure": {
            "sample_product_count": to_int(all_products.get("样本商品数")),
            "top10_avg_monthly_units": to_float(top10.get("月均销量")),
            "top10_avg_monthly_revenue_usd": to_float(top10.get("月均销售额($)")),
            "top_product_asin": top_product.get("ASIN"),
            "top_product_monthly_units_share": to_float(top_product.get("月销量占比")),
            "top10_product_units_share": sum_top(product_concentration, "月销量占比", 10),
            "top_brand": top_brand.get("品牌"),
            "top_brand_units_share": to_float(top_brand.get("月销量占比")),
            "top_seller_location": top_location.get("卖家所属地"),
            "top_seller_location_units_share": to_float(top_location.get("销量占比")),
            "search_result_rows": len(search_records),
            "search_result_unique_asins": search_quality.get("unique_asin_count"),
            "search_result_duplicate_asins": search_quality.get("duplicate_asin_count"),
        },
        "competitor_candidates": {
            "top10": top_products(product_concentration),
            "recent_winners": recent_winners(search_records),
            "structure_supplement": structure_supplements(search_records),
        },
        "top_products": top_product_rows,
        "direction_cards": direction_cards,
        "next_review_voc_asins": build_review_voc_asin_batch(product_concentration, search_records),
        "candidate_boundary_review": boundary_review,
        "market_structure": market_structure,
        "new_listing_opportunity": {
            "new_listing_count_6m": to_int(new_products.get("样本商品数")),
            "new_listing_avg_monthly_units": to_float(new_products.get("月均销量")),
            "new_listing_avg_monthly_revenue_usd": to_float(new_products.get("月均销售额($)")),
            "recent_6m_units_share": to_float(recent_listing.get("销量占比")),
            "latest_listing_date": all_products.get("商品最新上架时间"),
            "friendliness": _new_listing_friendliness(
                to_int(new_products.get("样本商品数")),
                to_float(recent_listing.get("销量占比")),
                to_int(all_products.get("样本商品数")),
                bool(recent_winners(search_records, limit=1)),
            ),
        },
        "preliminary_profit_space": {
            "avg_price_usd": to_float(all_products.get("平均价格($)")),
            "top_price_band_by_units": top_price_band.get("价格区间($)"),
            "top_price_band_units_share": to_float(top_price_band.get("销量占比")),
            "note": "仅为价格空间参考，采购价、FBA、头程和入库配置费仍需后续利润复核。",
        },
        "risk_flags": [
            "市场退货率高于同类目平均" if return_level == "中" else "退货率暂未高于同类目平均",
            "当前品类仍需后续结合评论、结构/外观专利、材质安全和使用场景责任风险复核。",
        ],
        "return_risk": {
            "level": return_level,
            "market_return_rate": market_return_rate,
            "category_return_rate": category_return_rate,
            "source": "卖家精灵市场分析-商品需求趋势",
        },
        "ip_compliance_risk": {
            "level": "待确认",
            "notes": "需后续检查商标、外观/结构专利、材质安全、目标站点合规要求和功能宣称风险。",
        },
        "data_quality": {
            "source": "manual_export" if not _sorftime_snapshot else "mixed",
            "source_types": manifest.get("data_quality", {}).get("available_source_types", []),
            "missing_source_types": manifest.get("data_quality", {}).get("missing_source_types", []),
            "manifest_warnings": manifest.get("data_quality", {}).get("warnings", []),
            "sf_warnings": _sf_warnings,
            "search_result_quality": search_quality,
            "top_product_quality": market_structure.get("data_quality", {}),
        },
        "missing_data": [
            "采购价",
            "FBA费用",
            "头程费用",
            "入库配置费",
            "评论/VOC证据",
            "商标/专利复核",
        ],
        "next_step": "先看报表后多方向候选卡，确认主线/旁支/排除项，再按选定方向抓评论 VOC。",
        "source_refs": source_refs,
    }
    if _sf_category or _sf_keywords:
        _apply_sorftime_enrichment(result, _sf_keywords, _sf_category)
    if _sorftime_snapshot:
        _apply_sorftime_verification_signals(result, {"category_report_snapshot": _sorftime_snapshot})
    return result


def merge_sorftime_signals(candidate: dict[str, Any], sorftime_verification: dict[str, Any]) -> dict[str, Any]:
    """Decompose sorftime_verification blob into specific candidate fields.

    Writes into demand_evidence (trend/search signals) and competition_structure
    (keyword-based competitor count). Does not overwrite fields that already have
    non-null values from SellerSprite, so the two sources stay traceable.
    """
    candidate = dict(candidate)
    demand = dict(candidate.get("demand_evidence", {}))
    competition = dict(candidate.get("competition_structure", {}))

    ct = sorftime_verification.get("category_trend", {})
    if ct:
        trend_dir = ct.get("trend_direction", "")
        new_prod_trend = ct.get("new_product_share_trend", "")
        conc_trend = ct.get("top3_concentration_trend", "")
        parts = []
        if trend_dir:
            parts.append(f"类目趋势：{trend_dir}")
        if new_prod_trend:
            parts.append(f"新品占比趋势：{new_prod_trend}")
        if conc_trend:
            parts.append(f"头部集中度趋势：{conc_trend}")
        if parts:
            demand["trend_signal"] = "；".join(parts) + "（Sorftime category_trend）"
        demand["sorftime_category_trend"] = ct

    kw_list = sorftime_verification.get("keyword_verification", [])
    if kw_list:
        top_kw = kw_list[0]
        if not demand.get("search_signal") and top_kw.get("monthly_search_volume"):
            demand["search_signal"] = (
                f"「{top_kw.get('keyword')}」月搜索量 {_plain_number(top_kw.get('monthly_search_volume'))}"
                + (f"，CPC {top_kw.get('cpc')}" if top_kw.get("cpc") else "")
                + "（Sorftime keyword_detail）"
            )
        if not competition.get("keyword_competitor_count") and top_kw.get("competitor_count"):
            competition["keyword_competitor_count"] = top_kw.get("competitor_count")
        demand["sorftime_keyword_verification"] = kw_list

    traffic = sorftime_verification.get("traffic_terms", {})
    if traffic:
        demand["sorftime_traffic_terms"] = traffic

    candidate["demand_evidence"] = demand
    candidate["competition_structure"] = competition
    _apply_sorftime_verification_signals(candidate, sorftime_verification)
    candidate["sorftime_verification"] = sorftime_verification
    refs = list(candidate.get("source_refs") or [])
    for source in _sorftime_source_refs(sorftime_verification):
        if source not in refs:
            refs.append(source)
    candidate["source_refs"] = refs
    return candidate


def build_candidate_pool(manifest: dict[str, Any], sorftime_verification: dict[str, Any] | None = None) -> dict[str, Any]:
    candidate = build_candidate(manifest)
    if sorftime_verification:
        candidate = merge_sorftime_signals(candidate, sorftime_verification)
    data_sources = list(manifest.get("data_quality", {}).get("available_source_types", []))
    if sorftime_verification:
        for source in _sorftime_source_refs(sorftime_verification):
            if source not in data_sources:
                data_sources.append(source)
    pool_metadata: dict[str, Any] = {
        "pool_id": "pool-manual-export-" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S"),
        "site": manifest.get("metadata", {}).get("site") or "US",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "discovery_mode": "manual_export" if not sorftime_verification else "mixed",
        "data_sources": data_sources,
        "import_manifest": manifest.get("metadata", {}).get("manifest_id"),
    }
    if sorftime_verification:
        pool_metadata["sorftime_verified_at"] = sorftime_verification.get("verified_at", "")
    return {
        "metadata": pool_metadata,
        "source_brief": {
            "brief_id": "brief-from-manual-export",
            "site": manifest.get("metadata", {}).get("site") or "US",
            "search_scope": {
                "free_text": manifest.get("metadata", {}).get("task_name", ""),
                "seed_keyword": extract_seed_keyword(manifest),
            },
            "exclusion_rules": [],
            "preference_rules": {},
        },
        "summary": {
            "total_candidates": 1,
            "continue_count": 1 if candidate["status"] == "继续看" else 0,
            "trial_count": 1 if candidate["status"] == "试做" else 0,
            "watch_count": 1 if candidate["status"] == "观察" else 0,
            "drop_count": 1 if candidate["status"] == "先放弃" else 0,
            "key_gaps": candidate["missing_data"],
        },
        "candidates": [candidate],
    }


def _sorftime_source_refs(sorftime_verification: dict[str, Any]) -> list[str]:
    refs: list[str] = []
    if sorftime_verification.get("keyword_verification"):
        refs.append("sorftime:keyword_detail")
    if sorftime_verification.get("traffic_terms"):
        refs.append("sorftime:product_traffic_terms")
    if sorftime_verification.get("category_search"):
        refs.append("sorftime:category_search_from_product_name")
    if sorftime_verification.get("category_report_snapshot"):
        refs.append("sorftime:category_report")
    if sorftime_verification.get("category_trend"):
        refs.append("sorftime:category_trend")
    if sorftime_verification.get("category_keywords"):
        refs.append("sorftime:category_keywords")
    return refs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build candidate_pool from manual export import manifest.")
    parser.add_argument("manifest", help="Path to import_manifest.json generated by inspect_manual_exports.py.")
    parser.add_argument("output", help="Path to write candidate_pool.json.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    manifest_path = Path(args.manifest).expanduser().resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    candidate_pool = build_candidate_pool(manifest)
    output = Path(args.output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(candidate_pool, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote candidate pool: {output}")
    print("Candidates:", len(candidate_pool["candidates"]))


if __name__ == "__main__":
    main()
