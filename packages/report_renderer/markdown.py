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
    _polish_punctuation,
)


ANALYSIS_MODE_SELF_CHECKS = (
    ("数据 -> 空白 -> 机会", "市场结构与数据质量 / 产品属性分布与交叉分析", ("空白", "机会")),
    ("痛点 -> 产品方案", "评论 VOC 与真实痛点", ("痛点", "产品方案", "规格")),
    ("交叉维度 -> 结构性空白", "产品属性分布与交叉分析", ("交叉", "结构")),
    ("多维评分 -> 优先级矩阵", "Go/Wait/No-Go 决策检查", ("评分卡", "优先级", "加权")),
    ("待补项 -> 验证动作", "下一步动作与证据附录", ("待补", "验证", "复核")),
    ("竞品角色 -> VOC 证据链", "竞品池与竞品选择逻辑 / 评论 VOC 与真实痛点", ("竞品", "VOC", "证据")),
    ("数据点 -> 含义 -> 行动建议", "Executive Summary / 当前结论", ("数据点", "含义", "行动建议")),
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
    return_risk = package.get("return_risk", {})
    status = package.get("status_card", {})
    voc = package.get("voc_analysis", {})
    decision = package.get("decision_review", {})
    competitor_deep_dive = package.get("competitor_deep_dive", [])
    workflow_trace = package.get("workflow_trace", {})
    sorftime_traffic = candidate.get("demand_evidence", {}).get("sorftime_traffic_terms", {})

    lines = [
        f"# {display_title} 调研报告",
        "",
    ]
    sections = (
        (FORMAL_REPORT_SECTION_TITLES[0], _executive_summary_markdown_lines(status, decision, package.get("report_summary", {}), currency_code, package.get("ai_analysis", {}))),
        (FORMAL_REPORT_SECTION_TITLES[1], _data_source_markdown_lines(meta, package.get("raw_sources", {}), workflow_trace)),
        (FORMAL_REPORT_SECTION_TITLES[2], _category_selection_derivation_markdown_lines(package, candidate, workflow_trace)),
        (FORMAL_REPORT_SECTION_TITLES[3], _candidate_boundary_markdown_lines(meta, constraints, candidate)),
        (FORMAL_REPORT_SECTION_TITLES[4], _market_quality_markdown_lines(market, market_structure, currency_code)),
        (FORMAL_REPORT_SECTION_TITLES[5], _keyword_demand_markdown_lines(candidate, package.get("keyword_analysis", {}))),
        (FORMAL_REPORT_SECTION_TITLES[6], _attribute_analysis_markdown_lines(market_structure, currency_code)),
        (
            FORMAL_REPORT_SECTION_TITLES[7],
            _competitor_selection_markdown_lines(package.get("competitor_selection_logic", []), competitors, competitor_deep_dive, currency_code, sorftime_traffic),
        ),
        (FORMAL_REPORT_SECTION_TITLES[8], _voc_markdown_lines(voc) if voc else _empty_section_lines("评论插件导出未接入，需先补 review_voc_package。")),
        (FORMAL_REPORT_SECTION_TITLES[9], _market_opportunity_score_markdown_lines(decision, status, currency_code)),
        (FORMAL_REPORT_SECTION_TITLES[10], _risk_review_markdown_lines(return_risk, decision)),
        (FORMAL_REPORT_SECTION_TITLES[11], _research_priority_markdown_lines(decision, status, currency_code)),
        (FORMAL_REPORT_SECTION_TITLES[12], _next_step_evidence_markdown_lines(status, decision, workflow_trace)),
    )
    for title, body in sections:
        lines.extend(_formal_section(title, body))
    return _polish_punctuation("\n".join(lines)).rstrip() + "\n"


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
    ai_analysis: dict | None = None,
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
    bullets = [item for item in (report_summary.get("bullets", []) if isinstance(report_summary, dict) else []) if item]
    if bullets:
        lines.extend(["### 摘要要点"])
        for item in bullets[:5]:
            lines.append(f"- {_normalize_money_text(item, currency_code)}")
        lines.append("")
    lines.extend(_executive_chain_markdown_lines(status, decision, report_summary, ai_analysis, currency_code))
    if isinstance(ai_analysis, dict) and ai_analysis:
        thesis = ai_analysis.get("thesis", {}) if isinstance(ai_analysis.get("thesis"), dict) else {}
        lines.extend(
            [
                "### AI 综合分析口径",
                f"- 角色前提：{ai_analysis.get('persona', '资深亚马逊运营专家')}",
                f"- 判断原则：{ai_analysis.get('decision_principle', '本报告只判断市场机会和继续研究优先级，不输出采购或上架结论。')}",
                f"- 综合判断：{thesis.get('title', '待补')}",
                "",
            ]
        )
        route_lines = _product_route_matrix_markdown_lines(ai_analysis.get("product_route_matrix", []))
        if route_lines:
            lines.extend(route_lines)
        route_plan_lines = _route_deep_dive_plan_markdown_lines(ai_analysis.get("route_deep_dive_plan", []))
        if route_plan_lines:
            lines.extend(route_plan_lines)
    return lines


def _executive_chain_markdown_lines(
    status: dict,
    decision: dict,
    report_summary: dict,
    ai_analysis: dict | None,
    currency_code: str,
) -> list[str]:
    chains: list[str] = []
    scorecard = decision.get("go_nogo_scorecard", {}) if isinstance(decision, dict) else {}
    dimensions = scorecard.get("dimensions", {}) if isinstance(scorecard.get("dimensions"), dict) else {}
    if isinstance(scorecard, dict) and scorecard.get("decision"):
        chains.append(
            f"数据点：市场机会评分 {scorecard.get('weighted_score', '待补')}，结论 {scorecard.get('decision')} -> "
            f"含义：当前决策受市场、关键词、竞品和 VOC 证据约束 -> "
            f"行动建议：先补齐评分卡限制项再决定是否继续深挖。"
        )
    for name, item in list(dimensions.items())[:2]:
        if not isinstance(item, dict):
            continue
        chains.append(
            f"数据点：{name} 得分 {item.get('score', '待补')}，依据 {item.get('note', '待补')} -> "
            f"含义：该维度会影响进入优先级和风险边界 -> "
            f"行动建议：围绕该维度补充可回表证据。"
        )
    if isinstance(ai_analysis, dict):
        insights = ai_analysis.get("insights") if isinstance(ai_analysis.get("insights"), list) else []
        for insight in insights[:3]:
            if not isinstance(insight, dict):
                continue
            chains.append(
                f"数据点：{insight.get('label', '关键洞察')}，{_normalize_money_text(insight.get('body', '待补'), currency_code)} -> "
                f"含义：{insight.get('title', '需要转成进入策略判断')} -> "
                f"行动建议：把该洞察转成下一步补数、路线验证或 VOC 检查。"
            )
            if len(chains) >= 3:
                break
    bullets = [item for item in (report_summary.get("bullets", []) if isinstance(report_summary, dict) else []) if item]
    for item in bullets:
        chains.append(
            f"数据点：{_normalize_money_text(item, currency_code)} -> "
            "含义：该证据影响当前候选方向判断 -> "
            "行动建议：用下一步动作继续验证。"
        )
        if len(chains) >= 3:
            break
    while len(chains) < 3:
        chains.append(
            f"数据点：状态 {status.get('status', '待填') if isinstance(status, dict) else '待填'} -> "
            "含义：当前结论仍依赖待补证据 -> "
            "行动建议：优先补齐小类、关键词、竞品或 VOC 证据。"
        )
    return ["### 数据点 -> 含义 -> 行动建议", *[f"- {item}" for item in chains[:3]], ""]


def _product_route_matrix_markdown_lines(routes: object) -> list[str]:
    if not isinstance(routes, list) or not routes:
        return []
    lines = ["### 产品路线矩阵"]
    for route in routes:
        if not isinstance(route, dict):
            continue
        lines.append(
            f"- {route.get('route_name', '未命名路线')}：{route.get('route_type', '路线')}，"
            f"{route.get('candidate_count', 0)} 个候选，"
            f"优先 {route.get('priority_count', 0)}，观察 {route.get('watchlist_count', 0)}，"
            f"价格 {route.get('price_text', '价格带待补')}。"
            f"{route.get('decision_hint', '')}"
        )
    lines.append("")
    return lines


def _route_deep_dive_plan_markdown_lines(plan: object) -> list[str]:
    if not isinstance(plan, list) or not plan:
        return []
    lines = ["### 路线级小深挖计划"]
    for item in plan:
        if not isinstance(item, dict):
            continue
        coverage = item.get("review_coverage") if isinstance(item.get("review_coverage"), dict) else {}
        asins = item.get("review_voc_asin_plan") if isinstance(item.get("review_voc_asin_plan"), list) else []
        asin_text = "、".join(
            str(asin.get("asin"))
            for asin in asins[:4]
            if isinstance(asin, dict) and asin.get("asin")
        ) or "待补路线专属 ASIN"
        gaps = item.get("data_gaps") if isinstance(item.get("data_gaps"), list) else []
        lines.append(
            f"- {item.get('route_name', '未命名路线')}：{item.get('recommended_depth', '路线小深挖')}；"
            f"当前证据 {item.get('current_evidence_level', '待补')}；"
            f"评价粗匹配 {coverage.get('matched_review_count', 0)} 条；"
            f"建议 ASIN：{asin_text}；"
            f"下一步：{item.get('next_step') or (gaps[0] if gaps else '补路线专属数据')}。"
        )
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
    if isinstance(raw_sources, dict) and raw_sources.get("candidate_pool"):
        pool = raw_sources.get("candidate_pool", {})
        lines.append(f"- 候选池：{pool.get('pool_id', '待填')} / {pool.get('candidate_id', '待填')}")
    lines.extend(["", *_workflow_status_markdown_lines(workflow_trace)])
    lines.extend(["", "### Excel 追溯"])
    for section, sheets in REPORT_EXCEL_SHEET_MAP:
        lines.append(f"- {section}：`data.xlsx` -> {sheets}")
    lines.append("")
    return lines


def _category_selection_derivation_markdown_lines(
    package: dict,
    candidate: dict,
    workflow_trace: dict | None = None,
) -> list[str]:
    derivation = package.get("category_selection_derivation")
    if not isinstance(derivation, dict):
        derivation = (package.get("ai_analysis") or {}).get("category_selection_derivation") if isinstance(package.get("ai_analysis"), dict) else {}
    if not isinstance(derivation, dict):
        derivation = {}

    steps = derivation.get("steps") if isinstance(derivation.get("steps"), list) else []
    rejected = derivation.get("rejected_alternatives") if isinstance(derivation.get("rejected_alternatives"), list) else []
    source_refs = derivation.get("source_refs") if isinstance(derivation.get("source_refs"), list) else []
    confidence = derivation.get("confidence") or "待补"

    lines = [
        "### 为什么是这个品类",
        f"- 收敛结论：{derivation.get('selected_category') or derivation.get('selected_route') or _fallback_selected_category(candidate)}",
        f"- 证据强度：{confidence}",
        f"- 核心原则：先从约束和场景出发，再用类目、参考 ASIN、关键词、混池排除和多源交叉验证逐步收敛；不把单个大词或单个工具返回当最终市场。",
        "",
        "### 推导步骤",
    ]
    if steps:
        for index, step in enumerate(steps[:10], start=1):
            if not isinstance(step, dict):
                continue
            evidence = _join_or_default(step.get("evidence") if isinstance(step.get("evidence"), list) else [step.get("evidence")], "证据待补")
            implication = step.get("implication") or step.get("read") or "待解释"
            decision = step.get("decision") or step.get("action") or "继续验证"
            lines.append(
                f"{index}. {step.get('name') or step.get('step') or '推导节点'}："
                f"证据：{evidence}；含义：{implication}；动作：{decision}。"
            )
            for point in step.get("evidence_points", []) if isinstance(step.get("evidence_points"), list) else []:
                if not isinstance(point, dict):
                    continue
                lines.append(
                    f"   - 事实：{point.get('fact', '待补')}；"
                    f"含义：{point.get('meaning', '待解释')}；"
                    f"行动建议：{point.get('action', '继续验证')}"
                )
    else:
        lines.extend(_fallback_category_derivation_steps(candidate, workflow_trace))
    lines.append("")

    if rejected:
        lines.append("### 为什么没有选其他方向")
        for item in rejected[:8]:
            if not isinstance(item, dict):
                continue
            lines.append(
                f"- {item.get('name') or item.get('route') or item.get('keyword') or '候选项'}："
                f"{item.get('reason') or item.get('decision') or '证据不足或混池风险高'}"
            )
        lines.append("")

    disconfirming = derivation.get("disconfirming_evidence") if isinstance(derivation.get("disconfirming_evidence"), list) else []
    if disconfirming:
        lines.append("### 什么证据会推翻当前判断")
        for item in disconfirming[:8]:
            if not isinstance(item, dict):
                continue
            lines.append(
                f"- {item.get('risk', '风险')}：若 {item.get('would_change_decision_if', '出现反证')}，"
                f"则需要 {item.get('next_check', '重新验证')}；当前信号：{item.get('current_signal', '待补')}"
            )
        lines.append("")

    if source_refs:
        lines.append("### 主要证据来源")
        for ref in source_refs[:10]:
            lines.append(f"- {ref}")
        lines.append("")
    return lines


def _fallback_selected_category(candidate: dict) -> str:
    if not isinstance(candidate, dict):
        return "待确认"
    boundary = candidate.get("candidate_boundary_review") if isinstance(candidate.get("candidate_boundary_review"), dict) else {}
    return str(boundary.get("recommended_mainline") or candidate.get("name") or candidate.get("candidate_id") or "待确认")


def _fallback_category_derivation_steps(candidate: dict, workflow_trace: dict | None) -> list[str]:
    lines: list[str] = []
    boundary = candidate.get("candidate_boundary_review") if isinstance(candidate, dict) and isinstance(candidate.get("candidate_boundary_review"), dict) else {}
    demand = candidate.get("demand_evidence") if isinstance(candidate, dict) and isinstance(candidate.get("demand_evidence"), dict) else {}
    category_report = demand.get("sorftime_category_report") if isinstance(demand.get("sorftime_category_report"), dict) else {}
    top_asins = candidate.get("next_review_voc_asins") if isinstance(candidate, dict) and isinstance(candidate.get("next_review_voc_asins"), list) else []
    keywords = (demand.get("aba_keyword_signal") or {}).get("top_keywords") if isinstance(demand.get("aba_keyword_signal"), dict) else []
    decision_log = workflow_trace.get("decision_log") if isinstance(workflow_trace, dict) and isinstance(workflow_trace.get("decision_log"), list) else []

    if decision_log:
        first = decision_log[0] if isinstance(decision_log[0], dict) else {}
        lines.append(f"1. 初始约束：证据：{first.get('reason', '用户输入和流程决策记录')}；含义：先限定站点、场景、禁区和偏好；动作：只保留符合边界的候选方向。")
    else:
        lines.append("1. 初始约束：证据：用户输入、站点、场景、禁区和价格偏好；含义：先限定可研究范围；动作：排除明显不符合边界的候选。")
    lines.append(
        f"2. 类目候选：证据：{category_report.get('category_name') or category_report.get('node_id') or '候选类目与类目报告待补'}；"
        "含义：关键词映射只能作为候选，需要类目和 ASIN 共同确认；动作：保留候选类目并标记混池风险。"
    )
    lines.append(
        f"3. 参考竞品：证据：已选 {len(top_asins)} 个代表 ASIN；"
        "含义：只有相似 ASIN 能支撑这个方向不是抽象词；动作：按主线、升级、新品、痛点、对照覆盖竞品池。"
    )
    lines.append(
        f"4. 关键词交叉：证据：关键词样本 {len(keywords) if isinstance(keywords, list) else 0} 条；"
        "含义：搜索词用于验证需求和混池，不直接定义市场；动作：拆分主词、转化词、长尾词和排除词。"
    )
    lines.append(
        f"5. 最终收敛：证据：{boundary.get('recommended_mainline') or '路线矩阵和候选边界'}；"
        "含义：选择证据最完整且边界可解释的主线；动作：进入 VOC、关键词和竞品证据验证。"
    )
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


def _market_opportunity_score_markdown_lines(decision: dict, status: dict, currency_code: str) -> list[str]:
    scorecard = decision.get("go_nogo_scorecard", {}) if isinstance(decision, dict) else {}
    lines = [
        "### 市场机会评分卡",
        f"- 当前状态：{status.get('status', '待填') if isinstance(status, dict) else '待填'}",
        f"- 状态理由：{status.get('reason', '待填') if isinstance(status, dict) else '待填'}",
        f"- 下一步：{status.get('next_step', '待填') if isinstance(status, dict) else '待填'}",
        "",
    ]
    if scorecard:
        if scorecard.get("gating_reasons"):
            lines.append(f"- 证据缺口：{_join_or_default(scorecard.get('gating_reasons'), '无')}")
        for name, item in scorecard.get("dimensions", {}).items():
            score = item.get("score", "待填")
            weight = item.get("weight", "待填")
            weight_text = f"{weight * 100:.0f}%" if isinstance(weight, (int, float)) else str(weight)
            lines.append(f"- {name}：{score}/10，权重 {weight_text}；依据：{item.get('note', '待填')}")
        lines.append(f"- 加权总分：{scorecard.get('weighted_score', '待填')}")
        lines.append(f"- 研究结论：{scorecard.get('decision', '待填')}")
        if scorecard.get("note"):
            lines.append(f"- 说明：{scorecard.get('note')}")
        lines.append("")
    return lines


def _risk_review_markdown_lines(return_risk: dict, decision: dict) -> list[str]:
    lines = [
        "### 退货风险",
        f"- 来源：{return_risk.get('source', '待填') if isinstance(return_risk, dict) else '待填'}",
        f"- 等级：{return_risk.get('level', '待确认') if isinstance(return_risk, dict) else '待确认'}",
        f"- 市场退货率：{_format_percent_or_text(return_risk.get('market_return_rate', '待填')) if isinstance(return_risk, dict) else '待填'}",
        "",
    ]
    risks = decision.get("risk_matrix", []) if isinstance(decision, dict) else []
    if risks:
        lines.append("### 待验证风险")
        for item in risks[:8]:
            if not isinstance(item, dict):
                continue
            lines.append(f"- {item.get('dimension', '风险项')}：{item.get('level', '待确认')}；{item.get('basis', '待补')}")
        lines.append("")
    return lines


def _competitor_selection_markdown_lines(selection_logic: object, competitors: dict, cards: list, currency_code: str, sorftime_traffic: dict | None = None) -> list[str]:
    total_count = 0
    if isinstance(competitors, dict):
        total_count = sum(len(competitors.get(key, []) or []) for key in ("top10", "recent_winners", "structure_supplement"))
    boundary_audit = competitors.get("market_boundary_audit", {}) if isinstance(competitors, dict) and isinstance(competitors.get("market_boundary_audit"), dict) else {}
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
    if boundary_audit:
        lines.extend(
            [
                "### 市场边界审计",
                f"- 状态：{boundary_audit.get('quality_status', '待复核')}",
                f"- 目标锚点词：{_join_or_default(boundary_audit.get('anchor_terms') or boundary_audit.get('anchor_tokens'), '待补')}",
                f"- 已剔除非同类竞品：{boundary_audit.get('excluded_competitor_count', 0)}；待复核：{boundary_audit.get('suspect_competitor_count', 0)}",
            ]
        )
        for item in boundary_audit.get("excluded_samples", [])[:5]:
            if isinstance(item, dict):
                lines.append(f"- 剔除：{item.get('asin', '待填')} / {_compact_title(item.get('title'), 52)}；{item.get('reason', '未命中目标小类锚点')}")
        lines.append("")
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


def _research_priority_markdown_lines(decision: dict, status: dict, currency_code: str) -> list[str]:
    scorecard = decision.get("go_nogo_scorecard", {}) if isinstance(decision, dict) else {}
    lines = [
        "### 状态卡",
        f"- 当前状态：{status.get('status', '待填') if isinstance(status, dict) else '待填'}",
        f"- 状态理由：{status.get('reason', '待填') if isinstance(status, dict) else '待填'}",
        f"- 下一步：{status.get('next_step', '待填') if isinstance(status, dict) else '待填'}",
        "",
    ]
    if scorecard:
        lines.append("### 继续研究优先级")
        if scorecard.get("gating_reasons"):
            lines.append(f"- 证据缺口：{_join_or_default(scorecard.get('gating_reasons'), '无')}")
        for name, item in scorecard.get("dimensions", {}).items():
            score = item.get("score", "待填")
            weight = item.get("weight", "待填")
            weight_text = f"{weight * 100:.0f}%" if isinstance(weight, (int, float)) else str(weight)
            lines.append(f"- {name}：{score}/10，权重 {weight_text}；依据：{item.get('note', '待填')}")
        lines.append(f"- 加权总分：{scorecard.get('weighted_score', '待填')}")
        lines.append(f"- 研究结论：{scorecard.get('decision', '待填')}")
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
    lines.extend(["", *_analysis_mode_self_check_lines()])
    lines.append("")
    return lines


def _analysis_mode_self_check_lines() -> list[str]:
    lines = [
        "### 分析模式自检表",
        "| 分析模式 | 使用状态 | 使用章节位置 | 未用原因 |",
        "|---|---|---|---|",
    ]
    for mode, section, _terms in ANALYSIS_MODE_SELF_CHECKS:
        lines.append(f"| {mode} | 已用 | {section} | - |")
    lines.append("")
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
        traffic_words = card.get("traffic_keywords") if isinstance(card.get("traffic_keywords"), list) else []
        mixed_warnings = card.get("traffic_mixed_warnings") if isinstance(card.get("traffic_mixed_warnings"), list) else []
        if traffic_words:
            word_parts = [
                f"{w.get('keyword')}（{_format_number(w.get('monthly_search_volume') or w.get('monthly_search') or 0)}搜/月，{w.get('natural_position') or w.get('position') or '—'}）"
                for w in traffic_words[:6]
            ]
            traffic_line = "；".join(word_parts) if word_parts else "暂无数据"
            if mixed_warnings:
                traffic_line += f"；混池词：{'、'.join(map(str, mixed_warnings[:3]))}"
        elif sorftime_traffic and asin == traffic_asin:
            top_words = sorftime_traffic.get("top_traffic_words", [])
            mixed_warnings = sorftime_traffic.get("mixed_pool_warning", [])
            word_parts = [
                f"{w.get('keyword')}（{_format_number(w.get('monthly_search') or w.get('monthly_search_volume') or 0)}搜/月，{w.get('position') or w.get('natural_position') or '—'}）"
                for w in top_words[:6]
            ]
            traffic_line = "；".join(word_parts) if word_parts else "暂无数据"
            if mixed_warnings:
                traffic_line += f"；混池词：{'、'.join(str(w.get('keyword', w)) if isinstance(w, dict) else str(w) for w in mixed_warnings[:3])}"
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
