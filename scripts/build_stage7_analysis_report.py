#!/usr/bin/env python3
"""Build Stage 7 integrated precheck report from multi-agent evidence packets."""

from __future__ import annotations

import argparse
from datetime import datetime
from html import escape
import json
from pathlib import Path
import re
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.report_renderer.xlsx_writer import write_xlsx


ALLOWED_VERDICTS = {"继续看", "谨慎继续", "暂缓"}

PROFIT_BACKFILL_FIELDS = [
    {
        "field": "final_sku_bom",
        "label": "最终 SKU / BOM",
        "where": "Stage 8 利润模板的备注或 operator_notes；同时建议在供应商报价表保留 BOM 行",
        "required": "是",
        "source_hint": "人工 review 后锁定候选款、最终规格、配件数量、包装方式和版本差异",
        "note": "同一供应链链接常混合低配、高配、配件和套装价；未锁 SKU 前不能算利润。",
    },
    {
        "field": "sale_price",
        "label": "建议售价",
        "where": "profit_review_template.xlsx / 利润输入 / value 列",
        "required": "是",
        "source_hint": "参考目标路线 Amazon 竞品价格带和你的定价策略",
        "note": "按目标站点币种填写；建议用低/中/高三个售价场景做敏感性测算。",
    },
    {
        "field": "purchase_cost_cny",
        "label": "采购价",
        "where": "profit_review_template.xlsx / 利润输入 / value 列",
        "required": "是",
        "source_hint": "锁定最终 SKU 后用供应商报价覆盖；Stage 7 只提供 1688 RMB 占位",
        "note": "不要使用详情页最低引流价、配件价或非目标版本价格。",
    },
    {
        "field": "exchange_rate",
        "label": "汇率",
        "where": "profit_review_template.xlsx / 利润输入 / value 列",
        "required": "是",
        "source_hint": "运营填写当前 USD/CNY 口径",
        "note": "例：7.2 表示 1 USD = 7.2 RMB。",
    },
    {
        "field": "fba_fee",
        "label": "FBA 配送费",
        "where": "profit_review_template.xlsx / 利润输入 / value 列",
        "required": "是",
        "source_hint": "Amazon 收入计算器或后台费用预估",
        "note": "FBA 费用对尺寸分段和重量敏感，必须按最终包装重算。",
    },
    {
        "field": "first_leg_shipping_cny",
        "label": "头程费用",
        "where": "profit_review_template.xlsx / 利润输入 / value 列",
        "required": "是",
        "source_hint": "货代报价；或用实际重、体积重和渠道估算",
        "note": "大体积或多配件方案需要单独做体积重压力测试。",
    },
    {
        "field": "actual_weight_g",
        "label": "实际重量",
        "where": "profit_review_template.xlsx / 利润输入 / value 列",
        "required": "是",
        "source_hint": "供应商按最终 SKU 重报单套净重/毛重",
        "note": "供应链页面字段可能是单配件、单件、外箱或异常值，不能直接定稿。",
    },
    {
        "field": "volume_weight_g",
        "label": "体积重",
        "where": "profit_review_template.xlsx / 利润输入 / value 列",
        "required": "是",
        "source_hint": "用最终单品包装长宽高换算",
        "note": "建议同时记录 package_length_cm、package_width_cm、package_height_cm 作为来源。",
    },
    {
        "field": "inbound_placement_fee_cny",
        "label": "入库配置费",
        "where": "profit_review_template.xlsx / 利润输入 / value 列",
        "required": "是",
        "source_hint": "运营按 Amazon 入仓方案填写",
        "note": "不确定时留空，系统应保持 Wait，不默认 0。",
    },
    {
        "field": "commission_rate",
        "label": "佣金率",
        "where": "profit_review_template.xlsx / 利润输入 / value 列",
        "required": "否",
        "source_hint": "Amazon 类目费率",
        "note": "默认可先用 15%，精算以后台费率表为准。",
    },
    {
        "field": "ad_rate",
        "label": "新品广告费率",
        "where": "profit_review_template.xlsx / 利润输入 / value 列",
        "required": "否",
        "source_hint": "运营广告假设",
        "note": "默认可先压测 20%，若关键词混池严重，建议同时测 25%-30%。",
    },
    {
        "field": "return_rate",
        "label": "退货率",
        "where": "profit_review_template.xlsx / 利润输入 / value 列",
        "required": "否",
        "source_hint": "类目退货率、竞品差评和样品测试结果",
        "note": "差评高频问题、结构失效、缺件或使用门槛会提高退货损耗；不要只填类目均值。",
    },
    {
        "field": "ip_compliance_status",
        "label": "知产 / 合规初筛状态",
        "where": "Stage 8 合规模板或 profit_compliance evidence",
        "required": "是",
        "source_hint": "专利检索、认证/标签、材质和包装合规",
        "note": "特殊结构、外观、功能件、材料声明和包装标签需要做合规/知产边界复核。",
    },
]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Stage 7 integrated precheck report.")
    parser.add_argument("run_dir", help="Run directory, for example runs/<run_id>.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    run_dir = Path(args.run_dir).expanduser().resolve()
    if not run_dir.exists():
        raise FileNotFoundError(f"run_dir not found: {run_dir}")

    packets = load_packets(run_dir)
    analysis = build_analysis_packet(run_dir, packets)
    analysis_dir = run_dir / "analysis"
    analysis_dir.mkdir(parents=True, exist_ok=True)

    analysis_json = analysis_dir / "analysis_evidence_packet.json"
    html_path = analysis_dir / "analysis_report.html"
    xlsx_path = analysis_dir / "analysis_report.xlsx"
    qa_path = analysis_dir / "delivery_qa_result.json"

    analysis_json.write_text(json.dumps(analysis, ensure_ascii=False, indent=2), encoding="utf-8")
    html_path.write_text(render_html_report(analysis), encoding="utf-8")
    write_xlsx(xlsx_path, build_workbook_sheets(analysis))
    qa = run_delivery_qa(run_dir, analysis, analysis_json, html_path, xlsx_path)
    qa_path.write_text(json.dumps(qa, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Wrote {analysis_json}")
    print(f"Wrote {html_path}")
    print(f"Wrote {xlsx_path}")
    print(f"Wrote {qa_path}")
    if qa.get("status") != "pass":
        return 1
    return 0


def load_packets(run_dir: Path) -> dict[str, Any]:
    paths = {
        "search_demand": run_dir / "search_demand" / "search_demand_evidence_packet.json",
        "market_structure": run_dir / "market_structure" / "market_structure_evidence_packet.json",
        "voc": run_dir / "review_voc" / "voc_evidence_packet.json",
        "supply_chain": run_dir / "supply_chain" / "supply_chain_evidence_packet.stage7.json",
        "route_matrix": run_dir / "route_matrix_confirm.json",
        "workflow_state": run_dir / "workflow_state.json",
        "report_writer_narrative": run_dir / "analysis" / "report_writer_narrative.json",
    }
    packets: dict[str, Any] = {"paths": paths}
    for key, path in paths.items():
        packets[key] = load_json(path, required=key not in {"workflow_state", "report_writer_narrative"})
    return packets


def load_json(path: Path, required: bool = True) -> dict[str, Any]:
    if not path.exists():
        if required:
            raise FileNotFoundError(path)
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"JSON root must be object: {path}")
    return data


def build_analysis_packet(run_dir: Path, packets: dict[str, Any]) -> dict[str, Any]:
    search = packets["search_demand"]
    market = packets["market_structure"]
    voc = packets["voc"]
    supply = packets["supply_chain"]
    route_matrix = packets["route_matrix"]
    report_writer_narrative = packets.get("report_writer_narrative") or {}
    paths = packets["paths"]

    verdict = decide_verdict(search, market, voc, supply)
    source_packets = [
        source_packet_row("Search Demand / Sorftime", paths["search_demand"], search),
        source_packet_row("Market Structure / 卖家精灵", paths["market_structure"], market),
        source_packet_row("VOC Evidence", paths["voc"], voc),
        source_packet_row("Supply Chain / 1688", paths["supply_chain"], supply),
        source_packet_row("Route Matrix", paths["route_matrix"], route_matrix),
    ]

    sorftime_validation = build_sorftime_validation(search)
    seller_sprite_validation = build_seller_sprite_validation(market)
    reference_asin_pool = build_reference_asin_pool(search, market, route_matrix)
    category_opportunity = build_category_opportunity(search, market)
    keyword_pool = build_keyword_pool(search, market)
    voc_translation = build_voc_translation(voc)
    supply_chain_match = build_supply_chain_match(supply)
    route_judgment = build_route_judgment(market, route_matrix, supply)
    blocking_gaps = build_blocking_gaps(search, market, voc, supply)
    evidence_boundaries = build_evidence_boundaries(search, market, voc, supply)
    next_conditions = build_next_stage_conditions()
    review_focus = build_human_review_focus(voc, supply)
    recommended_targets = build_recommended_targets(supply, market)
    lead_operator_analysis = build_lead_operator_analysis(
        verdict,
        sorftime_validation,
        seller_sprite_validation,
        voc_translation,
        supply_chain_match,
        route_judgment,
        blocking_gaps,
    )
    multi_agent_synthesis = build_multi_agent_synthesis(
        sorftime_validation,
        seller_sprite_validation,
        voc_translation,
        supply_chain_match,
    )

    return {
        "packet_id": "analysis_evidence_packet",
        "packet_version": "stage7-integrated-precheck-v1",
        "agent_role": "Lead Operator Agent",
        "persona": "资深亚马逊运营专家",
        "stage": "integrated_precheck",
        "run_id": run_dir.name,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "verdict": verdict,
        "one_sentence_conclusion": one_sentence_conclusion(verdict, sorftime_validation, seller_sprite_validation, supply_chain_match),
        "confidence": "medium",
        "source_packets": source_packets,
        "lead_operator_analysis": lead_operator_analysis,
        "reference_asin_pool": reference_asin_pool,
        "category_opportunity": category_opportunity,
        "keyword_pool": keyword_pool,
        "report_writer_narrative": build_report_writer_narrative(
            report_writer_narrative,
            verdict,
            lead_operator_analysis,
            sorftime_validation,
            seller_sprite_validation,
            voc_translation,
            supply_chain_match,
            blocking_gaps,
        ),
        "sorftime_market_validation": sorftime_validation,
        "seller_sprite_validation": seller_sprite_validation,
        "voc_spec_translation": voc_translation,
        "supply_chain_match": supply_chain_match,
        "route_judgment": route_judgment,
        "recommended_review_targets": recommended_targets,
        "multi_agent_synthesis": multi_agent_synthesis,
        "human_review_focus": review_focus,
        "profit_backfill_location": {
            "stage": "Stage 8 利润 / FBA / 合规复核",
            "template": "profit_review_template.xlsx",
            "template_command": "python3 scripts/build_profit_template.py <research_package.json> <run_dir>/profit_review_template.xlsx",
            "merge_command": "python3 scripts/apply_profit_review.py <filled_profit_review_template.xlsx> <research_package.json>",
            "where_to_fill": "正式利润回填在 profit_review_template.xlsx 的「利润输入」Sheet，填写 value 列；本报告 Excel 的 Profit Backfill Sheet 是字段清单和来源提示。",
            "rule": "利润、FBA、头程、入库配置费、合规未回填前，不能输出强 Go。",
        },
        "profit_backfill_fields": PROFIT_BACKFILL_FIELDS,
        "evidence_boundaries": evidence_boundaries,
        "blocking_gaps": blocking_gaps,
        "next_stage_entry_conditions": next_conditions,
        "lineage": {
            "run_dir": str(run_dir),
            "source_packet_paths": {key: str(path) for key, path in packets["paths"].items()},
            "output_paths": {
                "analysis_json": str(run_dir / "analysis" / "analysis_evidence_packet.json"),
                "html": str(run_dir / "analysis" / "analysis_report.html"),
                "xlsx": str(run_dir / "analysis" / "analysis_report.xlsx"),
                "qa": str(run_dir / "analysis" / "delivery_qa_result.json"),
            },
        },
    }


def decide_verdict(search: dict[str, Any], market: dict[str, Any], voc: dict[str, Any], supply: dict[str, Any]) -> str:
    recommended = as_list(supply.get("recommended_candidates"))
    visual_status = ((supply.get("visual_and_spec_review_status") or {}).get("overall_status") or "")
    market_has_primary = bool(((market.get("market_size") or {}).get("primary_market") or {}).get("overview_all"))
    review_count = ((voc.get("review_scope") or {}).get("review_count") or 0)
    mix_pool_risk = any(str(item.get("value")) == "高" for item in as_list(search.get("derived_metrics")) if item.get("name") == "mix_pool_risk")
    if not market_has_primary or review_count == 0 or not recommended:
        return "暂缓"
    if "pending" in str(visual_status) or mix_pool_risk:
        return "谨慎继续"
    return "继续看"


def source_packet_row(name: str, path: Path, packet: dict[str, Any]) -> dict[str, Any]:
    provenance = packet.get("execution_provenance") if isinstance(packet.get("execution_provenance"), dict) else {}
    provenance_note = provenance.get("note") or provenance.get("subagent_note") or ""
    return {
        "name": name,
        "path": str(path),
        "exists": path.exists(),
        "packet_id": packet.get("packet_id", ""),
        "agent_role": packet.get("agent_role", ""),
        "confidence": packet.get("confidence", packet.get("confidence_rationale", "")),
        "execution_provenance": provenance,
        "executed_by_agent": provenance.get("executed_by_agent", False),
        "execution_mode": provenance.get("execution_mode", ""),
        "subagent_id": provenance.get("subagent_id", ""),
        "provenance_note": provenance_note,
    }


def build_sorftime_validation(search: dict[str, Any]) -> dict[str, Any]:
    facts = as_list(search.get("facts"))
    keyword_rows = []
    traffic_rows = []
    feature_rows = []
    supply_hint_rows = []
    for fact in facts:
        source = str(fact.get("source", ""))
        subject = str(fact.get("subject", ""))
        row = {
            "id": fact.get("id", ""),
            "source": source,
            "subject": subject,
            "metric": fact.get("metric", ""),
            "value": fact.get("value", ""),
            "note": fact.get("note", ""),
        }
        if source.endswith("keyword_detail"):
            keyword_rows.append(row)
        elif "traffic" in source:
            traffic_rows.append(row)
        elif "feature" in source:
            feature_rows.append(row)
        elif "ali1688" in source:
            supply_hint_rows.append(row)
    return {
        "agent": "Search Demand Agent / Sorftime",
        "keyword_rows": keyword_rows,
        "traffic_rows": traffic_rows,
        "keyword_demand": build_keyword_demand_rows(search, keyword_rows),
        "category_background": build_category_background_rows(search),
        "traffic_term_groups": build_traffic_term_groups(search, traffic_rows),
        "trend_signal": search.get("trend_signal") or {},
        "feature_rows": feature_rows,
        "supply_hint_rows": supply_hint_rows,
        "derived_metrics": as_list(search.get("derived_metrics")),
        "insights": as_list(search.get("insights_for_handoff")),
        "data_gaps": as_list(search.get("data_gaps")),
        "summary": sorftime_summary(keyword_rows, search.get("derived_metrics"), search.get("insights_for_handoff")),
    }


def build_keyword_demand_rows(search: dict[str, Any], fallback_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for item in as_list(search.get("keyword_demand")):
        rows.append(
            {
                "keyword": item.get("keyword", ""),
                "monthly_search_volume": item.get("monthly_search_volume", ""),
                "cpc": item.get("cpc", ""),
                "competitor_count": item.get("competitor_count", ""),
                "seasonality": item.get("seasonality", ""),
                "route_relevance": item.get("route_relevance", ""),
                "top_products": as_list(item.get("top5_natural_products"))[:4],
            }
        )
    if rows:
        return rows
    return [
        {
            "keyword": row.get("subject", ""),
            "monthly_search_volume": row.get("value", ""),
            "cpc": "",
            "competitor_count": "",
            "seasonality": "",
            "route_relevance": row.get("note", ""),
            "top_products": [],
        }
        for row in fallback_rows
    ]


def build_category_background_rows(search: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for fact in as_list((search.get("category_match") or {}).get("facts")):
        value = fact.get("value") if isinstance(fact.get("value"), dict) else {}
        rows.append(
            {
                "category": fact.get("subject", ""),
                "node_id": value.get("nodeId", value.get("nodeid", "")),
                "top100_monthly_units": value.get("top100_monthly_units", value.get("Top100产品月销量", "")),
                "average_price_usd": value.get("average_price_usd", value.get("average_price", "")),
                "median_price_usd": value.get("median_price_usd", value.get("median_price", "")),
                "top3_share": value.get(
                    "top3_product_sales_volume_share",
                    value.get("top3_product_units_share", value.get("销量前3的产品月销量占比", "")),
                ),
                "amazon_owned_share": value.get(
                    "amazon_owned_sales_volume_share",
                    value.get("amazon_owned_units_share", value.get("亚马逊自营月销量占比", "")),
                ),
                "low_review_share": value.get("low_reviews_sales_volume_share", value.get("评价数量300以下产品月销量占比", "")),
                "interpretation": fact.get("interpretation", ""),
            }
        )
    return rows


def build_traffic_term_groups(search: dict[str, Any], fallback_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups = []
    for group in as_list(search.get("traffic_terms")):
        asins = []
        for asin_row in as_list(group.get("asins")):
            asins.append(
                {
                    "asin": asin_row.get("asin", ""),
                    "role": asin_row.get("role", ""),
                    "positive_terms": as_list(asin_row.get("positive_terms"))[:5],
                    "bucket_terms": as_list(asin_row.get("bucket_related_terms"))[:3],
                    "noise_terms": as_list(asin_row.get("noise_terms"))[:5],
                }
            )
        groups.append(
            {
                "route_id": group.get("route_id", ""),
                "traffic_read": group.get("traffic_read", ""),
                "asins": asins,
            }
        )
    if groups:
        return groups
    return [
        {
            "route_id": row.get("subject", ""),
            "traffic_read": row.get("note", ""),
            "asins": [
                {
                    "asin": row.get("subject", ""),
                    "role": "",
                    "positive_terms": [{"keyword": item, "monthly_search_volume": "", "organic_position": ""} for item in as_list(row.get("value"))[:5]],
                    "bucket_terms": [],
                    "noise_terms": [],
                }
            ],
        }
        for row in fallback_rows
    ]


def sorftime_summary(keyword_rows: list[dict[str, Any]], derived_metrics: Any, insights: Any) -> str:
    ranked = sorted(
        [row for row in keyword_rows if isinstance(row.get("value"), (int, float))],
        key=lambda row: float(row.get("value") or 0),
        reverse=True,
    )
    top = ranked[0] if ranked else (keyword_rows[0] if keyword_rows else {})
    cleaner_metric = next(
        (
            item
            for item in as_list(derived_metrics)
            if "quality" in str(item.get("name", "")).lower() or "keyword" in str(item.get("name", "")).lower()
        ),
        {},
    )
    insight = first_text(as_list(insights), "text")
    if top and cleaner_metric:
        return (
            f"Sorftime 显示核心词「{top.get('subject')}」月搜约 {fmt_number(top.get('value'))}；"
            f"关键词质量判断为：{cleaner_metric.get('value')}。{cleaner_metric.get('explanation') or top.get('note', '')}"
        )
    if top:
        return f"Sorftime 显示核心词「{top.get('subject')}」月搜约 {fmt_number(top.get('value'))}；{top.get('note', '')}"
    return insight or "Sorftime 已完成搜索需求复核，详见关键词、流量词和 data gaps。"


def build_seller_sprite_validation(market: dict[str, Any]) -> dict[str, Any]:
    primary_market = ((market.get("market_size") or {}).get("primary_market") or {})
    overview = primary_market.get("overview_all") or {}
    price_band = market.get("price_band") or {}
    grouped_price = price_band.get("primary_market_distribution_grouped") or {}
    review_metric = next(
        (
            metric
            for metric in as_list(market.get("derived_metrics"))
            if metric.get("id") == "dm_primary_review_threshold"
        ),
        {},
    )
    route_rows = as_list(market.get("route_market_fit"))
    keyword_validation = market.get("keyword_competitor_validation") or {}
    label = primary_market.get("market_label") or "目标市场"
    return {
        "agent": "Market Structure Agent / 卖家精灵",
        "primary_market": {
            "label": label,
            "sample_count": overview.get("样本商品数", ""),
            "avg_monthly_units": overview.get("月均销量", ""),
            "avg_monthly_revenue_usd": overview.get("月均销售额($)", ""),
            "avg_price_usd": overview.get("平均价格($)", ""),
            "avg_rating_count": overview.get("平均评分数", ""),
        },
        "price_band": grouped_price,
        "review_threshold": (review_metric.get("values") or {}),
        "new_product_signal": market.get("new_product_signal") or {},
        "route_market_fit": route_rows,
        "keyword_competitor_validation": keyword_validation,
        "derived_metrics": as_list(market.get("derived_metrics")),
        "insights": as_list(market.get("insights_for_handoff")),
        "data_gaps": as_list(market.get("data_gaps")),
        "summary": seller_sprite_summary(overview, grouped_price, review_metric, route_rows),
    }


def seller_sprite_summary(
    overview: dict[str, Any],
    grouped_price: dict[str, Any],
    review_metric: dict[str, Any],
    route_rows: list[dict[str, Any]],
) -> str:
    under_15 = fmt_percent((grouped_price.get("under_15") or {}).get("unit_share"))
    over_30 = fmt_percent((grouped_price.get("30_plus") or {}).get("unit_share"))
    review_500 = fmt_percent(((review_metric.get("values") or {}).get("500_plus_reviews") or {}).get("unit_share"))
    route_count = len(route_rows)
    return (
        f"卖家精灵主市场样本 {fmt_number(overview.get('样本商品数'))} 个，均价约 ${fmt_number(overview.get('平均价格($)'))}；"
        f"<$15 贡献销量 {under_15}，$30+ 贡献销量 {over_30}，500+ 评论商品贡献销量 {review_500}。"
        f"已按 {route_count} 条路线拆开看价格、销量和评论门槛。"
    )


def build_reference_asin_pool(search: dict[str, Any], market: dict[str, Any], route_matrix: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in as_list(market.get("reference_asin_pool")) + as_list(search.get("reference_asin_inputs")):
        if not isinstance(item, dict):
            continue
        asin = item.get("asin")
        if not asin:
            continue
        rows.append(
            {
                "asin": asin,
                "route_ref": item.get("route_ref") or item.get("route_id") or item.get("route_name", ""),
                "asin_role": item.get("asin_role") or item.get("role", ""),
                "similarity_reason": item.get("similarity_reason") or item.get("reason", ""),
                "category_path": item.get("category_path", ""),
                "category_role": item.get("category_role", ""),
                "price": item.get("price", item.get("price_usd", "")),
                "monthly_sales": item.get("monthly_sales", item.get("avg_monthly_units", "")),
                "rating_count": item.get("rating_count", item.get("reviews", "")),
                "lineage": item.get("lineage") or item.get("source_refs") or "",
            }
        )
    if rows:
        return dedupe_rows(rows, "asin")[:30]

    for route in as_list(market.get("route_market_fit")) + as_list(route_matrix.get("route_matrix")):
        for asin in as_list(route.get("representative_asins")):
            rows.append(
                {
                    "asin": asin,
                    "route_ref": route.get("route_name") or route.get("route_id", ""),
                    "asin_role": route.get("role_from_route_matrix", route.get("role", "代表样本")),
                    "similarity_reason": route.get("why", route.get("operator_read", "路线代表 ASIN，需补相似理由")),
                    "category_path": "",
                    "category_role": "",
                    "price": "",
                    "monthly_sales": route.get("avg_monthly_units", ""),
                    "rating_count": route.get("median_rating_count", ""),
                    "lineage": "route_matrix / market_structure fallback",
                }
            )
    return dedupe_rows(rows, "asin")[:30]


def build_category_opportunity(search: dict[str, Any], market: dict[str, Any]) -> dict[str, Any]:
    category_candidates = normalize_category_candidates(search, market)
    asin_category_mapping = as_list(market.get("asin_category_mapping"))
    price_band_opportunity = normalize_price_band_opportunity(market)
    new_release_opportunity = score_new_release_opportunities(
        as_list(market.get("new_release_opportunity")) or as_list(market.get("new_product_signal"))
    )
    category_seasonality = normalize_category_seasonality(search, market)
    return {
        "category_candidates": category_candidates,
        "asin_category_mapping": asin_category_mapping,
        "price_band_opportunity": price_band_opportunity,
        "new_release_opportunity": new_release_opportunity,
        "category_seasonality": category_seasonality,
        "summary": category_opportunity_summary(category_candidates, price_band_opportunity, new_release_opportunity),
    }


def normalize_category_candidates(search: dict[str, Any], market: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in as_list(market.get("category_candidates")) + as_list(search.get("category_candidates")):
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "category_name": item.get("category_name") or item.get("name") or item.get("category", ""),
                "node_id": item.get("node_id") or item.get("nodeId") or item.get("nodeid", ""),
                "category_path": item.get("category_path", ""),
                "category_role": item.get("category_role") or item.get("role", ""),
                "source_type": item.get("source_type", ""),
                "matched_asin_count": item.get("matched_asin_count", ""),
                "evidence_strength": item.get("evidence_strength", item.get("confidence", "")),
                "recommended_use": item.get("recommended_use", ""),
                "risk_tags": join_text(item.get("risk_tags")),
                "lineage": item.get("lineage") or item.get("source_refs") or "",
            }
        )
    if rows:
        return rows

    for fact in as_list((search.get("category_match") or {}).get("facts")):
        value = fact.get("value") if isinstance(fact.get("value"), dict) else {}
        rows.append(
            {
                "category_name": fact.get("subject", ""),
                "node_id": value.get("nodeId", value.get("nodeid", "")),
                "category_path": "",
                "category_role": "candidate",
                "source_type": "legacy_category_match",
                "matched_asin_count": "",
                "evidence_strength": "",
                "recommended_use": "needs_manual_review",
                "risk_tags": "",
                "lineage": fact.get("id", ""),
            }
        )
    return rows


def normalize_price_band_opportunity(market: dict[str, Any]) -> list[dict[str, Any]]:
    rows = as_list(market.get("price_band_opportunity"))
    if rows:
        return rows
    grouped = ((market.get("price_band") or {}).get("primary_market_distribution_grouped") or {})
    normalized: list[dict[str, Any]] = []
    for band, value in grouped.items():
        if not isinstance(value, dict):
            continue
        normalized.append(
            {
                "category_ref": "primary_market",
                "price_band": band,
                "product_count": value.get("product_count", ""),
                "sales_share": value.get("unit_share", ""),
                "revenue_share": value.get("revenue_share", ""),
                "median_rating_count": value.get("median_rating_count", ""),
                "top3_product_share": value.get("top3_product_share", ""),
                "top3_brand_share": value.get("top3_brand_share", ""),
                "new_release_count": value.get("new_release_count", ""),
                "low_review_winner_count": value.get("low_review_winner_count", ""),
                "opportunity_level": value.get("opportunity_level", "watch"),
                "reason": value.get("reason", "旧价格带字段兜底，需补完整价格段机会"),
                "lineage": "market.price_band.primary_market_distribution_grouped",
            }
        )
    return normalized


def category_opportunity_summary(
    categories: list[dict[str, Any]],
    price_bands: list[dict[str, Any]],
    new_release: list[dict[str, Any]],
) -> str:
    subcats = [row for row in categories if str(row.get("category_role")) in {"subcategory_market", "小类"}]
    mixed = [row for row in categories if str(row.get("category_role")) in {"mixed_pool", "混池", "excluded", "排除"}]
    strong_bands = [row for row in price_bands if str(row.get("opportunity_level")) == "strong"]
    return (
        f"候选类目 {len(categories)} 个，其中小类候选 {len(subcats)} 个、混池/排除 {len(mixed)} 个；"
        f"价格带机会 {len(price_bands)} 段，强机会 {len(strong_bands)} 段；"
        f"新品机会记录 {len(new_release)} 条。"
    )


def score_new_release_opportunities(rows: list[Any]) -> list[dict[str, Any]]:
    scored: list[dict[str, Any]] = []
    for raw in rows:
        if not isinstance(raw, dict):
            continue
        item = dict(raw)
        score, level, reason = new_release_score(item)
        item["new_release_opportunity_score"] = score
        item["new_release_opportunity_level"] = level
        item["score_reason"] = item.get("score_reason") or reason
        scored.append(item)
    return scored


def normalize_category_seasonality(search: dict[str, Any], market: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in as_list(search.get("category_seasonality")) + as_list(market.get("category_seasonality")):
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "category_ref": item.get("category_ref") or item.get("category_name") or item.get("category", ""),
                "category_role": item.get("category_role", ""),
                "trend_source": item.get("trend_source") or item.get("source_type") or "",
                "trend_index": item.get("trend_index") or item.get("trendIndex") or "",
                "peak_months": join_text(item.get("peak_months")),
                "low_months": join_text(item.get("low_months")),
                "seasonality_level": item.get("seasonality_level", ""),
                "trend_direction": item.get("trend_direction", ""),
                "keyword_heat_note": item.get("keyword_heat_note", ""),
                "category_seasonality_note": item.get("category_seasonality_note") or item.get("reason", ""),
                "lineage": item.get("lineage") or item.get("source_refs") or "",
            }
        )
    if rows:
        return rows
    trend = search.get("trend_signal") if isinstance(search.get("trend_signal"), dict) else {}
    if trend:
        rows.append(
            {
                "category_ref": trend.get("category_ref", "category_trend"),
                "category_role": trend.get("category_role", ""),
                "trend_source": "legacy_trend_signal",
                "trend_index": trend.get("trend_index", ""),
                "peak_months": join_text(trend.get("peak_months")),
                "low_months": join_text(trend.get("low_months")),
                "seasonality_level": trend.get("seasonality_level", ""),
                "trend_direction": trend.get("trend_direction", ""),
                "keyword_heat_note": "旧字段兜底；关键词热度不能替代类目淡旺季",
                "category_seasonality_note": trend.get("summary", trend.get("handoff_read", "")),
                "lineage": "search.trend_signal",
            }
        )
    return rows


def new_release_score(item: dict[str, Any]) -> tuple[int, str, str]:
    score = 0
    reasons: list[str] = []
    new_count = numeric_value(item.get("new_release_count"))
    sales_share = numeric_value(item.get("new_release_sales_share"))
    revenue_share = numeric_value(item.get("new_release_revenue_share"))
    low_review_samples = item.get("low_review_samples")
    low_review_count = len(low_review_samples) if isinstance(low_review_samples, list) else numeric_value(item.get("low_review_winner_count"))
    signal = str(item.get("ranking_entry_signal") or "").lower()
    risks = join_text(item.get("risk_tags"))

    if new_count is not None and new_count >= 3:
        score += 20
        reasons.append("有新品样本")
    if sales_share is not None and sales_share >= 0.05:
        score += 25
        reasons.append("新品有销量占比")
    if revenue_share is not None and revenue_share >= 0.05:
        score += 15
        reasons.append("新品有销售额占比")
    if low_review_count is not None and low_review_count >= 2:
        score += 25
        reasons.append("低评论样本可放量")
    if signal == "strong":
        score += 20
        reasons.append("新品榜信号强")
    elif signal == "watch":
        score += 10
        reasons.append("新品榜信号可观察")
    if risks:
        score -= min(25, len(re.split(r"[;,，；/|]", risks)) * 8)
        reasons.append("存在风险标签")
    score = max(0, min(100, score))
    if score >= 70:
        return score, "strong", "；".join(reasons) or "新品机会强"
    if score >= 35:
        return score, "watch", "；".join(reasons) or "新品机会可观察"
    if score == 0 and not reasons:
        return score, "unknown", "新品数据待补"
    return score, "weak", "；".join(reasons) or "新品机会偏弱"


def build_keyword_pool(search: dict[str, Any], market: dict[str, Any]) -> dict[str, Any]:
    pool = search.get("keyword_pool_by_role") if isinstance(search.get("keyword_pool_by_role"), dict) else {}
    normalized = {
        "main_traffic": normalize_keyword_role_rows(pool.get("main_traffic")),
        "conversion_quality": normalize_keyword_role_rows(pool.get("conversion_quality")),
        "traffic": normalize_keyword_role_rows(pool.get("traffic")),
        "precise_long_tail": normalize_keyword_role_rows(pool.get("precise_long_tail")),
        "mixed_or_excluded": normalize_keyword_role_rows(pool.get("mixed_or_excluded")),
    }
    if not any(normalized.values()):
        normalized = keyword_pool_from_legacy(search, market)
    scored = score_keyword_pool(normalized)
    return {
        "roles": scored,
        "mix_pool_summary": mix_pool_summary(scored),
        "summary": keyword_pool_summary(scored),
    }


def normalize_keyword_role_rows(value: Any) -> list[dict[str, Any]]:
    rows = []
    for item in as_list(value):
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "keyword": item.get("keyword", ""),
                "keyword_role": item.get("keyword_role", ""),
                "source_type": item.get("source_type", ""),
                "matched_asin_count": item.get("matched_asin_count", ""),
                "monthly_search_volume": item.get("monthly_search_volume", ""),
                "cpc": item.get("cpc", ""),
                "competition_count": item.get("competition_count", ""),
                "mix_pool_tags": join_text(item.get("mix_pool_tags")),
                "recommended_action": item.get("recommended_action", ""),
                "reason": item.get("reason", ""),
                "lineage": item.get("lineage") or item.get("source_refs") or "",
            }
        )
    return rows


def keyword_pool_from_legacy(search: dict[str, Any], market: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    roles = {key: [] for key in ("main_traffic", "conversion_quality", "traffic", "precise_long_tail", "mixed_or_excluded")}
    for item in as_list(search.get("keyword_demand")):
        keyword = item.get("keyword")
        if not keyword:
            continue
        roles["traffic"].append(
            {
                "keyword": keyword,
                "keyword_role": "traffic",
                "source_type": "legacy_keyword_demand",
                "matched_asin_count": "",
                "monthly_search_volume": item.get("monthly_search_volume", ""),
                "cpc": item.get("cpc", ""),
                "competition_count": item.get("competitor_count", ""),
                "mix_pool_tags": "",
                "recommended_action": "watch",
                "reason": item.get("route_relevance", "旧关键词字段兜底，需补 ASIN 反查分层"),
                "lineage": "",
            }
        )
    validation = market.get("keyword_competitor_validation") if isinstance(market.get("keyword_competitor_validation"), dict) else {}
    for item in as_list(validation.get("keywords")) + as_list(validation.get("rows")):
        keyword = item.get("keyword") if isinstance(item, dict) else ""
        if keyword:
            roles["conversion_quality"].append(
                {
                    "keyword": keyword,
                    "keyword_role": "conversion_quality",
                    "source_type": "seller_sprite_cross_check",
                    "matched_asin_count": item.get("matched_asin_count", ""),
                    "monthly_search_volume": item.get("monthly_search_volume", ""),
                    "cpc": item.get("cpc", ""),
                    "competition_count": item.get("competition_count", ""),
                    "mix_pool_tags": join_text(item.get("mix_pool_tags")),
                    "recommended_action": item.get("recommended_action", "main_check"),
                    "reason": item.get("reason", "卖家精灵关键词交叉验证"),
                    "lineage": item.get("lineage", ""),
                }
            )
    return roles


def keyword_pool_summary(roles: dict[str, list[dict[str, Any]]]) -> str:
    return (
        f"关键词池共 {sum(len(rows) for rows in roles.values())} 个："
        f"主要流量词 {len(roles.get('main_traffic', []))}，"
        f"转化优质词 {len(roles.get('conversion_quality', []))}，"
        f"流量词 {len(roles.get('traffic', []))}，"
        f"精准长尾词 {len(roles.get('precise_long_tail', []))}，"
        f"混池/排除词 {len(roles.get('mixed_or_excluded', []))}。"
    )


def score_keyword_pool(roles: dict[str, list[dict[str, Any]]]) -> dict[str, list[dict[str, Any]]]:
    scored: dict[str, list[dict[str, Any]]] = {}
    for role, rows in roles.items():
        scored_rows = []
        for row in rows:
            item = dict(row)
            score, level, action = keyword_mix_pool_score(role, item)
            item["mix_pool_score"] = score
            item["mix_pool_risk_level"] = level
            if not item.get("recommended_action"):
                item["recommended_action"] = action
            scored_rows.append(item)
        scored[role] = scored_rows
    return scored


def keyword_mix_pool_score(role: str, row: dict[str, Any]) -> tuple[int, str, str]:
    score = 0
    tags = [tag.strip() for tag in re.split(r"[;,，；/|]", str(row.get("mix_pool_tags") or "")) if tag.strip()]
    action = str(row.get("recommended_action") or "")
    matched = numeric_value(row.get("matched_asin_count"))
    if role == "mixed_or_excluded":
        score += 70
    if tags:
        score += min(40, len(tags) * 15)
    if action == "exclude":
        score += 30
    elif action == "watch":
        score += 15
    if matched is not None and matched <= 1 and role not in {"precise_long_tail", "mixed_or_excluded"}:
        score += 10
    score = min(100, score)
    if score >= 70:
        return score, "high", "exclude"
    if score >= 35:
        return score, "medium", action or "watch"
    return score, "low", action or "main_check"


def mix_pool_summary(roles: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    all_rows = [row for rows in roles.values() for row in rows]
    high = [row for row in all_rows if row.get("mix_pool_risk_level") == "high"]
    medium = [row for row in all_rows if row.get("mix_pool_risk_level") == "medium"]
    excluded = [row for row in all_rows if row.get("recommended_action") == "exclude"]
    return {
        "total_keywords": len(all_rows),
        "high_risk_count": len(high),
        "medium_risk_count": len(medium),
        "excluded_count": len(excluded),
        "top_risk_keywords": [row.get("keyword") for row in sorted(all_rows, key=lambda item: numeric_value(item.get("mix_pool_score")) or 0, reverse=True)[:8]],
    }


def build_voc_translation(voc: dict[str, Any]) -> dict[str, Any]:
    review_scope = voc.get("review_scope") or {}
    pain_rows = as_list(voc.get("pain_points_by_dimension"))
    spec_mapping = as_list(voc.get("spec_mapping"))
    spec_rows = normalize_voc_spec_rows(pain_rows, spec_mapping)
    report_requirements = (voc.get("report_spec_requirements") or {}).get("for_html_report") or []
    positive_drivers = as_list(voc.get("positive_drivers"))
    return {
        "agent": "VOC Evidence Agent",
        "review_scope": review_scope,
        "pain_points": pain_rows,
        "spec_mapping": spec_mapping,
        "spec_rows": spec_rows,
        "coverage_gap": as_list(voc.get("coverage_gap")),
        "report_spec_requirements": report_requirements,
        "positive_drivers": positive_drivers,
        "derived_metrics": as_list(voc.get("derived_metrics")),
        "insights": as_list(voc.get("insights_for_handoff")),
        "data_gaps": as_list(voc.get("data_gaps")),
        "summary": voc_summary(review_scope, pain_rows),
    }


def normalize_voc_spec_rows(pain_rows: list[dict[str, Any]], spec_mapping: list[dict[str, Any]]) -> list[dict[str, Any]]:
    mapping_by_dimension = {str(item.get("pain_dimension") or ""): item for item in spec_mapping}
    rows: list[dict[str, Any]] = []
    for pain in pain_rows:
        dimension = str(pain.get("dimension") or "")
        mapping = mapping_by_dimension.get(dimension, {})
        rows.append(
            {
                "pain_dimension": dimension,
                "fact_observation": pain.get("fact_summary") or mapping.get("fact_observation") or "",
                "spec_requirement": first_nonempty_list(
                    pain.get("spec_requirement"),
                    pain.get("inferred_spec_requirement"),
                    mapping.get("inferred_spec_requirement"),
                ),
                "sample_tests": first_nonempty_list(pain.get("sample_tests"), mapping.get("sample_tests")),
                "supplier_validation": first_nonempty_list(
                    pain.get("supplier_validation"),
                    pain.get("supplier_questions"),
                    mapping.get("supplier_validation"),
                ),
            }
        )
    if rows:
        return rows
    for item in spec_mapping:
        rows.append(
            {
                "pain_dimension": item.get("pain_dimension", ""),
                "fact_observation": item.get("fact_observation", ""),
                "spec_requirement": as_list(item.get("inferred_spec_requirement")),
                "sample_tests": as_list(item.get("sample_tests")),
                "supplier_validation": as_list(item.get("supplier_validation")),
            }
        )
    return rows


def first_nonempty_list(*values: Any) -> list[Any]:
    for value in values:
        items = as_list(value)
        if items:
            return items
    return []


def voc_summary(review_scope: dict[str, Any], pain_rows: list[dict[str, Any]]) -> str:
    low_rating = review_scope.get("low_rating_count", "")
    count = review_scope.get("review_count", "")
    top_pains = sorted(pain_rows, key=lambda row: row.get("low_rating_hits", 0), reverse=True)[:3]
    top_text = "、".join(str(row.get("dimension", "")) for row in top_pains if row.get("dimension"))
    return f"VOC 覆盖 {fmt_number(count)} 条评论、低分 {fmt_number(low_rating)} 条，最该转成规格验证的是：{top_text}。"


def build_supply_chain_match(supply: dict[str, Any]) -> dict[str, Any]:
    recommended = as_list(supply.get("recommended_candidates"))
    backup = as_list(supply.get("backup_candidates"))
    screening = supply.get("screening_scope") or {}
    price_range = supply.get("price_range_rmb") or {}
    visual_status = supply.get("visual_and_spec_review_status") or {}
    return {
        "agent": "Supply Chain Agent / 1688",
        "screening_scope": screening,
        "price_range_rmb": price_range,
        "available_forms": as_list(supply.get("available_forms")),
        "voc_spec_coverage": as_list(supply.get("voc_spec_coverage")),
        "visual_and_spec_review_status": visual_status,
        "recommended_candidates": recommended,
        "backup_candidates": backup,
        "profit_backfill_hints": supply.get("profit_backfill_hints") or {},
        "derived_metrics": as_list(supply.get("derived_metrics")),
        "insights": as_list(supply.get("insights_for_handoff")),
        "data_gaps": as_list(supply.get("data_gaps")),
        "summary": supply_chain_summary(screening, price_range, recommended, visual_status),
    }


def supply_chain_summary(
    screening: dict[str, Any],
    price_range: dict[str, Any],
    recommended: list[dict[str, Any]],
    visual_status: dict[str, Any],
) -> str:
    candidate_count = screening.get("candidate_count", "")
    raw_count = screening.get("raw_1688_evidence_count", candidate_count)
    price_text = f"RMB {price_range.get('min', '')}-{price_range.get('max', '')}"
    return (
        f"1688 原始候选 {fmt_number(raw_count)} 条，核心有效 RMB 样本 {fmt_number(screening.get('core_valid_1688_rmb_sample_count'))} 条，"
        f"优先 review 候选 {len(recommended)} 条；采购价信号 {price_text}。"
        f"当前视觉/样品状态为 {public_text(visual_status.get('overall_status', '待复核'))}。"
    )


def build_route_judgment(market: dict[str, Any], route_matrix: dict[str, Any], supply: dict[str, Any]) -> list[dict[str, Any]]:
    route_rows = as_list(market.get("route_market_fit")) or as_list(route_matrix.get("route_matrix"))
    supply_gaps = "；".join(gap.get("gap", "") for gap in as_list(supply.get("data_gaps"))[:3])
    judgments: list[dict[str, Any]] = []
    for index, route in enumerate(route_rows):
        route_id = str(route.get("route_id", ""))
        route_name = str(route.get("route_name", ""))
        facts = route.get("facts") if isinstance(route.get("facts"), dict) else route
        role = str(route.get("role_from_route_matrix") or route.get("role") or "")
        status = str(route.get("status_from_route_matrix") or route.get("status") or "")
        if index == 0 or "主推" in role or "优先" in status:
            decision = "主推候选，谨慎继续"
            operator_read = "当前证据相对最完整，适合作为人工 review 的第一优先级；但必须完成视觉、规格、样品和利润复核后才能进入下一阶段。"
        elif "备选" in role or "观察" in status or index == 1:
            decision = "备选观察，先不主推"
            operator_read = "存在市场或差异化信号，但供应链、包装、利润或需求意图仍需补证；适合保留，不适合现在直接主推。"
        else:
            decision = "基础参照，不单独主推"
            operator_read = "适合做价格锚点、痛点来源或对照样本；除非后续数据证明有明确升级空间，否则不单独推进。"
        judgments.append(
            {
                "route_id": route_id,
                "route_name": route_name,
                "decision": decision,
                "operator_read": operator_read,
                "price_band_usd": {
                    "min": facts.get("price_min_usd", ""),
                    "max": facts.get("price_max_usd", ""),
                    "avg": facts.get("avg_price_usd", ""),
                },
                "avg_monthly_units": facts.get("avg_monthly_units", ""),
                "median_rating_count": facts.get("median_rating_count", ""),
                "representative_asins": route.get("representative_asins", []),
                "role": role,
                "status": status,
                "risk_note": supply_gaps if index > 0 else "",
            }
        )
    return judgments


def build_blocking_gaps(search: dict[str, Any], market: dict[str, Any], voc: dict[str, Any], supply: dict[str, Any]) -> list[dict[str, str]]:
    gaps: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    def add_gap(source: str, raw_gap: Any, raw_impact: Any) -> None:
        public_gap = public_blocking_gap(source, raw_gap, raw_impact)
        if not public_gap:
            return
        key = (public_gap["source"], public_gap["gap"])
        if key in seen:
            return
        seen.add(key)
        gaps.append(public_gap)

    for gap in as_list(search.get("data_gaps")):
        add_gap("Sorftime", gap.get("gap", ""), gap.get("impact", ""))
    for gap in as_list(market.get("data_gaps"))[:4]:
        add_gap("卖家精灵", gap.get("gap", ""), gap.get("impact", ""))
    for gap in as_list(voc.get("data_gaps"))[:3]:
        add_gap("VOC", gap.get("gap", ""), gap.get("impact", ""))
    for gap in as_list(supply.get("data_gaps"))[:8]:
        add_gap("1688", gap.get("gap", ""), gap.get("impact", ""))
    gaps.extend(
        [
            {
                "source": "利润/FBA",
                "gap": "利润、FBA、头程、入库配置费未回填",
                "impact": "无法判断真实毛利和广告/退货后的利润安全边界。",
            },
            {
                "source": "合规",
                "gap": "知产、材质、标签和认证初筛未回填",
                "impact": "无法排除结构、外观、功能件、材质声明、包装标签和认证风险。",
            },
        ]
    )
    return [gap for gap in gaps if gap.get("gap")]


def build_evidence_boundaries(
    search: dict[str, Any],
    market: dict[str, Any],
    voc: dict[str, Any],
    supply: dict[str, Any],
) -> list[dict[str, str]]:
    boundaries: list[dict[str, str]] = []
    target_region = infer_target_review_region(search, market)
    visual_status = supply.get("visual_and_spec_review_status") or {}
    visual_review_status = supply.get("visual_review_status") or {}
    pending_visual = (
        "pending" in str(visual_status.get("overall_status", ""))
        or "pending" in str(visual_review_status.get("overall_status", ""))
        or bool(visual_review_status.get("pending_visual_detail_review"))
    )
    if pending_visual:
        boundaries.append(
            {
                "label": "1688 视觉/实物",
                "status": "未完成",
                "what_we_have": "已完成标题、详情文本、SKU、价格、MOQ、规格字段和图片 URL 队列预筛。",
                "what_it_means": "这说明有候选供给和优先打开顺序，但不能证明主图/详情图真实匹配，也不能判断实物质量。",
                "next_action": "人工打开优先候选，确认图片、SKU/BOM、材质结构、包装重量和样品表现。",
            }
        )

    review_scope = voc.get("review_scope") or {}
    review_region = str(review_scope.get("primary_review_region") or "")
    region_share = primary_region_share(review_scope, review_region)
    if review_region:
        region_matches_target = bool(target_region and review_region == target_region)
        boundaries.append(
            {
                "label": "VOC 评论地区",
                "status": "目标地区样本可用" if region_matches_target and region_share >= 0.7 else "需看地区占比",
                "what_we_have": voc_scope_sentence(review_scope),
                "what_it_means": "VOC 以主要评论地区判断用户口径；采集入口只是为了拿到更多评论，不等于目标市场。",
                "next_action": "如果主要评论地区不是目标市场，才需要补采；主要评论地区与目标市场一致且占比高时，可作为目标用户痛点样本使用。",
            }
        )
    return boundaries


def infer_target_review_region(search: dict[str, Any], market: dict[str, Any]) -> str:
    site = infer_target_site(search, market)
    site_to_region = {
        "US": "United States",
        "CA": "Canada",
        "UK": "United Kingdom",
        "GB": "United Kingdom",
        "DE": "Germany",
        "FR": "France",
        "IT": "Italy",
        "ES": "Spain",
        "JP": "Japan",
        "MX": "Mexico",
        "AU": "Australia",
    }
    return site_to_region.get(site, "")


def infer_target_site(search: dict[str, Any], market: dict[str, Any]) -> str:
    candidates: list[str] = []
    for packet in (search, market):
        for ref in as_list(packet.get("input_refs")):
            if not isinstance(ref, dict):
                continue
            params = ref.get("params") if isinstance(ref.get("params"), dict) else {}
            for key in ("keywordSupportSite", "amzSite", "site", "marketplace"):
                value = params.get(key) or ref.get(key)
                if value:
                    candidates.append(str(value))
            path = str(ref.get("path", ""))
            match = re.search(r"(?:^|[-_/])(US|CA|UK|GB|DE|FR|IT|ES|JP|MX|AU)(?:[-_/]|$)", path, re.I)
            if match:
                candidates.append(match.group(1))
    for scope in (search.get("source_scope"), market.get("source_scope")):
        for item in as_list(scope):
            match = re.search(r"\b(US|CA|UK|GB|DE|FR|IT|ES|JP|MX|AU)\b", str(item), re.I)
            if match:
                candidates.append(match.group(1))
    return candidates[0].upper() if candidates else ""


def primary_region_share(review_scope: dict[str, Any], review_region: str) -> float:
    total = review_scope.get("review_count") or 0
    if not total:
        return 0.0
    for row in as_list(review_scope.get("review_region_distribution")):
        if row.get("name") == review_region:
            try:
                return float(row.get("count") or 0) / float(total)
            except (TypeError, ValueError, ZeroDivisionError):
                return 0.0
    return 0.0


def voc_scope_sentence(review_scope: dict[str, Any]) -> str:
    entry_site = review_scope.get("primary_entry_site") or "采集入口待标注"
    review_region = review_scope.get("primary_review_region") or "评论地区待标注"
    review_count = fmt_number(review_scope.get("review_count"))
    region_rows = as_list(review_scope.get("review_region_distribution"))
    top_region = region_rows[0] if region_rows else {}
    top_region_text = ""
    if top_region:
        top_region_text = f"，其中 {top_region.get('name')} {fmt_number(top_region.get('count'))} 条"
    return f"评论采集入口为 {entry_site}，样本 {review_count} 条；主要评论地区为 {review_region}{top_region_text}。"


def public_blocking_gap(source: str, raw_gap: Any, raw_impact: Any) -> dict[str, str] | None:
    gap = str(raw_gap or "")
    impact = str(raw_impact or "")
    combined = f"{gap} {impact}"
    if not gap:
        return None
    if "未写入 MCP 原始快照" in combined or "本 Agent 未读取卖家精灵原始导出" in combined:
        return None
    if "category_search_from_product_name" in combined or "category_report" in combined:
        return {
            "source": source,
            "gap": "Sorftime 类目与 Top100 数据需要完整刷新复核",
            "impact": "这是系统侧可补跑的数据校验，不需要你额外提供数据；补跑后用于确认类目规模、集中度和代表 ASIN 是否变化。",
        }
    if "competitor_product_keywords" in combined or "product_traffic_terms" in combined or "page=1" in combined:
        return {
            "source": source,
            "gap": "竞品关键词和 ASIN 流量词还需要继续深挖",
            "impact": "这是系统侧 Sorftime 深挖动作，不需要你额外提供数据；会影响长尾词、自然位/广告位词库和流量边界判断。",
        }
    if "similar_product_feature" in combined:
        return {
            "source": source,
            "gap": "产品特征数据需要结合竞品标题、VOC 和供应链详情复核",
            "impact": "避免把不匹配的工具返回当成规格结论；最终规格仍以候选链接、样品和差评痛点验证为准。",
        }
    if "ali1688_similar_product" in combined:
        return {
            "source": source,
            "gap": "1688 粗供给信号不能替代候选供应商复核",
            "impact": "供应商优先级仍要看详情图、SKU、BOM、包装、报价和样品表现；这不需要你再提供基础市场数据。",
        }
    return {
        "source": source,
        "gap": public_text(gap),
        "impact": public_text(impact),
    }


def build_next_stage_conditions() -> list[dict[str, str]]:
    return [
        {"condition": "人工 review HTML/Excel 后确认主推路线", "status": "待你 review", "why": "决定继续看主推候选、保留备选，还是暂停。"},
        {"condition": "1688 优先候选完成视觉/规格复核", "status": "待你 review", "why": "确认图片、SKU、BOM 和目标产品一致，剔除低配/配件/混图。"},
        {"condition": "最终 SKU、采购价、重量和包装尺寸可填写", "status": "待供应商报价或人工确认", "why": "Stage 8 利润模型需要这些字段，不然只能 Wait。"},
        {"condition": "FBA、头程、入库配置费、广告和退货假设已回填", "status": "待回填", "why": "决定真实毛利能不能扛住混池流量和退货风险。"},
        {"condition": "知产/合规初筛没有硬阻断", "status": "待回填", "why": "特殊结构、外观、材料、标签和认证需要避免后续不可控风险。"},
        {"condition": "样品测试能覆盖 VOC 痛点", "status": "待打样", "why": "样品必须验证低分评论里的核心风险，而不是只看外观相似。"},
    ]


def build_human_review_focus(voc: dict[str, Any], supply: dict[str, Any]) -> list[dict[str, str]]:
    recommended = as_list(supply.get("recommended_candidates"))
    coverage = as_list(supply.get("voc_spec_coverage"))
    pain_rows = sorted(as_list(voc.get("pain_points_by_dimension")), key=lambda row: row.get("low_rating_hits", 0), reverse=True)
    rows = [
        {
            "focus": "先打开 1688 优先候选的详情图和 SKU",
            "why": "确认图片、SKU、详情规格和目标产品形态一致，排除低配、配件价、混图和非目标版本。",
            "evidence": f"供应链已给出 {len(recommended)} 个优先 review 候选，但视觉/规格仍需人工确认。",
        },
        {
            "focus": "锁定最终 BOM 和版本",
            "why": "同一供应链页面可能同时包含基础款、高配款、配件和不同包装；利润只能按最终 SKU 测。",
            "evidence": "1688 候选的价格区间、MOQ、SKU 和 must_verify 字段。",
        },
    ]
    for pain in pain_rows[:3]:
        dimension = str(pain.get("dimension", ""))
        if not dimension:
            continue
        rows.append(
            {
                "focus": f"围绕「{dimension}」做规格确认",
                "why": str(pain.get("inference") or pain.get("fact_summary") or "该痛点在低分评论中反复出现，需要转成样品测试和供应商问询字段。"),
                "evidence": f"VOC 低分命中 {fmt_number(pain.get('low_rating_hits'))}，关键词命中 {fmt_number(pain.get('keyword_hits'))}。",
            }
        )
    for item in coverage[:2]:
        rows.append(
            {
                "focus": f"复核供应链是否覆盖「{item.get('voc_dimension', '关键规格')}」",
                "why": str(item.get("current_supply_coverage") or "供应链目前只有部分字段信号，需要确认规格和样品表现。"),
                "evidence": f"覆盖状态：{item.get('coverage_status', '待确认')}；未验证：{join_text(item.get('unverified_specs'))}",
            }
        )
    return rows[:7]


def build_recommended_targets(supply: dict[str, Any], market: dict[str, Any]) -> dict[str, Any]:
    candidates = as_list(supply.get("recommended_candidates"))
    route_targets = []
    for route in as_list(market.get("route_market_fit")):
        route_targets.append(
            {
                "route_id": route.get("route_id", ""),
                "route_name": route.get("route_name", ""),
                "representative_asins": route.get("representative_asins", []),
                "role": route.get("role_from_route_matrix", route.get("role", "")),
            }
        )
    return {
        "1688_priority_candidates": candidates,
        "amazon_route_targets": route_targets,
    }


def build_lead_operator_analysis(
    verdict: str,
    sorftime_validation: dict[str, Any],
    seller_sprite_validation: dict[str, Any],
    voc_translation: dict[str, Any],
    supply_chain_match: dict[str, Any],
    route_judgment: list[dict[str, Any]],
    blocking_gaps: list[dict[str, str]],
) -> dict[str, Any]:
    primary_route = route_judgment[0] if route_judgment else {}
    backup_routes = route_judgment[1:3]
    top_pains = sorted(voc_translation["pain_points"], key=lambda row: row.get("low_rating_hits", 0), reverse=True)[:3]
    top_pain_text = "、".join(str(row.get("dimension", "")) for row in top_pains if row.get("dimension")) or "核心低分痛点"
    top_keyword = first_keyword(sorftime_validation["keyword_rows"])
    market_label = seller_sprite_validation["primary_market"].get("label") or "目标市场"
    candidate_count = len(supply_chain_match["recommended_candidates"])
    return {
        "headline": f"资深运营预审结论：{verdict}",
        "decision_logic": [
            f"需求不是空的：Sorftime 已验证核心搜索入口，卖家精灵也有 {market_label} 的市场结构数据；但还要拆清楚哪些词是真需求，哪些只是混池流量。",
            f"当前不能直接立项：评论里的主要风险集中在 {top_pain_text}，供应链候选仍需要视觉、规格、样品和利润复核。",
            f"下一步最小动作：优先 review「{primary_route.get('route_name', '主推候选路线')}」和 {candidate_count} 个 1688 候选，确认最终 SKU/BOM 后再进入利润/FBA/合规测算。",
        ],
        "market_read": [
            sorftime_validation["summary"],
            seller_sprite_validation["summary"],
            f"运营含义：不要只看搜索量最大的词「{top_keyword}」，还要按参考 ASIN、产品形态、使用场景和竞品自然位拆出更干净的验证词。",
        ],
        "product_read": [
            voc_translation["summary"],
            "真正能拉开差异的不是堆配置，而是把低分评论里的痛点翻译成可测试、可报价、可验收的产品规格。",
        ],
        "supply_read": [
            supply_chain_match["summary"],
            "1688 已经能证明存在候选供给，但还不能证明供应商解决了 VOC 里的关键问题；因此报告只推荐 review 顺序，不直接推荐下单。",
        ],
        "route_read": [f"{row['route_name']}：{row['decision']}。{row['operator_read']}" for row in route_judgment],
        "why_not_strong_go_yet": [
            gap["gap"] + ("：" + gap["impact"] if gap.get("impact") else "")
            for gap in blocking_gaps[:8]
        ],
        "primary_route": primary_route,
        "backup_routes": backup_routes,
        "top_pains": top_pains,
    }


def build_report_writer_narrative(
    narrative: dict[str, Any],
    verdict: str,
    lead: dict[str, Any],
    sorftime_validation: dict[str, Any],
    seller_sprite_validation: dict[str, Any],
    voc_translation: dict[str, Any],
    supply_chain_match: dict[str, Any],
    blocking_gaps: list[dict[str, str]],
) -> dict[str, Any]:
    """Normalize optional Report Writer Agent prose; fallback remains evidence-driven."""
    if narrative:
        return {
            "source": "report_writer_agent",
            "headline": public_text(narrative.get("headline") or lead.get("headline") or f"资深运营预审结论：{verdict}"),
            "one_sentence": public_text(narrative.get("one_sentence") or narrative.get("one_sentence_conclusion") or ""),
            "principle": public_text(narrative.get("principle") or "数据用于帮助判断是否值得继续投入，不用于制造确定性。"),
            "analysis_cards": normalize_analysis_cards(narrative.get("analysis_cards")),
            "review_reader_note": public_text(narrative.get("review_reader_note") or ""),
        }
    return {
        "source": "template_fallback",
        "headline": lead.get("headline") or f"资深运营预审结论：{verdict}",
        "one_sentence": "",
        "principle": "数据多不是为了把报告写复杂，而是为了少踩坑；利润、合规和样品证据没闭环前，不直接立项。",
        "analysis_cards": [
            {"title": "市场是否值得继续看", "body": " ".join(lead["market_read"][:2])},
            {"title": "产品机会在哪里", "body": " ".join(lead["product_read"][:2])},
            {"title": "供应链现在能说明什么", "body": " ".join(lead["supply_read"][:2])},
            {
                "title": "为什么还不能直接立项",
                "body": "；".join(lead["why_not_strong_go_yet"][:3])
                or "利润、FBA、合规、样品或人工 review 证据未闭环前，不能直接立项。",
            },
        ],
        "review_reader_note": build_reader_note(sorftime_validation, seller_sprite_validation, voc_translation, supply_chain_match, blocking_gaps),
    }


def normalize_analysis_cards(cards: Any) -> list[dict[str, str]]:
    normalized = []
    for item in as_list(cards):
        if not isinstance(item, dict):
            continue
        title = public_text(item.get("title") or item.get("heading") or "")
        body = public_text(item.get("body") or item.get("text") or "")
        if title and body:
            normalized.append({"title": title, "body": body})
    return normalized[:6]


def build_reader_note(
    sorftime_validation: dict[str, Any],
    seller_sprite_validation: dict[str, Any],
    voc_translation: dict[str, Any],
    supply_chain_match: dict[str, Any],
    blocking_gaps: list[dict[str, str]],
) -> str:
    gap = blocking_gaps[0] if blocking_gaps else {}
    return (
        f"这份报告先看结论和 AI 综合分析，再用 Sorftime、卖家精灵、VOC、1688 四块数据回看证据。"
        f"Sorftime 关键词 {len(sorftime_validation.get('keyword_demand', []))} 条、"
        f"卖家精灵主市场样本 {fmt_number(seller_sprite_validation.get('primary_market', {}).get('sample_count'))} 个、"
        f"VOC 评论 {fmt_number(voc_translation.get('review_scope', {}).get('review_count'))} 条、"
        f"1688 优先候选 {len(supply_chain_match.get('recommended_candidates', []))} 个。"
        f"当前最大卡点：{gap.get('gap', '利润、FBA、合规和人工 review 仍待闭环')}。"
    )


def build_multi_agent_synthesis(
    sorftime_validation: dict[str, Any],
    seller_sprite_validation: dict[str, Any],
    voc_translation: dict[str, Any],
    supply_chain_match: dict[str, Any],
) -> list[dict[str, str]]:
    return [
        {
            "agent": "Sorftime / Search Demand",
            "judgment": "需求成立，但入口词混池严重。",
            "handoff": sorftime_validation["summary"],
        },
        {
            "agent": "卖家精灵 / Market Structure",
            "judgment": "市场可做观察，但低价和评论壁垒明显。",
            "handoff": seller_sprite_validation["summary"],
        },
        {
            "agent": "VOC Evidence",
            "judgment": "痛点可翻译成规格和样品测试项。",
            "handoff": voc_translation["summary"],
        },
        {
            "agent": "1688 / Supply Chain",
            "judgment": "主路线有供应形态，供应商仍需人工视觉和规格复核。",
            "handoff": supply_chain_match["summary"],
        },
        {
            "agent": "Lead Operator",
            "judgment": "谨慎继续，不强 Go。",
            "handoff": "先 review 主推候选和利润字段；回填利润/FBA/合规后再进入利润、FBA 和合规复核。",
        },
    ]


def one_sentence_conclusion(
    verdict: str,
    sorftime_validation: dict[str, Any],
    seller_sprite_validation: dict[str, Any],
    supply_chain_match: dict[str, Any],
) -> str:
    return (
        f"{verdict}：需求和代表竞品入口成立，1688 也有主路线候选；"
        "但入口词可能混池、价格带/评论壁垒、VOC 结构痛点、视觉规格未复核和利润/FBA/合规未回填，决定了现在只能先做人工 review。"
    )


def render_html_report(analysis: dict[str, Any]) -> str:
    title = "选品综合预审报告"
    html = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)}</title>
  <style>{HTML_STYLE}</style>
</head>
<body>
  <header class="topbar">
    <a href="#conclusion">结论</a>
    <a href="#ai-analysis">AI分析</a>
    <a href="#reference-asins">参考ASIN</a>
    <a href="#category-opportunity">类目机会</a>
    <a href="#keyword-pool">关键词池</a>
    <a href="#voc">VOC</a>
    <a href="#supply">1688候选</a>
    <a href="#review">人工 Review</a>
    <a href="#profit">利润回填</a>
    <a href="#next">下一步</a>
    <a href="#audit">证据审计</a>
  </header>
  <main class="page">
    {render_hero(analysis)}
    {render_evidence_boundary_section(analysis)}
    {render_lead_section(analysis)}
    {render_reference_asin_section(analysis)}
    {render_category_opportunity_section(analysis)}
    {render_keyword_pool_section(analysis)}
    {render_market_section(analysis)}
    {render_sorftime_section(analysis)}
    {render_voc_section(analysis)}
    {render_supply_section(analysis)}
    {render_review_section(analysis)}
    {render_profit_section(analysis)}
    {render_next_section(analysis)}
    {render_audit_section(analysis)}
  </main>
</body>
</html>"""
    return html


def render_hero(analysis: dict[str, Any]) -> str:
    supply = analysis["supply_chain_match"]
    keyword_pool = analysis.get("keyword_pool") or {}
    category = analysis.get("category_opportunity") or {}
    subcategory_count = len(
        [
            row
            for row in as_list(category.get("category_candidates"))
            if str(row.get("category_role")) in {"subcategory_market", "小类"}
        ]
    )
    report_title = report_subject(analysis)
    metrics = [
        ("结论", analysis["verdict"], "继续看 / 谨慎继续 / 暂缓"),
        ("参考 ASIN", f"{len(as_list(analysis.get('reference_asin_pool')))} 个", "用于反推类目和关键词"),
        ("候选小类", f"{subcategory_count} 个", "大类容量与小类机会分开看"),
        ("关键词池", f"{sum(len(rows) for rows in (keyword_pool.get('roles') or {}).values())} 个", "已按角色分层"),
        ("1688 候选", f"{len(supply['recommended_candidates'])} 个优先 review", "仍需视觉/规格复核"),
    ]
    return f"""
<section class="hero" id="conclusion">
  <div>
    <p class="eyebrow">选品预审报告 / 利润回填前</p>
    <h1>{escape(report_title)}</h1>
    <h2 class="one-line-title">一句话结论：{escape(analysis['verdict'])}</h2>
    <p class="lead">{escape(analysis['one_sentence_conclusion'])}</p>
    <div class="pill-row">
      <span class="pill verdict">{escape(analysis['verdict'])}</span>
      <span class="pill">资深亚马逊运营视角</span>
      <span class="pill">ASIN + 类目 + 词表 + VOC + 1688</span>
    </div>
  </div>
  <div class="metric-grid">{''.join(metric_card(*item) for item in metrics)}</div>
</section>"""


def render_evidence_boundary_section(analysis: dict[str, Any]) -> str:
    boundaries = analysis.get("evidence_boundaries") or []
    if not boundaries:
        return ""
    return f"""
<section class="section compact-section" id="evidence-boundary">
  <div class="section-head">
    <p class="eyebrow">证据边界</p>
    <h2>这些地方不能被报告说过头</h2>
    <p>这不是本次商品特例，而是每轮预审都要保留的通用边界：哪些已经有数据，哪些还必须人工或下一阶段确认。</p>
  </div>
  <div class="boundary-grid">
    {''.join(boundary_card(item) for item in boundaries[:6])}
  </div>
</section>"""


def boundary_card(item: dict[str, str]) -> str:
    return f"""
<article class="boundary-card">
  <div class="boundary-topline">
    <strong>{escape(item.get('label', '证据边界'))}</strong>
    <span>{escape(item.get('status', '待确认'))}</span>
  </div>
  <dl>
    <dt>已有证据</dt><dd>{escape(public_text(item.get('what_we_have', ''), max_len=320))}</dd>
    <dt>不能代表</dt><dd>{escape(public_text(item.get('what_it_means', ''), max_len=320))}</dd>
    <dt>下一步</dt><dd>{escape(public_text(item.get('next_action', ''), max_len=320))}</dd>
  </dl>
</article>"""


def render_lead_section(analysis: dict[str, Any]) -> str:
    lead = analysis["lead_operator_analysis"]
    narrative = analysis.get("report_writer_narrative") or {}
    cards = narrative.get("analysis_cards") or [
        {"title": "市场是否值得继续看", "body": " ".join(lead["market_read"][:2])},
        {"title": "产品机会在哪里", "body": " ".join(lead["product_read"][:2])},
        {"title": "供应链现在能说明什么", "body": " ".join(lead["supply_read"][:2])},
        {"title": "为什么还不能直接立项", "body": "；".join(lead["why_not_strong_go_yet"][:3])},
    ]
    headline = narrative.get("headline") or lead["headline"]
    principle = narrative.get("principle") or "数据多不是为了把报告写复杂，而是为了少踩坑；利润、合规和样品证据没闭环前，不直接立项。"
    thesis_html = (
        narrative_paragraphs(narrative.get("one_sentence") or analysis["one_sentence_conclusion"], max_chunks=2, max_len=520)
        + narrative_paragraphs(principle, class_name="analysis-principle", max_chunks=2, max_len=520)
        + narrative_paragraphs(narrative.get("review_reader_note"), max_chunks=3, max_len=820)
    )
    return f"""
<section class="section ai-analysis" id="ai-analysis">
  <div class="section-head">
    <p class="eyebrow">AI 综合分析</p>
    <h2>先说判断，再看证据</h2>
    <p>下面这块只讲运营能直接用来判断的内容，详细来源放在后面的数据章节和证据审计里。</p>
  </div>
  <div class="analysis-thesis">
    <div class="analysis-persona">资深亚马逊运营专家视角</div>
    <strong>{escape(headline)}</strong>
    <div class="analysis-copy analysis-copy-thesis">{thesis_html}</div>
  </div>
  <div class="analysis-grid">
    {''.join(analysis_card(card.get('title', ''), card.get('body', '')) for card in cards)}
  </div>
  <article class="panel">
    <h3>路线怎么取舍</h3>
    {simple_table(['路线', '当前判断', '运营解读', '价格/销量/评论'], [
        [
            row.get('route_name', ''),
            row.get('decision', ''),
            row.get('operator_read', ''),
            f"${fmt_number((row.get('price_band_usd') or {}).get('avg'))} / 月销 {fmt_number(row.get('avg_monthly_units'))} / 中位评论 {fmt_number(row.get('median_rating_count'))}",
        ]
        for row in analysis['route_judgment']
    ])}
  </article>
</section>"""


def render_market_section(analysis: dict[str, Any]) -> str:
    seller = analysis["seller_sprite_validation"]
    market = seller["primary_market"]
    price = seller["price_band"]
    review = seller["review_threshold"]
    metric_rows = [
        ["主市场样本数", market.get("sample_count", ""), market.get("label", "目标市场")],
        ["月均销量", market.get("avg_monthly_units", ""), "主市场概览"],
        ["月均销售额", market.get("avg_monthly_revenue_usd", ""), "USD"],
        ["平均价格", market.get("avg_price_usd", ""), "USD"],
        ["<$15 销量占比", fmt_percent((price.get("under_15") or {}).get("unit_share")), "低价销量主导"],
        ["$30+ 销量占比", fmt_percent((price.get("30_plus") or {}).get("unit_share")), "高客单存在但不是主销量段"],
        ["500+ 评论销量占比", fmt_percent((review.get("500_plus_reviews") or {}).get("unit_share")), "评论壁垒明显"],
    ]
    route_rows = []
    for route in seller["route_market_fit"]:
        facts = route.get("facts") if isinstance(route.get("facts"), dict) else {}
        route_rows.append(
            [
                route.get("route_name", ""),
                f"${fmt_number(facts.get('price_min_usd'))}-${fmt_number(facts.get('price_max_usd'))}",
                fmt_number(facts.get("avg_monthly_units")),
                fmt_number(facts.get("median_rating_count")),
                route.get("status_from_route_matrix", route.get("status", "")),
            ]
        )
    return f"""
<section class="section" id="market">
  <div class="section-head">
    <p class="eyebrow">卖家精灵关键词与竞品验证</p>
    <h2>先看市场底盘和路线门槛</h2>
    <p>{escape(seller['summary'])}</p>
  </div>
  <div class="two-col">
    <article class="panel">
      <h3>卖家精灵市场结构</h3>
      {simple_table(['指标', '值', '解读'], metric_rows)}
    </article>
    <article class="panel">
      <h3>路线代表样本</h3>
      {simple_table(['路线', '价格窗', '月均销量', '中位评论', '状态'], route_rows)}
    </article>
  </div>
</section>"""


def render_reference_asin_section(analysis: dict[str, Any]) -> str:
    rows = [
        [
            item.get("asin", ""),
            item.get("route_ref", ""),
            item.get("asin_role", ""),
            item.get("similarity_reason", ""),
            item.get("category_path", ""),
            item.get("price", ""),
            item.get("monthly_sales", ""),
            item.get("rating_count", ""),
        ]
        for item in as_list(analysis.get("reference_asin_pool"))
    ]
    return f"""
<section class="section" id="reference-asins">
  <div class="section-head">
    <p class="eyebrow">参考 ASIN 池</p>
    <h2>先看竞品是否真的相似</h2>
    <p>参考 ASIN 用来反推大小类目、反查关键词、确认价格带和评论门槛；不是随便找几个高销量商品。</p>
  </div>
  {simple_table(['ASIN', '路线', '角色', '相似/排除理由', '类目路径', '价格', '月销量', '评论数'], rows)}
</section>"""


def render_category_opportunity_section(analysis: dict[str, Any]) -> str:
    data = analysis.get("category_opportunity") or {}
    categories = [
        [
            row.get("category_name", ""),
            row.get("node_id", ""),
            row.get("category_role", ""),
            row.get("source_type", ""),
            row.get("matched_asin_count", ""),
            row.get("evidence_strength", ""),
            row.get("recommended_use", ""),
            row.get("risk_tags", ""),
        ]
        for row in as_list(data.get("category_candidates"))
    ]
    price_rows = [
        [
            row.get("category_ref", ""),
            row.get("price_band", ""),
            row.get("product_count", ""),
            fmt_percent(row.get("sales_share")),
            fmt_percent(row.get("revenue_share")),
            row.get("median_rating_count", ""),
            fmt_percent(row.get("top3_product_share")),
            fmt_percent(row.get("top3_brand_share")),
            row.get("new_release_count", ""),
            row.get("opportunity_level", ""),
            row.get("reason", ""),
        ]
        for row in as_list(data.get("price_band_opportunity"))
    ]
    new_rows = [
        [
            row.get("category_ref", ""),
            row.get("new_release_count", ""),
            fmt_percent(row.get("new_release_sales_share")),
            fmt_percent(row.get("new_release_revenue_share")),
            join_text(row.get("low_review_samples")),
            row.get("ranking_entry_signal", ""),
            row.get("new_release_opportunity_score", ""),
            row.get("new_release_opportunity_level", ""),
            row.get("score_reason", ""),
            join_text(row.get("risk_tags")),
        ]
        for row in as_list(data.get("new_release_opportunity"))
        if isinstance(row, dict)
    ]
    seasonality_rows = [
        [
            row.get("category_ref", ""),
            row.get("category_role", ""),
            row.get("trend_source", ""),
            row.get("trend_index", ""),
            row.get("peak_months", ""),
            row.get("low_months", ""),
            row.get("seasonality_level", ""),
            row.get("trend_direction", ""),
            row.get("keyword_heat_note", ""),
            row.get("category_seasonality_note", ""),
        ]
        for row in as_list(data.get("category_seasonality"))
    ]
    return f"""
<section class="section" id="category-opportunity">
  <div class="section-head">
    <p class="eyebrow">大小类目与小类机会</p>
    <h2>大类看容量，小类看进入机会</h2>
    <p>{escape(data.get('summary', '类目机会待补。'))}</p>
  </div>
  <article class="panel">
    <h3>候选类目池</h3>
    {simple_table(['类目', 'nodeId', '角色', '来源', '命中 ASIN', '证据强度', '推荐用途', '风险标签'], categories)}
  </article>
  <article class="panel">
    <h3>价格带机会</h3>
    {simple_table(['类目/路线', '价格段', '商品数', '销量占比', '销售额占比', '评论中位数', 'Top3商品占比', 'Top3品牌占比', '新品数', '机会', '说明'], price_rows)}
  </article>
  <article class="panel">
    <h3>新品机会</h3>
    {simple_table(['类目/路线', '新品数', '新品销量占比', '新品销售额占比', '低评论样本', '新品榜信号', '机会分', '机会等级', '评分原因', '风险'], new_rows)}
  </article>
  <article class="panel">
    <h3>类目淡旺季</h3>
    {simple_table(['类目/路线', '类目角色', '来源', '指标', '旺季月份', '淡季月份', '季节性', '趋势', '关键词热度备注', '类目备注'], seasonality_rows)}
  </article>
</section>"""


def render_keyword_pool_section(analysis: dict[str, Any]) -> str:
    data = analysis.get("keyword_pool") or {}
    roles = data.get("roles") or {}
    mix_summary = data.get("mix_pool_summary") or {}
    role_labels = {
        "main_traffic": "主要流量词",
        "conversion_quality": "转化优质词",
        "traffic": "流量词",
        "precise_long_tail": "精准长尾词",
        "mixed_or_excluded": "混池/排除词",
    }
    blocks = []
    for role, label in role_labels.items():
        rows = [
            [
                row.get("keyword", ""),
                row.get("source_type", ""),
                row.get("matched_asin_count", ""),
                row.get("monthly_search_volume", ""),
                row.get("cpc", ""),
                row.get("competition_count", ""),
                row.get("mix_pool_tags", ""),
                row.get("mix_pool_score", ""),
                row.get("mix_pool_risk_level", ""),
                row.get("recommended_action", ""),
                row.get("reason", ""),
            ]
            for row in as_list(roles.get(role))[:20]
        ]
        blocks.append(
            f"""
<article class="panel">
  <h3>{escape(label)}</h3>
  {simple_table(['关键词', '来源', '命中 ASIN', '月搜', 'CPC', '竞争量', '混池标签', '混池分', '风险', '动作', '原因'], rows)}
</article>"""
        )
    return f"""
<section class="section" id="keyword-pool">
  <div class="section-head">
    <p class="eyebrow">运营式关键词池</p>
    <h2>关键词要分角色，不能混成一张大表</h2>
    <p>{escape(data.get('summary', '关键词池待补。'))} 混池高风险 {escape(str(mix_summary.get('high_risk_count', 0)))} 个，中风险 {escape(str(mix_summary.get('medium_risk_count', 0)))} 个。</p>
  </div>
  {''.join(blocks)}
</section>"""


def render_sorftime_section(analysis: dict[str, Any]) -> str:
    data = analysis["sorftime_market_validation"]
    keyword_rows = [
        [
            row.get("keyword", ""),
            f"月搜 {fmt_number(row.get('monthly_search_volume'))}",
            f"CPC ${fmt_number(row.get('cpc'))}" if row.get("cpc") not in (None, "") else "CPC 待补",
            f"竞品 {fmt_number(row.get('competitor_count'))}",
            row.get("seasonality", ""),
            row.get("route_relevance", ""),
        ]
        for row in data["keyword_demand"][:10]
    ]
    category_cards = "".join(category_fact_card(row) for row in data["category_background"][:4]) or empty_state("类目背景待补。")
    traffic_cards = "".join(traffic_group_card(group) for group in data["traffic_term_groups"][:4]) or empty_state("竞品流量词待补。")
    trend = data.get("trend_signal") or {}
    trend_text = trend.get("summary") or (trend.get("handoff_read") if isinstance(trend, dict) else "") or "趋势证据待补。"
    return f"""
<section class="section sorftime-section" id="sorftime">
  <div class="section-head wide">
    <p class="eyebrow">Sorftime 市场验证</p>
    <h2>Sorftime 实时验证</h2>
    <p>用实时关键词、类目和产品流量词校验需求强度、混池边界和代表竞品入口。</p>
  </div>
  <div class="sorftime-stack">
    <article class="panel">
      <h3>关键词需求</h3>
      {simple_table(['关键词', '月搜索量', 'CPC', '竞争量', '旺季', '运营解读'], keyword_rows)}
    </article>
    <article class="panel">
      <h3>类目背景</h3>
      <div class="fact-grid category-grid">{category_cards}</div>
    </article>
    <article class="panel">
      <h3>趋势提醒</h3>
      <p>{escape(public_text(trend_text))}</p>
    </article>
  </div>
  <article class="panel">
    <h3>竞品流量词</h3>
    <div class="traffic-grid">{traffic_cards}</div>
  </article>
</section>"""


def render_voc_section(analysis: dict[str, Any]) -> str:
    data = analysis["voc_spec_translation"]
    pain_rows = sorted(data["pain_points"], key=lambda row: row.get("low_rating_hits", 0), reverse=True)
    spec_rows = [
        [
            item.get("pain_dimension", ""),
            item.get("fact_observation", ""),
            join_text(item.get("spec_requirement")),
            join_text(item.get("sample_tests")),
        ]
        for item in data.get("spec_rows", [])
    ]
    coverage_rows = [
        [
            item.get("asin", ""),
            item.get("route_role", item.get("role", "")),
            item.get("impact", item.get("reason", "")),
        ]
        for item in data.get("coverage_gap", [])
    ]
    return f"""
<section class="section" id="voc">
  <div class="section-head">
    <p class="eyebrow">VOC 差评痛点与规格翻译</p>
    <h2>买家差评在提醒我们哪些规格不能省</h2>
    <p>{escape(data['summary'])}</p>
  </div>
  {simple_table(['痛点维度', '关键词命中', '低分命中', '运营解读'], [
      [row.get('dimension', ''), row.get('keyword_hits', ''), row.get('low_rating_hits', ''), row.get('inference', row.get('fact_summary', ''))]
      for row in pain_rows
  ])}
  <article class="panel">
    <h3>把差评翻译成打样检查项</h3>
    {simple_table(['痛点', '评论事实', '供应商规格要问什么', '样品要测什么'], spec_rows)}
  </article>
  {f"<article class=\"panel warn\"><h3>评论覆盖缺口</h3>{simple_table(['未覆盖 ASIN', '路线角色', '对判断的影响'], coverage_rows)}</article>" if coverage_rows else ""}
</section>"""


def render_supply_section(analysis: dict[str, Any]) -> str:
    data = analysis["supply_chain_match"]
    candidates = data["recommended_candidates"]
    candidate_rows = [
        [
            item.get("review_priority", ""),
            link(item.get("offer_id", ""), item.get("url", "")),
            item.get("title", ""),
            fmt_rmb(item.get("price_rmb_conservative")),
            item.get("moq_text", ""),
            item.get("stage7_review_reason", ""),
            join_text(item.get("must_verify_before_use")),
        ]
        for item in candidates
    ]
    coverage_rows = [
        [
            row.get("voc_dimension", ""),
            row.get("coverage_status", ""),
            row.get("current_supply_coverage", ""),
            join_text(row.get("unverified_specs")),
        ]
        for row in data["voc_spec_coverage"]
    ]
    return f"""
<section class="section" id="supply">
  <div class="section-head">
    <p class="eyebrow">1688 候选款 / 候选供应商</p>
    <h2>先看这些候选，再决定是否去聊供应商</h2>
    <p>{escape(data['summary'])}</p>
  </div>
  <div class="notice">这些不是“已推荐下单供应商”，而是优先 review 清单。你需要先打开链接看图、SKU、规格和包装，再决定是否问价或打样。</div>
  <div class="supplier-grid">
    {''.join(candidate_card(item) for item in candidates[:8])}
  </div>
  <article class="panel">
    <h3>候选明细表</h3>
    {simple_table(['优先级', 'Offer', '标题', '保守价', 'MOQ', '推荐理由', '必须验证'], candidate_rows)}
  </article>
  <article class="panel">
    <h3>供应链能覆盖哪些 VOC 规格</h3>
    {simple_table(['VOC 维度', '覆盖状态', '当前供应信号', '未验证规格'], coverage_rows)}
  </article>
</section>"""


def render_audit_section(analysis: dict[str, Any]) -> str:
    return f"""
<section class="section appendix" id="audit">
  <div class="section-head">
    <p class="eyebrow">证据审计</p>
    <h2>数据从哪里来</h2>
    <p>这部分给你核对来源和流程用，不参与前面的运营阅读主线。</p>
  </div>
    {simple_table(['数据源', '判断', '给报告的关键信息'], [
      [source_label(row.get('agent', '')), row.get('judgment', ''), row.get('handoff', '')]
      for row in analysis['multi_agent_synthesis']
  ])}
  <article class="panel">
    <h3>证据包执行来源</h3>
    <div class="audit-grid">
      {''.join(audit_source_card(row) for row in analysis['source_packets'])}
    </div>
  </article>
</section>"""


def audit_source_card(row: dict[str, Any]) -> str:
    mode = execution_mode_label(row.get("execution_mode", "未标注"))
    source = source_label(row.get("name", ""))
    role = source_label(row.get("agent_role", "")) or "来源模块待标注"
    status = "来源已记录" if row.get("execution_mode") else "来源未记录"
    subtask = row.get("subagent_id") or "未记录"
    note = public_provenance_note(row)
    return f"""
<article class="audit-card">
  <div class="audit-topline">
    <strong>{escape(source)}</strong>
    <span>{escape(status)}</span>
  </div>
  <div class="audit-meta">
    <span>{escape(role)}</span>
    <span>{escape(mode)}</span>
    <span>任务记录：{escape(str(subtask))}</span>
  </div>
  <p>{escape(note)}</p>
</article>"""


def render_review_section(analysis: dict[str, Any]) -> str:
    return f"""
<section class="section" id="review">
  <div class="section-head">
    <p class="eyebrow">你人工 review 时重点看什么</p>
    <h2>你自己打开链接时，先看这些</h2>
  </div>
  {simple_table(['重点', '为什么看', '证据来源'], [
      [row.get('focus', ''), row.get('why', ''), row.get('evidence', '')]
      for row in analysis['human_review_focus']
  ])}
</section>"""


def render_profit_section(analysis: dict[str, Any]) -> str:
    location = analysis["profit_backfill_location"]
    rows = [
        [field["field"], field["label"], field["where"], field["required"], field["source_hint"], field["note"]]
        for field in analysis["profit_backfill_fields"]
    ]
    return f"""
<section class="section" id="profit">
  <div class="section-head">
    <p class="eyebrow">利润回填字段在哪里、需要填哪些</p>
    <h2>review 完后，利润从这里开始补</h2>
    <p>{escape(location['where_to_fill'])}</p>
  </div>
  <div class="notice">{escape(location['rule'])}</div>
  {simple_table(['字段', '含义', '回填位置', '必填', '来源提示', '说明'], rows)}
</section>"""


def render_next_section(analysis: dict[str, Any]) -> str:
    return f"""
<section class="section" id="next">
  <div class="section-head">
    <p class="eyebrow">下一步进入利润/FBA/合规的条件</p>
    <h2>什么情况下进入下一步</h2>
  </div>
  {simple_table(['条件', '当前状态', '为什么需要'], [
      [row.get('condition', ''), row.get('status', ''), row.get('why', '')]
      for row in analysis['next_stage_entry_conditions']
  ])}
</section>"""


def metric_card(label: str, value: str, note: str) -> str:
    return f"""
<div class="metric">
  <div class="metric-label">{escape(str(label))}</div>
  <div class="metric-value">{escape(str(value))}</div>
  <div class="metric-note">{escape(str(note))}</div>
</div>"""


def split_narrative_text(text: str) -> list[str]:
    value = str(text or "").strip()
    if not value:
        return []
    pieces = [piece.strip() for piece in re.split(r"(?<=[。！？；;])\s*", value) if piece.strip()]
    if len(pieces) == 1 and len(pieces[0]) > 180:
        pieces = [piece.strip() for piece in re.split(r"(?<=，)\s*", pieces[0]) if piece.strip()]
    chunks: list[str] = []
    current = ""
    for piece in pieces:
        if not current:
            current = piece
        elif len(current) + len(piece) <= 190:
            current += piece
        else:
            chunks.append(current)
            current = piece
    if current:
        chunks.append(current)
    return chunks


def split_reading_points(text: Any, max_len: int = 900) -> list[str]:
    value = public_text(text, max_len=max_len)
    if not value:
        return []
    value = re.sub(r"(?<!^)(第[一二三四五六七八九十]+[，,])", r"|\1", value)
    raw_parts: list[str] = []
    for block in value.split("|"):
        raw_parts.extend(piece.strip() for piece in re.split(r"(?<=[。！？；;])\s*", block) if piece.strip())
    points: list[str] = []
    for piece in raw_parts:
        if len(piece) <= 150:
            points.append(piece)
            continue
        comma_parts = [part.strip() for part in re.split(r"(?<=，)\s*", piece) if part.strip()]
        current = ""
        for part in comma_parts:
            if not current:
                current = part
            elif len(current) + len(part) <= 130:
                current += part
            else:
                points.append(current)
                current = part
        if current:
            points.append(current)
    return points


def narrative_paragraphs(text: Any, class_name: str = "", max_chunks: int = 4, max_len: int = 760) -> str:
    chunks = split_narrative_text(public_text(text, max_len=max_len))
    if max_chunks:
        chunks = chunks[:max_chunks]
    if not chunks:
        return ""
    class_attr = f' class="{escape(class_name, quote=True)}"' if class_name else ""
    return "".join(f"<p{class_attr}>{escape(chunk)}</p>" for chunk in chunks)


def analysis_card(title: str, text: str) -> str:
    chunks = split_reading_points(text, max_len=900)[:6]
    lead = chunks[0] if chunks else ""
    support = chunks[1:] or chunks[:1]
    return f"""
<article class="analysis-card">
  <div class="analysis-card-title">{escape(title)}</div>
  <p class="analysis-card-lead">{escape(lead)}</p>
  <div class="analysis-points">
    {''.join(f"<div><span>{escape(analysis_point_label(index))}</span><p>{escape(chunk)}</p></div>" for index, chunk in enumerate(support[:4]))}
  </div>
</article>"""


def analysis_point_label(index: int) -> str:
    labels = ["证据", "风险", "动作", "补证"]
    return labels[index] if index < len(labels) else "补充"


def candidate_card(item: dict[str, Any]) -> str:
    checks = as_list(item.get("must_verify_before_use"))[:3]
    tags = as_list((item.get("supplier_signals") or {}).get("tags"))[:4]
    tag_html = "".join(f"<span>{escape(str(tag))}</span>" for tag in tags)
    checks_html = bullet_list(checks or ["确认最终 SKU/BOM、真实报价、包装尺寸重量和样品表现。"])
    offer = item.get("offer_id", "")
    title = item.get("title", "候选款")
    url = item.get("url", "")
    offer_link = link(offer or title, url)
    offer_html = offer_link.value if isinstance(offer_link, Html) else escape(str(offer_link))
    return f"""
<article class="supplier-card">
  <div class="supplier-body">
    <div class="supplier-topline">
      <span class="rank-pill">#{escape(str(item.get('review_priority', '')))}</span>
      <span class="status-pill">{escape(public_text(item.get('recommendation_level', '优先 review')))}</span>
      <span>{escape(public_text(item.get('visual_review_status', '待复核')))}</span>
      {f"<span>{escape(image_url_status_label(item.get('image_url_status')))}</span>" if item.get('image_url_status') else ""}
    </div>
    <div class="supplier-title-block">
      <h3>{offer_html}</h3>
      <p>{escape(public_text(title, max_len=240))}</p>
    </div>
    <div class="supplier-stats">
      <div><span>保守采购价</span><strong>{escape(fmt_rmb(item.get('price_rmb_conservative')))}</strong></div>
      <div><span>MOQ</span><strong>{escape(str(item.get('moq_text', '待确认')))}</strong></div>
    </div>
    <div class="tag-row">{tag_html or '<span>标签待确认</span>'}</div>
    <div class="supplier-reason"><strong>为什么先看它</strong><span>{escape(str(item.get('stage7_review_reason', '')))}</span></div>
    <div class="supplier-check"><strong>打开页面重点确认</strong>{checks_html}</div>
  </div>
</article>"""


def image_url_status_label(status: Any) -> str:
    labels = {
        "accessible": "图片链接可访问",
        "inaccessible": "图片链接失效",
        "blocked": "图片访问被拦截",
        "not_provided": "未提供图片链接",
    }
    return labels.get(str(status), str(status))


def category_fact_card(row: dict[str, Any]) -> str:
    title = row.get("category") or "类目"
    subtitle = f"nodeId {row.get('node_id')}" if row.get("node_id") else "nodeId 待补"
    stats = [
        ("Top100 月销量", fmt_number(row.get("top100_monthly_units"))),
        ("均价", f"${fmt_number(row.get('average_price_usd'))}" if row.get("average_price_usd") not in (None, "") else "待补"),
        ("中位价", f"${fmt_number(row.get('median_price_usd'))}" if row.get("median_price_usd") not in (None, "") else "待补"),
        ("Top3 占比", row.get("top3_share") or "待补"),
        ("自营占比", row.get("amazon_owned_share") or "待补"),
        ("低评销量占比", row.get("low_review_share") or "待补"),
    ]
    stats_html = "".join(f"<div><span>{escape(label)}</span><strong>{escape(str(value))}</strong></div>" for label, value in stats)
    return f"""
<div class="fact-card">
  <span>类目</span>
  <strong>{escape(str(title))}</strong>
  <em>{escape(str(subtitle))}</em>
  <div class="mini-facts">{stats_html}</div>
  <p>{escape(public_text(row.get('interpretation', '')))}</p>
</div>"""


def traffic_group_card(group: dict[str, Any]) -> str:
    asins = as_list(group.get("asins"))[:4]
    cards = []
    for asin_row in asins:
        positive = ", ".join(
            str(term.get("keyword", ""))
            for term in as_list(asin_row.get("positive_terms"))[:5]
            if term.get("keyword")
        )
        noise = ", ".join(str(term) for term in as_list(asin_row.get("noise_terms"))[:5] if str(term))
        cards.append(
            f"""
<div class="traffic-card">
  <strong>{escape(str(asin_row.get('asin', 'ASIN 待补')))}</strong>
  <span>{escape(str(asin_row.get('role', '代表样本')))}</span>
  <p>{escape(positive or '正向流量词待补')}</p>
  {f'<em>混池：{escape(noise)}</em>' if noise else ''}
</div>"""
        )
    return f"""
<div class="traffic-group">
  <div class="traffic-read">{escape(public_text(group.get('traffic_read', '')))}</div>
  <div class="traffic-cards">{''.join(cards) or empty_state('ASIN 流量词待补。')}</div>
</div>"""


def empty_state(text: str) -> str:
    return f"<div class=\"empty-state\">{escape(text)}</div>"


def bullet_list(items: list[Any]) -> str:
    lis = "".join(f"<li>{escape(public_text(item))}</li>" for item in items if str(item))
    return f"<ul>{lis}</ul>"


def simple_table(headers: list[str], rows: list[list[Any]]) -> str:
    header_html = "".join(f"<th>{escape(str(header))}</th>" for header in headers)
    body_rows = []
    for row in rows:
        cells = []
        for cell in row:
            if isinstance(cell, Html):
                cells.append(f"<td>{cell.value}</td>")
            else:
                cells.append(f"<td>{escape(public_text(cell))}</td>")
        body_rows.append(f"<tr>{''.join(cells)}</tr>")
    return f"""
<div class="table-wrap">
  <table>
    <thead><tr>{header_html}</tr></thead>
    <tbody>{''.join(body_rows)}</tbody>
  </table>
</div>"""


class Html:
    def __init__(self, value: str) -> None:
        self.value = value


def link(label: Any, url: Any) -> Html | str:
    if not url:
        return str(label or "")
    return Html(f'<a href="{escape(str(url), quote=True)}" target="_blank" rel="noreferrer">{escape(str(label or url))}</a>')


def report_subject(analysis: dict[str, Any]) -> str:
    route = (analysis.get("route_judgment") or [{}])[0].get("route_name")
    market = (analysis.get("seller_sprite_validation") or {}).get("primary_market", {}).get("label")
    if route:
        return f"{route} / 选品综合预审"
    if market:
        return f"{market} / 选品综合预审"
    return "选品综合预审报告"


def first_keyword(keyword_rows: list[dict[str, Any]]) -> str:
    ranked = sorted(
        [row for row in keyword_rows if isinstance(row.get("value"), (int, float))],
        key=lambda row: float(row.get("value") or 0),
        reverse=True,
    )
    row = ranked[0] if ranked else (keyword_rows[0] if keyword_rows else {})
    return str(row.get("subject") or "核心关键词")


def first_text(rows: list[Any], key: str) -> str:
    for row in rows:
        if isinstance(row, dict) and row.get(key):
            return str(row.get(key))
        if isinstance(row, str) and row:
            return row
    return ""


def source_label(value: Any) -> str:
    text = str(value)
    replacements = {
        "Sorftime / Search Demand": "Sorftime 搜索需求",
        "Search Demand / Sorftime": "Sorftime 搜索需求",
        "卖家精灵 / Market Structure": "卖家精灵市场结构",
        "Market Structure / 卖家精灵": "卖家精灵市场结构",
        "VOC Evidence": "评论 VOC",
        "Supply Chain / 1688": "1688 供应链",
        "1688 / Supply Chain": "1688 供应链",
        "Lead Operator": "AI 综合判断",
        "Route Matrix": "路线矩阵",
        "Search Demand Agent": "Sorftime 搜索需求",
        "Market Structure Agent": "卖家精灵市场结构",
        "VOC Evidence Agent": "评论 VOC",
        "Supply Chain Agent": "1688 供应链",
        "Lead Operator Agent": "AI 综合判断",
    }
    return replacements.get(text, text)


def execution_mode_label(value: Any) -> str:
    text = str(value)
    replacements = {
        "real_subagent_spawn": "独立数据复核",
        "serial_fallback": "主流程降级执行",
        "script_generated": "脚本生成",
        "legacy_import": "历史导入",
        "": "未标注",
        "未标注": "未标注",
    }
    return replacements.get(text, text)


def public_provenance_note(item: dict[str, Any]) -> str:
    if item.get("executed_by_agent") is True:
        source = source_label(item.get("agent_role") or item.get("name") or "该模块")
        return f"{source}已完成独立数据复核；本报告仅把它作为证据输入，最终结论仍由综合分析生成。"
    note = str(item.get("provenance_note") or "")
    replacements = {
        "Search Demand Agent": "Sorftime 搜索需求复核",
        "Market Structure Agent": "卖家精灵市场结构复核",
        "VOC Evidence Agent": "评论 VOC 复核",
        "Supply Chain Agent": "1688 供应链复核",
        "Lead Operator Agent": "AI 综合判断模块",
        "主 Agent": "主流程",
        "Go/No-Go": "最终立项判断",
        "GO/NO-GO": "最终立项判断",
    }
    for old, new in replacements.items():
        note = note.replace(old, new)
    if note:
        return clean_sentence(note)
    if item.get("execution_mode"):
        return "来源模式已记录；本报告只读取该证据包，不改变原始数据。"
    return "来源记录缺失；这是系统侧审计元数据缺口，不是用户需要补的业务数据。"


def public_text(text: Any, max_len: int = 420) -> str:
    value = clean_sentence(text, max_len=max_len)
    if not value:
        return ""
    replacements = {
        "pending_human_visual_and_sample_review": "待人工视觉和样品复核",
        "pending_visual_review": "待视觉复核",
        "category_search_from_product_name": "Sorftime 类目搜索",
        "category_report": "Sorftime 类目 Top100 报告",
        "competitor_product_keywords": "竞品关键词反查",
        "product_traffic_terms": "ASIN 流量词反查",
        "similar_product_feature": "相似产品特征分析",
        "ali1688_similar_product": "1688 相似货源搜索",
        "Stage 8/9": "利润、FBA 和合规复核",
        "Stage 8": "利润/FBA/合规复核",
        "Stage 9": "最终决策复核",
        "Wait": "暂不推进",
        "operator_notes": "运营备注",
    }
    for old, new in replacements.items():
        value = value.replace(old, new)
    value = re.sub(r"runs/[^\\s；，。]+", "历史快照", value)
    value = re.sub(r"page\\s*=\\s*\\d+", "部分页码", value)
    value = re.sub(r"\\bMCP\\b", "工具", value)
    return value


def clean_sentence(text: Any, max_len: int = 420) -> str:
    value = " ".join(str(text or "").split())
    if len(value) <= max_len:
        return value
    return value[: max_len - 1].rstrip() + "..."


def build_workbook_sheets(analysis: dict[str, Any]) -> list[tuple[str, list[list[object]]]]:
    return [
        ("Executive Summary", executive_summary_rows(analysis)),
        ("Route Matrix", route_matrix_rows(analysis)),
        ("Reference ASINs", reference_asin_rows(analysis)),
        ("Category Candidates", category_candidate_rows(analysis)),
        ("Keyword Pool", keyword_pool_rows(analysis)),
        ("Price Bands", price_band_rows(analysis)),
        ("Sorftime", sorftime_rows(analysis)),
        ("SellerSprite", seller_sprite_rows(analysis)),
        ("VOC Spec Map", voc_rows(analysis)),
        ("1688 Candidates", supply_rows(analysis)),
        ("Evidence Audit", agent_handoff_rows(analysis)),
        ("Profit Backfill", profit_backfill_rows(analysis)),
    ]


def executive_summary_rows(analysis: dict[str, Any]) -> list[list[object]]:
    return [
        ["Field", "Value", "Note"],
        ["Run ID", analysis["run_id"], ""],
        ["Verdict", analysis["verdict"], "继续看 / 谨慎继续 / 暂缓"],
        ["One Sentence Conclusion", analysis["one_sentence_conclusion"], ""],
        ["Confidence", analysis["confidence"], ""],
        ["Lead Persona", analysis["persona"], ""],
        ["Profit Backfill Location", analysis["profit_backfill_location"]["where_to_fill"], ""],
        ["Next Rule", analysis["profit_backfill_location"]["rule"], ""],
    ]


def route_matrix_rows(analysis: dict[str, Any]) -> list[list[object]]:
    rows = [["route_id", "route_name", "decision", "operator_read", "avg_price_usd", "avg_monthly_units", "median_rating_count", "representative_asins"]]
    for row in analysis["route_judgment"]:
        rows.append(
            [
                row.get("route_id", ""),
                row.get("route_name", ""),
                row.get("decision", ""),
                row.get("operator_read", ""),
                (row.get("price_band_usd") or {}).get("avg", ""),
                row.get("avg_monthly_units", ""),
                row.get("median_rating_count", ""),
                ", ".join(map(str, row.get("representative_asins", []))),
            ]
        )
    return rows


def reference_asin_rows(analysis: dict[str, Any]) -> list[list[object]]:
    rows = [["asin", "route_ref", "asin_role", "similarity_reason", "category_path", "category_role", "price", "monthly_sales", "rating_count", "lineage"]]
    for item in as_list(analysis.get("reference_asin_pool")):
        rows.append(
            [
                item.get("asin", ""),
                item.get("route_ref", ""),
                item.get("asin_role", ""),
                item.get("similarity_reason", ""),
                item.get("category_path", ""),
                item.get("category_role", ""),
                item.get("price", ""),
                item.get("monthly_sales", ""),
                item.get("rating_count", ""),
                join_text(item.get("lineage")) if isinstance(item.get("lineage"), list) else item.get("lineage", ""),
            ]
        )
    return rows


def category_candidate_rows(analysis: dict[str, Any]) -> list[list[object]]:
    data = analysis.get("category_opportunity") or {}
    rows = [["category_name", "node_id", "category_path", "category_role", "source_type", "matched_asin_count", "evidence_strength", "recommended_use", "risk_tags", "lineage"]]
    for item in as_list(data.get("category_candidates")):
        rows.append(
            [
                item.get("category_name", ""),
                item.get("node_id", ""),
                item.get("category_path", ""),
                item.get("category_role", ""),
                item.get("source_type", ""),
                item.get("matched_asin_count", ""),
                item.get("evidence_strength", ""),
                item.get("recommended_use", ""),
                item.get("risk_tags", ""),
                join_text(item.get("lineage")) if isinstance(item.get("lineage"), list) else item.get("lineage", ""),
            ]
        )
    rows.append([])
    rows.append(["asin", "route_ref", "category_path", "node_id", "bsr_rank", "category_role", "mapping_source", "conflict_note"])
    for item in as_list(data.get("asin_category_mapping")):
        if not isinstance(item, dict):
            continue
        rows.append(
            [
                item.get("asin", ""),
                item.get("route_ref", ""),
                item.get("category_path", ""),
                item.get("node_id", item.get("nodeId", "")),
                item.get("bsr_rank", ""),
                item.get("category_role", ""),
                item.get("mapping_source", ""),
                item.get("conflict_note", ""),
            ]
        )
    rows.append([])
    rows.append(["category_ref", "category_role", "trend_source", "trend_index", "peak_months", "low_months", "seasonality_level", "trend_direction", "keyword_heat_note", "category_seasonality_note", "lineage"])
    for item in as_list(data.get("category_seasonality")):
        if not isinstance(item, dict):
            continue
        rows.append(
            [
                item.get("category_ref", ""),
                item.get("category_role", ""),
                item.get("trend_source", ""),
                item.get("trend_index", ""),
                item.get("peak_months", ""),
                item.get("low_months", ""),
                item.get("seasonality_level", ""),
                item.get("trend_direction", ""),
                item.get("keyword_heat_note", ""),
                item.get("category_seasonality_note", ""),
                join_text(item.get("lineage")) if isinstance(item.get("lineage"), list) else item.get("lineage", ""),
            ]
        )
    return rows


def keyword_pool_rows(analysis: dict[str, Any]) -> list[list[object]]:
    roles = ((analysis.get("keyword_pool") or {}).get("roles") or {})
    rows = [["keyword_role", "keyword", "source_type", "matched_asin_count", "monthly_search_volume", "cpc", "competition_count", "mix_pool_tags", "mix_pool_score", "mix_pool_risk_level", "recommended_action", "reason", "lineage"]]
    for role, role_rows in roles.items():
        for item in as_list(role_rows):
            rows.append(
                [
                    role,
                    item.get("keyword", ""),
                    item.get("source_type", ""),
                    item.get("matched_asin_count", ""),
                    item.get("monthly_search_volume", ""),
                    item.get("cpc", ""),
                    item.get("competition_count", ""),
                    item.get("mix_pool_tags", ""),
                    item.get("mix_pool_score", ""),
                    item.get("mix_pool_risk_level", ""),
                    item.get("recommended_action", ""),
                    item.get("reason", ""),
                    join_text(item.get("lineage")) if isinstance(item.get("lineage"), list) else item.get("lineage", ""),
                ]
            )
    return rows


def price_band_rows(analysis: dict[str, Any]) -> list[list[object]]:
    data = analysis.get("category_opportunity") or {}
    rows = [["category_ref", "price_band", "product_count", "sales_share", "revenue_share", "median_rating_count", "top3_product_share", "top3_brand_share", "new_release_count", "low_review_winner_count", "opportunity_level", "reason", "lineage"]]
    for item in as_list(data.get("price_band_opportunity")):
        if not isinstance(item, dict):
            continue
        rows.append(
            [
                item.get("category_ref", ""),
                item.get("price_band", ""),
                item.get("product_count", ""),
                item.get("sales_share", ""),
                item.get("revenue_share", ""),
                item.get("median_rating_count", ""),
                item.get("top3_product_share", ""),
                item.get("top3_brand_share", ""),
                item.get("new_release_count", ""),
                item.get("low_review_winner_count", ""),
                item.get("opportunity_level", ""),
                item.get("reason", ""),
                join_text(item.get("lineage")) if isinstance(item.get("lineage"), list) else item.get("lineage", ""),
            ]
        )
    rows.append([])
    rows.append(["category_ref", "new_release_count", "new_release_sales_share", "new_release_revenue_share", "low_review_samples", "launch_period", "ranking_entry_signal", "new_release_opportunity_score", "new_release_opportunity_level", "score_reason", "risk_tags"])
    for item in as_list(data.get("new_release_opportunity")):
        if not isinstance(item, dict):
            continue
        rows.append(
            [
                item.get("category_ref", ""),
                item.get("new_release_count", ""),
                item.get("new_release_sales_share", ""),
                item.get("new_release_revenue_share", ""),
                join_text(item.get("low_review_samples")),
                item.get("launch_period", ""),
                item.get("ranking_entry_signal", ""),
                item.get("new_release_opportunity_score", ""),
                item.get("new_release_opportunity_level", ""),
                item.get("score_reason", ""),
                join_text(item.get("risk_tags")),
            ]
        )
    return rows


def sorftime_rows(analysis: dict[str, Any]) -> list[list[object]]:
    data = analysis["sorftime_market_validation"]
    rows = [["source", "subject", "metric", "value", "note"]]
    for row in data["keyword_rows"] + data["traffic_rows"] + data["feature_rows"] + data["supply_hint_rows"]:
        rows.append([row.get("source", ""), row.get("subject", ""), row.get("metric", ""), row.get("value", ""), row.get("note", "")])
    rows.append([])
    rows.append(["derived_metric", "value", "basis", "", ""])
    for item in data["derived_metrics"]:
        rows.append([item.get("name", item.get("metric", "")), item.get("value", ""), join_text(item.get("basis")), "", ""])
    return rows


def seller_sprite_rows(analysis: dict[str, Any]) -> list[list[object]]:
    data = analysis["seller_sprite_validation"]
    rows = [["type", "metric", "value", "note"]]
    for key, value in data["primary_market"].items():
        rows.append(["primary_market", key, value, ""])
    for band, value in data["price_band"].items():
        rows.append(["price_band", band, json.dumps(value, ensure_ascii=False), ""])
    for band, value in data["review_threshold"].items():
        rows.append(["review_threshold", band, json.dumps(value, ensure_ascii=False), ""])
    rows.append([])
    rows.append(["route", "price_min", "price_max", "avg_units", "median_rating_count", "status"])
    for route in data["route_market_fit"]:
        facts = route.get("facts") if isinstance(route.get("facts"), dict) else {}
        rows.append(
            [
                route.get("route_name", ""),
                facts.get("price_min_usd", ""),
                facts.get("price_max_usd", ""),
                facts.get("avg_monthly_units", ""),
                facts.get("median_rating_count", ""),
                route.get("status_from_route_matrix", route.get("status", "")),
            ]
        )
    return rows


def voc_rows(analysis: dict[str, Any]) -> list[list[object]]:
    data = analysis["voc_spec_translation"]
    rows = [["pain_dimension", "keyword_hits", "low_rating_hits", "fact_summary", "inferred_spec_requirement", "sample_tests", "supplier_validation"]]
    spec_by_dimension = {item.get("pain_dimension"): item for item in data.get("spec_rows", [])}
    for pain in data["pain_points"]:
        mapping = spec_by_dimension.get(pain.get("dimension"), {})
        rows.append(
            [
                pain.get("dimension", ""),
                pain.get("keyword_hits", ""),
                pain.get("low_rating_hits", ""),
                pain.get("fact_summary", ""),
                join_text(mapping.get("spec_requirement")),
                join_text(mapping.get("sample_tests")),
                join_text(mapping.get("supplier_validation")),
            ]
        )
    for item in data.get("coverage_gap", []):
        rows.append(
            [
                f"coverage_gap:{item.get('asin', '')}",
                "",
                "",
                item.get("impact", item.get("reason", "")),
                "",
                "",
                item.get("route_role", item.get("role", "")),
            ]
        )
    return rows


def supply_rows(analysis: dict[str, Any]) -> list[list[object]]:
    rows = [["priority", "offer_id", "title", "url", "price_rmb_conservative", "moq", "recommendation_level", "image_url_status", "reason", "must_verify"]]
    for item in analysis["supply_chain_match"]["recommended_candidates"]:
        rows.append(
            [
                item.get("review_priority", ""),
                item.get("offer_id", ""),
                item.get("title", ""),
                item.get("url", ""),
                item.get("price_rmb_conservative", ""),
                item.get("moq_text", ""),
                item.get("recommendation_level", ""),
                item.get("image_url_status", ""),
                item.get("stage7_review_reason", ""),
                join_text(item.get("must_verify_before_use")),
            ]
        )
    rows.append([])
    rows.append(["backup_offer_id", "title", "url", "price_rmb_conservative", "moq", "backup_reason"])
    for item in analysis["supply_chain_match"]["backup_candidates"]:
        rows.append(
            [
                item.get("offer_id", ""),
                item.get("title", ""),
                item.get("url", ""),
                item.get("price_rmb_conservative", ""),
                item.get("moq_text", ""),
                item.get("backup_reason", ""),
            ]
        )
    return rows


def agent_handoff_rows(analysis: dict[str, Any]) -> list[list[object]]:
    rows = [["数据源", "判断", "给报告的关键信息"]]
    for item in analysis["multi_agent_synthesis"]:
        rows.append([source_label(item.get("agent", "")), item.get("judgment", ""), item.get("handoff", "")])
    rows.append([])
    rows.append(["证据包", "路径", "证据包 ID", "负责模块", "是否存在", "执行来源", "是否独立执行", "子任务 ID", "说明"])
    for item in analysis["source_packets"]:
        provenance = item.get("execution_provenance") or {}
        rows.append(
            [
                source_label(item.get("name", "")),
                item.get("path", ""),
                item.get("packet_id", ""),
                source_label(item.get("agent_role", "")),
                item.get("exists", ""),
                execution_mode_label(item.get("execution_mode", "")),
                item.get("executed_by_agent", ""),
                item.get("subagent_id", ""),
                public_provenance_note(item),
            ]
        )
    return rows


def profit_backfill_rows(analysis: dict[str, Any]) -> list[list[object]]:
    rows = [["field", "label", "回填位置", "是否必填", "来源提示", "note"]]
    for item in analysis["profit_backfill_fields"]:
        rows.append([item["field"], item["label"], item["where"], item["required"], item["source_hint"], item["note"]])
    return rows


def evidence_packets_requiring_provenance(analysis: dict[str, Any]) -> list[dict[str, Any]]:
    packets = []
    for item in analysis.get("source_packets", []):
        packet_id = str(item.get("packet_id") or "")
        if packet_id.endswith("_evidence") or packet_id == "search_demand_evidence":
            packets.append(item)
    return packets


def provenance_is_recorded(item: dict[str, Any]) -> bool:
    provenance = item.get("execution_provenance") if isinstance(item.get("execution_provenance"), dict) else {}
    return bool(provenance.get("execution_mode") and provenance.get("agent_role"))


def run_delivery_qa(run_dir: Path, analysis: dict[str, Any], analysis_json: Path, html_path: Path, xlsx_path: Path) -> dict[str, Any]:
    checks = []
    warnings = []

    def add_check(name: str, passed: bool, detail: str = "") -> None:
        checks.append({"name": name, "passed": passed, "detail": detail})

    add_check("analysis JSON exists", analysis_json.exists(), str(analysis_json))
    add_check("HTML exists", html_path.exists(), str(html_path))
    add_check("XLSX exists", xlsx_path.exists() and xlsx_path.stat().st_size > 1000, str(xlsx_path))
    add_check("verdict allowed", analysis.get("verdict") in ALLOWED_VERDICTS, str(analysis.get("verdict")))
    add_check("not strong go", analysis.get("verdict") != "GO", str(analysis.get("verdict")))
    category_data = analysis.get("category_opportunity") if isinstance(analysis.get("category_opportunity"), dict) else {}
    keyword_data = analysis.get("keyword_pool") if isinstance(analysis.get("keyword_pool"), dict) else {}
    keyword_roles = keyword_data.get("roles") if isinstance(keyword_data.get("roles"), dict) else {}
    add_check("reference ASIN pool exists", bool(as_list(analysis.get("reference_asin_pool"))), "reference_asin_pool")
    add_check("category candidates exist", bool(as_list(category_data.get("category_candidates"))), "category_candidates")
    add_check("keyword pool by role exists", any(as_list(rows) for rows in keyword_roles.values()), "keyword_pool_by_role")
    add_check("price band opportunity exists", bool(as_list(category_data.get("price_band_opportunity"))), "price_band_opportunity")
    if not as_list(category_data.get("new_release_opportunity")):
        warnings.append("小类目新品机会待补；报告只能展示当前市场结构，不能判断新品榜机会。")
    if not as_list(category_data.get("category_seasonality")):
        warnings.append("类目淡旺季待补；不能用关键词搜索热度替代产品淡旺季判断。")
    narrative = analysis.get("report_writer_narrative") if isinstance(analysis.get("report_writer_narrative"), dict) else {}
    add_check(
        "report writer narrative exists",
        bool(narrative.get("analysis_cards")),
        str(narrative.get("source", "")),
    )

    html_text = html_path.read_text(encoding="utf-8") if html_path.exists() else ""
    required_sections = [
        "一句话",
        "证据边界",
        "AI 综合分析",
        "参考 ASIN 池",
        "大小类目与小类机会",
        "运营式关键词池",
        "价格带机会",
        "Sorftime 市场验证",
        "Sorftime 实时验证",
        "关键词需求",
        "类目背景",
        "竞品流量词",
        "VOC 差评痛点与规格翻译",
        "1688 候选款 / 候选供应商",
        "你人工 review 时重点看什么",
        "利润回填字段在哪里",
        "下一步进入利润/FBA/合规的条件",
        "证据审计",
    ]
    for section in required_sections:
        add_check(f"HTML contains {section}", section in html_text, section)

    missing_sources = [item for item in analysis["source_packets"] if not item.get("exists")]
    add_check("source packets exist", not missing_sources, ", ".join(item.get("name", "") for item in missing_sources))
    search_packet = next((item for item in analysis["source_packets"] if item.get("packet_id") == "search_demand_evidence"), {})
    search_provenance = search_packet.get("execution_provenance") if isinstance(search_packet.get("execution_provenance"), dict) else {}
    search_agent_ok = (
        search_provenance.get("executed_by_agent") is True
        and search_provenance.get("execution_mode") == "real_subagent_spawn"
        and search_provenance.get("agent_role") == "Search Demand Agent"
    )
    add_check(
        "Sorftime 搜索需求由独立数据复核完成",
        search_agent_ok,
        public_provenance_note(search_packet) if search_agent_ok else "Sorftime 搜索需求独立复核未确认。",
    )

    visual_status = analysis["supply_chain_match"]["visual_and_spec_review_status"].get("overall_status", "")
    if "pending" in str(visual_status):
        warnings.append("1688 候选仍待人工视觉、规格和样品复核；本报告只推荐 review 优先级，不声明供应商已确认。")
    unmarked_sources = [
        source_label(item.get("name", ""))
        for item in evidence_packets_requiring_provenance(analysis)
        if item.get("exists") and not provenance_is_recorded(item)
    ]
    if unmarked_sources:
        warnings.append(f"以下证据包缺少系统侧来源记录：{', '.join(unmarked_sources)}。这不是用户要补的数据。")
    review_scope = analysis["voc_spec_translation"].get("review_scope") or {}
    review_region = str(review_scope.get("primary_review_region") or "")
    target_region = infer_target_review_region(
        analysis.get("sorftime_market_validation", {}),
        analysis.get("seller_sprite_validation", {}),
    )
    if review_region and target_region and review_region != target_region:
        warnings.append(f"VOC 主要评论地区不是目标市场 {target_region}；建议补采目标地区用户评论。")
    if analysis.get("verdict") == "谨慎继续":
        warnings.append("利润/FBA/合规未回填，当前不能输出强 Go。")

    status = "pass" if all(item["passed"] for item in checks) else "fail"
    return {
        "status": status,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "run_dir": str(run_dir),
        "checks": checks,
        "warnings": warnings,
        "outputs": {
            "analysis_evidence_packet": str(analysis_json),
            "analysis_report_html": str(html_path),
            "analysis_report_xlsx": str(xlsx_path),
        },
    }


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def dedupe_rows(rows: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for row in rows:
        value = str(row.get(key) or "").strip()
        dedupe_key = value or json.dumps(row, ensure_ascii=False, sort_keys=True)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        result.append(row)
    return result


def join_text(value: Any) -> str:
    if isinstance(value, list):
        return "；".join(str(item) for item in value if str(item))
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    return "" if value is None else str(value)


def fmt_number(value: Any) -> str:
    if value in (None, ""):
        return "待补"
    if isinstance(value, (int, float)):
        if isinstance(value, float) and not value.is_integer():
            return f"{value:,.2f}".rstrip("0").rstrip(".")
        return f"{int(value):,}"
    return str(value)


def fmt_percent(value: Any) -> str:
    if value in (None, ""):
        return "待补"
    if isinstance(value, (int, float)):
        return f"{value * 100:.1f}%"
    return str(value)


def numeric_value(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if value in (None, ""):
        return None
    match = re.search(r"-?\d+(?:\.\d+)?", str(value))
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


def fmt_rmb(value: Any) -> str:
    if value in (None, ""):
        return "待补"
    if isinstance(value, (int, float)):
        return f"RMB {value:g}"
    return f"RMB {value}"


HTML_STYLE = """
:root {
  --ink: #17202a;
  --muted: #5f6b7a;
  --line: #d8dee8;
  --soft: #f5f7fa;
  --panel: #ffffff;
  --accent: #0f766e;
  --accent-soft: #d9f3ef;
  --warn: #9a3412;
  --warn-soft: #fff1e6;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
  color: var(--ink);
  background: #eef2f6;
  line-height: 1.55;
}
.topbar {
  position: sticky;
  top: 0;
  z-index: 5;
  display: flex;
  gap: 18px;
  overflow-x: auto;
  padding: 12px 24px;
  background: rgba(255,255,255,.95);
  border-bottom: 1px solid var(--line);
  white-space: nowrap;
}
.topbar a { color: var(--muted); text-decoration: none; font-size: 13px; }
.topbar a:hover { color: var(--accent); }
.page {
  width: min(1180px, calc(100% - 32px));
  margin: 0 auto;
  padding: 28px 0 56px;
}
.hero {
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) minmax(320px, .8fr);
  gap: 24px;
  align-items: stretch;
  padding: 34px;
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 8px;
}
.eyebrow {
  margin: 0 0 8px;
  color: var(--accent);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: .08em;
  text-transform: uppercase;
}
h1, h2, h3 { margin: 0; line-height: 1.25; letter-spacing: 0; }
h1 { font-size: 34px; }
h2 { font-size: 24px; }
h3 { font-size: 17px; margin-bottom: 12px; }
.one-line-title { margin-top: 18px; font-size: 20px; color: #0f766e; }
.lead { margin: 18px 0 0; font-size: 18px; color: #2d3748; }
.pill-row { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 22px; }
.pill {
  display: inline-flex;
  align-items: center;
  min-height: 30px;
  padding: 6px 11px;
  border-radius: 999px;
  background: var(--soft);
  color: var(--muted);
  font-size: 13px;
}
.pill.verdict { background: var(--accent-soft); color: #075e58; font-weight: 700; }
.metric-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}
.metric {
  min-height: 112px;
  padding: 18px;
  background: var(--soft);
  border: 1px solid var(--line);
  border-radius: 8px;
}
.metric-label { color: var(--muted); font-size: 13px; }
.metric-value { margin-top: 8px; font-size: 24px; font-weight: 750; }
.metric-note { margin-top: 8px; color: var(--muted); font-size: 13px; }
.section {
  margin-top: 24px;
  padding: 28px;
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 8px;
}
.compact-section {
  padding-bottom: 24px;
}
.section-head {
  max-width: 880px;
  margin-bottom: 20px;
}
.section-head.wide { max-width: 1080px; }
.section-head p:not(.eyebrow) { margin: 10px 0 0; color: var(--muted); }
.two-col {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px;
}
.sorftime-stack {
  display: grid;
  gap: 18px;
}
.side-stack {
  display: grid;
  gap: 18px;
}
.panel {
  margin-top: 18px;
  padding: 20px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: #fff;
}
.ai-analysis {
  background: linear-gradient(180deg, #ffffff 0%, #f7fbfa 100%);
}
.analysis-thesis {
  display: grid;
  gap: 8px;
  margin-bottom: 16px;
  padding: 20px;
  border: 1px solid #a7d8d1;
  border-radius: 8px;
  background: #edf9f7;
}
.analysis-thesis strong {
  font-size: 26px;
  line-height: 1.22;
}
.analysis-persona {
  width: fit-content;
  border: 1px solid #8ed0c7;
  border-radius: 999px;
  background: #ffffff;
  color: #0f766e;
  padding: 5px 10px;
  font-size: 13px;
  font-weight: 800;
}
.analysis-principle { color: var(--muted) !important; font-size: 14px; }
.analysis-copy {
  display: grid;
  gap: 10px;
}
.analysis-copy-thesis { gap: 12px; }
.analysis-copy p {
  margin: 0;
  color: #334155;
  line-height: 1.68;
}
.analysis-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
  align-items: start;
}
.analysis-card {
  display: grid;
  align-content: start;
  gap: 14px;
  min-height: 0;
  padding: 18px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: #fff;
}
.analysis-card-title {
  color: var(--accent);
  font-size: 13px;
  font-weight: 800;
}
.analysis-card-lead {
  margin: 0;
  color: #1f2937;
  font-size: 15px;
  font-weight: 750;
  line-height: 1.62;
}
.analysis-points {
  display: grid;
  gap: 10px;
}
.analysis-points div {
  display: grid;
  grid-template-columns: 46px minmax(0, 1fr);
  gap: 10px;
  align-items: start;
  padding-top: 10px;
  border-top: 1px solid #e5edf3;
}
.analysis-points span {
  display: inline-flex;
  justify-content: center;
  min-height: 24px;
  padding: 3px 6px;
  border-radius: 6px;
  background: var(--accent-soft);
  color: #075e58;
  font-size: 12px;
  font-weight: 800;
}
.analysis-points p {
  margin: 0;
  color: #334155;
  line-height: 1.62;
}
.fact-grid,
.traffic-grid,
.traffic-cards {
  display: grid;
  gap: 12px;
}
.boundary-grid,
.audit-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}
.boundary-card,
.audit-card {
  display: grid;
  gap: 12px;
  align-content: start;
  padding: 16px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: #fff;
}
.boundary-topline,
.audit-topline {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  align-items: flex-start;
}
.boundary-topline strong,
.audit-topline strong {
  color: #17202a;
}
.boundary-topline span,
.audit-topline span {
  flex: 0 0 auto;
  border-radius: 999px;
  padding: 3px 8px;
  background: var(--warn-soft);
  color: #9a3412;
  font-size: 12px;
  font-weight: 800;
}
.boundary-card dl {
  display: grid;
  gap: 8px;
  margin: 0;
}
.boundary-card dt {
  color: var(--accent);
  font-size: 12px;
  font-weight: 800;
}
.boundary-card dd {
  margin: -6px 0 2px;
  color: #334155;
  line-height: 1.58;
}
.audit-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.audit-meta span {
  border: 1px solid var(--line);
  border-radius: 999px;
  padding: 3px 8px;
  color: var(--muted);
  font-size: 12px;
}
.audit-card p {
  margin: 0;
  color: #334155;
  line-height: 1.58;
}
.category-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
  align-items: start;
}
.fact-card,
.traffic-group,
.traffic-card,
.empty-state {
  border: 1px solid var(--line);
  border-radius: 8px;
  background: #fbfdfc;
}
.fact-card {
  display: grid;
  gap: 8px;
  padding: 14px;
}
.fact-card > span,
.traffic-card span {
  color: var(--muted);
  font-size: 12px;
  font-weight: 800;
}
.fact-card > strong,
.traffic-card > strong {
  color: #17202a;
  font-size: 18px;
}
.fact-card em,
.traffic-card em {
  color: #9a3412;
  font-style: normal;
}
.fact-card p,
.traffic-card p,
.traffic-read {
  margin: 0;
  color: #334155;
}
.mini-facts {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}
.mini-facts div {
  padding: 9px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: #fff;
}
.mini-facts span {
  display: block;
  color: var(--muted);
  font-size: 12px;
  font-weight: 800;
}
.mini-facts strong {
  display: block;
  margin-top: 3px;
}
.traffic-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}
.traffic-group {
  padding: 14px;
}
.traffic-read {
  margin-bottom: 12px;
  font-weight: 700;
}
.traffic-card {
  display: grid;
  gap: 6px;
  padding: 12px;
  background: #fff;
}
.empty-state {
  padding: 14px;
  color: var(--muted);
}
.panel.warn { background: var(--warn-soft); border-color: #fed7aa; }
.notice {
  margin: 14px 0 18px;
  padding: 14px 16px;
  border-left: 4px solid var(--warn);
  background: var(--warn-soft);
  color: #713f12;
  border-radius: 6px;
}
ul { margin: 0; padding-left: 18px; }
li + li { margin-top: 8px; }
.supplier-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 14px;
}
.supplier-card {
  border: 1px solid var(--line);
  border-radius: 8px;
  background: #fbfdfc;
}
.supplier-body {
  display: grid;
  align-content: start;
  gap: 10px;
  padding: 18px;
}
.supplier-topline,
.tag-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}
.rank-pill,
.status-pill,
.tag-row span {
  min-height: 26px;
  display: inline-flex;
  align-items: center;
  border-radius: 8px;
  padding: 3px 8px;
  font-size: 12px;
  font-weight: 800;
}
.rank-pill { background: var(--accent); color: #fff; }
.status-pill { background: var(--accent-soft); color: #075e58; border: 1px solid #bfe7e1; }
.tag-row span { background: var(--soft); color: var(--muted); border: 1px solid var(--line); }
.supplier-title-block {
  display: grid;
  gap: 8px;
  min-width: 0;
}
.supplier-title-block h3 {
  margin: 0;
  font-size: 20px;
  line-height: 1.25;
  overflow-wrap: anywhere;
}
.supplier-title-block p {
  margin: 0;
  color: #17202a;
  overflow-wrap: anywhere;
}
.supplier-stats {
  display: grid;
  grid-template-columns: repeat(2, minmax(140px, 1fr));
  gap: 10px;
}
.supplier-stats div {
  padding: 10px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: #fff;
}
.supplier-stats span {
  display: block;
  color: var(--muted);
  font-size: 12px;
  font-weight: 800;
}
.supplier-stats strong {
  display: block;
  margin-top: 4px;
  color: #9a3412;
  font-size: 18px;
}
.supplier-reason,
.supplier-check {
  display: grid;
  gap: 6px;
}
.supplier-reason span {
  line-height: 1.65;
  color: #334155;
}
.supplier-reason strong,
.supplier-check strong {
  color: var(--accent);
  font-size: 13px;
}
.appendix {
  background: #f8fafc;
}
.table-wrap {
  width: 100%;
  overflow-x: auto;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: #fff;
}
table { width: 100%; border-collapse: collapse; min-width: 760px; }
th, td {
  padding: 11px 12px;
  border-bottom: 1px solid var(--line);
  vertical-align: top;
  text-align: left;
  font-size: 13px;
}
th {
  position: sticky;
  top: 0;
  background: #f8fafc;
  color: #334155;
  font-weight: 700;
}
tr:last-child td { border-bottom: 0; }
a { color: #0f766e; }
@media (max-width: 860px) {
  .page { width: min(100% - 20px, 1180px); padding-top: 18px; }
  .hero, .two-col, .analysis-grid, .supplier-stats, .traffic-grid, .mini-facts, .category-grid, .boundary-grid, .audit-grid { grid-template-columns: 1fr; }
  .hero, .section { padding: 22px; }
  .metric-grid { grid-template-columns: 1fr; }
  h1 { font-size: 28px; }
}
"""


if __name__ == "__main__":
    raise SystemExit(main())
