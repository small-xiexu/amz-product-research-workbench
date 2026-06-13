"""候选池预审 HTML 看板渲染（从 render_candidate_pool.py 拆分，纯移动不改逻辑）。"""

from __future__ import annotations

import json
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any

from packages.report_renderer.candidate_pool.shared import *  # noqa: F401,F403
from packages.report_renderer.candidate_pool.shared import (
    _sorted_candidates,
    _decision_text,
    _evidence_lines,
    _keyword_signal_lines,
    _direction_card_lines,
    _boundary_review_lines,
    _candidate_quality_lines,
    _data_quality_overview,
    _review_asin_lines,
    _risk_lines,
    _number,
    _percent,
    _display_value,
    STATUS_ORDER,
)


def render_dashboard(candidate_pool: dict[str, Any]) -> str:
    metadata = candidate_pool.get("metadata", {})
    candidates = _sorted_candidates(candidate_pool)
    primary = candidates[0] if candidates else {}
    site = escape(str(metadata.get("site", "待填")))
    generated_at = escape(_format_precheck_generated_at(metadata.get("generated_at", "待填")))
    direction_cards = "\n".join(_direction_panel_html(card) for card in primary.get("direction_cards", []))
    stat_cards = "\n".join(_precheck_stat_card(label, value, note) for label, value, note in _precheck_stats(candidate_pool, primary))
    boundary_panel = _boundary_dashboard_html(primary)
    quality_panel = _quality_dashboard_html(candidate_pool, primary)
    review_table = _review_asin_dashboard_table(primary)
    candidate_overview = _candidate_overview_html(candidates)
    action_cards = _precheck_action_cards_html(primary)
    title = escape(str(primary.get("name", "候选品池预审")))
    decision = escape(_decision_text(primary) if primary else "待生成候选方向")
    next_step = escape(str(primary.get("next_step", "待补")))

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>候选品池预审看板</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f3f0ea;
      --surface: #fffefa;
      --surface-muted: #f7f3eb;
      --surface-strong: #eef4f2;
      --ink: #1f2933;
      --muted: #667085;
      --line: #e3ded5;
      --line-soft: rgba(31, 41, 51, 0.08);
      --accent: #c57445;
      --blue: #52727b;
      --green: #66764f;
      --red: #a25045;
      --amber: #98723a;
      font-family: Inter, "PingFang SC", "Microsoft YaHei", -apple-system, BlinkMacSystemFont, sans-serif;
      color: var(--ink);
      background: var(--bg);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      padding: 24px;
      letter-spacing: 0;
      background:
        radial-gradient(circle at top left, rgba(197, 116, 69, 0.10), transparent 32rem),
        linear-gradient(180deg, #f6f1e9 0%, var(--bg) 100%);
    }}
    main {{
      max-width: 1360px;
      margin: 0 auto;
    }}
    .hero {{
      display: grid;
      grid-template-columns: minmax(0, 1.34fr) minmax(340px, 0.86fr);
      gap: 16px;
      align-items: stretch;
      margin-bottom: 16px;
    }}
    .panel {{
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 24px;
      box-shadow: 0 18px 44px rgba(31, 41, 51, 0.06);
    }}
    .hero-main {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(260px, 0.62fr);
      gap: 18px;
      align-items: end;
    }}
    .hero-title {{
      margin: 8px 0 12px;
      font-size: 38px;
      line-height: 1.12;
      letter-spacing: 0;
    }}
    .eyebrow {{
      font-size: 12px;
      font-weight: 800;
      letter-spacing: 0.14em;
      text-transform: uppercase;
      color: var(--accent);
    }}
    .lead {{
      max-width: 70ch;
      margin: 0;
      color: var(--muted);
      font-size: 15px;
      line-height: 1.75;
    }}
    .meta {{
      margin-top: 16px;
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }}
    .chip, .status {{
      display: inline-flex;
      align-items: center;
      min-height: 30px;
      padding: 0 10px;
      border: 1px solid var(--line);
      border-radius: 999px;
      color: var(--ink);
      background: var(--surface-muted);
      font-size: 12px;
      font-weight: 700;
    }}
    .step-list {{
      display: grid;
      gap: 8px;
      margin: 0;
      padding: 0;
      list-style: none;
    }}
    .step-list li {{
      margin: 0;
      padding: 10px 12px;
      border: 1px solid var(--line-soft);
      border-radius: 8px;
      background: rgba(247, 243, 235, 0.76);
      color: var(--ink);
      font-size: 13px;
      line-height: 1.55;
    }}
    .decision-box {{
      height: 100%;
      background: var(--surface-strong);
      border-color: #d7e3df;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
    }}
    .decision-label {{
      font-size: 12px;
      color: var(--muted);
      font-weight: 800;
      letter-spacing: 0.12em;
      text-transform: uppercase;
    }}
    .decision-value {{
      margin-top: 12px;
      font-size: 30px;
      line-height: 1.18;
      font-weight: 850;
    }}
    .next-step {{
      margin-top: 18px;
      padding: 14px 16px;
      background: rgba(255, 255, 255, 0.72);
      border: 1px solid #d7e2e5;
      border-radius: 8px;
      font-size: 14px;
      line-height: 1.65;
      color: var(--ink);
    }}
    .stat-grid {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 12px;
      margin-bottom: 16px;
    }}
    .stat {{
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 16px;
    }}
    .stat-label {{
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
    }}
    .stat-value {{
      margin-top: 8px;
      font-size: 28px;
      line-height: 1;
      font-weight: 850;
    }}
    .stat-note {{
      margin-top: 8px;
      color: var(--muted);
      font-size: 12px;
      line-height: 1.5;
    }}
    .section {{
      margin-top: 24px;
    }}
    .section-head {{
      display: flex;
      align-items: end;
      justify-content: space-between;
      gap: 16px;
      margin-bottom: 14px;
    }}
    h2 {{
      margin: 0;
      font-size: 24px;
      line-height: 1.25;
    }}
    .hint {{
      margin: 4px 0 0;
      color: var(--muted);
      font-size: 14px;
      line-height: 1.6;
    }}
    .direction-grid {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 12px;
    }}
    .direction {{
      background: var(--surface);
      border: 1px solid var(--line);
      border-left: 5px solid var(--blue);
      border-radius: 8px;
      padding: 18px;
      min-height: 100%;
    }}
    .direction.main {{ border-left-color: var(--green); }}
    .direction.drop {{ border-left-color: var(--red); }}
    .direction.watch {{ border-left-color: var(--amber); }}
    .direction:first-child {{
      grid-column: span 2;
      background: linear-gradient(180deg, #fffefa 0%, #f8f4ec 100%);
    }}
    .direction-top {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: flex-start;
    }}
    .direction h3 {{
      margin: 0;
      font-size: 19px;
      line-height: 1.35;
    }}
    .direction-form {{
      margin: 10px 0 0;
      color: var(--muted);
      font-size: 13px;
      line-height: 1.55;
    }}
    .mini-grid {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 8px;
      margin-top: 14px;
    }}
    .mini {{
      background: var(--surface-muted);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 10px;
    }}
    .mini-label {{
      color: var(--muted);
      font-size: 11px;
      font-weight: 700;
    }}
    .mini-value {{
      margin-top: 4px;
      font-size: 17px;
      font-weight: 820;
    }}
    ul {{
      margin: 12px 0 0;
      padding-left: 18px;
    }}
    li {{
      margin: 6px 0;
      color: var(--muted);
      font-size: 13px;
      line-height: 1.55;
    }}
    .recommend {{
      margin-top: 14px;
      padding: 12px;
      background: rgba(197, 116, 69, 0.08);
      border: 1px solid rgba(197, 116, 69, 0.18);
      border-radius: 8px;
      font-size: 13px;
      line-height: 1.6;
    }}
    .two-col {{
      display: grid;
      grid-template-columns: minmax(0, 0.95fr) minmax(0, 1.05fr);
      gap: 12px;
    }}
    .workbench-row {{
      display: grid;
      grid-template-columns: minmax(0, 1.1fr) minmax(300px, 0.9fr);
      gap: 12px;
      align-items: start;
    }}
    .action-grid {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 12px;
    }}
    .action-card {{
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 16px;
    }}
    .action-label {{
      color: var(--muted);
      font-size: 12px;
      font-weight: 800;
      letter-spacing: 0.1em;
      text-transform: uppercase;
    }}
    .action-value {{
      margin-top: 8px;
      font-size: 18px;
      line-height: 1.35;
      font-weight: 850;
    }}
    .candidate-list {{
      display: grid;
      gap: 8px;
    }}
    .candidate-row {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 10px;
      align-items: center;
      padding: 11px 12px;
      border: 1px solid var(--line-soft);
      border-radius: 8px;
      background: var(--surface-muted);
      font-size: 13px;
      line-height: 1.45;
    }}
    .candidate-row strong {{
      display: block;
      overflow-wrap: anywhere;
    }}
    .candidate-row span {{
      color: var(--muted);
      font-size: 12px;
    }}
    .table-wrap {{
      overflow-x: auto;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--surface);
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      min-width: 720px;
    }}
    th, td {{
      padding: 12px 14px;
      border-bottom: 1px solid var(--line);
      text-align: left;
      font-size: 13px;
      vertical-align: top;
    }}
    th {{
      color: var(--muted);
      background: var(--surface-muted);
      font-weight: 800;
    }}
    tr:last-child td {{ border-bottom: 0; }}
    @media (max-width: 1080px) {{
      .hero, .hero-main, .workbench-row, .two-col, .direction-grid {{
        grid-template-columns: 1fr;
      }}
      .direction:first-child {{
        grid-column: auto;
      }}
      .action-grid, .stat-grid {{
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }}
    }}
    @media (max-width: 760px) {{
      body {{ padding: 16px; }}
      .action-grid, .stat-grid, .mini-grid {{
        grid-template-columns: 1fr;
      }}
      .hero-title {{ font-size: 28px; }}
    }}
  </style>
