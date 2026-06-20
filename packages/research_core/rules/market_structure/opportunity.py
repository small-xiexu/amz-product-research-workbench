"""机会判断与待确认标签（从 market_structure_rules.py 拆分，纯移动不改逻辑）。"""

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


__all__ = [
    'opportunity_clues',
    'opportunity_type',
    'build_opportunity_judgments',
    'opportunity_judgment_summary',
    'next_check_for_opportunity',
    'pending_label_items',
]


def opportunity_clues(cross_analysis: list[dict[str, Any]]) -> list[str]:
    clues = []
    for analysis in cross_analysis:
        for cell in analysis.get("cells", [])[:5]:
            if cell.get("count", 0) <= 5 and (cell.get("avg_monthly_units") or 0) >= 100:
                clues.append(f"{analysis.get('label')}：{cell.get('row')} x {cell.get('column')} 样本少但有销量，需确认是否真机会。")
            if len(clues) >= 5:
                return clues
    return clues or ["当前先输出结构线索，机会判断需结合完整 Top100、评论和关键词复核。"]


def opportunity_type(row_value: str, column_value: str, items: list[dict[str, Any]]) -> str:
    count = len(items)
    avg_units = avg(item.get("monthly_units") for item in items)
    avg_rating = avg(item.get("rating") for item in items)
    unknown_count = sum(
        1
        for product in items
        if "未知" in {tag_value(product.get("attribute_tags", {}).get("price_band")), tag_value(product.get("attribute_tags", {}).get("review_band"))}
        or tag_value(product.get("attribute_tags", {}).get("product_route")) == "待确认"
    )
    if not count:
        return "待验证"
    if unknown_count / count >= 0.5:
        return "待验证"
    if count <= 3 and avg_units is not None and avg_units >= 100:
        return "待验证"
    if avg_units is not None and avg_units <= 50:
        return "伪机会"
    if avg_rating is not None and avg_rating < 4.0:
        return "待验证"
    if ("近半年" in row_value or "近半年" in column_value) and avg_units is not None and avg_units >= 100:
        return "真机会"
    if avg_units is not None and avg_units >= 500 and count >= 5:
        return "真机会"
    return "待验证"


def build_opportunity_judgments(cross_analysis: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for analysis in cross_analysis:
        for cell in analysis.get("cells", [])[:8]:
            rows.append(
                {
                    "cross_dimension": analysis.get("label"),
                    "combination": f"{cell.get('row')} x {cell.get('column')}",
                    "opportunity_type": cell.get("opportunity_type", "待验证"),
                    "sample_count": cell.get("count"),
                    "avg_price": cell.get("avg_price"),
                    "avg_monthly_units": cell.get("avg_monthly_units"),
                    "avg_rating": cell.get("avg_rating"),
                    "basis": cell.get("interpretation"),
                    "next_check": next_check_for_opportunity(cell.get("opportunity_type", "待验证")),
                    "sample_asins": cell.get("sample_asins", []),
                }
            )
    priority = {"真机会": 0, "待验证": 1, "伪机会": 2}
    rows.sort(key=lambda item: (priority.get(str(item.get("opportunity_type")), 9), -(to_float(item.get("avg_monthly_units")) or 0)))
    return rows[:20]


def opportunity_judgment_summary(opportunity_judgments: list[dict[str, Any]]) -> str:
    counter = Counter(str(item.get("opportunity_type", "待验证")) for item in opportunity_judgments)
    parts = [f"{label} {counter.get(label, 0)} 个" for label in ("真机会", "待验证", "伪机会")]
    return "；".join(parts)


def next_check_for_opportunity(opportunity: str) -> str:
    if opportunity == "真机会":
        return "优先结合 VOC、竞品深拆和关键词/小类目证据确认是否可进入产品方案。"
    if opportunity == "伪机会":
        return "不作为主线机会，除非评论或关键词证据能解释销量偏弱原因。"
    return "需要补评论、样品结构、关键词或运营标签复核后再判断。"


def pending_label_items(products: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for product in products:
        tags = product.get("attribute_tags", {})
        route = tags.get("product_route", "")
        confidence = product.get("tag_confidence", "")
        notes = product.get("tag_notes", [])
        if route == "待确认" or confidence in {"低", "中"} or notes:
            rows.append(
                {
                    "asin": product.get("asin"),
                    "title": product.get("title"),
                    "price": product.get("price"),
                    "monthly_units": product.get("monthly_units"),
                    "product_route": route,
                    "feature_tags": tags.get("feature_tags", []),
                    "tag_confidence": confidence,
                    "tag_notes": notes,
                    "operator_product_route": "",
                    "operator_main_scene": "",
                    "operator_note": "",
                }
            )
    return rows[:80]
