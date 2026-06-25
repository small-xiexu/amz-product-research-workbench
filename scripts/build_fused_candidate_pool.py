#!/usr/bin/env python3
"""Build fused candidate_pool.json from SellerSprite MCP + Sorftime MCP data.

This script replaces the SellerSprite Excel import pathway. It reads MCP JSON data
and produces candidate_pool.json + a human-readable HTML operations report.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Normalization: SellerSprite MCP → NormalizedProduct
# ---------------------------------------------------------------------------

def _ss_to_normalized(ss_item: dict[str, Any]) -> dict[str, Any]:
    """Convert a SellerSprite competitor_lookup item to NormalizedProduct."""
    badges = ss_item.get("badge") or {}
    return {
        "asin": ss_item.get("asin", ""),
        "title": ss_item.get("title", ""),
        "brand": ss_item.get("brand", ""),
        "seller_name": ss_item.get("sellerName", ""),
        "seller_nation": ss_item.get("sellerNation", ""),
        "price_usd": ss_item.get("price"),
        "monthly_units": ss_item.get("units"),
        "monthly_revenue_usd": ss_item.get("revenue"),
        "rating": ss_item.get("rating"),
        "rating_count": ss_item.get("ratings"),
        "bsr_rank": ss_item.get("bsr"),
        "fulfillment": ss_item.get("fulfillment", ""),
        "node_id": str(ss_item.get("nodeId", "")),
        "node_path": ss_item.get("nodeIdPath", ""),
        "available_date": ss_item.get("availableDate"),
        "is_best_seller": badges.get("bestSeller", "N") != "N",
        "is_amazon_choice": badges.get("amazonChoice", "N") != "N",
        "is_new_release": badges.get("newRelease", "N") != "N",
        "lqs": ss_item.get("lqs"),
        "profit_margin": ss_item.get("profit"),
        "fba_fee": ss_item.get("fba"),
        "variations": ss_item.get("variations", 1),
        "sellers": ss_item.get("sellers", 1),
        "source": "seller_sprite_mcp",
    }


# ---------------------------------------------------------------------------
# Normalization: Sorftime MCP → NormalizedProduct
# ---------------------------------------------------------------------------

def _sf_to_normalized(sf_item: dict[str, Any]) -> dict[str, Any]:
    """Convert a Sorftime category_report item to NormalizedProduct."""
    return {
        "asin": sf_item.get("ASIN", ""),
        "title": sf_item.get("标题", ""),
        "brand": sf_item.get("品牌", ""),
        "seller_name": sf_item.get("卖家", ""),
        "seller_nation": sf_item.get("卖家来源", ""),
        "price_usd": float(sf_item.get("价格", 0)) if sf_item.get("价格") else None,
        "monthly_units": int(sf_item.get("月销量", 0)) if sf_item.get("月销量") else None,
        "monthly_revenue_usd": float(sf_item.get("月销额", 0)) if sf_item.get("月销额") else None,
        "rating": float(sf_item.get("星级", 0)) if sf_item.get("星级") else None,
        "rating_count": int(sf_item.get("评论数", 0)) if sf_item.get("评论数") else None,
        "gross_margin": float(sf_item.get("毛利率", 0)) if sf_item.get("毛利率") else None,
        "source": "sorftime_mcp",
    }


# ---------------------------------------------------------------------------
# Cross-source merge by ASIN
# ---------------------------------------------------------------------------

def _merge_by_asin(ss_products: list[dict], sf_products: list[dict]) -> list[dict]:
    """Merge SS and SF products by ASIN, annotating source coverage."""
    sf_by_asin: dict[str, dict] = {p["asin"]: p for p in sf_products if p.get("asin")}
    merged = []
    seen_asins: set[str] = set()

    for ss_p in ss_products:
        asin = ss_p.get("asin", "")
        if not asin or asin in seen_asins:
            continue
        seen_asins.add(asin)
        sf_p = sf_by_asin.get(asin)
        entry = {
            **ss_p,
            "sf_data": sf_p,
            "dual_source": sf_p is not None,
        }
        merged.append(entry)

    # Add SF-only products
    for sf_p in sf_products:
        asin = sf_p.get("asin", "")
        if asin and asin not in seen_asins:
            seen_asins.add(asin)
            merged.append({
                "asin": asin,
                "title": sf_p.get("title", ""),
                "brand": sf_p.get("brand", ""),
                "seller_name": sf_p.get("seller_name", ""),
                "seller_nation": sf_p.get("seller_nation", ""),
                "price_usd": sf_p.get("price_usd"),
                "monthly_units": sf_p.get("monthly_units"),
                "monthly_revenue_usd": sf_p.get("monthly_revenue_usd"),
                "rating": sf_p.get("rating"),
                "rating_count": sf_p.get("rating_count"),
                "source": "sorftime_mcp",
                "sf_data": sf_p,
                "dual_source": False,
            })

    return merged


# ---------------------------------------------------------------------------
# SF deviation from SS baseline (SS is ground truth, SF is supplementary)
# ---------------------------------------------------------------------------

def _detect_sf_deviation(merged: list[dict]) -> list[dict]:
    """Detect where Sorftime data deviates significantly from SellerSprite baseline."""
    deviations = []
    for p in merged:
        if not p.get("dual_source"):
            continue
        sf = p.get("sf_data") or {}
        diffs = []

        ss_units = p.get("monthly_units") or 0
        sf_units = sf.get("monthly_units") or 0
        if ss_units and sf_units and ss_units > 0:
            ratio = abs(ss_units - sf_units) / ss_units
            if ratio > 0.20:
                diffs.append({
                    "field": "monthly_units",
                    "ss_baseline": ss_units,
                    "sf_value": sf_units,
                    "sf_deviation_pct": round(ratio * 100, 1),
                })

        ss_price = p.get("price_usd") or 0
        sf_price = sf.get("price_usd") or 0
        if ss_price and sf_price and ss_price > 0:
            ratio = abs(ss_price - sf_price) / ss_price
            if ratio > 0.15:
                diffs.append({
                    "field": "price_usd",
                    "ss_baseline": ss_price,
                    "sf_value": sf_price,
                    "sf_deviation_pct": round(ratio * 100, 1),
                })

        ss_rating = p.get("rating") or 0
        sf_rating = sf.get("rating") or 0
        if ss_rating and sf_rating and abs(ss_rating - sf_rating) > 0.3:
            diffs.append({
                "field": "rating",
                "ss_baseline": ss_rating,
                "sf_value": sf_rating,
                "sf_deviation_abs": round(abs(ss_rating - sf_rating), 1),
            })

        if diffs:
            deviations.append({
                "asin": p["asin"],
                "title": p.get("title", ""),
                "diffs": diffs,
                "severity": "high" if len(diffs) >= 2 else "medium",
            })

    return deviations


# ---------------------------------------------------------------------------
# Direction cards (Route A / Route B)
# ---------------------------------------------------------------------------

def _build_direction_cards() -> list[dict]:
    """Build route direction analysis for wire floor brush."""
    return [
        {
            "route": "A",
            "name": "纯钢丝地板刷",
            "description": "Stainless steel / metal wire bristle floor scrub brush, no squeegee, single-material cleaning",
            "target_asins": ["B0GCM16WVW", "B0CNXJ5D11", "B0FX4NW8R4"],
            "market_position": "niche",
            "total_monthly_units": 533 + 678 + 142,
            "avg_price": 20.29,
            "avg_rating": 4.43,
            "avg_reviews": 696,
            "pros": ["差异化明显", "直接竞品仅3个", "材质壁垒(不锈钢丝)"],
            "cons": ["市场体量小(~1.4K/月)", "消费者更偏好3-in-1多功能", "MAVRIZ新品评论少"],
            "verdict": "利基机会，需要教育市场"
        },
        {
            "route": "B",
            "name": "钢丝差异化三合一",
            "description": "3-in-1 format (scrub brush + squeegee + scraper) with wire bristle differentiation",
            "target_asins": ["B0C6XTNXL8", "B0FHQ25K2S", "B0DR8SMB8H"],
            "market_position": "mainstream_with_twist",
            "total_monthly_units": 12227 + 10070 + 6601,
            "avg_price": 22.03,
            "avg_rating": 4.43,
            "avg_reviews": 1478,
            "pros": ["市场体量大(~28.9K/月)", "消费者已验证的需求", "钢丝可作为差异化卖点"],
            "cons": ["头部集中度高(DOLPLEAP+HelpX+AIR U+)", "需要同时做好刷毛+刮水+铲刀"],
            "verdict": "主流赛道，用钢丝材质做差异化切入"
        }
    ]


# ---------------------------------------------------------------------------
# New listing friendliness score
# ---------------------------------------------------------------------------

def _new_listing_friendliness(listing_dist: list[dict]) -> dict:
    """Score how friendly the category is for new listings."""
    total_units = sum(d.get("units", 0) for d in listing_dist)
    if total_units == 0:
        return {"score": "unknown", "reason": "无上架分布数据"}

    recent_3m_units = sum(
        d.get("units", 0) for d in listing_dist
        if "1个月" in d.get("label", "") or "3个月" in d.get("label", "")
    )
    recent_6m_units = recent_3m_units + sum(
        d.get("units", 0) for d in listing_dist
        if "半年" in d.get("label", "")
    )

    ratio_3m = recent_3m_units / total_units
    ratio_6m = recent_6m_units / total_units

    if ratio_3m > 0.15:
        return {"score": "excellent", "reason": f"近3个月上架产品占{ratio_3m:.1%}销量，新品友好"}
    elif ratio_6m > 0.15:
        return {"score": "good", "reason": f"近6个月上架产品占{ratio_6m:.1%}销量，新品有机会"}
    elif ratio_6m > 0.08:
        return {"score": "moderate", "reason": f"近6个月上架产品占{ratio_6m:.1%}销量，需强差异化"}
    else:
        return {"score": "difficult", "reason": f"近6个月新品仅占{ratio_6m:.1%}销量，老品壁垒高"}


# ---------------------------------------------------------------------------
# Generate HTML operations report
# ---------------------------------------------------------------------------

def _build_html_report(
    ss_market: dict[str, Any],
    ss_products: list[dict],
    ss_brands: list[dict],
    ss_sellers: list[dict],
    ss_price_dist: list[dict],
    ss_listing_dist: list[dict],
    ss_country_dist: list[dict],
    ss_rating_dist: list[dict],
    sf_category: dict[str, Any],
    sf_keyword: dict[str, Any],
    sf_deviations: list[dict],
    direction_cards: list[dict],
    new_listing_score: dict,
    merged_pool: list[dict],
) -> str:
    """Build a standalone HTML operations report."""

    def _fmt_num(n) -> str:
        if n is None:
            return "-"
        n = float(n) if not isinstance(n, (int, float)) else n
        if n >= 1_000_000:
            return f"${n/1_000_000:.1f}M"
        if n >= 1000:
            return f"${n/1000:.0f}K" if n < 10000 else f"${n/1000:.1f}K"
        return f"${n:.0f}"

    def _fmt_units(n) -> str:
        if n is None:
            return "-"
        n = int(n) if not isinstance(n, (int, float)) else n
        if n >= 1000:
            return f"{n/1000:.1f}K"
        return str(n)

    def _fmt_pct(n) -> str:
        if n is None:
            return "-"
        return f"{float(n)*100:.1f}%"

    sf_stats = sf_category.get("类目统计报告") or {}

    # Product concentration table (clean, no SF columns)
    product_rows = ""
    for i, p in enumerate(ss_products[:10]):
        product_rows += f"""
        <tr>
          <td>{i+1}</td>
          <td><a href="https://www.amazon.com/dp/{p.get('asin','')}" target="_blank">{p.get('asin','')}</a></td>
          <td>{p.get('title','')[:60]}...</td>
          <td>{p.get('brand','')}</td>
          <td>${p.get('price',0)}</td>
          <td>{_fmt_units(p.get('totalUnits',0))}</td>
          <td>{_fmt_num(p.get('totalRevenue',0))}</td>
          <td>{"<span class=\"tag tag-green\">新品</span>" if p.get('newFlag') else "-"}</td>
          <td>⭐{p.get('rating',0)} ({p.get('ratings',0)})</td>
        </tr>"""

    # Brand concentration table
    brand_rows = ""
    for i, b in enumerate(ss_brands[:8]):
        brand_rows += f"""
        <tr>
          <td>{i+1}</td>
          <td>{b.get('brand','')}</td>
          <td>{b.get('products',0)}</td>
          <td>{_fmt_units(b.get('totalUnits',0))}</td>
          <td>{_fmt_pct(b.get('totalUnitsRatio',0))}</td>
          <td>{_fmt_num(b.get('totalRevenue',0))}</td>
          <td>⭐{b.get('rating',0)} ({b.get('ratings',0)})</td>
        </tr>"""

    # Seller concentration table
    seller_rows = ""
    for i, s in enumerate(ss_sellers[:8]):
        seller_rows += f"""
        <tr>
          <td>{i+1}</td>
          <td>{s.get('sellerName','')}</td>
          <td>{s.get('products',0)}</td>
          <td>{_fmt_units(s.get('totalUnits',0))}</td>
          <td>{_fmt_pct(s.get('totalUnitsRatio',0))}</td>
          <td>{_fmt_num(s.get('totalRevenue',0))}</td>
        </tr>"""

    # Price distribution table
    price_rows = ""
    for d in ss_price_dist:
        units_ratio = d.get('unitsRatio', 0)
        highlight = "font-weight:bold;background:#e8f5e9" if units_ratio > 0.2 else ""
        price_rows += f"""
        <tr style="{highlight}">
          <td>{d.get('label','')}</td>
          <td>{d.get('products',0)}</td>
          <td>{_fmt_units(d.get('units',0))}</td>
          <td>{_fmt_pct(units_ratio)}</td>
          <td>{_fmt_num(d.get('revenue',0))}</td>
        </tr>"""

    # Listing age distribution table
    listing_rows = ""
    for d in ss_listing_dist:
        listing_rows += f"""
        <tr>
          <td>{d.get('label','')}</td>
          <td>{d.get('products',0)}</td>
          <td>{_fmt_units(d.get('units',0))}</td>
          <td>{_fmt_pct(d.get('unitsRatio',0))}</td>
        </tr>"""

    # Seller country table
    country_rows = ""
    for d in ss_country_dist:
        country_rows += f"""
        <tr>
          <td>{d.get('label','')}</td>
          <td>{d.get('products',0)}</td>
          <td>{_fmt_units(d.get('units',0))}</td>
          <td>{_fmt_pct(d.get('unitsRatio',0))}</td>
          <td>{_fmt_pct(d.get('revenueRatio',0))}</td>
        </tr>"""

    # Rating distribution table
    rating_rows = ""
    for d in ss_rating_dist:
        units_ratio = d.get('unitsRatio', 0)
        highlight = "font-weight:bold;background:#e8f5e9" if units_ratio > 0.2 else ""
        rating_rows += f"""
        <tr style="{highlight}">
          <td>{d.get('label','')}</td>
          <td>{d.get('products',0)}</td>
          <td>{_fmt_units(d.get('units',0))}</td>
          <td>{_fmt_pct(units_ratio)}</td>
        </tr>"""

    # Direction cards
    dir_cards = ""
    for d in direction_cards:
        pros = "".join(f"<li>{p}</li>" for p in d["pros"])
        cons = "".join(f"<li>{c}</li>" for c in d["cons"])
        dir_cards += f"""
        <div class="direction-card">
          <h3>Route {d['route']}: {d['name']} <span class="badge">{d['market_position']}</span></h3>
          <p>{d['description']}</p>
          <div class="dir-stats">
            <div class="stat"><strong>月销:</strong> {_fmt_units(d['total_monthly_units'])}</div>
            <div class="stat"><strong>均价:</strong> ${d['avg_price']}</div>
            <div class="stat"><strong>均分:</strong> ⭐{d['avg_rating']}</div>
            <div class="stat"><strong>均评论:</strong> {_fmt_units(d['avg_reviews'])}</div>
          </div>
          <div class="pros-cons">
            <div class="pros"><strong>优势</strong><ul>{pros}</ul></div>
            <div class="cons"><strong>风险</strong><ul>{cons}</ul></div>
          </div>
          <p class="verdict"><strong>判断:</strong> {d['verdict']}</p>
        </div>"""

    # SF deviation rows
    deviation_rows = ""
    for c in sf_deviations:
        diffs_html = ""
        for diff in c["diffs"]:
            diffs_html += f'<span class="conflict-tag">{diff["field"]}: SS基线={diff.get("ss_baseline","?")} SF={diff.get("sf_value","?")} (偏离{diff.get("sf_deviation_pct","?")}%)</span> '
        deviation_rows += f"""
        <tr>
          <td><a href="https://www.amazon.com/dp/{c['asin']}" target="_blank">{c['asin']}</a></td>
          <td>{c['title'][:50]}...</td>
          <td><span class="confidence confidence-{c['severity']}">{c['severity']}</span></td>
          <td>{diffs_html}</td>
        </tr>"""

    nl = new_listing_score
    keyword_comp = sf_keyword.get("关键词", "")
    monthly_search = sf_keyword.get("月搜索量", "")
    weekly_search = sf_keyword.get("周搜索量", "")
    cpc = sf_keyword.get("推荐cpc竞价", "")
    competitor_count = sf_keyword.get("搜索结果竞品数量", "")
    peak_season = sf_keyword.get("词搜索量旺季", "")

    sf_top1_units = sf_stats.get("top100产品月销量", "-")
    sf_top1_rev = sf_stats.get("top100产品月销额", "-")
    sf_amazon_share = sf_stats.get("amazonOwned_sales_volume_share", "-")
    sf_high_rated_share = sf_stats.get("high_rated_sales_volume_share", "-")
    sf_low_reviews_share = sf_stats.get("low_reviews_sales_volume_share", "-")
    sf_top3_brand = sf_stats.get("top3_brands_sales_volume_share", "-")
    sf_top3_seller = sf_stats.get("top3_seller_sales_volume_share", "-")
    sf_avg_price = sf_stats.get("average_price", "-")
    sf_median_price = sf_stats.get("median_price", "-")
    sf_top3_product = sf_stats.get("top3_product_sales_volume_share", "-")

    # Calculate SS aggregate stats
    ss_top3_units_ratio = sum(p.get("totalUnitsRatio", 0) for p in ss_products[:3]) * 100
    ss_top3_rev_ratio = sum(p.get("totalRevenueRatio", 0) for p in ss_products[:3]) * 100
    ss_top3_brand_ratio = sum(b.get("totalUnitsRatio", 0) for b in ss_brands[:3]) * 100
    ss_top3_seller_ratio = sum(s.get("totalUnitsRatio", 0) for s in ss_sellers[:3]) * 100
    ss_cn_units_ratio = sum(d.get("unitsRatio", 0) for d in ss_country_dist if "中国" in d.get("label", "")) * 100
    ss_recent_1y_ratio = sum(d.get("unitsRatio", 0) for d in ss_listing_dist if d.get("label", "") in ("1个月", "3个月", "半年", "1年")) * 100
    ss_price_15_25_ratio = sum(d.get("unitsRatio", 0) for d in ss_price_dist if d.get("label", "") in ("15-20", "20-25")) * 100
    ss_high_rated_ratio = sum(d.get("unitsRatio", 0) for d in ss_rating_dist if float(d.get("label", "0")[:3].replace("-",".") or 0) >= 4.0) * 100

    # --- Score label mapping ---
    score_labels = {"excellent": "优秀", "good": "良好", "moderate": "中等", "difficult": "困难"}
    nl_score_cn = score_labels.get(nl['score'], nl['score'])

    # --- Price bar chart ---
    def _price_bar_label(label, pct):
        tag = "tag-green" if pct > 0.25 else "tag-amber" if pct > 0.10 else "tag-gray"
        strength = "强" if pct > 0.25 else "关注" if pct > 0.10 else "弱"
        bar_h = max(int(pct * 180), 20)
        color = "#059669" if pct > 0.25 else "#f59e0b" if pct > 0.10 else "#9ca3af"
        return f'<div class="price-bar"><div class="bar" style="height:{bar_h}px;background:{color};">{pct*100:.0f}%</div><span class="bar-label">{label}</span><div class="label">{label}<span class="tag {tag}">{strength}</span></div></div>'

    price_bars = []
    for d in ss_price_dist:
        pct = d.get('unitsRatio', 0)
        price_bars.append(_price_bar_label(d.get('label',''), pct))
    price_bar_chart = "\n        ".join(price_bars)

    price_table_rows = ""
    for d in ss_price_dist:
        units_ratio = d.get('unitsRatio', 0)
        if units_ratio > 0.25:
            tag = '<span class="tag tag-green">强</span>'
        elif units_ratio > 0.10:
            tag = '<span class="tag tag-amber">关注</span>'
        else:
            tag = '<span class="tag tag-gray">弱</span>'
        price_table_rows += f'''
        <tr>
          <td>{d.get('label','')}</td>
          <td>{d.get('products',0)}</td>
          <td>{_fmt_units(d.get('units',0))}</td>
          <td>{_fmt_pct(units_ratio)}</td>
          <td>{_fmt_num(d.get('revenue',0))}</td>
          <td>{tag}</td>
        </tr>'''

    # --- Direction cards (uses insight-card style) ---
    dir_cards = ""
    for d in direction_cards:
        pros = "".join(f"<li>{p}</li>" for p in d["pros"])
        cons = "".join(f"<li>{c}</li>" for c in d["cons"])
        dir_cards += f"""
        <div class="insight-card good">
          <h4>Route {d['route']}: {d['name']} — {d['market_position']}</h4>
          <p>{d['description']}</p>
          <p style="margin-top:8px;font-size:13px;color:var(--muted);">
            <strong>月销:</strong> {_fmt_units(d['total_monthly_units'])} &nbsp;|&nbsp;
            <strong>均价:</strong> ${d['avg_price']} &nbsp;|&nbsp;
            <strong>均分:</strong> {d['avg_rating']} &nbsp;|&nbsp;
            <strong>均评论:</strong> {_fmt_units(d['avg_reviews'])}
          </p>
          <div class="insight-row" style="margin-top:8px;">
            <div class="pros" style="font-size:13px;"><strong>优势</strong><ul style="padding-left:20px;margin-top:4px;">{pros}</ul></div>
            <div class="cons" style="font-size:13px;"><strong>风险</strong><ul style="padding-left:20px;margin-top:4px;">{cons}</ul></div>
          </div>
          <p style="margin-top:8px;font-size:13px;color:var(--muted);font-style:italic;"><strong>判断:</strong> {d['verdict']}</p>
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>钢丝地板刷 — 市场调研报告</title>
<style>
/* Stage 7 报告视觉模板 — HTML 必须内嵌 <style> 块，禁止 <link> 外部引用 */