</head>
<body>
  <main>
    <header class="hero">
      <div class="panel hero-main">
        <div>
          <div class="eyebrow">Candidate Precheck</div>
          <h1 class="hero-title">{title}</h1>
          <p class="lead">这页是正式深挖前的方向选择台：先把主线、旁支、混池和排除项摆清楚，再决定抓哪批评论、补哪些判断。</p>
          <div class="meta">
            <span class="chip">站点 {site}</span>
            <span class="chip">生成时间 {generated_at}</span>
          </div>
        </div>
        <ol class="step-list">
          <li><strong>1. 先定主线：</strong>选择一个最值得深挖的产品形态。</li>
          <li><strong>2. 再定边界：</strong>哪些保留参考，哪些先排除。</li>
          <li><strong>3. 最后抓 VOC：</strong>用建议 ASIN 批次进入评论插件。</li>
        </ol>
      </div>
      <div class="panel decision-box">
        <div>
          <div class="decision-label">Current Decision</div>
          <div class="decision-value">{decision}</div>
        </div>
        <div class="next-step">下一步：{next_step}</div>
      </div>
    </header>

    <div class="stat-grid">
      {stat_cards}
    </div>

    <section class="section">
      <div class="action-grid">
        {action_cards}
      </div>
    </section>

    <section class="section">
      <div class="section-head">
        <div>
          <div class="eyebrow">Direction Cards</div>
          <h2>先选方向，再抓评论</h2>
          <p class="hint">方向卡来自真实搜索结果、ABA 关键词和标题场景识别。第一张优先看，后面的用于判断旁支、混池或排除项。</p>
        </div>
      </div>
      <div class="direction-grid">
        {direction_cards or '<div class="panel">方向卡待生成。</div>'}
      </div>
    </section>

    <section class="section workbench-row">
      <div class="two-col">
        {boundary_panel}
        {quality_panel}
      </div>
      {candidate_overview}
    </section>

    <section class="section">
      <div class="section-head">
        <div>
          <div class="eyebrow">VOC Batch</div>
          <h2>建议评论采集 ASIN 批次</h2>
          <p class="hint">确认方向后，从这批 ASIN 中选择进入评论插件采集，避免随机抓单品。</p>
        </div>
      </div>
      {review_table}
    </section>
  </main>
