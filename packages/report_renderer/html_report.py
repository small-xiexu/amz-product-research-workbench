"""HTML decision report renderer.

The Markdown report keeps the full 12-section audit trail. This HTML report is
for product-selection decisions: conclusion first, evidence second, raw tables
last.
"""

from __future__ import annotations

import re
from html import escape
from typing import Any

from packages.report_renderer.formatting import (
    _clean_display_title,
    _format_number,
    _polish_punctuation,
    _site_currency_code,
)


def render_report_html(package: dict[str, Any]) -> str:
    model = _decision_model(package)
    title = model["title"]
    sections = [
        _hero_section(model),
        _data_sources_section(model),
        _quick_read_section(model),
        _ai_analysis_section(model),
        _route_matrix_section(model),
        _market_section(model),
        _voc_section(model),
        _market_score_section(model),
        _next_steps_section(model),
        _appendix_section(model),
    ]
    html = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)} / 选品决策报告</title>
  <style>{DECISION_REPORT_STYLE}</style>
</head>
<body>
  <header class="topbar">
    <a href="#conclusion">结论</a>
    <a href="#sources">数据源</a>
    <a href="#ai-analysis">AI分析</a>
    <a href="#routes">路线</a>
    <a href="#market">市场</a>
    <a href="#sorftime">Sorftime</a>
    <a href="#voc">评价</a>
    <a href="#score">评分</a>
    <a href="#next-steps">下一步</a>
    <a href="data.xlsx">Excel底表</a>
    <a href="report.md">完整Markdown</a>
  </header>
  <main class="page">
    {''.join(sections)}
  </main>
</body>
</html>"""
    return _polish_punctuation(html)


def _decision_model(package: dict[str, Any]) -> dict[str, Any]:
    meta = package.get("metadata", {}) if isinstance(package, dict) else {}
    status = package.get("status_card", {}) if isinstance(package.get("status_card"), dict) else {}
    decision = package.get("decision_review", {}) if isinstance(package.get("decision_review"), dict) else {}
    market = package.get("market_analysis", {}) if isinstance(package.get("market_analysis"), dict) else {}
    market_structure = package.get("market_structure", {}) if isinstance(package.get("market_structure"), dict) else {}
    voc = package.get("voc_analysis", {}) if isinstance(package.get("voc_analysis"), dict) else {}
    ai_analysis = package.get("ai_analysis", {}) if isinstance(package.get("ai_analysis"), dict) else {}
    candidate = package.get("normalized_tables", {}).get("candidate", {}) if isinstance(package.get("normalized_tables"), dict) else {}
    if not isinstance(candidate, dict):
        candidate = {}
    demand = candidate.get("demand_evidence", {}) if isinstance(candidate.get("demand_evidence"), dict) else {}
    sorftime = candidate.get("sorftime_verification", {}) if isinstance(candidate.get("sorftime_verification"), dict) else {}
    scorecard = decision.get("go_nogo_scorecard", {}) if isinstance(decision.get("go_nogo_scorecard"), dict) else {}
    site = str(meta.get("site") or "US")
    return {
        "title": _clean_report_title(meta.get("seed_keyword_or_category", "AMZ 选品报告")),
        "site": site,
        "currency": _site_currency_code(site),
        "status": str(status.get("status") or scorecard.get("decision") or "待判断"),
        "status_reason": _clean_sentence(status.get("reason") or decision.get("status_explanation") or ""),
        "next_step": _clean_sentence(status.get("next_step") or _default_next_step(decision)),
        "decision": decision,
        "scorecard": scorecard,
        "market": market,
        "market_structure": market_structure,
        "voc": voc,
        "ai_analysis": ai_analysis,
        "route_matrix": package.get("product_route_matrix") if isinstance(package.get("product_route_matrix"), list) else ai_analysis.get("product_route_matrix", []),
        "route_deep_dive_plan": package.get("route_deep_dive_plan") if isinstance(package.get("route_deep_dive_plan"), list) else ai_analysis.get("route_deep_dive_plan", []),
        "candidate": candidate,
        "demand": demand,
        "sorftime": sorftime,
        "data_sources": meta.get("data_sources", []) if isinstance(meta.get("data_sources"), list) else [],
        "operator_inputs": package.get("operator_inputs", {}) if isinstance(package.get("operator_inputs"), dict) else {},
    }


def _default_next_step(decision: dict[str, Any]) -> str:
    missing = decision.get("missing_inputs") if isinstance(decision.get("missing_inputs"), list) else []
    if missing:
        return f"先补齐：{'、'.join(map(str, missing[:4]))}"
    return "补齐小类、关键词、竞品和 VOC 证据后再判断是否继续深挖。"


def _hero_section(model: dict[str, Any]) -> str:
    status = model["status"]
    score = model["scorecard"].get("weighted_score")
    score_text = f"{score}/10" if score not in (None, "") else "待补"
    gating = model["scorecard"].get("gating_reasons") or model["decision"].get("missing_inputs") or []
    return f"""
<section class="hero" id="conclusion">
  <div class="hero-copy">
    <div class="eyebrow">选品决策报告</div>
    <h1>{escape(model["title"])}</h1>
    <p class="lead">{escape(_plain_decision_sentence(model))}</p>
    <div class="chip-row">
      <span class="chip strong">{escape(status)}</span>
      <span class="chip">评分 {escape(score_text)}</span>
      <span class="chip">站点 {escape(model["site"])}</span>
    </div>
  </div>
  <aside class="decision-card">
    <div class="decision-label">现在怎么判断</div>
    <div class="decision-value">{escape(status)}</div>
    <p>{escape(model["status_reason"] or "已有数据支持继续看，但还不能直接 Go。")}</p>
    <div class="block-title">卡点</div>
    {_simple_list(gating[:5] or ["大类、小类、关键词、竞品和 VOC 证据仍需交叉验证。"])}
  </aside>
</section>"""


def _quick_read_section(model: dict[str, Any]) -> str:
    voc_summary = model["voc"].get("summary", {}) if isinstance(model["voc"].get("summary"), dict) else {}
    market = model["market"]
    top_sorftime = _top_sorftime_keyword(model)
    cards = [
        ("市场", _market_short_label(market), market.get("market_size", "待补")),
        ("Sorftime", top_sorftime[0], top_sorftime[1]),
        ("评价", f"{voc_summary.get('review_count', 0)} 条评论", f"低分 {voc_summary.get('low_rating_count', 0)} 条；覆盖 {voc_summary.get('asin_count', 0)} 个 ASIN"),
        ("路线", f"{len(model.get('route_matrix', []))} 条路线", "主线、升级、场景和套装分开判断"),
    ]
    return f"""
<section class="section quick-read">
  <div class="section-head">
    <h2>一眼看懂</h2>
    <p>先看这些，再决定要不要继续花时间。</p>
  </div>
  <div class="metric-grid">
    {''.join(_metric_card(label, value, note) for label, value, note in cards)}
  </div>
</section>"""


def _data_sources_section(model: dict[str, Any]) -> str:
    cards = [
        ("卖家精灵", "市场 / Top 商品 / 关键词反查", _source_status(model, "seller_sprite")),
        ("Sorftime", "关键词 / 类目 / 竞品流量词", _source_status(model, "sorftime")),
        ("评价插件", "评论 VOC / 低分证据", _source_status(model, "review")),
        ("路线矩阵", "大类 / 小类 / 代表 ASIN", f"{len(model.get('route_matrix', []))} 条路线"),
    ]
    return f"""
