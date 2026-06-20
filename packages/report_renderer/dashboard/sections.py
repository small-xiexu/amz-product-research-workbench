"""HTML 看板分区渲染。从 render_report.py R5 抽离，纯移动不改逻辑。"""

from __future__ import annotations

import json
import math
import re
from datetime import datetime
from html import escape

from packages.report_renderer.dashboard.style import DASHBOARD_STYLE
from packages.report_renderer.constants import (
    FORMAL_REPORT_SECTION_TITLES,
    REPORT_EXCEL_SHEET_MAP,
)
from packages.report_renderer.formatting import (
    _format_number,
    _format_count_items,
    _site_currency_code,
    _format_money,
    _normalize_money_text,
    _format_percent_or_text,
    _market_size_value_text,
    _display_value,
    _safe_float,
    _median,
    _safe_sheet_name,
    _compact_title,
    _trim_sentence_end,
    _join_or_default,
    _localized_title,
    _clean_display_title,
    _display_dashboard_value,
    _format_evidence_refs,
)


def render_dashboard(package: dict) -> str:
    model = _dashboard_model(package)
    title = escape(str(model["title"]))
    title_cn = escape(str(model.get("title_cn", "")))
    browser_title = f"{title} / {title_cn}" if title_cn else title
    sections = [
        _dashboard_hero(model),
        _dashboard_metric_grid(model),
        _dashboard_market_section(model),
        _dashboard_keyword_section(model),
        _dashboard_competitor_voc_section(model),
        _dashboard_market_score_section(model),
        _dashboard_footer(model),
    ]
    return f"""<!doctype html>
<html lang="zh-CN">
  <head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{browser_title}</title>
  <style>{DASHBOARD_STYLE}</style>
</head>
<body>
  <main class="page">
    {''.join(sections)}
  </main>
</body>
</html>"""


def _dashboard_model(package: dict[str, Any]) -> dict[str, Any]:
    meta = package.get("metadata", {})
    candidate = package.get("normalized_tables", {}).get("candidate", {})
    demand = candidate.get("demand_evidence", {})
    competition = candidate.get("competition_structure", {})
    new_listing = candidate.get("new_listing_opportunity", {})
    return_risk = package.get("return_risk", {})
    market = package.get("market_analysis", {})
    market_structure = package.get("market_structure", {})
    price_band_context = package.get("price_band_context", {})
    voc = package.get("voc_analysis", {})
    status = package.get("status_card", {})
    decision = package.get("decision_review", {})
    summary = package.get("report_summary", {})
    return {
        "title": _clean_display_title(meta.get("seed_keyword_or_category", "调研看板")),
        "title_cn": _localized_title(_clean_display_title(meta.get("seed_keyword_or_category", ""))),
        "currency_code": _site_currency_code(meta.get("site", "US")),
        "meta": meta,
        "candidate": candidate,
        "demand": demand,
        "competition": competition,
        "new_listing": new_listing,
        "return_risk": return_risk,
        "market": market,
        "market_structure": market_structure,
        "price_band_context": price_band_context,
        "scorecard": (decision.get("go_nogo_scorecard", {}) if isinstance(decision, dict) else {}),
        "voc": voc,
        "status": status,
        "decision": decision,
        "summary": summary,
        "data_quality": market_structure.get("data_quality", {}),
        "distributions": market_structure.get("attribute_distributions", []),
        "cross_analysis": market_structure.get("cross_analysis", []),
        "competitor_pool": package.get("competitor_pool", {}),
        "top_products": package.get("normalized_tables", {}).get("top100", []),
        "missing_inputs": decision.get("missing_inputs", []) if isinstance(decision, dict) else [],
        "facts": decision.get("facts", []) if isinstance(decision, dict) else [],
        "inferences": decision.get("inferences", []) if isinstance(decision, dict) else [],
        "actions": decision.get("action_items", []) if isinstance(decision, dict) else [],
        "risks": decision.get("risk_matrix", []) if isinstance(decision, dict) else [],
        "links": {
            "markdown": "report.md",
            "html_report": "report.html",
            "summary": "summary.md",
            "excel": "data.xlsx",
        },
    }


