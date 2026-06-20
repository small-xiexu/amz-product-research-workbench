"""Market data text formatters — pure data-to-string, no business judgment."""

from __future__ import annotations

from typing import Any


def _market_size_text(candidate: dict[str, Any]) -> str:
    demand = candidate.get("demand_evidence", {})
    competition = candidate.get("competition_structure", {})
    category_report = demand.get("sorftime_category_report", {})
    parts = []
    if competition.get("sample_product_count") is not None:
        parts.append(f"样本商品数 {_fmt_number(competition.get('sample_product_count'))}")
    if demand.get("market_avg_monthly_units") is not None:
        parts.append(f"市场月均销量 {_fmt_number(demand.get('market_avg_monthly_units'))}")
    if demand.get("market_avg_monthly_revenue_usd") is not None:
        parts.append(f"市场月均销售额 USD {_fmt_number(demand.get('market_avg_monthly_revenue_usd'))}")
    if competition.get("top10_avg_monthly_units") is not None:
        parts.append(f"Top10 月均销量 {_fmt_number(competition.get('top10_avg_monthly_units'))}")
    if isinstance(category_report, dict) and category_report.get("product_count"):
        parts.append(
            f"Sorftime category_report 样本 {category_report.get('product_count')} 个"
            + (f"，总月销量 {_fmt_number(category_report.get('total_monthly_units'))}" if category_report.get("total_monthly_units") is not None else "")
        )
    return "；".join(parts) if parts else "待填"

def _price_band_text(candidate: dict[str, Any]) -> str:
    demand = candidate.get("demand_evidence", {})
    price_context = candidate.get("price_band_context", {}) if isinstance(candidate.get("price_band_context"), dict) else {}
    category_report = demand.get("sorftime_category_report", {})
    parts = []
    if price_context.get("top_price_band_by_units"):
        parts.append(f"销量集中价格带 {price_context.get('top_price_band_by_units')} USD")
    if price_context.get("top_price_band_units_share") is not None:
        parts.append(f"该价格带销量占比 {_fmt_percent(price_context.get('top_price_band_units_share'))}")
    if demand.get("market_avg_price_usd") is not None:
        parts.append(f"市场平均价 USD {_fmt_number(demand.get('market_avg_price_usd'))}")
    if isinstance(category_report, dict) and category_report.get("avg_price_usd") is not None:
        parts.append(f"Sorftime 均价 USD {_fmt_number(category_report.get('avg_price_usd'))}")
    return "；".join(parts) if parts else "待填"

def _brand_concentration_text(candidate: dict[str, Any]) -> str:
    competition = candidate.get("competition_structure", {})
    category_report = candidate.get("demand_evidence", {}).get("sorftime_category_report", {})
    top_brand = competition.get("top_brand")
    top_share = competition.get("top_brand_units_share")
    top10_share = competition.get("top10_product_units_share")
    parts = []
    if top_brand:
        parts.append(f"头部品牌 {top_brand} 销量占比 {_fmt_percent(top_share)}")
    if top10_share is not None:
        parts.append(f"Top10 商品销量占比 {_fmt_percent(top10_share)}")
    if isinstance(category_report, dict) and category_report.get("top10_units_share") is not None:
        parts.append(f"Sorftime Top10 销量占比 {_fmt_percent(category_report.get('top10_units_share'))}")
    return "；".join(parts) if parts else "待填"

def _seller_concentration_text(candidate: dict[str, Any]) -> str:
    competition = candidate.get("competition_structure", {})
    location = competition.get("top_seller_location")
    share = competition.get("top_seller_location_units_share")
    if location:
        return f"主要卖家所在地 {location}，销量占比 {_fmt_percent(share)}"
    return "待填"

def _new_listing_text(candidate: dict[str, Any]) -> str:
    new_listing = candidate.get("new_listing_opportunity", {})
    category_report = candidate.get("demand_evidence", {}).get("sorftime_category_report", {})
    parts = []
    if new_listing.get("new_listing_count_6m") is not None:
        parts.append(f"近半年新品 {new_listing.get('new_listing_count_6m')} 个")
    if new_listing.get("new_listing_avg_monthly_units") is not None:
        parts.append(f"近半年新品月均销量 {_fmt_number(new_listing.get('new_listing_avg_monthly_units'))}")
    if new_listing.get("recent_6m_units_share") is not None:
        parts.append(f"近半年新品销量占比 {_fmt_percent(new_listing.get('recent_6m_units_share'))}")
    if isinstance(category_report, dict) and category_report.get("new_product_count_6m") is not None:
        parts.append(
            f"Sorftime 近半年新品 {category_report.get('new_product_count_6m')} 个"
            + (f"，销量占比 {_fmt_percent(category_report.get('new_product_units_share'))}" if category_report.get("new_product_units_share") is not None else "")
        )
    return "；".join(parts) if parts else "待填"

def _return_rate_text(candidate: dict[str, Any]) -> str:
    return_risk = candidate.get("return_risk", {})
    market_rate = return_risk.get("market_return_rate")
    category_rate = return_risk.get("category_return_rate")
    if market_rate is None and category_rate is None:
        return "待填"
    return f"市场退货率 {_fmt_percent(market_rate)}；类目退货率 {_fmt_percent(category_rate)}"

def _fmt_number(value: Any) -> str:
    if value is None:
        return "待填"
    if isinstance(value, (int, float)):
        if abs(value) >= 1000:
            return f"{value:,.0f}"
        if value == int(value):
            return str(int(value))
        return f"{value:.2f}"
    return str(value)

def _fmt_percent(value: Any) -> str:
    if value is None:
        return "待填"
    if isinstance(value, (int, float)):
        percent_value = value * 100 if -1 <= value <= 1 else value
        return f"{percent_value:.2f}%"
    text = str(value)
    return text if "%" in text else text + "%"

def _join_text(*parts: Any) -> str:
    cleaned = [str(part).strip().rstrip("。；;") for part in parts if part not in (None, "")]
    return "；".join(part for part in cleaned if part)


def _positive_count(value: Any) -> int:
    if isinstance(value, bool) or value is None:
        return 0
    if isinstance(value, (int, float)):
        return int(value) if value > 0 else 0
    if isinstance(value, str):
        normalized = value.replace(",", "").strip()
        if normalized.isdigit():
            return int(normalized)
    return 0


def _market_structure_summary_line(candidate: dict[str, Any]) -> str:
    market_structure = candidate.get("market_structure", {})
    summary = market_structure.get("summary", {}) if isinstance(market_structure, dict) else {}
    if summary.get("quality_summary"):
        return f"数据质量：{summary.get('quality_summary')}"
    return ""
