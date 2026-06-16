from __future__ import annotations

import json
import shutil
import subprocess
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
    validate_workflow_state,
)
from packages.research_core.workflows import WorkflowConfig, run_research_workflow
from packages.research_core.workflows.product_research_workflow import build_workflow_trace
from packages.research_core.workflows import DecisionRecord, advance_stage, create_initial_state
from packages.research_core.pipeline.apply_ip_compliance_review import apply_ip_compliance_review, next_step_for
from packages.research_core.pipeline.apply_profit_review import apply_profit_review
from packages.research_core.pipeline.build_candidate_pool_from_import_manifest import build_candidate_pool
from packages.research_core.pipeline.build_research_package_from_candidate import build_research_package
from packages.research_core.pipeline.validate_research_outputs import validate_workflow_output
from packages.report_renderer.render_report import (
    FORMAL_REPORT_SECTION_TITLES,
    render_data_workbook,
    render_markdown,
    render_report_html,
)


ROOT = Path(__file__).resolve().parents[1]


class RegressionTests(unittest.TestCase):
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

    def test_ip_compliance_next_step_is_actionable(self) -> None:
        self.assertIn("补齐知产/合规初筛字段", next_step_for("待复核", ["产品用途"], []))
        self.assertIn("先处理待复核项", next_step_for("待复核", [], ["知产：外观专利"]))
        self.assertIn("专业复核", next_step_for("高", [], []))
        self.assertIn("继续结合利润复核", next_step_for("低", [], []))

    def test_apply_ip_compliance_review_updates_next_step(self) -> None:
        package = _load_json("examples/minimal_research_package.json")
        review = {
            "product_flags": {
                "product_usage": "户外照明",
                "user_group": "成人",
                "material_coating": "塑料",
                "package_instruction_plan": "说明书",
            },
            "ip_rows": [
                {"risk_type": "商标", "result": "低", "evidence_note": "未发现明显冲突。"},
            ],
            "compliance_rows": [
                {"product_attribute": "带电/电子产品", "result": "中", "evidence_note": "需确认认证资料。"},
            ],
        }

        updated = apply_ip_compliance_review(package, review)
        next_step = updated["ip_compliance_review"]["next_step"]
        self.assertIn("打样前", next_step)
        self.assertEqual(updated["status_card"]["next_step"], next_step)

    def test_profit_review_marks_missing_required_costs(self) -> None:
        package = _load_json("examples/minimal_research_package.json")
        updated = apply_profit_review(
            package,
            {
                "sale_price": 19.99,
                "purchase_cost_cny": 30,
                "exchange_rate": 7.2,
                "fba_fee": 4.5,
            },
        )

        missing = updated["profit_review"]["missing_fields"]
        self.assertIn("头程费用", missing)
        self.assertIn("入库配置费", missing)
        self.assertEqual(updated["profit_reference"]["status"], "待补")

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
            (final_report / "summary.md").write_text("# 摘要\n", encoding="utf-8")
            (final_report / "dashboard.html").write_text("<!doctype html><html></html>", encoding="utf-8")
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
            (final_report / "summary.md").write_text("# 摘要\n", encoding="utf-8")
            (final_report / "dashboard.html").write_text("<!doctype html><html></html>", encoding="utf-8")
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
            (final_report / "summary.md").write_text("# 摘要\n", encoding="utf-8")

            result = validate_workflow_output(workflow_dir)

        self.assertFalse(result.ok)
        self.assertTrue(any("report.html" in item for item in result.errors))
        self.assertTrue(any("dashboard.html" in item for item in result.errors))
        self.assertTrue(any("data.xlsx" in item for item in result.errors))

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
        self.assertIn("网页报告", report)
        self.assertIn("dashboard.html", report)
        self.assertIn("data.xlsx", report)
        self.assertIn("Executive Summary / 当前结论", report)

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

    def test_sorftime_category_report_and_supply_chain_flow_to_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            candidate_pool = build_candidate_pool(
                _minimal_import_manifest(Path(tmp)),
                sorftime_verification=_sample_sorftime_verification(),
            )
        candidate = candidate_pool["candidates"][0]
        research_package = build_research_package(candidate_pool, candidate["candidate_id"])
        report = render_markdown(research_package)

        self.assertEqual(candidate["demand_evidence"]["sorftime_category_report"]["product_count"], 2)
        self.assertEqual(candidate["preliminary_profit_space"]["supply_chain_signal"]["supplier_count"], 2)
        self.assertIn("Sorftime category_report 快照", report)
        self.assertIn("1688 中国站人民币粗采购价信号", report)
        self.assertEqual(research_package["profit_reference"]["supply_chain_signal"]["purchase_price_cny_min"], 12.0)

    def test_ali1688_raw_result_flows_to_supply_chain_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            candidate_pool = build_candidate_pool(
                _minimal_import_manifest(Path(tmp)),
                sorftime_verification=_sample_ali1688_raw_verification(),
            )
        candidate = candidate_pool["candidates"][0]
        signal = candidate["preliminary_profit_space"]["supply_chain_signal"]
        research_package = build_research_package(candidate_pool, candidate["candidate_id"])
        report = render_markdown(research_package)

        self.assertEqual(signal["supplier_count"], 2)
        self.assertEqual(signal["relevant_supplier_count"], 2.0)
        self.assertEqual(signal["quote_currency"], "RMB")
        self.assertEqual(signal["source_site"], "1688中国站")
        self.assertEqual(signal["rejected_sample_count"], 0)
        self.assertEqual(signal["purchase_price_cny_min"], 8.5)
        self.assertEqual(signal["purchase_price_cny_max"], 37.0)
        self.assertEqual(signal["sample_products"][0]["supplier"], "义乌市隋媲电子商务商行")
        self.assertIn("1688 中国站人民币粗采购价信号", report)
        self.assertIn("免手持狗绳 腰带牵引绳", report)

    def test_ali1688_filters_non_china_1688_or_non_rmb_samples(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            candidate_pool = build_candidate_pool(
                _minimal_import_manifest(Path(tmp)),
                sorftime_verification=_sample_mixed_ali1688_verification(),
            )
        candidate = candidate_pool["candidates"][0]
        signal = candidate["preliminary_profit_space"]["supply_chain_signal"]

        self.assertEqual(signal["raw_supplier_count"], 4)
        self.assertEqual(signal["supplier_count"], 1)
        self.assertEqual(signal["rejected_sample_count"], 3)
        self.assertEqual(signal["purchase_price_cny_min"], 14.0)
        self.assertEqual(signal["purchase_price_cny_max"], 14.0)
        self.assertIn("非1688中国站链接", signal["rejection_reasons"])
        self.assertIn("币种不是RMB/CNY", signal["rejection_reasons"])
        self.assertIn("价格字段疑似非人民币", signal["rejection_reasons"])
        self.assertEqual(len(signal["sample_products"]), 1)
        self.assertTrue(signal["sample_products"][0]["url"].startswith("https://detail.1688.com/"))

    def test_ali1688_all_invalid_samples_do_not_create_price_range(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            candidate_pool = build_candidate_pool(
                _minimal_import_manifest(Path(tmp)),
                sorftime_verification=_sample_invalid_ali1688_verification(),
            )
        candidate = candidate_pool["candidates"][0]
        signal = candidate["preliminary_profit_space"]["supply_chain_signal"]

        self.assertEqual(signal["supplier_count"], 0)
        self.assertEqual(signal["rejected_sample_count"], 2)
        self.assertNotIn("purchase_price_cny_min", signal)
        self.assertIn("禁止用Alibaba国际站USD报价替代", signal["note"])

    def test_interactive_workflow_initial_broad_discovery_requires_operator_boundary(self) -> None:
        state = create_initial_state(
            workflow_id="wf-001",
            mode="broad_discovery",
            initial_intent="美国站家居清洁小工具",
            site="US",
        )

        self.assertEqual(state.stage, "intent_intake")
        self.assertTrue(state.decision_required)
        self.assertIn("业务边界", state.operator_question)
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
        self.assertIn("产品边界", state.operator_question)

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
        "profit_review": {"applied": False, "status": "待填写模板"},
        "ip_compliance_review": {"applied": False, "status": "待填写模板"},
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
        "# 选品流程运行摘要\n\n- 利润复核：待填写模板\n- 知产/合规初筛：待填写模板\n",
        encoding="utf-8",
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
        "supply_chain_signal": {
            "searchName": "刮窗器",
            "source_url": "https://www.1688.com/",
            "quote_currency": "RMB",
            "exchange_rate": 7.2,
            "products": [
                {"title": "刮窗器套装", "price": "12-18", "quote_currency": "RMB", "supplier": "供应商A", "url": "https://detail.1688.com/offer/10001.html"},
                {"title": "伸缩刮窗器", "price": "16-22", "quote_currency": "RMB", "supplier": "供应商B", "url": "https://detail.1688.com/offer/10002.html"},
            ],
        },
    }


def _sample_ali1688_raw_verification() -> dict:
    return {
        "verified_at": "2026-06-15",
        "supply_chain_signal": {
            "search_name": "免手持狗绳 腰带牵引绳",
            "relevant_supplier_count": 2,
            "purchase_price_usd_avg": 2.8,
        },
        "ali1688_similar_product": [
            {
                "Title": "现货解放双手反光斜跨肩挎牵引绳多功能跑步牵引绳宠物牵引带防丢",
                "Price": "15.6",
                "Currency": "RMB",
                "WholesalePriceRange": [{"Price": "8.50", "PurchaseQuantity": "≥1个"}],
                "StoreName": "义乌市隋媲电子商务商行",
                "Url": "https://detail.1688.com/offer/651810362213.html",
            },
            {
                "Title": "亚马逊狗绳子狗链防爆冲中型大型犬弹力牵引绳反光运动遛狗腰包",
                "Price": "37.0",
                "Currency": "RMB",
                "WholesalePriceRange": [
                    {"Price": "37.00", "PurchaseQuantity": "2~49个"},
                    {"Price": "36.50", "PurchaseQuantity": "50~499个"},
                    {"Price": "36.00", "PurchaseQuantity": "≥500个"},
                ],
                "StoreName": "保定君乐途箱包制造有限公司",
                "Url": "https://detail.1688.com/offer/671808165514.html",
            },
        ],
    }


def _sample_mixed_ali1688_verification() -> dict:
    return {
        "verified_at": "2026-06-16",
        "supply_chain_signal": {
            "search_name": "免手持狗绳 腰带牵引绳",
            "purchase_price_usd_avg": 1.9,
        },
        "ali1688_similar_product": [
            {
                "Title": "有效1688人民币货源",
                "Price": "14.00",
                "Currency": "RMB",
                "StoreName": "义乌供应商",
                "Url": "https://detail.1688.com/offer/700000000001.html",
            },
            {
                "Title": "Alibaba international USD source",
                "Price": "$2.30",
                "Currency": "USD",
                "StoreName": "Alibaba Supplier",
                "Url": "https://www.alibaba.com/product-detail/dog-leash.html",
            },
            {
                "Title": "非1688站点人民币报价",
                "Price": "13.00",
                "Currency": "RMB",
                "StoreName": "外部站点",
                "Url": "https://supplier.example.com/item/1",
            },
            {
                "Title": "1688链接但价格带美元符号",
                "Price": "$1.99",
                "StoreName": "币种异常供应商",
                "Url": "https://detail.1688.com/offer/700000000002.html",
            },
        ],
    }


def _sample_invalid_ali1688_verification() -> dict:
    return {
        "verified_at": "2026-06-16",
        "supply_chain_signal": {"search_name": "免手持狗绳 腰带牵引绳"},
        "ali1688_similar_product": [
            {
                "Title": "Alibaba国际站样本",
                "Price": "$2.30",
                "Currency": "USD",
                "Url": "https://www.alibaba.com/product-detail/dog-leash.html",
            },
            {
                "Title": "外部站点样本",
                "Price": "12.00",
                "Currency": "RMB",
                "Url": "https://example.com/dog-leash",
            },
        ],
    }


def _minimal_delivery_sheets(top100_rows: int, interactive: bool = False) -> list[tuple[str, list[list[object]]]]:
    rows: list[list[object]] = [["ASIN", "标题", "价格", "月销量"]]
    for index in range(top100_rows):
        rows.append([f"B{index:09d}", f"测试商品 {index}", 19.99, 100 + index])
    return [
        ("数据来源说明", [["来源", "说明"], ["seller-sprite-export", "测试"]]),
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
            ],
        ),
        ("竞品池", [["ASIN", "标题"], ["B000000001", "测试"]]),
        (
            "Go_No-Go评分卡",
            [
                ["维度", "得分（满分10）", "权重", "加权得分", "依据"],
                ["市场规模", 6, "16%", 0.96, "测试"],
                ["竞争格局", 6, "16%", 0.96, "测试"],
                ["需求清晰度", 6, "14%", 0.84, "测试"],
                ["新品友好度", 6, "12%", 0.72, "测试"],
                ["利润可行性", 5, "16%", 0.8, "待补"],
                ["知产/合规/退货风险", 5, "14%", 0.7, "待补"],
                ["数据完整度", 8, "12%", 0.96, "测试"],
                [],
                ["加权总分", 5.94, "", "", ""],
                ["决策结论", "WAIT", "", "", ""],
                ["决策限制", "利润复核未回填；知产/合规初筛未回填", "", "", ""],
            ],
        ),
        ("决策检查", [["字段", "值"], ["状态", "观察"]]),
        ("风险矩阵", [["维度", "等级"], ["数据", "低"]]),
        ("状态卡", [["字段", "值"], ["状态", "观察"]]),
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
            ],
        ),
        ("利润参考结果", [["字段", "值"], ["状态", "待填写模板"]]),
        ("利润成本拆分", [["字段", "值"], ["状态", "未计算"]]),
        ("知产合规复核", [["字段", "值"], ["状态", "待填写模板"]]),
        ("知产初筛", [["字段", "值"], ["状态", "待复核"]]),
        ("合规认证预判", [["字段", "值"], ["状态", "待复核"]]),
    ]


def _minimal_formal_report_markdown(interactive: bool = False) -> str:
    lines = ["# 测试调研报告", ""]
    for title in FORMAL_REPORT_SECTION_TITLES:
        lines.extend([f"## {title}", "", "- 测试内容", ""])
    lines.append("- 数据来源说明 / 状态卡 / 下一步 / 待补项")
    if interactive:
        lines.extend(["", "### 交互式流程状态", "- workflow_state 测试"])
        lines.extend(["", "### 交互式下一步动作", "- 下一步测试"])
        lines.extend(["", "### 关键决策记录", "- 决策测试"])
    return "\n".join(lines) + "\n"


def _minimal_formal_report_html() -> str:
    return (
        '<!doctype html><html lang="zh-CN"><head><title>网页报告</title></head>'
        "<body><h2>Executive Summary / 当前结论</h2></body></html>"
    )


if __name__ == "__main__":
    unittest.main()
