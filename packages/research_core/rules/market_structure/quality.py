"""Top100 数据质量检查（从 market_structure_rules.py 拆分，纯移动不改逻辑）。"""

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
