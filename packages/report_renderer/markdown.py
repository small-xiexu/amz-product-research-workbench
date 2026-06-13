"""Markdown 正式报告渲染（12 章）。从 render_report.py R4 抽离，纯移动不改逻辑。"""

from __future__ import annotations

import json
import math
import re
from datetime import datetime
from html import escape

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
    _format_generated_at,
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


def render_markdown(package: dict) -> str:
    meta = package.get("metadata", {})
    currency_code = _site_currency_code(meta.get("site", "US"))
    display_title = _clean_display_title(meta.get("seed_keyword_or_category", "未命名品类"))
    constraints = package.get("constraints", {})
    candidate = package.get("normalized_tables", {}).get("candidate", {})
    market = package.get("market_analysis", {})
    market_structure = package.get("market_structure", {})
    competitors = package.get("competitor_pool", {})
    profit = package.get("profit_reference", {})
    return_risk = package.get("return_risk", {})
    status = package.get("status_card", {})
    voc = package.get("voc_analysis", {})
    decision = package.get("decision_review", {})
    ip_screening = package.get("ip_screening", {})
    compliance = package.get("compliance_screening", {})
    ip_compliance_review = package.get("ip_compliance_review", {})
    competitor_deep_dive = package.get("competitor_deep_dive", [])
    workflow_trace = package.get("workflow_trace", {})
    sorftime_traffic = candidate.get("demand_evidence", {}).get("sorftime_traffic_terms", {})

    lines = [
        f"# {display_title} 调研报告",
        "",
    ]
    sections = (
        (FORMAL_REPORT_SECTION_TITLES[0], _executive_summary_markdown_lines(status, decision, package.get("report_summary", {}), currency_code)),
        (FORMAL_REPORT_SECTION_TITLES[1], _data_source_markdown_lines(meta, package.get("raw_sources", {}), workflow_trace)),
        (FORMAL_REPORT_SECTION_TITLES[2], _candidate_boundary_markdown_lines(meta, constraints, candidate)),
        (FORMAL_REPORT_SECTION_TITLES[3], _market_quality_markdown_lines(market, market_structure, currency_code)),
        (FORMAL_REPORT_SECTION_TITLES[4], _keyword_demand_markdown_lines(candidate, package.get("keyword_analysis", {}))),
        (FORMAL_REPORT_SECTION_TITLES[5], _attribute_analysis_markdown_lines(market_structure, currency_code)),
        (
            FORMAL_REPORT_SECTION_TITLES[6],
            _competitor_selection_markdown_lines(package.get("competitor_selection_logic", []), competitors, competitor_deep_dive, currency_code, sorftime_traffic),
        ),
        (FORMAL_REPORT_SECTION_TITLES[7], _voc_markdown_lines(voc) if voc else _empty_section_lines("评论插件导出未接入，需先补 review_voc_package。")),
        (FORMAL_REPORT_SECTION_TITLES[8], _profit_review_markdown_lines(profit, package.get("operator_inputs", {}), currency_code)),
        (
            FORMAL_REPORT_SECTION_TITLES[9],
            _risk_review_markdown_lines(return_risk, ip_screening, compliance, ip_compliance_review),
        ),
        (FORMAL_REPORT_SECTION_TITLES[10], _go_nogo_markdown_lines(decision, status, currency_code)),
        (FORMAL_REPORT_SECTION_TITLES[11], _next_step_evidence_markdown_lines(status, decision, workflow_trace)),
    )
    for title, body in sections:
        lines.extend(_formal_section(title, body))
    return "\n".join(lines).rstrip() + "\n"


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


def _formal_section(title: str, body: list[str]) -> list[str]:
    lines = [f"## {title}", ""]
    lines.extend(body or ["- 待补", ""])
    if lines[-1] != "":
        lines.append("")
    return lines


def _empty_section_lines(message: str) -> list[str]:
    return [f"- 待补：{message}", ""]


