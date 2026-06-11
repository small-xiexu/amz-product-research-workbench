"""Render a minimal research report from a research package."""

from __future__ import annotations

import math
import re
from datetime import datetime
from html import escape
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile
from xml.sax.saxutils import escape as xml_escape


DASHBOARD_STYLE = """
:root {
  --bg: #f3f0ea;
  --panel: #fffefa;
  --panel-soft: #f7f3eb;
  --panel-dark: #eef4f2;
  --panel-darker: #e5eeeb;
  --text: #1f2933;
  --muted: #6e7480;
  --line: rgba(32, 40, 51, 0.10);
  --line-soft: rgba(32, 40, 51, 0.06);
  --accent: #c57445;
  --accent-soft: #e7a56f;
  --accent-2: #52727b;
  --accent-3: #66764f;
  --shadow: 0 18px 44px rgba(28, 37, 49, 0.07);
}
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; }
body {
  background:
    radial-gradient(circle at top left, rgba(197, 116, 69, 0.10), transparent 34rem),
    linear-gradient(180deg, #f6f1e9 0%, #f8f5ef 100%);
  color: var(--text);
  font-family: Inter, "PingFang SC", "Microsoft YaHei", -apple-system, BlinkMacSystemFont, sans-serif;
  letter-spacing: 0;
}
a { color: inherit; text-decoration: none; }
.page {
  max-width: 1540px;
  margin: 0 auto;
  padding: 24px 24px 44px;
}
.hero {
  display: grid;
  grid-template-columns: minmax(0, 1.16fr) minmax(360px, 0.84fr);
  gap: 16px;
  align-items: stretch;
}
.panel {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 8px;
  box-shadow: var(--shadow);
  padding: 26px;
}
.panel-dark {
  background: linear-gradient(160deg, var(--panel-dark) 0%, var(--panel-darker) 100%);
  border: 1px solid rgba(32, 40, 51, 0.08);
  color: var(--text);
}
.eyebrow {
  font-size: 12px;
  line-height: 1;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: #c47a4d;
  font-weight: 700;
}
.title {
  margin: 10px 0 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.title-en {
  font-size: 46px;
  line-height: 1.04;
  letter-spacing: 0;
}
.title-cn {
  font-size: 18px;
  line-height: 1.25;
  color: var(--muted);
  font-weight: 600;
  letter-spacing: 0;
}
.subtitle {
  max-width: 60ch;
  font-size: 15px;
  line-height: 1.8;
  color: var(--muted);
}
.badge-row,
.pill-row,
.link-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.badge,
.pill,
.link-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  border-radius: 999px;
  font-size: 12px;
  line-height: 1;
  white-space: nowrap;
  border: 1px solid rgba(32, 40, 51, 0.08);
  background: rgba(32, 40, 51, 0.04);
  color: var(--text);
}
.badge.dark,
.pill.dark {
  border-color: rgba(32, 40, 51, 0.08);
  background: rgba(255, 255, 255, 0.72);
  color: var(--text);
}
.hero-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 16px;
}
.hero-meta .badge {
  font-weight: 600;
}
.hero-status {
  min-height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}
.status-label {
  font-size: 12px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: rgba(32, 40, 51, 0.58);
  font-weight: 700;
}
.status-value {
  margin: 12px 0 10px;
  font-size: 42px;
  line-height: 1;
  font-weight: 800;
  color: var(--text);
}
.status-copy {
  font-size: 15px;
  line-height: 1.75;
  color: var(--muted);
  max-width: 42ch;
}
.status-note {
  margin-top: 16px;
  padding: 14px 16px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.78);
  border: 1px solid rgba(32, 40, 51, 0.08);
  font-size: 13px;
  line-height: 1.65;
  color: var(--text);
}
.status-stack {
  display: grid;
  gap: 10px;
  margin-top: 18px;
}
.status-bullet {
  padding: 12px 14px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.78);
  border: 1px solid rgba(32, 40, 51, 0.08);
  font-size: 13px;
  line-height: 1.55;
  color: var(--text);
  overflow-wrap: anywhere;
}
.summary-strip {
  margin-top: 22px;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}
.summary-item {
  min-height: 112px;
  padding: 14px;
  border-radius: 8px;
  background: var(--panel-soft);
  border: 1px solid var(--line-soft);
}
.summary-label {
  font-size: 12px;
  line-height: 1;
  color: var(--muted);
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}
.summary-value {
  margin-top: 9px;
  font-size: 20px;
  line-height: 1.35;
  font-weight: 850;
  overflow-wrap: anywhere;
}
.summary-note {
  margin-top: 8px;
  font-size: 13px;
  line-height: 1.55;
  color: var(--muted);
}
.metric-grid {
  margin-top: 16px;
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
}
.metric-card {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 8px;
  box-shadow: var(--shadow);
  padding: 18px;
  min-height: 128px;
}
.metric-label {
  font-size: 12px;
  letter-spacing: 0.09em;
  text-transform: uppercase;
  color: var(--muted);
}
.metric-value {
  margin-top: 10px;
  font-size: 28px;
  line-height: 1.15;
  font-weight: 800;
}
.metric-note {
  margin-top: 8px;
  font-size: 13px;
  line-height: 1.6;
  color: var(--muted);
}
.section {
  margin-top: 30px;
}
.section-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: 12px;
  margin-bottom: 22px;
}
.section-title {
  margin: 0;
  font-size: 25px;
  line-height: 1.2;
  letter-spacing: 0;
  max-width: 24ch;
}
.section-note {
  max-width: 64ch;
  font-size: 13px;
  line-height: 1.65;
  color: var(--muted);
}
.two-col {
  display: grid;
  grid-template-columns: 1.08fr 0.92fr;
  gap: 18px;
}
.stack {
  display: grid;
  gap: 18px;
}
.subpanel {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 8px;
  box-shadow: var(--shadow);
  padding: 24px;
}
.subpanel.dark {
  background: linear-gradient(160deg, #f0f4f8 0%, #e6edf3 100%);
  border: 1px solid rgba(32, 40, 51, 0.08);
  color: var(--text);
}
.bar-group {
  display: grid;
  gap: 14px;
}
.bar-row {
  display: grid;
  grid-template-columns: 160px minmax(0, 1fr) auto;
  gap: 12px;
  align-items: center;
}
.bar-label {
  font-size: 13px;
  line-height: 1.45;
  overflow-wrap: anywhere;
}
.bar-track {
  position: relative;
  height: 11px;
  border-radius: 999px;
  background: rgba(32, 40, 51, 0.08);
  overflow: hidden;
}
.bar-fill {
  position: absolute;
  inset: 0 auto 0 0;
  border-radius: 999px;
  background: linear-gradient(90deg, var(--accent), var(--accent-soft));
}
.bar-fill.alt {
  background: linear-gradient(90deg, var(--accent-2), #8da98a);
}
.bar-fill.cool {
  background: linear-gradient(90deg, #8793a7, #e0a461);
}
.bar-value {
  font-size: 13px;
  color: var(--muted);
  white-space: nowrap;
}
.grid-2 {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}
.grid-3 {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}
.info-card {
  padding: 14px;
  border-radius: 8px;
  background: var(--panel-soft);
  border: 1px solid var(--line-soft);
}
.info-card.dark {
  background: rgba(255, 255, 255, 0.82);
  border-color: rgba(32, 40, 51, 0.08);
}
.info-label {
  font-size: 12px;
  color: var(--muted);
  letter-spacing: 0.06em;
  text-transform: uppercase;
}
.info-card.dark .info-label {
  color: rgba(32, 40, 51, 0.58);
}
.info-value {
  margin-top: 8px;
  font-size: 23px;
  line-height: 1.2;
  font-weight: 800;
  overflow-wrap: anywhere;
}
.info-note {
  margin-top: 8px;
  font-size: 13px;
  line-height: 1.55;
  color: var(--muted);
  overflow-wrap: anywhere;
}
.info-card.dark .info-note {
  color: var(--muted);
}
.note-list {
  display: grid;
  gap: 10px;
}
.note-item {
  padding: 12px 14px;
  border-radius: 8px;
  background: rgba(32, 40, 51, 0.04);
  border: 1px solid rgba(32, 40, 51, 0.07);
  font-size: 13px;
  line-height: 1.65;
  overflow-wrap: anywhere;
}
.note-item.dark {
  background: rgba(255, 255, 255, 0.82);
  border-color: rgba(32, 40, 51, 0.08);
  color: var(--text);
}
.table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
.table th,
.table td {
  padding: 10px 12px;
  border-bottom: 1px solid rgba(32, 40, 51, 0.08);
  text-align: left;
  vertical-align: top;
}
.table th {
  color: var(--muted);
  font-weight: 700;
  white-space: nowrap;
}
.table tr:last-child td { border-bottom: none; }
.chart-shell {
  background: var(--panel-soft);
  border: 1px solid var(--line-soft);
  border-radius: 8px;
  overflow: hidden;
}
.chart-shell.dark {
  background: rgba(255, 255, 255, 0.65);
  border-color: rgba(32, 40, 51, 0.08);
}
.chart-svg {
  width: 100%;
  height: auto;
  display: block;
}
.segment-matrix {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  padding: 16px;
}
.segment-card {
  min-height: 150px;
  padding: 16px;
  border-radius: 8px;
  background: rgba(255, 253, 248, 0.86);
  border: 1px solid rgba(32, 40, 51, 0.08);
}
.segment-card.featured {
  background: rgba(215, 116, 67, 0.08);
  border-color: rgba(215, 116, 67, 0.18);
}
.segment-head {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  align-items: flex-start;
}
.segment-name {
  font-size: 17px;
  line-height: 1.25;
  font-weight: 800;
}
.segment-count {
  padding: 5px 9px;
  border-radius: 8px;
  background: rgba(32, 40, 51, 0.06);
  color: var(--muted);
  font-size: 12px;
  white-space: nowrap;
}
.segment-desc {
  margin-top: 8px;
  font-size: 12px;
  line-height: 1.55;
  color: var(--muted);
}
.segment-main {
  margin-top: 12px;
  display: grid;
  gap: 4px;
}
.segment-brand {
  font-size: 16px;
  line-height: 1.25;
  font-weight: 800;
  overflow-wrap: anywhere;
}
.segment-meta {
  font-size: 13px;
  line-height: 1.55;
  color: var(--muted);
}
.segment-chips {
  margin-top: 12px;
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}
.segment-chip {
  padding: 5px 8px;
  border-radius: 999px;
  background: rgba(32, 40, 51, 0.05);
  color: var(--muted);
  font-size: 12px;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.risk-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}
.risk-card {
  padding: 14px;
  border-radius: 8px;
  background: var(--panel);
  border: 1px solid var(--line);
}
.risk-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  margin-bottom: 10px;
}
.risk-title {
  font-size: 14px;
  font-weight: 700;
}
.level-badge {
  padding: 6px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
  background: rgba(215, 116, 67, 0.14);
  color: #b45309;
  white-space: nowrap;
}
.level-badge.medium { background: rgba(63, 116, 128, 0.14); color: #0f4f5c; }
.level-badge.low { background: rgba(125, 141, 82, 0.14); color: #556b2f; }
.level-badge.wait { background: rgba(114, 120, 135, 0.14); color: #4b5563; }
.risk-basis,
.risk-next {
  font-size: 13px;
  line-height: 1.6;
  overflow-wrap: anywhere;
}
.risk-basis { color: var(--text); }
.risk-next { margin-top: 8px; color: var(--muted); }
.footer {
  margin-top: 18px;
  padding-top: 18px;
  display: flex;
  gap: 14px;
  justify-content: space-between;
  align-items: flex-start;
  flex-wrap: wrap;
  color: var(--muted);
  font-size: 12px;
  line-height: 1.65;
}
.footer-links {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.link-chip {
  background: rgba(32, 40, 51, 0.04);
}
.muted {
  color: var(--muted);
}
@media (max-width: 1220px) {
  .hero,
  .two-col { grid-template-columns: 1fr; }
  .metric-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 760px) {
  .page { padding: 14px; }
  .panel, .subpanel { padding: 18px; border-radius: 8px; }
  .title-en { font-size: 34px; }
  .title-cn { font-size: 15px; }
  .metric-grid,
  .grid-2,
  .grid-3,
  .summary-strip,
  .segment-matrix,
  .risk-grid { grid-template-columns: 1fr; }
  .bar-row { grid-template-columns: 1fr; }
  .bar-value { justify-self: start; }
}
"""