def _dashboard_hero(model: dict[str, Any]) -> str:
    status = model.get("status", {})
    decision = model.get("decision", {})
    currency_code = model.get("currency_code", "USD")
    bullets = []
    for item in (decision.get("facts", []) or [])[:2]:
        bullets.append(_normalize_money_text(item, currency_code))
    for item in (decision.get("inferences", []) or [])[:1]:
        bullets.append(_normalize_money_text(item, currency_code))
    if not bullets:
        bullets = [_normalize_money_text(item, currency_code) for item in (model.get("summary", {}).get("bullets", []) or [])[:3]]
    meta_badges = [
        f"站点 {model['meta'].get('site', '待填')}",
        f"样本 {model.get('data_quality', {}).get('actual_count', len(model.get('top_products', [])))} / {model.get('data_quality', {}).get('expected_count', 100)}",
        f"数据源 {len(model['meta'].get('data_sources', []))}",
        f"金额口径 {currency_code}",
    ]
    links = [
        f'<a class="link-chip" href="{model["links"]["html_report"]}">网页版报告</a>',
        f'<a class="link-chip" href="{model["links"]["markdown"]}">Markdown</a>',
        f'<a class="link-chip" href="{model["links"]["excel"]}">Excel 底表</a>',
        f'<a class="link-chip" href="{model["links"]["summary"]}">摘要</a>',
    ]
    reason = str(status.get("reason", "待补"))
    next_step = str(status.get("next_step", "待补"))
    status_value = str(status.get("status", "待填"))
    missing_line = "、".join(str(item) for item in (model.get("missing_inputs", []) or [])[:4]) or "暂无"
    first_fact = _normalize_money_text((decision.get("facts") or ["当前先看市场、小类、关键词、竞品和 VOC 证据。"])[0], currency_code)
    title_cn_html = (
        f'<span class="title-cn">{escape(str(model.get("title_cn", "")))}</span>'
        if model.get("title_cn")
        else ""
    )
    return f"""
<section class="hero">
  <div class="panel">
    <div class="eyebrow">Amazon Product Research Dashboard</div>
    <h1 class="title">
      <span class="title-en">{escape(str(model['title']))}</span>
      {title_cn_html}
    </h1>
    <div class="subtitle">{escape(first_fact)}</div>
    <div class="hero-meta">
      {''.join(f'<span class="badge">{escape(item)}</span>' for item in meta_badges)}
    </div>
    <div class="hero-meta" style="margin-top:14px;">
      {''.join(links)}
    </div>
    <div class="summary-strip">
      <div class="summary-item">
        <div class="summary-label">当前结论</div>
        <div class="summary-value">{escape(status_value)}</div>
        <div class="summary-note">{escape(first_fact)}</div>
      </div>
      <div class="summary-item">
        <div class="summary-label">下一步</div>
        <div class="summary-value">{escape(next_step)}</div>
        <div class="summary-note">先完成这个动作，再进入更细的补数和复核。</div>
      </div>
      <div class="summary-item">
        <div class="summary-label">待补重点</div>
        <div class="summary-value">{escape(missing_line)}</div>
        <div class="summary-note">这些字段补齐后，结论可信度会明显提升。</div>
      </div>
    </div>
  </div>
  <div class="panel panel-dark hero-status">
    <div>
      <div class="status-label">Go / No-Go</div>
      <div class="status-value">{escape(status_value)}</div>
      <div class="status-copy">{escape(reason)}</div>
      <div class="status-note">下一步：{escape(next_step)}</div>
    </div>
    <div class="status-stack">
      {''.join(f'<div class="status-bullet">{escape(item)}</div>' for item in bullets[:3])}
    </div>
  </div>
</section>"""


def _dashboard_metric_grid(model: dict[str, Any]) -> str:
    market = model.get("market", {})
    competition = model.get("competition", {})
    scorecard = model.get("scorecard", {}) if isinstance(model.get("scorecard"), dict) else {}
    price_band_context = model.get("price_band_context", {}) if isinstance(model.get("price_band_context"), dict) else {}
    data_quality = model.get("data_quality", {})
    currency_code = model.get("currency_code", "USD")
    metrics = [
        (
            "市场规模",
            market.get("market_size", "待填"),
            market.get("price_band", "待填"),
        ),
        (
            "竞争集中度",
            competition.get("top10_product_units_share"),
            market.get("brand_concentration", "待填"),
        ),
        (
            "市场机会评分",
            scorecard.get("weighted_score", "待填"),
            f"研究结论 {scorecard.get('decision', '待填')}；价格带 {price_band_context.get('top_price_band_by_units', '待补')}",
        ),
        (
            "数据质量",
            f"{data_quality.get('actual_count', '待填')} / {data_quality.get('expected_count', '100')}",
            data_quality.get("quality_summary", data_quality.get("level", "待填")),
        ),
    ]
    cards = []
    for label, value, note in metrics:
        if isinstance(value, (int, float)):
            if "share" in label.lower() or "集中度" in label:
                value_text = _format_percent_or_text(value)
            elif label == "市场机会评分":
                value_text = f"{value:.2f}" if isinstance(value, float) else str(value)
            else:
                value_text = _format_number(value)
        elif label == "市场规模":
            value_text = _market_size_value_text(value, currency_code)
        else:
            value_text = _normalize_money_text(value, currency_code) if label == "市场规模" else str(value)
        note_text = _normalize_money_text(note, currency_code) if isinstance(note, str) else str(note)
        cards.append(
            f"""
            <div class="metric-card">
              <div class="metric-label">{escape(label)}</div>
              <div class="metric-value">{escape(value_text)}</div>
              <div class="metric-note">{escape(note_text)}</div>
            </div>
            """
        )
    return f'<section class="metric-grid">{"".join(cards)}</section>'


def _dashboard_market_section(model: dict[str, Any]) -> str:
    distributions = model.get("distributions", [])
    data_quality = model.get("data_quality", {})
    summary = model.get("market_structure", {}).get("summary", {})
    quality_summary = summary.get("quality_summary") or data_quality.get("quality_summary") or "暂无完整度说明。"
    dominant_structure = summary.get("dominant_structure") or "暂无主结构特征。"
    warnings = data_quality.get("warnings", []) or []
    clue_items = summary.get("opportunity_clues", []) or []
    price_dist = _find_distribution(distributions, "price_band")
    review_dist = _find_distribution(distributions, "review_band")
    age_dist = _find_distribution(distributions, "listing_age_band")
    left_content = [
        _render_distribution_panel("价格带结构", price_dist, "看主卖价位在哪个区间，避免一上来就冲最拥挤的位置。"),
        _render_distribution_panel("评论门槛", review_dist, "看评论门槛卡在哪里，判断新品是否真有切口。"),
        _render_distribution_panel("上架时间", age_dist, "看老品/新品比例，判断市场是否仍在流动。"),
    ]
    right_notes = [
        ("数据质量", quality_summary),
        ("结构特征", dominant_structure),
    ]
    if warnings:
        right_notes.extend((f"提醒 {idx + 1}", warning) for idx, warning in enumerate(warnings[:3]))
    if clue_items:
        right_notes.extend((f"交叉线索 {idx + 1}", clue) for idx, clue in enumerate(clue_items[:3]))
    return f"""
<section class="section">
  <div class="section-header">
    <div>
      <div class="eyebrow">Market View</div>
      <h2 class="section-title">先看大盘，再看谁在吃销量</h2>
    </div>
    <div class="section-note">这块回答三个问题：市场有没有量、头部品牌吃掉了多少、评论门槛高不高。右侧只保留结构判断，不把原始明细堆到页面上。</div>
  </div>
  <div class="two-col">
    <div class="stack">
      {''.join(left_content)}
    </div>
    <div class="subpanel">
      <div class="section-header" style="margin-bottom:12px;">
        <div>
          <div class="eyebrow">Structure Notes</div>
          <h3 class="section-title" style="font-size:22px;">结构判断和提醒</h3>
        </div>
      </div>
      <div class="grid-2">
        {''.join(_render_info_card(label, value) for label, value in right_notes[:4])}
      </div>
      <div class="note-list" style="margin-top:12px;">
        {''.join(f'<div class="note-item">{escape(str(item[0]))}：{escape(str(item[1]))}</div>' for item in right_notes[4:]) if len(right_notes) > 4 else '<div class="note-item">当前结构线索不多，但已足够支持先看后补。</div>'}
      </div>
    </div>
  </div>
</section>"""


