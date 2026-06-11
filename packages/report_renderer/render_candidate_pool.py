"""Render candidate-pool precheck outputs before deep research."""

from __future__ import annotations

from datetime import datetime
from html import escape
import json
from pathlib import Path
from typing import Any

from packages.report_renderer.render_report import _write_xlsx


STATUS_ORDER = {"继续看": 0, "试做": 1, "观察": 2, "先放弃": 3}


def build_outputs(input_path: str, output_dir: str) -> None:
    candidate_pool = json.loads(Path(input_path).read_text(encoding="utf-8"))
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "candidate_pool.json").write_text(
        json.dumps(candidate_pool, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (out / "precheck_report.md").write_text(render_markdown(candidate_pool), encoding="utf-8")
    (out / "precheck_summary.md").write_text(render_summary(candidate_pool), encoding="utf-8")
    (out / "precheck_dashboard.html").write_text(render_dashboard(candidate_pool), encoding="utf-8")
    render_data_workbook(candidate_pool, out / "precheck_data.xlsx")


def render_markdown(candidate_pool: dict[str, Any]) -> str:
    metadata = candidate_pool.get("metadata", {})
    summary = candidate_pool.get("summary", {})
    source_brief = candidate_pool.get("source_brief", {})
    candidates = _sorted_candidates(candidate_pool)
    site = metadata.get("site") or source_brief.get("site") or "待填"
    first_next_step = _first_next_step(candidates)

    lines: list[str] = [
        "# 候选品池预审报告",
        "",
        "## 本轮结论",
        f"- 站点：{site}",
        f"- 候选方向数：{summary.get('total_candidates', len(candidates))}",
        f"- 继续看：{summary.get('continue_count', _count_status(candidates, '继续看'))}",
        f"- 试做：{summary.get('trial_count', _count_status(candidates, '试做'))}",
        f"- 观察：{summary.get('watch_count', _count_status(candidates, '观察'))}",
        f"- 先放弃：{summary.get('drop_count', _count_status(candidates, '先放弃'))}",
        f"- 建议下一步：{first_next_step}",
        "",
        "## 数据盘点",
    ]
    lines.extend(_bullet_lines(_data_quality_overview(candidate_pool)))
    lines.extend(
        [
            "",
            "## 候选总览",
            "",
            "| 候选方向 | 状态 | 预审判断 | 主要证据 | 主要风险 | 缺失数据 |",
            "|---|---|---|---|---|---|",
        ]
    )

    for candidate in candidates:
        lines.append(
            "| "
            + " | ".join(
                [
                    _md_cell(candidate.get("name")),
                    _md_cell(candidate.get("status")),
                    _md_cell(_decision_text(candidate)),
                    _md_cell("; ".join(_evidence_lines(candidate)[:3])),
                    _md_cell("; ".join(_risk_lines(candidate)[:3])),
                    _md_cell("; ".join(candidate.get("missing_data", [])[:5])),
                ]
            )
            + " |"
        )

    for candidate in candidates:
        lines.extend(
            [
                "",
                f"## {candidate.get('name', '未命名候选方向')}",
                "",
                f"- 状态：{candidate.get('status', '待填')}",
                f"- 预审判断：{_decision_text(candidate)}",
                f"- 出现原因：{candidate.get('reason', '待填')}",
                "",
                "### 需求证据",
            ]
        )
        lines.extend(_bullet_lines(_evidence_lines(candidate)))
        lines.extend(["", "### 竞争和新品机会"])
        lines.extend(_bullet_lines(_competition_lines(candidate)))
        lines.extend(["", "### 关键词和混池提示"])
        lines.extend(_bullet_lines(_keyword_signal_lines(candidate)))
        lines.extend(["", "### 报表后多方向候选卡"])
        lines.extend(_bullet_lines(_direction_card_lines(candidate)))
        lines.extend(["", "### 候选边界二次校准"])
        lines.extend(_bullet_lines(_boundary_review_lines(candidate)))
        lines.extend(["", "### 建议评论 VOC ASIN 批次"])
        lines.extend(_bullet_lines(_review_asin_lines(candidate)))
        lines.extend(["", "### 数据质量口径"])
        lines.extend(_bullet_lines(_candidate_quality_lines(candidate)))
        lines.extend(["", "### 风险和缺口"])
        lines.extend(_bullet_lines(_risk_lines(candidate)))
        lines.extend(_bullet_lines([f"缺失数据：{', '.join(candidate.get('missing_data', []))}"]))
        lines.extend(["", "### 下一步"])
        lines.extend(_bullet_lines([candidate.get("next_step", "待补")]))
        lines.extend(["", "### 来源"])
        lines.extend(_bullet_lines(candidate.get("source_refs", []) or ["待补"]))

    lines.extend(
        [
            "",
            "## 使用边界",
            "- 本报告用于候选方向预审，只判断是否值得进入正式深挖。",
            "- 利润、退货、知产和合规仍为早期提示，不能替代运营复核。",
            "- 进入深挖后才接入评论/VOC、Top10 标杆组、近半年新品组和利润复核。",
        ]
    )
    return "\n".join(lines) + "\n"


def render_summary(candidate_pool: dict[str, Any]) -> str:
    candidates = _sorted_candidates(candidate_pool)
    lines = [
        "# 候选池摘要",
        "",
        f"- 候选方向数：{len(candidates)}",
        f"- 优先处理：{_first_candidate_name(candidates)}",
        f"- 下一步：{_first_next_step(candidates)}",
        "",
        "## 候选状态",
    ]
    for candidate in candidates:
        lines.append(
            f"- {candidate.get('name', '未命名候选方向')}：{candidate.get('status', '待填')}，"
            f"{_decision_text(candidate)}"
        )
    return "\n".join(lines) + "\n"


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


def render_data_workbook(candidate_pool: dict[str, Any], output_path: str | Path) -> None:
    _write_xlsx(Path(output_path), _build_workbook_sheets(candidate_pool))


def _build_workbook_sheets(candidate_pool: dict[str, Any]) -> list[tuple[str, list[list[object]]]]:
    candidates = _sorted_candidates(candidate_pool)
    metadata = candidate_pool.get("metadata", {})
    summary = candidate_pool.get("summary", {})
    source_brief = candidate_pool.get("source_brief", {})
    return [
        (
            "候选总览",
            [
                ["候选ID", "候选方向", "类型", "状态", "预审判断", "主要证据", "关键词/混池提示", "报表后方向卡", "候选边界校准", "建议VOC ASIN", "数据质量口径", "主要风险", "缺失数据", "下一步"],
                *[
                    [
                        candidate.get("candidate_id"),
                        candidate.get("name"),
                        candidate.get("candidate_type"),
                        candidate.get("status"),
                        _decision_text(candidate),
                        "\n".join(_evidence_lines(candidate)),
                        "\n".join(_keyword_signal_lines(candidate)),
                        "\n".join(_direction_card_lines(candidate)),
                        "\n".join(_boundary_review_lines(candidate)),
                        "\n".join(_review_asin_lines(candidate)),
                        "\n".join(_candidate_quality_lines(candidate)),
                        "\n".join(_risk_lines(candidate)),
                        "\n".join(candidate.get("missing_data", [])),
                        candidate.get("next_step"),
                    ]
                    for candidate in candidates
                ],
            ],
        ),
        ("候选详情", _candidate_detail_rows(candidates)),
        ("ABA关键词", _aba_keyword_rows(candidates)),
        ("方向候选卡", _direction_card_rows(candidates)),
        ("边界校准", _boundary_review_rows(candidates)),
        ("建议VOC ASIN", _review_asin_rows(candidates)),
        ("数据质量口径", _quality_rows(candidates)),
        ("待确认标签", _pending_label_rows(candidates)),
        ("缺失数据", _missing_data_rows(candidates)),
        ("来源追溯", _source_rows(candidates)),
        (
            "本轮摘要",
            [
                ["字段", "值"],
                ["站点", metadata.get("site") or source_brief.get("site")],
                ["生成时间", metadata.get("generated_at")],
                ["发现模式", metadata.get("discovery_mode")],
                ["候选数量", summary.get("total_candidates", len(candidates))],
                ["关键缺口", "\n".join(summary.get("key_gaps", []))],
                ["调研范围", _display_value(source_brief.get("search_scope"))],
                ["排除规则", "\n".join(source_brief.get("exclusion_rules", []))],
            ],
        ),
    ]


def _candidate_detail_rows(candidates: list[dict[str, Any]]) -> list[list[object]]:
    rows: list[list[object]] = [["候选方向", "模块", "字段", "值"]]
    modules = [
        ("需求证据", "demand_evidence"),
        ("竞争结构", "competition_structure"),
        ("新品机会", "new_listing_opportunity"),
        ("利润空间参考", "preliminary_profit_space"),
        ("退货风险", "return_risk"),
        ("知产/合规风险", "ip_compliance_risk"),
        ("数据质量", "data_quality"),
    ]
    for candidate in candidates:
        rows.append([candidate.get("name"), "基础信息", "出现原因", candidate.get("reason")])
        for module_label, module_key in modules:
            module = candidate.get(module_key, {})
            if isinstance(module, dict):
                for key, value in module.items():
                    rows.append([candidate.get("name"), module_label, key, _display_value(value)])
    return rows


def _aba_keyword_rows(candidates: list[dict[str, Any]]) -> list[list[object]]:
    rows: list[list[object]] = [["候选方向", "类型", "关键词", "翻译", "月搜索量", "现排名", "PPC(USD)", "点击量", "SPR", "来源文件"]]
    for candidate in candidates:
        signal = candidate.get("demand_evidence", {}).get("aba_keyword_signal", {})
        if not isinstance(signal, dict):
            continue
        for row_type, items in (
            ("Top ABA词", signal.get("top_keywords", [])),
            ("目标相关词", signal.get("target_keywords", [])),
            ("混池风险词", signal.get("mixed_keywords", [])),
        ):
            for item in items:
                if not isinstance(item, dict):
                    continue
                rows.append([
                    candidate.get("name"),
                    row_type,
                    item.get("keyword"),
                    item.get("translation"),
                    item.get("monthly_searches"),
                    item.get("current_rank"),
                    item.get("ppc_usd"),
                    item.get("clicks"),
                    item.get("spr"),
                    item.get("source_file"),
                ])
    if len(rows) == 1:
        rows.append(["待填", "待填", "待填", "", "", "", "", "", "", ""])
    return rows


def _direction_card_rows(candidates: list[dict[str, Any]]) -> list[list[object]]:
    rows: list[list[object]] = [
        [
            "候选方向",
            "方向卡",
            "角色",
            "状态",
            "产品形态",
            "商品数",
            "合计月销量",
            "均价(USD)",
            "关联关键词",
            "代表ASIN",
            "核心证据",
            "风险",
            "AI建议",
            "运营可选动作",
            "下一步",
        ]
    ]
    for candidate in candidates:
        for card in candidate.get("direction_cards", []):
            keywords = []
            for item in card.get("matched_keywords", []):
                if isinstance(item, dict) and item.get("keyword"):
                    keywords.append(f"{item.get('keyword')} / 月搜 {_number(item.get('monthly_searches'))}")
            products = []
            for item in card.get("representative_products", []):
                if isinstance(item, dict) and item.get("asin"):
                    products.append(f"{item.get('asin')} / {item.get('brand') or '未知品牌'} / 月销 {_number(item.get('monthly_units'))}")
            rows.append([
                candidate.get("name"),
                card.get("name"),
                card.get("role"),
                card.get("status"),
                card.get("product_form"),
                card.get("product_count"),
                card.get("total_monthly_units"),
                card.get("avg_price_usd"),
                "\n".join(keywords),
                "\n".join(products),
                "\n".join(str(item) for item in card.get("evidence", [])),
                "\n".join(str(item) for item in card.get("risks", [])),
                card.get("ai_recommendation"),
                "\n".join(str(item) for item in card.get("operator_options", [])),
                card.get("next_action"),
            ])
    if len(rows) == 1:
        rows.append(["待填", "待填", "待填", "待填", "待填", "", "", "", "", "", "", "", "", "", ""])
    return rows


def _boundary_review_rows(candidates: list[dict[str, Any]]) -> list[list[object]]:
    rows: list[list[object]] = [["候选方向", "检查点", "推荐主线", "保留参考", "优先排除", "确认问题", "默认处理"]]
    for candidate in candidates:
        review = candidate.get("candidate_boundary_review", {})
        if not isinstance(review, dict):
            continue
        rows.append([
            candidate.get("name"),
            review.get("checkpoint"),
            review.get("recommended_mainline"),
            "\n".join(str(item) for item in review.get("keep_as_reference", [])),
            "\n".join(str(item) for item in review.get("exclude_first", [])),
            "\n".join(str(item) for item in review.get("questions", [])),
            review.get("default_if_no_change"),
        ])
    if len(rows) == 1:
        rows.append(["待填", "待填", "待填", "待填", "待填", "待填", "待填"])
    return rows


def _review_asin_rows(candidates: list[dict[str, Any]]) -> list[list[object]]:
    rows: list[list[object]] = [["候选方向", "ASIN", "品牌", "标题", "价格(USD)", "月销量", "评分", "评分数", "推荐原因"]]
    for candidate in candidates:
        for item in candidate.get("next_review_voc_asins", []):
            rows.append([
                candidate.get("name"),
                item.get("asin"),
                item.get("brand"),
                item.get("title"),
                item.get("price_usd"),
                item.get("monthly_units"),
                item.get("rating"),
                item.get("rating_count"),
                item.get("reason"),
            ])
    if len(rows) == 1:
        rows.append(["待填", "待填", "待填", "待填", "", "", "", "", ""])
    return rows


def _quality_rows(candidates: list[dict[str, Any]]) -> list[list[object]]:
    rows: list[list[object]] = [["候选方向", "模块", "字段", "值"]]
    for candidate in candidates:
        quality = candidate.get("data_quality", {})
        if not isinstance(quality, dict):
            continue
        search_quality = quality.get("search_result_quality", {})
        if isinstance(search_quality, dict):
            for key, value in search_quality.items():
                rows.append([candidate.get("name"), "搜索结果口径", key, _display_value(value)])
        top_quality = quality.get("top_product_quality", {})
        if isinstance(top_quality, dict):
            for key, value in top_quality.items():
                rows.append([candidate.get("name"), "Top商品质量", key, _display_value(value)])
        for warning in quality.get("manifest_warnings", [])[:30]:
            rows.append([candidate.get("name"), "导入盘点提醒", "warning", warning])
    if len(rows) == 1:
        rows.append(["待填", "待填", "待填", "待填"])
    return rows


def _pending_label_rows(candidates: list[dict[str, Any]]) -> list[list[object]]:
    """Products with auto-tag confidence 低 or product_route 待确认, for operator correction."""
    rows: list[list[object]] = [[
        "候选方向", "ASIN", "标题（截取）", "价格($)", "月销量",
        "AI路线标签", "AI功能标签", "置信度",
        "运营填写-产品路线", "运营填写-主场景", "备注",
    ]]
    for candidate in candidates:
        market_structure = candidate.get("market_structure", {})
        tagged_products = market_structure.get("tagged_products", []) if isinstance(market_structure, dict) else []
        for product in tagged_products:
            tags = product.get("attribute_tags", {})
            route = tags.get("product_route", "")
            confidence = tags.get("tag_confidence", "")
            if route == "待确认" or confidence == "低":
                title = str(product.get("title") or "")[:60]
                feature = ", ".join(tags.get("feature_tags", [])) if isinstance(tags.get("feature_tags"), list) else str(tags.get("feature_tags", ""))
                rows.append([
                    candidate.get("name", ""),
                    product.get("asin", ""),
                    title,
                    product.get("price"),
                    product.get("monthly_units"),
                    route,
                    feature,
                    confidence,
                    "",  # 运营填写
                    "",  # 运营填写
                    "",  # 备注
                ])
    if len(rows) == 1:
        rows.append(["暂无待确认标签", "", "", "", "", "", "", "", "", "", ""])
    return rows


def _missing_data_rows(candidates: list[dict[str, Any]]) -> list[list[object]]:
    rows: list[list[object]] = [["候选方向", "缺失数据", "处理建议"]]
    for candidate in candidates:
        for gap in candidate.get("missing_data", []):
            rows.append([candidate.get("name"), gap, _gap_action(gap)])
    if len(rows) == 1:
        rows.append(["待填", "待填", "待填"])
    return rows


def _source_rows(candidates: list[dict[str, Any]]) -> list[list[object]]:
    rows: list[list[object]] = [["候选方向", "来源"]]
    for candidate in candidates:
        for source in candidate.get("source_refs", []):
            rows.append([candidate.get("name"), source])
    if len(rows) == 1:
        rows.append(["待填", "待填"])
    return rows


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


def _sorted_candidates(candidate_pool: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = [item for item in candidate_pool.get("candidates", []) if isinstance(item, dict)]
    return sorted(candidates, key=lambda item: STATUS_ORDER.get(str(item.get("status")), 9))


def _count_status(candidates: list[dict[str, Any]], status: str) -> int:
    return sum(1 for candidate in candidates if candidate.get("status") == status)


def _first_candidate_name(candidates: list[dict[str, Any]]) -> str:
    return str(candidates[0].get("name", "待补")) if candidates else "待补"


def _first_next_step(candidates: list[dict[str, Any]]) -> str:
    return str(candidates[0].get("next_step", "待补")) if candidates else "待补"


def _decision_text(candidate: dict[str, Any]) -> str:
    status = candidate.get("status")
    if status in ("继续看", "试做"):
        return "可进入深挖候选，但正式结论需补评论、竞品池、利润和风险复核"
    if status == "观察":
        return "先补关键缺口或换一批数据复核，再决定是否深挖"
    if status == "先放弃":
        return "暂不进入深挖，除非后续有明确改品方案或新证据"
    return "状态待确认"


def _evidence_lines(candidate: dict[str, Any]) -> list[str]:
    demand = candidate.get("demand_evidence", {})
    lines = list(candidate.get("appearance_reason", [])[:3])
    if demand.get("market_avg_monthly_units") is not None:
        lines.append(f"市场月均销量：{_number(demand.get('market_avg_monthly_units'))}")
    if demand.get("market_avg_monthly_revenue_usd") is not None:
        lines.append(f"市场月均销售额：USD {_number(demand.get('market_avg_monthly_revenue_usd'))}")
    if demand.get("market_avg_price_usd") is not None:
        lines.append(f"市场平均价：USD {_number(demand.get('market_avg_price_usd'))}")
    if demand.get("top_keyword"):
        keyword_line = f"核心流量词：{demand.get('top_keyword')}"
        if demand.get("top_keyword_monthly_searches") is not None:
            keyword_line += f"（月搜索量 {_number(demand.get('top_keyword_monthly_searches'))}）"
        lines.append(keyword_line)
    if demand.get("aba_top_search_term"):
        lines.append(f"ABA 搜索词：{demand.get('aba_top_search_term')}")
    aba_signal = demand.get("aba_keyword_signal", {})
    if isinstance(aba_signal, dict) and aba_signal.get("signal"):
        lines.append(str(aba_signal.get("signal")))
    for key in ("search_signal", "trend_signal", "top100_signal"):
        if demand.get(key):
            lines.append(f"{key}：{demand.get(key)}")
    return [str(item) for item in lines if item not in (None, "")]


def _keyword_signal_lines(candidate: dict[str, Any]) -> list[str]:
    signal = candidate.get("demand_evidence", {}).get("aba_keyword_signal", {})
    if not isinstance(signal, dict):
        return []
    lines: list[str] = []
    if signal.get("signal"):
        lines.append(str(signal.get("signal")))
    target_keywords = signal.get("target_keywords", [])
    if target_keywords:
        values = [
            f"{item.get('keyword')}（月搜 {_number(item.get('monthly_searches'))}）"
            for item in target_keywords[:5]
            if isinstance(item, dict) and item.get("keyword")
        ]
        if values:
            lines.append("目标相关词：" + "；".join(values))
    mixed_keywords = signal.get("mixed_keywords", [])
    if mixed_keywords:
        values = [
            f"{item.get('keyword')}（{item.get('intent')}，月搜 {_number(item.get('monthly_searches'))}）"
            for item in mixed_keywords[:5]
            if isinstance(item, dict) and item.get("keyword")
        ]
        if values:
            lines.append("混池风险词：" + "；".join(values))
    return lines


def _direction_card_lines(candidate: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for card in candidate.get("direction_cards", [])[:6]:
        if not isinstance(card, dict):
            continue
        evidence = "；".join(str(item) for item in card.get("evidence", [])[:3])
        line = (
            f"{card.get('name', '未命名方向')}｜{card.get('role', '待判断')}｜{card.get('status', '待判断')}｜"
            f"商品 {card.get('product_count', '待补')} 个｜合计月销量 {_number(card.get('total_monthly_units'))}｜"
            f"AI建议：{card.get('ai_recommendation', '待补')}"
        )
        if evidence:
            line += f"｜证据：{evidence}"
        lines.append(line)
    return lines


def _boundary_review_lines(candidate: dict[str, Any]) -> list[str]:
    review = candidate.get("candidate_boundary_review", {})
    if not isinstance(review, dict):
        return []
    lines = []
    if review.get("recommended_mainline"):
        lines.append(f"推荐主线：{review.get('recommended_mainline')}")
    keep = review.get("keep_as_reference", [])
    if keep:
        lines.append("保留参考：" + "；".join(str(item) for item in keep[:8]))
    exclude = review.get("exclude_first", [])
    if exclude:
        lines.append("优先排除：" + "；".join(str(item) for item in exclude[:8]))
    for question in review.get("questions", [])[:5]:
        lines.append(f"待确认：{question}")
    if review.get("default_if_no_change"):
        lines.append(f"默认：{review.get('default_if_no_change')}")
    return lines


def _candidate_quality_lines(candidate: dict[str, Any]) -> list[str]:
    quality = candidate.get("data_quality", {})
    if not isinstance(quality, dict):
        return []
    lines: list[str] = []
    search_quality = quality.get("search_result_quality", {})
    if isinstance(search_quality, dict):
        for note in search_quality.get("notes", [])[:4]:
            lines.append(str(note))
        if search_quality.get("duplicate_asin_count"):
            lines.append(f"重复 ASIN 数：{search_quality.get('duplicate_asin_count')}")
    top_quality = quality.get("top_product_quality", {})
    if isinstance(top_quality, dict):
        lines.append(
            f"Top商品质量：{top_quality.get('level', '待补')}，"
            f"唯一 ASIN {top_quality.get('unique_asin_count', '待补')}，"
            f"质量分 {top_quality.get('quality_score', '待补')}"
        )
        for warning in top_quality.get("warnings", [])[:4]:
            lines.append(str(warning))
    for warning in quality.get("manifest_warnings", [])[:5]:
        lines.append(str(warning))
    return lines


def _data_quality_overview(candidate_pool: dict[str, Any]) -> list[str]:
    metadata = candidate_pool.get("metadata", {})
    source_brief = candidate_pool.get("source_brief", {})
    search_scope = source_brief.get("search_scope", {}) if isinstance(source_brief.get("search_scope"), dict) else {}
    lines = [
        f"发现模式：{metadata.get('discovery_mode', '待填')}",
        f"数据源类型：{', '.join(metadata.get('data_sources', [])) or '待补'}",
        f"搜索入口：{search_scope.get('seed_keyword', '待补')}",
    ]
    for candidate in _sorted_candidates(candidate_pool):
        for line in _candidate_quality_lines(candidate)[:4]:
            lines.append(f"{candidate.get('name', '候选方向')}：{line}")
    return lines


def _review_asin_lines(candidate: dict[str, Any]) -> list[str]:
    items = candidate.get("next_review_voc_asins", [])
    lines = []
    for item in items[:20]:
        asin = item.get("asin")
        if not asin:
            continue
        details = []
        if item.get("brand"):
            details.append(str(item.get("brand")))
        if item.get("monthly_units") is not None:
            details.append(f"月销 {_number(item.get('monthly_units'))}")
        if item.get("reason"):
            details.append(str(item.get("reason")))
        lines.append(f"{asin}：" + "，".join(details))
    return lines


def _competition_lines(candidate: dict[str, Any]) -> list[str]:
    competition = candidate.get("competition_structure", {})
    new_listing = candidate.get("new_listing_opportunity", {})
    profit = candidate.get("preliminary_profit_space", {})
    lines: list[str] = []
    if competition.get("sample_product_count") is not None:
        lines.append(f"样本商品数：{_number(competition.get('sample_product_count'))}")
    if competition.get("top10_avg_monthly_units") is not None:
        lines.append(f"Top10 月均销量：{_number(competition.get('top10_avg_monthly_units'))}")
    if competition.get("top10_product_units_share") is not None:
        lines.append(f"Top10 商品销量占比：{_percent(competition.get('top10_product_units_share'))}")
    if competition.get("top_brand"):
        lines.append(f"头部品牌：{competition.get('top_brand')}，销量占比 {_percent(competition.get('top_brand_units_share'))}")
    if competition.get("top_seller_location"):
        lines.append(
            f"主要卖家所在地：{competition.get('top_seller_location')}，销量占比 "
            f"{_percent(competition.get('top_seller_location_units_share'))}"
        )
    if new_listing.get("new_listing_count_6m") is not None:
        lines.append(f"近半年新品数：{_number(new_listing.get('new_listing_count_6m'))}")
    if new_listing.get("new_listing_avg_monthly_units") is not None:
        lines.append(f"近半年新品月均销量：{_number(new_listing.get('new_listing_avg_monthly_units'))}")
    if profit.get("top_price_band_by_units"):
        lines.append(f"销量集中价格带：{profit.get('top_price_band_by_units')}")
    if competition.get("notes"):
        lines.append(str(competition.get("notes")))
    return [line for line in lines if line]


def _risk_lines(candidate: dict[str, Any]) -> list[str]:
    lines = [str(item) for item in candidate.get("risk_flags", []) if item]
    return_risk = candidate.get("return_risk", {})
    ip_risk = candidate.get("ip_compliance_risk", {})
    if return_risk.get("level"):
        text = f"退货风险：{return_risk.get('level')}"
        if return_risk.get("market_return_rate") is not None:
            text += f"，市场退货率 {_percent(return_risk.get('market_return_rate'))}"
        if return_risk.get("category_return_rate") is not None:
            text += f"，类目退货率 {_percent(return_risk.get('category_return_rate'))}"
        lines.append(text)
    if ip_risk.get("level"):
        text = f"知产/合规：{ip_risk.get('level')}"
        if ip_risk.get("notes"):
            text += f"，{ip_risk.get('notes')}"
        lines.append(text)
    return lines


def _bullet_lines(items: list[Any]) -> list[str]:
    values = [str(item) for item in items if item not in (None, "")]
    if not values:
        return ["- 待补"]
    return [f"- {value}" for value in values]


def _gap_action(gap: str) -> str:
    if "评论" in gap or "VOC" in gap:
        return "进入深挖后读取自有评论插件导出"
    if "FBA" in gap or "头程" in gap or "入库" in gap or "采购" in gap:
        return "利润复核阶段由运营手填或后台核算"
    if "商标" in gap or "专利" in gap:
        return "进入深挖后做知产初筛并保留人工复核"
    return "根据是否进入深挖决定是否补充"


def _number(value: Any) -> str:
    if value is None:
        return "待补"
    if isinstance(value, (int, float)):
        if abs(value) >= 1000:
            return f"{value:,.0f}"
        if value == int(value):
            return str(int(value))
        return f"{value:.2f}"
    return str(value)


def _percent(value: Any) -> str:
    if value is None:
        return "待补"
    if isinstance(value, (int, float)):
        percent_value = value * 100 if -1 <= value <= 1 else value
        return f"{percent_value:.2f}%"
    text = str(value)
    return text if "%" in text else text + "%"


def _format_precheck_generated_at(value: Any) -> str:
    if value in (None, "", "待填"):
        return "待填"
    text = str(value)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return text
    return parsed.strftime("%Y-%m-%d %H:%M:%S")


def _md_cell(value: Any) -> str:
    text = _display_value(value)
    return text.replace("|", "\\|").replace("\n", "<br>")


def _display_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)
