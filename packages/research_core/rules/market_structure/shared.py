"""市场结构计算共享工具与常量（从 market_structure_rules.py 拆分）。"""

from __future__ import annotations

from typing import Any

REQUIRED_PRODUCT_FIELDS = [
    ("asin", "ASIN"),
    ("title", "标题"),
    ("price", "价格"),
    ("monthly_units", "月销量"),
    ("monthly_revenue_usd", "月销售额"),
    ("rating", "评分"),
    ("rating_count", "评分数"),
    ("listing_days", "上架天数"),
    ("brand", "品牌"),
    ("category", "小类目"),
]

__all__ = [
    'tag_value',
    'avg',
    'round_number',
    'to_float',
    'is_blank',
    'safe_rate',
    'format_percent',
    'compact_text',
    'REQUIRED_PRODUCT_FIELDS',
]


def tag_value(value: Any) -> str:
    if isinstance(value, list):
        return "+".join(compact_text(item) for item in value if compact_text(item)) or "未知"
    return compact_text(value) or "未知"


def avg(values: Any) -> float | None:
    numbers = [to_float(value) for value in values]
    numbers = [value for value in numbers if value is not None]
    if not numbers:
        return None
    return sum(numbers) / len(numbers)


def round_number(value: float | None, digits: int = 1) -> float | None:
    return round(value, digits) if value is not None else None


def to_float(value: Any) -> float | None:
    if value in (None, "", "--", "--,--"):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "").replace("$", "").replace("%", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def is_blank(value: Any) -> bool:
    return value in (None, "", "--", "--,--")


def safe_rate(numerator: int | float, denominator: int | float) -> float:
    if not denominator:
        return 0.0
    return numerator / denominator


def format_percent(value: Any) -> str:
    number = to_float(value)
    if number is None:
        return "待填"
    return f"{number * 100:.1f}%"


def compact_text(value: Any) -> str:
    return "" if value is None else str(value).strip()