def _executive_summary_markdown_lines(
    status: dict,
    decision: dict,
    report_summary: dict,
    currency_code: str,
) -> list[str]:
    missing_inputs = decision.get("missing_inputs", []) if isinstance(decision, dict) else []
    lines = [
        "### 状态卡",
        f"- 金额口径：统一按 {currency_code} 展示",
        f"- 状态：{status.get('status', '待填') if isinstance(status, dict) else '待填'}",
        f"- 理由：{status.get('reason', '待填') if isinstance(status, dict) else '待填'}",
        f"- 下一步：{status.get('next_step', '待填') if isinstance(status, dict) else '待填'}",
        f"- 待补项：{_join_or_default(missing_inputs[:8], '暂无')}",
        "",
    ]
    bullets = report_summary.get("bullets", []) if isinstance(report_summary, dict) else []
    if bullets:
        lines.extend(["### 摘要要点"])
        for item in bullets[:5]:
            lines.append(f"- {_normalize_money_text(item, currency_code)}")
        lines.append("")
    return lines


def _decision_markdown_lines(decision: dict, currency_code: str = "USD") -> list[str]:
    if not decision:
        return []
    lines: list[str] = []
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


def _data_source_markdown_lines(
    meta: dict,
    raw_sources: dict | None = None,
    workflow_trace: dict | None = None,
) -> list[str]:
    lines = ["### 数据来源说明"]
    sources = meta.get("data_sources", []) if isinstance(meta, dict) else []
    if sources:
        for source in sources:
            lines.append(f"- {source}")
    else:
        lines.append("- 待补：metadata.data_sources 未填写")
    if meta.get("site"):
        lines.append(f"- 站点：{meta.get('site')}")
    if meta.get("generated_at"):
        lines.append(f"- 生成时间：{meta.get('generated_at')}")
    if isinstance(raw_sources, dict) and raw_sources.get("candidate_pool"):
        pool = raw_sources.get("candidate_pool", {})
        lines.append(f"- 候选池：{pool.get('pool_id', '待填')} / {pool.get('candidate_id', '待填')}")
    lines.extend(["", *_workflow_status_markdown_lines(workflow_trace)])
    lines.extend(["", "### Excel 追溯"])
    for section, sheets in REPORT_EXCEL_SHEET_MAP:
        lines.append(f"- {section}：`data.xlsx` -> {sheets}")
    lines.append("")
    return lines


def _status_card_markdown_lines(status: dict, decision: dict) -> list[str]:
    missing_inputs = decision.get("missing_inputs", []) if isinstance(decision, dict) else []
    missing_line = "、".join(str(item) for item in missing_inputs[:8]) or "暂无"
    lines = [
        "## 状态卡",
        "",
        f"- 状态：{status.get('status', '待填') if isinstance(status, dict) else '待填'}",
        f"- 理由：{status.get('reason', '待填') if isinstance(status, dict) else '待填'}",
        f"- 下一步：{status.get('next_step', '待填') if isinstance(status, dict) else '待填'}",
        f"- 待补项：{missing_line}",
        "",
    ]
    return lines


def _candidate_boundary_markdown_lines(meta: dict, constraints: dict, candidate: dict) -> list[str]:
    boundary = candidate.get("candidate_boundary_review", {}) if isinstance(candidate, dict) else {}
    lines = [
        f"- 候选 ID：{meta.get('candidate_id', '待填')}",
        f"- 候选池 ID：{meta.get('candidate_pool_id', '待填')}",
        f"- 关键词/品类：{meta.get('seed_keyword_or_category', '待填')}",
        f"- 产品形态：{meta.get('product_shape', '待填')}",
        f"- 明确禁区：{_join_or_default((constraints or {}).get('exclusion_rules', []), '暂无')}",
        f"- 推荐主线：{boundary.get('recommended_mainline', '待确认')}",
        f"- 校准节点：{boundary.get('checkpoint', '待确认')}",
        "",
    ]
    direction_cards = candidate.get("direction_cards", []) if isinstance(candidate, dict) else []
    if direction_cards:
        lines.append("### 报表后方向卡")
        for item in direction_cards[:6]:
            if not isinstance(item, dict):
                continue
            lines.append(
                f"- {item.get('role', '方向')} / {item.get('status', '待确认')}："
                f"{item.get('name', '待填')}；商品数 {item.get('product_count', '待填')}；"
                f"月销量 {_format_number(item.get('total_monthly_units')) if item.get('total_monthly_units') is not None else '待填'}"
            )
        lines.append("")
    return lines


