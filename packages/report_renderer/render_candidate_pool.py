"""Render candidate-pool precheck outputs before deep research."""

from __future__ import annotations

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
        "## 候选总览",
        "",
        "| 候选方向 | 状态 | 预审判断 | 主要证据 | 主要风险 | 缺失数据 |",
        "|---|---|---|---|---|---|",
    ]

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
    site = escape(str(metadata.get("site", "待填")))
    cards = "\n".join(_candidate_card_html(candidate) for candidate in candidates)
    generated_at = escape(str(metadata.get("generated_at", "待填")))

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>候选品池预审看板</title>
  <style>
    :root {{
      color-scheme: light;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: #172033;
      background: #f6f7f9;
    }}
    body {{
      margin: 0;
      padding: 32px;
    }}
    main {{
      max-width: 1120px;
      margin: 0 auto;
    }}
    header {{
      margin-bottom: 24px;
    }}
    h1 {{
      margin: 0 0 8px;
      font-size: 30px;
      line-height: 1.2;
    }}
    .meta {{
      color: #5c667a;
      font-size: 14px;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 16px;
    }}
    article {{
      background: #ffffff;
      border: 1px solid #dce1ea;
      border-radius: 8px;
      padding: 18px;
    }}
    h2 {{
      margin: 0 0 10px;
      font-size: 19px;
    }}
    .status {{
      display: inline-flex;
      align-items: center;
      min-height: 26px;
      padding: 0 10px;
      border-radius: 999px;
      font-size: 13px;
      font-weight: 700;
      background: #e9f2ff;
      color: #1f5fae;
    }}
    .status.drop {{
      background: #fff0f0;
      color: #a73333;
    }}
    .status.watch {{
      background: #fff6dd;
      color: #8a5d00;
    }}
    .status.trial {{
      background: #eaf8ee;
      color: #237043;
    }}
    section {{
      margin-top: 14px;
    }}
    h3 {{
      margin: 0 0 6px;
      font-size: 13px;
      color: #5c667a;
    }}
    ul {{
      margin: 0;
      padding-left: 18px;
    }}
    li {{
      margin: 4px 0;
      line-height: 1.45;
    }}
    .decision {{
      margin-top: 10px;
      font-weight: 700;
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <h1>候选品池预审看板</h1>
      <div class="meta">站点：{site} · 生成时间：{generated_at}</div>
    </header>
    <div class="grid">
      {cards}
    </div>
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
                ["候选ID", "候选方向", "类型", "状态", "预审判断", "主要证据", "主要风险", "缺失数据", "下一步"],
                *[
                    [
                        candidate.get("candidate_id"),
                        candidate.get("name"),
                        candidate.get("candidate_type"),
                        candidate.get("status"),
                        _decision_text(candidate),
                        "\n".join(_evidence_lines(candidate)),
                        "\n".join(_risk_lines(candidate)),
                        "\n".join(candidate.get("missing_data", [])),
                        candidate.get("next_step"),
                    ]
                    for candidate in candidates
                ],
            ],
        ),
        ("候选详情", _candidate_detail_rows(candidates)),
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


def _candidate_card_html(candidate: dict[str, Any]) -> str:
    status = str(candidate.get("status", "待填"))
    status_class = {
        "先放弃": "drop",
        "观察": "watch",
        "试做": "trial",
    }.get(status, "")
    evidence = "".join(f"<li>{escape(item)}</li>" for item in _evidence_lines(candidate)[:4])
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
        lines.append(f"市场月均销售额：${_number(demand.get('market_avg_monthly_revenue_usd'))}")
    if demand.get("market_avg_price_usd") is not None:
        lines.append(f"市场平均价：${_number(demand.get('market_avg_price_usd'))}")
    if demand.get("top_keyword"):
        keyword_line = f"核心流量词：{demand.get('top_keyword')}"
        if demand.get("top_keyword_monthly_searches") is not None:
            keyword_line += f"（月搜索量 {_number(demand.get('top_keyword_monthly_searches'))}）"
        lines.append(keyword_line)
    if demand.get("aba_top_search_term"):
        lines.append(f"ABA 搜索词：{demand.get('aba_top_search_term')}")
    for key in ("search_signal", "trend_signal", "top100_signal"):
        if demand.get(key):
            lines.append(f"{key}：{demand.get(key)}")
    return [str(item) for item in lines if item not in (None, "")]


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


def _md_cell(value: Any) -> str:
    text = _display_value(value)
    return text.replace("|", "\\|").replace("\n", "<br>")


def _display_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)