<section class="section source-section" id="sources">
  <div class="section-head">
    <h2>四份数据怎么一起看</h2>
    <p>卖家精灵看市场底盘，Sorftime 看实时变化，评价插件看真实吐槽，路线矩阵看机会边界是否清楚。</p>
  </div>
  <div class="source-grid">
    {''.join(_source_card(*card) for card in cards)}
  </div>
	</section>"""


def _ai_analysis_section(model: dict[str, Any]) -> str:
    ai_analysis = model.get("ai_analysis", {}) if isinstance(model.get("ai_analysis"), dict) else {}
    persona = str(ai_analysis.get("persona") or "资深亚马逊运营专家")
    role_scope = str(ai_analysis.get("role_scope") or "先把话说明白，再看证据：这块只讲能不能继续、还差什么、卡在哪。")
    decision_principle = str(ai_analysis.get("decision_principle") or "本报告只判断市场机会和继续研究优先级，不输出采购或上架结论。")
    thesis = _ai_analysis_thesis(model, ai_analysis)
    insight_items = _analysis_items_from_package(ai_analysis) or _ai_insight_items(model)
    spec_actions = _list_from_package(ai_analysis.get("product_spec_actions")) or _product_spec_actions(model)
    market_actions = _list_from_package(ai_analysis.get("market_validation_actions")) or _market_validation_actions(model)
    source_scope = _list_from_package(ai_analysis.get("data_source_scope"))
    return f"""
<section class="section ai-analysis" id="ai-analysis">
  <div class="section-head">
    <h2>AI 综合分析</h2>
    <p>{escape(role_scope)}</p>
  </div>
  <div class="analysis-thesis">
    <div class="analysis-persona">{escape(persona)}视角</div>
    <span>综合判断</span>
    <strong>{escape(thesis[0])}</strong>
    <p>{escape(thesis[1])}</p>
    <p class="analysis-principle">{escape(decision_principle)}</p>
  </div>
  {_analysis_sources(source_scope)}
  <div class="analysis-grid">
    {''.join(_analysis_item_card(item) for item in insight_items)}
  </div>
  <div class="spec-bridge">
    <div>
      <h3>评论要变成怎么改</h3>
      {_simple_list(spec_actions)}
    </div>
    <div>
      <h3>下一轮市场验证</h3>
      {_simple_list(market_actions)}
    </div>
  </div>
</section>"""


def _route_matrix_section(model: dict[str, Any]) -> str:
    routes = model.get("route_matrix") if isinstance(model.get("route_matrix"), list) else []
    deep_dive_plan = model.get("route_deep_dive_plan") if isinstance(model.get("route_deep_dive_plan"), list) else []
    return f"""
<section class="section route-section" id="routes">
  <div class="section-head">
    <h2>产品路线对比</h2>
    <p>先把可能的款式铺开，再逐路线补数据，最后只让证据最完整的 1-2 条进入完整深挖。</p>
  </div>
  <div class="route-grid">
    {''.join(_route_card(route) for route in routes) or _empty_state("还没有形成产品路线矩阵，先补代表 ASIN、关键词和产品形态标签。")}
  </div>
  {_route_deep_dive_plan_block(deep_dive_plan)}
</section>"""


def _route_card(route: dict[str, Any]) -> str:
    representatives = route.get("representative_items") if isinstance(route.get("representative_items"), list) else []
    actions = route.get("validation_actions") if isinstance(route.get("validation_actions"), list) else []
    count_line = (
        f"{route.get('candidate_count', 0)} 个候选，"
        f"优先 {route.get('priority_count', 0)}，观察 {route.get('watchlist_count', 0)}"
    )
    return f"""
<article class="route-card">
  <div class="route-topline">
    <span>{escape(str(route.get("route_type") or "路线"))}</span>
    <strong>{escape(str(route.get("price_text") or "价格带待补"))}</strong>
  </div>
  <h3>{escape(str(route.get("route_name") or "未命名路线"))}</h3>
  <p class="route-count">{escape(count_line)}</p>
  <div class="route-copy">
    <strong>机会</strong>
    <p>{escape(str(route.get("opportunity") or "待判断"))}</p>
    <strong>风险</strong>
    <p>{escape(str(route.get("risks") or "待验证"))}</p>
  </div>
  {_route_representatives(representatives)}
  <div class="route-next">
    <strong>下一步验证</strong>
    {_simple_list(actions[:3] or [route.get("decision_hint") or "补代表竞品、评论证据和产品验证依据。"])}
  </div>
</article>"""


def _route_representatives(items: list[Any]) -> str:
    if not items:
        return '<div class="route-items empty-route">当前没有明确候选，后续找货要主动补这条路线。</div>'
    rows = []
    for item in items[:3]:
        if not isinstance(item, dict):
            continue
        title = _truncate(str(item.get("title") or "未命名商品"), 38)
        url = str(item.get("url") or "")
        price = str(item.get("price_text") or "价格带待补")
        status = str(item.get("status") or "待确认")
        title_html = (
            f'<a href="{escape(url)}" target="_blank" rel="noopener noreferrer">{escape(title)}</a>'
            if url
            else escape(title)
        )
        rows.append(f"<li>{title_html}<span>{escape(status)} / {escape(price)}</span></li>")
    return f'<ul class="route-items">{"".join(rows)}</ul>' if rows else '<div class="route-items empty-route">暂无代表商品。</div>'


def _route_deep_dive_plan_block(plan: list[Any]) -> str:
    if not plan:
        return ""
    return f"""
  <div class="route-plan">
    <div class="subsection-head">
      <h3>路线级小深挖计划</h3>
      <p>每条保留路线都要单独补卖家精灵、Sorftime、评价和代表竞品证据，再决定是否进入主推。</p>
    </div>
    <div class="route-plan-grid">
      {''.join(_route_plan_card(item) for item in plan)}
    </div>
  </div>"""


def _route_plan_card(item: Any) -> str:
    if not isinstance(item, dict):
        return ""
    asins = item.get("review_voc_asin_plan") if isinstance(item.get("review_voc_asin_plan"), list) else []
    gaps = item.get("data_gaps") if isinstance(item.get("data_gaps"), list) else []
    searches = item.get("route_search_terms") if isinstance(item.get("route_search_terms"), list) else []
    sorftime = item.get("sorftime_checks") if isinstance(item.get("sorftime_checks"), list) else []
    coverage = item.get("review_coverage") if isinstance(item.get("review_coverage"), dict) else {}
    asins_html = _route_plan_asins(asins)
    gaps_html = _simple_list(gaps[:3] or [item.get("next_step") or "这条路线暂时没有明显缺口，进入下一轮人工复核。"])
    return f"""
<article class="route-plan-card">
  <div class="route-plan-head">
    <span>{escape(str(item.get("recommended_depth") or "路线小深挖"))}</span>
    <strong>{escape(str(item.get("current_evidence_level") or "待补"))}证据</strong>
  </div>
  <h3>{escape(str(item.get("route_name") or "未命名路线"))}</h3>
  <p>{escape(str(item.get("why") or ""))}</p>
  <div class="route-plan-facts">
    <div><b>评价覆盖</b><span>{escape(str(coverage.get("matched_review_count", 0)))} 条 / {escape(str(len(coverage.get("matched_asins", []) if isinstance(coverage.get("matched_asins"), list) else [])))} 个 ASIN</span></div>
    <div><b>路线搜索词</b><span>{escape("、".join(map(str, searches[:3])) or "待补关键词")}</span></div>
  </div>
  <div class="route-plan-sub">
    <strong>建议 VOC ASIN</strong>
    {asins_html}
  </div>
  <div class="route-plan-sub">
    <strong>Sorftime 要看</strong>
    {_simple_list(sorftime[:2] or ["补路线专属 keyword_detail 和竞品流量词。"])}
  </div>
  <div class="route-plan-sub">
    <strong>现在缺什么</strong>
    {gaps_html}
  </div>