def render_markdown(package: dict) -> str:
    meta = package.get("metadata", {})
    currency_code = _site_currency_code(meta.get("site", "US"))
    display_title = _clean_display_title(meta.get("seed_keyword_or_category", "未命名品类"))
    market = package.get("market_analysis", {})
    market_structure = package.get("market_structure", {})
    competitors = package.get("competitor_pool", {})
    profit = package.get("profit_reference", {})
    status = package.get("status_card", {})
    voc = package.get("voc_analysis", {})
    decision = package.get("decision_review", {})
    ip_screening = package.get("ip_screening", {})
    compliance = package.get("compliance_screening", {})
    ip_compliance_review = package.get("ip_compliance_review", {})

    lines = [
        f"# {display_title} 调研报告",
        "",
        "## 结论摘要",
        f"- 金额口径：统一按 {currency_code} 展示",
        f"- 状态：{status.get('status', '待填')}",
        f"- 理由：{status.get('reason', '待填')}",
        "",
    ]
    lines.extend(_decision_markdown_lines(decision, currency_code))
    lines.extend(
        [
            "## 市场扫描",
            f"- 市场规模：{_normalize_money_text(market.get('market_size', '待填'), currency_code)}",
            f"- 价格带：{_normalize_money_text(market.get('price_band', '待填'), currency_code)}",
            f"- 品牌集中度：{market.get('brand_concentration', '待填')}",
            f"- 卖家结构：{market.get('seller_concentration', '待填')}",
            f"- 新品机会：{market.get('new_listing_ratio', '待填')}",
            "",
        ]
    )
    lines.extend(_market_structure_markdown_lines(market_structure))
    lines.extend(_competitor_markdown_lines(competitors, currency_code))
    lines.extend(
        [
            "## 利润参考",
            f"- 基础 FBA 毛利：{_format_money(profit.get('base_fba_gross_profit', '待填'), currency_code)}",
            f"- 基础 FBA 毛利率：{_format_percent_or_text(profit.get('base_fba_margin', '待填'))}",
            f"- 扣广告和退货后的 FBA 毛利：{_format_money(profit.get('post_ads_returns_gross_profit', '待填'), currency_code)}",
            f"- 扣广告和退货后的 FBA 毛利率：{_format_percent_or_text(profit.get('post_ads_returns_margin', '待填'))}",
            "",
        ]
    )
    lines.extend(_profit_breakdown_markdown_lines(profit))
    lines.extend(_ip_compliance_markdown_lines(ip_screening, compliance, ip_compliance_review))
    if voc:
        lines.extend(_voc_markdown_lines(voc))
    competitor_deep_dive = package.get("competitor_deep_dive", [])
    if competitor_deep_dive:
        lines.extend(_competitor_deep_dive_markdown_lines(competitor_deep_dive, currency_code))
    return "\n".join(lines)