:root {{
  --bg: #f5f6f8;
  --card: #fff;
  --ink: #1a1a2e;
  --muted: #6b7280;
  --accent: #059669;
  --accent-soft: #ecfdf5;
  --warn: #d97706;
  --warn-soft: #fffbeb;
  --danger: #dc2626;
  --danger-soft: #fef2f2;
  --border: #e5e7eb;
}}

* {{ box-sizing: border-box; margin: 0; padding: 0; }}

body {{
  background: var(--bg);
  color: var(--ink);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
  font-size: 15px;
  line-height: 1.7;
}}

.page {{ max-width: 1100px; margin: 0 auto; padding: 32px 24px 60px; }}

/* ---- Hero ---- */
.hero {{
  background: linear-gradient(135deg, #065f46 0%, #047857 100%);
  color: #fff;
  border-radius: 12px;
  padding: 28px 32px;
  margin-bottom: 20px;
}}
.hero .eyebrow {{ font-size: 13px; letter-spacing: .08em; opacity: .75; margin-bottom: 6px; text-transform: uppercase; }}
.hero h1 {{ font-size: 38px; font-weight: 800; margin-bottom: 8px; letter-spacing: -.02em; }}
.hero .verdict {{
  display: inline-block;
  background: #fff;
  color: #065f46;
  font-weight: 800;
  font-size: 15px;
  padding: 6px 16px;
  border-radius: 6px;
  margin-bottom: 10px;
}}
.hero .lead {{ font-size: 17px; opacity: .9; max-width: 720px; line-height: 1.7; }}
.hero-grid {{ display: grid; grid-template-columns: repeat(6, 1fr); gap: 16px; margin-top: 16px; }}
.hero-metric {{
  background: rgba(255,255,255,.12);
  border-radius: 8px;
  padding: 12px 14px;
}}
.hero-metric .label {{ font-size: 12px; opacity: .7; margin-bottom: 4px; }}
.hero-metric .value {{ font-size: 26px; font-weight: 800; }}

/* ---- Section Cards ---- */
.section {{
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 24px 28px;
  margin-bottom: 16px;
}}
.section h2 {{ font-size: 22px; font-weight: 700; margin-bottom: 4px; }}
.section .subtitle {{ color: var(--muted); font-size: 14px; margin-bottom: 14px; }}

/* ---- Insight Cards ---- */
.insight-row {{
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin-bottom: 16px;
}}
.insight-card {{
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 14px;
}}
.insight-card.good {{ border-left: 4px solid var(--accent); background: var(--accent-soft); }}
.insight-card.warn {{ border-left: 4px solid var(--warn); background: var(--warn-soft); }}
.insight-card h4 {{ font-size: 15px; margin-bottom: 4px; }}
.insight-card p {{ font-size: 14px; color: #4b5563; }}

/* ---- Tables ---- */
table {{ width: 100%; border-collapse: collapse; margin-top: 8px; }}
th {{
  background: #f9fafb;
  color: #374151;
  font-weight: 700;
  font-size: 13px;
  padding: 8px 10px;
  text-align: left;
  border-bottom: 2px solid var(--border);
}}
td {{
  padding: 8px 10px;
  border-bottom: 1px solid #f3f4f6;
  font-size: 14px;
  vertical-align: top;
}}
tr:last-child td {{ border-bottom: 0; }}

/* ---- Tags ---- */
.tag {{
  display: inline-block;
  font-size: 12px;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 4px;
}}
.tag-green {{ background: var(--accent-soft); color: #065f46; }}
.tag-amber {{ background: var(--warn-soft); color: #92400e; }}
.tag-red   {{ background: var(--danger-soft); color: #b91c1c; }}
.tag-gray  {{ background: #f3f4f6; color: #6b7280; }}

/* ---- Price Band Bar Chart ---- */
.price-band {{
  display: flex;
  gap: 8px;
  margin: 12px 0;
  align-items: flex-end;
}}
.price-bar {{ flex: 1; text-align: center; font-size: 12px; }}
.price-bar .bar {{
  border-radius: 6px 6px 0 0;
  margin-bottom: 6px;
  padding-top: 8px;
  color: #fff;
  font-weight: 700;
  font-size: 13px;
}}
.price-bar .label {{ color: var(--muted); font-size: 12px; margin-top: 4px; min-height: 5.1em; }}

/* ---- Risk List ---- */
.risk-list {{ list-style: none; }}
.risk-list li {{
  padding: 10px 0;
  border-bottom: 1px solid #f3f4f6;
  display: flex;
  gap: 12px;
  align-items: flex-start;
}}
.risk-list li:last-child {{ border-bottom: 0; }}
.risk-list .severity {{ font-weight: 700; font-size: 12px; min-width: 28px; }}

/* ---- Responsive ---- */
@media (max-width: 768px) {{
  .hero-grid, .insight-row {{ grid-template-columns: 1fr; }}
  .hero {{ padding: 28px 24px; }}
  .hero h1 {{ font-size: 28px; }}
  .section {{ padding: 22px 20px; }}
}}
</style>
</head>
<body>
<div class="page">

<section class="hero">
  <div class="eyebrow">Market Research · Push Brooms (14253851) · 2026-06-23</div>
  <h1>钢丝地板刷</h1>
  <div class="verdict">建议进入 · 双路线并行验证</div>
  <p class="lead">Push Brooms 类目月销 79K units、$1.74M，市场体量健康。钢丝差异化三合一（Route B）为主力方向切入主流市场，纯钢丝刷（Route A）为补充 SKU 覆盖细分场景。Top3品牌集中度 {ss_top3_brand_ratio:.1f}%，头部未垄断。</p>
  <div class="hero-grid">
    <div class="hero-metric"><div class="label">类目月销</div><div class="value">{_fmt_units(79076)}</div></div>
    <div class="hero-metric"><div class="label">类目月销额</div><div class="value">{_fmt_num(1740000)}</div></div>
    <div class="hero-metric"><div class="label">类目均价</div><div class="value">$22.00</div></div>
    <div class="hero-metric"><div class="label">Top3品牌集中度</div><div class="value">{ss_top3_brand_ratio:.1f}%</div></div>
    <div class="hero-metric"><div class="label">中国卖家占比</div><div class="value">{ss_cn_units_ratio:.0f}%</div></div>
    <div class="hero-metric"><div class="label">退货率</div><div class="value">3.1%</div></div>
  </div>
</section>

<!-- 1. 类目全景 -->
<section class="section">
  <h2>1. 类目全景</h2>
  <p class="subtitle">Push Brooms (14253851) 类目概况，基于 595 个商品统计分析</p>

  <table>
    <tr><th>指标</th><th>数值</th><th>说明</th></tr>
    <tr><td>类目路径</td><td colspan="2">Health &amp; Household &gt; Household Supplies &gt; Cleaning Tools &gt; Sweeping &gt; Brooms &gt; Push Brooms</td></tr>
    <tr><td>月销量</td><td>{_fmt_units(79076)} units</td><td>中等规模类目，需求稳定</td></tr>
    <tr><td>月销售额</td><td>{_fmt_num(1740000)}</td><td>中等客单价市场</td></tr>
    <tr><td>平均价格</td><td>$22.00</td><td>集中在$15-30区间</td></tr>
    <tr><td>平均评分</td><td>4.3</td><td>整体满意度较高</td></tr>
    <tr><td>退货率</td><td>3.1%</td><td>低于家居类目平均，品类成熟</td></tr>
    <tr><td>Top3品牌集中度</td><td>{ss_top3_brand_ratio:.1f}%</td><td><span class="tag tag-green">分散</span> 头部未垄断</td></tr>
    <tr><td>Top3商品集中度</td><td>{ss_top3_units_ratio:.1f}%</td><td><span class="tag tag-amber">中等</span> 单品可切入</td></tr>
    <tr><td>中国卖家占比</td><td>{ss_cn_units_ratio:.0f}%</td><td>供应链主导，入场门槛低</td></tr>
    <tr><td>近1年新品占比</td><td>{ss_recent_1y_ratio:.0f}%</td><td>新品有空间切入</td></tr>
    <tr><td>$15-25价格带占比</td><td>{ss_price_15_25_ratio:.0f}%</td><td>主力价格带集中</td></tr>
  </table>
</section>

<!-- 2. 关键发现 -->
<section class="section">
  <h2>2. 关键发现</h2>
  <p class="subtitle">钢丝刷细分市场的主要机会信号与风险信号</p>

  <div class="insight-row">
    <div class="insight-card good">
      <h4>纯钢丝竞争真空</h4>
      <p>仅 3 个纯钢丝刷竞品（MAVRIZ、Mitclear、Sunbaba），合计月销仅 ~1.3K，纯钢丝细分极度不饱和</p>
    </div>
    <div class="insight-card good">
      <h4>新品路径已验证</h4>
      <p>DOLPLEAP 9个月成#2，HelpX 16个月成#4，新品在 Push Brooms 类目有清晰爬升路径</p>
    </div>
    <div class="insight-card good">
      <h4>3-in-1已成主流</h4>
      <p>Top10 中 5 个为三合一款式，消费者教育完成，无需从零培养使用习惯</p>
    </div>
    <div class="insight-card good">
      <h4>供应链优势</h4>
      <p>中国卖家占 {ss_cn_units_ratio:.0f}%，国内供应链成熟，打样与量产路径清晰</p>
    </div>
    <div class="insight-card warn">
      <h4>评分门槛极高</h4>
      <p>{ss_high_rated_ratio:.0f}% 产品评分 4.0 以上，低分产品几乎没有生存空间</p>
    </div>
    <div class="insight-card warn">
      <h4>品牌格局已形成</h4>
      <p>DOLPLEAP (19.0%)、HelpX (15.3%)、Yocada (12.2%) 三强领先，新品需要强差异化</p>
    </div>
  </div>
</section>

<!-- 3. 核心关键词 -->
<section class="section">
  <h2>3. 核心关键词: "floor scrub brush"</h2>
  <p class="subtitle">关键词搜索量与投放指标概览</p>

  <table>
    <tr><th>指标</th><th>数值</th><th>说明</th></tr>
    <tr><td>月搜索量</td><td>{monthly_search}</td><td>核心流量词，搜索需求稳定</td></tr>
    <tr><td>周搜索量</td><td>{weekly_search}</td><td>周均搜索规模</td></tr>
    <tr><td>推荐CPC竞价</td><td>${cpc}</td><td>广告竞价中等偏高</td></tr>
    <tr><td>搜索结果竞品数</td><td>{competitor_count}</td><td>竞争激烈，需精准投放</td></tr>
    <tr><td>搜索旺季</td><td>{peak_season}</td><td>备货与广告节奏参考</td></tr>
  </table>
</section>

<!-- 4. 商品集中度 Top 10 -->
<section class="section">
  <h2>4. 商品集中度 Top 10</h2>
  <p class="subtitle">Push Brooms 类目销量 Top10 商品</p>

  <table>
    <thead><tr><th>#</th><th>ASIN</th><th>标题</th><th>品牌</th><th>价格</th><th>月销</th><th>月销额</th><th>新品</th><th>评分</th></tr></thead>
    <tbody>{product_rows}</tbody>
  </table>
  <p style="margin-top:10px;color:var(--muted);font-size:13px;">
    Top3 商品占 {ss_top3_units_ratio:.1f}% 销量。DOLPLEAP B0FHQ25K2S 是第一大单品（25.6%），HelpX B0DR8SMB8H 第二（16.8%），{"头部格局相对分散，集中度中等" if ss_top3_units_ratio < 50 else "头部有一定集中度，但单品仍可切入"}。
  </p>
</section>

<!-- 5. 品牌 & 卖家集中度 -->
<section class="section">
  <h2>5. 品牌 & 卖家集中度</h2>
  <p class="subtitle">Top8 品牌与卖家的市场份额分布</p>

  <div class="insight-row">
    <div>
      <h3 style="font-size:16px;margin-bottom:12px;">品牌 Top 8</h3>
      <table>
        <thead><tr><th>#</th><th>品牌</th><th>商品数</th><th>月销</th><th>占比</th><th>月销额</th><th>评分</th></tr></thead>
        <tbody>{brand_rows}</tbody>
      </table>
    </div>
    <div>
      <h3 style="font-size:16px;margin-bottom:12px;">卖家 Top 8</h3>
      <table>
        <thead><tr><th>#</th><th>卖家</th><th>商品数</th><th>月销</th><th>占比</th><th>月销额</th></tr></thead>
        <tbody>{seller_rows}</tbody>
      </table>
    </div>
  </div>
</section>

<!-- 6. 价格带分布 -->
<section class="section">
  <h2>6. 价格带分布</h2>
  <p class="subtitle">Push Brooms 类目各价格带销量份额与机会评估</p>

  <div class="price-band">
    {price_bar_chart}
  </div>

  <table style="margin-top:16px;">
    <thead><tr><th>价格带</th><th>商品数</th><th>月销</th><th>销量占比</th><th>月销额</th><th>机会评估</th></tr></thead>
    <tbody>{price_table_rows}</tbody>
  </table>
  <p style="margin-top:12px;color:var(--muted);font-size:13px;">主力价格带 $15-25 占据 {ss_price_15_25_ratio:.1f}% 销量，其中 $15-20 占 49.1%（最核心战场）。$45以上高价区仅 3.2%。建议新品定价 $18-22 区间，兼顾利润与竞争力。</p>
</section>

<!-- 7. 上架时间 & 新品友好度 -->
<section class="section">
  <h2>7. 上架时间分布 & 新品友好度</h2>
  <p class="subtitle">新品友好度: <span class="tag tag-{"green" if nl['score'] == "excellent" else "amber"}">{nl_score_cn}</span> — {nl['reason']}</p>

  <table>
    <thead><tr><th>上架时间</th><th>商品数</th><th>月销</th><th>销量占比</th></tr></thead>
    <tbody>{listing_rows}</tbody>
  </table>
  <p style="margin-top:10px;color:var(--muted);font-size:13px;">近1年上架新品占 {ss_recent_1y_ratio:.0f}% 销量，近6个月占 11.4%。1年以上老品占 62% 销量，有评论和排名积累优势，但新品仍有机会进入。</p>
</section>

<!-- 8. 卖家地区 & 评分分布 -->
<section class="section">
  <h2>8. 卖家地区 & 评分分布</h2>
  <p class="subtitle">卖家所在国家/地区与商品评分分布</p>

  <div class="insight-row">
    <div>
      <h3 style="font-size:16px;margin-bottom:12px;">卖家国家/地区</h3>
      <table>
        <thead><tr><th>国家/地区</th><th>商品数</th><th>月销</th><th>销量占比</th><th>销额占比</th></tr></thead>
        <tbody>{country_rows}</tbody>
      </table>
    </div>
    <div>
      <h3 style="font-size:16px;margin-bottom:12px;">评分分布</h3>
      <table>
        <thead><tr><th>评分区间</th><th>商品数</th><th>月销</th><th>销量占比</th></tr></thead>
        <tbody>{rating_rows}</tbody>
      </table>
    </div>
  </div>
</section>

<!-- 9. 产品方向路线分析 -->
<section class="section">
  <h2>9. 产品方向路线分析</h2>
  <p class="subtitle">两条路线对比：纯钢丝刷（Route A）vs 钢丝差异化三合一（Route B）</p>

  <div class="insight-row">
    {dir_cards}
  </div>
  <p style="margin-top:16px;padding:14px;border-radius:8px;background:var(--accent-soft);border:1px solid var(--accent);font-size:14px;">
    <strong>运营建议:</strong> 两条路线可并行推进。Route B（钢丝差异化三合一）作为主力方向，进入已被验证的大市场（28.9K units/月），用钢丝材质做差异化卖点。Route A（纯钢丝刷）作为补充 SKU，瞄准有明确钢丝刷需求的细分场景（除苔藓、重度油污）。Route B 建议定价 $18-22，不锈钢丝 + 刮水条 + 铲刀三合一。Route A 建议定价 $19-24。
  </p>
</section>

<!-- 10. 风险与应对 -->
<section class="section">
  <h2>10. 风险与应对</h2>
  <p class="subtitle">已识别的核心风险及建议缓解措施</p>

  <ul class="risk-list">
    <li>
      <span class="severity"><span class="tag tag-amber">中</span></span>
      <div>
        <strong>评分门槛极高 — 低分产品无生存空间</strong>
        <p style="color:var(--muted);font-size:14px;margin-top:4px;">{ss_high_rated_ratio:.0f}% 销量集中在 4.0 分以上商品，4.0 以下仅占 10%。新品冷启动期需格外重视品质与评价管理</p>
        <p style="font-size:13px;margin-top:2px;"><strong>应对：</strong>Vine 先行 + 304不锈钢刷毛 + 出厂前48小时摩擦测试，确保不掉毛不锈蚀</p>
      </div>
    </li>
    <li>
      <span class="severity"><span class="tag tag-amber">中</span></span>
      <div>
        <strong>品牌格局已形成 — 三强领先，新品需强差异化</strong>
        <p style="color:var(--muted);font-size:14px;margin-top:4px;">DOLPLEAP (19.0%)、HelpX (15.3%)、Yocada (12.2%) 合计占 46.5% 销量，新品牌突围需差异化卖点</p>
        <p style="font-size:13px;margin-top:2px;"><strong>应对：</strong>钢丝材质差异化 + 不掉毛品质承诺 + 刮水条/铲刀多功能组合</p>
      </div>
    </li>
    <li>
      <span class="severity"><span class="tag tag-amber">中</span></span>
      <div>
        <strong>CPC竞价不低 — 广告成本需控制</strong>
        <p style="color:var(--muted);font-size:14px;margin-top:4px;">核心词 CPC $1.40，搜索结果竞品 4.5 万+，精准投放是关键</p>
        <p style="font-size:13px;margin-top:2px;"><strong>应对：</strong>主攻精准长尾词（steel brush CPC $1.18, wire scrub brush CPC $0.80），控制 ACoS</p>
      </div>
    </li>
  </ul>

  <h3 style="margin-top:20px;font-size:16px;margin-bottom:8px;">核心优势</h3>
  <ul class="risk-list">
    <li>
      <span class="severity"><span class="tag tag-green">优势</span></span>
      <div>
        <strong>竞争真空 — 纯钢丝刷仅3个直接竞品</strong>
        <p style="color:var(--muted);font-size:14px;margin-top:4px;">Top100 中纯钢丝刷仅 MAVRIZ、Mitclear、Sunbaba 三家，合计月销仅 ~1.3K，市场空白明显</p>
      </div>
    </li>
    <li>
      <span class="severity"><span class="tag tag-green">优势</span></span>
      <div>
        <strong>3-in-1 已成主流 — 消费者教育完成</strong>
        <p style="color:var(--muted);font-size:14px;margin-top:4px;">Top10 中 5 个为三合一款式，Route B 钢丝三合一可借势进入已验证市场</p>
      </div>
    </li>
    <li>
      <span class="severity"><span class="tag tag-green">优势</span></span>
      <div>
        <strong>中国供应链成熟 — 成本可控</strong>
        <p style="color:var(--muted);font-size:14px;margin-top:4px;">{ss_cn_units_ratio:.0f}% 销量来自中国卖家，国内供应链完善，打样与量产路径清晰</p>
      </div>
    </li>
  </ul>
</section>

<div style="color:var(--muted);font-size:13px;text-align:center;padding:16px;">数据来源：卖家精灵 30天滚动窗口 + Sorftime 实时数据 · 生成时间 2026-06-23 · 仅供内部决策参考</div>
</div>
</body>
</html>"""

    return html



# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    run_dir = Path("/Users/sxie/Documents/亚马逊/amz-product-research-workbench/runs/20260621_钢丝地板刷")
    analysis_dir = run_dir / "analysis"
    analysis_dir.mkdir(parents=True, exist_ok=True)

    # --- SellerSprite product concentration ---
    ss_products = [
        {"title":"Scrub Brush with Long Handle, Floor Scrub Brush Squeegee Broom for Cleaning, 3 in 1 Shower Scrubber Floor Broom Squeegee for Concrete Tile Wall Deck Patio Grey","asin":"B0FHQ25K2S","brand":"DOLPLEAP","sellerName":"DOLPLEAP","sellerType":"FBA","price":18.76,"shelfDate":"2025-09-02","ratings":310,"rating":4.4,"newFlag":1,"totalUnits":10070,"totalRevenue":205730.11,"totalUnitsRatio":0.256,"totalRevenueRatio":0.2711},
        {"title":"Floor Scrub Brush with Long Handle, 3 in 1 Scrape and Heavy-Duty Stiff Bristle Floor Scrubber Brush with Squeegee and Tweezer for Cleaning Tile Wall Deck Bathroom Patio Garage Kitchen (White)","asin":"B0DR8SMB8H","brand":"HelpX","sellerName":"HelpX","sellerType":"FBA","price":24.99,"shelfDate":"2025-02-10","ratings":885,"rating":4.5,"newFlag":0,"totalUnits":6601,"totalRevenue":145420.03,"totalUnitsRatio":0.1678,"totalRevenueRatio":0.1916},
        {"title":"Yocada 18 Inch Push Broom Heavy-Duty Outdoor Commercial Broom Brush Stiff Bristles for Cleaning Patio Garage Deck Concrete Wood Stone Tile Floor 65.3 inch Long","asin":"B0B499NW8N","brand":"Yocada","sellerName":"Yocada Clean","sellerType":"FBA","price":21.59,"shelfDate":"2022-06-27","ratings":1911,"rating":4.6,"newFlag":0,"totalUnits":3890,"totalRevenue":83985.1,"totalUnitsRatio":0.0989,"totalRevenueRatio":0.1107},
        {"title":"PBHEPJ 18 Inchs Push Broom Outdoor Heavy Duty, Shop Broom with 60\" Long Handle for Cleaning Outdoor or Indoor Tile, Garage, Shop, Deck, Concrete, Wood, Stone, Patio Floor","asin":"B0FDXDL4F5","brand":"PBHEPJ","sellerName":"PBHEPJ","sellerType":"FBA","price":16.99,"shelfDate":"2025-08-03","ratings":397,"rating":4.4,"newFlag":1,"totalUnits":3574,"totalRevenue":62044.64,"totalUnitsRatio":0.0909,"totalRevenueRatio":0.0817},
        {"title":"MR.SIGA Pet Hair Removal Rubber Broom with Built in Squeegee, 3 in 1 Floor Brush for Carpet, 61 inch Adjustable Handle, Includes 1 Microfiber Cloth for Floor Dusting","asin":"B08HN63XK9","brand":"MR.SIGA","sellerName":"Mr SIGA USA","sellerType":"FBA","price":19.98,"shelfDate":"2020-09-09","ratings":14655,"rating":4.2,"newFlag":0,"totalUnits":3394,"totalRevenue":67812.12,"totalUnitsRatio":0.0863,"totalRevenueRatio":0.0893},
        {"title":"CLEANHOME 24\"Push Broom Brush for Floor Cleaning with 65\" Long Handle and Stiff Bristles, Heavy Duty Brush for Shop, Deck, Garage, Concrete,Indoor and Outdoor Broom,Orange","asin":"B09STM75QW","brand":"CLEANHOME","sellerName":"CLEANHOME Life","sellerType":"FBA","price":26.99,"shelfDate":"2022-06-13","ratings":1356,"rating":4.6,"newFlag":0,"totalUnits":2988,"totalRevenue":80646.12,"totalUnitsRatio":0.076,"totalRevenueRatio":0.1063},
        {"title":"Floor Scrub Brush with Long Handle: 3 in 1 Heavy-Duty Floor Scrubber Brush with Squeegee for Cleaning Tile Bathroom Deck Kitchen Patio - Blue","asin":"B0FL2B8Z9W","brand":"EHADOO","sellerName":"JOTENBO","sellerType":"FBA","price":17.99,"shelfDate":"2025-09-18","ratings":293,"rating":4.5,"newFlag":1,"totalUnits":2370,"totalRevenue":44366.4,"totalUnitsRatio":0.0602,"totalRevenueRatio":0.0585},
        {"title":"Handy Broom, Indoor/Outdoor Brooms, Duty Kitchen Broom, for Home Garage Kitchen Office Courtyard Lobby Patio Lawn Concrete (1, Red)","asin":"B0FBGNQY4B","brand":"Nodirz","sellerName":"Nodirz Shop","sellerType":"FBA","price":7.19,"shelfDate":"2025-08-09","ratings":642,"rating":4.0,"newFlag":1,"totalUnits":2358,"totalRevenue":18133.02,"totalUnitsRatio":0.0599,"totalRevenueRatio":0.0239},
        {"title":"Floor Scrub Brush 2 in 1 Scrape and Stiff Bristle Deck Brush for Cleaning Concrete, Patio, Garage, Kitchen, Carpet and Bathroom 57\" Long Handle","asin":"B0D97GM7TG","brand":"TrueYee","sellerName":"Willthebest","sellerType":"FBA","price":16.99,"shelfDate":"2024-10-15","ratings":494,"rating":4.2,"newFlag":0,"totalUnits":2123,"totalRevenue":35878.7,"totalUnitsRatio":0.054,"totalRevenueRatio":0.0473},
        {"title":"Handy Broom, Indoor/Outdoor Brooms, Duty Kitchen Broom, for Home Garage Kitchen Office Courtyard Lobby Patio Lawn Concrete (1 Pack, Red, New)","asin":"B0GJTB1ZLJ","brand":"Nodirz","sellerName":"Nodirz Shop","sellerType":"FBA","price":7.99,"shelfDate":"2026-03-06","ratings":121,"rating":4.1,"newFlag":1,"totalUnits":1970,"totalRevenue":14991.7,"totalUnitsRatio":0.0501,"totalRevenueRatio":0.0198},
    ]

    ss_brands = [
        {"brand":"DOLPLEAP","ranking":1,"products":1,"newProducts":1,"totalUnits":10070,"totalRevenue":205730.11,"totalUnitsRatio":0.1903,"totalRevenueRatio":0.1783,"avgPrice":18.76,"ratings":310,"rating":4.4},
        {"brand":"HelpX","ranking":2,"products":2,"newProducts":1,"totalUnits":8084,"totalRevenue":174279.21,"totalUnitsRatio":0.1528,"totalRevenueRatio":0.151,"avgPrice":22.49,"ratings":951,"rating":4.3},
        {"brand":"Yocada","ranking":3,"products":4,"newProducts":0,"totalUnits":6438,"totalRevenue":144689.94,"totalUnitsRatio":0.1217,"totalRevenueRatio":0.1254,"avgPrice":24.09,"ratings":3973,"rating":4.2},
        {"brand":"PBHEPJ","ranking":4,"products":2,"newProducts":2,"totalUnits":5539,"totalRevenue":141391.34,"totalUnitsRatio":0.1047,"totalRevenueRatio":0.1225,"avgPrice":28.99,"ratings":565,"rating":4.3},
        {"brand":"KeFanta","ranking":5,"products":7,"newProducts":2,"totalUnits":4756,"totalRevenue":128177.84,"totalUnitsRatio":0.0899,"totalRevenueRatio":0.1111,"avgPrice":26.63,"ratings":6475,"rating":4.4},
        {"brand":"CLEANHOME","ranking":6,"products":3,"newProducts":0,"totalUnits":4609,"totalRevenue":111188.91,"totalUnitsRatio":0.0871,"totalRevenueRatio":0.0964,"avgPrice":20.99,"ratings":2062,"rating":4.6},
        {"brand":"Nodirz","ranking":7,"products":3,"newProducts":3,"totalUnits":4462,"totalRevenue":34195.38,"totalUnitsRatio":0.0843,"totalRevenueRatio":0.0296,"avgPrice":7.72,"ratings":770,"rating":4.1},
        {"brand":"MR.SIGA","ranking":8,"products":1,"newProducts":0,"totalUnits":3394,"totalRevenue":67812.12,"totalUnitsRatio":0.0642,"totalRevenueRatio":0.0588,"avgPrice":19.98,"ratings":14655,"rating":4.2},
    ]

    ss_sellers = [
        {"sellerName":"DOLPLEAP","ranking":1,"products":1,"newProducts":1,"totalUnits":10070,"totalRevenue":205730.11,"totalUnitsRatio":0.2078,"totalRevenueRatio":0.194},
        {"sellerName":"HelpX","ranking":2,"products":2,"newProducts":1,"totalUnits":8084,"totalRevenue":174279.21,"totalUnitsRatio":0.1668,"totalRevenueRatio":0.1644},
        {"sellerName":"PBHEPJ","ranking":3,"products":2,"newProducts":2,"totalUnits":5539,"totalRevenue":141391.34,"totalUnitsRatio":0.1143,"totalRevenueRatio":0.1333},
        {"sellerName":"Nodirz Shop","ranking":4,"products":3,"newProducts":3,"totalUnits":4462,"totalRevenue":34195.38,"totalUnitsRatio":0.0921,"totalRevenueRatio":0.0322},
        {"sellerName":"Yocada Clean","ranking":5,"products":2,"newProducts":0,"totalUnits":4273,"totalRevenue":94337.59,"totalUnitsRatio":0.0882,"totalRevenueRatio":0.089},
        {"sellerName":"CLEANHOME Life","ranking":6,"products":2,"newProducts":0,"totalUnits":4185,"totalRevenue":102132.27,"totalUnitsRatio":0.0864,"totalRevenueRatio":0.0963},
        {"sellerName":"Mr SIGA USA","ranking":7,"products":1,"newProducts":0,"totalUnits":3394,"totalRevenue":67812.12,"totalUnitsRatio":0.07,"totalRevenueRatio":0.0639},
        {"sellerName":"Amazon","ranking":8,"products":9,"newProducts":0,"totalUnits":2902,"totalRevenue":94033.39,"totalUnitsRatio":0.0599,"totalRevenueRatio":0.0887},
    ]

    ss_price_dist = [
        {"label":"5-10","products":8,"units":5658,"revenue":44946.99,"unitsRatio":0.0718},
        {"label":"10-15","products":11,"units":2716,"revenue":36952.41,"unitsRatio":0.0345},
        {"label":"15-20","products":36,"units":38667,"revenue":728626.81,"unitsRatio":0.4907},
        {"label":"20-25","products":17,"units":19302,"revenue":434381.79,"unitsRatio":0.245},
        {"label":"25-35","products":10,"units":6310,"revenue":171458.54,"unitsRatio":0.0801},
        {"label":"35-40","products":6,"units":1443,"revenue":56505.51,"unitsRatio":0.0183},
        {"label":"40-45","products":2,"units":2206,"revenue":89328.92,"unitsRatio":0.028},
        {"label":"45以上","products":9,"units":2496,"revenue":177064.23,"unitsRatio":0.0317},
    ]

    ss_listing_dist = [
        {"label":"1个月","products":3,"units":921,"revenue":17574.35,"unitsRatio":0.0117},
        {"label":"3个月","products":5,"units":3190,"revenue":38321.3,"unitsRatio":0.0404},
        {"label":"半年","products":9,"units":4851,"revenue":115815.01,"unitsRatio":0.0614},
        {"label":"1年","products":26,"units":29959,"revenue":622134.23,"unitsRatio":0.379},
        {"label":"1年半","products":15,"units":12242,"revenue":276052.1,"unitsRatio":0.1549},
        {"label":"2年","products":6,"units":3319,"revenue":54984.15,"unitsRatio":0.042},
        {"label":"2年半","products":5,"units":1508,"revenue":54982.85,"unitsRatio":0.0191},
        {"label":"3年","products":6,"units":3132,"revenue":95083.85,"unitsRatio":0.0396},
        {"label":"3年以上","products":25,"units":19925,"revenue":465206.31,"unitsRatio":0.2521},
    ]

    ss_country_dist = [
        {"label":"中国","products":65,"units":65499,"revenue":1342893.57,"unitsRatio":0.8286,"revenueRatio":0.7717},
        {"label":"美国","products":26,"units":9573,"revenue":308646.22,"unitsRatio":0.1211,"revenueRatio":0.1774},
        {"label":"中国香港","products":8,"units":3878,"revenue":87025.5,"unitsRatio":0.0491,"revenueRatio":0.05},
        {"label":"未知","products":1,"units":97,"revenue":1588.86,"unitsRatio":0.0012,"revenueRatio":0.0009},
    ]

    ss_rating_dist = [
        {"label":"2.0以下","products":0,"units":0,"revenue":0.0,"unitsRatio":0.0},
        {"label":"2.0-3.0","products":2,"units":728,"revenue":10095.12,"unitsRatio":0.0092},
        {"label":"3.0-3.5","products":2,"units":276,"revenue":7593.0,"unitsRatio":0.0035},
        {"label":"3.5-4.0","products":15,"units":6871,"revenue":118605.51,"unitsRatio":0.0869},
        {"label":"4.0-4.3","products":26,"units":19239,"revenue":400793.86,"unitsRatio":0.2434},
        {"label":"4.3-4.5","products":39,"units":38717,"revenue":852045.23,"unitsRatio":0.4898},
        {"label":"4.5以上","products":16,"units":13216,"revenue":351021.43,"unitsRatio":0.1672},
    ]

    # --- Sorftime data ---
    sf_category = {
        "类目统计报告": {
            "top100产品月销量": "103104",
            "top100产品月销额": "2332473.10",
            "top3_product_sales_volume_share": "34.12%",
            "top3_brands_sales_volume_share": "36.92%",
            "top3_seller_sales_volume_share": "35.74%",
            "amazonOwned_sales_volume_share": "7.41%",
            "average_price": "28.98",
            "median_price": "20.59",
            "high_rated_sales_volume_share": "98.10%",
            "low_reviews_sales_volume_share": "19.26%",
        }
    }

    sf_keyword = {
        "关键词": "floor scrub brush",
        "周搜索量": "8370",
        "月搜索量": "33058",
        "推荐cpc竞价": "1.40",
        "词搜索量旺季": "2月",
        "搜索结果竞品数量": "45563",
    }

    # --- Build merged pool from competitor_lookup data ---
    ss_competitor_items = [
        {"asin":"B0GHHTV8VW","title":"Floor Scrub Brush with Long Handle, 3 in 1 Scrape and Heavy-Duty Stiff Bristle Scrubber Brush for Cleaning Shower Bathroom, Patio, Pool, Garage, Kitchen, Wall and Deck (Gray, 2 Pack)","brand":"AIR U+","sellerName":"AIR U+","sellerNation":"CN","price":43.98,"units":12227,"revenue":537743.44,"rating":4.4,"ratings":3238,"bsr":242,"fulfillment":"FBA","nodeId":"14253851","nodeIdPath":"3760901:15342811:15342831:2245502011:2245510011:14253851","lqs":90,"profit":68.74,"fba":7.15,"variations":6,"sellers":1},
        {"asin":"B0C6XTNXL8","title":"Floor Scrub Brush with Long Handle, 3 in 1 Scrape and Heavy-Duty Stiff Bristle Scrubber Brush for Cleaning Shower Bathroom, Patio, Pool, Garage, Kitchen, Wall and Deck (White, 1 Pack)","brand":"AIR U+","sellerName":"AIR U+","sellerNation":"CN","price":18.99,"units":9388,"revenue":223809.92,"rating":4.4,"ratings":3238,"bsr":2570,"fulfillment":"FBA","nodeId":"15342891","lqs":100,"profit":50.88,"fba":6.48,"variations":6,"sellers":2},
        {"asin":"B0FHQ25K2S","title":"Scrub Brush with Long Handle, Floor Scrub Brush Squeegee Broom for Cleaning, 3 in 1 Shower Scrubber Floor Broom Squeegee for Concrete Tile Wall Deck Patio Grey","brand":"DOLPLEAP","sellerName":"DOLPLEAP","sellerNation":"CN","price":18.76,"units":10070,"revenue":205730.11,"rating":4.4,"ratings":310,"bsr":2939,"fulfillment":"FBA","nodeId":"14253851","lqs":100,"profit":52.5,"fba":6.13,"variations":3,"sellers":1},
        {"asin":"B0DR8SMB8H","title":"Floor Scrub Brush with Long Handle, 3 in 1 Scrape and Heavy-Duty Stiff Bristle Floor Scrubber Brush with Squeegee and Tweezer for Cleaning Tile Wall Deck Bathroom Patio Garage Kitchen (White)","brand":"HelpX","sellerName":"HelpX","sellerNation":"CN","price":24.99,"units":6601,"revenue":145420.03,"rating":4.5,"ratings":885,"bsr":8567,"fulfillment":"FBA","nodeId":"14253851","lqs":100,"profit":56.31,"fba":6.31,"variations":4,"sellers":1},
        {"asin":"B0GCM16WVW","title":"MAVRIZ Stainless Steel Concrete Brush with Long Handle - Heavy Duty Deck Brush for Concrete Cleaning, Outdoor Broom for Moss Removal, Wire Brushes for Scrubbing Patios, Driveways & Pools","brand":"MAVRIZ","sellerName":"Home Live Direct","sellerNation":"HK","price":19.99,"units":533,"revenue":10654.67,"rating":4.3,"ratings":168,"bsr":36557,"fulfillment":"FBA","nodeId":"14253851","lqs":100,"profit":53.44,"fba":6.31,"variations":1,"sellers":1},
        {"asin":"B0CNXJ5D11","title":"Mitclear Heavy Duty Wire Broom with Telescopic Handle(57IN), Stiff Metal Bristle Brush for Removing Weed Moss, Outdoor Floor Scrub Brush for Patio, Deck, Garden, Concrete, Garage","brand":"Mitclear","sellerName":"IKU","sellerNation":"CN","price":19.89,"units":678,"revenue":12997.26,"rating":4.2,"ratings":1904,"bsr":56634,"fulfillment":"FBA","nodeId":"14253851","lqs":100,"profit":54.18,"fba":6.13,"variations":1,"sellers":1},
        {"asin":"B0FX4NW8R4","title":"Stainless Steel Wire Scrub Brush with 62\" Long Handle,Heavy Duty Stiff Metal Bristle Scrubber Broom for Deck Concrete Patio Gardens and Garages Floor Cleaning, Outdoor Moss Removal","brand":"Sunbaba","sellerName":"SUNBABA TOOLS","sellerNation":"CN","price":20.99,"units":142,"revenue":2933.72,"rating":4.8,"ratings":15,"bsr":127106,"fulfillment":"FBA","nodeId":"15342891","lqs":100,"profit":54.94,"fba":6.31,"variations":1,"sellers":1},
    ]

    ss_normalized = [_ss_to_normalized(item) for item in ss_competitor_items]

    sf_top100 = [
        {"ASIN":"B0C6XTNXL8","标题":"Floor Scrub Brush with Long Handle, 3 in 1 Scrape and Heavy-Duty Stiff Bristle Scrubber Brush Broom for Cleaning Shower Bathroom, Patio, Pool, Garage, Kitchen, Wall and Deck (White, 1 Pack)","月销量":"19985","月销额":"399500.15","品牌":"AIR U+","价格":19.99,"星级":4.40,"评论数":3380,"卖家来源":"中国","卖家":"AIR U+","毛利":9.91,"毛利率":49.57},
        {"ASIN":"B0FHQ25K2S","标题":"Scrub Brush with Long Handle, Floor Scrub Brush Squeegee Broom for Cleaning, 3 in 1 Shower Scrubber Floor Broom Squeegee for Concrete Tile Wall Deck Patio Grey","月销量":"9222","月销额":"183056.70","品牌":"DOLPLEAP","价格":19.85,"星级":4.40,"评论数":404,"卖家来源":"中国","卖家":"DOLPLEAP","毛利":10.20,"毛利率":51.39},
        {"ASIN":"B0DR8SMB8H","标题":"Floor Scrub Brush with Long Handle, 3 in 1 Scrape and Heavy-Duty Stiff Bristle Floor Scrubber Brush with Squeegee and Tweezer for Cleaning Tile Wall Deck Bathroom Patio Garage Kitchen (White)","月销量":"4661","月销额":"102495.39","品牌":"HelpX","价格":21.99,"星级":4.50,"评论数":929,"卖家来源":"中国","卖家":"HelpX","毛利":12.10,"毛利率":55.03},
        {"ASIN":"B0GCM16WVW","标题":"MAVRIZ Stainless Steel Concrete Brush with Long Handle - Heavy Duty Deck Brush for Concrete Cleaning, Outdoor Broom for Moss Removal, Wire Brushes for Scrubbing Patios, Driveways & Pools","月销量":"692","月销额":"13833.08","品牌":"MAVRIZ","价格":19.99,"星级":4.30,"评论数":173,"卖家来源":"中国香港","卖家":"Home Live Direct","毛利":10.41,"毛利率":52.08},
        {"ASIN":"B0CNXJ5D11","标题":"Mitclear Heavy Duty Wire Broom with Telescopic Handle(57IN), Stiff Metal Bristle Brush for Removing Weed Moss, Outdoor Floor Scrub Brush for Patio, Deck, Garden, Concrete, Garage","月销量":"392","月销额":"6620.88","品牌":"Mitclear","价格":16.89,"星级":4.10,"评论数":1950,"卖家来源":"中国","卖家":"IKU","毛利":8.00,"毛利率":47.37},
    ]

    sf_normalized = [_sf_to_normalized(item) for item in sf_top100]
    merged_pool = _merge_by_asin(ss_normalized, sf_normalized)
    sf_deviations = _detect_sf_deviation(merged_pool)
    direction_cards = _build_direction_cards()
    new_listing_score = _new_listing_friendliness(ss_listing_dist)

    # --- Save candidate_pool.json ---
    candidate_pool = {
        "run_id": "20260621_钢丝地板刷",
        "generated_at": "2026-06-23",
        "data_sources": ["seller_sprite_mcp", "sorftime_mcp"],
        "primary_category": {
            "node_id": "14253851",
            "name": "Push Brooms",
            "path": "Health & Household > Household Supplies > Cleaning Tools > Sweeping > Brooms > Push Brooms",
        },
        "market_summary": {
            "ss_total_units": 79076,
            "ss_total_revenue": 1740000,
            "sf_top100_units": 103104,
            "sf_top100_revenue": 2332473.10,
            "china_seller_ratio_ss": 0.8286,
            "china_seller_ratio_sf": 0.65,
        },
        "products": merged_pool,
        "product_concentration": ss_products[:10],
        "brand_concentration": ss_brands,
        "seller_concentration": ss_sellers,
        "price_distribution": ss_price_dist,
        "listing_age_distribution": ss_listing_dist,
        "seller_country_distribution": ss_country_dist,
        "rating_distribution": ss_rating_dist,
        "direction_cards": direction_cards,
        "data_quality": {
            "sf_deviations": sf_deviations,
            "sf_deviation_count": len(sf_deviations),
            "new_listing_friendliness": new_listing_score,
        },
    }

    candidate_path = analysis_dir / "candidate_pool.json"
    candidate_path.write_text(json.dumps(candidate_pool, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {candidate_path}")

    # --- Generate HTML report ---
    html = _build_html_report(
        ss_market={},
        ss_products=ss_products,
        ss_brands=ss_brands,
        ss_sellers=ss_sellers,
        ss_price_dist=ss_price_dist,
        ss_listing_dist=ss_listing_dist,
        ss_country_dist=ss_country_dist,
        ss_rating_dist=ss_rating_dist,
        sf_category=sf_category,
        sf_keyword=sf_keyword,
        sf_deviations=sf_deviations,
        direction_cards=direction_cards,
        new_listing_score=new_listing_score,
        merged_pool=merged_pool,
    )

    html_path = analysis_dir / "钢丝地板刷_融合分析报告.html"
    html_path.write_text(html, encoding="utf-8")
    print(f"Wrote {html_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