</article>"""


def _route_plan_asins(asins: list[Any]) -> str:
    if not asins:
        return '<div class="empty-route">还没有路线专属 ASIN，需要先补竞品。</div>'
    rows = []
    for item in asins[:4]:
        if not isinstance(item, dict):
            continue
        asin = str(item.get("asin") or "待补")
        title = _truncate(str(item.get("title") or ""), 44)
        ctype = str(item.get("competitor_type") or "竞品")
        rows.append(f"<li><b>{escape(asin)}</b><span>{escape(ctype)} · {escape(title)}</span></li>")
    return f'<ul class="route-plan-asins">{"".join(rows)}</ul>' if rows else '<div class="empty-route">还没有路线专属 ASIN。</div>'


def _market_section(model: dict[str, Any]) -> str:
    market = model["market"]
    summary = model["market_structure"].get("summary", {}) if isinstance(model["market_structure"].get("summary"), dict) else {}
    warnings = summary.get("warnings") if isinstance(summary.get("warnings"), list) else []
    sorftime_html = _sorftime_section(model)
    rows = [
        ("市场体量", market.get("market_size", "待补")),
        ("价格带", market.get("price_band", "待补")),
        ("竞争格局", market.get("brand_concentration", "待补")),
        ("新品机会", market.get("new_listing_ratio", "待补")),
        ("退货风险", market.get("return_rate", "待补")),
    ]
    return f"""
<section class="section" id="market">
  <div class="section-head">
    <h2>市场判断</h2>
    <p>这个方向有需求，但头部集中度不低，不能靠普通低价款硬冲。</p>
  </div>
  <div class="fact-table">{''.join(_fact_row(label, value) for label, value in rows)}</div>
  {_callout("数据口径提醒", "；".join(map(str, warnings[:2])) if warnings else "暂无明显数据口径提醒。", "muted")}
  {sorftime_html}
	</section>"""


def _sorftime_section(model: dict[str, Any]) -> str:
    keywords = _sorftime_keywords(model)
    traffic_groups = _traffic_groups(model)
    category = _sorftime_category_report(model)
    trend = model.get("demand", {}).get("sorftime_category_trend", {})
    category_rows = []
    if isinstance(category, dict) and category:
        category_rows = [
            ("类目", f"{category.get('category_name', '待补')} / nodeId {category.get('node_id', '待补')}"),
            ("Top 样本", f"{category.get('product_count', '待补')} 个；总月销量 {_format_number(category.get('total_monthly_units')) if category.get('total_monthly_units') is not None else '待补'}"),
            ("集中度", f"Top3 商品占比 {_percent(category.get('top3_product_units_share'))}；头部品牌 {category.get('top_brand', '待补')}"),
        ]
    if isinstance(trend, dict) and trend:
        category_rows.append(("趋势", trend.get("trend_direction") or trend.get("trend_summary") or "已接入"))
    return f"""
<div class="sorftime-panel" id="sorftime">
  <div class="subsection-head">
    <h3>Sorftime 实时验证</h3>
    <p>用实时关键词、类目和竞品流量词校验卖家精灵导出，重点看混池和需求强度。</p>
  </div>
  <div class="sorftime-layout">
    <div class="sorftime-keywords">
      {''.join(_keyword_row(item) for item in keywords[:7]) or _empty_state("Sorftime 关键词待接入。")}
    </div>
    <div class="sorftime-side">
      <h4>类目背景</h4>
      <div class="mini-facts">{''.join(_mini_fact(label, value) for label, value in category_rows) or _empty_state("category_report 待接入。")}</div>
      <h4>竞品流量词</h4>
      <div class="traffic-list">{''.join(_traffic_card(item) for item in traffic_groups[:4]) or _empty_state("product_traffic_terms 待接入。")}</div>
    </div>
  </div>
</div>"""


def _voc_section(model: dict[str, Any]) -> str:
    voc = model["voc"]
    summary = voc.get("summary", {}) if isinstance(voc.get("summary"), dict) else {}
    pain_points = voc.get("pain_points") if isinstance(voc.get("pain_points"), list) else []
    highlights = voc.get("highlights") if isinstance(voc.get("highlights"), list) else []
    if not pain_points:
        pain_points = _fallback_voc_pain_points()
    if not highlights:
        highlights = _fallback_voc_highlights()
    scope_note = summary.get("source_scope_note") or voc.get("source_scope", {}).get("note", "")
    return f"""
<section class="section" id="voc">
  <div class="section-head">
    <h2>评价告诉我们什么</h2>
    <p>这里看真实用户为什么买、为什么骂，直接转成产品改款方向。</p>
  </div>
  <div class="split">
    <div>
      <h3>主要差评痛点</h3>
      <div class="stack">{''.join(_finding_card(item) for item in pain_points[:6])}</div>
    </div>
    <div>
      <h3>可以保留的卖点</h3>
      <div class="stack">{''.join(_finding_card(item) for item in highlights[:5])}</div>
    </div>
  </div>
  <div class="note-line">样本：{escape(str(summary.get("review_count", 0)))} 条评论，{escape(str(summary.get("asin_count", 0)))} 个 ASIN，低分 {escape(str(summary.get("low_rating_count", 0)))} 条。{escape(str(scope_note))}</div>
</section>"""


def _market_score_section(model: dict[str, Any]) -> str:
    decision = model["decision"]
    risks = decision.get("risk_matrix") if isinstance(decision.get("risk_matrix"), list) else []
    missing = decision.get("missing_inputs") if isinstance(decision.get("missing_inputs"), list) else []
    scorecard = model["scorecard"]
    dims = scorecard.get("dimensions") if isinstance(scorecard.get("dimensions"), dict) else {}
    return f"""
<section class="section" id="score">
  <div class="section-head">
    <h2>市场机会评分</h2>
    <p>这里判断的是是否值得继续研究，不是采购、试单或上架结论。</p>
  </div>
  <div class="split">
    <div>
      <h3>必须补齐</h3>
      {_simple_list(missing[:8] or ["小类 Top100、关键词反查、代表竞品和评论 VOC。"])}
    </div>
    <div>
      <div class="mini-section-head">
        <h3>评分简表</h3>
        <p>满分 10 分，分数越高代表越有利。</p>
      </div>
      <div class="score-list">{''.join(_score_row(name, item) for name, item in dims.items()) or _empty_state("暂无评分卡。")}</div>
    </div>
  </div>
  <h3>主要风险</h3>
  <div class="risk-grid">{''.join(_risk_card(item) for item in risks[:8])}</div>
</section>"""


def _next_steps_section(model: dict[str, Any]) -> str:
    steps = [
        ("1", "确认目标小类", "补小类 Top100 和类目报告，确认大类与小类不是混池。"),
        ("2", "补关键词反查", "按主线、升级、场景和套装路线分别看成交词和混池词。"),
        ("3", "补代表竞品", "每条保留路线至少保留 2-3 个代表 ASIN，作为后续 VOC 和流量词入口。"),
        ("4", "把 VOC 转产品规格", "把高频差评拆成尺寸、材质、结构、配件、包装和说明书检查项。"),
    ]
    return f"""
