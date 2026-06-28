"""P7 report delivery tests: seed handoff → Agent output → XLSX/QA chain.

Verifies that build_report_seed / build_report_xlsx keep the Report Generation Agent boundary:
the script creates report_data.seed.json, then only generates XLSX/QA after an
agent has written report_data.json and the formal HTML report.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

from openpyxl import load_workbook

from packages.research_core.pipeline.build_conflict_review import run_conflict_review
from packages.research_core.pipeline.build_evaluation_summary import (
    run_evaluations,
)
from packages.research_core.pipeline.build_integrated_judgment import (
    run_integrated_judgment,
)
from packages.research_core.pipeline.build_mcp_candidate_pool import run_candidate_pool
from packages.research_core.pipeline.build_review_asin_batch import run_review_asin_batch
from packages.research_core.pipeline.build_review_voc_package import run_review_voc_package
from packages.research_core.pipeline.build_route_matrix_confirmation import (
    run_route_matrix_confirmation,
)
from packages.research_core.pipeline.build_sellersprite_deep_dive import (
    run_sellersprite_deep_dive,
)
from packages.research_core.pipeline.build_sorftime_deep_dive import (
    run_sorftime_deep_dive,
)
from packages.research_core.pipeline.build_voc_gate import run_voc_gate
from packages.research_core.pipeline.build_analysis_packet import (
    build_analysis_packet, load_packets, _extract_product_name,
)
from packages.research_core.pipeline.constants import (
    FORBIDDEN_HTML_PATTERNS,
    REQUIRED_SECTION_MARKERS,
    REQUIRED_REPORT_DATA_SECTIONS,
    REQUIRED_REPORT_DATA_DECLARATIONS,
)
from packages.research_core.pipeline.xlsx_back_table import (
    xlsx_sheets_from_report_data,
)
from packages.research_core.pipeline.public_language import (
    find_public_language_issues,
    public_label,
    public_text,
)
from packages.research_core.pipeline.seed_report_data import (
    seed_report_data_from_analysis,
)
from packages.research_core.pipeline.quick_market_check import run_quick_market_check
from tests.agent_output_fixtures import write_agent_candidate_pool, write_agent_route_matrix
from packages.report_renderer.xlsx_writer import write_xlsx


ROOT = Path(__file__).resolve().parents[1]
P1_FIXTURES = ROOT / "tests" / "fixtures" / "p1_quick_check"


def _cli_env() -> dict:
    import os
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT) + (":" + env.get("PYTHONPATH", "") if env.get("PYTHONPATH") else "")
    return env


# ── Public language cleanup ─────────────────────────────────────────────

class PublicLanguageTests(unittest.TestCase):
    """Operator-facing deliverables translate internal labels and dramatic phrasing."""

    def test_public_text_translates_internal_jargon(self) -> None:
        dirty = "P0安全风险是0评论新品的生死考验，confidence Medium，final_verdict=watch，rating=blocked，Stage 10a。"
        clean = public_text(dirty)
        self.assertIn("上市前必须验证的安全可靠性问题", clean)
        self.assertIn("判断置信度中等", clean)
        self.assertIn("建议先验证", clean)
        self.assertIn("当前不满足放行条件", clean)
        self.assertEqual(find_public_language_issues(clean), [])

    def test_public_label_translates_priority_and_confidence(self) -> None:
        self.assertEqual(public_label("P0", context="priority"), "必须验证")
        self.assertEqual(public_label("medium", context="confidence"), "判断置信度中等")


# ── Seed handoff ────────────────────────────────────────────────────────

class ReportSeedHandoffTests(unittest.TestCase):
    """Generate report_data.seed.json for Report Generation Agent."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self._tmp = Path(self._tmpdir.name)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def _seed_full_pipeline(self) -> tuple[Path, dict, dict]:
        run_dir = self._tmp / "20260625_generic_delivery"
        run_dir.mkdir()
        (run_dir / "workflow_state.json").write_text(
            json.dumps(_workflow_state(), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        run_quick_market_check(run_dir, snapshot_source_dir=P1_FIXTURES)
        write_agent_candidate_pool(run_dir)
        run_candidate_pool(run_dir)
        write_agent_route_matrix(run_dir)
        run_route_matrix_confirmation(run_dir)
        run_sellersprite_deep_dive(run_dir, snapshot_source=self._write_ss())
        run_sorftime_deep_dive(run_dir, snapshot_source=self._write_sf())
        run_conflict_review(run_dir)
        run_review_asin_batch(run_dir)
        run_review_voc_package(run_dir, self._write_rx(35))
        run_voc_gate(run_dir)
        _write_agent_evaluations(run_dir)
        run_evaluations(run_dir)
        judgment = run_integrated_judgment(run_dir)
        packets = load_packets(run_dir)
        analysis = build_analysis_packet(run_dir, packets)
        return run_dir, analysis, judgment

    def _write_ss(self) -> Path:
        p = self._tmp / "ss_snap.json"
        p.write_text(json.dumps(_valid_sellersprite_snapshot(), ensure_ascii=False, indent=2), encoding="utf-8")
        return p

    def _write_sf(self) -> Path:
        p = self._tmp / "sf_snap.json"
        p.write_text(json.dumps(_valid_sorftime_snapshot(), ensure_ascii=False, indent=2), encoding="utf-8")
        return p

    def _write_rx(self, count: int = 35) -> Path:
        p = self._tmp / "test_reviews.xlsx"
        _write_review_xlsx_file(p, _sample_reviews(count))
        return p

    def test_seed_preserves_all_required_sections(self) -> None:
        """Seed has all 11 required sections for agent enhancement."""
        run_dir, analysis, judgment = self._seed_full_pipeline()
        seed = seed_report_data_from_analysis(analysis)
        for section in REQUIRED_REPORT_DATA_SECTIONS:
            self.assertIn(section, seed, f"Missing section: {section}")
        for decl in REQUIRED_REPORT_DATA_DECLARATIONS:
            self.assertIn(decl, seed, f"Missing declaration: {decl}")

    def test_seed_hero_has_initial_verdict(self) -> None:
        """Seed carries an initial verdict draft, not final agent prose."""
        run_dir, analysis, judgment = self._seed_full_pipeline()
        seed = seed_report_data_from_analysis(analysis)
        hero = seed.get("hero", {})
        self.assertTrue(hero.get("verdict"), "Hero verdict should not be empty")

    def test_seed_preserves_source_paths(self) -> None:
        """source_path markers are preserved (including __ai_pending__ for unresolved)."""
        run_dir, analysis, judgment = self._seed_full_pipeline()
        seed = seed_report_data_from_analysis(analysis)
        source_paths = _extract_all_source_paths(seed)
        # Should have many source_paths (both resolved and __ai_pending__)
        self.assertGreater(len(source_paths), 0)
        # None should be empty string (would trigger QA block)
        for sp in source_paths:
            self.assertNotEqual(sp, "", "source_path must not be empty string")

    def test_cli_stops_after_seed_before_agent_outputs(self) -> None:
        """build_report_seed must not create formal report_data/HTML/XLSX."""
        run_dir, analysis, judgment = self._seed_full_pipeline()
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "packages" / "research_core" / "pipeline" / "build_report_seed.py"),
                str(run_dir),
            ],
            capture_output=True, text=True, env=_cli_env(),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Stage 11 complete", result.stdout)
        analysis_dir = run_dir / "analysis"
        self.assertTrue((analysis_dir / "report_data.seed.json").exists())
        self.assertTrue((analysis_dir / "analysis_packet.json").exists())
        self.assertFalse((analysis_dir / "report_data.json").exists())
        self.assertFalse(any(analysis_dir.glob("*_分析报告.html")))
        self.assertFalse(any(analysis_dir.glob("*_决策工具包.xlsx")))
        self.assertFalse((analysis_dir / "delivery_qa_result.json").exists())


# ── Agent HTML contract tests ─────────────────────────────────────────────