def render_summary(package: dict) -> str:
    status = package.get("status_card", {})
    decision = package.get("decision_review", {})
    voc = package.get("voc_analysis", {})
    voc_stats = (voc.get("summary") or {}) if isinstance(voc, dict) else {}
    voc_note = (
        f"已接入 {voc_stats.get('review_count', 0)} 条评论，{voc_stats.get('asin_count', 0)} 个 ASIN"
        if voc_stats.get("review_count")
        else "待接入"
    )
    first_action = (decision.get("action_items") or ["待填"])[0] if isinstance(decision, dict) else "待填"
    return "\n".join(
        [
            "# 摘要",
            "",
            f"- 状态：{status.get('status', '待填')}",
            f"- 原因：{status.get('reason', '待填')}",
            f"- 下一步：{status.get('next_step', '待填')}",
            f"- 评论 VOC：{voc_note}（痛点分析由 Claude 在对话中完成）",
            f"- 第一动作：{first_action}",
        ]
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
        _dashboard_profit_risk_section(model),
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
    profit = package.get("profit_reference", {})
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
        "profit": profit,
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
            "summary": "summary.md",
            "excel": "data.xlsx",
        },
    }


def _localized_title(title: str) -> str:
    return str(title or "").strip()


def _clean_display_title(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return "调研看板"
    internal_markers = [
        "UI重构预览",
        "UI 重构预览",
        "UI重构版",
        "UI 重构版",
        "重构预览",
        "预览版",
        "重新验证",
        "重新驗證",
    ]
    for marker in internal_markers:
        text = text.replace(marker, "")
    text = re.sub(r"[_｜|/\\-]+\s*/", " /", text)
    text = re.sub(r"[_｜|/\\-]{2,}", "_", text)
    text = re.sub(r"\s{2,}", " ", text)
    text = text.strip(" _-/｜|\\")
    return text or "调研看板"


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
        f'<a class="link-chip" href="{model["links"]["markdown"]}">报告正文</a>',
        f'<a class="link-chip" href="{model["links"]["excel"]}">Excel 底表</a>',
        f'<a class="link-chip" href="{model["links"]["summary"]}">摘要</a>',
    ]
    reason = str(status.get("reason", "待补"))
    next_step = str(status.get("next_step", "待补"))
    status_value = str(status.get("status", "待填"))
    missing_line = "、".join(str(item) for item in (model.get("missing_inputs", []) or [])[:4]) or "暂无"
    first_fact = _normalize_money_text((decision.get("facts") or ["当前先看市场和结构，再补利润和合规。"])[0], currency_code)
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
    profit = model.get("profit", {})
    data_quality = model.get("data_quality", {})
    currency_code = model.get("currency_code", "USD")
    base_profit = profit.get("base_fba_gross_profit")
    post_profit = profit.get("post_ads_returns_gross_profit")
    profit_note = (
        f"基础毛利 { _format_money(base_profit, currency_code) }，扣广告和退货后 { _format_money(post_profit, currency_code) }"
        if isinstance(base_profit, (int, float)) or isinstance(post_profit, (int, float))
        else f"基础毛利 {base_profit}，扣广告和退货后 {post_profit}"
    )
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
            "利润参考",
            profit.get("post_ads_returns_margin", profit.get("base_fba_gross_profit", "待填")),
            profit_note,
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
            elif "利润参考" in label and isinstance(value, (int, float)) and 0 <= value <= 1:
                value_text = _format_percent_or_text(value)
            else:
                value_text = _format_money(value, currency_code) if label == "利润参考" else _format_number(value)
        elif label == "市场规模":
            value_text = _market_size_value_text(value, currency_code)
        else:
            value_text = _normalize_money_text(value, currency_code) if label in {"市场规模", "利润参考"} else str(value)
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