def _market_quality_markdown_lines(market: dict, market_structure: dict, currency_code: str) -> list[str]:
    lines = [
        f"- 市场规模：{_normalize_money_text(market.get('market_size', '待填'), currency_code)}",
        f"- 价格带：{_normalize_money_text(market.get('price_band', '待填'), currency_code)}",
        f"- 品牌集中度：{market.get('brand_concentration', '待填')}",
        f"- 卖家结构：{market.get('seller_concentration', '待填')}",
        f"- 新品机会：{market.get('new_listing_ratio', '待填')}",
        f"- 退货率：{market.get('return_rate', '待填')}",
        "",
    ]
    category_report = market.get("sorftime_category_report", {}) if isinstance(market, dict) else {}
    if isinstance(category_report, dict) and category_report:
        lines.extend(
            [
                "### Sorftime category_report 快照",
                f"- 类目：{category_report.get('category_name', '待填')} / nodeId {category_report.get('node_id', '待填')}",
                f"- Top 样本数：{category_report.get('product_count', '待填')}",
                f"- 总月销量：{_format_number(category_report.get('total_monthly_units')) if category_report.get('total_monthly_units') is not None else '待填'}",
                f"- 均价：{_format_money(category_report.get('avg_price_usd'), currency_code) if category_report.get('avg_price_usd') is not None else '待填'}",
                f"- Top10 销量占比：{_format_percent_or_text(category_report.get('top10_units_share', '待填'))}",
                f"- 近半年新品：{category_report.get('new_product_count_6m', '待填')} 个，销量占比 {_format_percent_or_text(category_report.get('new_product_units_share', '待填'))}",
                "",
            ]
        )
    lines.extend(_market_structure_markdown_lines(market_structure))
    return lines


def _market_structure_markdown_lines(market_structure: dict) -> list[str]:
    if not market_structure:
        return []
    summary = market_structure.get("summary", {})
    quality = market_structure.get("data_quality", {})
    distributions = market_structure.get("attribute_distributions", [])
    cross_analysis = market_structure.get("cross_analysis", [])
    lines = ["### 数据质量"]
    if summary.get("quality_summary"):
        lines.append(f"- {summary.get('quality_summary')}")
    if summary.get("dominant_structure"):
        lines.append(f"- 结构特征：{summary.get('dominant_structure')}")
    if quality.get("warnings"):
        for warning in quality.get("warnings", [])[:5]:
            lines.append(f"- 提醒：{warning}")
    lines.append("")
    if distributions:
        lines.append("### 属性结构概览")
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


def _keyword_demand_markdown_lines(candidate: dict, keyword_analysis: dict) -> list[str]:
    demand = candidate.get("demand_evidence", {}) if isinstance(candidate, dict) else {}
    aba_signal = demand.get("aba_keyword_signal", {}) if isinstance(demand, dict) else {}
    lines = [
        f"- 卖家精灵核心词：{demand.get('top_keyword', '待填')}",
        f"- 核心词月搜索量：{_format_number(demand.get('top_keyword_monthly_searches')) if demand.get('top_keyword_monthly_searches') is not None else '待填'}",
        f"- 搜索信号：{keyword_analysis.get('search_signal', demand.get('search_signal', '待填'))}",
        f"- 趋势信号：{keyword_analysis.get('trend_signal', demand.get('trend_signal', '待填'))}",
        f"- ABA 核心词：{demand.get('aba_top_search_term') or '待填'}",
        f"- ABA 点击 ASIN：{demand.get('aba_top_clicked_asin') or '待填'}",
        "",
    ]
    target_keywords = aba_signal.get("target_keywords", []) if isinstance(aba_signal, dict) else []
    top_keywords = target_keywords or (aba_signal.get("top_keywords", []) if isinstance(aba_signal, dict) else [])
    if top_keywords:
        lines.append("### ABA/关键词线索")
        for item in top_keywords[:8]:
            lines.append(
                f"- {item.get('keyword', '待填')}：月搜 {_format_number(item.get('monthly_searches'))}；"
                f"点击 { _format_number(item.get('clicks')) if item.get('clicks') is not None else '待填'}；"
                f"PPC {item.get('ppc_usd', '待填')}；意图 {item.get('intent', '待确认')}"
            )
        lines.append("")
    return lines