</body>
</html>"""


def _precheck_stats(candidate_pool: dict[str, Any], candidate: dict[str, Any]) -> list[tuple[str, str, str]]:
    metadata = candidate_pool.get("metadata", {})
    quality = candidate.get("data_quality", {}) if isinstance(candidate, dict) else {}
    search_quality = quality.get("search_result_quality", {}) if isinstance(quality, dict) else {}
    return [
        ("数据源", str(len(metadata.get("data_sources", []))), "卖家精灵/ABA 已识别来源数"),
        ("唯一 ASIN", _number(search_quality.get("unique_asin_count")), "候选池按去重商品计算"),
        ("方向卡", _number(len(candidate.get("direction_cards", []))), "主线、旁支和排除项"),
        ("建议 VOC", _number(len(candidate.get("next_review_voc_asins", []))), "下一步可复制给评论插件"),
    ]


def _precheck_stat_card(label: str, value: str, note: str) -> str:
    return f"""<div class="stat">
  <div class="stat-label">{escape(label)}</div>
  <div class="stat-value">{escape(value)}</div>
  <div class="stat-note">{escape(note)}</div>
</div>"""


def _precheck_action_cards_html(candidate: dict[str, Any]) -> str:
    review_asins = candidate.get("next_review_voc_asins", []) if isinstance(candidate, dict) else []
    boundary = candidate.get("candidate_boundary_review", {}) if isinstance(candidate, dict) else {}
    direction_cards = candidate.get("direction_cards", []) if isinstance(candidate, dict) else []
    mainline = boundary.get("recommended_mainline", "待确认") if isinstance(boundary, dict) else "待确认"
    first_direction = direction_cards[0] if direction_cards and isinstance(direction_cards[0], dict) else {}
    cards = [
        (
            "主线建议",
            mainline or first_direction.get("name", "待确认"),
            "先确认这条线是否符合运营想做的产品形态。",
        ),
        (
            "VOC 批次",
            f"{len(review_asins)} 个 ASIN",
            "确认边界后，把这批 ASIN 复制到评论插件。",
        ),
        (
            "当前动作",
            candidate.get("next_step", "待补") if isinstance(candidate, dict) else "待补",
            "不要直接定品，先完成这一轮人工校准。",
        ),
    ]
    return "".join(
        f"""<div class="action-card">
  <div class="action-label">{escape(label)}</div>
  <div class="action-value">{escape(str(value))}</div>
  <p class="hint">{escape(str(note))}</p>