def _dashboard_keyword_section(model: dict[str, Any]) -> str:
    demand = model.get("demand", {})
    market = model.get("market", {})
    keyword_analysis = model.get("candidate", {}).get("demand_evidence", {})
    currency_code = model.get("currency_code", "USD")
    cards = [
        ("核心关键词", keyword_analysis.get("top_keyword", "待补"), "卖家精灵反查 / 搜索词入口"),
        ("月搜索量", _format_number(keyword_analysis.get("top_keyword_monthly_searches")), "关键词需求规模"),
        ("ABA 核心词", keyword_analysis.get("aba_top_search_term", "待补"), "亚马逊后台关键词线索"),
        ("ABA 点击 ASIN", keyword_analysis.get("aba_top_clicked_asin", "待补"), "直接可转成竞品跟踪"),
    ]
    note_items = [
        f"市场平均价：{_format_money(market.get('market_avg_price_usd'), currency_code) if market.get('market_avg_price_usd') is not None else '待填'}",
        f"市场月均销量：{_format_number(market.get('market_avg_monthly_units')) if market.get('market_avg_monthly_units') is not None else '待填'}",
        f"搜索信号：{model.get('candidate', {}).get('demand_evidence', {}).get('search_signal', '待填')}",
        f"趋势信号：{model.get('candidate', {}).get('demand_evidence', {}).get('trend_signal', '待填')}",
    ]
    return f"""
<section class="section">
  <div class="section-header">
    <div>
      <div class="eyebrow">Keyword Lens</div>
      <h2 class="section-title">流量、CPC、竞品数最好一起看</h2>
    </div>
    <div class="section-note">单看搜索量会误判，单看竞品数又会忽略需求强度。这里把关键词线索放在同一块里，方便判断切入口。</div>
  </div>
  <div class="two-col">
    <div class="subpanel">
      <div class="grid-2">
        {''.join(_render_info_card(label, value, note) for label, value, note in cards)}
      </div>
      <div class="note-list" style="margin-top:12px;">
        {''.join(f'<div class="note-item">{escape(item)}</div>' for item in note_items)}
      </div>
    </div>
    <div class="subpanel dark">
      <div class="eyebrow" style="color: rgba(215, 116, 67, 0.82);">Query Snapshot</div>
      <h3 class="section-title" style="font-size:22px; color: var(--text);">关键词信息要能直接转成动作</h3>
      <div class="stack" style="margin-top:16px;">
        {''.join(_render_info_card_dark(f'线索 {idx + 1}', item) for idx, item in enumerate(model.get('summary', {}).get('bullets', [])[:3])) if model.get('summary', {}).get('bullets') else '<div class="note-item dark">当前没有额外关键词表时，就先靠卖家精灵的搜索词、ABA 和市场分析做第一轮判断。</div>'}
      </div>
      <div class="pill-row" style="margin-top:16px;">
        <span class="pill dark">卖家精灵搜索结果</span>
        <span class="pill dark">ABA 关键词</span>
        <span class="pill dark">市场分析</span>
      </div>
    </div>
  </div>
</section>"""