def _attribute_analysis_markdown_lines(market_structure: dict, currency_code: str) -> list[str]:
    definitions = market_structure.get("attribute_definitions", []) if isinstance(market_structure, dict) else []
    distributions = market_structure.get("attribute_distributions", []) if isinstance(market_structure, dict) else []
    cross_analysis = market_structure.get("cross_analysis", []) if isinstance(market_structure, dict) else []
    pending_labels = market_structure.get("pending_label_items", []) if isinstance(market_structure, dict) else []
    opportunity_judgments = market_structure.get("opportunity_judgments", []) if isinstance(market_structure, dict) else []
    summary = market_structure.get("summary", {}) if isinstance(market_structure, dict) else {}
    lines: list[str] = []
    if definitions:
        lines.append("### 属性定义")
        for item in definitions[:8]:
            lines.append(f"- {item.get('label', item.get('dimension', '维度'))}：{item.get('rule', '待填')}")
        lines.append("")
    if distributions:
        lines.append("### 属性分布")
        for item in distributions[:8]:
            lines.append(f"- {item.get('label', item.get('dimension', '维度'))}：{item.get('summary', '待填')}")
        lines.append("")
    if cross_analysis:
        lines.append("### 属性交叉分析")
        for item in cross_analysis[:6]:
            lines.append(f"- {item.get('label', '交叉维度')}：{item.get('summary', '待填')}")
        lines.append("")
    if opportunity_judgments:
        lines.append("### 机会判断")
        if summary.get("opportunity_judgment_summary"):
            lines.append(f"- 汇总：{summary.get('opportunity_judgment_summary')}")
        for item in opportunity_judgments[:8]:
            lines.append(
                f"- {item.get('opportunity_type', '待验证')}：{item.get('cross_dimension', '交叉维度')} / "
                f"{item.get('combination', '组合待填')}；均销量 {_format_number(item.get('avg_monthly_units'))}；"
                f"下一步：{item.get('next_check', '待验证')}"
            )
        lines.append("")
    if pending_labels:
        lines.append("### 待确认标签")
        lines.append(f"- 待运营复核商品数：{len(pending_labels)}")
        for item in pending_labels[:8]:
            lines.append(
                f"- {item.get('asin', '待填')}：路线 {item.get('product_route', '待确认')}；"
                f"置信度 {item.get('tag_confidence', '待确认')}；{_compact_title(item.get('title'), 48)}"
            )
        lines.append("")
    return lines or _empty_section_lines("属性分布和交叉分析未生成。")


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


def _profit_review_markdown_lines(profit: dict, operator_inputs: dict, currency_code: str) -> list[str]:
    lines = [
        f"- 基础 FBA 毛利：{_format_money(profit.get('base_fba_gross_profit', '待填'), currency_code)}",
        f"- 基础 FBA 毛利率：{_format_percent_or_text(profit.get('base_fba_margin', '待填'))}",
        f"- 扣广告和退货后的 FBA 毛利：{_format_money(profit.get('post_ads_returns_gross_profit', '待填'), currency_code)}",
        f"- 扣广告和退货后的 FBA 毛利率：{_format_percent_or_text(profit.get('post_ads_returns_margin', '待填'))}",
        "",
    ]
    missing_inputs = [
        label
        for key, label in (
            ("purchase_cost", "采购价"),
            ("exchange_rate", "站点汇率"),
            ("fba_fee", "FBA费用"),
            ("first_leg_shipping", "头程费用"),
            ("inbound_placement_fee", "入库配置费"),
        )
        if str(operator_inputs.get(key, "待补")) in {"", "待补", "待填", "None"}
    ]
    lines.append(f"- 利润待补：{_join_or_default(missing_inputs, '暂无')}")
    lines.append("")
    supply_chain = profit.get("supply_chain_signal", {}) if isinstance(profit, dict) else {}
    if isinstance(supply_chain, dict) and supply_chain:
        lines.extend(
            [
                "### 1688 粗估 COGS 信号",
                f"- 搜索词：{supply_chain.get('search_name', '待填')}",
                f"- 供应商样本：{supply_chain.get('supplier_count', '待填')}",
                f"- 采购价区间：RMB {supply_chain.get('purchase_price_cny_min', '待填')} - {supply_chain.get('purchase_price_cny_max', '待填')}",
                f"- 折美元均价：{_format_money(supply_chain.get('purchase_price_usd_avg'), currency_code) if supply_chain.get('purchase_price_usd_avg') is not None else '待汇率'}",
                f"- 口径：{supply_chain.get('note', '只作早期粗估，不替代运营利润模板。')}",
                "",
            ]
        )
    lines.extend(_profit_breakdown_markdown_lines(profit))
    return lines


