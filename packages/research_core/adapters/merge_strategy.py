"""Field priority rules and merge logic for multi-source product data."""

from __future__ import annotations

from typing import Any

from packages.research_core.schema import NormalizedProduct, NormalizedKeyword, FieldSource


# 两源都有时的优先规则。"any" 表示取第一个非 None 值。
FIELD_PRIORITY: dict[str, str] = {
    # 卖家精灵优先（精度更高）
    "monthly_units":        "seller_sprite",
    "monthly_revenue_usd":  "seller_sprite",
    "lqs":                  "seller_sprite",
    "listing_days":         "seller_sprite",
    "listing_date":         "seller_sprite",
    "has_a_plus":           "seller_sprite",
    "has_video":            "seller_sprite",
    "bullet_points":        "seller_sprite",
    "parent_asin":          "seller_sprite",
    "bsr":                  "seller_sprite",
    "seller":               "seller_sprite",
    "seller_location":      "seller_sprite",
    "weight":               "seller_sprite",
    "size":                 "seller_sprite",
    "package_weight":       "seller_sprite",
    "package_size":         "seller_sprite",
    "variant_count":        "seller_sprite",
    # Sorftime 优先（实时/独有）
    "cpc":                  "sorftime",
    "trend_direction":      "sorftime",
    "trend_24m":            "sorftime",
    "seasonality":          "sorftime",
    "competitor_count":     "sorftime",
    # 任意源都可（取第一个非 None 值）
    "price":                "any",
    "rating":               "any",
    "rating_count":         "any",
    "brand":                "any",
    "category":             "any",
    "fulfillment":          "any",
    "title":                "any",
    "url":                  "any",
}

# 仅卖家精灵提供的字段，Sorftime 模式下缺失时补充 data_quality 警告
SS_ONLY_FIELDS: list[tuple[str, str]] = [
    ("lqs",       "Listing 质量分（LQS）"),
    ("has_a_plus", "A+ 页面"),
    ("has_video",  "视频介绍"),
    ("listing_days", "上架天数"),
]


def _pick(field: str, ss_val: Any, sf_val: Any) -> Any:
    priority = FIELD_PRIORITY.get(field, "any")
    if priority == "seller_sprite":
        return ss_val if ss_val is not None else sf_val
    if priority == "sorftime":
        return sf_val if sf_val is not None else ss_val
    return ss_val if ss_val is not None else sf_val


def merge_products(
    ss_products: list[NormalizedProduct],
    sf_products: list[NormalizedProduct],
) -> list[NormalizedProduct]:
    """按 ASIN 合并两源产品列表，字段按 FIELD_PRIORITY 取优先值。

    SS 有而 SF 无的 ASIN 直接保留；SF 有而 SS 无的 ASIN 也直接保留。
    """
    ss_by_asin = {p.asin: p for p in ss_products if p.asin}
    sf_by_asin = {p.asin: p for p in sf_products if p.asin}
    all_asins = list(ss_by_asin.keys()) + [a for a in sf_by_asin if a not in ss_by_asin]

    merged: list[NormalizedProduct] = []
    for asin in all_asins:
        ss = ss_by_asin.get(asin)
        sf = sf_by_asin.get(asin)
        if ss is None:
            merged.append(sf)  # type: ignore[arg-type]
            continue
        if sf is None:
            merged.append(ss)
            continue

        sources: dict[str, FieldSource] = {}

        def pick(f: str) -> Any:
            sv = getattr(ss, f, None)
            fv = getattr(sf, f, None)
            val = _pick(f, sv, fv)
            winner = "seller_sprite" if val == sv else "sorftime"
            conf = "high" if winner == "seller_sprite" else "medium"
            if val is not None:
                sources[f] = FieldSource(source=winner, confidence=conf)
            return val

        p = NormalizedProduct(
            asin=asin,
            title=pick("title"),
            brand=pick("brand"),
            parent_asin=pick("parent_asin"),
            category=pick("category"),
            price=pick("price"),
            monthly_units=pick("monthly_units"),
            monthly_revenue_usd=pick("monthly_revenue_usd"),
            rating=pick("rating"),
            rating_count=pick("rating_count"),
            listing_date=pick("listing_date"),
            listing_days=pick("listing_days"),
            fulfillment=pick("fulfillment"),
            lqs=pick("lqs"),
            variant_count=pick("variant_count"),
            has_a_plus=pick("has_a_plus"),
            has_video=pick("has_video"),
            bullet_points=pick("bullet_points"),
            bsr=pick("bsr"),
            seller=pick("seller"),
            seller_location=pick("seller_location"),
            weight=pick("weight"),
            size=pick("size"),
            package_weight=pick("package_weight"),
            package_size=pick("package_size"),
            url=pick("url"),
            data_freshness=ss.data_freshness or sf.data_freshness,
            note=ss.note or sf.note,
            _field_sources=sources,
        )
        merged.append(p)

    return merged


def sorftime_only_warnings(products: list[NormalizedProduct]) -> list[str]:
    """仅 Sorftime 数据时，检查 SS 专有字段缺失并返回警告列表。"""
    if not products:
        return []
    warnings = []
    for field_key, label in SS_ONLY_FIELDS:
        missing = sum(1 for p in products if getattr(p, field_key, None) is None)
        if missing == len(products):
            warnings.append(f"⚠️ {label}（{field_key}）：当前数据来自 Sorftime，该字段不可用，相关维度评估受限。")
    return warnings
