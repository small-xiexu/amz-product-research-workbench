"""候选池预审 Markdown 渲染（从 render_candidate_pool.py 拆分，纯移动不改逻辑）。"""

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
            "- 价格带、退货和体验风险仅用于市场机会判断，不输出后置落地结论。",
            "- 进入深挖后才接入评论/VOC、Top10 标杆组、近半年新品组和市场机会评分。",
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


def _count_status(candidates: list[dict[str, Any]], status: str) -> int:
    return sum(1 for candidate in candidates if candidate.get("status") == status)


def _first_candidate_name(candidates: list[dict[str, Any]]) -> str:
    return str(candidates[0].get("name", "待补")) if candidates else "待补"


def _first_next_step(candidates: list[dict[str, Any]]) -> str:
    return str(candidates[0].get("next_step", "待补")) if candidates else "待补"


def _competition_lines(candidate: dict[str, Any]) -> list[str]:
    competition = candidate.get("competition_structure", {})
    new_listing = candidate.get("new_listing_opportunity", {})
    price_context = candidate.get("price_band_context", {})
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
    if price_context.get("top_price_band_by_units"):
        lines.append(f"销量集中价格带：{price_context.get('top_price_band_by_units')}")
    elif price_context.get("price_band"):
        lines.append(f"价格带上下文：{price_context.get('price_band')}")
    if competition.get("notes"):
        lines.append(str(competition.get("notes")))
    return [line for line in lines if line]


def _bullet_lines(items: list[Any]) -> list[str]:
    values = [str(item) for item in items if item not in (None, "")]
    if not values:
        return ["- 待补"]
    return [f"- {value}" for value in values]


def _md_cell(value: Any) -> str:
    text = _display_value(value)
    return text.replace("|", "\\|").replace("\n", "<br>")