def _risk_review_markdown_lines(return_risk: dict, ip_screening: dict, compliance: dict, review: dict) -> list[str]:
    lines = [
        "### 退货风险",
        f"- 来源：{return_risk.get('source', '待填') if isinstance(return_risk, dict) else '待填'}",
        f"- 等级：{return_risk.get('level', '待确认') if isinstance(return_risk, dict) else '待确认'}",
        f"- 市场退货率：{_format_percent_or_text(return_risk.get('market_return_rate', '待填')) if isinstance(return_risk, dict) else '待填'}",
        "",
    ]
    lines.extend(_ip_compliance_markdown_lines(ip_screening, compliance, review))
    return lines


def _competitor_selection_markdown_lines(selection_logic: object, competitors: dict, cards: list, currency_code: str, sorftime_traffic: dict | None = None) -> list[str]:
    total_count = 0
    if isinstance(competitors, dict):
        total_count = sum(len(competitors.get(key, []) or []) for key in ("top10", "recent_winners", "structure_supplement"))
    selection_rows = selection_logic if isinstance(selection_logic, list) else []
    covered_types = sorted(
        {
            str(item.get("competitor_type"))
            for item in selection_rows
            if isinstance(item, dict) and item.get("competitor_type")
        }
    )
    lines = [
        f"- 竞品池覆盖数量：{total_count}",
        "- 选择逻辑：优先覆盖 Top10 标杆、近半年放量新品、结构补充样本和价格/功能差异样本。",
        "- 证据口径：每个竞品行应回到 `data.xlsx` 的 `竞品池` 与 `竞品深拆卡` Sheet 核对。",
        f"- VOC 推荐抓取覆盖角色：{_join_or_default(covered_types, '待补')}",
        "",
    ]
    if selection_rows:
        lines.append("### 竞品选择逻辑表")
        for item in selection_rows[:12]:
            if not isinstance(item, dict):
                continue
            lines.append(
                f"- {item.get('asin', '待填')} / {item.get('brand', '待填')} / {item.get('competitor_type', '待填')}："
                f"{_compact_title(item.get('title'), 48)}；"
                f"价格 {_format_money(item.get('price_usd'), currency_code)}；"
                f"月销量 {_format_number(item.get('monthly_units'))}；"
                f"评分 {item.get('rating', '待填')}（{_format_number(item.get('rating_count'))}）；"
                f"理由：{item.get('selection_reason', '待填')}"
            )
        lines.append("")
    lines.extend(_competitor_markdown_lines(competitors, currency_code))
    lines.extend(_competitor_deep_dive_markdown_lines(cards, currency_code, sorftime_traffic))
    return lines


