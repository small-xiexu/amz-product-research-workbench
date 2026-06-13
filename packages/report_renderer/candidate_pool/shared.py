"""候选池预审渲染共享助手与格式化（从 render_candidate_pool.py 拆分）。"""

from __future__ import annotations

import json
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any

from packages.report_renderer.formatting import _display_value

STATUS_ORDER = {"继续看": 0, "试做": 1, "观察": 2, "先放弃": 3}

__all__ = [
    '_sorted_candidates',
    '_decision_text',
    '_evidence_lines',
    '_keyword_signal_lines',
    '_direction_card_lines',
    '_boundary_review_lines',
    '_candidate_quality_lines',
    '_data_quality_overview',
    '_review_asin_lines',
    '_risk_lines',
    '_number',
    '_percent',
    '_display_value',
    'STATUS_ORDER',
]


def _sorted_candidates(candidate_pool: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = [item for item in candidate_pool.get("candidates", []) if isinstance(item, dict)]
    return sorted(candidates, key=lambda item: STATUS_ORDER.get(str(item.get("status")), 9))


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
