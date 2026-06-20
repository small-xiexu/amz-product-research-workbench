from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from openpyxl import load_workbook

from packages.report_renderer.xlsx_writer import write_xlsx
from packages.research_core.adapters import SorftimeAdapter, SortimeAdapter
from packages.research_core.contracts import (
    ContractValidationError,
    validate_candidate_pool,
    validate_import_manifest,
    validate_research_package,
    validate_research_package_chapters,
    validate_workflow_state,
)
from packages.research_core.workflows import WorkflowConfig, run_research_workflow
from packages.research_core.workflows.product_research_workflow import build_workflow_trace
from packages.research_core.workflows import DecisionRecord, advance_stage, create_initial_state
from packages.research_core.pipeline.build_route_matrix_confirm import build_route_matrix_confirm
from packages.research_core.pipeline.build_candidate_pool_from_import_manifest import build_candidate_pool
from packages.research_core.pipeline.build_research_data_packet import build_research_data_packet
from packages.research_core.pipeline.build_research_package_from_candidate import build_research_package
from packages.research_core.pipeline.cross_analysis import build_cross_analysis
from packages.research_core.pipeline.parse_top100_dimensions import parse_top100_dimensions
from packages.research_core.pipeline.audit_run_status import audit_run_status
from packages.research_core.pipeline.validate_research_outputs import validate_workflow_output
from packages.report_renderer.render_report import (
    FORMAL_REPORT_SECTION_TITLES,
    render_data_workbook,
    render_markdown,
    render_report_html,
)
from scripts.build_stage7_analysis_report import build_analysis_packet, build_workbook_sheets, render_html_report


ROOT = Path(__file__).resolve().parents[1]


