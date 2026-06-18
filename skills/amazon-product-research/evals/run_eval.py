#!/usr/bin/env python3
"""Run lightweight evals for the amazon-product-research skill."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.render_deliverables import render_deliverables


EVAL_DIR = Path(__file__).resolve().parent
FILES_DIR = EVAL_DIR / "files"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run amazon-product-research eval checks.")
    parser.add_argument(
        "check",
        nargs="?",
        default="render_minimal_research_package",
        choices=("render_minimal_research_package",),
    )
    args = parser.parse_args(argv)

    if args.check == "render_minimal_research_package":
        return _run_minimal_research_package_eval()
    raise ValueError(f"unsupported eval check: {args.check}")


def _run_minimal_research_package_eval() -> int:
    fixture_path = FILES_DIR / "minimal_research_package.json"
    package = json.loads(fixture_path.read_text(encoding="utf-8"))
    package = _expand_eval_package(package)

    with tempfile.TemporaryDirectory(prefix="amz_skill_eval_") as tmp:
        run_dir = Path(tmp)
        final_report_dir = run_dir / "final_report"
        package_path = run_dir / "research_package.json"
        package_path.write_text(json.dumps(package, ensure_ascii=False, indent=2), encoding="utf-8")
        _write_workflow_summary(run_dir)
        result = render_deliverables(package_path, final_report_dir, mode="all")
        if result is None:
            raise RuntimeError("render_deliverables did not return validation result")
        print(f"generated: {final_report_dir}")
        if not result.ok:
            print("\n".join(result.errors))
            return 1
        print(f"validate_ok: {len(result.notes)} notes")
    return 0


def _write_workflow_summary(run_dir: Path) -> None:
    summary = {
        "review_voc": {"enabled": True, "status": "已接入最小 eval 评论证据"},
        "profit_review": {"applied": False, "status": "待填写模板"},
        "ip_compliance_review": {"applied": False, "status": "待填写模板"},
    }
    (run_dir / "workflow_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (run_dir / "workflow_summary.md").write_text(
        "# 选品流程运行摘要\n\n"
        "- 评论 VOC：已接入最小 eval 评论证据\n"
        "- 利润复核：待填写模板\n"
        "- 知产/合规初筛：待填写模板\n",
        encoding="utf-8",
    )


def _expand_eval_package(package: dict[str, Any]) -> dict[str, Any]:
    expanded = copy.deepcopy(package)
    fixture = expanded.pop("eval_fixture", {})
    top100_count = int(fixture.get("top100_count", 100))
    competitor_count = int(fixture.get("competitor_count", 10))

    top_products = _build_top_products(top100_count)
    normalized = expanded.setdefault("normalized_tables", {})
    normalized["top100"] = top_products
    normalized["top_product_tags"] = top_products
    normalized["voc_evidence"] = _build_voc_evidence()

    market_structure = expanded.setdefault("market_structure", {})
    market_structure.setdefault("data_quality", _build_data_quality(top100_count))
    market_structure.setdefault("attribute_definitions", _build_attribute_definitions())
    market_structure.setdefault("attribute_distributions", _build_attribute_distributions())
    market_structure.setdefault("cross_analysis", _build_cross_analysis())
    market_structure.setdefault("opportunity_judgments", _build_opportunity_judgments())
    market_structure.setdefault("pending_label_items", [top_products[-1]])
    market_structure.setdefault(
        "summary",
        {
            "quality_summary": "Top100 eval 样例完整，字段用于渲染和校验 smoke test。",
            "dominant_structure": "中价基础款贡献销量，高价升级款用于验证差异化。",
            "opportunity_clues": [
                "中价位 + 防滑结构存在薄供给",
                "升级材质 + 高评论门槛需要验证",
                "组合套装路线先作为观察项",
            ],
            "opportunity_judgment_summary": "样例中保留真机会、伪机会和待验证三类判断。",
        },
    )

    competitors = _build_competitors(competitor_count)
    expanded["competitor_selection_logic"] = competitors
    expanded["competitor_pool"] = {
        "top10": competitors[:4],
        "recent_winners": competitors[4:7],
        "structure_supplement": competitors[7:],
    }
    expanded["competitor_deep_dive"] = [
        {
            "card_type": item["competitor_type"],
            "asin": item["asin"],
            "brand": item["brand"],
            "title": item["title"],
            "price_usd": item["price_usd"],
            "monthly_units": item["monthly_units"],
            "rating": item["rating"],
            "rating_count": item["rating_count"],
            "listing_days": 180 + index,
            "note": "eval 竞品深拆卡，用于验证报告和 Excel 回表。",
        }
        for index, item in enumerate(competitors[:5])
    ]

    expanded.setdefault("product_route_matrix", _build_route_matrix())
    expanded.setdefault("route_deep_dive_plan", _build_route_plan(competitors))
    ai_analysis = expanded.setdefault("ai_analysis", {})
    ai_analysis.setdefault("product_route_matrix", expanded["product_route_matrix"])
    ai_analysis.setdefault("route_deep_dive_plan", expanded["route_deep_dive_plan"])
    return expanded


def _build_top_products(count: int) -> list[dict[str, Any]]:
    products: list[dict[str, Any]] = []
    routes = ("基础款", "升级款", "场景款", "组合套装款")
    for index in range(count):
        route = routes[index % len(routes)]
        price = 18.99 + (index % 8) * 2
        products.append(
            {
                "asin": f"B{index:09d}",
                "title": f"Eval {route} Product {index}",
                "price": round(price, 2),
                "monthly_units": 120 + index,
                "monthly_revenue_usd": round(price * (120 + index), 2),
                "rating": round(3.8 + (index % 7) * 0.1, 1),
                "rating_count": 60 + index * 3,
                "listing_date": "2026-01-01",
                "listing_days": 100 + index,
                "brand": f"EvalBrand{index % 12}",
                "category": "Eval Category",
                "attribute_tags": {
                    "price_band": "$20-$35" if price < 35 else "$35+",
                    "product_route": route,
                    "review_band": "中评论门槛" if index % 3 else "高评论门槛",
                },
                "tag_confidence": "高" if index < count - 1 else "低",
                "tag_notes": "eval generated",
            }
        )
    return products


def _build_data_quality(count: int) -> dict[str, Any]:
    return {
        "expected_count": 100,
        "actual_count": count,
        "completeness_rate": 1.0,
        "quality_score": 95,
        "level": "可用于 eval",
        "unique_asin_count": count,
        "next_check": "真实运行时替换为卖家精灵 Top100 明细。",
        "warnings": [],
    }


def _build_attribute_definitions() -> list[dict[str, str]]:
    return [
        {"dimension": "price_band", "label": "价格带", "rule": "按售价分为 $20 以下、$20-$35、$35+"},
        {"dimension": "product_route", "label": "产品路线", "rule": "按标题和形态识别基础款、升级款、场景款、组合套装款"},
        {"dimension": "review_band", "label": "评论门槛", "rule": "按 rating_count 分为低/中/高评论门槛"},
    ]


def _build_attribute_distributions() -> list[dict[str, Any]]:
    return [
        {
            "dimension": "price_band",
            "label": "价格带",
            "summary": "$20-$35 为 eval 主力价格带，适合观察中价位承接能力。",
            "buckets": [
                {"value": "$20 以下", "count": 18, "share": 0.18},
                {"value": "$20-$35", "count": 62, "share": 0.62},
                {"value": "$35+", "count": 20, "share": 0.2},
            ],
        },
        {
            "dimension": "product_route",
            "label": "产品路线",
            "summary": "基础款数量最多，升级款和组合套装款用于验证差异化。",
            "buckets": [
                {"value": "基础款", "count": 38, "share": 0.38},
                {"value": "升级款", "count": 26, "share": 0.26},
                {"value": "场景款", "count": 20, "share": 0.2},
                {"value": "组合套装款", "count": 16, "share": 0.16},
            ],
        },
        {
            "dimension": "review_band",
            "label": "评论门槛",
            "summary": "中评论门槛样本较多，新品进入仍需看 VOC 和供应链。",
            "buckets": [
                {"value": "低评论门槛", "count": 20, "share": 0.2},
                {"value": "中评论门槛", "count": 55, "share": 0.55},
                {"value": "高评论门槛", "count": 25, "share": 0.25},
            ],
        },
    ]


def _build_cross_analysis() -> list[dict[str, Any]]:
    return [
        {
            "label": "价格带 x 产品路线",
            "purpose": "识别中价位路线薄供给",
            "summary": "$20-$35 的升级款样本少但销量不低，属于待验证机会。",
            "cells": [
                {"row": "$20-$35", "column": "升级款", "count": 2, "avg_price": 29.99, "avg_monthly_units": 980, "avg_rating": 4.2, "opportunity_type": "薄供给", "interpretation": "需要验证供应链是否能承接升级结构。"},
                {"row": "$35+", "column": "基础款", "count": 0, "avg_price": 0, "avg_monthly_units": 0, "avg_rating": 0, "opportunity_type": "伪空白", "interpretation": "高价基础款缺少合理需求场景。"},
            ],
        },
        {
            "label": "评论门槛 x 产品路线",
            "purpose": "判断新品冷启动难度",
            "summary": "中评论门槛场景款可作为观察路线。",
            "cells": [
                {"row": "中评论门槛", "column": "场景款", "count": 3, "avg_price": 24.99, "avg_monthly_units": 620, "avg_rating": 4.1, "opportunity_type": "待验证", "interpretation": "评论门槛可接受，但需要 VOC 证明场景痛点。"}
            ],
        },
        {
            "label": "价格带 x 评论门槛",
            "purpose": "识别价格和冷启动组合",
            "summary": "$20-$35 + 中评论门槛是 eval 主力组合。",
            "cells": [
                {"row": "$20-$35", "column": "中评论门槛", "count": 5, "avg_price": 27.99, "avg_monthly_units": 740, "avg_rating": 4.3, "opportunity_type": "主力组合", "interpretation": "可作为主线验证，不直接等同于 Go。"}
            ],
        },
    ]


def _build_opportunity_judgments() -> list[dict[str, Any]]:
    return [
        {
            "cross_dimension": "价格带 x 产品路线",
            "combination": "$20-$35 x 升级款",
            "opportunity_type": "待验证",
            "sample_count": 2,
            "avg_price": 29.99,
            "avg_monthly_units": 980,
            "avg_rating": 4.2,
            "basis": "薄供给但销量信号存在。",
            "next_check": "补供应商结构和 VOC 痛点到规格映射。",
            "sample_asins": ["B000000001", "B000000002"],
        },
        {
            "cross_dimension": "价格带 x 产品路线",
            "combination": "$35+ x 基础款",
            "opportunity_type": "伪机会",
            "sample_count": 0,
            "avg_price": 0,
            "avg_monthly_units": 0,
            "avg_rating": 0,
            "basis": "缺少合理价格承接。",
            "next_check": "不作为主推，只保留观察。",
            "sample_asins": [],
        },
    ]


def _build_competitors(count: int) -> list[dict[str, Any]]:
    roles = ("量级标杆", "近半年新品", "痛点参考", "功能差异代表", "价格带覆盖")
    competitors: list[dict[str, Any]] = []
    for index in range(count):
        price = 19.99 + index
        competitors.append(
            {
                "asin": f"C{index:09d}",
                "brand": f"EvalCompetitor{index}",
                "title": f"Eval Competitor Product {index}",
                "price_usd": round(price, 2),
                "price": round(price, 2),
                "monthly_units": 950 - index * 30,
                "monthly_revenue_usd": round(price * (950 - index * 30), 2),
                "rating": round(4.5 - (index % 5) * 0.1, 1),
                "rating_count": 120 + index * 20,
                "competitor_type": roles[index % len(roles)],
                "coverage_dimensions": ["价格带", "产品路线", "评论门槛"],
                "selection_reason": "覆盖 eval 竞品角色和报告校验字段。",
                "listing_date": "2025-12-01",
                "listing_days": 180 + index,
                "note": "eval competitor",
            }
        )
    return competitors


def _build_voc_evidence() -> list[dict[str, Any]]:
    return [
        {
            "finding_type": "痛点",
            "finding_name": "结构松动",
            "review_count": 5,
            "severity": "高",
            "review_id": "R-EVAL-001",
            "asin": "C000000001",
            "site": "US",
            "review_region": "United States",
            "rating": 2,
            "review_date": "2026-01-01",
            "snippet": "The buckle became loose after several uses.",
            "url": "https://example.com/review/1",
        },
        {
            "finding_type": "痛点",
            "finding_name": "材质磨损",
            "review_count": 4,
            "severity": "中",
            "review_id": "R-EVAL-002",
            "asin": "C000000002",
            "site": "US",
            "review_region": "United States",
            "rating": 3,
            "review_date": "2026-01-02",
            "snippet": "The strap started fraying around the edge.",
            "url": "https://example.com/review/2",
        },
        {
            "finding_type": "亮点",
            "finding_name": "安装简单",
            "review_count": 6,
            "severity": "低",
            "review_id": "R-EVAL-003",
            "asin": "C000000003",
            "site": "US",
            "review_region": "United States",
            "rating": 5,
            "review_date": "2026-01-03",
            "snippet": "Setup was quick and clear.",
            "url": "https://example.com/review/3",
        },
    ]


def _build_route_matrix() -> list[dict[str, Any]]:
    return [
        {
            "route_name": "主线：中价升级款",
            "route_type": "主线",
            "candidate_count": 18,
            "priority_count": 6,
            "watchlist_count": 3,
            "price_text": "$20-$35",
            "opportunity": "中价位承接强，VOC 可转规格。",
            "risks": "供应链结构需打样确认。",
            "validation_actions": ["问供应商扣具结构", "样品做耐用测试", "补 3 个竞品 VOC"],
            "decision_hint": "优先继续验证。",
        },
        {
            "route_name": "旁支：组合套装款",
            "route_type": "旁支观察",
            "candidate_count": 8,
            "priority_count": 1,
            "watchlist_count": 4,
            "price_text": "$25-$40",
            "opportunity": "可提升客单价。",
            "risks": "重量、包装和缺件风险更高。",
            "validation_actions": ["核包装重量", "问替换件", "看差评缺件"],
            "decision_hint": "暂不抢主线资源。",
        },
    ]


def _build_route_plan(competitors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "route_name": "主线：中价升级款",
            "route_type": "主线",
            "recommended_depth": "完整深挖",
            "current_evidence_level": "中",
            "why": "市场、VOC 和供应链都有可验证证据。",
            "seller_sprite_exports": ["主词搜索结果", "Top100 完整明细"],
            "sorftime_checks": ["keyword_detail", "product_traffic_terms"],
            "review_voc_asin_plan": [
                {"asin": item["asin"], "competitor_type": item["competitor_type"], "title": item["title"]}
                for item in competitors[:3]
            ],
            "review_coverage": {"matched_review_count": 12, "matched_asins": [item["asin"] for item in competitors[:3]]},
            "supply_chain_search_terms": ["中价 升级款 供应商", "防滑 结构 配件"],
            "data_gaps": ["需要真实供应商样品测试"],
            "decision_gate": ["样品通过耐用测试", "利润模板回填后仍可接受"],
            "next_step": "补供应商样品和利润模板。",
        }
    ]


if __name__ == "__main__":
    raise SystemExit(main())