def _dashboard_competitor_voc_section(model: dict[str, Any]) -> str:
    competitor_pool = model.get("competitor_pool", {})
    voc = model.get("voc", {})
    decision = model.get("decision", {})
    currency_code = model.get("currency_code", "USD")
    top10 = competitor_pool.get("top10", []) or []
    recent = competitor_pool.get("recent_winners", []) or []
    structure = competitor_pool.get("structure_supplement", []) or []
    scatter_items = top10[:10] or recent[:10] or structure[:10]
    pain_points = voc.get("pain_points", []) if isinstance(voc, dict) else []
    highlights = voc.get("highlights", []) if isinstance(voc, dict) else []
    voc_summary = voc.get("summary", {}) if isinstance(voc, dict) else {}
    right_cards = []
    if pain_points:
        right_cards.append(("首要痛点", pain_points[0].get("name", "待填"), f"{pain_points[0].get('review_count', '待填')} 条评论"))
        for item in pain_points[:4]:
            right_cards.append((item.get("name", "待填"), item.get("review_count", "待填"), item.get("severity", "待补")))
    else:
        right_cards.append(("评论 VOC", "待接入", "把评论插件导出的 Excel / HTML 喂给系统后，这里会出现差评主题和证据。"))
        for item in (decision.get("inferences", []) or [])[:3]:
            right_cards.append(("结构线索", item, "当前先靠市场和竞品判断"))
    competitor_rows = top10[:5] or recent[:5] or structure[:5]
    table_rows = []
    for item in competitor_rows:
        table_rows.append(
            "<tr>"
            f"<td>{escape(str(item.get('brand', '')))}</td>"
            f"<td>{escape(_compact_title(item.get('title'), 38))}</td>"
            f"<td>{escape(_format_money(item.get('price'), currency_code) if item.get('price') is not None else '待填')}</td>"
            f"<td>{escape(_format_number(item.get('monthly_units')) if item.get('monthly_units') is not None else '待填')}</td>"
            f"<td>{escape(str(item.get('note', '')))}</td>"
            "</tr>"
        )
    if not table_rows:
        table_rows.append('<tr><td colspan="5" class="muted">当前没有可展示的竞品明细。</td></tr>')
    entry_site_text = _format_count_items(voc_summary.get("entry_site_distribution", []), limit=2)
    review_region_text = _format_count_items(voc_summary.get("review_region_distribution", []), limit=4)
    source_note = str(voc_summary.get("source_scope_note", ""))
    voc_note = (
        f"评论数 {voc_summary.get('review_count', '待填')}，ASIN 数 {voc_summary.get('asin_count', '待填')}，"
        f"低分评论 {voc_summary.get('low_rating_count', '待填')}。"
        f"采集入口：{entry_site_text or '待填'}；评论地区：{review_region_text or '待填'}。"
        f"{source_note}"
    )
    scatter_points = []
    for item in scatter_items:
        price = _safe_float(item.get("price"))
        monthly_units = _safe_float(item.get("monthly_units"))
        if price is None or monthly_units is None:
            continue
        scatter_points.append({
            "brand": str(item.get("brand") or item.get("title") or "竞品"),
            "price": price,
            "monthly_units": monthly_units,
        })
    scatter_takeaway = "当前样本更像“价格分层 + 销量分层”并存的市场。"
    if scatter_points:
        top_sales = max(scatter_points, key=lambda point: point["monthly_units"])
        high_price = max(scatter_points, key=lambda point: point["price"])
        mid_price = _median([point["price"] for point in scatter_points])
        mid_item = min(scatter_points, key=lambda point: abs(point["price"] - mid_price))
        pattern = "低价冲量" if top_sales["price"] <= mid_price else "高价冲量"
        scatter_takeaway = (
            f"当前样本更像“{pattern} + 中价过渡 + 高价守盘”三层市场："
            f"{top_sales['brand']}（{_format_money(top_sales['price'], currency_code)} / {_format_number(top_sales['monthly_units'])}）"
            f"是销量龙头，{mid_item['brand']} 位于中价带，"
            f"{high_price['brand']}（{_format_money(high_price['price'], currency_code)} / {_format_number(high_price['monthly_units'])}）"
            f"在高价端仍有销量。"
        )
    return f"""
<section class="section">
  <div class="section-header">
    <div>
      <div class="eyebrow">Competitor & VOC</div>
      <h2 class="section-title">竞品怎么站位，差评又在打哪里</h2>
    </div>
    <div class="section-note">左边看代表竞品的价格和销量分层，右边看差评主题和改品方向。没有 VOC 时，也能先把结构线索摆出来。</div>
  </div>
  <div class="two-col">
    <div class="subpanel">
      <div class="note-item" style="margin-bottom:12px; background: rgba(215, 116, 67, 0.08); border-color: rgba(215, 116, 67, 0.18); font-weight: 600;">{escape(scatter_takeaway)}</div>
      <div class="chart-shell">
        {_render_competitor_segments(scatter_items, currency_code)}
      </div>
      <div style="margin-top:14px;">
        <table class="table">
          <thead>
            <tr><th>品牌</th><th>标题</th><th>价格</th><th>月销量</th><th>备注</th></tr>
          </thead>
          <tbody>
            {''.join(table_rows)}
          </tbody>
        </table>
      </div>
    </div>
    <div class="subpanel">
      <div class="section-header" style="margin-bottom:12px;">
        <div>
          <div class="eyebrow">VOC Notes</div>
          <h3 class="section-title" style="font-size:22px;">差评和机会点</h3>
        </div>
      </div>
      <div class="note-item" style="margin-bottom:12px;">{escape(voc_note)}</div>
      <div class="grid-2">
        {''.join(_render_info_card(item[0], item[1], item[2]) for item in right_cards[:4])}
      </div>
      <div class="note-list" style="margin-top:12px;">
        {''.join(f'<div class="note-item">{escape(str(item.get("name", "待补")))}：{escape(str(item.get("hypothesis", "待补")))} </div>' for item in (voc.get("opportunity_hypotheses", [])[:3] if isinstance(voc, dict) else [])) if voc.get("opportunity_hypotheses") else '<div class="note-item">VOC 未接入时，这里会先显示结构判断和下一步接入提示。</div>'}
      </div>
      <div class="pill-row" style="margin-top:16px;">
        {''.join(f'<span class="pill">{escape(str(item.get("name", "改品机会")))} </span>' for item in highlights[:3]) if highlights else '<span class="pill">评论插件待接入</span>'}
      </div>
    </div>
  </div>
</section>"""