</div>"""
        for label, value, note in cards
    )


def _candidate_overview_html(candidates: list[dict[str, Any]]) -> str:
    rows = []
    for index, candidate in enumerate(candidates[:6], start=1):
        rows.append(
            f"""<div class="candidate-row">
  <div>
    <strong>{index}. {escape(str(candidate.get("name", "未命名候选方向")))}</strong>
    <span>{escape(_decision_text(candidate))}</span>
  </div>
  <span class="status">{escape(str(candidate.get("status", "待填")))}</span>
</div>"""
        )
    body = "".join(rows) or '<div class="candidate-row"><strong>候选方向待生成</strong><span>待导入数据</span></div>'
    return f"""<div class="panel">
  <div class="eyebrow">Candidate Queue</div>
  <h2>候选方向总览</h2>
  <p class="hint">这里不是排名榜，而是提醒本轮有哪些方向在参与判断。</p>
  <div class="candidate-list" style="margin-top:14px;">{body}</div>
</div>"""


def _direction_panel_html(card: dict[str, Any]) -> str:
    status_class = _direction_status_class(str(card.get("status", "")))
    metrics = [
        ("商品数", _number(card.get("product_count"))),
        ("合计月销", _number(card.get("total_monthly_units"))),
        ("均价", "USD " + _number(card.get("avg_price_usd")) if card.get("avg_price_usd") is not None else "待补"),
    ]
    metric_html = "".join(
        f'<div class="mini"><div class="mini-label">{escape(label)}</div><div class="mini-value">{escape(value)}</div></div>'
        for label, value in metrics
    )
    evidence_html = "".join(f"<li>{escape(str(item))}</li>" for item in card.get("evidence", [])[:4])
    risk_html = "".join(f"<li>{escape(str(item))}</li>" for item in card.get("risks", [])[:2])
    return f"""<article class="direction {status_class}">
  <div class="direction-top">
    <div>
      <h3>{escape(str(card.get("name", "未命名方向")))}</h3>
      <p class="direction-form">{escape(str(card.get("product_form", "待补")))}</p>
    </div>
    <span class="status">{escape(str(card.get("role", "待判断")))} · {escape(str(card.get("status", "待判断")))}</span>
  </div>
  <div class="mini-grid">{metric_html}</div>
  <ul>{evidence_html or "<li>证据待补</li>"}</ul>
  <ul>{risk_html}</ul>
  <div class="recommend">AI 建议：{escape(str(card.get("ai_recommendation", "待补")))}</div>