def _load_generic_redline_module():
    module_path = ROOT / "scripts" / "check_generic_redlines.py"
    spec = importlib.util.spec_from_file_location("check_generic_redlines", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class RegressionTests(unittest.TestCase):
    def test_route_matrix_confirm_is_derived_from_run_packets(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir) / "generic_route_run"
            (run_dir / "market_structure").mkdir(parents=True)
            (run_dir / "search_demand").mkdir()
            (run_dir / "workflow_state.json").write_text(
                json.dumps(
                    {
                        "workflow_id": "generic_route_run",
                        "site": "US",
                        "known_inputs": {
                            "scenario": "桌面整理",
                            "constraints": ["非电动"],
                            "confirmed_stage0_route": "手动整理工具",
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (run_dir / "review_asin_batch.json").write_text(
                json.dumps(
                    {
                        "workflow_id": "generic_route_run",
                        "site": "US",
                        "candidate_name": "手动整理工具",
                        "confirmed_boundary": {
                            "mainline": "手动整理工具",
                            "keep_routes": ["基础款", "升级款"],
                            "exclude_routes": ["电动工具"],
                        },
                        "asin_batch": [{"asin": "ASIN001", "route": "base_route"}],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (run_dir / "market_structure" / "market_structure_evidence_packet.json").write_text(
                json.dumps(
                    {
                        "route_market_fit": [
                            {
                                "route_id": "base_route",
                                "route_name": "基础路线",
                                "role_from_route_matrix": "主推",
                                "status_from_route_matrix": "继续看",
                                "facts": {"avg_price_usd": 20},
                                "representative_asins": ["ASIN001"],
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (run_dir / "search_demand" / "search_demand_evidence_packet.json").write_text(
                json.dumps(
                    {
                        "keyword_pool_by_role": {
                            "main_traffic": [{"keyword": "manual organizer", "route_refs": ["base_route"]}],
                            "mixed_or_excluded": [{"keyword": "electric organizer", "reason": "非目标形态"}],
                        }
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            packet = build_route_matrix_confirm(run_dir)

        self.assertEqual(packet["packet_id"], "route_matrix_confirm")
        self.assertEqual(packet["selected_route"], "手动整理工具")
        self.assertEqual(packet["route_matrix"][0]["representative_asins"], ["ASIN001"])
        self.assertIn("manual organizer", packet["route_matrix"][0]["keyword_refs"])
        self.assertEqual(packet["category_selection_derivation"]["rejected_alternatives"][0]["name"], "电动工具")

    def test_generic_redline_flags_case_specific_terms_in_reusable_assets(self) -> None:
        checker = _load_generic_redline_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            run_file = root / "runs" / "20260619_manual_window_cleaning_tools" / "mcp" / "route.json"
            run_file.parent.mkdir(parents=True)
            run_file.write_text('{"asin": "B0BZZDPPRX", "keyword": "window squeegee"}\n', encoding="utf-8")
            package_file = root / "packages" / "report_renderer" / "template.py"
            package_file.parent.mkdir(parents=True)
            package_file.write_text('DEFAULT_REFERENCE = "B0BZZDPPRX"\n', encoding="utf-8")

            term_groups = checker.merge_terms(run_dirs=(run_file.parents[2],))
            violations = checker.scan_generic_redlines(root=root, includes=("packages",), term_groups=term_groups)

        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0].path, "packages/report_renderer/template.py")
        self.assertEqual(violations[0].group, "run_asins")

    def test_generic_redline_ignores_run_artifacts_and_honors_waiver(self) -> None:
        checker = _load_generic_redline_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            run_file = root / "runs" / "20260619_manual_window_cleaning_tools" / "mcp" / "route.json"
            run_file.parent.mkdir(parents=True)
            run_file.write_text('{"keyword": "window squeegee"}\n', encoding="utf-8")
            docs_file = root / "docs" / "appendix.md"
            docs_file.parent.mkdir(parents=True)
            docs_file.write_text(
                "<!-- generic-redline: allow -->\n"
                "历史附录可保留 B0BZZDPPRX 作为说明，不进入通用逻辑。\n",
                encoding="utf-8",
            )

            term_groups = checker.merge_terms(custom_terms=("B0BZZDPPRX", "window squeegee"))
            violations = checker.scan_generic_redlines(root=root, includes=("docs", "runs"), term_groups=term_groups)

        self.assertEqual(violations, [])

    def test_stage7_analysis_report_uses_operator_research_objects(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir) / "generic_stage7_run"
            run_dir.mkdir()
            paths = {
                "search_demand": run_dir / "search_demand" / "search_demand_evidence_packet.json",
                "market_structure": run_dir / "market_structure" / "market_structure_evidence_packet.json",
                "voc": run_dir / "review_voc" / "voc_evidence_packet.json",
                "route_matrix": run_dir / "route_matrix_confirm.json",
                "workflow_state": run_dir / "workflow_state.json",
                "report_writer_narrative": run_dir / "analysis" / "report_writer_narrative.json",
            }
            for path in paths.values():
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("{}", encoding="utf-8")
            (run_dir / "import_manifest.json").write_text(
                json.dumps(
                    {
                        "files": [{"file_name": "market.xlsx", "parse_status": "parsed", "warnings": []}],
                        "data_quality": {
                            "available_source_types": [
                                "seller_sprite_market_analysis",
                                "seller_sprite_search_results",
                                "seller_sprite_reverse_asin_keywords",
                                "amazon_aba_keywords",
                            ],
                            "missing_source_types": [],
                            "warnings": [],
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            search_packet = {
                "packet_id": "search_demand_evidence",
                "agent_role": "Search Demand Agent",
                "confidence": "medium",
                "execution_provenance": {
                    "executed_by_agent": True,
                    "agent_role": "Search Demand Agent",
                    "execution_mode": "real_subagent_spawn",
                },
                "reference_asin_inputs": [
                    {
                        "asin": "ASINREF001",
                        "route_ref": "base_route",
                        "asin_role": "primary_reference",
                        "similarity_reason": "形态和使用场景接近",
                    }
                ],
                "category_candidates": [
                    {
                        "category_name": "General Utility Holders",
                        "node_id": "100100",
                        "category_role": "subcategory_market",
                        "source_type": "asin_category_mapping",
                        "matched_asin_count": 1,
                        "evidence_strength": "strong",
                        "recommended_use": "analyze_entry",
                    }
                ],
                "keyword_pool_by_role": {
                    "main_traffic": [
                        {
                            "keyword": "utility holder",
                            "keyword_role": "main_traffic",
                            "source_type": "product_traffic_terms",
                            "matched_asin_count": 3,
                            "monthly_search_volume": 12000,
                            "cpc": 1.2,
                            "recommended_action": "main_check",
                            "reason": "多个参考 ASIN 命中且搜索结果相似",
                        }
                    ],
                    "conversion_quality": [],
                    "traffic": [],
                    "precise_long_tail": [
                        {
                            "keyword": "compact utility holder for desk",
                            "keyword_role": "precise_long_tail",
                            "source_type": "competitor_product_keywords",
                            "matched_asin_count": 2,
                            "monthly_search_volume": 1400,
                            "recommended_action": "supplement_check",
                            "reason": "规格和场景更明确",
                        }
                    ],
                    "mixed_or_excluded": [
                        {
                            "keyword": "branded replacement accessory",
                            "keyword_role": "mixed_or_excluded",
                            "source_type": "keyword_search_results",
                            "mix_pool_tags": ["品牌词", "配件"],
                            "recommended_action": "exclude",
                            "reason": "搜索结果不是目标产品形态",
                        }
                    ],
                },
                "category_seasonality": [
                    {
                        "category_ref": "Utility Holders",
                        "category_role": "subcategory_market",
                        "trend_source": "category_trend",
                        "trend_index": "SalesCount",
                        "peak_months": ["November", "December"],
                        "low_months": ["February"],
                        "seasonality_level": "medium",
                        "trend_direction": "stable",
                        "keyword_heat_note": "关键词热度仅作搜索参考",
                        "category_seasonality_note": "类目销量在 Q4 更强",
                    }
                ],
                "data_gaps": [],
            }
            market_packet = {
                "packet_id": "market_structure_evidence",
                "agent_role": "Market Structure Agent",
                "confidence": "medium",
                "execution_provenance": {
                    "executed_by_agent": False,
                    "agent_role": "Market Structure Agent",
                    "execution_mode": "script_generated",
                },
                "reference_asin_pool": [
                    {
                        "asin": "ASINREF001",
                        "route_ref": "base_route",
                        "asin_role": "primary_reference",
                        "similarity_reason": "形态、价格带和使用场景接近",
                        "category_path": "Home > Utility Holders",
                        "category_role": "小类",
                        "price": 24.99,
                        "monthly_sales": 900,
                        "rating_count": 180,
                    }
                ],
                "category_candidates": [
                    {
                        "category_name": "Home Utility",
                        "node_id": "100000",
                        "category_role": "broad_market",
                        "source_type": "seller_sprite_market",
                        "evidence_strength": "medium",
                        "recommended_use": "analyze_capacity",
                    },
                    {
                        "category_name": "Utility Holders",
                        "node_id": "100100",
                        "category_role": "subcategory_market",
                        "source_type": "asin_category_mapping",
                        "matched_asin_count": 1,
                        "evidence_strength": "strong",
                        "recommended_use": "analyze_entry",
                    },
                ],
                "asin_category_mapping": [
                    {
                        "asin": "ASINREF001",
                        "route_ref": "base_route",
                        "category_path": "Home > Utility Holders",
                        "node_id": "100100",
                        "category_role": "小类",
                        "mapping_source": "seller_sprite",
                    }
                ],
                "market_size": {
                    "primary_market": {
                        "market_label": "Utility Holders",
                        "overview_all": {
                            "样本商品数": 100,
                            "月均销量": 850,
                            "月均销售额($)": 24000,
                            "平均价格($)": 24.5,
                            "平均评分数": 260,
                        },
                    }
                },
                "price_band_opportunity": [
                    {
                        "category_ref": "Utility Holders",
                        "price_band": "$20-$30",
                        "product_count": 32,
                        "sales_share": 0.42,
                        "revenue_share": 0.46,
                        "median_rating_count": 160,
                        "top3_product_share": 0.18,
                        "top3_brand_share": 0.24,
                        "new_release_count": 5,
                        "low_review_winner_count": 3,
                        "opportunity_level": "strong",
                        "reason": "销量和销售额都有占比，且低评论样本存在",
                    }
                ],
                "new_release_opportunity": [
                    {
                        "category_ref": "Utility Holders",
                        "new_release_count": 5,
                        "new_release_sales_share": 0.08,
                        "new_release_revenue_share": 0.07,
                        "low_review_samples": ["ASINNEW001", "ASINNEW002"],
                        "ranking_entry_signal": "watch",
                    }
                ],
                "route_market_fit": [
                    {
                        "route_id": "base_route",
                        "route_name": "基础收纳路线",
                        "role": "主推代表",
                        "status": "继续看",
                        "facts": {
                            "price_min_usd": 20,
                            "price_max_usd": 30,
                            "avg_price_usd": 24.5,
                            "avg_monthly_units": 850,
                            "median_rating_count": 160,
                        },
                        "representative_asins": ["ASINREF001"],
                    }
                ],
                "data_gaps": [],
            }
            voc_packet = {
                "packet_id": "voc_evidence",
                "agent_role": "VOC Evidence Agent",
                "confidence": "medium",
                "review_scope": {
                    "review_count": 48,
                    "low_rating_count": 12,
                    "primary_review_region": "United States",
                    "review_region_distribution": [{"name": "United States", "count": 42}],
                },
                "pain_points_by_dimension": [
                    {
                        "dimension": "耐用性",
                        "keyword_hits": 8,
                        "low_rating_hits": 5,
                        "fact_summary": "低分评论反复提到结构松动",
                    }
                ],
                "data_gaps": [],
            }
            route_matrix = {"route_matrix": market_packet["route_market_fit"]}

            analysis = build_analysis_packet(
                run_dir,
                {
                    "paths": paths,
                    "search_demand": search_packet,
                    "market_structure": market_packet,
                    "voc": voc_packet,
                    "route_matrix": route_matrix,
                    "workflow_state": {},
                    "report_writer_narrative": {},
                },
            )

            self.assertEqual(len(analysis["reference_asin_pool"]), 1)
            self.assertEqual(analysis["category_opportunity"]["price_band_opportunity"][0]["price_band"], "$20-$30")
            self.assertEqual(analysis["category_opportunity"]["category_seasonality"][0]["trend_source"], "category_trend")
            self.assertEqual(len(analysis["keyword_pool"]["roles"]["mixed_or_excluded"]), 1)
            new_release = analysis["category_opportunity"]["new_release_opportunity"][0]
            self.assertGreaterEqual(new_release["new_release_opportunity_score"], 35)
            self.assertIn(new_release["new_release_opportunity_level"], {"watch", "strong"})
            mixed_keyword = analysis["keyword_pool"]["roles"]["mixed_or_excluded"][0]
            self.assertGreaterEqual(mixed_keyword["mix_pool_score"], 70)
            self.assertEqual(mixed_keyword["mix_pool_risk_level"], "high")
            self.assertIn("run_status_audit", analysis)
            self.assertTrue(analysis["run_status_audit"]["citation_checks"]["has_category_derivation"])
            self.assertTrue(
                any(step.get("evidence_points") for step in analysis["category_selection_derivation"]["steps"])
            )
            self.assertTrue(analysis["category_selection_derivation"]["disconfirming_evidence"])

            html = render_html_report(analysis)
            for text in ["市场是否值得继续看", "为什么还不能直接立项", "下一步", "风险 / 缺口 / 下一步", "什么证据会推翻当前判断", "参考 ASIN", "大类 / 小类市场分析", "关键词与需求信号", "价格带机会", "混池/排除词", "类目淡旺季"]:
                self.assertIn(text, html)
            for forbidden in ["供应商预审", "主市场均价", "资深亚马逊运营专家视角", "资深亚马逊运营视角", "stage_7_integrated_precheck_report", "含义待解释"]:
                self.assertNotIn(forbidden, html)
            self.assertIn("fact-row", html)
            self.assertNotIn("<p>；</p>", html)
            self.assertIn("break-inside: avoid", html)
            self.assertIn("min-width: max(1180px, 100%)", html)
            self.assertIn("min-width: 0;", html)
            self.assertIn("max-width: 100%;", html)

            sheet_names = [name for name, _rows in build_workbook_sheets(analysis)]
            for name in ["Reference ASINs", "Category Candidates", "Keyword Pool", "Market Opportunity", "Route Judgment", "Risks And Next"]:
                self.assertIn(name, sheet_names)
            keyword_sheet = dict(build_workbook_sheets(analysis))["Keyword Pool"]
            self.assertIn("mix_pool_score", keyword_sheet[0])
            derivation_sheet = dict(build_workbook_sheets(analysis))["Category Derivation"]
            self.assertEqual(derivation_sheet[0], ["section", "step", "evidence", "implication", "decision", "lineage"])
            self.assertTrue(any(row and row[0] == "step" for row in derivation_sheet))

    def test_audit_run_status_reports_stage_gap_and_next_action(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir) / "generic_run"
            run_dir.mkdir()
            (run_dir / "workflow_state.json").write_text(
                json.dumps(
                    {
                        "workflow_id": "generic_run",
                        "stage": "stage_5_1_route_sorftime_calibration_completed",
                        "initial_intent": "测试方向",
                        "known_inputs": {"stage1_quick_probe_summary": "已快探"},
                        "missing_inputs": ["评论插件导出数据"],
                        "next_actions": [
                            {
                                "stage": "stage_6_voc_waiting_review_export",
                                "question": "等待评论导出",
                                "recommended_action": {
                                    "type": "review_crawl",
                                    "label": "抓取评论 VOC",
                                    "reason": "需要评论证据验证痛点。",
                                },
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (run_dir / "import_manifest.json").write_text(
                json.dumps(
                    {
                        "files": [{"file_name": "market.xlsx", "parse_status": "parsed", "warnings": []}],
                        "data_quality": {
                            "available_source_types": ["seller_sprite_market_analysis", "amazon_aba_keywords"],
                            "missing_source_types": ["seller_sprite_reverse_asin_keywords"],
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (run_dir / "candidate_pool.json").write_text(json.dumps({"candidates": []}), encoding="utf-8")
            (run_dir / "candidate_pool.json").write_text(json.dumps({"candidates": []}), encoding="utf-8")
            (run_dir / "research_package.json").write_text(json.dumps({}), encoding="utf-8")
            (run_dir / "mcp").mkdir()
            (run_dir / "mcp" / "route_sorftime_calibration.json").write_text("{}", encoding="utf-8")
            (run_dir / "review_asin_batch.json").write_text("{}", encoding="utf-8")

            audit = audit_run_status(run_dir)

        self.assertEqual(audit["current_stage"]["status"], "pending")
        self.assertTrue(any(item["item"] == "评论插件导出数据" for item in audit["blockers"]))
        self.assertIn("抓取评论 VOC", [item["label"] for item in audit["next_actions"]])

    def test_parse_top100_dimensions_confidence_layers_and_capture_groups(self) -> None:
        products = [
            {"asin": "B000000001", "title": "Premium 12 Inch Window Squeegee Large Kit", "monthly_sales": 100},
            {"asin": "B000000002", "title": "Medium microfiber cleaning tool", "monthly_sales": 80},
            {"asin": "B000000003", "title": "Generic cleaning tool", "monthly_sales": 10},
        ]
        rules = {
            "dimensions": [
                {
                    "name": "尺寸",
                    "label": "size",
                    "rules": [
                        {"type": "regex", "pattern": r"(\d+)\s*inch", "value": "$1 inch", "confidence": "high"},
                        {"type": "keyword", "keywords": ["small", "medium", "large"], "confidence": "medium"},
                    ],
                    "default": "未知",
                }
            ]
        }

        parsed, uncertain = parse_top100_dimensions(products, rules)

        self.assertEqual(parsed[0]["parsed_dimensions"]["size"]["value"], "12 inch")
        self.assertEqual(parsed[0]["parsed_dimensions"]["size"]["parse_confidence"], "high")
        self.assertEqual(parsed[1]["parsed_dimensions"]["size"]["value"], "medium")
        self.assertEqual(parsed[1]["parsed_dimensions"]["size"]["parse_confidence"], "medium")
        self.assertEqual(parsed[2]["parsed_dimensions"]["size"]["value"], "未知")
        self.assertEqual(parsed[2]["parsed_dimensions"]["size"]["parse_confidence"], "low")
        self.assertEqual(uncertain, [{"asin": "B000000003", "title": "Generic cleaning tool", "uncertain_dimensions": ["size"]}])

    def test_cross_analysis_builds_matrix_gaps_and_thresholds(self) -> None:
        products = [
            {
                "asin": "B000000001",
                "monthly_sales": 100,
                "monthly_revenue": 1000,
                "parsed_dimensions": {"size": {"value": "large"}, "price_band": {"value": "high"}, "material": {"value": "steel"}},
            },
            {
                "asin": "B000000002",
                "monthly_sales": 60,
                "monthly_revenue": 600,
                "parsed_dimensions": {"size": {"value": "small"}, "price_band": {"value": "low"}, "material": {"value": "plastic"}},
            },
            {
                "asin": "B000000003",
                "monthly_sales": 40,
                "monthly_revenue": 400,
                "parsed_dimensions": {"size": {"value": "small"}, "price_band": {"value": "high"}, "material": {"value": "plastic"}},
            },
        ]
        config = {
            "pairs": [
                {"dim1": "size", "dim2": "price_band", "scarcity_threshold": 1},
                {"dim1": "material", "dim2": "price_band", "scarcity_threshold": 2},
            ]
        }

        result = build_cross_analysis(products, config)

        self.assertEqual(len(result), 2)
        first = result[0]
        self.assertEqual(first["dim1"], "size")
        self.assertEqual(first["dim2"], "price_band")
        self.assertEqual(len(first["matrix"]), 4)
        blank_gap = next(item for item in first["gaps"] if item["dim1_value"] == "large" and item["dim2_value"] == "low")
        self.assertEqual(blank_gap["gap_type"], "空白")
        thin_gap = next(item for item in first["gaps"] if item["dim1_value"] == "large" and item["dim2_value"] == "high")
        self.assertEqual(thin_gap["gap_type"], "薄供给")
        self.assertEqual(thin_gap["products"], ["B000000001"])

    def test_cross_analysis_accepts_empty_product_list(self) -> None:
        result = build_cross_analysis([], {"pairs": [{"dim1": "size", "dim2": "price_band"}]})

        self.assertEqual(result[0]["matrix"], [])
        self.assertEqual(result[0]["gaps"], [])

    def test_research_data_packet_is_structured_and_serializable(self) -> None:
        candidate_pool = {
            "metadata": {"site": "US", "pool_id": "pool-1"},
            "source_brief": {},
            "candidates": [
                {
                    "candidate_id": "cand-1",
                    "name": "Window Cleaning Kit",
                    "candidate_type": "market_direction",
                    "status": "观察",
                    "reason": "候选池原始状态说明",
                    "top_products": [
                        {
                            "asin": "B000000001",
                            "title": "Premium 12 Inch Window Squeegee Kit",
                            "price": 19.99,
                            "monthly_sales": 120,
                            "monthly_units": 120,
                            "monthly_revenue": 2398.8,
                        },
                        {
                            "asin": "B000000002",
                            "title": "Medium Window Cleaning Kit",
                            "price": 12.99,
                            "monthly_sales": 80,
                            "monthly_units": 80,
                            "monthly_revenue": 1039.2,
                        },
                    ],
                    "market_structure": {},
                    "dimension_rules": {
                        "dimensions": [
                            {
                                "name": "尺寸",
                                "label": "size",
                                "rules": [
                                    {"type": "regex", "pattern": r"(\d+)\s*inch", "value": "$1 inch", "confidence": "high"},
                                    {"type": "keyword", "keywords": ["medium"], "confidence": "medium"},
                                ],
                                "default": "未知",
                            }
                        ]
                    },
                    "cross_config": {"pairs": [{"dim1": "size", "dim2": "price_band", "scarcity_threshold": 1}]},
                    "price_band_context": {
                        "avg_price_usd": 18.99,
                        "top_price_band_by_units": "10-20",
                        "top_price_band_units_share": 0.42,
                        "note": "仅用于市场价格带判断。",
                    },
                    "demand_evidence": {},
                    "competition_structure": {},
                }
            ],
        }

        data_packet = build_research_data_packet(candidate_pool, "cand-1")

        json.dumps(data_packet, ensure_ascii=False)
        self.assertNotIn("decision_review", data_packet)
        self.assertNotIn("ai_analysis", data_packet)
        self.assertNotIn("status_card", data_packet)
        self.assertNotIn("opportunity_hypotheses", data_packet)
        self.assertEqual(data_packet["data_packet_version"], "P28.4")
        self.assertEqual(data_packet["market_structure"]["scripted_dimension_parse"]["dimension_count"], 1)
        self.assertEqual(data_packet["market_structure"]["scripted_cross_analysis"]["pair_count"], 1)
        self.assertEqual(data_packet["normalized_tables"]["top_product_tags"][0]["attribute_tags"]["size"], "12 inch")

    def test_research_package_generates_insights_from_data_packet(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            candidate_pool = build_candidate_pool(
                _minimal_import_manifest(Path(tmp)),
                sorftime_verification=_sample_sorftime_verification(),
            )
        candidate = candidate_pool["candidates"][0]

        research_package = build_research_package(candidate_pool, candidate["candidate_id"])

        self.assertIn("decision_review", research_package)
        self.assertIn("ai_analysis", research_package)
        self.assertIn("status_card", research_package)
        self.assertEqual(research_package["data_packet_version"], "P28.4")

    def test_sorftime_adapter_name_and_legacy_alias(self) -> None:
        snapshot = {
            "fetched_at": "2026-06-12T00:00:00Z",
            "product_list": [{"asin": "B000000001", "title": "Sample", "monthly_sales": 120}],
            "keyword_data": [{"keyword": "sample keyword", "monthly_search_volume": 1000}],
            "category_trend": {"category_name": "Sample Category", "trend_direction": "增长"},
        }

        self.assertIs(SortimeAdapter, SorftimeAdapter)
        adapter = SorftimeAdapter(snapshot)
        self.assertEqual(adapter.fetch_products()[0].asin, "B000000001")
        self.assertEqual(adapter.fetch_keywords()[0].keyword, "sample keyword")
        self.assertEqual(adapter.fetch_category().category_name, "Sample Category")  # type: ignore[union-attr]

    def test_xlsx_writer_produces_readable_workbook(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "sample.xlsx"
            write_xlsx(output, [("长Sheet名称/需要清理[]:*?", [["标题", "说明"], ["A", "中文内容"]])])
            workbook = load_workbook(output, read_only=True, data_only=True)

            self.assertEqual(workbook.sheetnames[0], "长Sheet名称_需要清理_____")
            sheet = workbook[workbook.sheetnames[0]]
            self.assertEqual(sheet["A2"].value, "A")
            self.assertEqual(sheet["B2"].value, "中文内容")

    def test_validate_research_outputs_accepts_minimal_complete_workflow(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workflow_dir = Path(tmp)
            final_report = workflow_dir / "final_report"
            final_report.mkdir()
            _write_minimal_workflow_summary(workflow_dir)
            (final_report / "report.md").write_text(_minimal_formal_report_markdown(), encoding="utf-8")
            (final_report / "report.html").write_text(_minimal_formal_report_html(), encoding="utf-8")
            write_xlsx(final_report / "data.xlsx", _minimal_delivery_sheets(top100_rows=100))

            result = validate_workflow_output(workflow_dir)

        self.assertTrue(result.ok, result.errors)
        self.assertFalse(result.warnings)

    def test_validate_research_outputs_accepts_interactive_workflow(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workflow_dir = Path(tmp)
            final_report = workflow_dir / "final_report"
            final_report.mkdir()
            _write_minimal_workflow_summary(workflow_dir, interactive=True)
            (final_report / "report.md").write_text(_minimal_formal_report_markdown(interactive=True), encoding="utf-8")
            (final_report / "report.html").write_text(_minimal_formal_report_html(), encoding="utf-8")
            write_xlsx(final_report / "data.xlsx", _minimal_delivery_sheets(top100_rows=100, interactive=True))

            result = validate_workflow_output(workflow_dir)

        self.assertTrue(result.ok, result.errors)
        self.assertFalse(result.warnings)

    def test_validate_research_outputs_reports_missing_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workflow_dir = Path(tmp)
            final_report = workflow_dir / "final_report"
            final_report.mkdir()
            _write_minimal_workflow_summary(workflow_dir)
            (final_report / "report.md").write_text(_minimal_formal_report_markdown(), encoding="utf-8")

            result = validate_workflow_output(workflow_dir)

        self.assertFalse(result.ok)
        self.assertTrue(any("report.html" in item for item in result.errors))
        self.assertTrue(any("data.xlsx" in item for item in result.errors))

    def test_validate_research_outputs_errors_when_analysis_modes_are_insufficient(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workflow_dir = Path(tmp)
            final_report = workflow_dir / "final_report"
            final_report.mkdir()
            _write_minimal_workflow_summary(workflow_dir)
            sparse_report = "\n".join(
                ["# 测试调研报告", ""]
                + [line for title in FORMAL_REPORT_SECTION_TITLES for line in (f"## {title}", "", "- 测试内容", "")]
                + ["- 数据来源说明 / 状态卡 / 下一步 / 待补项"]
            )
            (final_report / "report.md").write_text(sparse_report, encoding="utf-8")
            (final_report / "report.html").write_text(_minimal_formal_report_html(), encoding="utf-8")
            write_xlsx(final_report / "data.xlsx", _minimal_delivery_sheets(top100_rows=100))

            result = validate_workflow_output(workflow_dir)

        self.assertFalse(result.ok)
        self.assertTrue(any("分析模式少于 3 种" in item for item in result.errors))

    def test_validate_research_outputs_errors_when_report_is_too_short(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workflow_dir = Path(tmp)
            _write_complete_delivery(
                workflow_dir,
                _minimal_formal_report_markdown(line_count=80, chain_count=3, attribute_distribution_count=2),
            )

            result = validate_workflow_output(workflow_dir)

        self.assertFalse(result.ok)
        self.assertTrue(any("report.md 总行数少于 200 行" in item for item in result.errors))

    def test_validate_research_outputs_errors_when_executive_chains_are_insufficient(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workflow_dir = Path(tmp)
            _write_complete_delivery(
                workflow_dir,
                _minimal_formal_report_markdown(line_count=220, chain_count=2, attribute_distribution_count=2),
            )

            result = validate_workflow_output(workflow_dir)

        self.assertFalse(result.ok)
        self.assertTrue(any("数据点 -> 含义 -> 行动建议" in item for item in result.errors))

    def test_validate_research_outputs_accepts_quantitative_report_thresholds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workflow_dir = Path(tmp)
            _write_complete_delivery(
                workflow_dir,
                _minimal_formal_report_markdown(line_count=220, chain_count=3, attribute_distribution_count=2),
            )

            result = validate_workflow_output(workflow_dir)

        self.assertTrue(result.ok, result.errors)

    def test_render_markdown_uses_formal_report_sections(self) -> None:
        package = _load_json("examples/minimal_research_package.json")
        report = render_markdown(package)
        positions = [report.index(f"## {title}") for title in FORMAL_REPORT_SECTION_TITLES]

        self.assertEqual(positions, sorted(positions))
        self.assertIn("## Executive Summary / 当前结论", report)
        self.assertIn("## 下一步动作与证据附录", report)

    def test_render_report_html_contains_formal_report_links(self) -> None:
        package = _load_json("examples/minimal_research_package.json")
        report = render_report_html(package)

        self.assertIn("<!doctype html>", report)
        self.assertIn('<html lang="zh-CN">', report)
        self.assertIn("选品决策报告", report)
        self.assertIn("一眼看懂", report)
        self.assertIn("市场机会评分", report)
        self.assertIn('href="data.xlsx" download', report)
        self.assertIn('href="report.md" download', report)
        self.assertIn("下载 Excel 报表", report)
        self.assertIn("下载 Markdown 报告", report)
        self.assertNotIn('href="summary.md"', report)
        self.assertNotIn('href="dashboard.html"', report)
        self.assertNotIn("旧版摘要看板", report)

    def test_render_markdown_includes_interactive_workflow_trace(self) -> None:
        package = _load_json("examples/minimal_research_package.json")
        package["workflow_trace"] = _sample_workflow_trace()
        report = render_markdown(package)

        self.assertIn("### 交互式流程状态", report)
        self.assertIn("workflow-001", report)
        self.assertIn("确认主线为窗户清洁组合工具", report)
        self.assertIn("### 关键决策记录", report)

    def test_data_workbook_includes_interactive_decision_sheet(self) -> None:
        package = _load_json("examples/minimal_research_package.json")
        package["workflow_trace"] = _sample_workflow_trace()
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "data.xlsx"
            render_data_workbook(package, output)
            workbook = load_workbook(output, read_only=True, data_only=True)
            sheet = workbook["交互决策记录"]
            values = [row[0] for row in sheet.iter_rows(values_only=True)]

        self.assertIn("流程状态", values)
        self.assertIn("决策记录", values)

    def test_contract_validators_reject_missing_handoff_fields(self) -> None:
        with self.assertRaisesRegex(ContractValidationError, "metadata"):
            validate_import_manifest({"files": [], "data_quality": {}})

        with self.assertRaisesRegex(ContractValidationError, "candidates"):
            validate_candidate_pool({"metadata": {}, "source_brief": {}, "candidates": []})

        with self.assertRaisesRegex(ContractValidationError, "normalized_tables"):
            validate_research_package({"metadata": {"candidate_id": "cand-1"}})

        with self.assertRaisesRegex(ContractValidationError, "workflow_id"):
            validate_workflow_state({"mode": "targeted_deep_dive", "stage": "intent_intake"})

    def test_contract_validators_accept_minimal_handoff_packages(self) -> None:
        validate_import_manifest(
            {
                "metadata": {"site": "US", "task_name": "测试任务"},
                "files": [],
                "data_quality": {"available_source_types": [], "missing_source_types": []},
            }
        )
        validate_candidate_pool(
            {
                "metadata": {"site": "US"},
                "source_brief": {},
                "candidates": [
                    {
                        "candidate_id": "cand-1",
                        "name": "测试方向",
                        "status": "观察",
                        "demand_evidence": {},
                        "competition_structure": {},
                        "top_products": [],
                    }
                ],
            }
        )
        validate_research_package(
            {
                "metadata": {"candidate_id": "cand-1"},
                "normalized_tables": {"candidate": {}, "top100": []},
                "market_structure": {},
                "decision_review": {"go_nogo_scorecard": {}},
                "status_card": {},
            }
        )
        validate_workflow_state(_sample_workflow_state())

    def test_research_package_chapter_validator_rejects_missing_metadata_site(self) -> None:
        package = _valid_research_package_for_chapter_validation()
        del package["metadata"]["site"]

        with self.assertRaisesRegex(ContractValidationError, "research_package.metadata.site"):
            validate_research_package_chapters(package)

    def test_research_package_chapter_validator_rejects_missing_decision_review(self) -> None:
        package = _valid_research_package_for_chapter_validation()
        del package["decision_review"]

        with self.assertRaisesRegex(ContractValidationError, "research_package.decision_review"):
            validate_research_package_chapters(package)

    def test_research_package_chapter_validator_accepts_complete_package(self) -> None:
        validate_research_package_chapters(_valid_research_package_for_chapter_validation())

    def test_sorftime_category_report_and_price_band_context_flow_to_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            candidate_pool = build_candidate_pool(
                _minimal_import_manifest(Path(tmp)),
                sorftime_verification=_sample_sorftime_verification(),
            )
        candidate = candidate_pool["candidates"][0]
        research_package = build_research_package(candidate_pool, candidate["candidate_id"])
        report = render_markdown(research_package)

        self.assertEqual(candidate["demand_evidence"]["sorftime_category_report"]["product_count"], 2)
        self.assertIn("price_band_context", candidate)
        self.assertEqual(candidate["price_band_context"]["note"], "仅用于判断市场价格带和新品切入口，不做后置落地测算。")
        self.assertIn("Sorftime category_report 快照", report)
        self.assertIn("价格带", report)
        self.assertEqual(research_package["price_band_context"]["top_price_band_by_units"], candidate["price_band_context"]["top_price_band_by_units"])

    def test_research_package_records_expert_ai_analysis_persona(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            candidate_pool = build_candidate_pool(
                _minimal_import_manifest(Path(tmp)),
                sorftime_verification=_sample_sorftime_verification(),
            )
        candidate = candidate_pool["candidates"][0]
        voc_package = {
            "summary": {
                "review_count": 42,
                "asin_count": 3,
                "low_rating_count": 8,
                "media_review_count": 5,
            },
            "normalized_reviews": [],
            "pain_points": [],
            "highlights": [],
        }

        research_package = build_research_package(candidate_pool, candidate["candidate_id"], voc_package)
        report = render_report_html(research_package)

        self.assertEqual(research_package["ai_analysis"]["persona"], "资深亚马逊运营专家")
        self.assertIn("卖家精灵", research_package["ai_analysis"]["data_source_scope"][0])
        self.assertIn("Sorftime", research_package["ai_analysis"]["data_source_scope"][1])
        self.assertIn("评价插件", research_package["ai_analysis"]["data_source_scope"][2])
        self.assertIn("路线矩阵", research_package["ai_analysis"]["data_source_scope"][3])
        self.assertIn("资深亚马逊运营专家视角", report)
        self.assertIn("AI 综合分析", report)
        self.assertIn("数据越多越好，但不是拿来堆字", report)
        self.assertIn("四份数据怎么一起看", report)
        self.assertIn("评论要变成怎么改", report)

    def test_voc_risk_matrix_uses_summary_when_findings_are_not_curated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            candidate_pool = build_candidate_pool(_minimal_import_manifest(Path(tmp)))
        candidate = candidate_pool["candidates"][0]
        voc_package = {
            "summary": {
                "review_count": 399,
                "asin_count": 4,
                "low_rating_count": 77,
                "media_review_count": 32,
            },
            "normalized_reviews": [
                {
                    "review_id": "R1",
                    "asin": "B000000001",
                    "rating": 2,
                    "review_text": "Belt loosens during running.",
                }
            ],
            "pain_points": [],
            "highlights": [],
        }

        research_package = build_research_package(candidate_pool, candidate["candidate_id"], voc_package)
        voc_risk = next(
            item for item in research_package["decision_review"]["risk_matrix"]
            if item["dimension"] == "评论/VOC"
        )

        self.assertEqual(voc_risk["level"], "中")
        self.assertIn("已接入 399 条评论", voc_risk["basis"])
        self.assertIn("覆盖 4 个 ASIN", voc_risk["basis"])
        self.assertIn("低分 77 条", voc_risk["basis"])
        self.assertNotIn("未接入评论 VOC", voc_risk["basis"])

    def test_product_route_matrix_keeps_dual_leash_waist_bag_route(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            candidate_pool = build_candidate_pool(_minimal_import_manifest(Path(tmp)))
        candidate = candidate_pool["candidates"][0]
        candidate["name"] = "宠物牵引绳 / dog leash"
        candidate["product_route_profile"] = _dog_leash_route_profile()
        candidate.setdefault("competitor_candidates", {})["recent_winners"] = [
            {
                "asin": "B0DUALWAIST",
                "title": "SparklyPets Double Bungee Waist 2 Dog Leash with Running Belt Fanny Pack",
                "price": 39.99,
                "monthly_units": 1200,
                "rating_count": 2800,
            }
        ]
        candidate.setdefault("market_structure", {})["tagged_products"] = [
            {
                "asin": "B0DUALWAIST",
                "title": "Double Bungee Waist 2 Dog Leash with Running Belt Fanny Pack",
                "price": 39.99,
            },
            {
                "asin": "B0BASICWAIST",
                "title": "Dual Leash Hands Free Dog Leash with Waist Belt and Pouch",
                "price": 24.99,
            },
        ]

        research_package = build_research_package(candidate_pool, candidate["candidate_id"])
        routes = {item["route_id"]: item for item in research_package["product_route_matrix"]}
        route_plan = {item["route_id"]: item for item in research_package["route_deep_dive_plan"]}
        html = render_report_html(research_package)

        self.assertIn("upgraded_core", routes)
        self.assertGreaterEqual(routes["upgraded_core"]["candidate_count"], 1)
        self.assertIn("双牵引绳 + 腰包", routes["upgraded_core"]["route_name"])
        self.assertIn("scenario_specialized", routes)
        self.assertIn("upgraded_core", route_plan)
        self.assertEqual(route_plan["upgraded_core"]["recommended_depth"], "必须路线小深挖")
        self.assertIn("双牵引绳 腰包", route_plan["upgraded_core"]["route_search_terms"])
        self.assertTrue(route_plan["upgraded_core"]["review_voc_asin_plan"])
        self.assertIn("产品路线对比", html)
        self.assertIn("路线级小深挖计划", html)
        self.assertIn("双牵引绳 + 腰包/腰带", html)

    def test_product_route_matrix_is_generic_for_window_squeegee(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            candidate_pool = build_candidate_pool(_minimal_import_manifest(Path(tmp)))
        candidate = candidate_pool["candidates"][0]
        candidate.setdefault("competitor_candidates", {})["recent_winners"] = [
            {
                "asin": "B0SQUEEGEE1",
                "title": "2 in 1 Window Squeegee Cleaning Kit with Extendable Pole and Replacement Microfiber Pads",
                "price": 24.99,
                "monthly_units": 900,
                "rating_count": 580,
            }
        ]
        candidate.setdefault("market_structure", {})["tagged_products"] = [
            {
                "asin": "B0SQUEEGEE1",
                "title": "2 in 1 Window Squeegee Cleaning Kit with Extendable Pole and Replacement Microfiber Pads",
                "price": 24.99,
            },
            {
                "asin": "B0SQUEEGEE2",
                "title": "Window Cleaning Kit Set with Replacement Pads",
                "price": 19.99,
            },
        ]

        research_package = build_research_package(candidate_pool, candidate["candidate_id"])
        routes = {item["route_id"]: item for item in research_package["product_route_matrix"]}
        route_plan = {item["route_id"]: item for item in research_package["route_deep_dive_plan"]}
        names = " ".join(str(route.get("route_name")) for route in routes.values())

        self.assertIn("base_core", routes)
        self.assertIn("upgraded_core", routes)
        self.assertIn("bundle_or_set", routes)
        self.assertIn("scenario_specialized", routes)
        self.assertIn("窗户刮水器", names)
        self.assertIn("extendable", names)
        self.assertTrue(any("套装" in term for term in route_plan["bundle_or_set"]["route_search_terms"]))
        self.assertNotIn("牵引绳", names)
        self.assertNotIn("腰包", names)

    def test_market_boundary_filters_off_category_competitors_and_downgrades_score(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            candidate_pool = build_candidate_pool(_minimal_import_manifest(Path(tmp)))
        candidate = candidate_pool["candidates"][0]
        candidate["name"] = "窗户刮水器 / window squeegee"
        candidate.setdefault("demand_evidence", {})["top_keyword"] = "car accessories"
        candidate["demand_evidence"]["aba_keyword_signal"] = {
            "top_keywords": [
                {"keyword": "window squeegee", "monthly_searches": 84045},
                {"keyword": "window cleaning kit", "monthly_searches": 47039},
            ]
        }
        candidate.setdefault("market_structure", {})["tagged_products"] = [
            {"asin": "B0SQUEEGEE1", "title": "Window Squeegee Cleaning Kit with Extendable Pole"},
            {"asin": "B0SQUEEGEE2", "title": "Shower Squeegee for Glass Doors and Window Cleaning"},
        ]
        candidate.setdefault("competitor_candidates", {})["top10"] = [
            {
                "asin": "B0SQUEEGEE1",
                "title": "Window Squeegee Cleaning Kit with Extendable Pole",
                "monthly_units": 900,
            }
        ]
        candidate["competitor_candidates"]["recent_winners"] = [
            {
                "asin": "B0WIPES",
                "title": "DUDE Wipes Flushable Adult Wet Wipes Coffee Scented",
                "monthly_units": 300604,
            }
        ]
        candidate["competitor_candidates"]["structure_supplement"] = [
            {
                "asin": "B0BATTERY",
                "title": "Amazon Basics 12-Pack AA Alkaline Batteries",
                "monthly_units": 386097,
            }
        ]
        voc_package = {
            "summary": {"review_count": 1143, "asin_count": 12, "low_rating_count": 295},
            "normalized_reviews": [
                {
                    "review_id": "R1",
                    "asin": "B0SQUEEGEE1",
                    "rating": 1,
                    "review_text": "Leaves streaks and the rubber blade falls apart.",
                }
            ],
            "pain_points": [],
            "highlights": [],
        }

        research_package = build_research_package(candidate_pool, candidate["candidate_id"], voc_package)
        scorecard = research_package["decision_review"]["go_nogo_scorecard"]
        audit = research_package["competitor_pool"]["market_boundary_audit"]
        effective_competitors = json.dumps(
            {
                "competitor_pool": {
                    "top10": research_package["competitor_pool"]["top10"],
                    "recent_winners": research_package["competitor_pool"]["recent_winners"],
                    "structure_supplement": research_package["competitor_pool"]["structure_supplement"],
                },
                "competitor_deep_dive": research_package["competitor_deep_dive"],
                "selection_logic": research_package["competitor_selection_logic"],
            },
            ensure_ascii=False,
        )

        self.assertEqual(audit["excluded_competitor_count"], 2)
        self.assertNotIn("DUDE Wipes", effective_competitors)
        self.assertNotIn("AA Alkaline Batteries", effective_competitors)
        self.assertLessEqual(scorecard["dimensions"]["小类边界清晰度"]["score"], 4.5)
        self.assertLessEqual(scorecard["dimensions"]["数据完整度"]["score"], 6.0)
        self.assertTrue(any("竞品池存在" in item for item in scorecard["gating_reasons"]))
        self.assertTrue(research_package["voc_analysis"]["pain_points"])

    def test_product_route_matrix_does_not_leak_fixture_categories_for_new_category(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manifest = _minimal_import_manifest(Path(tmp))
            manifest["metadata"]["task_name"] = "爆米花机 / popcorn maker"
            candidate_pool = build_candidate_pool(manifest)
        candidate = candidate_pool["candidates"][0]
        candidate["name"] = "爆米花机 / popcorn maker"
        candidate.setdefault("demand_evidence", {})["top_keyword"] = "popcorn maker"
        candidate.setdefault("competitor_candidates", {})["recent_winners"] = [
            {
                "asin": "B0POPCORN1",
                "title": "Hot Air Popcorn Maker with Measuring Cup and Removable Chute",
                "price": 29.99,
                "monthly_units": 1500,
                "rating_count": 4200,
            }
        ]
        candidate.setdefault("market_structure", {})["tagged_products"] = [
            {
                "asin": "B0POPCORN1",
                "title": "Hot Air Popcorn Maker with Measuring Cup and Removable Chute",
                "price": 29.99,
            }
        ]

        research_package = build_research_package(candidate_pool, candidate["candidate_id"])
        rendered = json.dumps(research_package, ensure_ascii=False)

        self.assertIn("爆米花机", rendered)
        self.assertIn("popcorn maker", rendered)
        for fixture_term in ("牵引绳", "狗绳", "腰包", "刮窗器", "刮水器", "window squeegee", "dog leash"):
            self.assertNotIn(fixture_term, rendered)

    def test_interactive_workflow_initial_broad_discovery_requires_operator_boundary(self) -> None:
        state = create_initial_state(
            workflow_id="wf-001",
            mode="broad_discovery",
            initial_intent="美国站家居清洁小工具",
            site="US",
        )

        self.assertEqual(state.stage, "intent_intake")
        self.assertTrue(state.decision_required)
        self.assertIn("场景/痛点", state.operator_question)
        self.assertEqual(state.next_actions[0].recommended_action.action_type, "operator_decision")

    def test_interactive_workflow_targeted_deep_dive_requires_product_boundary(self) -> None:
        state = create_initial_state(
            workflow_id="wf-002",
            mode="targeted_deep_dive",
            initial_intent="窗户刮水器二合一工具",
            site="US",
        )

        self.assertEqual(state.stage, "intent_intake")
        self.assertTrue(state.decision_required)
        self.assertIn("场景/痛点", state.operator_question)
        self.assertIn("产品边界", state.operator_question)

    def test_stage_four_and_five_force_route_confirmation(self) -> None:
        base = create_initial_state(
            workflow_id="wf-004",
            mode="targeted_deep_dive",
            initial_intent="窗户刮水器二合一工具",
            site="US",
        )
        candidate_review = _workflow_state_for_test(base, stage="candidate_pool_review")
        boundary = _workflow_state_for_test(base, stage="boundary_confirmation")
        voc_planning = _workflow_state_for_test(base, stage="voc_batch_planning")

        candidate_card = candidate_review.next_actions[0]
        boundary_card = boundary.next_actions[0]
        voc_card = voc_planning.next_actions[0]

        self.assertIn("产品路线矩阵", candidate_review.operator_question)
        self.assertIn("基础款", candidate_review.operator_question)
        self.assertTrue(any(option.id == "rename_routes" for option in candidate_card.options))
        self.assertIn("路线级小深挖", boundary_card.recommended_action.reason)
        self.assertTrue(any(option.id == "rename_route_by_shape" for option in boundary_card.options))
        self.assertIn("每条保留路线", voc_planning.operator_question)
        self.assertTrue(any(option.id == "call_route_extend" for option in voc_card.options))

    def test_interactive_workflow_advances_with_decision_log(self) -> None:
        state = create_initial_state(
            workflow_id="wf-003",
            mode="targeted_deep_dive",
            initial_intent="窗户刮水器二合一工具",
        )
        next_state = advance_stage(
            state,
            DecisionRecord(
                decision_id="decision-001",
                stage=state.stage,
                actor="operator",
                decision="确认主线为刮条+海绵垫窗户清洁工具",
                rationale="排除单独清洁液和汽车专用工具。",
            ),
        )

        self.assertEqual(next_state.stage, "exploration_planning")
        self.assertEqual(len(next_state.decision_log), 1)
        # targeted_deep_dive 的 exploration_planning 先做 Sorftime 前置快验，action_type 为 mcp_call
        self.assertEqual(next_state.next_actions[0].recommended_action.action_type, "mcp_call")

    def test_build_workflow_trace_preserves_decision_log_for_report(self) -> None:
        trace = build_workflow_trace(_sample_workflow_state(), Path("/tmp/workflow_state.json"))

        self.assertEqual(trace["workflow_state"]["workflow_id"], "workflow-001")
        self.assertEqual(trace["decision_log"][0]["decision"], "确认主线为窗户清洁组合工具")
        self.assertEqual(trace["next_actions"][0]["recommended_action"]["type"], "operator_export")
        self.assertTrue(trace["source_file"].endswith("/tmp/workflow_state.json"))

    def test_interactive_workflow_cli_writes_state_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "workflow_state.json"
            completed = subprocess.run(
                [
                    "python3",
                    str(ROOT / "scripts/plan_interactive_workflow.py"),
                    str(output),
                    "--mode",
                    "targeted_deep_dive",
                    "--intent",
                    "窗户刮水器二合一工具",
                    "--workflow-id",
                    "wf-cli",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            data = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(data["workflow_id"], "wf-cli")
        self.assertEqual(data["next_actions"][0]["recommended_action"]["type"], "operator_decision")

    @unittest.skipUnless(
        (ROOT / "卖家精灵导出样例_美国站_宠物牵引绳_20260607").exists(),
        "local SellerSprite sample folder is ignored and may be absent",
    )
    def test_manual_export_sample_builds_candidate_pool(self) -> None:
        from packages.research_core.pipeline.inspect_manual_exports import build_manifest

        source = ROOT / "卖家精灵导出样例_美国站_宠物牵引绳_20260607"
        with tempfile.TemporaryDirectory() as tmp:
            copied_source = Path(tmp) / source.name
            shutil.copytree(source, copied_source, ignore=shutil.ignore_patterns(".DS_Store"))
            manifest = build_manifest(copied_source, "美国站宠物牵引绳样例", "US")
            candidate_pool = build_candidate_pool(manifest)

        self.assertEqual(candidate_pool["summary"]["total_candidates"], 1)
        candidate = candidate_pool["candidates"][0]
        self.assertTrue(candidate["candidate_id"].startswith("cand-"))
        self.assertGreaterEqual(len(candidate.get("top_products", [])), 1)

    @unittest.skipUnless(
        (ROOT / "卖家精灵导出样例_美国站_宠物牵引绳_20260607").exists(),
        "local SellerSprite sample folder is ignored and may be absent",
    )
    def test_workflow_api_runs_manual_export_sample(self) -> None:
        source = ROOT / "卖家精灵导出样例_美国站_宠物牵引绳_20260607"
        with tempfile.TemporaryDirectory() as tmp:
            copied_source = Path(tmp) / source.name
            output_dir = Path(tmp) / "workflow"
            shutil.copytree(source, copied_source, ignore=shutil.ignore_patterns(".DS_Store"))

            result = run_research_workflow(
                WorkflowConfig(
                    manual_export_folder=copied_source,
                    output_dir=output_dir,
                    site="US",
                    task_name="Workflow API 回归",
                )
            )

            validation = validate_workflow_output(output_dir)

        self.assertTrue(result.report_path.name.endswith("report.md"))
        self.assertTrue(validation.ok, validation.errors)

    @unittest.skipUnless(
        (ROOT / "卖家精灵导出样例_美国站_宠物牵引绳_20260607").exists(),
        "local SellerSprite sample folder is ignored and may be absent",
    )
    def test_workflow_cli_stays_compatible(self) -> None:
        source = ROOT / "卖家精灵导出样例_美国站_宠物牵引绳_20260607"
        with tempfile.TemporaryDirectory() as tmp:
            copied_source = Path(tmp) / source.name
            output_dir = Path(tmp) / "workflow_cli"
            shutil.copytree(source, copied_source, ignore=shutil.ignore_patterns(".DS_Store"))

            completed = subprocess.run(
                [
                    "python3",
                    str(ROOT / "scripts/run_research_workflow.py"),
                    str(copied_source),
                    str(output_dir),
                    "--site",
                    "US",
                    "--task-name",
                    "Workflow CLI 回归",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            validation = validate_workflow_output(output_dir)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("Wrote workflow outputs", completed.stdout)
        self.assertTrue(validation.ok, validation.errors)


def _load_json(relative_path: str) -> dict:
    return json.loads((ROOT / relative_path).read_text(encoding="utf-8"))


def _write_minimal_workflow_summary(workflow_dir: Path, interactive: bool = False) -> None:
    summary = {
        "review_voc": {"enabled": False},
        "market_analysis": {"enabled": True, "status": "待补小类/关键词/竞品/VOC"},
    }
    if interactive:
        summary["interactive_workflow"] = {
            "enabled": True,
            "workflow_id": "workflow-001",
            "mode": "targeted_deep_dive",
            "stage": "seller_sprite_request",
            "decision_count": 1,
            "source_file": "/tmp/workflow_state.json",
        }
    (workflow_dir / "workflow_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (workflow_dir / "workflow_summary.md").write_text(
        "# 选品流程运行摘要\n\n- 市场机会分析：待补小类、关键词、竞品和评论 VOC\n",
        encoding="utf-8",
    )


def _write_complete_delivery(workflow_dir: Path, report_markdown: str) -> None:
    final_report = workflow_dir / "final_report"
    final_report.mkdir()
    _write_minimal_workflow_summary(workflow_dir)
    (final_report / "report.md").write_text(report_markdown, encoding="utf-8")
    (final_report / "report.html").write_text(_minimal_formal_report_html(), encoding="utf-8")
    write_xlsx(final_report / "data.xlsx", _minimal_delivery_sheets(top100_rows=100))


def _valid_research_package_for_chapter_validation() -> dict:
    return {
        "metadata": {
            "site": "US",
            "candidate_id": "cand-1",
            "seed_keyword_or_category": "window cleaning kit",
            "data_sources": ["seller-sprite-export"],
        },
        "normalized_tables": {"candidate": {}, "top100": []},
        "market_structure": {},
        "market_analysis": {
            "market_size": "样本 100 个",
            "price_band": "20-30 USD",
            "brand_concentration": "Top10 分散",
        },
        "review_sources": {},
        "voc_analysis": {},
        "decision_review": {
            "go_nogo_scorecard": {
                "weighted_score": 5.5,
                "decision": "WAIT",
            }
        },
        "competitor_selection_logic": [
            {
                "asin": "B000000001",
                "competitor_type": "Top10 标杆",
                "selection_reason": "测试",
            }
        ],
        "status_card": {},
    }


def _workflow_state_for_test(base, stage: str):
    from packages.research_core.workflows import WorkflowState, plan_next_action

    return plan_next_action(
        WorkflowState(
            workflow_id=base.workflow_id,
            mode=base.mode,
            stage=stage,
            initial_intent=base.initial_intent,
            site=base.site,
            known_inputs=base.known_inputs,
            missing_inputs=base.missing_inputs,
            evidence_refs=base.evidence_refs,
            decision_log=base.decision_log,
        )
    )


def _sample_workflow_state() -> dict:
    return {
        "workflow_id": "workflow-001",
        "mode": "targeted_deep_dive",
        "stage": "seller_sprite_request",
        "initial_intent": "窗户刮水器二合一工具",
        "site": "US",
        "known_inputs": {"confirmed_boundary": "刮条 + 海绵/布垫 + 窗户清洁组合工具"},
        "missing_inputs": ["卖家精灵搜索结果", "市场分析 Top100"],
        "decision_required": False,
        "operator_question": "请按 2 个主关键词导出搜索结果和市场分析。",
        "next_actions": [
            {
                "stage": "seller_sprite_request",
                "decision_required": False,
                "question": "请导出卖家精灵数据。",
                "recommended_action": {
                    "type": "operator_export",
                    "label": "导出卖家精灵搜索结果和市场分析",
                    "reason": "运营已确认产品边界，需要真实 Top100 数据进入候选池。",
                },
                "options": [
                    {"id": "export_now", "label": "立即导出", "impact": "进入数据盘点"},
                ],
                "evidence_refs": [
                    {"ref_type": "decision", "ref_id": "decision-001", "path": "", "note": "边界确认"},
                ],
            }
        ],
        "evidence_refs": [
            {"ref_type": "selection_brief", "ref_id": "brief-001", "path": "/tmp/brief.json", "note": "初始意图"},
        ],
        "decision_log": [
            {
                "decision_id": "decision-001",
                "stage": "intent_intake",
                "actor": "operator",
                "decision": "确认主线为窗户清洁组合工具",
                "rationale": "排除单独清洁液，保留长杆和替换布垫。",
                "evidence_refs": [
                    {"ref_type": "conversation", "ref_id": "turn-001", "path": "", "note": "运营确认"},
                ],
                "created_at": "2026-06-12T00:00:00+00:00",
            }
        ],
        "updated_at": "2026-06-12T00:05:00+00:00",
    }


def _sample_workflow_trace() -> dict:
    return build_workflow_trace(_sample_workflow_state(), Path("/tmp/workflow_state.json"))


def _minimal_import_manifest(source_folder: Path) -> dict:
    return {
        "metadata": {
            "site": "US",
            "task_name": "窗户刮水器二合一工具",
            "generated_at": "2026-06-13T00:00:00+00:00",
            "manifest_id": "manifest-test",
            "source_folder": str(source_folder),
        },
        "files": [],
        "data_quality": {
            "available_source_types": ["sorftime"],
            "missing_source_types": [],
            "warnings": [],
        },
    }


def _sample_sorftime_verification() -> dict:
    return {
        "verified_at": "2026-06-13",
        "category_report_snapshot": {
            "category_name": "Squeegees",
            "nodeId": "2245500011",
            "products": [
                {
                    "asin": "B0SF000001",
                    "title": "2 in 1 Window Squeegee",
                    "brand": "BrandA",
                    "price": 19.99,
                    "monthly_sales": 1200,
                    "monthly_revenue": 23988,
                    "rating": 4.5,
                    "rating_count": 320,
                    "listing_days": 120,
                },
                {
                    "asin": "B0SF000002",
                    "title": "Window Cleaning Kit",
                    "brand": "BrandB",
                    "price": 24.99,
                    "monthly_sales": 800,
                    "monthly_revenue": 19992,
                    "rating": 4.3,
                    "rating_count": 180,
                    "listing_days": 260,
                },
            ],
        },
    }


def _dog_leash_route_profile() -> dict:
    return {
        "profile_id": "dog_leash_test_fixture",
        "route_overrides": {
            "base_core": {
                "route_name": "基础款：腰包/腰带 + 单牵引绳",
                "match_terms": ("腰包", "腰带", "腰部", "束腰", "pouch", "waist", "belt", "hands free"),
                "competitor_terms": ("hands free", "waist", "belt", "pouch", "bungee", "running", "jogging"),
                "review_terms": ("hands free", "waist", "belt", "pouch", "bungee", "running", "jogging", "腰", "免手持"),
                "route_search_terms": ["跑步牵引绳 腰包", "免手持 狗绳 腰带", "宠物跑步牵引绳 腰包", "腰带 弹力 牵引绳"],
            },
            "upgraded_core": {
                "route_name": "升级款：双牵引绳 + 腰包/腰带",
                "match_terms": ("一拖二", "双牵", "双头", "双体", "双套", "两犬", "两只狗", "多狗", "two dog", "dual leash"),
                "require_any_terms": ("腰包", "腰带", "腰部", "束腰", "pouch", "waist", "belt", "hands free", "免手持"),
                "competitor_terms": ("double", "dual dog", "dual leash", "two dog", "2 dog", "multiple dogs", "waist", "belt", "pouch"),
                "review_terms": ("double", "dual dog", "dual leash", "two dog", "two dogs", "2 dog", "2 dogs", "multiple dogs", "双", "两只", "多狗", "一拖二"),
                "route_search_terms": ["双牵引绳 腰包", "双狗 跑步 腰带", "一拖二 腰包 牵引绳", "双体 牵引绳 腰包"],
            },
            "adjacent_or_watch": {
                "route_name": "旁支观察：一拖二/斜挎/普通弹力绳",
                "match_terms": ("一拖二", "双头", "斜挎", "普通弹力绳", "splitter", "crossbody"),
                "route_search_terms": ["一拖二 狗绳", "双头 狗狗牵引绳", "双狗 防缠绕 牵引绳", "多狗 牵引绳"],
            },
        },
    }


def _minimal_delivery_sheets(top100_rows: int, interactive: bool = False) -> list[tuple[str, list[list[object]]]]:
    rows: list[list[object]] = [["ASIN", "标题", "价格", "月销量"]]
    for index in range(top100_rows):
        rows.append([f"B{index:09d}", f"测试商品 {index}", 19.99, 100 + index])
    return [
        ("数据来源说明", [["来源", "说明"], ["seller-sprite-export", "测试"]]),
        ("调研边界", [["字段", "值"], ["站点", "US"]]),
        ("市场结构", [["字段", "值"], ["市场规模", "测试"]]),
        ("Top100原始明细", rows),
        ("数据质量检查", [["字段", "值"], ["实际数量", top100_rows]]),
        ("属性定义", [["维度", "名称", "判定规则"], ["price_band", "价格带", "测试"], ["review_band", "评论门槛", "测试"], ["product_route", "产品路线", "测试"]]),
        ("Top商品打标", [["ASIN", "标题", "属性标签", "置信度"], ["B000000001", "测试", "{}", "高"]]),
        ("待确认标签", [["ASIN", "标题", "置信度"], ["B000000002", "测试", "低"]]),
        ("属性分布", [["维度", "名称", "分布摘要"], ["shape", "测试", "测试"]]),
        (
            "属性交叉分析",
            [
                ["交叉维度", "说明", "组合", "样本数"],
                ["价格带 x 销量层级", "测试", "", ""],
                ["上架时间 x 评论门槛", "测试", "", ""],
                ["产品路线 x 销量层级", "测试", "", ""],
            ],
        ),
        ("机会判断", [["交叉维度", "组合", "机会类型"], ["价格带 x 销量层级", "20-30 x 1000+", "待验证"]]),
        (
            "竞品选择逻辑",
            [
                ["ASIN", "品牌", "标题", "价格(USD)", "月销量", "评分", "评分数", "竞品类型", "覆盖维度", "选择理由"],
                ["B000000001", "BrandA", "测试", 19.99, 1000, 4.5, 200, "量级标杆", "销量量级", "测试"],
                ["B000000002", "BrandB", "测试", 25.99, 800, 4.4, 150, "近半年新品", "新品", "测试"],
                ["B000000003", "BrandC", "测试", 12.99, 500, 3.9, 80, "痛点参考", "评分/评论门槛", "测试"],
                ["B000000004", "BrandD", "测试", 29.99, 700, 4.2, 90, "功能差异代表", "功能/结构", "测试"],
                ["B000000005", "BrandE", "测试", 9.99, 600, 4.1, 70, "价格带覆盖", "低价带", "测试"],
                ["B000000006", "BrandF", "测试", 39.99, 400, 4.6, 300, "价格带覆盖", "高价带", "测试"],
                ["B000000007", "BrandG", "测试", 18.99, 550, 4.0, 120, "功能差异代表", "场景差异", "测试"],
                ["B000000008", "BrandH", "测试", 21.99, 530, 3.8, 60, "痛点参考", "低评分", "测试"],
                ["B000000009", "BrandI", "测试", 24.99, 510, 4.3, 110, "量级标杆", "销量量级", "测试"],
                ["B000000010", "BrandJ", "测试", 27.99, 490, 4.5, 95, "近半年新品", "新品", "测试"],
            ],
        ),
        ("竞品池", [["ASIN", "标题"], ["B000000001", "测试"]]),
        (
            "市场机会评分卡",
            [
                ["维度", "得分（满分10）", "权重", "加权得分", "依据"],
                ["市场规模", 6, "16%", 0.96, "测试"],
                ["竞争格局", 6, "16%", 0.96, "测试"],
                ["需求清晰度", 6, "14%", 0.84, "测试"],
                ["小类边界清晰度", 6, "12%", 0.72, "测试"],
                ["新品友好度", 6, "12%", 0.72, "测试"],
                ["VOC证据质量", 5, "14%", 0.7, "待补"],
                ["退货/体验风险", 5, "10%", 0.5, "待补"],
                ["数据完整度", 8, "12%", 0.96, "测试"],
                [],
                ["加权总分", 5.94, "", "", ""],
                ["决策结论", "WAIT", "", "", ""],
                ["决策限制", "小类、关键词、竞品和 VOC 证据待补", "", "", ""],
            ],
        ),
        ("决策检查", [["字段", "值"], ["状态", "观察"]]),
        ("风险矩阵", [["维度", "等级"], ["数据", "低"]]),
        ("状态卡", [["字段", "值"], ["状态", "观察"]]),
        ("路线深挖计划", [["路线", "当前证据", "下一步"], ["基础款", "待补", "补小类、关键词、竞品和 VOC"]]),
        *(
            [
                (
                    "交互决策记录",
                    [
                        ["类型", "阶段", "动作/决策", "角色/动作类型", "理由/问题", "证据", "时间/来源"],
                        ["流程状态", "seller_sprite_request", "workflow-001", "targeted_deep_dive", "请导出卖家精灵数据", "", "/tmp/workflow_state.json"],
                        ["决策记录", "intent_intake", "确认主线为窗户清洁组合工具", "operator", "排除单独清洁液", "conversation/turn-001", "2026-06-12T00:00:00+00:00"],
                    ],
                )
            ]
            if interactive
            else []
        ),
        ("评论VOC", [["字段", "值"], ["未接入", ""]]),
        (
            "VOC证据",
            [
                ["类型", "主题", "评论数", "等级", "评论ID", "ASIN", "采集入口站点", "评论地区", "评分", "日期", "证据片段", "链接"],
                ["痛点", "测试", 1, "中", "R1", "B000000001", "US", "United States", 2, "2026-01-01", "测试片段", "https://example.com"],
                ["痛点", "测试", 1, "中", "R2", "B000000002", "US", "United States", 3, "2026-01-02", "测试片段2", "https://example.com/2"],
                ["亮点", "测试", 1, "低", "R3", "B000000003", "US", "United States", 5, "2026-01-03", "测试片段3", "https://example.com/3"],
            ],
        ),
        ("退货风险", [["字段", "值"], ["状态", "待复核"]]),
    ]


def _minimal_formal_report_markdown(
    interactive: bool = False,
    line_count: int = 220,
    chain_count: int = 3,
    attribute_distribution_count: int = 2,
) -> str:
    lines = ["# 测试调研报告", ""]
    for title in FORMAL_REPORT_SECTION_TITLES:
        lines.extend([f"## {title}", "", "- 测试内容", ""])
        if title == "Executive Summary / 当前结论":
            lines.append("### 数据点 -> 含义 -> 行动建议")
            for index in range(chain_count):
                lines.append(f"- 数据点：测试数据 {index} -> 含义：测试含义 {index} -> 行动建议：测试动作 {index}")
            lines.append("")
        if title == "产品属性分布与交叉分析":
            lines.append("### 属性分布")
            for index in range(attribute_distribution_count):
                lines.append(f"- 测试维度{index}：测试分布")
            lines.append("")
        if title == "下一步动作与证据附录":
            lines.extend(
                [
                    "### 分析模式自检表",
                    "| 分析模式 | 使用状态 | 使用章节位置 | 未用原因 |",
                    "|---|---|---|---|",
                    "| 数据 -> 空白 -> 机会 | 已用 | 市场结构与数据质量 |  |",
                    "| 痛点 -> 产品方案 | 已用 | 评论 VOC 与真实痛点 |  |",
                    "| 数据点 -> 含义 -> 行动建议 | 已用 | Executive Summary / 当前结论 |  |",
                    "",
                ]
            )
    lines.append(
        "- 数据来源说明 / 状态卡 / 下一步 / 待补项；"
        "事实：Top100 有 100 行。推断：当前只适合作为测试交付。"
        "关键洞察：数据点、含义要转成行动建议。"
        "AI 综合分析：先看空白和机会，再看痛点到产品方案。"
        "交叉维度用于识别结构性空白；评分卡、优先级和加权结果用于 Go/Wait/No-Go。"
        "待补项必须转成验证动作和复核动作；竞品角色、VOC 和证据链必须互相对应。"
    )
    if interactive:
        lines.extend(["", "### 交互式流程状态", "- workflow_state 测试"])
        lines.extend(["", "### 交互式下一步动作", "- 下一步测试"])
        lines.extend(["", "### 关键决策记录", "- 决策测试"])
    filler_index = 0
    while len([line for line in lines if line.strip()]) < line_count:
        lines.append(f"- 补充测试行 {filler_index}：用于满足正式报告最小行数。")
        filler_index += 1
    return "\n".join(lines) + "\n"


def _minimal_formal_report_html() -> str:
    return (
        '<!doctype html><html lang="zh-CN"><head><title>选品决策报告</title></head>'
        "<body><h1>选品决策报告</h1><h2>一眼看懂</h2><h2>市场机会评分</h2></body></html>"
    )


if __name__ == "__main__":
    unittest.main()
