"""候选池预审 Excel 渲染（从 render_candidate_pool.py 拆分，纯移动不改逻辑）。"""

from __future__ import annotations

import json
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any

from packages.report_renderer.workbook import _write_xlsx

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
        ("价格带上下文", "price_band_context"),
        ("退货风险", "return_risk"),
        ("市场验证风险", "market_validation_risk"),
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


def _gap_action(gap: str) -> str:
    if "评论" in gap or "VOC" in gap:
        return "进入深挖后读取自有评论插件导出"
    if "价格" in gap or "价格带" in gap:
        return "补卖家精灵市场分析或 Top100 价格分布"
    if "商标" in gap or "专利" in gap:
        return "仅作为人工风险提示，当前主链路不做结论"
    return "根据是否进入深挖决定是否补充"