</article>"""


def _direction_status_class(status: str) -> str:
    if "深挖" in status or "继续" in status:
        return "main"
    if "排除" in status:
        return "drop"
    if "谨慎" in status:
        return "watch"
    return ""


def _boundary_dashboard_html(candidate: dict[str, Any]) -> str:
    review = candidate.get("candidate_boundary_review", {}) if isinstance(candidate, dict) else {}
    questions = review.get("questions", []) if isinstance(review, dict) else []
    question_html = "".join(f"<li>{escape(str(item))}</li>" for item in questions[:6])
    keep = "；".join(str(item) for item in review.get("keep_as_reference", [])[:6]) if isinstance(review, dict) else "待补"
    exclude = "；".join(str(item) for item in review.get("exclude_first", [])[:6]) if isinstance(review, dict) else "待补"
    return f"""<div class="panel">
  <div class="eyebrow">Human Gate</div>
  <h2>VOC 前先确认边界</h2>
  <p class="hint">推荐主线：{escape(str(review.get("recommended_mainline", "待补") if isinstance(review, dict) else "待补"))}</p>
  <p class="hint">保留参考：{escape(keep or "待补")}</p>
  <p class="hint">优先排除：{escape(exclude or "待补")}</p>
  <ul>{question_html or "<li>待补确认问题</li>"}</ul>
</div>"""


def _quality_dashboard_html(candidate_pool: dict[str, Any], candidate: dict[str, Any]) -> str:
    lines = _data_quality_overview(candidate_pool)
    html = "".join(f"<li>{escape(str(item))}</li>" for item in lines[:8])
    return f"""<div class="panel">
  <div class="eyebrow">Data Quality</div>
  <h2>先看数据口径</h2>
  <p class="hint">这里提醒的是能不能放心进入下一步，不是最终选品结论。</p>
  <ul>{html or "<li>数据口径待补</li>"}</ul>
</div>"""


def _review_asin_dashboard_table(candidate: dict[str, Any]) -> str:
    rows = []
    for item in candidate.get("next_review_voc_asins", [])[:12]:
        rows.append(
            "<tr>"
            f"<td>{escape(str(item.get('asin', '待补')))}</td>"
            f"<td>{escape(str(item.get('brand', '待补')))}</td>"
            f"<td>{escape(str(item.get('title', '待补'))[:88])}</td>"
            f"<td>{escape(_number(item.get('monthly_units')))}</td>"
            f"<td>{escape(str(item.get('reason', '待补')))}</td>"
            "</tr>"
        )
    body = "".join(rows) or '<tr><td colspan="5">建议 ASIN 待生成</td></tr>'
    return f"""<div class="table-wrap">
  <table>
    <thead><tr><th>ASIN</th><th>品牌</th><th>标题</th><th>月销量</th><th>推荐原因</th></tr></thead>
    <tbody>{body}</tbody>
  </table>
</div>"""


def _candidate_card_html(candidate: dict[str, Any]) -> str:
    status = str(candidate.get("status", "待填"))
    status_class = {
        "先放弃": "drop",
        "观察": "watch",
        "试做": "trial",
    }.get(status, "")
    evidence = "".join(f"<li>{escape(item)}</li>" for item in _evidence_lines(candidate)[:4])
    directions = "".join(f"<li>{escape(item)}</li>" for item in _direction_card_lines(candidate)[:4])
    boundary = "".join(f"<li>{escape(item)}</li>" for item in _boundary_review_lines(candidate)[:3])
    risks = "".join(f"<li>{escape(item)}</li>" for item in _risk_lines(candidate)[:4])
    missing = "".join(f"<li>{escape(str(item))}</li>" for item in candidate.get("missing_data", [])[:5])
    return f"""<article>
  <h2>{escape(str(candidate.get("name", "未命名候选方向")))}</h2>
  <span class="status {status_class}">{escape(status)}</span>
  <div class="decision">{escape(_decision_text(candidate))}</div>
  <section>
    <h3>主要证据</h3>
    <ul>{evidence or "<li>待补</li>"}</ul>
  </section>
  <section>
    <h3>报表后方向</h3>
    <ul>{directions or "<li>待补</li>"}</ul>
  </section>
  <section>
    <h3>VOC 前确认</h3>
    <ul>{boundary or "<li>待补</li>"}</ul>
  </section>
  <section>
    <h3>主要风险</h3>
    <ul>{risks or "<li>待补</li>"}</ul>
  </section>
  <section>
    <h3>缺失数据</h3>
    <ul>{missing or "<li>暂无</li>"}</ul>
  </section>
</article>"""


def _format_precheck_generated_at(value: Any) -> str:
    if value in (None, "", "待填"):
        return "待填"
    text = str(value)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return text
    return parsed.strftime("%Y-%m-%d %H:%M:%S")