def _dashboard_profit_risk_section(model: dict[str, Any]) -> str:
    profit = model.get("profit", {})
    decision = model.get("decision", {})
    risks = model.get("risks", []) or []
    missing_inputs = model.get("missing_inputs", []) or []
    currency_code = model.get("currency_code", "USD")
    cost_breakdown = profit.get("cost_breakdown", {}) if isinstance(profit, dict) else {}
    profit_cards = [
        ("基础 FBA 毛利", _format_money(profit.get("base_fba_gross_profit", "待补"), currency_code), "扣除采购、头程、FBA、佣金和仓储后的基础结果"),
        ("基础毛利率", _format_percent_or_text(profit.get("base_fba_margin")) if profit.get("base_fba_margin") is not None else "待补", "不含广告和退款"),
        ("扣广告/退货毛利", _format_money(profit.get("post_ads_returns_gross_profit", "待补"), currency_code), "更贴近真实投放后的结果"),
        ("扣广告/退货毛利率", _format_percent_or_text(profit.get("post_ads_returns_margin")) if profit.get("post_ads_returns_margin") is not None else "待补", "最终是否值得推进的核心参考"),
    ]
    cost_rows = []
    labels = [
        ("sale_price", "建议售价"),
        ("purchase_cost", "采购价"),
        ("first_leg_shipping", "头程费用"),
        ("fba_fee", "FBA费用"),
        ("commission", "佣金"),
        ("storage_fee", "仓储费"),
        ("inbound_placement_fee", "入库配置费"),
        ("ad_cost", "广告费"),
        ("return_loss", "退款损失"),
    ]
    for key, label in labels:
        if key in cost_breakdown:
            cost_rows.append((label, cost_breakdown.get(key)))
    risk_cards = []
    for risk in risks[:6]:
        if isinstance(risk, dict):
            risk_cards.append(risk)
    if not risk_cards:
        risk_cards = [
            {"dimension": "风险矩阵", "level": "待填", "basis": "还没有回填到这一步。", "next_check": "等利润和合规填完后再看。"}
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
        {''.join(_render_info_card(label, value, note) for label, value, note in profit_cards)}
      </div>
      <div class="section-header" style="margin-top:18px; margin-bottom:10px;">
        <div>
          <div class="eyebrow">Cost Breakdown</div>
          <h3 class="section-title" style="font-size:22px;">利润拆分</h3>
        </div>
      </div>
      <div class="note-item" style="margin-bottom:12px;">本页金额按上方统一口径展示；模板里的成本项会自动换算后汇总。</div>
      <table class="table">
        <thead><tr><th>项目</th><th>值</th></tr></thead>
        <tbody>
          {''.join(f'<tr><td>{escape(str(label))}</td><td>{escape(_format_money(value, currency_code) if isinstance(value, (int, float)) else str(value))}</td></tr>' for label, value in cost_rows) if cost_rows else '<tr><td class="muted">利润明细待补</td><td class="muted">-</td></tr>'}
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
    meta = model.get("meta", {})
    generated_at = _format_generated_at(meta.get("generated_at", "待填"))
    return f"""
<footer class="footer">
  <div>
    <div>生成时间：{escape(str(generated_at))}</div>
  </div>
  <div class="footer-links">
    <a class="link-chip" href="{model['links']['markdown']}">报告正文</a>
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


def _display_dashboard_value(value: Any) -> str:
    if value is None:
        return "待填"
    if isinstance(value, float):
        if 0 <= value <= 1:
            return _format_percent_or_text(value)
        return _format_number(value)
    if isinstance(value, int):
        return _format_number(value)
    return str(value)


def _safe_float(value: Any) -> float | None:
    if value in (None, "", "--", "待填"):
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


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2


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


def render_data_workbook(package: dict, output_path: str | Path) -> None:
    sheets = _build_workbook_sheets(package)
    _write_xlsx(Path(output_path), sheets)


def build_outputs(input_path: str, output_dir: str) -> None:
    package = json.loads(Path(input_path).read_text(encoding="utf-8"))
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "research_package.json").write_text(
        json.dumps(package, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (out / "report.md").write_text(render_markdown(package), encoding="utf-8")
    (out / "summary.md").write_text(render_summary(package), encoding="utf-8")
    (out / "dashboard.html").write_text(render_dashboard(package), encoding="utf-8")
    render_data_workbook(package, out / "data.xlsx")


def _build_workbook_sheets(package: dict) -> list[tuple[str, list[list[object]]]]:
    meta = package.get("metadata", {})
    currency_code = _site_currency_code(meta.get("site", "US"))
    constraints = package.get("constraints", {})
    operator_inputs = package.get("operator_inputs", {})
    market = package.get("market_analysis", {})
    market_structure = package.get("market_structure", {})
    competitors = package.get("competitor_pool", {})
    profit = package.get("profit_reference", {})
    return_risk = package.get("return_risk", {})
    ip_screening = package.get("ip_screening", {})
    compliance = package.get("compliance_screening", {})
    ip_compliance_review = package.get("ip_compliance_review", {})
    status = package.get("status_card", {})
    decision = package.get("decision_review", {})

    return [
        ("数据来源说明", _source_rows(meta)),
        (
            "调研边界",
            _dict_rows(
                {
                    "站点": meta.get("site"),
                    "关键词/品类": meta.get("seed_keyword_or_category"),
                    "产品形态": meta.get("product_shape"),
                    "明确禁区": constraints.get("exclusion_rules"),
                }
            ),
        ),
        ("运营手填项", _profit_input_rows(operator_inputs, currency_code)),
        ("市场结构", _dict_rows(market)),
        (
            "Top100原始明细",
            _top_product_rows(package.get("normalized_tables", {}).get("top100"), currency_code),
        ),
        ("数据质量检查", _data_quality_rows(market_structure.get("data_quality", {}))),
        ("属性定义", _attribute_definition_rows(market_structure.get("attribute_definitions", []))),
        ("Top商品打标", _top_product_rows(package.get("normalized_tables", {}).get("top_product_tags"), currency_code, include_tags=True)),
        ("属性分布", _attribute_distribution_rows(market_structure.get("attribute_distributions", []))),
        ("属性交叉分析", _cross_analysis_rows(market_structure.get("cross_analysis", []), currency_code)),
        ("竞品池", _competitor_rows(competitors, currency_code)),
        ("竞品深拆卡", _competitor_deep_dive_rows(package.get("competitor_deep_dive", []), currency_code)),
        ("利润测算输入", _profit_input_rows(operator_inputs, currency_code)),
        ("利润参考结果", _dict_rows(profit)),
        ("利润成本拆分", _profit_breakdown_rows(profit)),
        ("决策检查", _decision_rows(decision)),
        ("风险矩阵", _risk_matrix_rows(decision.get("risk_matrix", []) if isinstance(decision, dict) else [])),
        ("评论VOC", _voc_summary_rows(package.get("voc_analysis", {}))),
        ("VOC证据", _voc_evidence_rows(package.get("normalized_tables", {}).get("voc_evidence", []))),
        ("退货风险", _dict_rows(return_risk)),
        ("知产合规复核", _dict_rows(ip_compliance_review)),
        ("知产初筛", _ip_screening_rows(ip_screening)),
        ("合规认证预判", _compliance_screening_rows(compliance)),
        ("状态卡", _dict_rows(status)),
    ]


def _decision_markdown_lines(decision: dict, currency_code: str = "USD") -> list[str]:
    if not decision:
        return []
    lines = ["## 决策检查", ""]
    if decision.get("status_explanation"):
        lines.extend(["### 状态解释", f"- {decision.get('status_explanation')}", ""])
    for title, key in (
        ("事实", "facts"),
        ("推断", "inferences"),
        ("待补", "missing_inputs"),
        ("建议动作", "action_items"),
    ):
        values = decision.get(key, [])
        if not values:
            continue
        lines.append(f"### {title}")
        for item in values[:8]:
            lines.append(f"- {_normalize_money_text(item, currency_code)}")
        lines.append("")
    risks = decision.get("risk_matrix", [])
    if risks:
        lines.append("### 风险矩阵")
        for item in risks:
            basis = _trim_sentence_end(_normalize_money_text(item.get("basis", "待填"), currency_code))
            lines.append(
                f"- {item.get('dimension', '待填')}：{item.get('level', '待填')}。"
                f"依据：{basis}；下一步：{_normalize_money_text(item.get('next_check', '待填'), currency_code)}"
            )
        lines.append("")
    return lines


def _market_structure_markdown_lines(market_structure: dict) -> list[str]:
    if not market_structure:
        return []
    summary = market_structure.get("summary", {})
    quality = market_structure.get("data_quality", {})
    distributions = market_structure.get("attribute_distributions", [])
    cross_analysis = market_structure.get("cross_analysis", [])
    lines = ["## 数据质量与属性结构", ""]
    if summary.get("quality_summary"):
        lines.append(f"- {summary.get('quality_summary')}")
    if summary.get("dominant_structure"):
        lines.append(f"- 结构特征：{summary.get('dominant_structure')}")
    if quality.get("warnings"):
        for warning in quality.get("warnings", [])[:5]:
            lines.append(f"- 提醒：{warning}")
    for item in distributions[:4]:
        if isinstance(item, dict):
            lines.append(f"- {item.get('label', item.get('dimension', '维度'))}：{item.get('summary', '待填')}")
    if summary.get("opportunity_clues"):
        lines.append("- 交叉线索：")
        for clue in summary.get("opportunity_clues", [])[:4]:
            lines.append(f"  - {clue}")
    if cross_analysis:
        first = cross_analysis[0]
        lines.append(f"- 交叉分析：{first.get('summary', '待填')}")
    lines.append("")
    return lines


def _profit_breakdown_markdown_lines(profit: dict) -> list[str]:
    breakdown = profit.get("cost_breakdown", {}) if isinstance(profit, dict) else {}
    if not breakdown:
        return []
    currency_code = profit.get("currency_code", "USD")
    labels = {
        "sale_price": "建议售价",
        "purchase_cost": "采购价",
        "first_leg_shipping": "头程费用",
        "fba_fee": "FBA费用",
        "commission": "佣金",
        "storage_fee": "仓储费",
        "inbound_placement_fee": "入库配置费",
        "ad_cost": "广告费",
        "return_loss": "退款损失",
    }
    lines = ["### 利润成本拆分"]
    for key, label in labels.items():
        if key in breakdown:
            value = breakdown.get(key)
            lines.append(f"- {label}：{_format_money(value, currency_code) if isinstance(value, (int, float)) else value}")
    if profit.get("notes"):
        lines.append(f"- 说明：{profit.get('notes')}")
    lines.append("")
    return lines


def _profit_breakdown_rows(profit: dict) -> list[list[object]]:
    currency_code = profit.get("currency_code", "USD")
    rows: list[list[object]] = [["项目", "值"]]
    if not profit:
        rows.append(["状态", "未生成"])
        return rows
    breakdown = profit.get("cost_breakdown", {})
    for key, label in (
        ("sale_price", "建议售价"),
        ("purchase_cost", "采购价"),
        ("first_leg_shipping", "头程费用"),
        ("fba_fee", "FBA费用"),
        ("commission", "佣金"),
        ("storage_fee", "仓储费"),
        ("inbound_placement_fee", "入库配置费"),
        ("ad_cost", "广告费"),
        ("return_loss", "退款损失"),
    ):
        if isinstance(breakdown, dict) and key in breakdown:
            rows.append([label, breakdown.get(key)])
    for key, value in (profit.get("rate_assumptions", {}) if isinstance(profit, dict) else {}).items():
        rows.append([key, value])
    if len(rows) == 1:
        rows.append(["状态", profit.get("status", "未计算")])
    return rows


def _ip_compliance_markdown_lines(ip_screening: dict, compliance: dict, review: dict) -> list[str]:
    if not ip_screening and not compliance and not review:
        return []
    lines = ["## 知产/合规初筛", ""]
    if review:
        missing = review.get("missing_fields", [])
        pending = review.get("pending_fields", [])
        lines.extend(
            [
                f"- 总状态：{review.get('status', '待补')}",
                f"- 整体风险：{review.get('overall_level', '待复核')}",
                f"- 下一步：{review.get('next_step', '待复核')}",
            ]
        )
        if missing:
            lines.append(f"- 待补字段：{'、'.join(str(item) for item in missing[:8])}")
        if pending:
            lines.append(f"- 待复核项：{'、'.join(str(item) for item in pending[:8])}")
        lines.append("")
    if ip_screening:
        lines.extend(
            [
                "### 知产初筛",
                f"- 状态：{ip_screening.get('status', '待补')}",
                f"- 风险等级：{ip_screening.get('level', ip_screening.get('overall_level', '待复核'))}",
                f"- 摘要：{ip_screening.get('summary', ip_screening.get('notes', '待复核'))}",
                f"- 边界：{ip_screening.get('boundary', '仅为早期初筛，不替代专业结论。')}",
                "",
            ]
        )
    if compliance:
        lines.extend(
            [
                "### 合规认证预判",
                f"- 状态：{compliance.get('status', '待补')}",
                f"- 风险等级：{compliance.get('level', compliance.get('overall_level', '待复核'))}",
                f"- 摘要：{compliance.get('summary', compliance.get('notes', '待复核'))}",
                f"- 边界：{compliance.get('boundary', '仅为可能材料和待复核项，不替代专业结论。')}",
                "",
            ]
        )
    return lines


def _ip_screening_rows(ip_screening: dict) -> list[list[object]]:
    rows: list[list[object]] = [
        ["字段", "值"],
        ["状态", ip_screening.get("status", "未生成")],
        ["风险等级", ip_screening.get("level", "")],
        ["整体风险", ip_screening.get("overall_level", "")],
        ["摘要", ip_screening.get("summary", "")],
        ["边界", ip_screening.get("boundary", "")],
        [],
        ["风险类型", "触发原因", "检索入口", "检索网址", "建议关键词", "结果", "证据链接", "证据说明", "下一步"],
    ]
    for item in ip_screening.get("rows", []):
        if isinstance(item, dict):
            rows.append(
                [
                    item.get("risk_type"),
                    item.get("trigger_reason"),
                    item.get("search_entry"),
                    item.get("search_url"),
                    item.get("suggested_keywords"),
                    item.get("result"),
                    item.get("evidence_link"),
                    item.get("evidence_note"),
                    item.get("next_step"),
                ]
            )
    if len(rows) == 8:
        rows.append(["未生成", "", "", "", "", "", "", "", ""])
    return rows


def _compliance_screening_rows(compliance: dict) -> list[list[object]]:
    rows: list[list[object]] = [
        ["字段", "值"],
        ["状态", compliance.get("status", "未生成")],
        ["风险等级", compliance.get("level", "")],
        ["整体风险", compliance.get("overall_level", "")],
        ["摘要", compliance.get("summary", "")],
        ["边界", compliance.get("boundary", "")],
        [],
        ["产品属性字段", "属性值"],
    ]
    product_flags = compliance.get("product_flags", {})
    if isinstance(product_flags, dict) and product_flags:
        for key, value in product_flags.items():
            rows.append([key, value])
    else:
        rows.append(["未填写", ""])
    rows.extend(
        [
            [],
            ["触发字段", "产品属性", "美国可能材料", "欧盟/英国可能材料", "早期状态", "推荐入口", "结果", "证据链接", "证据说明", "下一步"],
        ]
    )
    for item in compliance.get("rows", []):
        if isinstance(item, dict):
            rows.append(
                [
                    item.get("trigger_field"),
                    item.get("product_attribute"),
                    item.get("us_possible_materials"),
                    item.get("eu_uk_possible_materials"),
                    item.get("early_status"),
                    item.get("recommended_entries"),
                    item.get("result"),
                    item.get("evidence_link"),
                    item.get("evidence_note"),
                    item.get("next_step"),
                ]
            )
    return rows


def _decision_rows(decision: dict) -> list[list[object]]:
    rows: list[list[object]] = [["模块", "内容"]]
    if not decision:
        rows.append(["状态", "未生成"])
        return rows
    if decision.get("status_explanation"):
        rows.append(["状态解释", decision.get("status_explanation")])
    for label, key in (
        ("事实", "facts"),
        ("推断", "inferences"),
        ("待补", "missing_inputs"),
        ("建议动作", "action_items"),
    ):
        for item in decision.get(key, []):
            rows.append([label, item])
    return rows


def _risk_matrix_rows(risks: list[dict]) -> list[list[object]]:
    rows: list[list[object]] = [["维度", "等级", "依据", "下一步"]]
    for item in risks:
        rows.append([item.get("dimension"), item.get("level"), item.get("basis"), item.get("next_check")])
    if len(rows) == 1:
        rows.append(["未生成", "", "", ""])
    return rows


def _trim_sentence_end(value: object) -> str:
    return str(value).rstrip("。；; ")


def _voc_markdown_lines(voc: dict) -> list[str]:
    summary = voc.get("summary", {})
    lines = [
        "## 评论 VOC",
        f"- 评论数：{summary.get('review_count', '待填')}",
        f"- ASIN 数：{summary.get('asin_count', '待填')}",
        f"- 采集入口站点：{_format_count_items(summary.get('entry_site_distribution', []), 3) or '待填'}",
        f"- 评论地区分布：{_format_count_items(summary.get('review_region_distribution', []), 5) or '待填'}",
        f"- 低分评论数：{summary.get('low_rating_count', '待填')}",
        f"- 口径说明：{summary.get('source_scope_note', '站点字段仅表示采集入口。')}",
        "",
        "### 主要痛点",
    ]
    for finding in voc.get("pain_points", [])[:5]:
        lines.append(f"- {finding.get('name', '待填')}：{finding.get('review_count', '待填')} 条，等级 {finding.get('severity', '待填')}")
        for evidence in finding.get("evidence", [])[:3]:
            lines.append(
                f"  - `{evidence.get('review_id', '待填')}` / {evidence.get('asin', '待填')} / "
                f"{evidence.get('rating', '待填')}星：{evidence.get('snippet', '待填')}"
            )
    lines.extend(["", "### 主要亮点"])
    for finding in voc.get("highlights", [])[:5]:
        lines.append(f"- {finding.get('name', '待填')}：{finding.get('review_count', '待填')} 条")
    lines.extend(["", "### 改品机会"])
    for item in voc.get("opportunity_hypotheses", [])[:5]:
        evidence_ids = ", ".join(item.get("evidence_review_ids", [])[:5])
        lines.append(f"- {item.get('name', '待填')}：{item.get('hypothesis', '待填')}（证据：{evidence_ids}）")
    lines.append("")
    return lines


def _first_finding_name(findings: list[dict]) -> str:
    if not findings:
        return "待填"
    return str(findings[0].get("name", "待填"))


def _voc_summary_rows(voc: dict) -> list[list[object]]:
    rows: list[list[object]] = [["字段", "值"]]
    if not voc:
        rows.append(["状态", "未接入"])
        return rows
    summary = voc.get("summary", {})
    rows.extend(
        [
            ["评论数", summary.get("review_count")],
            ["ASIN数", summary.get("asin_count")],
            ["采集入口站点", _format_count_items(summary.get("entry_site_distribution", []), 8)],
            ["评论地区分布", _format_count_items(summary.get("review_region_distribution", []), 12)],
            ["主采集入口", summary.get("primary_entry_site")],
            ["主要评论地区", summary.get("primary_review_region")],
            ["口径说明", summary.get("source_scope_note")],
            ["低分评论数", summary.get("low_rating_count")],
            ["含图片/视频评论数", summary.get("media_review_count")],
            ["首要痛点", _first_finding_name(voc.get("pain_points", []))],
            ["首要亮点", _first_finding_name(voc.get("highlights", []))],
            ["证据规则", voc.get("evidence_policy")],
        ]
    )
    return rows


def _voc_evidence_rows(evidence_rows: object) -> list[list[object]]:
    rows: list[list[object]] = [["类型", "主题", "评论数", "等级", "评论ID", "ASIN", "采集入口站点", "评论地区", "评分", "日期", "证据片段", "链接"]]
    if isinstance(evidence_rows, list):
        for item in evidence_rows:
            if isinstance(item, dict):
                rows.append(
                    [
                        item.get("finding_type"),
                        item.get("finding_name"),
                        item.get("review_count"),
                        item.get("severity"),
                        item.get("review_id"),
                        item.get("asin"),
                        item.get("site"),
                        item.get("review_region"),
                        item.get("rating"),
                        item.get("review_date"),
                        item.get("snippet"),
                        item.get("url"),
                    ]
                )
    if len(rows) == 1:
        rows.append(["未接入", "", "", "", "", "", "", "", "", "", "", ""])
    return rows


def _source_rows(meta: dict) -> list[list[object]]:
    rows: list[list[object]] = [["来源", "说明"]]
    for source in meta.get("data_sources", []):
        rows.append([source, "metadata.data_sources"])
    if len(rows) == 1:
        rows.append(["待填", ""])
    return rows


def _data_quality_rows(data_quality: dict) -> list[list[object]]:
    rows: list[list[object]] = [["字段", "值"]]
    if not data_quality:
        rows.append(["状态", "未生成"])
        return rows
    rows.extend(
        [
            ["要求数量", data_quality.get("expected_count")],
            ["实际数量", data_quality.get("actual_count")],
            ["完整度", _format_percent_or_text(data_quality.get("completeness_rate", "待填"))],
            ["质量分", data_quality.get("quality_score")],
            ["质量等级", data_quality.get("level")],
            ["唯一 ASIN 数", data_quality.get("unique_asin_count")],
            ["下一步", data_quality.get("next_check")],
        ]
    )
    warnings = data_quality.get("warnings", [])
    if warnings:
        rows.append(["提醒", ""])
        for item in warnings:
            rows.append(["提醒", item])
    missing_fields = data_quality.get("missing_fields", [])
    if missing_fields:
        rows.append(["缺失字段", ""])
        for item in missing_fields:
            rows.append([item.get("label"), f"缺失 {item.get('missing_count')} 条 / {item.get('missing_rate')}"])
    abnormal_items = data_quality.get("abnormal_items", [])
    if abnormal_items:
        rows.append(["异常值", ""])
        for item in abnormal_items:
            rows.append([item.get("label"), item.get("count")])
    duplicates = data_quality.get("duplicate_asins", [])
    if duplicates:
        rows.append(["重复 ASIN", "、".join(str(item) for item in duplicates[:20])])
    duplicate_parent = data_quality.get("duplicate_parent_asins", [])
    if duplicate_parent:
        rows.append(["重复父 ASIN", "、".join(str(item) for item in duplicate_parent[:20])])
    if len(rows) == 1:
        rows.append(["状态", "未生成"])
    return rows


def _attribute_definition_rows(definitions: list[dict[str, object]]) -> list[list[object]]:
    rows: list[list[object]] = [["维度", "名称", "判定规则"]]
    for item in definitions:
        if isinstance(item, dict):
            rows.append([item.get("dimension"), item.get("label"), item.get("rule")])
    if len(rows) == 1:
        rows.append(["未生成", "", ""])
    return rows


def _top_product_rows(products: object, currency_code: str = "USD", include_tags: bool = False) -> list[list[object]]:
    rows: list[list[object]] = [["ASIN", "标题", "价格", "月销量", "评分", "评分数", "上架时间", "上架天数", "品牌", "类目", "来源"]]
    if include_tags:
        rows[0].extend(["属性标签", "置信度", "备注"])
    if isinstance(products, list):
        for item in products:
            if not isinstance(item, dict):
                continue
            row = [
                item.get("asin"),
                item.get("title"),
                item.get("price"),
                item.get("monthly_units"),
                item.get("rating"),
                item.get("rating_count"),
                item.get("listing_date"),
                item.get("listing_days"),
                item.get("brand"),
                item.get("category"),
                item.get("note", "卖家精灵搜索结果明细"),
            ]
            if include_tags:
                row.extend(
                    [
                        _display_value(item.get("attribute_tags")),
                        item.get("tag_confidence"),
                        _display_value(item.get("tag_notes")),
                    ]
                )
            rows.append(row)
    if len(rows) == 1:
        rows.append(["待填"] + [""] * (len(rows[0]) - 1))
    return rows


def _attribute_distribution_rows(distributions: list[dict[str, object]]) -> list[list[object]]:
    rows: list[list[object]] = [["维度", "名称", "分布摘要"]]
    for item in distributions:
        if isinstance(item, dict):
            rows.append([item.get("dimension"), item.get("label"), item.get("summary")])
            for bucket in item.get("buckets", [])[:8]:
                if isinstance(bucket, dict):
                    rows.append(
                        [
                            f"  - {item.get('dimension')}",
                            bucket.get("value"),
                            f"{bucket.get('count')} / {_format_percent_or_text(bucket.get('share'))}",
                        ]
                    )
    if len(rows) == 1:
        rows.append(["未生成", "", ""])
    return rows


def _cross_analysis_rows(cross_analysis: list[dict[str, object]], currency_code: str = "USD") -> list[list[object]]:
    rows: list[list[object]] = [["交叉维度", "说明", "组合", "样本数", "均价", "月销量均值", "评分均值", "解释"]]
    for item in cross_analysis:
        if not isinstance(item, dict):
            continue
        cells = item.get("cells", [])
        rows.append([item.get("label"), item.get("purpose"), "", "", "", "", "", item.get("summary")])
        for cell in cells[:8]:
            if isinstance(cell, dict):
                rows.append(
                    [
                        "",
                        "",
                        f"{cell.get('row')} x {cell.get('column')}",
                        cell.get("count"),
                        cell.get("avg_price"),
                        cell.get("avg_monthly_units"),
                        cell.get("avg_rating"),
                        cell.get("interpretation"),
                    ]
                )
    if len(rows) == 1:
        rows.append(["未生成", "", "", "", "", "", "", ""])
    return rows


def _dict_rows(data: dict) -> list[list[object]]:
    rows: list[list[object]] = [["字段", "值"]]
    for key, value in data.items():
        rows.append([key, _display_value(value)])
    if len(rows) == 1:
        rows.append(["待填", ""])
    return rows


def _profit_input_rows(inputs: dict, currency_code: str) -> list[list[object]]:
    rows: list[list[object]] = [["字段", "值"]]
    labels = [
        ("sale_price", f"建议售价（{currency_code}）"),
        ("purchase_cost", f"采购价（{currency_code}）"),
        ("purchase_cost_cny", "采购价（RMB）"),
        ("exchange_rate", f"站点汇率（RMB/{currency_code}）"),
        ("fba_fee", f"FBA费用（{currency_code}）"),
        ("first_leg_shipping", f"头程费用（{currency_code}）"),
        ("first_leg_shipping_cny", "头程费用（RMB）"),
        ("inbound_placement_fee", f"入库配置费（{currency_code}）"),
        ("inbound_placement_fee_cny", "入库配置费（RMB）"),
        ("commission_rate", "佣金率"),
        ("storage_fee_rate", "仓储费率"),
        ("ad_rate_assumption", "广告费率"),
        ("return_rate_assumption", "退货率"),
        ("actual_weight_g", "实际重量（g）"),
        ("volume_weight_g", "体积重（g）"),
        ("first_leg_channel", "头程渠道"),
    ]
    seen = set()
    for key, label in labels:
        if key in inputs:
            rows.append([label, _display_value(inputs.get(key))])
            seen.add(key)
    for key, value in inputs.items():
        if key not in seen:
            rows.append([key, _display_value(value)])
    if len(rows) == 1:
        rows.append(["待填", ""])
    return rows


def _table_rows(data: object, headers: list[str]) -> list[list[object]]:
    rows: list[list[object]] = [headers]
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                rows.append([_display_value(item.get(header)) for header in headers])
    if len(rows) == 1:
        rows.append(["待填"] + [""] * (len(headers) - 1))
    return rows


def _competitor_rows(competitors: dict, currency_code: str = "USD") -> list[list[object]]:
    rows: list[list[object]] = [["分组", "ASIN", "品牌", "标题", "价格", "月销量", "月销售额", "销量占比", "BSR", "评分", "评分数", "上架时间", "上架天数", "备注"]]
    groups = [
        ("top10", "Top10 标杆组"),
        ("recent_winners", "近半年放量新品组"),
        ("structure_supplement", "结构补充组"),
    ]
    for key, label in groups:
        for item in competitors.get(key, []):
            if isinstance(item, dict):
                rows.append(
                    [
                        label,
                        item.get("asin"),
                        item.get("brand"),
                        item.get("title"),
                        item.get("price"),
                        item.get("monthly_units"),
                        item.get("monthly_revenue_usd"),
                        item.get("units_share"),
                        item.get("bsr"),
                        item.get("rating"),
                        item.get("rating_count"),
                        item.get("listing_date"),
                        item.get("listing_days"),
                        item.get("note"),
                    ]
                )
    if len(rows) == 1:
        rows.append(["待填"] + [""] * (len(rows[0]) - 1))
    return rows


def _competitor_markdown_lines(competitors: dict, currency_code: str = "USD") -> list[str]:
    if not competitors:
        return []
    groups = [
        ("top10", "Top10 标杆组"),
        ("recent_winners", "近半年放量新品组"),
        ("structure_supplement", "结构补充组"),
    ]
    lines = ["## 竞品池", ""]
    has_any = False
    for key, label in groups:
        items = competitors.get(key, [])
        if not items:
            continue
        has_any = True
        lines.append(f"### {label}")
        for item in items[:5]:
            lines.append(
                "- "
                + " / ".join(
                    part
                    for part in [
                        str(item.get("asin", "")),
                        str(item.get("brand", "")),
                        _compact_title(item.get("title")),
                        _format_number(item.get("price")) if item.get("price") not in (None, "") else "",
                        _format_number(item.get('monthly_units')) if item.get("monthly_units") not in (None, "") else "",
                        str(item.get("note", "")),
                    ]
                    if part
                )
            )
        lines.append("")
    return lines if has_any else []


def _competitor_deep_dive_rows(cards: list, currency_code: str = "USD") -> list[list[object]]:
    rows: list[list[object]] = [[
        "类型", "ASIN", "品牌", "标题（截取）",
        f"价格({currency_code})", "月销量", "评分", "评分数", "上架天数",
        "备注", "流量词（P19待补）",
    ]]
    for card in (cards or []):
        rows.append([
            card.get("card_type", ""),
            card.get("asin", ""),
            card.get("brand", ""),
            _compact_title(card.get("title"), 60),
            card.get("price_usd"),
            card.get("monthly_units"),
            card.get("rating"),
            card.get("rating_count"),
            card.get("listing_days"),
            card.get("note", ""),
            "—",
        ])
    if len(rows) == 1:
        rows.append(["暂无深拆卡数据"] + [""] * 10)
    return rows


def _competitor_deep_dive_markdown_lines(cards: list, currency_code: str = "USD") -> list[str]:
    if not cards:
        return []
    lines = ["", "## 重点竞品数据", ""]
    for card in cards:
        asin = card.get("asin", "")
        title = _compact_title(card.get("title"), 60)
        card_type = card.get("card_type", "")
        price = card.get("price_usd")
        units = card.get("monthly_units")
        rating = card.get("rating")
        rating_count = card.get("rating_count")
        listing_days = card.get("listing_days")
        lines += [
            f"### {card_type}：{asin}",
            f"- 标题：{title}",
            f"- 价格：{_format_money(price, currency_code)}　月销量：{_format_number(units)}　评分：{rating}（{_format_number(rating_count)} 条）　上架天数：{listing_days or '待补'}",
            f"- 流量词：待 P19 Sorftime 补充",
            "",
        ]
    return lines


def _compact_title(value: object, limit: int = 72) -> str:
    text = str(value or "").strip()
    return text[:limit] + ("..." if len(text) > limit else "")


def _format_number(value: object) -> str:
    if isinstance(value, (int, float)):
        if abs(value) >= 1000:
            return f"{value:,.0f}"
        if value == int(value):
            return str(int(value))
        return f"{value:.2f}"
    return str(value)


def _format_count_items(items: object, limit: int = 5) -> str:
    if not isinstance(items, list):
        return ""
    parts = []
    for item in items[:limit]:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        count = item.get("count")
        if name:
            parts.append(f"{name} {count}" if count not in (None, "") else name)
    return "；".join(parts)


def _site_currency_code(site: object) -> str:
    text = str(site or "").strip().upper()
    mapping = {
        "US": "USD",
        "CA": "CAD",
        "UK": "GBP",
        "EU": "EUR",
        "DE": "EUR",
        "FR": "EUR",
        "IT": "EUR",
        "ES": "EUR",
        "JP": "JPY",
        "AU": "AUD",
        "MX": "MXN",
        "USD": "USD",
        "CAD": "CAD",
        "GBP": "GBP",
        "EUR": "EUR",
        "JPY": "JPY",
        "AUD": "AUD",
        "MXN": "MXN",
        "CNY": "CNY",
        "RMB": "RMB",
    }
    return mapping.get(text, text or "USD")


def _format_money(value: object, currency_code: str) -> str:
    if value in (None, "", "待填", "待补"):
        return "待补"
    if isinstance(value, (int, float)):
        formatted = f"{abs(value):,.2f}" if abs(value) >= 1000 else f"{abs(value):.2f}"
        sign = "-" if value < 0 else ""
        return f"{sign}{formatted}"
    return str(value)


def _normalize_money_text(value: object, currency_code: str) -> str:
    text = str(value or "")
    if not text:
        return text
    text = text.replace("美元", "")
    text = text.replace("美金", "")
    text = text.replace("人民币", "")
    text = text.replace("USD", "")
    text = text.replace("RMB", "")
    text = text.replace("$", "")
    text = text.replace("￥", "")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _format_generated_at(value: object) -> str:
    text = str(value or "").strip()
    if not text or text == "待填":
        return "待填"
    normalized = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return text
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone()
    return parsed.strftime("%Y-%m-%d %H:%M:%S")


def _format_percent_or_text(value: object) -> str:
    if isinstance(value, (int, float)):
        return f"{value * 100:.2f}%"
    return str(value)


def _market_size_value_text(value: object, currency_code: str) -> str:
    text = _normalize_money_text(value, currency_code)
    if not isinstance(value, str):
        return text
    match = re.search(r"市场月均销售额\s*([^；;]+)", text)
    if match:
        return match.group(1).strip()
    return text


def _display_value(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _write_xlsx(output_path: Path, sheets: list[tuple[str, list[list[object]]]]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output_path, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", _content_types_xml(len(sheets)))
        archive.writestr("_rels/.rels", _root_rels_xml())
        archive.writestr("docProps/core.xml", _core_props_xml())
        archive.writestr("docProps/app.xml", _app_props_xml())
        archive.writestr("xl/workbook.xml", _workbook_xml(sheets))
        archive.writestr("xl/_rels/workbook.xml.rels", _workbook_rels_xml(len(sheets)))
        for index, (_, rows) in enumerate(sheets, start=1):
            archive.writestr(f"xl/worksheets/sheet{index}.xml", _worksheet_xml(rows))


def _content_types_xml(sheet_count: int) -> str:
    sheet_overrides = "\n".join(
        f'<Override PartName="/xl/worksheets/sheet{index}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        for index in range(1, sheet_count + 1)
    )
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
  <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
  {sheet_overrides}
</Types>"""


def _root_rels_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>"""


def _core_props_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/">
  <dc:creator>amz-product-research-workbench</dc:creator>
</cp:coreProperties>"""


def _app_props_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties">
  <Application>amz-product-research-workbench</Application>
</Properties>"""


def _workbook_xml(sheets: list[tuple[str, list[list[object]]]]) -> str:
    sheet_nodes = "\n".join(
        f'<sheet name="{_xml_attr(_safe_sheet_name(name))}" sheetId="{index}" r:id="rId{index}"/>'
        for index, (name, _) in enumerate(sheets, start=1)
    )
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets>
    {sheet_nodes}
  </sheets>
</workbook>"""


def _workbook_rels_xml(sheet_count: int) -> str:
    rel_nodes = "\n".join(
        f'<Relationship Id="rId{index}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{index}.xml"/>'
        for index in range(1, sheet_count + 1)
    )
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  {rel_nodes}
</Relationships>"""


def _worksheet_xml(rows: list[list[object]]) -> str:
    row_nodes = "\n".join(
        f'<row r="{row_index}">{_cells_xml(row, row_index)}</row>'
        for row_index, row in enumerate(rows, start=1)
    )
    column_nodes = _columns_xml(rows)
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  {column_nodes}
  <sheetData>
    {row_nodes}
  </sheetData>
</worksheet>"""


def _columns_xml(rows: list[list[object]]) -> str:
    widths = _worksheet_column_widths(rows)
    if not widths:
        return ""
    nodes = "\n".join(
        f'<col min="{index}" max="{index}" width="{width:.1f}" customWidth="1"/>'
        for index, width in enumerate(widths, start=1)
    )
    return f"<cols>\n    {nodes}\n  </cols>"


def _worksheet_column_widths(rows: list[list[object]]) -> list[float]:
    column_count = max((len(row) for row in rows), default=0)
    if column_count == 0:
        return []
    headers = [str(rows[0][index]).strip() if index < len(rows[0]) else "" for index in range(column_count)]
    widths: list[float] = []
    for column_index in range(column_count):
        header = headers[column_index]
        values = [row[column_index] for row in rows if column_index < len(row)]
        max_units = max((_display_width(value) for value in values), default=0)
        min_width, max_width = _column_width_bounds(header)
        width = max(min_width, min(max_units * 1.05 + 2, max_width))
        widths.append(round(width, 1))
    return widths


def _column_width_bounds(header: str) -> tuple[float, float]:
    key = header.strip().lower()
    bounds = {
        "field": (24, 32),
        "label": (16, 24),
        "value": (18, 28),
        "currency": (18, 26),
        "填写口径": (18, 30),
        "required": (12, 18),
        "是否必填": (12, 18),
        "default": (18, 32),
        "note": (52, 90),
        "说明": (36, 90),
        "标题": (36, 72),
        "商品标题": (42, 80),
        "来源": (32, 80),
        "证据": (36, 90),
        "下一步": (36, 90),
    }
    return bounds.get(key, (10, 56))


def _display_width(value: object) -> int:
    text = _display_value(value)
    if not text:
        return 0
    return max((_line_display_width(line) for line in text.splitlines()), default=0)


def _line_display_width(text: str) -> int:
    width = 0
    for char in text:
        code = ord(char)
        if (
            0x1100 <= code <= 0x11FF
            or 0x2E80 <= code <= 0xA4CF
            or 0xAC00 <= code <= 0xD7AF
            or 0xF900 <= code <= 0xFAFF
            or 0xFE10 <= code <= 0xFE6F
            or 0xFF00 <= code <= 0xFFEF
        ):
            width += 2
        else:
            width += 1
    return width


def _cells_xml(row: list[object], row_index: int) -> str:
    cells = []
    for column_index, value in enumerate(row, start=1):
        cell_ref = f"{_column_letter(column_index)}{row_index}"
        text = xml_escape(_display_value(value))
        cells.append(f'<c r="{cell_ref}" t="inlineStr"><is><t>{text}</t></is></c>')
    return "".join(cells)


def _xml_attr(value: str) -> str:
    return xml_escape(value, {'"': "&quot;"})


def _column_letter(index: int) -> str:
    letters = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


def _safe_sheet_name(name: str) -> str:
    invalid_chars = set("[]:*?/\\")
    safe = "".join("_" if char in invalid_chars else char for char in name)
    return safe[:31] or "Sheet"


if __name__ == "__main__":
    raise SystemExit("Use build_outputs(input_path, output_dir) from a wrapper script.")