def _render_competitor_segments(items: list[dict[str, Any]], currency_code: str = "USD") -> str:
    points = []
    for item in items:
        price = _safe_float(item.get("price"))
        monthly_units = _safe_float(item.get("monthly_units"))
        if price is None or monthly_units is None:
            continue
        points.append(
            {
                "brand": str(item.get("brand") or item.get("title") or "竞品"),
                "title": str(item.get("title") or ""),
                "price": price,
                "monthly_units": monthly_units,
                "rating_count": _safe_float(item.get("rating_count")) or 0,
            }
        )
    if not points:
        return '<div class="note-item">竞品价格或月销量数据不足，暂时无法分层。</div>'
    median_price = _median([point["price"] for point in points])
    median_units = _median([point["monthly_units"] for point in points])
    segments = [
        {
            "key": "low_high",
            "name": "低价冲量",
            "desc": "价格低于中位，销量高于中位。优先看它靠低价、广告还是产品力吃量。",
            "featured": True,
            "items": [],
        },
        {
            "key": "high_high",
            "name": "高价高销",
            "desc": "价格和销量都高，通常代表品牌、品质或功能壁垒。",
            "featured": False,
            "items": [],
        },
        {
            "key": "low_low",
            "name": "低价低销",
            "desc": "低价也没跑出销量，可能不是优先模仿对象。",
            "featured": False,
            "items": [],
        },
        {
            "key": "high_low",
            "name": "高价低销",
            "desc": "高价端仍有样本，适合看是否存在小众高客单切口。",
            "featured": False,
            "items": [],
        },
    ]
    segment_by_key = {segment["key"]: segment for segment in segments}
    for point in points:
        price_side = "low" if point["price"] <= median_price else "high"
        unit_side = "high" if point["monthly_units"] >= median_units else "low"
        segment_by_key[f"{price_side}_{unit_side}"]["items"].append(point)
    cards = []
    for segment in segments:
        segment_items = sorted(segment["items"], key=lambda point: point["monthly_units"], reverse=True)
        leader = segment_items[0] if segment_items else None
        if leader:
            brand = _compact_title(leader["brand"], 18)
            meta = f"{_format_money(leader['price'], currency_code)} / 月销 {_format_number(leader['monthly_units'])}"
            title = _compact_title(leader["title"], 42) if leader["title"] else "代表竞品"
            other_chips = "".join(
                f'<span class="segment-chip">{escape(_compact_title(item["brand"], 14))}</span>'
                for item in segment_items[1:4]
            )
            main = f"""
            <div class="segment-main">
              <div class="segment-brand">{escape(brand)}</div>
              <div class="segment-meta">{escape(meta)}</div>
              <div class="segment-meta">{escape(title)}</div>
            </div>
            <div class="segment-chips">{other_chips or '<span class="segment-chip">暂无更多样本</span>'}</div>
            """
        else:
            main = """
            <div class="segment-main">
              <div class="segment-brand">暂无样本</div>
              <div class="segment-meta">当前 Top 样本没有落在这一层。</div>
            </div>
            """
        cards.append(
            f"""
            <div class="segment-card {'featured' if segment.get('featured') and leader else ''}">
              <div class="segment-head">
                <div class="segment-name">{escape(str(segment["name"]))}</div>
                <div class="segment-count">{len(segment_items)} 个</div>
              </div>
              <div class="segment-desc">{escape(str(segment["desc"]))}</div>
              {main}
            </div>
            """
        )
    return f"""
    <div style="padding:16px 16px 0;">
      <div class="eyebrow">Segment View</div>
      <h3 class="section-title" style="font-size:22px; margin-top:8px;">价格 × 销量分层</h3>
      <div class="section-note" style="margin-top:4px;">用价格中位和销量中位切成四层，先看每层的代表竞品，而不是在一堆点里找答案。</div>
      <div class="section-note" style="margin-top:6px;">中位参考：价格 {_format_money(median_price, currency_code)}；月销量 {_format_number(median_units)}。</div>
    </div>
    <div class="segment-matrix">
      {''.join(cards)}
    </div>
    """


def _dashboard_market_score_section(model: dict[str, Any]) -> str:
    scorecard = model.get("scorecard", {}) if isinstance(model.get("scorecard"), dict) else {}
    decision = model.get("decision", {})
    risks = model.get("risks", []) or []
    missing_inputs = model.get("missing_inputs", []) or []
    currency_code = model.get("currency_code", "USD")
    dimensions = scorecard.get("dimensions", {}) if isinstance(scorecard.get("dimensions"), dict) else {}
    score_cards = []
    for name, payload in list(dimensions.items())[:8]:
        if not isinstance(payload, dict):
            continue
        score = payload.get("score", "待补")
        weight = payload.get("weight", "")
        note = payload.get("note", "")
        score_text = f"{score}/10" if isinstance(score, (int, float)) else str(score)
        weight_text = _format_percent_or_text(weight) if isinstance(weight, (int, float)) else str(weight)
        score_cards.append((str(name), score_text, f"权重 {weight_text}；{note}"))
    if not score_cards:
        score_cards = [
            ("市场机会评分", scorecard.get("weighted_score", "待补"), scorecard.get("note", "评分卡待补")),
            ("研究结论", scorecard.get("decision", "待补"), "只表示是否值得继续研究，不代表进入后置落地。"),
        ]
    risk_cards = []
    for risk in risks[:6]:
        if isinstance(risk, dict):
            risk_cards.append(risk)
    if not risk_cards:
        risk_cards = [
            {"dimension": "风险矩阵", "level": "待填", "basis": "小类、关键词、竞品和 VOC 证据仍待补。", "next_check": "先补能改变市场机会结论的证据。"}
        ]
    missing_line = "、".join(str(item) for item in missing_inputs[:8]) or "暂无"
    return f"""
<section class="section">
  <div class="section-header">
    <div>
      <div class="eyebrow">Decision</div>
      <h2 class="section-title">最后把结论压缩成经营动作</h2>
    </div>
    <div class="section-note">这里不是为了写长结论，而是把“能不能继续推”拆成几个维度，给运营一个马上能用的判断面板。</div>
  </div>
  <div class="two-col">
    <div class="subpanel">
      <div class="grid-2">
        {''.join(_render_info_card(label, value, note) for label, value, note in score_cards)}
      </div>
      <div class="section-header" style="margin-top:18px; margin-bottom:10px;">
        <div>
          <div class="eyebrow">Opportunity Gate</div>
          <h3 class="section-title" style="font-size:22px;">继续研究门槛</h3>
        </div>
      </div>
      <div class="note-item" style="margin-bottom:12px;">当前看板只判断市场机会和继续研究优先级；后置落地判断不在本阶段输出。</div>
      <table class="table">
        <thead><tr><th>项目</th><th>值</th></tr></thead>
        <tbody>
          <tr><td>加权总分</td><td>{escape(str(scorecard.get('weighted_score', '待补')))}</td></tr>
          <tr><td>研究结论</td><td>{escape(str(scorecard.get('decision', '待补')))}</td></tr>
          <tr><td>限制原因</td><td>{escape('、'.join(map(str, scorecard.get('gating_reasons', []) or [])) or '暂无')}</td></tr>
        </tbody>
      </table>
    </div>
    <div class="subpanel">
      <div class="section-header" style="margin-bottom:12px;">
        <div>
          <div class="eyebrow">Risk Matrix</div>
          <h3 class="section-title" style="font-size:22px;">风险和待补</h3>
        </div>
      </div>
      <div class="risk-grid">
        {''.join(_render_risk_card(risk, currency_code) for risk in risk_cards)}
      </div>
      <div class="note-item" style="margin-top:12px;">待补清单：{escape(missing_line)}</div>
      <div class="note-item" style="margin-top:12px;">第一动作：{escape(str((decision.get('action_items') or ['待补'])[0] if isinstance(decision, dict) else '待补'))}</div>
    </div>
  </div>
</section>"""


