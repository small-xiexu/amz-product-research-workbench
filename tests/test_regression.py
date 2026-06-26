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

from packages.research_core.contracts import (
    ContractValidationError,
    validate_candidate_pool,
    validate_import_manifest,
    validate_workflow_state,
)
from packages.research_core.pipeline.build_route_matrix_confirmation import P3ContractError
from packages.research_core.workflows import DecisionRecord, advance_stage, create_initial_state

from packages.research_core.pipeline.audit_run_status import audit_run_status
from packages.research_core.pipeline.validate_research_outputs import validate_workflow_output
from packages.report_renderer.constants import FORMAL_REPORT_SECTION_TITLES
from packages.research_core.pipeline.constants import QA_RULE_VERSION
from packages.research_core.pipeline.build_analysis_packet import build_analysis_packet
from packages.research_core.pipeline.xlsx_back_table import build_workbook_sheets


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

    def test_analysis_report_uses_operator_research_objects(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir) / "generic_stage9_run"
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
            self.assertTrue(len(analysis["run_status_audit"]["stage_checks"]) > 0)
            self.assertTrue(
                any(step.get("evidence_points") for step in analysis["category_selection_derivation"]["steps"])
            )
            self.assertTrue(analysis["category_selection_derivation"]["disconfirming_evidence"])

            # 分析数据结构覆盖报告所需的 8 个板块
            required_sections = [
                "run_status_audit",
                "category_selection_derivation",
                "reference_asin_pool",
                "category_opportunity",
                "seller_sprite_validation",
                "search_market_validation",
                "keyword_pool",
                "voc_spec_translation",
                "route_judgment",
                "market_synthesis",
                "evidence_boundaries",
                "blocking_gaps",
                "human_review_focus",
                "next_stage_entry_conditions",
            ]
            for section in required_sections:
                self.assertIn(section, analysis, f"Report section missing: {section}")

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
                        "stage": "stage_5_route_matrix",
                        "initial_intent": "测试方向",
                        "known_inputs": {"stage1_quick_probe_summary": "已快探"},
                        "missing_inputs": ["评论插件导出数据"],
                        "next_actions": [
                            {
                                "stage": "stage_7_voc_gate",
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
            (run_dir / "research_package.json").write_text(json.dumps({}), encoding="utf-8")
            (run_dir / "mcp").mkdir()
            (run_dir / "mcp" / "route_sorftime_calibration.json").write_text("{}", encoding="utf-8")
            (run_dir / "review_asin_batch.json").write_text("{}", encoding="utf-8")

            audit = audit_run_status(run_dir)

        self.assertEqual(audit["current_stage"]["status"], "pending")
        self.assertTrue(any(item["item"] == "Stage 5 路线确认" for item in audit["blockers"]))
        self.assertIn("Stage 5 路线确认", [item["label"] for item in audit["next_actions"]])

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

    def test_validate_research_outputs_accepts_minimal_analysis_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workflow_dir = Path(tmp)
            analysis_dir = workflow_dir / "analysis"
            analysis_dir.mkdir()
            (analysis_dir / f"{workflow_dir.name}_分析报告.html").write_text(_minimal_analysis_report_html(), encoding="utf-8")
            write_xlsx(analysis_dir / f"{workflow_dir.name}_决策工具包.xlsx", _minimal_analysis_delivery_sheets())
            (analysis_dir / "delivery_qa_result.json").write_text(
                json.dumps({"status": "pass", "qa_rule_version": QA_RULE_VERSION}), encoding="utf-8"
            )

            result = validate_workflow_output(workflow_dir)

        self.assertTrue(result.ok, result.errors)
        self.assertFalse(result.warnings)

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


def _minimal_analysis_report_html() -> str:
    return (
        '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
        '<title>钢丝地板刷 · 市场机会报告</title>'
        '<style>body{margin:0;font-family:sans-serif}.page{max-width:1100px;margin:0 auto}'
        '.hero{background:#2e7d32;color:#fff;padding:24px}.verdict{font-size:24px;font-weight:bold}'
        '</style>'
        "</head><body><div class=\"page\">"
        "<section class=\"hero\"><div class=\"verdict\">建议进入小批量验证</div></section>"
        "<section><h2>类目全景</h2></section>"
        "<section><h2>核心竞品</h2></section>"
        "<section><h2>用户痛点</h2></section>"
        "<section><h2>价格带分布</h2></section>"
        "<section><h2>关键词与流量策略</h2></section>"
        "<section><h2>风险与下一步</h2><table class=\"go-nogo\"></table></section>"
        "</div></body></html>"
    )


def _minimal_analysis_delivery_sheets() -> list[tuple[str, list[list[object]]]]:
    return [
        ("路线计分卡", [["路线名", "综合判断"], ["主线", "建议进入"]]),
        ("竞品拆解", [["ASIN", "品牌"], ["B000000001", "测试"]]),
        ("关键词矩阵", [["关键词", "意图"], ["test keyword", "主攻意图"]]),
        ("样品检查表", [["痛点", "检测项"], ["测试痛点", "测试项"]]),
        ("冷启动预算", [["项目", "预估"], ["样品费", "5000"]]),
    ]


if __name__ == "__main__":
    unittest.main()
