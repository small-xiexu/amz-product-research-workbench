"""Excel 数据底表渲染（从 render_report.py R3 抽离，纯移动不改逻辑）。"""

from __future__ import annotations

import json
import math
import re
from datetime import datetime
from html import escape
from pathlib import Path

from packages.report_renderer.xlsx_writer import write_xlsx
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


def render_data_workbook(package: dict, output_path: str | Path) -> None:
    sheets = _build_workbook_sheets(package)
    _write_xlsx(Path(output_path), sheets)


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
        ("待确认标签", _pending_label_rows(market_structure.get("pending_label_items", []), currency_code)),
        ("属性分布", _attribute_distribution_rows(market_structure.get("attribute_distributions", []))),
        ("属性交叉分析", _cross_analysis_rows(market_structure.get("cross_analysis", []), currency_code)),
        ("机会判断", _opportunity_judgment_rows(market_structure.get("opportunity_judgments", []), currency_code)),
        ("竞品选择逻辑", _competitor_selection_logic_rows(package.get("competitor_selection_logic", []), currency_code)),
        ("竞品池", _competitor_rows(competitors, currency_code)),
        ("竞品深拆卡", _competitor_deep_dive_rows(package.get("competitor_deep_dive", []), currency_code)),
        ("进入壁垒", _entry_barriers_rows(package.get("entry_barriers", []))),
        ("Go_No-Go评分卡", _go_nogo_scorecard_rows(package.get("decision_review", {}).get("go_nogo_scorecard", {}) if isinstance(package.get("decision_review"), dict) else {})),
        ("利润测算输入", _profit_input_rows(operator_inputs, currency_code)),
        ("利润参考结果", _dict_rows(profit)),
        ("利润成本拆分", _profit_breakdown_rows(profit)),
        ("供应链粗估", _supply_chain_signal_rows(profit.get("supply_chain_signal", {}) if isinstance(profit, dict) else {})),
        ("决策检查", _decision_rows(decision)),
        ("风险矩阵", _risk_matrix_rows(decision.get("risk_matrix", []) if isinstance(decision, dict) else [])),
        ("交互决策记录", _workflow_trace_rows(package.get("workflow_trace", {}))),
        ("评论VOC", _voc_summary_rows(package.get("voc_analysis", {}))),
        ("VOC证据", _voc_evidence_rows(package.get("normalized_tables", {}).get("voc_evidence", []))),
        ("退货风险", _dict_rows(return_risk)),
        ("知产合规复核", _dict_rows(ip_compliance_review)),
        ("知产初筛", _ip_screening_rows(ip_screening)),
        ("合规认证预判", _compliance_screening_rows(compliance)),
        ("状态卡", _dict_rows(status)),
    ]


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


def _supply_chain_signal_rows(signal: dict) -> list[list[object]]:
    rows: list[list[object]] = [["字段", "值"]]
    if not signal:
        rows.append(["状态", "未接入"])
        return rows
    for key, label in (
        ("source_tool", "来源工具"),
        ("search_name", "搜索词"),
        ("supplier_count", "供应商样本数"),
        ("purchase_price_cny_min", "采购价下限(RMB)"),
        ("purchase_price_cny_max", "采购价上限(RMB)"),
        ("purchase_price_cny_avg", "采购价均值(RMB)"),
        ("purchase_price_usd_avg", "采购价均值(USD)"),
        ("exchange_rate", "折算汇率"),
        ("confidence", "置信度"),
        ("note", "口径说明"),
    ):
        rows.append([label, _display_value(signal.get(key))])
    sample_products = signal.get("sample_products", [])
    rows.extend([[], ["样本商品", "供应商", "价格下限(RMB)", "价格上限(RMB)", "链接"]])
    if isinstance(sample_products, list) and sample_products:
        for item in sample_products:
            if isinstance(item, dict):
                rows.append(
                    [
                        item.get("title"),
                        item.get("supplier"),
                        item.get("price_cny_min"),
                        item.get("price_cny_max"),
                        item.get("url"),
                    ]
                )
    else:
        rows.append(["未提供", "", "", "", ""])
    return rows


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


def _workflow_trace_rows(workflow_trace: dict) -> list[list[object]]:
    rows: list[list[object]] = [["类型", "阶段", "动作/决策", "角色/动作类型", "理由/问题", "证据", "时间/来源"]]
    trace = workflow_trace if isinstance(workflow_trace, dict) else {}
    state = trace.get("workflow_state", {}) if isinstance(trace, dict) else {}
    if not isinstance(state, dict) or not state:
        rows.append(["状态", "未接入", "workflow_state 未接入", "", "", "", ""])
        return rows

    rows.append(
        [
            "流程状态",
            state.get("stage"),
            state.get("workflow_id"),
            state.get("mode"),
            state.get("operator_question"),
            _format_evidence_refs(state.get("evidence_refs", [])),
            state.get("updated_at") or trace.get("source_file"),
        ]
    )
    next_actions = trace.get("next_actions") or state.get("next_actions", [])
    if isinstance(next_actions, list):
        for action in next_actions:
            if not isinstance(action, dict):
                continue
            recommended = action.get("recommended_action", {}) if isinstance(action.get("recommended_action"), dict) else {}
            rows.append(
                [
                    "下一步动作",
                    action.get("stage"),
                    recommended.get("label"),
                    recommended.get("type"),
                    recommended.get("reason") or action.get("question"),
                    _format_evidence_refs(action.get("evidence_refs", [])),
                    trace.get("source_file", ""),
                ]
            )
    decisions = trace.get("decision_log") or state.get("decision_log", [])
    if isinstance(decisions, list):
        for item in decisions:
            if not isinstance(item, dict):
                continue
            rows.append(
                [
                    "决策记录",
                    item.get("stage"),
                    item.get("decision"),
                    item.get("actor"),
                    item.get("rationale"),
                    _format_evidence_refs(item.get("evidence_refs", [])),
                    item.get("created_at"),
                ]
            )
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
    rows: list[list[object]] = [["交叉维度", "说明", "组合", "样本数", "均价", "月销量均值", "评分均值", "机会类型", "解释"]]
    for item in cross_analysis:
        if not isinstance(item, dict):
            continue
        cells = item.get("cells", [])
        rows.append([item.get("label"), item.get("purpose"), "", "", "", "", "", "", item.get("summary")])
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
                        cell.get("opportunity_type"),
                        cell.get("interpretation"),
                    ]
                )
    if len(rows) == 1:
        rows.append(["未生成", "", "", "", "", "", "", "", ""])
    return rows