def _go_nogo_markdown_lines(decision: dict, status: dict, currency_code: str) -> list[str]:
    scorecard = decision.get("go_nogo_scorecard", {}) if isinstance(decision, dict) else {}
    lines = [
        "### 状态卡",
        f"- 当前状态：{status.get('status', '待填') if isinstance(status, dict) else '待填'}",
        f"- 状态理由：{status.get('reason', '待填') if isinstance(status, dict) else '待填'}",
        f"- 下一步：{status.get('next_step', '待填') if isinstance(status, dict) else '待填'}",
        "",
    ]
    if scorecard:
        lines.append("### Go/Wait/No-Go 评分卡")
        if scorecard.get("gating_reasons"):
            lines.append(f"- 决策限制：{_join_or_default(scorecard.get('gating_reasons'), '无')}")
        for name, item in scorecard.get("dimensions", {}).items():
            score = item.get("score", "待填")
            weight = item.get("weight", "待填")
            weight_text = f"{weight * 100:.0f}%" if isinstance(weight, (int, float)) else str(weight)
            lines.append(f"- {name}：{score}/10，权重 {weight_text}；依据：{item.get('note', '待填')}")
        lines.append(f"- 加权总分：{scorecard.get('weighted_score', '待填')}")
        lines.append(f"- 决策结论：{scorecard.get('decision', '待填')}")
        if scorecard.get("note"):
            lines.append(f"- 说明：{scorecard.get('note')}")
        lines.append("")
    lines.extend(_decision_markdown_lines(decision, currency_code))
    return lines


def _next_step_evidence_markdown_lines(status: dict, decision: dict, workflow_trace: dict | None = None) -> list[str]:
    actions = decision.get("action_items", []) if isinstance(decision, dict) else []
    missing_inputs = decision.get("missing_inputs", []) if isinstance(decision, dict) else []
    lines = [
        f"- 下一步：{status.get('next_step', '待填') if isinstance(status, dict) else '待填'}",
        f"- 待补项：{_join_or_default(missing_inputs[:12], '暂无')}",
        "",
        "### 动作清单",
    ]
    if actions:
        for item in actions[:10]:
            lines.append(f"- {item}")
    else:
        lines.append("- 待 Claude 结合当前数据补充具体动作。")
    workflow_lines = _workflow_decision_markdown_lines(workflow_trace)
    if workflow_lines:
        lines.extend(["", *workflow_lines])
    lines.extend(["", "### 证据附录"])
    for section, sheets in REPORT_EXCEL_SHEET_MAP:
        lines.append(f"- {section}：`data.xlsx` -> {sheets}")
    lines.append("- 运行摘要：`workflow_summary.md` / `workflow_summary.json`")
    lines.append("")
    return lines


def _ip_compliance_markdown_lines(ip_screening: dict, compliance: dict, review: dict) -> list[str]:
    if not ip_screening and not compliance and not review:
        return []
    lines = ["### 知产/合规初筛", ""]
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