def _dashboard_footer(model: dict[str, Any]) -> str:
    return f"""
<footer class="footer">
  <div>
    <div>需要追溯时看 Excel 和 Markdown，页面先保留判断重点。</div>
  </div>
  <div class="footer-links">
    <a class="link-chip" href="{model['links']['html_report']}">网页版报告</a>
    <a class="link-chip" href="{model['links']['markdown']}">Markdown</a>
    <a class="link-chip" href="{model['links']['summary']}">摘要</a>
    <a class="link-chip" href="{model['links']['excel']}">Excel 明细</a>
  </div>
</footer>"""


def _render_distribution_panel(title: str, distribution: dict[str, Any] | None, note: str) -> str:
    if not distribution:
        return f"""
        <div class="subpanel">
          <div class="eyebrow">Distribution</div>
          <h3 class="section-title" style="font-size:22px;">{escape(title)}</h3>
          <div class="note-item" style="margin-top:12px;">{escape(note)}</div>
          <div class="note-item" style="margin-top:12px;">暂无可用分布数据。</div>
        </div>
        """
    buckets = distribution.get("buckets", [])[:5]
    rows = []
    max_share = max((float(bucket.get("share", 0)) for bucket in buckets), default=1) or 1
    for bucket in buckets:
        share = float(bucket.get("share", 0) or 0)
        width = max(6, round((share / max_share) * 100))
        rows.append(
            f"""
            <div class="bar-row">
              <div class="bar-label">{escape(str(bucket.get('value', '待填')))}</div>
              <div class="bar-track"><div class="bar-fill" style="width:{width}%"></div></div>
              <div class="bar-value">{escape(f"{bucket.get('count', 0)} / {share * 100:.1f}%")}</div>
            </div>
            """
        )
    return f"""
    <div class="subpanel">
      <div class="eyebrow">Distribution</div>
      <h3 class="section-title" style="font-size:22px;">{escape(title)}</h3>
      <div class="section-note" style="margin-top:6px;">{escape(note)}</div>
      <div class="bar-group" style="margin-top:16px;">{''.join(rows)}</div>
      <div class="note-item" style="margin-top:14px;">{escape(str(distribution.get('summary', '待填')))}</div>
    </div>
    """


def _render_info_card(label: str, value: Any, note: Any = "") -> str:
    return f"""
    <div class="info-card">
      <div class="info-label">{escape(str(label))}</div>
      <div class="info-value">{escape(_display_dashboard_value(value))}</div>
      <div class="info-note">{escape(str(note))}</div>
    </div>
    """


def _render_info_card_dark(label: str, value: Any, note: Any = "") -> str:
    return f"""
    <div class="info-card dark">
      <div class="info-label">{escape(str(label))}</div>
      <div class="info-value">{escape(_display_dashboard_value(value))}</div>
      <div class="info-note">{escape(str(note))}</div>
    </div>
    """


def _render_risk_card(risk: dict[str, Any], currency_code: str = "USD") -> str:
    level = str(risk.get("level", "待填"))
    level_class = _risk_level_class(level)
    return f"""
    <div class="risk-card">
      <div class="risk-head">
        <div class="risk-title">{escape(str(risk.get('dimension', '待填')))}</div>
        <div class="level-badge {level_class}">{escape(level)}</div>
      </div>
      <div class="risk-basis">{escape(_normalize_money_text(risk.get('basis', '待填'), currency_code))}</div>
      <div class="risk-next">下一步：{escape(_normalize_money_text(risk.get('next_check', '待补'), currency_code))}</div>
    </div>
    """


def _risk_level_class(level: str) -> str:
    if level in {"高", "强风险"}:
        return ""
    if level == "中":
        return "medium"
    if level == "低":
        return "low"
    return "wait"


def _find_distribution(distributions: list[dict[str, Any]], dimension: str) -> dict[str, Any] | None:
    for item in distributions:
        if isinstance(item, dict) and item.get("dimension") == dimension:
            return item
    return None