def _pending_label_rows(items: object, currency_code: str = "USD") -> list[list[object]]:
    rows: list[list[object]] = [[
        "ASIN", "标题（截取）", f"价格({currency_code})", "月销量",
        "AI产品路线", "AI功能标签", "置信度", "AI备注",
        "运营填写-产品路线", "运营填写-主场景", "运营备注",
    ]]
    if isinstance(items, list):
        for item in items:
            if not isinstance(item, dict):
                continue
            rows.append(
                [
                    item.get("asin"),
                    _compact_title(item.get("title"), 70),
                    item.get("price"),
                    item.get("monthly_units"),
                    item.get("product_route"),
                    _display_value(item.get("feature_tags")),
                    item.get("tag_confidence"),
                    _display_value(item.get("tag_notes")),
                    item.get("operator_product_route", ""),
                    item.get("operator_main_scene", ""),
                    item.get("operator_note", ""),
                ]
            )
    if len(rows) == 1:
        rows.append(["暂无待确认标签", "", "", "", "", "", "", "", "", "", ""])
    return rows


def _opportunity_judgment_rows(items: object, currency_code: str = "USD") -> list[list[object]]:
    rows: list[list[object]] = [[
        "交叉维度", "组合", "机会类型", "样本数", f"均价({currency_code})",
        "月销量均值", "评分均值", "依据", "下一步", "样本ASIN",
    ]]
    if isinstance(items, list):
        for item in items:
            if not isinstance(item, dict):
                continue
            rows.append(
                [
                    item.get("cross_dimension"),
                    item.get("combination"),
                    item.get("opportunity_type"),
                    item.get("sample_count"),
                    item.get("avg_price"),
                    item.get("avg_monthly_units"),
                    item.get("avg_rating"),
                    item.get("basis"),
                    item.get("next_check"),
                    _display_value(item.get("sample_asins")),
                ]
            )
    if len(rows) == 1:
        rows.append(["未生成", "", "", "", "", "", "", "", "", ""])
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


def _competitor_selection_logic_rows(items: object, currency_code: str = "USD") -> list[list[object]]:
    rows: list[list[object]] = [[
        "ASIN", "品牌", "标题（截取）", f"价格({currency_code})", "月销量",
        "评分", "评分数", "竞品类型", "覆盖维度", "选择理由",
    ]]
    if isinstance(items, list):
        for item in items:
            if not isinstance(item, dict):
                continue
            rows.append(
                [
                    item.get("asin"),
                    item.get("brand"),
                    _compact_title(item.get("title"), 80),
                    item.get("price_usd"),
                    item.get("monthly_units"),
                    item.get("rating"),
                    item.get("rating_count"),
                    item.get("competitor_type"),
                    _display_value(item.get("coverage_dimensions")),
                    item.get("selection_reason"),
                ]
            )
    if len(rows) == 1:
        rows.append(["未生成", "", "", "", "", "", "", "", "", ""])
    return rows


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


def _write_xlsx(output_path: Path, sheets: list[tuple[str, list[list[object]]]]) -> None:
    write_xlsx(output_path, sheets)


def _entry_barriers_rows(barriers: list[dict]) -> list[list[object]]:
    rows: list[list[object]] = [["壁垒类型", "等级", "数据依据", "判断规则", "建议"]]
    if not barriers:
        rows.append(["未生成", "", "", "", ""])
        return rows
    for item in barriers:
        rows.append([
            item.get("type"),
            item.get("level"),
            item.get("data_basis"),
            item.get("rule"),
            item.get("suggestion"),
        ])
    return rows


def _go_nogo_scorecard_rows(scorecard: dict) -> list[list[object]]:
    rows: list[list[object]] = [["维度", "得分（满分10）", "权重", "加权得分", "依据"]]
    if not scorecard:
        rows.append(["未生成", "", "", "", ""])
        return rows
    dimensions = scorecard.get("dimensions", {})
    for dim_name, dim_data in dimensions.items():
        score = dim_data.get("score", 0)
        weight = dim_data.get("weight", 0)
        rows.append([
            dim_name,
            score,
            f"{weight * 100:.0f}%",
            round(score * weight, 2),
            dim_data.get("note", ""),
        ])
    rows.append([])
    rows.append(["加权总分", scorecard.get("weighted_score", ""), "", "", ""])
    rows.append(["决策结论", scorecard.get("decision", ""), "", "", ""])
    rows.append(["决策限制", _display_value(scorecard.get("gating_reasons", [])), "", "", ""])
    rows.append(["说明", scorecard.get("note", ""), "", "", ""])
    return rows