def _voc_markdown_lines(voc: dict) -> list[str]:
    summary = voc.get("summary", {})
    lines = [
        "### 评论 VOC 摘要",
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


def _workflow_status_markdown_lines(workflow_trace: dict | None) -> list[str]:
    trace = workflow_trace if isinstance(workflow_trace, dict) else {}
    state = trace.get("workflow_state", {}) if isinstance(trace, dict) else {}
    if not isinstance(state, dict) or not state:
        return [
            "### 交互式流程状态",
            "- 未接入 workflow_state：本报告仅体现当前批处理数据结果，交互过程待补。",
        ]

    lines = [
        "### 交互式流程状态",
        f"- 流程 ID：{state.get('workflow_id', '待填')}",
        f"- 模式：{state.get('mode', '待填')}",
        f"- 当前阶段：{state.get('stage', '待填')}",
        f"- 初始意图：{state.get('initial_intent', '待填')}",
        f"- 站点：{state.get('site', '待填')}",
        f"- 是否等待运营决策：{'是' if state.get('decision_required') else '否'}",
    ]
    if state.get("operator_question"):
        lines.append(f"- 当前要问运营的问题：{state.get('operator_question')}")
    missing_inputs = state.get("missing_inputs", [])
    if missing_inputs:
        lines.append(f"- 交互流程待补：{_join_or_default(missing_inputs[:10], '暂无')}")
    if state.get("updated_at"):
        lines.append(f"- 状态更新时间：{state.get('updated_at')}")
    if trace.get("source_file"):
        lines.append(f"- 状态来源文件：`{trace.get('source_file')}`")
    return lines


def _workflow_decision_markdown_lines(workflow_trace: dict | None) -> list[str]:
    trace = workflow_trace if isinstance(workflow_trace, dict) else {}
    state = trace.get("workflow_state", {}) if isinstance(trace, dict) else {}
    if not isinstance(state, dict) or not state:
        return []

    lines: list[str] = ["### 交互式下一步动作"]
    next_actions = trace.get("next_actions") or state.get("next_actions", [])
    if isinstance(next_actions, list) and next_actions:
        for action in next_actions[:5]:
            if not isinstance(action, dict):
                continue
            recommended = action.get("recommended_action", {}) if isinstance(action.get("recommended_action"), dict) else {}
            lines.append(
                f"- {action.get('stage', state.get('stage', '待填'))}：{recommended.get('label', '待填')}；"
                f"类型 {recommended.get('type', '待填')}；原因：{recommended.get('reason', '待填')}"
            )
            if action.get("question"):
                lines.append(f"  - 运营问题：{action.get('question')}")
            options = action.get("options", [])
            if isinstance(options, list) and options:
                option_text = "；".join(
                    str(option.get("label", "")).strip()
                    for option in options[:4]
                    if isinstance(option, dict) and str(option.get("label", "")).strip()
                )
                if option_text:
                    lines.append(f"  - 可选动作：{option_text}")
    else:
        lines.append("- 暂无下一步动作卡。")

    decisions = trace.get("decision_log") or state.get("decision_log", [])
    lines.extend(["", "### 关键决策记录"])
    if isinstance(decisions, list) and decisions:
        for item in decisions[:10]:
            if not isinstance(item, dict):
                continue
            evidence_text = _format_evidence_refs(item.get("evidence_refs", []))
            suffix = f"（证据：{evidence_text}）" if evidence_text else ""
            lines.append(
                f"- {item.get('stage', '待填')} / {item.get('actor', '待填')}："
                f"{item.get('decision', '待填')}；理由：{item.get('rationale', '待填')}{suffix}"
            )
    else:
        lines.append("- 暂无运营/AI 决策记录。")
    return lines


def _competitor_markdown_lines(competitors: dict, currency_code: str = "USD") -> list[str]:
    if not competitors:
        return []
    groups = [
        ("top10", "Top10 标杆组"),
        ("recent_winners", "近半年放量新品组"),
        ("structure_supplement", "结构补充组"),
    ]
    lines = ["### 竞品池", ""]
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


def _competitor_deep_dive_markdown_lines(cards: list, currency_code: str = "USD", sorftime_traffic: dict | None = None) -> list[str]:
    if not cards:
        return []
    traffic_asin = (sorftime_traffic or {}).get("asin", "")
    lines = ["", "### 重点竞品数据", ""]
    for card in cards:
        asin = card.get("asin", "")
        title = _compact_title(card.get("title"), 60)
        card_type = card.get("card_type", "")
        price = card.get("price_usd")
        units = card.get("monthly_units")
        rating = card.get("rating")
        rating_count = card.get("rating_count")
        listing_days = card.get("listing_days")
        if sorftime_traffic and asin == traffic_asin:
            top_words = sorftime_traffic.get("top_traffic_words", [])
            mixed_warnings = sorftime_traffic.get("mixed_pool_warning", [])
            word_parts = [
                f"{w.get('keyword')}（{_format_number(w.get('monthly_search', 0))}搜/月，{w.get('position', '—')}）"
                for w in top_words[:6]
            ]
            traffic_line = "；".join(word_parts) if word_parts else "暂无数据"
            if mixed_warnings:
                warn_kws = "、".join(w.get("keyword", "") for w in mixed_warnings[:3])
                traffic_line += f"⚠️ 混池词：{warn_kws}"
        else:
            traffic_line = "待 Sorftime product_traffic_terms 补充"
        lines += [
            f"### {card_type}：{asin}",
            f"- 标题：{title}",
            f"- 价格：{_format_money(price, currency_code)}　月销量：{_format_number(units)}　评分：{rating}（{_format_number(rating_count)} 条）　上架天数：{listing_days or '待补'}",
            f"- 流量词：{traffic_line}",
            "",
        ]
    return lines