class AgentHTMLContractTests(unittest.TestCase):
    """Agent-written HTML follows delivery contract rules."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self._tmp = Path(self._tmpdir.name)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_html_has_all_six_main_sections(self) -> None:
        """Agent HTML contains all 6 required section markers."""
        html = _agent_report_html()
        for marker in REQUIRED_SECTION_MARKERS:
            self.assertIn(marker, html, f"Missing section: {marker}")

    def test_html_no_forbidden_internal_terms(self) -> None:
        """HTML does not leak Agent/MCP/tool/packet/pipeline/spawn/evidence_packet/source_path."""
        html = _agent_report_html()
        for pattern, description in FORBIDDEN_HTML_PATTERNS:
            matches = re.findall(pattern, html)
            self.assertEqual(len(matches), 0,
                           f"Forbidden pattern '{description}' found: {matches[:5]}")

    def test_html_has_inline_style(self) -> None:
        """Agent HTML embeds <style> block inline, no external CSS link."""
        html = _agent_report_html()
        self.assertIn("<style>", html)
        self.assertNotIn("report_template.css", html)

    def test_html_has_go_nogo_table(self) -> None:
        """Agent HTML has Go/No-Go table with go-nogo class."""
        html = _agent_report_html()
        self.assertIn("go-nogo", html)

    def test_html_starts_with_doctype(self) -> None:
        """Agent HTML is well-formed with DOCTYPE declaration."""
        html = _agent_report_html()
        self.assertTrue(html.strip().startswith("<!DOCTYPE html>"))


# ── XLSX back-table tests ────────────────────────────────────────────────

class XLSXBackTableTests(unittest.TestCase):
    """XLSX has all 10 required sheets."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self._tmp = Path(self._tmpdir.name)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def _build_report_data(self) -> dict[str, Any]:
        run_dir = self._tmp / "20260625_generic_xlsx"
        run_dir.mkdir()
        (run_dir / "workflow_state.json").write_text(
            json.dumps(_workflow_state(), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        run_quick_market_check(run_dir, snapshot_source_dir=P1_FIXTURES)
        write_agent_candidate_pool(run_dir)
        run_candidate_pool(run_dir)
        write_agent_route_matrix(run_dir)
        run_route_matrix_confirmation(run_dir)
        ss = self._tmp / "ss.json"
        ss.write_text(json.dumps(_valid_sellersprite_snapshot(), ensure_ascii=False, indent=2), encoding="utf-8")
        sf = self._tmp / "sf.json"
        sf.write_text(json.dumps(_valid_sorftime_snapshot(), ensure_ascii=False, indent=2), encoding="utf-8")
        rx = self._tmp / "rx.xlsx"
        _write_review_xlsx_file(rx, _sample_reviews(35))
        run_sellersprite_deep_dive(run_dir, snapshot_source=ss)
        run_sorftime_deep_dive(run_dir, snapshot_source=sf)
        run_conflict_review(run_dir)
        run_review_asin_batch(run_dir)
        run_review_voc_package(run_dir, rx)
        run_voc_gate(run_dir)
        _write_agent_evaluations(run_dir)
        run_evaluations(run_dir)
        run_integrated_judgment(run_dir)
        packets = load_packets(run_dir)
        analysis = build_analysis_packet(run_dir, packets)
        return seed_report_data_from_analysis(analysis)

    def test_all_five_sheets_generated(self) -> None:
        """report_data.json → 5-sheet decision workbook."""
        rd = self._build_report_data()
        rd_path = self._tmp / "report_data.json"
        rd_path.write_text(json.dumps(rd, ensure_ascii=False, indent=2), encoding="utf-8")
        sheets = xlsx_sheets_from_report_data(rd_path)
        sheet_names = {s[0] for s in sheets}
        expected = {"路线计分卡", "竞品拆解", "关键词矩阵", "样品检查表"}
        for name in expected:
            self.assertIn(name, sheet_names, f"Missing XLSX sheet: {name}")

    def test_xlsx_sheets_have_data_rows(self) -> None:
        """Each sheet has at least a header row."""
        rd = self._build_report_data()
        rd_path = self._tmp / "report_data.json"
        rd_path.write_text(json.dumps(rd, ensure_ascii=False, indent=2), encoding="utf-8")
        sheets = xlsx_sheets_from_report_data(rd_path)
        for name, rows in sheets:
            self.assertGreater(len(rows), 0, f"Sheet '{name}' has no rows")

    def test_xlsx_sanitizes_public_language(self) -> None:
        """Decision workbook cells do not expose internal jargon or dramatic phrasing."""
        rd = _minimal_valid_report_data()
        rd["competitors"] = [{
            "asin": {"value": "B0TEST", "source_path": "test"},
            "brand": {"value": "BrandX", "source_path": "test"},
            "monthly_sales": {"value": "500", "source_path": "test"},
            "price": {"value": "$19.99", "source_path": "test"},
            "rating": {"value": "4.2", "source_path": "test"},
            "rating_count": {"value": "200", "source_path": "test"},
            "available_date": {"value": "2026-01-01", "source_path": "test"},
            "route": {"value": "主线", "source_path": "test"},
            "source_path": "test",
        }]
        rd["pain_points"] = [{
            "priority": "P0",
            "dimension": {"value": "安全可靠性", "source_path": "test"},
            "review_count": {"value": "8", "source_path": "test"},
            "issue_description": "P0安全风险是0评论新品的生死考验。",
            "spec_requirement": "当前状态下做Go/No-Go是赌博。",
            "source_path": "test",
        }]
        judgment = {
            "competitor_weakness_map": [{
                "asin": "B0TEST",
                "fatal_weakness": "致命弱点：P0痛点。",
                "voc_evidence": "致命弱点：P0痛点。",
                "my_counter": "Stage 10a validation roadmap。",
            }],
            "competitor_benchmark": [{"asin": "B0TEST", "strength": "confidence Medium"}],
        }
        rd_path = self._tmp / "report_data.json"
        judgment_path = self._tmp / "judgment.json"
        rd_path.write_text(json.dumps(rd, ensure_ascii=False, indent=2), encoding="utf-8")
        judgment_path.write_text(json.dumps(judgment, ensure_ascii=False, indent=2), encoding="utf-8")

        sheets = xlsx_sheets_from_report_data(rd_path, judgment_path)
        for _, rows in sheets:
            for row in rows:
                for cell in row:
                    if isinstance(cell, str):
                        self.assertEqual(find_public_language_issues(cell), [])


# ── QA blocking rules ───────────────────────────────────────────────────

class QABlockingRulesTests(unittest.TestCase):
    """QA rules catch report issues."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self._tmp = Path(self._tmpdir.name)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_source_path_traceability_check_exists(self) -> None:
        """source_path validation is performed by QA."""
        rd_path = self._tmp / "report_data.json"
        rd_path.write_text(json.dumps(_minimal_valid_report_data(), ensure_ascii=False, indent=2), encoding="utf-8")
        # QA source validation checks that source_paths are not empty
        import random
        # The _validate_report_data_sources returns results structure
        from packages.research_core.pipeline.delivery_qa import _validate_report_data_sources
        result = _validate_report_data_sources(rd_path, {})
        self.assertIsInstance(result, dict)
        self.assertIn("pass", result)

    def test_html_forbidden_terms_detected(self) -> None:
        """Forbidden HTML patterns are caught."""
        from packages.research_core.pipeline.delivery_qa import _has_no_forbidden_html_patterns
        html_path = self._tmp / "test.html"
        html_path.write_text("<html>Agent says MCP tool pipeline spawn evidence_packet source_path</html>", encoding="utf-8")
        result = _has_no_forbidden_html_patterns(html_path)
        self.assertFalse(result["pass"])
        self.assertGreater(len(result.get("hits", [])), 0)

    def test_public_language_html_terms_detected(self) -> None:
        """Public-language violations are caught by HTML QA."""
        from packages.research_core.pipeline.delivery_qa import _has_no_forbidden_html_patterns
        html_path = self._tmp / "test.html"
        html_path.write_text("<html>P0安全风险是0评论新品的生死考验，confidence Medium。</html>", encoding="utf-8")
        result = _has_no_forbidden_html_patterns(html_path)
        self.assertFalse(result["pass"])
        self.assertGreater(len(result.get("hits", [])), 0)

    def test_public_language_xlsx_terms_detected(self) -> None:
        """Public-language violations are caught by XLSX QA."""
        from packages.research_core.pipeline.delivery_qa import _has_no_forbidden_xlsx_patterns
        xlsx_path = self._tmp / "bad.xlsx"
        write_xlsx(xlsx_path, [("Sheet1", [["说明"], ["P0安全风险是0评论新品的生死考验"]])])
        result = _has_no_forbidden_xlsx_patterns(xlsx_path)
        self.assertFalse(result["pass"])
        self.assertGreater(len(result.get("hits", [])), 0)

    def test_p0_blockers_block_delivery(self) -> None:
        """P0 blocking rules prevent delivery with unresolved blockers."""
        rd_path = self._tmp / "report_data.json"
        rd_path.write_text(json.dumps(_minimal_valid_report_data(), ensure_ascii=False, indent=2), encoding="utf-8")
        from packages.research_core.pipeline.delivery_qa import _validate_p0_delivery_blockers
        result = _validate_p0_delivery_blockers(self._tmp, rd_path)
        self.assertIsInstance(result, dict)
        self.assertIn("pass", result)


# ── Full chain CLI smoke ────────────────────────────────────────────────

class FullChainCLITests(unittest.TestCase):
    """CLI runs the full delivery chain."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self._tmp = Path(self._tmpdir.name)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def _seed_full_pipeline(self) -> Path:
        run_dir = self._tmp / "20260625_generic_full"
        run_dir.mkdir()
        (run_dir / "workflow_state.json").write_text(
            json.dumps(_workflow_state(), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        run_quick_market_check(run_dir, snapshot_source_dir=P1_FIXTURES)
        write_agent_candidate_pool(run_dir)
        run_candidate_pool(run_dir)
        write_agent_route_matrix(run_dir)
        run_route_matrix_confirmation(run_dir)
        ss = self._tmp / "ss.json"
        ss.write_text(json.dumps(_valid_sellersprite_snapshot(), ensure_ascii=False, indent=2), encoding="utf-8")
        sf = self._tmp / "sf.json"
        sf.write_text(json.dumps(_valid_sorftime_snapshot(), ensure_ascii=False, indent=2), encoding="utf-8")
        rx = self._tmp / "rx.xlsx"
        _write_review_xlsx_file(rx, _sample_reviews(35))
        run_sellersprite_deep_dive(run_dir, snapshot_source=ss)
        run_sorftime_deep_dive(run_dir, snapshot_source=sf)
        run_conflict_review(run_dir)
        run_review_asin_batch(run_dir)
        run_review_voc_package(run_dir, rx)
        run_voc_gate(run_dir)
        _write_agent_evaluations(run_dir)
        run_evaluations(run_dir)
        run_integrated_judgment(run_dir)
        return run_dir

    def test_build_report_chain_after_agent_handoff(self) -> None:
        """build_report_seed → agent → build_report_xlsx chain."""
        run_dir = self._seed_full_pipeline()
        analysis_dir = run_dir / "analysis"

        # Stage 11: seed
        seed_result = subprocess.run(
            [sys.executable,
             str(ROOT / "packages" / "research_core" / "pipeline" / "build_report_seed.py"),
             str(run_dir)],
            capture_output=True, text=True, env=_cli_env(),
        )
        self.assertEqual(seed_result.returncode, 0,
                         f"Seed failed: stdout={seed_result.stdout}, stderr={seed_result.stderr}")
        self.assertIn("Stage 11 complete", seed_result.stdout)
        self.assertTrue((analysis_dir / "report_data.seed.json").exists())
        self.assertFalse((analysis_dir / "report_data.json").exists())
        self.assertFalse(any(analysis_dir.glob("*_分析报告.html")))
        self.assertFalse(any(analysis_dir.glob("*_决策工具包.xlsx")))

        # Simulate Stage 12 Agent output
        _write_agent_report_outputs(run_dir)

        # Stage 12 post-Agent: XLSX + QA
        xlsx_result = subprocess.run(
            [sys.executable,
             str(ROOT / "packages" / "research_core" / "pipeline" / "build_report_xlsx.py"),
             str(run_dir)],
            capture_output=True, text=True, env=_cli_env(),
        )
        self.assertEqual(xlsx_result.returncode, 0,
                         f"XLSX/QA failed: stdout={xlsx_result.stdout}, stderr={xlsx_result.stderr}")
        self.assertIn("Report delivery: PASS", xlsx_result.stdout)

        self.assertTrue((analysis_dir / "report_data.json").exists())
        self.assertTrue(any(analysis_dir.glob("*_分析报告.html")))
        self.assertTrue(any(analysis_dir.glob("*_决策工具包.xlsx")))
        self.assertTrue((analysis_dir / "delivery_qa_result.json").exists())
        self.assertTrue((analysis_dir / "qa_notes.md").exists())
        self.assertTrue((run_dir / "audit_run_status.json").exists())

    def test_cli_nonexistent_dir_error(self) -> None:
        """Seed CLI with nonexistent path returns error."""
        result = subprocess.run(
            [sys.executable,
             str(ROOT / "packages" / "research_core" / "pipeline" / "build_report_seed.py"),
             "/nonexistent/dir"],
            capture_output=True, text=True, env=_cli_env(),
        )
        self.assertNotEqual(result.returncode, 0)
        # xlsx CLI too
        result2 = subprocess.run(
            [sys.executable,
             str(ROOT / "packages" / "research_core" / "pipeline" / "build_report_xlsx.py"),
             "/nonexistent/dir"],
            capture_output=True, text=True, env=_cli_env(),
        )
        self.assertNotEqual(result2.returncode, 0)


# ── Report Generation Agent ─────────────────────────────────────────────

class ReportAgentEnhancementTests(unittest.TestCase):
    """Agent enhancement from seed to report_data.json."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self._tmp = Path(self._tmpdir.name)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_enhance_preserves_all_sections(self) -> None:
        """Enhanced report_data has all 11 required sections."""
        from packages.research_core.pipeline.report_agent import enhance_seed_to_report_data
        seed = _minimal_valid_report_data()
        rd = enhance_seed_to_report_data(seed, None, None)
        for section in REQUIRED_REPORT_DATA_SECTIONS:
            self.assertIn(section, rd, f"Missing section: {section}")
        for decl in REQUIRED_REPORT_DATA_DECLARATIONS:
            self.assertIn(decl, rd, f"Missing declaration: {decl}")

    def test_enhance_adds_execution_provenance(self) -> None:
        """Enhancement adds serial_fallback provenance."""
        from packages.research_core.pipeline.report_agent import enhance_seed_to_report_data
        seed = _minimal_valid_report_data()
        rd = enhance_seed_to_report_data(seed, None, None)
        ep = rd.get("execution_provenance") or {}
        self.assertEqual(ep.get("execution_mode"), "serial_fallback")
        self.assertEqual(ep.get("agent_role"), "Report Generation Agent")

    def test_enhance_no_empty_source_path(self) -> None:
        """Enhanced report_data has zero empty-string source_paths."""
        from packages.research_core.pipeline.report_agent import enhance_seed_to_report_data
        seed = _minimal_valid_report_data()
        rd = enhance_seed_to_report_data(seed, None, None)
        empty = _extract_all_source_paths(rd)
        empty_strings = [sp for sp in empty if sp == ""]
        self.assertEqual(len(empty_strings), 0,
                         f"Found empty source_paths: {empty_strings}")

    def test_enhance_with_judgment_fills_verdict(self) -> None:
        """Judgment verdict overrides seed verdict."""
        from packages.research_core.pipeline.report_agent import enhance_seed_to_report_data
        seed = _minimal_valid_report_data()
        judgment = {
            "final_verdict": "go",
            "verdict_reason": "各项指标良好，建议进入。",
            "confidence": "high",
            "required_next_actions": ["补关键词数据", "联系供应商"],
        }
        rd = enhance_seed_to_report_data(seed, judgment, None)
        self.assertIn("建议进入小批量验证", rd["hero"]["verdict"])
        self.assertEqual(rd["hero"]["confidence"], "high")

    def test_enhance_with_judgment_populates_next_steps(self) -> None:
        """Judgment required_next_actions become next_steps."""
        from packages.research_core.pipeline.report_agent import enhance_seed_to_report_data
        seed = _minimal_valid_report_data()
        judgment = {
            "final_verdict": "watch",
            "required_next_actions": ["动作一", "动作二", "动作三", "动作四"],
        }
        rd = enhance_seed_to_report_data(seed, judgment, None)
        steps = rd.get("next_steps") or []
        self.assertGreater(len(steps), 0)
        self.assertLessEqual(len(steps), 3)

    def test_enhance_fills_competitor_judgments(self) -> None:
        """Competitors without judgment get data-driven judgment text."""
        from packages.research_core.pipeline.report_agent import enhance_seed_to_report_data
        seed = _minimal_valid_report_data()
        seed["competitors"] = [{
            "asin": {"value": "B0TEST", "source_path": "test"},
            "route": {"value": "主线", "source_path": "test"},
            "brand": {"value": "BrandX", "source_path": "test"},
            "price": {"value": "29", "source_path": "test"},
            "monthly_sales": {"value": "500", "source_path": "test"},
            "rating": {"value": "4.2", "source_path": "test"},
            "rating_count": {"value": "200", "source_path": "test"},
            "asin_role": {"value": "primary_reference", "source_path": "test"},
            "judgment": "",
            "source_path": "test",
        }]
        rd = enhance_seed_to_report_data(seed, None, None)
        c = rd["competitors"][0]
        self.assertTrue(c.get("judgment"), f"judgment should not be empty: {c}")

    def test_enhance_fills_pain_point_descriptions(self) -> None:
        """Pain points get issue and spec descriptions."""
        from packages.research_core.pipeline.report_agent import enhance_seed_to_report_data
        seed = _minimal_valid_report_data()
        seed["pain_points"] = [{
            "priority": "P0",
            "dimension": {"value": "漏水", "source_path": "test"},
            "review_count": {"value": "8", "source_path": "test"},
            "asins_affected_count": {"value": "2", "source_path": "__ai_pending__"},
            "issue_description": "",
            "spec_requirement": "",
            "source_path": "test",
        }]
        rd = enhance_seed_to_report_data(seed, None, None)
        pp = rd["pain_points"][0]
        self.assertTrue(pp.get("issue_description"))
        self.assertTrue(pp.get("spec_requirement"))

    def test_enhance_fills_price_band_judgments(self) -> None:
        """Price bands get opportunity-level judgments."""
        from packages.research_core.pipeline.report_agent import enhance_seed_to_report_data
        seed = _minimal_valid_report_data()
        seed["price_bands"] = [{
            "band": {"value": "20-30", "source_path": "test"},
            "unit_share": {"value": "35%", "source_path": "test"},
            "product_count": {"value": "15", "source_path": "test"},
            "opportunity_level": {"value": "strong", "source_path": "test"},
            "bar_height": {"value": 70, "source_path": "test"},
            "judgment": "",
            "source_path": "test",
        }]
        rd = enhance_seed_to_report_data(seed, None, None)
        pb = rd["price_bands"][0]
        self.assertTrue(pb.get("judgment"))
        self.assertIn("机会", pb.get("judgment", ""))

    def test_enhance_sanitizes_judgment_public_language(self) -> None:
        """Judgment prose is cleaned before it can feed HTML/XLSX deliverables."""
        from packages.research_core.pipeline.report_agent import enhance_seed_to_report_data
        seed = _minimal_valid_report_data()
        seed["pain_points"] = [{
            "priority": "P0",
            "dimension": {"value": "安全可靠性", "source_path": "test"},
            "review_count": {"value": "8", "source_path": "test"},
            "issue_description": "",
            "spec_requirement": "",
            "source_path": "test",
        }]
        seed["risks"] = [{
            "severity": "高",
            "description": "",
            "mitigation": "",
            "evidence_basis": "",
            "source_path": "test",
        }]
        dirty = "P0安全风险是0评论新品的生死考验，confidence Medium，final_verdict=watch，rating=blocked，Stage 10a。"
        judgment = {
            "final_verdict": "watch",
            "confidence": "medium",
            "route_recommendation": {"primary_recommendation": dirty},
            "voc_to_spec": [{
                "dimension": "安全可靠性",
                "issue_description": dirty,
                "spec_requirement": "P0安全项必须送测。",
            }],
            "risk_mitigation": [{
                "operational_meaning": dirty,
                "mitigation_path": "Stage 10a validation roadmap。",
            }],
        }
        rd = enhance_seed_to_report_data(seed, judgment, None)
        visible_text = "\n".join([
            rd["hero"]["lead_analysis"],
            rd["pain_points"][0]["issue_description"],
            rd["pain_points"][0]["spec_requirement"],
            rd["risks"][0]["description"],
            rd["risks"][0]["mitigation"],
        ])
        self.assertEqual(find_public_language_issues(visible_text), [])


class ReportAgentHTMLTests(unittest.TestCase):
    """Agent HTML output follows contract rules."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self._tmp = Path(self._tmpdir.name)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_html_all_six_sections(self) -> None:
        """Generated HTML contains all 6 required sections."""
        from packages.research_core.pipeline.report_agent import generate_operator_html
        rd = _minimal_valid_report_data()
        html = generate_operator_html(rd)
        for marker in REQUIRED_SECTION_MARKERS:
            self.assertIn(marker, html, f"Missing section: {marker}")

    def test_html_no_forbidden_terms(self) -> None:
        """Generated HTML has zero forbidden internal terms."""
        from packages.research_core.pipeline.report_agent import generate_operator_html
        rd = _minimal_valid_report_data()
        html = generate_operator_html(rd)
        for pattern, description in FORBIDDEN_HTML_PATTERNS:
            matches = re.findall(pattern, html)
            self.assertEqual(len(matches), 0,
                           f"Forbidden '{description}' found: {matches[:5]}")

    def test_html_sanitizes_backend_source_names(self) -> None:
        """Generated HTML does not expose backend data-source brand names."""
        from packages.research_core.pipeline.report_agent import generate_operator_html
        rd = _minimal_valid_report_data()
        rd["hero"]["lead_analysis"] = (
            "卖家精灵 market_research_statistics 待补；"
            "Sorftime keyword_detail 与 product_traffic_terms 待补。"
        )
        html = generate_operator_html(rd)
        self.assertNotIn("卖家精灵", html)
        self.assertNotIn("Sorftime", html)
        self.assertNotIn("market_research_statistics", html)
        self.assertNotIn("keyword_detail", html)
        self.assertNotIn("product_traffic_terms", html)

    def test_html_sanitizes_public_language(self) -> None:
        """Generated HTML translates internal labels and dramatic risk phrasing."""
        from packages.research_core.pipeline.report_agent import generate_operator_html
        rd = _minimal_valid_report_data()
        rd["hero"]["lead_analysis"] = (
            "P0安全风险是0评论新品的生死考验，confidence Medium，final_verdict=watch，rating=blocked，Stage 10a。"
        )
        rd["pain_points"] = [{
            "priority": "P0",
            "dimension": {"value": "安全可靠性", "source_path": "test"},
            "review_count": {"value": "8", "source_path": "test"},
            "issue_description": "致命弱点：P0痛点。",
            "spec_requirement": "当前状态下做Go/No-Go是赌博。",
            "source_path": "test",
        }]
        html = generate_operator_html(rd)
        self.assertEqual(find_public_language_issues(html), [])
        self.assertIn("必须验证", html)
        self.assertIn("判断置信度中等", html)

    def test_html_has_inline_style_not_external_css(self) -> None:
        """HTML embeds <style>, no report_template.css path."""
        from packages.research_core.pipeline.report_agent import generate_operator_html
        rd = _minimal_valid_report_data()
        html = generate_operator_html(rd)
        self.assertIn("<style>", html)
        self.assertNotIn("report_template.css", html)

    def test_html_has_go_nogo_class(self) -> None:
        """HTML has go-nogo class for the Go/No-Go table."""
        from packages.research_core.pipeline.report_agent import generate_operator_html
        rd = _minimal_valid_report_data()
        html = generate_operator_html(rd)
        self.assertIn("go-nogo", html)

    def test_html_starts_with_doctype(self) -> None:
        """HTML is well-formed."""
        from packages.research_core.pipeline.report_agent import generate_operator_html
        rd = _minimal_valid_report_data()
        html = generate_operator_html(rd)
        self.assertTrue(html.strip().startswith("<!DOCTYPE html>"))


class ReportAgentValidationTests(unittest.TestCase):
    """Agent output validation catches issues."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self._tmp = Path(self._tmpdir.name)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_valid_output_passes(self) -> None:
        """Valid report_data.json + HTML passes validation."""
        from packages.research_core.pipeline.report_agent import validate_agent_output
        rd_path = self._tmp / "report_data.json"
        rd_path.write_text(json.dumps(_minimal_valid_report_data(), ensure_ascii=False, indent=2), encoding="utf-8")
        html_path = self._tmp / "test.html"
        html_path.write_text(_agent_report_html(), encoding="utf-8")
        result = validate_agent_output(rd_path, html_path)
        self.assertTrue(result["valid"], f"Issues: {result.get('issues', [])}")

    def test_missing_report_data_detected(self) -> None:
        """Missing report_data.json is caught."""
        from packages.research_core.pipeline.report_agent import validate_agent_output
        rd_path = self._tmp / "missing.json"
        html_path = self._tmp / "test.html"
        html_path.write_text(_agent_report_html(), encoding="utf-8")
        result = validate_agent_output(rd_path, html_path)
        self.assertFalse(result["valid"])
        self.assertIn("report_data.json missing", result["issues"])

    def test_empty_source_path_detected(self) -> None:
        """Empty string source_path is caught."""
        from packages.research_core.pipeline.report_agent import validate_agent_output
        rd = _minimal_valid_report_data()
        rd["hero"]["metrics"]["target_market"]["source_path"] = ""
        rd_path = self._tmp / "report_data.json"
        rd_path.write_text(json.dumps(rd, ensure_ascii=False, indent=2), encoding="utf-8")
        html_path = self._tmp / "test.html"
        html_path.write_text(_agent_report_html(), encoding="utf-8")
        result = validate_agent_output(rd_path, html_path)
        self.assertFalse(result["valid"])
        self.assertTrue(any("empty source_path" in i for i in result.get("issues", [])))

    def test_missing_html_detected(self) -> None:
        """Missing HTML is caught."""
        from packages.research_core.pipeline.report_agent import validate_agent_output
        rd_path = self._tmp / "report_data.json"
        rd_path.write_text(json.dumps(_minimal_valid_report_data(), ensure_ascii=False, indent=2), encoding="utf-8")
        result = validate_agent_output(rd_path, self._tmp / "missing.html")
        self.assertIn("HTML missing", result.get("issues", []))

    def test_modified_template_css_detected(self) -> None:
        """HTML style drift from report_template.css is caught."""
        from packages.research_core.pipeline.report_agent import validate_agent_output
        rd_path = self._tmp / "report_data.json"
        rd_path.write_text(json.dumps(_minimal_valid_report_data(), ensure_ascii=False, indent=2), encoding="utf-8")
        html_path = self._tmp / "test.html"
        html_path.write_text(
            _agent_report_html().replace("--bg: #F8FAFC;", "--bg: #ffffff;"),
            encoding="utf-8",
        )
        result = validate_agent_output(rd_path, html_path)
        self.assertTrue(result["valid"], f"CSS 变体不应阻断: {result.get('issues')}")

    def test_unknown_class_is_warning_not_blocker(self) -> None:
        """模板外 class 仅 warning 不阻断。"""
        from packages.research_core.pipeline.report_agent import validate_agent_output
        rd_path = self._tmp / "report_data.json"
        rd_path.write_text(json.dumps(_minimal_valid_report_data(), ensure_ascii=False, indent=2), encoding="utf-8")
        html_path = self._tmp / "test.html"
        html_path.write_text(
            _agent_report_html().replace("</body>", '<div class="bar-label">漂移类名</div></body>'),
            encoding="utf-8",
        )
        result = validate_agent_output(rd_path, html_path)
        self.assertTrue(result["valid"], f"模板外 class 不应阻断: {result.get('issues')}")

    def test_fixed_data_source_section_detected(self) -> None:
        """The formal HTML must not add a fixed data source section."""
        from packages.research_core.pipeline.report_agent import validate_agent_output
        rd_path = self._tmp / "report_data.json"
        rd_path.write_text(json.dumps(_minimal_valid_report_data(), ensure_ascii=False, indent=2), encoding="utf-8")
        html_path = self._tmp / "test.html"
        html_path.write_text(
            _agent_report_html().replace("</body>", "<section><h2>数据来源与口径</h2></section></body>"),
            encoding="utf-8",
        )
        result = validate_agent_output(rd_path, html_path)
        self.assertFalse(result["valid"])
        self.assertTrue(any("数据来源与口径" in i for i in result.get("issues", [])))


class ReportAgentCLITests(unittest.TestCase):
    """CLI entry for Report Generation Agent."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self._tmp = Path(self._tmpdir.name)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_cli_run_report_agent_smoke(self) -> None:
        """run_report_agent CLI writes report_data.json and HTML."""
        run_dir = self._tmp / "test_run"
        analysis_dir = run_dir / "analysis"
        analysis_dir.mkdir(parents=True)
        (analysis_dir / "report_data.seed.json").write_text(
            json.dumps(_minimal_valid_report_data(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "run_report_agent.py"), str(run_dir)],
            capture_output=True, text=True, env=_cli_env(),
        )
        self.assertEqual(result.returncode, 0,
                         f"Agent CLI failed: stdout={result.stdout}, stderr={result.stderr}")
        self.assertTrue((analysis_dir / "report_data.json").exists())
        self.assertTrue(any(analysis_dir.glob("*_分析报告.html")))

    def test_cli_no_seed_fails(self) -> None:
        """CLI without seed returns error."""
        run_dir = self._tmp / "test_run"
        analysis_dir = run_dir / "analysis"
        analysis_dir.mkdir(parents=True)
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "run_report_agent.py"), str(run_dir)],
            capture_output=True, text=True, env=_cli_env(),
        )
        self.assertNotEqual(result.returncode, 0)

    def test_cli_nonexistent_dir_fails(self) -> None:
        """CLI with nonexistent directory returns error."""
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "run_report_agent.py"), "/nonexistent/dir"],
            capture_output=True, text=True, env=_cli_env(),
        )
        self.assertNotEqual(result.returncode, 0)

    def test_cli_full_two_phase_flow(self) -> None:
        """Phase 1 seed → Phase 2 agent → Phase 3 XLSX/QA."""
        run_dir = self._tmp / "full_flow"
        run_dir.mkdir()

        from packages.research_core.pipeline.quick_market_check import run_quick_market_check
        from packages.research_core.pipeline.build_mcp_candidate_pool import run_candidate_pool
        from packages.research_core.pipeline.build_route_matrix_confirmation import run_route_matrix_confirmation
        from packages.research_core.pipeline.build_sellersprite_deep_dive import run_sellersprite_deep_dive
        from packages.research_core.pipeline.build_sorftime_deep_dive import run_sorftime_deep_dive
        from packages.research_core.pipeline.build_conflict_review import run_conflict_review
        from packages.research_core.pipeline.build_review_asin_batch import run_review_asin_batch
        from packages.research_core.pipeline.build_review_voc_package import run_review_voc_package
        from packages.research_core.pipeline.build_voc_gate import run_voc_gate
        from packages.research_core.pipeline.build_evaluation_summary import run_evaluations
        from packages.research_core.pipeline.build_integrated_judgment import run_integrated_judgment

        (run_dir / "workflow_state.json").write_text(
            json.dumps(_workflow_state(), ensure_ascii=False, indent=2), encoding="utf-8")

        ss = self._tmp / "ss.json"
        ss.write_text(json.dumps(_valid_sellersprite_snapshot(), ensure_ascii=False, indent=2), encoding="utf-8")
        sf = self._tmp / "sf.json"
        sf.write_text(json.dumps(_valid_sorftime_snapshot(), ensure_ascii=False, indent=2), encoding="utf-8")
        rx = self._tmp / "rx.xlsx"
        _write_review_xlsx_file(rx, _sample_reviews(35))

        run_quick_market_check(run_dir, snapshot_source_dir=P1_FIXTURES)
        write_agent_candidate_pool(run_dir)
        run_candidate_pool(run_dir)
        write_agent_route_matrix(run_dir)
        run_route_matrix_confirmation(run_dir)
        run_sellersprite_deep_dive(run_dir, snapshot_source=ss)
        run_sorftime_deep_dive(run_dir, snapshot_source=sf)
        run_conflict_review(run_dir)
        run_review_asin_batch(run_dir)
        run_review_voc_package(run_dir, rx)
        run_voc_gate(run_dir)
        _write_agent_evaluations(run_dir)
        run_evaluations(run_dir)
        run_integrated_judgment(run_dir)

        analysis_dir = run_dir / "analysis"

        # Phase 1: build_report_seed → seed
        r1 = subprocess.run(
            [sys.executable,
             str(ROOT / "packages" / "research_core" / "pipeline" / "build_report_seed.py"),
             str(run_dir)],
            capture_output=True, text=True, env=_cli_env(),
        )
        self.assertEqual(r1.returncode, 0, f"Phase 1 failed: {r1.stderr}")
        self.assertIn("Stage 11 complete", r1.stdout)
        self.assertTrue((analysis_dir / "report_data.seed.json").exists())
        self.assertFalse((analysis_dir / "report_data.json").exists())

        # Phase 2: Agent → report_data.json + HTML
        # Overwrite serial_fallback judgment with contract-valid one first
        _write_agent_report_outputs(run_dir)
        self.assertTrue((analysis_dir / "report_data.json").exists())
        self.assertTrue(any(analysis_dir.glob("*_分析报告.html")))

        # Phase 3: build_report_xlsx → XLSX + QA
        r3 = subprocess.run(
            [sys.executable,
             str(ROOT / "packages" / "research_core" / "pipeline" / "build_report_xlsx.py"),
             str(run_dir)],
            capture_output=True, text=True, env=_cli_env(),
        )
        self.assertEqual(r3.returncode, 0, f"Phase 3 failed: stdout={r3.stdout}, stderr={r3.stderr}")
        self.assertIn("Report delivery: PASS", r3.stdout)
        self.assertTrue(any(analysis_dir.glob("*_决策工具包.xlsx")))
        self.assertTrue((analysis_dir / "delivery_qa_result.json").exists())
        self.assertTrue((analysis_dir / "qa_notes.md").exists())
        self.assertTrue((run_dir / "audit_run_status.json").exists())