<section class="section" id="next-steps">
  <div class="section-head">
    <h2>下一步怎么推进</h2>
    <p>先补会改变结论的东西，不做中看不中用的分析。</p>
  </div>
  <div class="step-grid">{''.join(_step_card(*step) for step in steps)}</div>
</section>"""


def _appendix_section(model: dict[str, Any]) -> str:
    return """
<section class="section appendix">
  <div class="section-head">
    <h2>证据入口</h2>
    <p>需要追溯时下载底表或完整 Markdown 报告。</p>
  </div>
  <div class="link-grid">
    <a href="data.xlsx" download>下载 Excel 报表</a>
    <a href="report.md" download>下载 Markdown 报告</a>
  </div>
</section>"""


def _plain_decision_sentence(model: dict[str, Any]) -> str:
    status = model["status"]
    if status in {"继续看", "WAIT", "Wait", "观察"}:
        return "当前建议继续看，但结论只停在市场机会层，需要继续补小类、关键词、竞品和 VOC 证据。"
    return model["status_reason"] or "当前结论需要结合市场、关键词、竞品和 VOC 证据复核。"


def _ai_analysis_thesis(model: dict[str, Any], ai_analysis: dict[str, Any] | None = None) -> tuple[str, str]:
    if isinstance(ai_analysis, dict):
        thesis = ai_analysis.get("thesis")
        if isinstance(thesis, dict):
            title = str(thesis.get("title") or "").strip()
            body = str(thesis.get("body") or "").strip()
            if title or body:
                return title or "继续看，但不要直接立项。", body
    status = str(model.get("status") or "WAIT")
    voc_summary = model.get("voc", {}).get("summary", {}) if isinstance(model.get("voc"), dict) else {}
    review_count = voc_summary.get("review_count") or 0
    if status.upper() == "GO":
        return (
            "市场机会可以继续深挖，但不是采购或上架结论。",
            f"现在已经有 {review_count} 条评价证据和路线矩阵支撑；下一步继续补小类和关键词证据。",
        )
    return (
        "继续看，但结论只停在市场机会层。",
        f"现在能推着往前走的证据有：评价样本 {review_count} 条和路线矩阵；真正卡住的是小类、关键词、竞品和 VOC 证据是否足够闭环。",
    )


def _analysis_items_from_package(ai_analysis: dict[str, Any]) -> list[dict[str, str]]:
    items = ai_analysis.get("insights")
    if not isinstance(items, list):
        return []
    result = []
    for item in items:
        if not isinstance(item, dict):
            continue
        result.append(
            {
                "label": str(item.get("label") or "分析"),
                "title": str(item.get("title") or ""),
                "body": str(item.get("body") or ""),
            }
        )
    return result


def _list_from_package(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if item not in (None, "")]


def _analysis_sources(items: list[str]) -> str:
    if not items:
        return ""
    return f"""
  <div class="analysis-sources">
    {''.join(f'<span>{escape(item)}</span>' for item in items[:4])}
  </div>"""


def _ai_insight_items(model: dict[str, Any]) -> list[dict[str, str]]:
    market = model.get("market", {})
    voc = model.get("voc", {})
    scorecard = model.get("scorecard", {})
    voc_summary = voc.get("summary", {}) if isinstance(voc.get("summary"), dict) else {}
    keywords = _sorftime_keywords(model)
    target_keyword = keywords[0] if keywords else {}
    gating = scorecard.get("gating_reasons") if isinstance(scorecard.get("gating_reasons"), list) else []
    return [
        {
            "label": "市场能不能进",
            "title": "有量，但不能拿普通款硬冲",
            "body": _join_text(
                market.get("market_size", "市场数据待补"),
                f"Sorftime 核心词 {target_keyword.get('keyword', '待补')} 月搜 {_format_number(target_keyword.get('monthly_search_volume'))}",
            ),
        },
        {
            "label": "评论里在说啥",
            "title": "最要命的是稳不稳、好不好用",
            "body": f"已经看了 {voc_summary.get('review_count', 0)} 条评论，低分 {voc_summary.get('low_rating_count', 0)} 条；下一步要把差评里的尺寸、材质、结构和使用体验问题写进样品验证清单。",
        },
        {
            "label": "小类和竞品是否对齐",
            "title": "先确认边界，再谈产品方案",
            "body": f"路线矩阵已拆出 {len(model.get('route_matrix', []))} 条路线；下一步按路线补代表 ASIN、关键词反查和 VOC。",
        },
        {
            "label": "现在卡哪",
            "title": "证据没闭环前先别冲",
            "body": "；".join(map(str, gating[:3])) if gating else "小类、关键词、竞品和 VOC 还要补。",
        },
    ]


def _analysis_item_card(item: dict[str, str]) -> str:
    return f"""
<article class="analysis-card">
  <div>{escape(item.get("label", "分析"))}</div>
  <h3>{escape(item.get("title", ""))}</h3>
  <p>{escape(item.get("body", ""))}</p>
</article>"""


def _product_spec_actions(model: dict[str, Any]) -> list[str]:
    return [
        "基础体验：尺寸、手感、稳定性和操作门槛先测清楚。",
        "结构耐用：连接处、缝线、扣件、边角和易损件要重点看。",
        "升级卖点：升级款必须有实物差异和测试证据，不能只靠标题词。",
        "包装说明：配件、说明书、警示语和缺件风险要提前确认。",
    ]


def _market_validation_actions(model: dict[str, Any]) -> list[str]:
    return [
        "主线、升级、场景和套装路线分别补代表 ASIN。",
        "每条保留路线单独看关键词反查，拆出主词、转化词、长尾词和混池词。",
        "VOC 按路线分组，不把旁支竞品的痛点直接套到主线。",
        "先判断市场机会是否值得继续研究，再决定是否进入更后置的落地验证。",
    ]


def _join_text(*parts: Any) -> str:
    return "；".join(str(part) for part in parts if part not in (None, ""))


def _market_short_label(market: dict[str, Any]) -> str:
    text = str(market.get("market_size") or "")
    match = re.search(r"市场月均销量\s*([^；;]+)", text)
    return f"月均销量 {match.group(1).strip()}" if match else "已接入"


def _metric_card(label: str, value: Any, note: Any) -> str:
    return f"""
<div class="metric-card">
  <div class="metric-label">{escape(str(label))}</div>
  <div class="metric-value">{escape(str(value))}</div>
  <div class="metric-note">{escape(str(note))}</div>
</div>"""


def _fact_row(label: str, value: Any) -> str:
    return f"""
<div class="fact-row">
  <div class="fact-label">{escape(str(label))}</div>
  <div class="fact-value">{escape(str(value))}</div>
</div>"""


def _finding_card(item: dict[str, Any]) -> str:
    name = item.get("name") or item.get("title") or "待归纳"
    count = item.get("review_count") or item.get("count") or ""
    description = item.get("description") or item.get("typical_problem") or item.get("hypothesis") or item.get("note") or ""
    evidence = item.get("evidence_review_ids") or item.get("evidence") or []
    if isinstance(evidence, list):
        evidence_text = "、".join(str(x.get("review_id", x)) if isinstance(x, dict) else str(x) for x in evidence[:4])
    else:
        evidence_text = str(evidence)
    return f"""
<article class="finding-card">
  <h4>{escape(str(name))}</h4>
  <p>{escape(str(description))}</p>
  <div class="tiny">{escape(_count_suffix(count))}{escape((" 证据：" + evidence_text) if evidence_text else "")}</div>
