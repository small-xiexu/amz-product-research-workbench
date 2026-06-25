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

    def test_skill_md_marks_legacy_commands(self):
        """SKILL.md 含'LEGACY FALLBACK'或'仅在 MCP 不可用时'。"""
        text = SKILL_MD.read_text(encoding="utf-8")
        self.assertIn("LEGACY FALLBACK", text)

    def test_skill_md_stage2_describes_mcp(self):
        """SKILL.md Stage 2 标题改为 MCP 快验描述。"""
        text = SKILL_MD.read_text(encoding="utf-8")
        self.assertIn("双 MCP 市场快验", text)

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
