"""产品属性打标与维度分桶（从 market_structure_rules.py 拆分，纯移动不改逻辑）。"""

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


def tag_product(product: dict[str, Any]) -> dict[str, Any]:
    tagged = dict(product)
    title = compact_text(product.get("title"))
    bullets = compact_text(product.get("bullet_points"))
    text = f"{title} {bullets}".lower()
    listing_days = to_float(product.get("listing_days"))
    price = to_float(product.get("price"))
    rating = to_float(product.get("rating"))
    rating_count = to_float(product.get("rating_count"))
    monthly_units = to_float(product.get("monthly_units"))
    variant_count = to_float(product.get("variant_count"))
    lqs = to_float(product.get("lqs"))
    tags = {
        "price_band": price_band(price),
        "review_band": review_band(rating_count),
        "rating_band": rating_band(rating),
        "listing_age_band": listing_age_band(listing_days),
        "monthly_units_band": monthly_units_band(monthly_units),
        "variant_band": variant_band(variant_count),
        "lqs_band": lqs_band(lqs),
        "fulfillment_band": compact_text(product.get("fulfillment")) or "未知",
        "has_a_plus": yes_no_tag(product.get("has_a_plus")),
        "has_video": yes_no_tag(product.get("has_video")),
        "product_route": product_route(text),
        "feature_tags": feature_tags(text),
    }
    tagged["attribute_tags"] = tags
    tagged["tag_confidence"] = tag_confidence(product, tags)
    tagged["tag_notes"] = tag_notes(product, tags)
    return tagged


def attribute_definitions() -> list[dict[str, str]]:
    return [
        {"dimension": "price_band", "label": "价格带", "rule": "<15、15-20、20-30、30+ USD"},
        {"dimension": "review_band", "label": "评论门槛", "rule": "0-50、51-200、201-1000、1000+ 评分数"},
        {"dimension": "rating_band", "label": "评分层级", "rule": "<4.0、4.0-4.3、4.3-4.6、4.6+"},
        {"dimension": "listing_age_band", "label": "上架时间", "rule": "近半年、半年-2年、2年以上"},
        {"dimension": "monthly_units_band", "label": "销量层级", "rule": "0、1-100、101-500、501-1000、1000+"},
        {"dimension": "variant_band", "label": "变体复杂度", "rule": "无/少变体、中变体、多变体"},
        {
            "dimension": "product_route",
            "label": "产品路线",
            "rule": "按标题和卖点识别通用结构特征：套装/组合、可伸缩/长杆、替换件/耗材、便携/迷你、专业/重型等。",
        },
    ]


def price_band(value: float | None) -> str:
    if value is None:
        return "未知"
    if value < 15:
        return "<15"
    if value < 20:
        return "15-20"
    if value < 30:
        return "20-30"
    return "30+"


def review_band(value: float | None) -> str:
    if value is None:
        return "未知"
    if value <= 50:
        return "0-50"
    if value <= 200:
        return "51-200"
    if value <= 1000:
        return "201-1000"
    return "1000+"


def rating_band(value: float | None) -> str:
    if value is None:
        return "未知"
    if value < 4.0:
        return "<4.0"
    if value < 4.3:
        return "4.0-4.3"
    if value < 4.6:
        return "4.3-4.6"
    return "4.6+"


def listing_age_band(value: float | None) -> str:
    if value is None:
        return "未知"
    if value <= 180:
        return "近半年"
    if value <= 730:
        return "半年-2年"
    return "2年以上"


def monthly_units_band(value: float | None) -> str:
    if value is None:
        return "未知"
    if value <= 0:
        return "0"
    if value <= 100:
        return "1-100"
    if value <= 500:
        return "101-500"
    if value <= 1000:
        return "501-1000"
    return "1000+"


def variant_band(value: float | None) -> str:
    if value is None:
        return "未知"
    if value <= 1:
        return "无/少变体"
    if value <= 5:
        return "中变体"
    return "多变体"


def lqs_band(value: float | None) -> str:
    if value is None:
        return "未知"
    if value >= 8:
        return "高"
    if value >= 6:
        return "中"
    return "低"


def yes_no_tag(value: Any) -> str:
    text = compact_text(value).lower()
    if text in {"是", "yes", "true", "1", "y"}:
        return "是"
    if text in {"否", "no", "false", "0", "n"}:
        return "否"
    return compact_text(value) or "未知"


def product_route(text: str) -> str:
    routes = []
    if any(token in text for token in ["2 in 1", "3 in 1", "two in one", "three in one", "combo", "bundle", "set", "kit", "pack"]):
        routes.append("套装/组合")
    if any(token in text for token in ["extendable", "telescopic", "extension pole", "long handle", "pole"]):
        routes.append("可伸缩/长杆")
    if any(token in text for token in ["replacement", "refill", "extra", "spare", "compatible"]):
        routes.append("替换件/耗材")
    if any(token in text for token in ["portable", "compact", "mini", "travel", "foldable", "folding"]):
        routes.append("便携/折叠")
    if any(token in text for token in ["heavy duty", "professional", "commercial", "industrial"]):
        routes.append("专业/重型")
    if not routes:
        return "待确认"
    return "+".join(routes[:3])


def feature_tags(text: str) -> list[str]:
    tags = []
    for token, label in [
        ("extendable", "可伸缩/长杆"),
        ("telescopic", "可伸缩/长杆"),
        ("extension pole", "可伸缩/长杆"),
        ("long handle", "可伸缩/长杆"),
        ("2 in 1", "多功能组合"),
        ("3 in 1", "多功能组合"),
        ("combo", "多功能组合"),
        ("bundle", "套装"),
        ("kit", "套装"),
        ("set", "套装"),
        ("replacement", "替换件/耗材"),
        ("refill", "替换件/耗材"),
        ("portable", "便携"),
        ("compact", "便携"),
        ("foldable", "折叠"),
        ("folding", "折叠"),
        ("heavy duty", "专业/重型"),
        ("professional", "专业/重型"),
        ("reflective", "反光/安全"),
        ("waterproof", "防水"),
        ("rechargeable", "可充电"),
        ("wireless", "无线"),
        ("adjustable", "可调节"),
    ]:
        if token in text and label not in tags:
            tags.append(label)
    return tags or ["待确认"]


def tag_confidence(product: dict[str, Any], tags: dict[str, Any]) -> str:
    missing_core = sum(1 for field in ("title", "price", "monthly_units", "rating", "rating_count", "listing_days") if is_blank(product.get(field)))
    if missing_core >= 3:
        return "低"
    if "未知" in {tags.get("price_band"), tags.get("review_band"), tags.get("listing_age_band")}:
        return "中"
    return "高"


def tag_notes(product: dict[str, Any], tags: dict[str, Any]) -> list[str]:
    notes = []
    if tags.get("product_route") == "待确认":
        notes.append("产品路线仅按标题/卖点弱识别，需人工抽查。")
    if compact_text(product.get("parent_asin")):
        notes.append("存在父 ASIN，需注意多变体口径。")
    return notes