</article>"""


def _risk_notes(items: list[Any]) -> str:
    if not items:
        return ""
    return (
        '<div class="note-check"><strong>还要确认</strong><ul class="mini-list">'
        + "".join(f"<li>{escape(str(item))}</li>" for item in items[:3])
        + "</ul></div>"
    )


def _tag_chips(items: list[Any]) -> str:
    if not items:
        return ""
    return '<div class="tag-row">' + "".join(f"<span>{escape(str(item))}</span>" for item in items) + "</div>"


def _score_row(name: str, item: dict[str, Any]) -> str:
    score = _score_text(item.get("score", "待补"))
    note = item.get("note", "")
    return f"""
<div class="score-row">
  <span>{escape(str(name))}</span>
  <strong>{escape(score)}</strong>
  <em>{escape(str(note))}</em>
</div>"""


def _score_text(score: Any) -> str:
    if isinstance(score, (int, float)):
        return f"{score:.1f}/10"
    text = str(score or "待补")
    if text == "待补" or "/" in text:
        return text
    try:
        return f"{float(text):.1f}/10"
    except ValueError:
        return text


def _risk_card(item: dict[str, Any]) -> str:
    return f"""
<article class="risk-card">
  <div class="risk-level">{escape(str(item.get("level", "待补")))}</div>
  <h4>{escape(str(item.get("dimension", "风险项")))}</h4>
  <p>{escape(str(item.get("basis", "待补")))}</p>
</article>"""


def _step_card(index: str, title: str, body: str) -> str:
    return f"""
<article class="step-card">
  <div class="step-index">{escape(index)}</div>
  <h3>{escape(title)}</h3>
  <p>{escape(body)}</p>
</article>"""


def _source_card(title: str, scope: str, status: str) -> str:
    return f"""
<article class="source-card">
  <h3>{escape(title)}</h3>
  <p>{escape(scope)}</p>
  <strong>{escape(status)}</strong>
</article>"""


def _source_status(model: dict[str, Any], source: str) -> str:
    sources = [str(item) for item in model.get("data_sources", [])]
    if source == "seller_sprite":
        count = sum(1 for item in sources if item.startswith("manual_export:"))
        return f"已接入 {count} 个导出文件" if count else "待接入"
    if source == "sorftime":
        keywords = len(_sorftime_keywords(model))
        traffic = len(_traffic_groups(model))
        category = _sorftime_category_report(model)
        return f"已接入 {keywords} 个关键词、{traffic} 个竞品流量词" + ("、类目报告" if category else "")
    if source == "review":
        summary = model.get("voc", {}).get("summary", {}) if isinstance(model.get("voc"), dict) else {}
        return f"已接入 {summary.get('review_count', 0)} 条评论"
    return "待接入"


def _sorftime_keywords(model: dict[str, Any]) -> list[dict[str, Any]]:
    demand = model.get("demand", {}) if isinstance(model.get("demand"), dict) else {}
    keywords = demand.get("sorftime_keyword_verification", [])
    if isinstance(keywords, list) and keywords:
        return [item for item in keywords if isinstance(item, dict)]
    sorftime = model.get("sorftime", {}) if isinstance(model.get("sorftime"), dict) else {}
    entries = sorftime.get("keyword_entries", [])
    return [item for item in entries if isinstance(item, dict)] if isinstance(entries, list) else []


def _sorftime_category_report(model: dict[str, Any]) -> dict[str, Any]:
    demand = model.get("demand", {}) if isinstance(model.get("demand"), dict) else {}
    category = demand.get("sorftime_category_report", {})
    if isinstance(category, dict) and category:
        return category
    sorftime = model.get("sorftime", {}) if isinstance(model.get("sorftime"), dict) else {}
    candidates = sorftime.get("category_candidates", [])
    if isinstance(candidates, list) and candidates:
        first = candidates[0]
        return first if isinstance(first, dict) else {}
    return {}


def _top_sorftime_keyword(model: dict[str, Any]) -> tuple[str, str]:
    keywords = _sorftime_keywords(model)
    if not keywords:
        return "待接入", "还没有 Sorftime keyword_detail"
    target = keywords[0]
    return (
        f"{_format_number(target.get('monthly_search_volume'))} 月搜",
        f"{target.get('keyword')}；CPC ${target.get('cpc', '待补')}；竞品 {_format_number(target.get('competitor_count'))}",
    )


def _traffic_groups(model: dict[str, Any]) -> list[dict[str, Any]]:
    demand = model.get("demand", {}) if isinstance(model.get("demand"), dict) else {}
    traffic = demand.get("sorftime_traffic_terms", {})
    if isinstance(traffic, dict):
        if isinstance(traffic.get("asins"), list):
            return [item for item in traffic.get("asins", []) if isinstance(item, dict)]
        if traffic.get("asin"):
            return [traffic]
    sorftime = model.get("sorftime", {}) if isinstance(model.get("sorftime"), dict) else {}
    entries = sorftime.get("product_traffic_entries", [])
    if isinstance(entries, list):
        return [item for item in entries if isinstance(item, dict)]
    return []


def _keyword_row(item: dict[str, Any]) -> str:
    return f"""
<div class="keyword-row">
  <strong>{escape(str(item.get('keyword', '待补')))}</strong>
  <span>月搜 {_format_number(item.get('monthly_search_volume'))}</span>
  <span>CPC ${escape(str(item.get('cpc', '待补')))}</span>
  <span>竞品 {_format_number(item.get('competitor_count'))}</span>
  <em>{escape(str(item.get('seasonality') or item.get('trend_direction') or ''))}</em>
</div>"""


def _traffic_card(item: dict[str, Any]) -> str:
    asin = str(item.get("asin") or "")
    words = item.get("top_traffic_words", [])
    if not isinstance(words, list):
        words = []
    warnings = item.get("mixed_pool_warning", [])
    if not isinstance(warnings, list):
        warnings = []
    word_text = "、".join(str(word.get("keyword", word)) if isinstance(word, dict) else str(word) for word in words[:5])
    warning_text = "、".join(str(word.get("keyword", word)) if isinstance(word, dict) else str(word) for word in warnings[:3])
    return f"""
<article class="traffic-card">
  <strong>{escape(asin or '竞品')}</strong>
  <span>{escape(word_text or '暂无词')}</span>
  {f'<em>混池：{escape(warning_text)}</em>' if warning_text else ''}
</article>"""


def _mini_fact(label: str, value: Any) -> str:
    return f"<div><span>{escape(str(label))}</span><strong>{escape(str(value))}</strong></div>"


def _percent(value: Any) -> str:
    if isinstance(value, (int, float)):
        return f"{value * 100:.1f}%" if abs(value) <= 1 else f"{value:.1f}%"
    if value in (None, ""):
        return "待补"
    return str(value)


def _simple_list(items: list[Any]) -> str:
    return '<ul class="plain-list">' + "".join(f"<li>{escape(str(item))}</li>" for item in items) + "</ul>"


def _callout(title: str, body: str, tone: str = "") -> str:
    return f"""
<div class="callout {escape(tone)}">
  <strong>{escape(title)}</strong>
  <span>{escape(body)}</span>