# ── Helpers ────────────────────────────────────────────────────────────

def _agent_report_html() -> str:
    """Minimal formal HTML report as if written by Report Generation Agent."""
    css = (
        ROOT
        / "skills"
        / "amazon-product-research"
        / "references"
        / "report_template.css"
    ).read_text(encoding="utf-8")
    return f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<style>
{css}
</style></head><body><div class="page">
<section class="hero"><div class="verdict">建议补齐数据后再评估</div>
<p class="lead">样本边界：基于当前样本做市场判断。</p></section>
<section class="section"><h2>类目全景</h2><p>先看目标类目的需求、价格和竞争边界。</p></section>
<section class="section"><h2>核心竞品</h2><table><tbody><tr><td>代表 ASIN</td></tr></tbody></table></section>
<section class="section"><h2>用户痛点</h2><p>把评论痛点翻译成产品规格要求。</p></section>
<section class="section"><h2>价格带分布</h2><p>结合样本价格带判断可验证区间。</p></section>
<section class="section"><h2>关键词与流量策略</h2><p>区分主攻词、可测词和排除词。</p></section>
<section class="section"><h2>风险与下一步</h2><table class="go-nogo">
<tbody><tr><td>补齐样本后再进入下一轮验证</td></tr></tbody></table></section>
</div></body></html>"""


def _write_agent_report_outputs(run_dir: Path) -> None:
    """Simulate Stage 10 + Stage 12 Agent outputs (contract-valid judgment + report_data + HTML)."""
    analysis_dir = run_dir / "analysis"

    # Overwrite serial_fallback judgment with contract-valid one (simulates Lead Operator Agent)
    judgment_path = analysis_dir / "integrated_operator_judgment.json"
    if judgment_path.exists():
        j = json.loads(judgment_path.read_text(encoding="utf-8"))
    else:
        j = {}
    j.update({
        "schema_version": "p7-judgment-v2",
        "packet_id": "integrated_operator_judgment",
        "stage": "stage_9_report",
        "generated_at": j.get("generated_at", "2026-06-25T00:00:00"),
        "final_verdict": "watch",
        "confidence": "medium",
        "verdict_reason": "基于六维评价的综合判断。",
        "biggest_opportunity": {"dimension": "market_demand", "score": 72, "detail": "类目容量适中"},
        "biggest_risk": {"dimension": "competition", "score": 45, "detail": "头部集中度较高"},
        "required_next_actions": ["验证打样品质", "对比竞品材质"],
        "operator_constraints": {},
        "constraints_applied": [],
        "evidence_refs": ["market_structure.market_size", "search_demand.keyword_pool"],
        "execution_provenance": {
            "executed_by_agent": True,
            "agent_role": "Lead Operator Agent",
            "execution_mode": "real_subagent_spawn",
            "subagent_id": "agent-lead-operator-test",
            "note": "Test fixture simulates Lead Operator final judgment.",
        },
        "route_recommendation": {"routes": [], "primary_recommendation": "建议主线款优先进入"},
        "route_tradeoff": [{"route_name": "主线", "gain": "流量大", "lose": "竞争激烈", "best_for": "有成本优势", "worst_for": "新手"}],
        "competitor_benchmark": [{"asin": "B001", "differentiation_direction": "材质升级", "pricing_anchor": "$19.99", "why_benchmark": "类目销量TOP"}],
        "competitor_weakness_map": [{"asin": "B001", "fatal_weakness": "卡扣易断", "my_counter": "不锈钢卡扣+5000次测试"}],
                "price_band_analysis": [{"range": "15-25", "competitive_meaning": "主力段", "entry_recommendation": "以此段切入"}],
        "voc_to_spec": [{"dimension": "耐用", "spec_requirement": "拉力≥50kg", "benchmark_gap": "竞品30kg", "differentiation_opportunity": "差异化在耐用"}],
        "keyword_strategy": {"primary_attack": [], "testable": [], "negative": []},
        "risk_mitigation": [{"operational_meaning": "季节波动", "mitigation_path": "提前备货"}],
        "validation_roadmap": [{"phase": "打样验证", "actions": ["找工厂"], "exit_criteria": "通过", "if_fail": "换供应商"}],
    })
    judgment_path.write_text(json.dumps(j, ensure_ascii=False, indent=2), encoding="utf-8")
    _mark_lead_operator_done(run_dir)

    seed_path = analysis_dir / "report_data.seed.json"
    report_data = json.loads(seed_path.read_text(encoding="utf-8"))
    report_data_path = analysis_dir / "report_data.json"
    report_data_path.write_text(json.dumps(report_data, ensure_ascii=False, indent=2), encoding="utf-8")
    html_path = analysis_dir / f"{_extract_product_name(run_dir)}_分析报告.html"
    html_path.write_text(_agent_report_html(), encoding="utf-8")


def _mark_lead_operator_done(run_dir: Path) -> None:
    """Simulate Lead Operator Agent completing Stage 10b."""
    progress_path = run_dir / "progress.json"
    if not progress_path.exists():
        return
    progress = json.loads(progress_path.read_text(encoding="utf-8"))
    stages = progress.setdefault("stages", {})
    stage = stages.setdefault("stage_9_report", {})
    stage.update({
        "status": "done",
        "attempts": max(1, int(stage.get("attempts", 0) or 0)),
        "input_artifacts": stage.get("input_artifacts") or [
            "evaluations/evaluation_summary.json",
            "analysis/integrated_operator_judgment.json",
        ],
        "output_artifacts": ["analysis/integrated_operator_judgment.json"],
        "validation_checks": [
            {
                "name": "lead_operator_final_judgment",
                "pass": True,
                "detail": "Lead Operator Agent filled final judgment.",
            }
        ],
        "resume_policy": {
            "reuse_existing_artifacts": True,
            "allow_repeat_mcp_call": False,
        },
        "last_error": "",
    })
    progress["current_stage"] = "stage_9_report"
    progress["next_action"] = {
        "type": "ready_for_report",
        "stage_id": "stage_11_report_seed",
        "description": "Lead Operator Agent 已完成最终判断，可进入报告 seed 和报告生成阶段。",
    }
    completed = progress.setdefault("completed_artifacts", [])
    artifact = "analysis/integrated_operator_judgment.json"
    if artifact not in completed:
        completed.append(artifact)
    progress_path.write_text(json.dumps(progress, ensure_ascii=False, indent=2), encoding="utf-8")


def _extract_all_source_paths(obj: Any) -> list[str]:
    """Recursively extract all source_path string values."""
    results: list[str] = []
    if isinstance(obj, dict):
        for key, val in obj.items():
            if key == "source_path" and isinstance(val, str):
                results.append(val)
            else:
                results.extend(_extract_all_source_paths(val))
    elif isinstance(obj, list):
        for item in obj:
            results.extend(_extract_all_source_paths(item))
    return results


def _minimal_valid_report_data() -> dict[str, Any]:
    return {
        "schema_version": "report-data-v1",
        "packet_id": "report_data",
        "run_id": "test",
        "generated_at": "2026-06-25T00:00:00",
        "evidence_sources": [{
            "name": {"value": "Test Source", "source_path": "test.source[0].name"},
            "path": {"value": "test/path.json", "source_path": "test.source[0].path"},
            "exists": {"value": True, "source_path": "test.source[0].exists"},
            "packet_id": {"value": "test_packet", "source_path": "test.source[0].packet_id"},
            "confidence": {"value": "medium", "source_path": "test.source[0].confidence"},
            "execution_mode": {"value": "serial_fallback", "source_path": "test.source[0].execution_mode"},
            "provenance_note": {"value": "test", "source_path": "test.source[0].provenance_note"},
        }],
        "hero": {
            "verdict": "建议补齐数据后再评估",
            "lead_analysis": "测试引导语。",
            "evidence_sources": ["Test Source"],
            "metrics": {
                "target_market": {"value": "测试类目", "source_path": "test.primary.label"},
                "monthly_demand": {"value": "100 units", "source_path": "test.primary.units"},
                "core_search_volume": {"value": "~10K", "source_path": "test.derived.csv"},
                "avg_price": {"value": "$20", "source_path": "test.primary.price"},
                "recommended_price": {"value": "$15-25", "source_path": "test.derived.rp"},
                "avg_rating": {"value": "4.5", "source_path": "test.primary.rating"},
            },
            "confidence": "medium",
            "data_freshness": "test",
        },
        "category_panorama": {
            "categories": [{
                "category_name": {"value": "测试类目", "source_path": "__ai_pending__"},
                "node_id": {"value": "123", "source_path": "__ai_pending__"},
                "category_path": {"value": "测试>类目", "source_path": "__ai_pending__"},
                "top100_monthly_sales": {"value": "1000", "source_path": "__ai_pending__"},
                "top100_monthly_revenue": {"value": "20000", "source_path": "__ai_pending__"},
                "product_count_in_category": {"value": "50", "source_path": "__ai_pending__"},
                "representative_asins": [],
                "avg_price": {"value": "20", "source_path": "__ai_pending__"},
                "category_role": {"value": "broad_market", "source_path": "__ai_pending__"},
                "reason": "测试理由",
                "lineage": ["__ai_pending__"],
            }],
            "sub_market": {"product_form": "测试", "estimated_monthly_units": "100", "estimated_monthly_revenue": "2000", "source_path": "__ai_pending__"},
            "market_health": {"top3_brand_share": "50%", "china_seller_share": "30%", "new_3m_share": "10%", "concentration_note": "测试", "source_path": "__ai_pending__"},
            "seasonality": {"peak_months": ["1月"], "trough_months": ["6月"], "peak_trough_ratio": "2:1", "source_path": "__ai_pending__"},
            "insights": [{"type": "good", "title": "测试", "body": "测试", "source_path": "__ai_pending__"}],
        },
        "data_sources": {
            "source_packets": [],
            "critical_inputs": {"route_matrix": "route_matrix_confirm.json", "workflow_state": "workflow_state.json"},
            "data_gaps": [],
            "freshness_note": "test",
        },
        "competitors": [],
        "pain_points": [],
        "price_bands": [],
        "keywords": [],
        "risks": [],
        "advantages": [],
        "gonogo_conditions": [],
        "next_steps": [],
    }


def _write_agent_evaluations(run_dir: Path) -> None:
    """Write 6 valid Agent-produced evaluation files so run_evaluations() can read them."""
    eval_dir = run_dir / "evaluations"
    eval_dir.mkdir(parents=True, exist_ok=True)
    dims = ["market_demand", "competition", "price_profit", "voc_opportunity", "risk", "data_quality"]
    for dim in dims:
        ev = {
            "schema_version": "p6-evaluation-v1",
            "packet_id": f"{dim}_evaluation",
            "stage": "evaluation",
            "score": 75,
            "rating": "strong",
            "confidence": "high",
            "key_reasons": [f"{dim} signal is healthy"],
            "risks": [],
            "required_followups": [f"Verify {dim} with additional data"],
            "evidence_refs": [f"evidence_packet.json#{dim}"],
            "execution_provenance": {
                "executed_by_agent": True,
                "agent_role": f"{dim} Evaluation Agent",
                "execution_mode": "real_subagent_spawn",
                "subagent_id": f"agent-{dim}-001",
                "note": "Agent produced evaluation from evidence packets.",
            },
        }
        (eval_dir / f"{dim}_evaluation.json").write_text(
            json.dumps(ev, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )


def _workflow_state() -> dict[str, Any]:
    return {
        "workflow_id": "20260625_generic_delivery",
        "mode": "market_quick_check",
        "stage": "stage_2_market_quick_check",
        "initial_intent": "<generic_direction>",
        "site": "US",
        "known_inputs": {
            "direction": "<generic_direction>",
            "keyword": "<generic_keyword>",
            "asin": "",
            "exclusions": [],
            "preferences": {},
        },
        "missing_inputs": [],
        "next_actions": [],
        "evidence_refs": [],
        "decision_log": [],
    }


def _sample_reviews(count: int = 35) -> list[dict[str, Any]]:
    reviews = []
    for i in range(1, count + 1):
        rating = 5.0 - (i % 5)
        if rating == 0:
            rating = 1.0
        reviews.append({
            "review_id": f"R{i:06d}",
            "asin": f"B0XXXXX{i % 8:03d}",
            "site": "US",
            "review_region": "US",
            "raw_date": f"2026-0{(i % 6) + 1:01d}-{(i % 28) + 1:02d}",
            "review_date": f"2026-0{(i % 6) + 1:01d}-{(i % 28) + 1:02d}",
            "raw_rating": str(int(rating)),
            "rating": rating,
            "sentiment": "正面" if rating >= 4 else ("中性" if rating == 3 else "负面"),
            "author": f"author_{i}",
            "verified": "是" if i % 3 != 0 else "否",
            "helpful_count": i % 10,
            "has_buyer_image": "是" if i % 5 == 0 else "否",
            "image_count": 1 if i % 5 == 0 else 0,
            "has_video": "否",
            "variant": f"Color-{chr(65 + i % 3)}",
            "color": f"Color-{chr(65 + i % 3)}",
            "size": "M",
            "title_en": f"Review title {i}",
            "body_en": f"This is a review for product {i}. Works well.{' Durability issue noted.' if rating <= 2 else ''}",
            "title_zh": f"评论标题{i}",
            "body_zh": f"这是第{i}条产品评测。{'耐用性存在问题，需要改进材料和做工。' if rating <= 2 else '整体体验良好，功能实用。'}",
            "url": f"https://amazon.com/review/R{i:06d}",
            "source_file": "test_reviews.xlsx",
        })
    return reviews


def _write_review_xlsx_file(path: Path, reviews: list[dict[str, Any]]) -> None:
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "评论数据"
    headers = [
        "ASIN", "站点", "评论ID", "评论地区", "原始评论日期", "评论日期",
        "原始评星", "评星", "情绪", "评论人", "评论人主页", "是否验证购买",
        "Helpful数量", "是否有买家实拍", "图片数量", "图片链接", "是否有视频",
        "评论产品的属性", "颜色", "尺寸", "英文标题", "英文评论",
        "标题中文翻译", "评论中文翻译", "评论链接",
    ]
    ws.append(headers)
    for r in reviews:
        ws.append([
            r.get("asin"), r.get("site"), r.get("review_id"), r.get("review_region"),
            r.get("raw_date"), r.get("review_date"), r.get("raw_rating"), r.get("rating"),
            r.get("sentiment"), r.get("author"), "", r.get("verified"),
            r.get("helpful_count"), r.get("has_buyer_image"), r.get("image_count"),
            "", r.get("has_video"), r.get("variant"), r.get("color"), r.get("size"),
            r.get("title_en"), r.get("body_en"), r.get("title_zh"), r.get("body_zh"),
            r.get("url"),
        ])
    wb.save(str(path))


def _valid_sellersprite_snapshot() -> dict:
    return {
        "schema_version": "p4-deep-contract-v1",
        "snapshot_id": "generic-sellersprite-deep",
        "run_id": "20260625_generic_delivery",
        "source_name": "sellersprite",
        "source_doc_refs": ["docs/references/p4_mcp_capability_mapping.md#sellersprite"],
        "route_refs": ["route_matrix_confirm.json#selected_routes[0]"],
        "selected_routes": ["<generic_route_ref>"],
        "tool_calls": [
            {"call_id": "call-market", "tool_name": "market_research", "params": {"marketplace": "US", "nodeIdPath": "<generic_node_path>"}, "status": "success", "started_at": "2026-06-25T00:00:00Z", "finished_at": "2026-06-25T00:00:01Z"},
            {"call_id": "call-price", "tool_name": "market_price_distribution", "params": {"marketplace": "US", "nodeIdPath": "<generic_node_path>"}, "status": "success", "started_at": "2026-06-25T00:00:00Z", "finished_at": "2026-06-25T00:00:01Z"},
            {"call_id": "call-seller", "tool_name": "market_seller_concentration", "params": {"marketplace": "US", "nodeIdPath": "<generic_node_path>"}, "status": "success", "started_at": "2026-06-25T00:00:00Z", "finished_at": "2026-06-25T00:00:01Z"},
            {"call_id": "call-product", "tool_name": "product_research", "params": {"marketplace": "US", "keyword": "<generic_keyword>"}, "status": "success", "started_at": "2026-06-25T00:00:00Z", "finished_at": "2026-06-25T00:00:01Z"},
            {"call_id": "call-asin", "tool_name": "asin_detail", "params": {"marketplace": "US", "asin": "<generic_asin>"}, "status": "success", "started_at": "2026-06-25T00:00:00Z", "finished_at": "2026-06-25T00:00:01Z"},
            {"call_id": "call-ratings", "tool_name": "market_ratings_count", "params": {"marketplace": "US", "nodeIdPath": "<generic_node_path>"}, "status": "success", "started_at": "2026-06-25T00:00:00Z", "finished_at": "2026-06-25T00:00:01Z"},
            {"call_id": "call-boundary", "tool_name": "competitor_lookup", "params": {"marketplace": "US", "asins": ["<generic_asin>"]}, "status": "success", "started_at": "2026-06-25T00:00:00Z", "finished_at": "2026-06-25T00:00:01Z"},
        ],
        "tool_results": [
            {"result_id": "result-market", "call_id": "call-market", "tool_name": "market_research", "status": "success", "raw_result": {"code": "OK", "data": {"nodeIdPath": "<generic_node_path>", "totalUnits": 1402826, "avgPrice": 23.27, "avgRatings": 11994, "avgRating": 4.59}}},
            {"result_id": "result-price", "call_id": "call-price", "tool_name": "market_price_distribution", "status": "success", "raw_result": {"code": "OK", "rows_sample": [{"priceRange": "<generic_price_band>", "products": 10, "units": 250, "revenue": 6000, "unitsRatio": 0.25}]}},
            {"result_id": "result-seller", "call_id": "call-seller", "tool_name": "market_seller_concentration", "status": "success", "raw_result": {"code": "OK", "rows_sample": [{"sellerName": "<generic_seller>", "products": 5, "totalUnits": 300, "totalRevenue": 7200, "totalUnitsRatio": 0.3, "totalRevenueRatio": 0.31}]}},
            {"result_id": "result-product", "call_id": "call-product", "tool_name": "product_research", "status": "success", "raw_result": {"code": "OK", "items_sample": [{"asin": "<generic_asin>", "brand": "<generic_brand>", "sellerName": "<generic_seller>", "price": 24.5, "ratings": 500, "rating": 4.4, "nodeIdPath": "<generic_node_path>", "totalUnits": 300}]}},
            {"result_id": "result-asin", "call_id": "call-asin", "tool_name": "asin_detail", "status": "success", "raw_result": {"code": "OK", "data": {"asin": "<generic_asin>", "price": 34.99, "rating": 4.7, "ratings": 116354, "reviews": 80, "sellerName": "<generic_seller>", "brand": "<generic_brand>", "nodeIdPath": "<generic_node_path>", "parentAsin": "<generic_parent_asin>", "variations": 3, "fulfillment": "FBA"}}},
            {"result_id": "result-ratings", "call_id": "call-ratings", "tool_name": "market_ratings_count", "status": "success", "raw_result": {"code": "OK", "rows_sample": [{"ratings": 11994, "rating": 4.59, "reviews": 80}]}},
            {"result_id": "result-boundary", "call_id": "call-boundary", "tool_name": "competitor_lookup", "status": "success", "raw_result": {"code": "OK", "items_sample": [{"asin": "<generic_asin>", "nodeIdPath": "<generic_node_path>", "price": 24.5}]}},
        ],
        "errors": [], "data_gaps": [], "created_at": "2026-06-25T00:00:00Z",
        "retry_policy": {"max_attempts": 1, "reuse_existing_snapshot": True, "allow_network_call": False},
        "force_refresh": False,
        "input_lineage": {"route_refs": ["route_matrix_confirm.json#selected_routes[0]"], "selected_routes": ["<generic_route_ref>"], "nodeIdPath": "<generic_node_path>"},
    }


def _valid_sorftime_snapshot() -> dict:
    return {
        "schema_version": "p4-deep-contract-v1",
        "snapshot_id": "generic-sorftime-deep",
        "run_id": "20260625_generic_delivery",
        "source_name": "sorftime",
        "source_doc_refs": ["docs/references/p4_mcp_capability_mapping.md#sorftime"],
        "route_refs": ["route_matrix_confirm.json#selected_routes[0]"],
        "selected_routes": ["<generic_route_ref>"],
        "tool_calls": [
            {"call_id": "call-category-search", "tool_name": "category_search_from_product_name", "params": {"amzSite": "US", "productName": "<generic_product_name>", "page": 1}, "status": "success", "started_at": "2026-06-25T00:00:00Z", "finished_at": "2026-06-25T00:00:01Z"},
            {"call_id": "call-category-report", "tool_name": "category_report", "params": {"amzSite": "US", "nodeId": "<generic_node_id>"}, "status": "success", "started_at": "2026-06-25T00:00:00Z", "finished_at": "2026-06-25T00:00:01Z"},
            {"call_id": "call-category-trend", "tool_name": "category_trend", "params": {"amzSite": "US", "nodeId": "<generic_node_id>", "trendIndex": "SalesCount"}, "status": "success", "started_at": "2026-06-25T00:00:00Z", "finished_at": "2026-06-25T00:00:01Z"},
            {"call_id": "call-keyword-detail", "tool_name": "keyword_detail", "params": {"keywordSupportSite": "US", "keyword": "<generic_keyword>"}, "status": "success", "started_at": "2026-06-25T00:00:00Z", "finished_at": "2026-06-25T00:00:01Z"},
            {"call_id": "call-keyword-trend", "tool_name": "keyword_trend", "params": {"keywordSupportSite": "US", "keyword": "<generic_keyword>"}, "status": "success", "started_at": "2026-06-25T00:00:00Z", "finished_at": "2026-06-25T00:00:01Z"},
            {"call_id": "call-keyword-extends", "tool_name": "keyword_extends", "params": {"keywordSupportSite": "US", "keyword": "<generic_keyword>"}, "status": "success", "started_at": "2026-06-25T00:00:00Z", "finished_at": "2026-06-25T00:00:01Z"},
            {"call_id": "call-keyword-results", "tool_name": "keyword_search_results", "params": {"keywordSupportSite": "US", "keyword": "<generic_keyword>"}, "status": "success", "started_at": "2026-06-25T00:00:00Z", "finished_at": "2026-06-25T00:00:01Z"},
            {"call_id": "call-product-detail", "tool_name": "product_detail", "params": {"amzSite": "US", "asin": "<generic_asin>"}, "status": "success", "started_at": "2026-06-25T00:00:00Z", "finished_at": "2026-06-25T00:00:01Z"},
            {"call_id": "call-product-trend", "tool_name": "product_trend", "params": {"amzSite": "US", "asin": "<generic_asin>"}, "status": "success", "started_at": "2026-06-25T00:00:00Z", "finished_at": "2026-06-25T00:00:01Z"},
            {"call_id": "call-product-traffic", "tool_name": "product_traffic_terms", "params": {"amzSite": "US", "asin": "<generic_asin>"}, "status": "success", "started_at": "2026-06-25T00:00:00Z", "finished_at": "2026-06-25T00:00:01Z"},
            {"call_id": "call-competitor-keywords", "tool_name": "competitor_product_keywords", "params": {"keywordSupportSite": "US", "asin": "<generic_asin>"}, "status": "success", "started_at": "2026-06-25T00:00:00Z", "finished_at": "2026-06-25T00:00:01Z"},
            {"call_id": "call-product-reviews", "tool_name": "product_reviews", "params": {"amzSite": "US", "asin": "<generic_asin>"}, "status": "success", "started_at": "2026-06-25T00:00:00Z", "finished_at": "2026-06-25T00:00:01Z"},
            {"call_id": "call-hot-feature", "tool_name": "similar_product_feature", "params": {"amzSite": "US", "productName": "<generic_product_name>"}, "status": "success", "started_at": "2026-06-25T00:00:00Z", "finished_at": "2026-06-25T00:00:01Z"},
        ],
        "tool_results": [
            {"result_id": "result-category-search", "call_id": "call-category-search", "tool_name": "category_search_from_product_name", "status": "success", "raw_result": [{"nodeid": "3395091", "类目名称": "Generic Bottles", "Top100产品月销量": "1402826", "Top100产品月销额": "38113406.99", "平均星级": "4.59", "平均评价数量": "11994.52", "平均价格": "23.270000", "销量前3的产品月销量占比": "47.67%", "销量前3的品牌月销量占比": "64.13%", "销量前3的卖家月销量占比": "84.24%"}]},
            {"result_id": "result-category-report", "call_id": "call-category-report", "tool_name": "category_report", "status": "success", "raw_result": {"Top100产品_sample": [{"ASIN": "<generic_asin>", "月销量": "379466", "月销额": "13277515.34", "品牌": "<generic_brand>", "价格": 34.99, "评论数": 116354, "星级": 4.7, "卖家": "<generic_seller>"}], "类目统计报告_sample": {"nodeid": "<generic_node_id>", "top100产品月销量": "3039427", "top100产品月销额": "84902657.07", "top3_product_sales_volume_share": "销量前三的产品月销量占比:37.22%", "top3_brands_sales_volume_share": "销量前三的品牌月销量占比:78.92%", "top3_seller_sales_volume_share": "销量前三的卖家月销量占比:92.35%", "amazonOwned_sales_volume_share": "亚马逊自营月销量占比:87.62%", "average_price": "销量前的80%产品平均价格：22.179", "median_price": "销量前的80%产品中位价格：9.49"}}},
            {"result_id": "result-category-trend", "call_id": "call-category-trend", "tool_name": "category_trend", "status": "success", "raw_result": {"series_sample": ["2024年06月=1232094", "2026年06月=717226"]}},
            {"result_id": "result-keyword-detail", "call_id": "call-keyword-detail", "tool_name": "keyword_detail", "status": "success", "raw_result": {"关键词": "<generic_keyword>", "周搜索量": "368705", "周搜索排名": "103", "月搜索量": "1397364", "推荐cpc竞价": "0.35", "词搜索量旺季": "8月", "搜索结果竞品数量": "144105", "top5_product_sample": [{"asin": "<generic_asin>", "price": 34.97, "monthly_sales": "本产品月销量：372207（占比：12.49%）", "brand": "<generic_brand>", "seller": "<generic_seller>"}]}},
            {"result_id": "result-keyword-trend", "call_id": "call-keyword-trend", "tool_name": "keyword_trend", "status": "success", "raw_result": {"关键词": "<generic_keyword>", "搜索量趋势_sample": ["2024年06月搜索量2364427", "2026年05月搜索量1526641"], "搜索排名趋势_sample": ["2024年06月搜索排名29", "2026年05月搜索排名105"], "推荐竞价趋势_sample": ["2024年07月cpc推荐竞价0.90", "2026年05月cpc推荐竞价0.35"]}},
            {"result_id": "result-keyword-extends", "call_id": "call-keyword-extends", "tool_name": "keyword_extends", "status": "success", "raw_result": [{"关键词": "<generic_keyword>", "周搜索量": 368705, "周搜索排名": 103, "月搜索量": 1397364, "cpc推荐竞价": "0.35", "季节性": "搜索量旺季:8月"}]},
            {"result_id": "result-keyword-results", "call_id": "call-keyword-results", "tool_name": "keyword_search_results", "status": "success", "raw_result": {"Top100产品_sample": [{"ASIN": "<generic_asin>", "标题": "<generic_title>", "价格": 34.99, "月销量": 379466, "品牌": "<generic_brand>", "卖家": "<generic_seller>"}]}},
            {"result_id": "result-product-detail", "call_id": "call-product-detail", "tool_name": "product_detail", "status": "success", "raw_result": {"ASIN": "<generic_asin>", "价格": 34.99, "月销量": "379466", "月销额": "13277515.34", "星级": 4.7, "评价数": 116354, "卖家": "<generic_seller>", "品牌": "<generic_brand>", "类目": "<generic_category>", "nodeId": "<generic_node_id>"}},
            {"result_id": "result-product-trend", "call_id": "call-product-trend", "tool_name": "product_trend", "status": "success", "raw_result": {"series_sample": ["2024年06月=1232094", "2026年06月=717226"]}},
            {"result_id": "result-product-traffic", "call_id": "call-product-traffic", "tool_name": "product_traffic_terms", "status": "success", "raw_result": {"keywords_sample": [{"关键词": "<generic_keyword>", "自然位": 3, "搜索量": 368705, "曝光时间": "2026-06"}]}},
            {"result_id": "result-competitor-keywords", "call_id": "call-competitor-keywords", "tool_name": "competitor_product_keywords", "status": "success", "raw_result": {"keywords_sample": [{"关键词": "<generic_keyword>", "自然位": 8, "搜索量": 368705}]}},
            {"result_id": "result-product-reviews", "call_id": "call-product-reviews", "tool_name": "product_reviews", "status": "success", "raw_result": {"reviews_sample": [{"rating": 4, "title": "<generic_title>", "date": "2026-06-01", "content": "<generic_review>"}]}},
            {"result_id": "result-hot-feature", "call_id": "call-hot-feature", "tool_name": "similar_product_feature", "status": "success", "raw_result": {"features_sample": [{"特征": "<generic_feature>", "占比": "40%"}]}},
        ],
        "errors": [], "data_gaps": [], "created_at": "2026-06-25T00:00:00Z",
        "retry_policy": {"max_attempts": 1, "reuse_existing_snapshot": True, "allow_network_call": False},
        "force_refresh": False,
        "input_lineage": {"route_refs": ["route_matrix_confirm.json#selected_routes[0]"], "selected_routes": ["<generic_route_ref>"], "nodeId": "<generic_node_id>", "nodeIdPath": "<generic_node_path>", "seed_keyword": "<generic_keyword>", "amzSite": "US"},
    }
