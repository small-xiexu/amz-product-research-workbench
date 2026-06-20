"""属性分布与交叉分析（从 market_structure_rules.py 拆分，纯移动不改逻辑）。"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from packages.research_core.rules.market_structure.shared import *  # noqa: F401,F403
from packages.research_core.rules.market_structure.shared import (
    tag_value,
    avg,
    round_number,
    to_float,
    is_blank,
    safe_rate,
    format_percent,
    compact_text,
    REQUIRED_PRODUCT_FIELDS,
)
from packages.research_core.rules.market_structure.opportunity import *  # noqa: F401,F403


def build_attribute_distributions(products: list[dict[str, Any]]) -> list[dict[str, Any]]:
    dimensions = [
        ("price_band", "价格带"),
        ("review_band", "评论门槛"),
        ("rating_band", "评分层级"),
        ("listing_age_band", "上架时间"),
        ("monthly_units_band", "销量层级"),
        ("variant_band", "变体复杂度"),
        ("lqs_band", "Listing质量"),
        ("fulfillment_band", "配送方式"),
        ("has_a_plus", "A+页面"),
        ("has_video", "视频介绍"),
        ("product_route", "产品路线"),
    ]
    return [distribution_for(products, key, label) for key, label in dimensions]


def distribution_for(products: list[dict[str, Any]], key: str, label: str) -> dict[str, Any]:
    counter: Counter[str] = Counter()
    for product in products:
        tags = product.get("attribute_tags", {})
        value = tags.get(key)
        if isinstance(value, list):
            for item in value:
                counter[compact_text(item) or "未知"] += 1
        else:
            counter[compact_text(value) or "未知"] += 1
    total = sum(counter.values())
    buckets = [
        {"value": value, "count": count, "share": safe_rate(count, total)}
        for value, count in counter.most_common()
    ]
    return {
        "dimension": key,
        "label": label,
        "total": total,
        "buckets": buckets,
        "summary": distribution_summary(label, buckets),
    }


def build_cross_analysis(products: list[dict[str, Any]]) -> list[dict[str, Any]]:
    analyses = [
        cross_dimension(
            products,
            "price_band",
            "monthly_units_band",
            "价格带 x 销量层级",
            "判断销量是否集中在低价带，或中高价是否仍有成交空间。",
        ),
        cross_dimension(
            products,
            "listing_age_band",
            "review_band",
            "上架时间 x 评论门槛",
            "识别近半年新品是否已经跨过评论门槛，避免把低评论新品误判成机会。",
        ),
        cross_dimension(
            products,
            "product_route",
            "monthly_units_band",
            "产品路线 x 销量层级",
            "判断不同功能路线的供给和销量信号，低样本路线只作线索。",
        ),
        cross_dimension(
            products,
            "rating_band",
            "review_band",
            "评分层级 x 评论门槛",
            "判断高评分是否需要高评论沉淀，或是否存在低评论高评分新品。",
        ),
        cross_dimension(
            products,
            "product_route",
            "price_band",
            "产品路线 x 价格带",
            "判断不同功能路线是否集中在低价或高价带，辅助定位差异化价格策略。",
        ),
    ]
    return analyses


def cross_dimension(
    products: list[dict[str, Any]],
    row_key: str,
    column_key: str,
    label: str,
    purpose: str,
) -> dict[str, Any]:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for product in products:
        tags = product.get("attribute_tags", {})
        row_value = tag_value(tags.get(row_key))
        column_value = tag_value(tags.get(column_key))
        groups[(row_value, column_value)].append(product)
    cells = []
    for (row_value, column_value), items in sorted(groups.items(), key=lambda item: len(item[1]), reverse=True):
        cells.append(
            {
                "row": row_value,
                "column": column_value,
                "count": len(items),
                "avg_price": round_number(avg(item.get("price") for item in items)),
                "avg_monthly_units": round_number(avg(item.get("monthly_units") for item in items)),
                "avg_rating": round_number(avg(item.get("rating") for item in items), 2),
                "sample_asins": [compact_text(item.get("asin")) for item in items[:5] if compact_text(item.get("asin"))],
                "interpretation": cell_interpretation(row_value, column_value, items),
                "opportunity_type": opportunity_type(row_value, column_value, items),
            }
        )
    return {
        "label": label,
        "row_dimension": row_key,
        "column_dimension": column_key,
        "purpose": purpose,
        "cells": cells[:20],
        "summary": cross_summary(cells),
    }


def build_summary(
    quality: dict[str, Any],
    distributions: list[dict[str, Any]],
    cross_analysis: list[dict[str, Any]],
    opportunity_judgments: list[dict[str, Any]],
) -> dict[str, Any]:
    top_price = bucket_value(distributions, "price_band")
    top_review = bucket_value(distributions, "review_band")
    top_age = bucket_value(distributions, "listing_age_band")
    top_route = bucket_value(distributions, "product_route")
    return {
        "quality_level": quality.get("level"),
        "quality_summary": f"当前商品明细 {quality.get('actual_count')} 条，完整度 {format_percent(quality.get('completeness_rate'))}，质量等级 {quality.get('level')}。",
        "dominant_structure": "；".join(
            item
            for item in [
                f"主价格带：{top_price}" if top_price else "",
                f"主评论门槛：{top_review}" if top_review else "",
                f"主上架时间：{top_age}" if top_age else "",
                f"主产品路线：{top_route}" if top_route else "",
            ]
            if item
        ),
        "opportunity_clues": opportunity_clues(cross_analysis),
        "opportunity_judgment_summary": opportunity_judgment_summary(opportunity_judgments),
        "warnings": quality.get("warnings", []),
    }


def bucket_value(distributions: list[dict[str, Any]], dimension: str) -> str:
    for item in distributions:
        if item.get("dimension") == dimension and item.get("buckets"):
            bucket = item["buckets"][0]
            return f"{bucket.get('value')}（{bucket.get('count')}，{format_percent(bucket.get('share'))}）"
    return ""


def distribution_summary(label: str, buckets: list[dict[str, Any]]) -> str:
    if not buckets:
        return f"{label} 暂无可用分布。"
    top = buckets[0]
    return f"{label}最多为 {top.get('value')}，占 {format_percent(top.get('share'))}。"


def cross_summary(cells: list[dict[str, Any]]) -> str:
    if not cells:
        return "暂无交叉分析结果。"
    top = cells[0]
    return f"最多组合为 {top.get('row')} x {top.get('column')}，样本 {top.get('count')} 个。"


def cell_interpretation(row_value: str, column_value: str, items: list[dict[str, Any]]) -> str:
    avg_units = avg(item.get("monthly_units") for item in items)
    if len(items) <= 3 and avg_units is not None and avg_units >= 100:
        return "样本少但有销量，可能是机会线索，也可能是导出样本不足。"
    if "近半年" in row_value and avg_units is not None and avg_units >= 100:
        return "新品已有销量信号，适合继续看放量原因。"
    if avg_units is not None and avg_units <= 50:
        return "销量偏弱，不能只按供给少判断为空白机会。"
    return "作为结构分布参考，需结合评论、关键词和竞品复核。"