</div>"""


def _empty_state(text: str) -> str:
    return f'<div class="empty">{escape(text)}</div>'


def _first_image(item: dict[str, Any]) -> str:
    images = item.get("local_image_urls") or item.get("image_urls") or item.get("visual_evidence_image_urls") or []
    if not isinstance(images, list):
        return ""
    for url in images:
        text = str(url or "")
        if "cbu01.alicdn.com/img/ibank/O1CN01rPM9XH1b9mrMaiL6h" in text:
            continue
        if text:
            return text
    return str(images[0]) if images else ""


def _fallback_voc_pain_points() -> list[dict[str, Any]]:
    return [
        {"name": "评论 VOC 待接入", "review_count": 0, "description": "还没有按路线导入评价插件数据，暂时不能归纳真实差评痛点。", "evidence_review_ids": []},
        {"name": "低分原因待归纳", "review_count": 0, "description": "下一步按路线抓取代表 ASIN 评论，再把尺寸、材质、结构、配件和使用体验问题拆成打样项。", "evidence_review_ids": []},
    ]


def _fallback_voc_highlights() -> list[dict[str, Any]]:
    return [
        {"name": "正向卖点待接入", "description": "评论导入后再判断哪些卖点是用户真实认可的，不用商品标题替代用户反馈。"},
        {"name": "路线差异待验证", "description": "主线、升级款、场景款和组合款要分开看评论，避免把旁支需求当成主线卖点。"},
    ]


def _clean_sentence(value: Any) -> str:
    return " ".join(str(value or "").split())


def _truncate(value: str, limit: int) -> str:
    text = " ".join(value.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _count_suffix(value: Any) -> str:
    return f"{value} 条" if value not in (None, "") else ""


def _clean_report_title(value: Any) -> str:
    title = _clean_display_title(value)
    title = re.sub(r"([_\-\s]+(?:20)?\d{6})(?=$)", "", title).strip()
    return title or "AMZ 选品报告"


DECISION_REPORT_STYLE = """
:root {
  --bg: #f4fafb;
  --surface: #ffffff;
  --surface-soft: #f7fbfb;
  --surface-tint: #edf8fb;
  --text: #17242b;
  --muted: #62717a;
  --line: #d8e6ea;
  --line-strong: #bdd4dc;
  --primary: #168aa3;
  --primary-strong: #126782;
  --primary-soft: #e4f6fa;
  --accent: #d97837;
  --accent-strong: #a44f1e;
  --accent-soft: #fff3ea;
  --success: #24856d;
  --warning: #966400;
  --danger: #a33a2b;
  --shadow: 0 12px 28px rgba(40, 78, 90, .08);
  --shadow-soft: 0 2px 9px rgba(40, 78, 90, .06);
}
* { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--text);
  font-family: Inter, "PingFang SC", "Microsoft YaHei", -apple-system, BlinkMacSystemFont, sans-serif;
  font-size: 16px;
  line-height: 1.62;
  letter-spacing: 0;
}
a { color: inherit; }
.topbar {
  position: sticky;
  top: 0;
  z-index: 20;
  display: flex;
  gap: 6px;
  align-items: center;
  overflow-x: auto;
  padding: 10px max(18px, calc((100vw - 1220px) / 2));
  border-bottom: 1px solid var(--line);
  background: rgba(249, 253, 253, .96);
  backdrop-filter: blur(12px);
}
.topbar a {
  flex: 0 0 auto;
  min-height: 36px;
  display: inline-flex;
  align-items: center;
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 6px 11px;
  color: #155e75;
  font-size: 14px;
  font-weight: 700;
  text-decoration: none;
  background: var(--surface);
  transition: background .18s ease, border-color .18s ease, color .18s ease;
}
.topbar a:hover { border-color: #9ed7e4; background: #e9f8fb; }
.topbar a:focus-visible,
.link-grid a:focus-visible {
  outline: 3px solid rgba(22, 138, 163, .24);
  outline-offset: 2px;
}
.page {
  max-width: 1220px;
  margin: 0 auto;
  padding: 24px 24px 64px;
}
.hero {
  display: grid;
  grid-template-columns: minmax(0, 1.45fr) minmax(320px, .9fr);
  gap: 16px;
  align-items: stretch;
}
.hero-copy,
.decision-card,
.section,
.metric-card,
.finding-card,
.risk-card,
.step-card {
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--surface);
  box-shadow: var(--shadow);
}
.hero-copy {
  padding: clamp(26px, 5vw, 52px);
}
.eyebrow {
  color: var(--accent-strong);
  font-size: 13px;
  font-weight: 800;
}
h1, h2, h3, h4, p { margin-top: 0; }
h1 {
  max-width: 820px;
  margin-bottom: 18px;
  font-size: clamp(32px, 5vw, 58px);
  line-height: 1.08;
  letter-spacing: 0;
  overflow-wrap: anywhere;
}
.lead {
  max-width: 760px;
  color: #344440;
  font-size: clamp(18px, 2vw, 23px);
}
.chip-row { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 24px; }
.chip {
  display: inline-flex;
  min-height: 34px;
  align-items: center;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--surface-tint);
  padding: 5px 11px;
  color: #33423f;
  font-size: 14px;
  font-weight: 700;
}
.chip.strong { background: var(--primary); color: #fff; border-color: var(--primary); }
.decision-card {
  padding: 24px;
  background: #eef9fb;
  color: var(--text);
  box-shadow: var(--shadow);
}
.decision-label { color: var(--primary-strong); font-weight: 800; }
.decision-value { margin: 8px 0 12px; font-size: 42px; font-weight: 900; line-height: 1; }
.decision-card p { color: #40535c; }
.block-title { margin-top: 22px; color: var(--primary-strong); font-size: 13px; font-weight: 900; }
.plain-list { margin: 8px 0 0; padding-left: 20px; }
.plain-list li { margin: 5px 0; }
.section { margin-top: 18px; padding: clamp(22px, 3vw, 32px); }
.section-head {
  display: flex;
  justify-content: space-between;
  gap: 20px;
  align-items: end;
  margin-bottom: 18px;
}
.section-head h2 { margin: 0; font-size: clamp(24px, 3vw, 34px); line-height: 1.15; }
.section-head p { max-width: 560px; margin: 0; color: var(--muted); }
.metric-grid,
.source-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
}
.metric-card,
.source-card {
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 18px;
  box-shadow: var(--shadow-soft);
  background: #fbfdfc;
}
.metric-label { color: var(--muted); font-size: 13px; font-weight: 800; }
.metric-value { margin-top: 8px; font-size: 25px; font-weight: 900; line-height: 1.15; }
.metric-note { margin-top: 8px; color: var(--muted); font-size: 14px; }
	.source-card h3 { margin-bottom: 6px; font-size: 18px; }
	.source-card p { margin-bottom: 10px; color: var(--muted); font-size: 14px; }
	.source-card strong { color: var(--primary-strong); }
	.ai-analysis {
	  background: linear-gradient(180deg, #ffffff 0%, #f6fcfd 100%);
	}
	.analysis-thesis {
	  display: grid;
	  gap: 6px;
	  border: 1px solid #a9dfe9;
	  border-radius: 8px;
	  background: #eaf8fb;
	  padding: 20px;
	  margin-bottom: 14px;
	}
	.analysis-persona {
	  width: fit-content;
	  border: 1px solid #8ed2df;
	  border-radius: 999px;
	  background: #f5fcfd;
	  color: var(--primary-strong);
	  padding: 5px 10px;
	  font-size: 13px;
	  font-weight: 900;
	}
	.analysis-thesis span,
	.analysis-card div {
	  color: var(--primary-strong);
	  font-size: 13px;
	  font-weight: 900;
	}
	.analysis-thesis strong {
	  color: var(--text);
	  font-size: clamp(22px, 2.6vw, 32px);
	  line-height: 1.18;
	}
	.analysis-thesis p {
	  max-width: 760px;
	  margin: 0;
	  color: #40535c;
	  font-size: 16px;
	  line-height: 1.65;
	}
	.analysis-principle {
	  margin-top: 6px !important;
	  color: #62727a !important;
	  font-size: 14px !important;
	}
	.analysis-sources {
	  display: grid;
	  grid-template-columns: repeat(4, minmax(0, 1fr));
	  gap: 10px;
	  margin-bottom: 14px;
	}
	.analysis-sources span {
	  border: 1px solid var(--line);
	  border-radius: 8px;
	  background: #f9fcfc;
	  padding: 9px 11px;
	  color: #64767d;
	  font-size: 13px;
	  line-height: 1.45;
	}
	.analysis-grid {
	  display: grid;
	  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
	  gap: 12px;
	}
	.analysis-card {
	  border: 1px solid var(--line);
	  border-radius: 8px;
	  background: #fbfdfc;
	  padding: 18px;
	  box-shadow: var(--shadow-soft);
	}
	.analysis-card h3 {
	  margin: 8px 0 8px;
	  font-size: 20px;
	  line-height: 1.3;
	}
	.analysis-card p {
	  margin: 0;
	  color: var(--muted);
	  font-size: 16px;
	  line-height: 1.62;
	}
	.spec-bridge {
	  display: grid;
	  grid-template-columns: 1fr 1fr;
	  gap: 14px;
	  margin-top: 14px;
	}
	.spec-bridge > div {
	  border: 1px solid var(--line);
	  border-radius: 8px;
	  background: var(--surface);
	  padding: 16px;
	}
	.spec-bridge h3 {
	  margin-bottom: 8px;
	  font-size: 18px;
	}
	.route-section {
	  background: linear-gradient(180deg, #ffffff 0%, #f7fcfd 100%);
	}
	.route-grid {
	  display: grid;
	  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
	  gap: 12px;
	  align-items: stretch;
	}
	.route-card {
	  display: flex;
	  min-width: 0;
	  flex-direction: column;
	  border: 1px solid var(--line);
	  border-radius: 8px;
	  background: #fbfdfc;
	  padding: 18px;
	  box-shadow: var(--shadow-soft);
	}
	.route-topline {
	  display: flex;
	  justify-content: space-between;
	  gap: 10px;
	  align-items: center;
	  margin-bottom: 10px;
	}
	.route-topline span {
	  min-height: 28px;
	  display: inline-flex;
	  align-items: center;
	  border: 1px solid #9bd8e5;
	  border-radius: 8px;
	  background: var(--primary-soft);
	  padding: 3px 8px;
	  color: var(--primary-strong);
	  font-size: 13px;
	  font-weight: 900;
	}
	.route-topline strong {
	  color: var(--accent-strong);
	  font-size: 18px;
	  white-space: nowrap;
	}
	.route-card h3 {
	  margin-bottom: 8px;
	  font-size: 21px;
	  line-height: 1.28;
	  overflow-wrap: anywhere;
	}
	.route-count {
	  margin-bottom: 12px;
	  color: var(--muted);
	  font-size: 14px;
	  font-weight: 700;
	}
	.route-copy {
	  display: grid;
	  gap: 4px;
	}
	.route-copy strong,
	.route-next strong {
	  color: var(--primary-strong);
	  font-size: 13px;
	  font-weight: 900;
	}
	.route-copy p {
	  margin-bottom: 9px;
	  color: #3c4d52;
	  font-size: 15px;
	  line-height: 1.58;
	  overflow-wrap: anywhere;
	}
	.route-items {
	  display: grid;
	  gap: 7px;
	  margin: 4px 0 14px;
	  padding: 0;
	  list-style: none;
	}
	.route-items li,
	.empty-route {
	  display: grid;
	  gap: 2px;
	  border: 1px solid var(--line);
	  border-radius: 8px;
	  background: var(--surface);
	  padding: 9px 10px;
	  font-size: 13px;
	}
	.route-items a {
	  color: var(--text);
	  font-weight: 800;
	  text-decoration: none;
	  overflow-wrap: anywhere;
	}
	.route-items a:hover { color: var(--primary); text-decoration: underline; }
	.route-items span,
	.empty-route {
	  color: var(--muted);
	}
	.route-next { margin-top: auto; }
	.route-plan {
	  margin-top: 18px;
	  border-top: 1px solid var(--line);
	  padding-top: 18px;
	}
	.route-plan-grid {
	  display: grid;
	  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
	  gap: 12px;
	}
	.route-plan-card {
	  border: 1px solid var(--line);
	  border-radius: 8px;
	  background: #ffffff;
	  padding: 18px;
	  box-shadow: var(--shadow-soft);
	}
	.route-plan-head {
	  display: flex;
	  justify-content: space-between;
	  gap: 10px;
	  align-items: center;
	  margin-bottom: 10px;
	}
	.route-plan-head span,
	.route-plan-head strong {
	  min-height: 28px;
	  display: inline-flex;
	  align-items: center;
	  border-radius: 8px;
	  padding: 3px 9px;
	  font-size: 13px;
	  font-weight: 900;
	}
	.route-plan-head span {
	  border: 1px solid #9bd8e5;
	  background: var(--primary-soft);
	  color: var(--primary-strong);
	}
	.route-plan-head strong {
	  border: 1px solid #e6c4aa;
	  background: var(--accent-soft);
	  color: var(--accent-strong);
	  white-space: nowrap;
	}
	.route-plan-card h3 {
	  margin-bottom: 8px;
	  font-size: 20px;
	  line-height: 1.28;
	  overflow-wrap: anywhere;
	}
	.route-plan-card p {
	  margin-bottom: 12px;
	  color: #43545a;
	  font-size: 15px;
	  line-height: 1.58;
	}
	.route-plan-facts {
	  display: grid;
	  grid-template-columns: 1fr 1fr;
	  gap: 8px;
	  margin-bottom: 12px;
	}
	.route-plan-facts div {
	  min-width: 0;
	  border: 1px solid var(--line);
	  border-radius: 8px;
	  background: #f8fcfc;
	  padding: 9px 10px;
	}
	.route-plan-facts b,
	.route-plan-sub strong {
	  display: block;
	  margin-bottom: 4px;
	  color: var(--primary-strong);
	  font-size: 13px;
	  font-weight: 900;
	}
	.route-plan-facts span {
	  color: var(--muted);
	  font-size: 14px;
	  overflow-wrap: anywhere;
	}
	.route-plan-sub {
	  margin-top: 10px;
	}
	.route-plan-asins {
	  display: grid;
	  gap: 7px;
	  margin: 6px 0 0;
	  padding: 0;
	  list-style: none;
	}
	.route-plan-asins li {
	  display: grid;
	  gap: 2px;
	  border: 1px solid var(--line);
	  border-radius: 8px;
	  background: #fbfdfc;
	  padding: 8px 10px;
	  font-size: 13px;
	}
	.route-plan-asins b { color: var(--primary-strong); }
	.route-plan-asins span { color: var(--muted); overflow-wrap: anywhere; }
	.fact-table {
	  display: grid;
	  gap: 8px;
}
.fact-row {
  display: grid;
  grid-template-columns: 150px minmax(0, 1fr);
  gap: 14px;
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 12px 14px;
  background: #fbfdfc;
}
.fact-label { color: var(--muted); font-weight: 800; }
.fact-value { color: #263633; }
.subsection-head {
  display: flex;
  justify-content: space-between;
  gap: 18px;
  align-items: end;
  margin: 30px 0 14px;
  padding-top: 18px;
  border-top: 1px solid var(--line);
}
.subsection-head h3 {
  margin: 0;
  font-size: clamp(22px, 2.4vw, 30px);
  line-height: 1.2;
}
.subsection-head p {
  max-width: 520px;
  margin: 0;
  color: var(--muted);
  font-size: 14px;
}
.mini-section-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}
.mini-section-head h3 { margin: 0; }
.mini-section-head p {
  margin: 0;
  color: var(--muted);
  font-size: 13px;
}
.sorftime-panel { margin-top: 18px; }
.sorftime-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.15fr) minmax(320px, .85fr);
  gap: 14px;
  align-items: start;
}
.sorftime-keywords,
.sorftime-side {
  border: 1px solid var(--line);
  border-radius: 8px;
  background: #fbfdfc;
  padding: 14px;
}
.keyword-row {
  display: grid;
  grid-template-columns: minmax(180px, 1.3fr) repeat(3, minmax(86px, .7fr)) minmax(70px, .5fr);
  gap: 8px;
  align-items: center;
  border-bottom: 1px solid var(--line);
  padding: 10px 0;
  font-size: 14px;
}
.keyword-row:first-child { padding-top: 0; }
.keyword-row:last-child { border-bottom: 0; padding-bottom: 0; }
.keyword-row strong { color: var(--text); }
.keyword-row span { color: #3d4c48; }
.keyword-row em { color: var(--muted); font-style: normal; }
.sorftime-side h4 {
  margin: 0 0 8px;
  color: var(--primary-strong);
  font-size: 14px;
}
.sorftime-side h4:not(:first-child) { margin-top: 16px; }
.mini-facts { display: grid; gap: 8px; }
.mini-facts div,
.traffic-card {
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--surface);
  padding: 9px 10px;
}
.mini-facts span {
  display: block;
  color: var(--muted);
  font-size: 12px;
  font-weight: 800;
}
.mini-facts strong {
  display: block;
  margin-top: 2px;
  color: #263633;
  font-size: 14px;
}
.traffic-list { display: grid; gap: 8px; }
.traffic-card { display: grid; gap: 4px; }
.traffic-card strong { color: var(--text); }
.traffic-card span,
.traffic-card em { color: var(--muted); font-size: 13px; font-style: normal; }
.traffic-card em { color: var(--accent-strong); }
.split { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 18px; }
.stack { display: grid; gap: 10px; }
.finding-card { padding: 16px; box-shadow: var(--shadow-soft); background: #fbfdfc; }
.finding-card h4 { margin-bottom: 6px; font-size: 17px; }
.finding-card p { margin-bottom: 8px; color: #384844; }
.tiny, .note-line { color: var(--muted); font-size: 13px; }
.note-line { margin-top: 16px; }
.status-pill {
  min-height: 26px;
  display: inline-flex;
  align-items: center;
  border: 1px solid #9bd8e5;
  border-radius: 8px;
  background: var(--primary-soft);
  padding: 2px 8px;
  color: var(--primary-strong);
}
.rank-pill {
  min-height: 26px;
  display: inline-flex;
  align-items: center;
  border-radius: 8px;
  background: var(--primary);
  padding: 2px 8px;
  color: #fff;
  font-weight: 900;
}
.metric-note,
.fact-value {
  overflow-wrap: anywhere;
}
.tag-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin: 0 0 10px;
}
.tag-row span {
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--surface-soft);
  padding: 2px 7px;
  color: #455550;
  font-size: 12px;
  font-weight: 700;
}
.note-check {
  display: grid;
  gap: 4px;
  margin: 8px 0;
  color: #344440;
  font-size: 14px;
}
.note-check strong {
  color: var(--primary-strong);
  font-size: 13px;
}
.link-grid a {
  min-height: 42px;
  display: inline-flex;
  align-items: center;
  border-radius: 8px;
  border: 1px solid var(--line-strong);
  background: var(--surface);
  padding: 7px 10px;
  color: var(--primary-strong);
  font-weight: 900;
  text-decoration: none;
}
.mini-list { margin: 0; padding-left: 18px; color: var(--muted); font-size: 13px; }
.watchlist-block {
  margin-top: 22px;
  padding-top: 4px;
}
.watchlist-block .subsection-head { margin-top: 0; }
.watchlist {
  display: grid;
  gap: 8px;
  margin: 0;
  padding: 0;
  list-style: none;
}
.watchlist li {
  display: grid;
  gap: 4px;
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 12px 14px;
  background: #fbfdfc;
}
.watchlist a { color: var(--primary); font-weight: 900; text-decoration: none; }
.watchlist span { color: var(--muted); }
.callout {
  display: grid;
  gap: 4px;
  margin-top: 18px;
  border: 1px solid #b8dce5;
  border-radius: 8px;
  background: #eef9fb;
  padding: 14px 16px;
}
.callout.action { border-color: #e5c3aa; background: var(--accent-soft); }
.callout.muted { border-color: var(--line); background: var(--surface-soft); }
.score-list, .risk-grid, .step-grid, .link-grid { display: grid; gap: 12px; }
.score-row {
  display: grid;
  grid-template-columns: 120px 76px minmax(0, 1fr);
  gap: 14px;
  align-items: center;
  border-bottom: 1px solid var(--line);
  padding: 10px 0;
}
.score-row strong {
  color: var(--primary);
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}
.score-row em { color: var(--muted); font-style: normal; }
.risk-grid { grid-template-columns: repeat(4, minmax(0, 1fr)); }
.risk-card { padding: 14px; box-shadow: var(--shadow-soft); background: #fbfdfc; }
.risk-level { color: var(--accent-strong); font-weight: 900; }
.risk-card h4 { margin: 6px 0; }
.risk-card p { margin-bottom: 0; color: var(--muted); font-size: 14px; }
.step-grid { grid-template-columns: repeat(4, minmax(0, 1fr)); }
.step-card { padding: 18px; box-shadow: var(--shadow-soft); background: #fbfdfc; }
.step-index {
  width: 34px;
  height: 34px;
  display: grid;
  place-items: center;
  border-radius: 8px;
  background: var(--primary);
  color: #fff;
  font-weight: 900;
}
.step-card h3 { margin: 12px 0 6px; font-size: 18px; }
.step-card p { margin-bottom: 0; color: var(--muted); }
.link-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
.link-grid a { justify-content: center; min-height: 46px; }
.empty {
  border: 1px dashed var(--line);
  border-radius: 8px;
  padding: 18px;
  color: var(--muted);
}
@media (max-width: 980px) {
	  .page { padding: 18px 14px 42px; }
	  .hero, .split, .metric-grid, .source-grid, .analysis-sources, .analysis-grid, .spec-bridge, .risk-grid, .step-grid, .link-grid, .sorftime-layout {
	    grid-template-columns: 1fr;
	  }
  .section-head { display: block; }
  .section-head p { margin-top: 6px; }
  .subsection-head { display: block; }
  .subsection-head p { margin-top: 6px; }
  .mini-section-head { display: block; }
  .mini-section-head p { margin-top: 4px; }
  .fact-row { grid-template-columns: 1fr; gap: 4px; }
  .keyword-row { grid-template-columns: minmax(160px, 1.4fr) repeat(2, minmax(80px, .8fr)); }
  .keyword-row em { grid-column: 1 / -1; }
  .score-row { grid-template-columns: 1fr; gap: 2px; }
}
@media (max-width: 520px) {
  .keyword-row { grid-template-columns: 1fr; gap: 2px; }
}
@media (prefers-reduced-motion: reduce) {
  html { scroll-behavior: auto; }
}
"""
