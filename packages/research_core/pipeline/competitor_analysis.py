"""Competitor deep-dive analysis — grouping and traffic word extraction."""

from __future__ import annotations

from typing import Any


def _competitor_items(items: Any) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        return []
    result = []
    for item in items:
        if not isinstance(item, dict):
            continue
        result.append(
            {
                "asin": item.get("asin"),
                "title": item.get("title"),
                "brand": item.get("brand"),
                "seller": item.get("seller"),
                "price": item.get("price"),
                "monthly_units": item.get("monthly_units"),
                "monthly_revenue_usd": item.get("monthly_revenue_usd"),
                "units_share": item.get("units_share"),
                "bsr": item.get("bsr"),
                "rating": item.get("rating"),
                "rating_count": item.get("rating_count"),
                "listing_date": item.get("listing_date"),
                "listing_days": item.get("listing_days"),
                "note": item.get("note"),
                "url": item.get("url"),
            }
        )
    return result

def _build_competitor_deep_dive(competitor_candidates: dict[str, Any], sorftime_traffic: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Build raw competitor data cards for Claude to analyze.

    No analysis text is generated here — learnable points, barriers, and
    strategic notes are for Claude to assess in conversation.
    """
    cards: list[dict[str, Any]] = []
    seen_asins: set[str] = set()

    def add_card(item: dict[str, Any], card_type: str) -> None:
        asin = str(item.get("asin") or "").strip()
        if not asin or asin in seen_asins:
            return
        seen_asins.add(asin)
        cards.append({
            "asin": asin,
            "card_type": card_type,
            "title": item.get("title"),
            "brand": item.get("brand"),
            "price_usd": item.get("price"),
            "monthly_units": item.get("monthly_units"),
            "rating": item.get("rating"),
            "rating_count": item.get("rating_count"),
            "listing_days": item.get("listing_days"),
            "note": item.get("note"),
            "url": item.get("url"),
            "market_boundary_status": item.get("market_boundary_status", "相关"),
            "market_boundary_reason": item.get("market_boundary_reason", ""),
            "traffic_keywords": _traffic_keywords_for_asin(sorftime_traffic, asin),
            "traffic_mixed_warnings": _traffic_warnings_for_asin(sorftime_traffic, asin),
        })

    for item in (competitor_candidates.get("top10") or [])[:3]:
        add_card(item, "标杆老品")
    for item in (competitor_candidates.get("recent_winners") or [])[:2]:
        add_card(item, "近半年新品")

    return cards

def _traffic_keywords_for_asin(sorftime_traffic: dict[str, Any] | None, asin: str) -> list[dict[str, Any]]:
    traffic = _traffic_item_for_asin(sorftime_traffic, asin)
    if not traffic:
        return []
    words = traffic.get("top_traffic_words") if isinstance(traffic.get("top_traffic_words"), list) else []
    return [item for item in words if isinstance(item, dict)][:8]

def _traffic_warnings_for_asin(sorftime_traffic: dict[str, Any] | None, asin: str) -> list[str]:
    traffic = _traffic_item_for_asin(sorftime_traffic, asin)
    if not traffic:
        return []
    warnings = traffic.get("mixed_pool_warning") if isinstance(traffic.get("mixed_pool_warning"), list) else []
    return [str(item) for item in warnings if item][:8]

def _traffic_item_for_asin(sorftime_traffic: dict[str, Any] | None, asin: str) -> dict[str, Any]:
    if not isinstance(sorftime_traffic, dict) or not asin:
        return {}
    if str(sorftime_traffic.get("asin") or "") == asin:
        return sorftime_traffic
    items = sorftime_traffic.get("asins") if isinstance(sorftime_traffic.get("asins"), list) else []
    for item in items:
        if isinstance(item, dict) and str(item.get("asin") or "") == asin:
            return item
    return {}
