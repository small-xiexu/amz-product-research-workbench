"""P9: Legacy downgrade — verify legacy scripts/docs still work but are marked correctly."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL_README = ROOT / "skills" / "amazon-product-research" / "README.md"
SKILL_MD = ROOT / "skills" / "amazon-product-research" / "SKILL.md"
LEGACY_DOC = ROOT / "docs" / "卖家精灵导出指令完整性规范.md"


class LegacyScriptImportTests(unittest.TestCase):
    """Task 3: legacy scripts still importable."""

    def test_inspect_manual_exports_importable(self):
        from packages.research_core.pipeline.inspect_manual_exports import main
        self.assertTrue(callable(main))

    def test_build_candidate_pool_importable(self):
        from packages.research_core.pipeline.build_candidate_pool_from_import_manifest import (
            main,
        )
        self.assertTrue(callable(main))

    def test_legacy_cli_scripts_exist(self):
        self.assertTrue((ROOT / "scripts" / "inspect_manual_exports.py").exists())
        self.assertTrue(
            (ROOT / "scripts" / "build_candidate_pool_from_import_manifest.py").exists()
        )


class LegacyCLITests(unittest.TestCase):
    """Task 3: legacy CLI still runs --help."""

    def test_inspect_manual_exports_help(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "inspect_manual_exports.py"), "--help"],
            capture_output=True, text=True, timeout=15,
            env={**__import__("os").environ, "PYTHONPATH": str(ROOT)},
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("usage:", result.stdout.lower())

    def test_build_candidate_pool_help(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "build_candidate_pool_from_import_manifest.py"), "--help"],
            capture_output=True, text=True, timeout=15,
            env={**__import__("os").environ, "PYTHONPATH": str(ROOT)},
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("usage:", result.stdout.lower())


class LegacyContractTests(unittest.TestCase):
    """Task 5: validate_import_manifest still works."""

    def test_valid_manifest_passes(self):
        from packages.research_core.contracts import validate_import_manifest

        manifest = {
            "metadata": {"site": "US", "task_name": "test"},
            "files": [],
            "data_quality": {"available_source_types": ["seller_sprite"], "missing_source_types": []},
        }
        validate_import_manifest(manifest)  # 不抛异常 = pass

    def test_invalid_manifest_raises(self):
        from packages.research_core.contracts import validate_import_manifest

        with self.assertRaises(Exception):
            validate_import_manifest({"metadata": {}, "files": [], "data_quality": {}})


class LegacyDocMarkerTests(unittest.TestCase):
    """Tasks 1-2, 4: verify docs mark legacy fallback correctly."""

    def test_readme_has_no_manual_export_as_primary(self):
        """主流程图不含'卖家精灵导出清单''导出文件盘点'。"""
        text = SKILL_README.read_text(encoding="utf-8")
        # 主流程图应在 ```text 代码块内，不含旧入口
        main_flow_start = text.find("当前主线（MCP 主路径）")
        self.assertGreater(main_flow_start, 0)
        main_flow_end = text.find("```", text.find("```", main_flow_start) + 3)
        main_flow = text[main_flow_start:main_flow_end]
        self.assertNotIn("卖家精灵导出清单", main_flow)
        self.assertNotIn("导出文件盘点", main_flow)

    def test_readme_has_mcp_main_path_entries(self):
        """README 常用入口表含 MCP 主路径命令。"""
        text = SKILL_README.read_text(encoding="utf-8")
        self.assertIn("MCP 候选池", text)
        self.assertIn("build_mcp_candidate_pool.py", text)

    def test_readme_has_legacy_fallback_section(self):
        """README 含'Legacy 回退'章节。"""
        text = SKILL_README.read_text(encoding="utf-8")
        self.assertIn("Legacy 回退", text)
        self.assertIn("MCP 不可用时", text)

    def test_skill_md_has_legacy_appendix(self):
        """SKILL.md 含 Legacy 回退附录。"""
        text = SKILL_MD.read_text(encoding="utf-8")
        self.assertIn("Legacy 回退", text)

    def test_skill_md_stage2_describes_quick_check(self):
        """SKILL.md Stage 2 描述双 Agent 并行快验。"""
        text = SKILL_MD.read_text(encoding="utf-8")
        self.assertIn("双 Agent 市场快验", text)

    def test_legacy_doc_has_fallback_marker(self):
        """卖家精灵导出指令完整性规范.md 含'LEGACY FALLBACK'标记。"""
        text = LEGACY_DOC.read_text(encoding="utf-8")
        self.assertIn("LEGACY FALLBACK", text)

    def test_legacy_scripts_have_docstring_marker(self):
        """Legacy 脚本 docstring 第一行含 LEGACY FALLBACK。"""
        import packages.research_core.pipeline.inspect_manual_exports as m1
        import packages.research_core.pipeline.build_candidate_pool_from_import_manifest as m2

        self.assertIn("LEGACY FALLBACK", m1.__doc__ or "")
        self.assertIn("LEGACY FALLBACK", m2.__doc__ or "")


class RegressionSmokeTests(unittest.TestCase):
    """轻量回归烟雾测试：确保关键模块仍可导入和运行。"""

    def test_legacy_pipeline_modules_importable(self):
        """已验证的 legacy 模块均可正常导入。"""
        import packages.research_core.pipeline.inspect_manual_exports
        import packages.research_core.pipeline.build_candidate_pool_from_import_manifest
        import packages.research_core.contracts.validators
        self.assertTrue(True)

    def test_contracts_no_import_error(self):
        """contracts 模块可正常导入。"""
        from packages.research_core.contracts import (
            validate_import_manifest,
            validate_candidate_pool,
        )
        self.assertTrue(callable(validate_import_manifest))
        self.assertTrue(callable(validate_candidate_pool))


class NewScriptImportTests(unittest.TestCase):
    """验证 P0 修复脚本和 P2 编排脚本可正常导入。"""

    def test_fill_quick_packet_contract_importable(self):
        """fill_quick_packet_contract 模块可正常导入。"""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "fill_quick_packet_contract",
            Path(__file__).resolve().parents[1] / "scripts" / "fill_quick_packet_contract.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.assertTrue(callable(mod.fill_contract))

    def test_fill_contract_all_17_fields(self):
        """fill_contract 补齐全部 17 个必填字段。"""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "fill_quick_packet_contract",
            Path(__file__).resolve().parents[1] / "scripts" / "fill_quick_packet_contract.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        result = mod.fill_contract({"support_level": "strong"}, "sellersprite")
        required = [
            "schema_version", "packet_id", "stage", "depth", "source_type",
            "support_level", "blocking_gaps", "mixed_pool_level",
            "demand_signal_level", "price_band_health", "category_boundary_clarity",
            "facts", "metric_basis", "evidence_refs", "confidence",
            "data_gaps", "execution_provenance",
        ]
        for field in required:
            with self.subTest(field=field):
                self.assertIn(field, result, f"Missing: {field}")

    def test_fill_contract_preserves_agent_content(self):
        """fill_contract 保留 Agent 原始内容。"""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "fill_quick_packet_contract",
            Path(__file__).resolve().parents[1] / "scripts" / "fill_quick_packet_contract.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        agent_output = {
            "support_level": "moderate",
            "market_overview": "类目月销约12万件",
            "custom_field": "should be preserved",
        }
        result = mod.fill_contract(agent_output, "sellersprite")
        self.assertEqual(result["market_overview"], "类目月销约12万件")
        self.assertEqual(result["custom_field"], "should be preserved")

    def test_init_workflow_state_importable(self):
        """init_workflow_state 模块可正常导入。"""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "init_workflow_state",
            Path(__file__).resolve().parents[1] / "scripts" / "init_workflow_state.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.assertTrue(callable(mod.init_workflow_state))

    def test_run_pipeline_importable(self):
        """run_pipeline 模块可正常导入。"""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "run_pipeline",
            Path(__file__).resolve().parents[1] / "scripts" / "run_pipeline.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.assertTrue(callable(mod.main))


class QuickGateCrossValidationTests(unittest.TestCase):
    """验证 Quick Gate 新增的交叉校验功能。"""

    def test_cross_validation_field_in_gate(self):
        """build_quick_market_gate 输出含 cross_validation 字段。"""
        from packages.research_core.pipeline.quick_market_check import build_quick_market_gate
        sellersprite = {
            "schema_version": "evidence-packet-v1",
            "packet_id": "sellersprite_quick_evidence_packet",
            "stage": "market_quick_check",
            "depth": "quick",
            "source_type": "sellersprite_mcp",
            "support_level": "strong",
            "blocking_gaps": [],
            "mixed_pool_level": "none",
            "demand_signal_level": "strong",
            "price_band_health": "healthy",
            "category_boundary_clarity": "clear",
            "facts": [],
            "metric_basis": {},
            "evidence_refs": [],
            "confidence": "medium",
            "data_gaps": [],
            "execution_provenance": {"execution_mode": "real_subagent_spawn"},
        }
        sorftime = dict(sellersprite)
        sorftime["packet_id"] = "sorftime_quick_evidence_packet"
        sorftime["source_type"] = "sorftime_mcp"
        gate = build_quick_market_gate(sellersprite, sorftime)
        self.assertIn("cross_validation", gate)
        self.assertIn("discrepancies", gate["cross_validation"])
        self.assertIn("has_discrepancies", gate["cross_validation"])

    def test_support_divergence_detected(self):
        """support_level 分歧被检出。"""
        from packages.research_core.pipeline.quick_market_check import build_quick_market_gate
        base = {
            "schema_version": "evidence-packet-v1",
            "packet_id": "sellersprite_quick_evidence_packet",
            "stage": "market_quick_check",
            "depth": "quick",
            "source_type": "sellersprite_mcp",
            "support_level": "strong",
            "blocking_gaps": [],
            "mixed_pool_level": "none",
            "demand_signal_level": "strong",
            "price_band_health": "healthy",
            "category_boundary_clarity": "clear",
            "facts": [],
            "metric_basis": {},
            "evidence_refs": [],
            "confidence": "medium",
            "data_gaps": [],
            "execution_provenance": {"execution_mode": "real_subagent_spawn"},
        }
        sf = dict(base)
        sf["packet_id"] = "sorftime_quick_evidence_packet"
        sf["source_type"] = "sorftime_mcp"
        sf["support_level"] = "weak"
        gate = build_quick_market_gate(base, sf)
        self.assertTrue(gate["cross_validation"]["has_discrepancies"])


class DeepSnapshotTests(unittest.TestCase):
    """验证 build_deep_snapshot 脚本。"""

    def test_build_deep_snapshot_importable(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "build_deep_snapshot",
            Path(__file__).resolve().parents[1] / "scripts" / "build_deep_snapshot.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.assertTrue(callable(mod.build_deep_snapshot))

    def test_all_15_fields_filled(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "build_deep_snapshot",
            Path(__file__).resolve().parents[1] / "scripts" / "build_deep_snapshot.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        result = mod.build_deep_snapshot(
            {"tool_calls": [{"tool_name": "market_research", "params": {"keyword": "dog leash"}}]},
            "sellersprite",
            run_id="test-run",
        )
        required = [
            "schema_version", "snapshot_id", "run_id", "source_name",
            "source_doc_refs", "route_refs", "selected_routes", "tool_calls",
            "tool_results", "errors", "data_gaps", "created_at",
            "retry_policy", "force_refresh", "input_lineage",
        ]
        for field in required:
            with self.subTest(field=field):
                self.assertIn(field, result, f"Missing: {field}")
        self.assertEqual(result["schema_version"], "p4-deep-contract-v1")
        self.assertEqual(result["source_name"], "sellersprite")
        self.assertEqual(len(result["tool_calls"]), 1)


class DeepEvidencePacketTests(unittest.TestCase):
    """验证 build_deep_evidence_packet 脚本。"""

    def test_build_deep_evidence_packet_importable(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "build_deep_evidence_packet",
            Path(__file__).resolve().parents[1] / "scripts" / "build_deep_evidence_packet.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.assertTrue(callable(mod.build_evidence_packet))

    def test_market_structure_packet_fields(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "build_deep_evidence_packet",
            Path(__file__).resolve().parents[1] / "scripts" / "build_deep_evidence_packet.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        agent_output = {
            "facts": {
                "reference_asin_pool": [
                    {"asin": "B0EXAMPLE1", "route_ref": "dog_leash", "price": 15.99},
                    {"asin": "B0EXAMPLE2", "route_ref": "dog_leash", "price": 22.50},
                ],
            },
        }
        result = mod.build_evidence_packet(agent_output, "sellersprite", run_id="test")
        self.assertEqual(result["packet_id"], "market_structure_evidence_packet")
        self.assertEqual(result["primary_source"], "sellersprite")
        self.assertEqual(len(result["evidence_items"]), 2)
        self.assertIn("metric_basis", result)

    def test_search_demand_packet_fields(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "build_deep_evidence_packet",
            Path(__file__).resolve().parents[1] / "scripts" / "build_deep_evidence_packet.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        result = mod.build_evidence_packet({}, "sorftime", run_id="test")
        self.assertEqual(result["packet_id"], "search_demand_evidence_packet")
        self.assertEqual(result["primary_source"], "sorftime")
        self.assertIn("metric_basis", result)
        self.assertIn("sorftime_deep", result["metric_basis"])

    def test_fallback_wraps_entire_facts(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "build_deep_evidence_packet",
            Path(__file__).resolve().parents[1] / "scripts" / "build_deep_evidence_packet.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        result = mod.build_evidence_packet(
            {"facts": {"custom_field": "no standard structure"}}, "sellersprite"
        )
        self.assertEqual(len(result["evidence_items"]), 1)
        self.assertEqual(result["evidence_items"][0]["item_type"], "competitor_structure")


class FillContractNestedFixTests(unittest.TestCase):
    """验证 fill_contract 的嵌套字段修复。"""

    def test_metric_basis_sub_fields_overwritten(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "fill_quick_packet_contract",
            Path(__file__).resolve().parents[1] / "scripts" / "fill_quick_packet_contract.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        # Agent provides empty or invalid metric_basis sub-fields
        agent_output = {
            "support_level": "strong",
            "metric_basis": {"marketplace": "", "currency": "", "data_window": ""},
        }
        result = mod.fill_contract(agent_output, "sellersprite")
        mb = result["metric_basis"]
        self.assertEqual(mb["marketplace"], "US")
        self.assertEqual(mb["currency"], "USD")
        self.assertEqual(mb["data_window"], "30d")
        self.assertEqual(mb["sample_scope"], "Top100")
        self.assertIn("collected_at", mb)

    def test_price_band_health_healthy_mapped_to_strong(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "fill_quick_packet_contract",
            Path(__file__).resolve().parents[1] / "scripts" / "fill_quick_packet_contract.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        # Agent writes "healthy" → mapped to "strong" (canonical per quick_market_check.py)
        result = mod.fill_contract(
            {"support_level": "strong", "price_band_health": "healthy"}, "sellersprite"
        )
        self.assertEqual(result["price_band_health"], "strong")

    def test_price_band_health_watch_mapped_to_moderate(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "fill_quick_packet_contract",
            Path(__file__).resolve().parents[1] / "scripts" / "fill_quick_packet_contract.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        result = mod.fill_contract(
            {"support_level": "strong", "price_band_health": "watch"}, "sellersprite"
        )
        self.assertEqual(result["price_band_health"], "moderate")

    def test_boundary_enum_partial_mapped(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "fill_quick_packet_contract",
            Path(__file__).resolve().parents[1] / "scripts" / "fill_quick_packet_contract.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        # "partial" is mapped to "moderate" by the boundary map
        result = mod.fill_contract(
            {"support_level": "strong", "category_boundary_clarity": "partial"}, "sellersprite"
        )
        self.assertEqual(result["category_boundary_clarity"], "moderate")


class RouteMatrixForceConfirmTests(unittest.TestCase):
    """验证 --force-confirm 绕过 needs_user_review 检查。"""

    def test_force_confirm_selects_with_support(self):
        from packages.research_core.pipeline.build_route_matrix_confirmation import _selection_status
        candidate = {
            "readiness_status": "needs_user_review",
            "support_level": "strong",
        }
        # Without force_confirm → rejected
        self.assertEqual(_selection_status(candidate, "warning"), "rejected")
        # With force_confirm → selected
        self.assertEqual(_selection_status(candidate, "warning", force_confirm=True), "selected")

    def test_force_confirm_still_rejects_blocker(self):
        from packages.research_core.pipeline.build_route_matrix_confirmation import _selection_status
        candidate = {
            "readiness_status": "needs_user_review",
            "support_level": "strong",
        }
        self.assertEqual(_selection_status(candidate, "blocker", force_confirm=True), "rejected")

    def test_force_confirm_still_rejects_excluded(self):
        from packages.research_core.pipeline.build_route_matrix_confirmation import _selection_status
        candidate = {
            "readiness_status": "needs_user_review",
            "support_level": "strong",
            "status": "先放弃",
        }
        self.assertEqual(_selection_status(candidate, "warning", force_confirm=True), "rejected")


class ExtractEvidenceAsinsFallbackTests(unittest.TestCase):
    """验证 _extract_evidence_asins 的 free-form facts 回退。"""

    def test_extracts_asins_from_freeform_facts(self):
        from packages.research_core.pipeline.build_review_asin_batch import _extract_evidence_asins

        # Agent free-form packet: no evidence_items, only facts.reference_asin_pool
        packet = {
            "facts": {
                "reference_asin_pool": [
                    {"asin": "B0AAA11111", "price": 15.99, "monthly_sales": 500},
                    {"asin": "B0BBB22222", "price": 22.50, "monthly_sales": 1200},
                ],
            },
        }
        result = _extract_evidence_asins(packet)
        self.assertIn("B0AAA11111", result)
        self.assertIn("B0BBB22222", result)
        self.assertEqual(result["B0AAA11111"]["price"], 15.99)

    def test_still_extracts_from_evidence_items_first(self):
        from packages.research_core.pipeline.build_review_asin_batch import _extract_evidence_asins

        packet = {
            "evidence_items": [
                {
                    "item_type": "competitor_structure",
                    "facts": {"raw_value": [{"asin": "B0CCC33333", "price": 9.99}]},
                },
            ],
            "facts": {"reference_asin_pool": [{"asin": "B0DDD44444"}]},
        }
        result = _extract_evidence_asins(packet)
        self.assertIn("B0CCC33333", result)
