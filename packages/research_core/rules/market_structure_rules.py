"""Market structure rules for Top product quality checks and basic tagging."""

from __future__ import annotations

from collections import Counter, defaultdict
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


def build_market_structure_analysis(products: list[dict[str, Any]], expected_count: int = 100) -> dict[str, Any]:
    """Build conservative quality checks, tags, distributions, and cross-analysis."""
    tagged_products = [tag_product(product) for product in products]
    quality = build_data_quality(tagged_products, expected_count)
    distributions = build_attribute_distributions(tagged_products)
    cross_analysis = build_cross_analysis(tagged_products)
    return {
        "summary": build_summary(quality, distributions, cross_analysis),
        "data_quality": quality,
        "attribute_definitions": attribute_definitions(),
        "attribute_distributions": distributions,
        "cross_analysis": cross_analysis,
        "tagged_products": tagged_products,
    }


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


def build_data_quality(products: list[dict[str, Any]], expected_count: int) -> dict[str, Any]:
    total = len(products)
    asin_values = [compact_text(product.get("asin")) for product in products if compact_text(product.get("asin"))]
    parent_values = [compact_text(product.get("parent_asin")) for product in products if compact_text(product.get("parent_asin"))]
    duplicate_asins = sorted(value for value, count in Counter(asin_values).items() if count > 1)
    duplicate_parent_asins = sorted(value for value, count in Counter(parent_values).items() if count > 1)
    missing = []
    for field, label in REQUIRED_PRODUCT_FIELDS:
        count = sum(1 for product in products if is_blank(product.get(field)))
        if count:
            missing.append({"field": field, "label": label, "missing_count": count, "missing_rate": safe_rate(count, total)})
    abnormal = abnormal_items(products)
    warnings = []
    if total < expected_count:
        warnings.append(f"商品明细只有 {total} 条，少于正式深挖要求的 Top{expected_count}，当前只能做基础结构分析。")
    if expected_count and total > expected_count:
        warnings.append(f"商品明细 {total} 条超过 Top{expected_count}，通常来自多关键词合并；统计应按去重商品池口径解释。")
    if duplicate_asins:
        warnings.append(f"存在重复 ASIN {len(duplicate_asins)} 个，需要确认是否为导出重复。")
    if duplicate_parent_asins:
        warnings.append(f"存在父 ASIN 重复 {len(duplicate_parent_asins)} 个，需注意多变体口径。")
    for item in missing:
        if item["missing_rate"] >= 0.2:
            warnings.append(f"{item['label']} 缺失率 {format_percent(item['missing_rate'])}，相关判断只能写弱结论。")
    if abnormal:
        warnings.append(f"发现 {len(abnormal)} 类异常值线索，需要人工复核。")
    completeness_score = quality_score(total, expected_count, missing, duplicate_asins, abnormal)
    return {
        "expected_count": expected_count,
        "actual_count": total,
        "completeness_rate": min(safe_rate(total, expected_count), 1),
        "unique_asin_count": len(set(asin_values)),
        "duplicate_asins": duplicate_asins[:20],
        "duplicate_parent_asins": duplicate_parent_asins[:20],
        "missing_fields": missing,
        "abnormal_items": abnormal,
        "warnings": warnings,
        "quality_score": completeness_score,
        "level": quality_level(completeness_score),
    }


def abnormal_items(products: list[dict[str, Any]]) -> list[dict[str, Any]]:
    checks = [
        ("price", "价格小于等于0", lambda value: value is not None and value <= 0),
        ("monthly_units", "月销量小于0", lambda value: value is not None and value < 0),
        ("rating", "评分不在0-5之间", lambda value: value is not None and (value < 0 or value > 5)),
        ("rating_count", "评分数小于0", lambda value: value is not None and value < 0),
        ("listing_days", "上架天数小于0", lambda value: value is not None and value < 0),
    ]
    result = []
    for field, label, predicate in checks:
        count = sum(1 for product in products if predicate(to_float(product.get(field))))
        if count:
            result.append({"field": field, "label": label, "count": count})
    return result


def quality_score(
    total: int,
    expected_count: int,
    missing: list[dict[str, Any]],
    duplicate_asins: list[str],
    abnormal: list[dict[str, Any]],
) -> int:
    score = 100
    if expected_count:
        score -= int(max(0, 1 - min(total / expected_count, 1)) * 40)
    score -= min(20, len(duplicate_asins) * 2)
    score -= min(20, sum(1 for item in missing if item["missing_rate"] >= 0.2) * 5)
    score -= min(20, len(abnormal) * 5)
    return max(0, min(100, score))


def quality_level(score: int) -> str:
    if score >= 85:
        return "高"
    if score >= 70:
        return "中"
    return "低"


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
            "listing_age_band",
            "review_band",
            "上架时间 x 评论门槛",
            "识别近半年新品是否已经跨过评论门槛，避免把低评论新品误判成机会。",
        ),
        cross_dimension(
            products,
            "price_band",
            "monthly_units_band",
            "价格带 x 销量层级",
            "判断销量是否集中在低价带，或中高价是否仍有成交空间。",
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
            "monthly_units_band",
            "产品路线 x 销量层级",
            "判断不同功能路线的供给和销量信号，低样本路线只作线索。",
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


def build_summary(quality: dict[str, Any], distributions: list[dict[str, Any]], cross_analysis: list[dict[str, Any]]) -> dict[str, Any]:
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
        "warnings": quality.get("warnings", []),
    }


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


def bucket_value(distributions: list[dict[str, Any]], dimension: str) -> str:
    for item in distributions:
        if item.get("dimension") == dimension and item.get("buckets"):
            bucket = item["buckets"][0]
            return f"{bucket.get('value')}（{bucket.get('count')}，{format_percent(bucket.get('share'))}）"
    return ""


def opportunity_clues(cross_analysis: list[dict[str, Any]]) -> list[str]:
    clues = []
    for analysis in cross_analysis:
        for cell in analysis.get("cells", [])[:5]:
            if cell.get("count", 0) <= 5 and (cell.get("avg_monthly_units") or 0) >= 100:
                clues.append(f"{analysis.get('label')}：{cell.get('row')} x {cell.get('column')} 样本少但有销量，需确认是否真机会。")
            if len(clues) >= 5:
                return clues
    return clues or ["当前先输出结构线索，机会判断需结合完整 Top100、评论和利润复核。"]


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
    return "作为结构分布参考，需结合评论、关键词和利润复核。"


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