def _render_competitor_scatter(items: list[dict[str, Any]], currency_code: str = "USD") -> str:
    if not items:
        return """
        <div class="subpanel" style="margin:0;">
          <div class="note-item">暂无竞品散点数据。</div>
        </div>
        """
    width = 760
    height = 420
    padding_x = 64
    padding_y = 52
    prices = [_safe_float(item.get("price")) for item in items if _safe_float(item.get("price")) is not None]
    units = [_safe_float(item.get("monthly_units")) for item in items if _safe_float(item.get("monthly_units")) is not None]
    reviews = [_safe_float(item.get("rating_count")) for item in items if _safe_float(item.get("rating_count")) is not None]
    if not prices or not units:
        return '<div class="note-item">竞品价格或月销量数据不足，暂时无法绘制散点。</div>'
    min_price = min(prices)
    max_price = max(prices)
    min_unit = min(units)
    max_unit = max(units)
    median_price = _median(prices)
    median_unit = _median(units)
    max_review = max(reviews) if reviews else 1
    use_log_units = max_unit > 0 and min_unit > 0 and (max_unit / max(min_unit, 1)) >= 8
    display_min_unit = min_unit
    display_mid_unit = math.sqrt(min_unit * max_unit) if use_log_units else (min_unit + max_unit) / 2
    display_max_unit = max_unit
    palette = ["#d77443", "#3f7480", "#7d8d52", "#b18c56", "#8a6cb3", "#6f8796"]
    def scale_x(value: float) -> float:
        if max_price == min_price:
            return width / 2
        return padding_x + ((value - min_price) / (max_price - min_price)) * (width - padding_x * 2)
    def scale_y(value: float) -> float:
        if max_unit == min_unit:
            return height / 2
        if use_log_units:
            min_log = math.log10(min_unit)
            max_log = math.log10(max_unit)
            value_log = math.log10(max(value, 0.01))
            return height - padding_y - ((value_log - min_log) / (max_log - min_log)) * (height - padding_y * 2)
        return height - padding_y - ((value - min_unit) / (max_unit - min_unit)) * (height - padding_y * 2)
    circles = []
    points: list[dict[str, Any]] = []
    sorted_items = sorted(items, key=lambda item: _safe_float(item.get("monthly_units")) or 0, reverse=True)
    for index, item in enumerate(sorted_items[:14]):
        price = _safe_float(item.get("price"))
        monthly_units = _safe_float(item.get("monthly_units"))
        rating_count = _safe_float(item.get("rating_count")) or 0
        if price is None or monthly_units is None:
            continue
        cx = scale_x(price)
        cy = scale_y(monthly_units)
        r = 6 + min(16, math.log1p(max(rating_count, 0)) / 1.6 if rating_count else 4)
        color = palette[index % len(palette)]
        title = _compact_title(item.get("brand") or item.get("title") or "竞品", 16)
        points.append(
            {
                "index": index,
                "cx": cx,
                "cy": cy,
                "r": r,
                "price": price,
                "monthly_units": monthly_units,
                "rating_count": rating_count,
                "color": color,
                "title": title,
            }
        )
        circles.append(
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="{color}" fill-opacity="0.78" stroke="rgba(255,255,255,.65)" stroke-width="1.2"/>'
        )
    label_budget = min(6, len(points))
    selected_indices: set[int] = set()
    if points:
        ranked = sorted(points, key=lambda point: point["monthly_units"], reverse=True)
        selected_indices.add(int(ranked[0]["index"]))
        lowest_price = min(points, key=lambda point: point["price"])
        highest_price = max(points, key=lambda point: point["price"])
        selected_indices.add(int(lowest_price["index"]))
        selected_indices.add(int(highest_price["index"]))
        while len(selected_indices) < label_budget:
            candidates = [point for point in ranked if int(point["index"]) not in selected_indices]
            if not candidates:
                break
            best_point = None
            best_score = -1.0
            for point in candidates:
                if selected_indices:
                    distance = min(
                        math.hypot(point["cx"] - other["cx"], point["cy"] - other["cy"])
                        for other in points
                        if int(other["index"]) in selected_indices
                    )
                else:
                    distance = 999.0
                score = distance + (point["monthly_units"] / max_unit) * 60 + (point["rating_count"] / max_review if max_review else 0) * 12
                if score > best_score:
                    best_score = score
                    best_point = point
            if best_point is None:
                break
            if len(selected_indices) >= 4 and best_score < 110:
                break
            selected_indices.add(int(best_point["index"]))

    def _boxes_overlap(a: dict[str, float], b: dict[str, float], margin: float = 10) -> bool:
        return not (
            a["x2"] + margin < b["x1"]
            or a["x1"] - margin > b["x2"]
            or a["y2"] + margin < b["y1"]
            or a["y1"] - margin > b["y2"]
        )

    labels = []
    occupied_boxes: list[dict[str, float]] = []
    for point in points:
        if int(point["index"]) not in selected_indices:
            continue
        title = str(point["title"])
        price = float(point["price"])
        monthly_units = float(point["monthly_units"])
        cx = float(point["cx"])
        cy = float(point["cy"])
        number_text = f"{_format_number(price)} / {_format_number(monthly_units)}"
        label_w = max(len(title), len(number_text)) * 6.8 + 16
        label_h = 32
        candidates = [
            {"x": cx + 16, "y": cy - label_h - 8, "anchor": "start"},
            {"x": cx + 16, "y": cy + 8, "anchor": "start"},
            {"x": cx - label_w - 16, "y": cy - label_h - 8, "anchor": "end"},
            {"x": cx - label_w - 16, "y": cy + 8, "anchor": "end"},
        ]
        placed = None
        for candidate in candidates:
            box = {
                "x1": candidate["x"],
                "y1": candidate["y"],
                "x2": candidate["x"] + label_w,
                "y2": candidate["y"] + label_h,
            }
            if box["x1"] < 8 or box["y1"] < 8 or box["x2"] > width - 8 or box["y2"] > height - 8:
                continue
            if any(_boxes_overlap(box, other) for other in occupied_boxes):
                continue
            occupied_boxes.append(box)
            placed = (candidate, box)
            break
        if placed is None:
            continue
        candidate, box = placed
        label_x = candidate["x"]
        label_y = candidate["y"]
        anchor = candidate["anchor"]
        labels.append(
            f'''
            <g>
              <title>{escape(f"{title} | 价格 {number_text}")}</title>
              <text x="{label_x:.1f}" y="{label_y + 12:.1f}" text-anchor="{anchor}" font-size="12" fill="#334155" stroke="rgba(255,255,255,.88)" stroke-width="3" paint-order="stroke">{escape(str(title))}</text>
              <text x="{label_x:.1f}" y="{label_y + 25:.1f}" text-anchor="{anchor}" font-size="10" fill="#6e7480" stroke="rgba(255,255,255,.88)" stroke-width="3" paint-order="stroke">{escape(number_text)}</text>
            </g>
            '''
        )
    axis_x1 = padding_x
    axis_y1 = height - padding_y
    x_mid = scale_x(median_price)
    y_mid = scale_y(median_unit)
    tick_values_x = [min_price, (min_price + max_price) / 2, max_price]
    tick_values_y = [display_min_unit, display_mid_unit, display_max_unit]
    x_ticks = []
    for value in tick_values_x:
        x = scale_x(value)
        x_ticks.append(
            f"""
            <line x1="{x:.1f}" y1="{axis_y1}" x2="{x:.1f}" y2="{axis_y1 + 6}" stroke="rgba(32,40,51,.18)" />
            <text x="{x:.1f}" y="{axis_y1 + 22}" text-anchor="middle" font-size="11" fill="#6e7480">{escape(_format_money(value, currency_code))}</text>
            """
        )
    y_ticks = []
    for value in tick_values_y:
        y = scale_y(value)
        y_ticks.append(
            f"""
            <line x1="{axis_x1 - 6}" y1="{y:.1f}" x2="{axis_x1}" y2="{y:.1f}" stroke="rgba(32,40,51,.18)" />
            <text x="{axis_x1 - 10}" y="{y + 4:.1f}" text-anchor="end" font-size="11" fill="#6e7480">{escape(_format_number(value))}</text>
            """
        )
    title = escape("价格 vs 月销量")
    return f"""
    <div style="padding:16px 16px 8px;">
      <div class="eyebrow">Scatter View</div>
      <h3 class="section-title" style="font-size:22px; margin-top:8px;">代表竞品：{title}</h3>
      <div class="section-note" style="margin-top:4px;">这张图主要看价格和销量怎么分层：左上低价冲量，右上高价高销，右下高价低销。中位参考线帮你快速看出谁在冲量、谁在守盘。</div>
      <div class="pill-row" style="margin-top:10px;">
        <span class="pill">左上 = 低价冲量</span>
        <span class="pill">右上 = 高价高销</span>
        <span class="pill">右下 = 高价低销</span>
      </div>
    </div>
    <svg class="chart-svg" viewBox="0 0 {width} {height}" role="img" aria-label="竞品价格与月销量散点图">
      <rect x="0" y="0" width="{width}" height="{height}" fill="transparent" />
      <line x1="{x_mid:.1f}" y1="{padding_y}" x2="{x_mid:.1f}" y2="{axis_y1}" stroke="rgba(32,40,51,.12)" stroke-dasharray="5 6" />
      <line x1="{axis_x1}" y1="{y_mid:.1f}" x2="{width - padding_x/2}" y2="{y_mid:.1f}" stroke="rgba(32,40,51,.12)" stroke-dasharray="5 6" />
      <line x1="{axis_x1}" y1="{padding_y}" x2="{axis_x1}" y2="{axis_y1}" stroke="rgba(32,40,51,.22)" stroke-width="1.2" />
      <line x1="{axis_x1}" y1="{axis_y1}" x2="{width - padding_x/2}" y2="{axis_y1}" stroke="rgba(32,40,51,.22)" stroke-width="1.2" />
      {''.join(x_ticks)}
      {''.join(y_ticks)}
      <text x="{axis_x1}" y="{padding_y - 14}" font-size="12" fill="#6e7480">月销量{escape('（压缩）' if use_log_units else '')}</text>
      <text x="{width - padding_x}" y="{axis_y1 + 38}" text-anchor="end" font-size="12" fill="#6e7480">价格</text>
      <text x="{x_mid + 8:.1f}" y="{padding_y + 16}" font-size="11" fill="#8a92a0">价格中位</text>
      <text x="{axis_x1 + 8}" y="{y_mid - 8:.1f}" font-size="11" fill="#8a92a0">销量中位</text>
      <text x="{axis_x1 + 10}" y="{padding_y + 20}" font-size="11" fill="#8a92a0">低价高销</text>
      <text x="{width - 124}" y="{padding_y + 20}" font-size="11" fill="#8a92a0">高价高销</text>
      <text x="{axis_x1 + 10}" y="{axis_y1 - 12}" font-size="11" fill="#8a92a0">低价低销</text>
      <text x="{width - 124}" y="{axis_y1 - 12}" font-size="11" fill="#8a92a0">高价低销</text>
      {''.join(circles)}
      {''.join(labels)}
    </svg>
    """
