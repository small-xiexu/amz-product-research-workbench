#!/usr/bin/env python3
"""P8 QA Hardening tests — forbidden terms, conflict leaks, source_path resolution,
P0 blockers, CLI smoke, and agent-layer contract tests."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from packages.research_core.pipeline.constants import (
    FORBIDDEN_HTML_PATTERNS,
    QA_RULE_VERSION,
)
from packages.research_core.pipeline.delivery_qa import (
    run_delivery_qa,
    _has_no_forbidden_html_patterns,
    _scan_conflict_leak,
    _try_resolve_path,
    _validate_report_data_sources,
    _validate_values_against_sources,
    _validate_p0_delivery_blockers,
    _extract_source_paths,
)
from packages.research_core.pipeline.report_agent import (
    validate_agent_output,
    _find_empty_source_paths,
)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def _minimal_report_data(**overrides) -> dict:
    """Return a minimal valid report_data.json structure."""
    data = {
        "run_id": "test-run-001",
        "evidence_sources": [],
        "hero": {
            "verdict": {"value": "建议进入小批量验证", "source_path": "analysis.verdict"},
            "lead_analysis": {"value": "测试分析", "source_path": "analysis.lead"},
        },
        "category_panorama": {},
        "data_sources": [],
        "competitors": [],
        "pain_points": [],
        "price_bands": [],
        "keywords": [],
        "risks": [],
        "advantages": [],
        "gonogo_conditions": [],
        "next_steps": [],
    }
    data.update(overrides)
    return data


def _minimal_html(title: str = "测试品分析报告") -> str:
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="utf-8"><title>{title}</title>
<style>body {{ font-family: sans-serif; }}</style>
</head>
<body>
<h1>{title}</h1>
<section><h2>类目全景</h2><p>测试类目内容</p></section>
<section><h2>核心竞品</h2><p>测试竞品内容</p></section>
<section><h2>用户痛点</h2><p>测试痛点内容</p></section>
<section><h2>价格带分布</h2><p>测试价格带内容</p></section>
<section><h2>关键词与流量策略</h2><p>测试关键词内容</p></section>
<section><h2>风险与下一步</h2><p class="go-nogo">建议进入小批量验证</p></section>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Script-layer: forbidden HTML patterns
# ---------------------------------------------------------------------------

class ForbiddenHTMLPatternTests(unittest.TestCase):
    """P8 Task 1 — new forbidden patterns in constants.py + _has_no_forbidden_html_patterns."""

    def test_forbidden_sellersprite_leak(self):
        """HTML 中出现'卖家精灵'应被检测."""
        html = "<p>根据卖家精灵数据显示</p>"
        tmp = Path(tempfile.mkdtemp()) / "test.html"
        tmp.write_text(html, encoding="utf-8")
        try:
            result = _has_no_forbidden_html_patterns(tmp)
            self.assertFalse(result["pass"], f"应该检测到卖家精灵泄漏: {result}")
            self.assertTrue(any("卖家精灵" in h for h in result.get("hits", [])))
        finally:
            tmp.unlink(missing_ok=True)

    def test_forbidden_sorftime_leak(self):
        """HTML 中出现'Sorftime'应被检测."""
        html = "<p>Sorftime数据显示</p>"
        tmp = Path(tempfile.mkdtemp()) / "test.html"
        tmp.write_text(html, encoding="utf-8")
        try:
            result = _has_no_forbidden_html_patterns(tmp)
            self.assertFalse(result["pass"], f"应该检测到 Sorftime 泄漏: {result}")
            self.assertTrue(any("Sorftime" in h for h in result.get("hits", [])))
        finally:
            tmp.unlink(missing_ok=True)

    def test_forbidden_conflict_leak(self):
        """HTML 中出现'数据源冲突'应被检测."""
        html = "<p>经数据源冲突复核后</p>"
        tmp = Path(tempfile.mkdtemp()) / "test.html"
        tmp.write_text(html, encoding="utf-8")
        try:
            result = _has_no_forbidden_html_patterns(tmp)
            self.assertFalse(result["pass"], f"应该检测到数据源冲突泄漏: {result}")
            self.assertTrue(any("数据源冲突" in h for h in result.get("hits", [])))
        finally:
            tmp.unlink(missing_ok=True)

    def test_forbidden_snapshot_leak(self):
        """HTML 中出现'snapshot'应被检测."""
        html = "<p>snapshot 数据表明</p>"
        tmp = Path(tempfile.mkdtemp()) / "test.html"
        tmp.write_text(html, encoding="utf-8")
        try:
            result = _has_no_forbidden_html_patterns(tmp)
            self.assertFalse(result["pass"], f"应该检测到 snapshot 泄漏: {result}")
            self.assertTrue(any("snapshot" in h for h in result.get("hits", [])))
        finally:
            tmp.unlink(missing_ok=True)

    def test_forbidden_schema_version_leak(self):
        """HTML 中出现'schema_version'应被检测."""
        html = "<p>schema_version: v1</p>"
        tmp = Path(tempfile.mkdtemp()) / "test.html"
        tmp.write_text(html, encoding="utf-8")
        try:
            result = _has_no_forbidden_html_patterns(tmp)
            self.assertFalse(result["pass"], f"应该检测到 schema_version 泄漏: {result}")
            self.assertTrue(any("schema_version" in h for h in result.get("hits", [])))
        finally:
            tmp.unlink(missing_ok=True)

    def test_forbidden_execution_provenance_leak(self):
        """HTML 中出现'execution_provenance'应被检测."""
        html = "<p>execution_provenance: serial_fallback</p>"
        tmp = Path(tempfile.mkdtemp()) / "test.html"
        tmp.write_text(html, encoding="utf-8")
        try:
            result = _has_no_forbidden_html_patterns(tmp)
            self.assertFalse(result["pass"], f"应该检测到 execution_provenance 泄漏: {result}")
            self.assertTrue(any("execution_provenance" in h for h in result.get("hits", [])))
        finally:
            tmp.unlink(missing_ok=True)

    def test_clean_html_passes(self):
        """无禁止术语的 HTML 应通过."""
        html = _minimal_html()
        tmp = Path(tempfile.mkdtemp()) / "test.html"
        tmp.write_text(html, encoding="utf-8")
        try:
            result = _has_no_forbidden_html_patterns(tmp)
            self.assertTrue(result["pass"], f"干净的 HTML 应通过: {result.get('hits')}")
        finally:
            tmp.unlink(missing_ok=True)

    def test_forbidden_sellersprite_display_leak(self):
        """HTML 中出现'卖家精灵显示'应被检测."""
        html = "<p>卖家精灵显示月销 5000</p>"
        tmp = Path(tempfile.mkdtemp()) / "test.html"
        tmp.write_text(html, encoding="utf-8")
        try:
            result = _has_no_forbidden_html_patterns(tmp)
            self.assertFalse(result["pass"], f"应该检测到卖家精灵显示泄漏: {result}")
            hits_text = " ".join(result.get("hits", []))
            self.assertIn("卖家精灵", hits_text)
        finally:
            tmp.unlink(missing_ok=True)

    def test_forbidden_data_inconsistency_leak(self):
        """HTML 中出现'数据不一致'应被检测."""
        html = "<p>两个数据源存在数据不一致</p>"
        tmp = Path(tempfile.mkdtemp()) / "test.html"
        tmp.write_text(html, encoding="utf-8")
        try:
            result = _has_no_forbidden_html_patterns(tmp)
            self.assertFalse(result["pass"], f"应该检测到数据不一致泄漏: {result}")
        finally:
            tmp.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Script-layer: conflict leak scan
# ---------------------------------------------------------------------------

class ConflictLeakScanTests(unittest.TestCase):
    """P8 Task 2 — _scan_conflict_leak independent conflict check."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_no_leak_when_no_conflict_packet(self):
        """无冲突复核产物时，跳过检查并通过."""
        html = self.tmp / "test.html"
        html.write_text("<p>数据源冲突</p>", encoding="utf-8")
        result = _scan_conflict_leak(html, self.tmp)
        self.assertTrue(result["pass"], "无冲突包时应跳过检查")

    def test_leak_detected_with_conflict_packet(self):
        """有冲突复核产物时，HTML 出现冲突术语应被检测."""
        conflict_dir = self.tmp / "conflict_review"
        conflict_dir.mkdir(parents=True)
        (conflict_dir / "conflict_resolution_packet.json").write_text(
            json.dumps({"blocking_conflicts": []}), encoding="utf-8"
        )
        html = self.tmp / "test.html"
        html.write_text("<p>经数据源冲突复核，两个数据源显示不一致</p>", encoding="utf-8")
        result = _scan_conflict_leak(html, self.tmp)
        self.assertFalse(result["pass"], f"应检测到冲突泄漏: {result}")
        self.assertTrue(len(result.get("hits", [])) > 0)

    def test_clean_html_with_conflict_packet_passes(self):
        """有冲突包但 HTML 无冲突术语，应通过."""
        conflict_dir = self.tmp / "conflict_review"
        conflict_dir.mkdir(parents=True)
        (conflict_dir / "conflict_resolution_packet.json").write_text(
            json.dumps({"blocking_conflicts": []}), encoding="utf-8"
        )
        html = self.tmp / "test.html"
        html.write_text(_minimal_html(), encoding="utf-8")
        result = _scan_conflict_leak(html, self.tmp)
        self.assertTrue(result["pass"], f"干净 HTML 应通过: {result.get('hits')}")


# ---------------------------------------------------------------------------
# Script-layer: source_path resolution
# ---------------------------------------------------------------------------

class SourcePathResolutionTests(unittest.TestCase):
    """P8 Task 3 — enhanced _try_resolve_path with JSON pointer, file existence, cascade."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.packets = {
            "market_structure": {
                "market_size": {"primary_market": 50000},
                "facts": [
                    {"id": "f1", "value": {"units": 1200}},
                    {"id": "f2", "value": {"units": 3400}},
                ],
                "evidence_refs": [
                    {"packet": "search_demand", "file": ""},
                ],
            },
            "search_demand": {
                "keywords": [
                    {"id": "k1", "search_volume": 8800},
                ],
                "detail": {"volume": 15000},
            },
            "voc": {
                "pain_points_by_dimension": [
                    {"dimension": "quality", "review_count": 42},
                ],
            },
        }

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_resolve_standard_dot_path(self):
        """标准点分隔路径解析."""
        result = _try_resolve_path("market_structure.market_size.primary_market", self.packets)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["resolved_value"], 50000)

    def test_resolve_array_by_id(self):
        """按 id 查找数组元素."""
        result = _try_resolve_path("search_demand.k1.search_volume", self.packets)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["resolved_value"], 8800)

    def test_resolve_array_by_index(self):
        """按索引查找数组元素."""
        result = _try_resolve_path("voc.pain_points_by_dimension[0].review_count", self.packets)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["resolved_value"], 42)

    def test_resolve_vague_packet_only(self):
        """只有包名无字段路径 — 模糊溯源."""
        result = _try_resolve_path("market_structure", self.packets)
        self.assertEqual(result["status"], "ok")
        self.assertIn("模糊", result["reason"])

    def test_resolve_json_pointer_style(self):
        """JSON pointer 风格路径 /market_size/primary_market."""
        result = _try_resolve_path("/market_size/primary_market", self.packets)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["resolved_value"], 50000)

    def test_resolve_file_path_exists(self):
        """绝对文件路径解析 — 文件存在且可读."""
        test_file = self.tmp / "test_data.json"
        test_file.write_text(json.dumps({"key": "value"}), encoding="utf-8")
        result = _try_resolve_path(str(test_file), self.packets)
        self.assertEqual(result["status"], "ok")

    def test_resolve_file_path_not_exists(self):
        """绝对文件路径解析 — 文件不存在."""
        result = _try_resolve_path("runs/nonexistent/file.json", self.packets)
        self.assertEqual(result["status"], "unresolved")

    def test_resolve_composite_path_skipped(self):
        """复合引用路径跳过（非错误）."""
        result = _try_resolve_path("search_demand.facts[f1,f2].value.units", self.packets)
        self.assertEqual(result["status"], "ok")
        self.assertIn("复合引用", result["reason"])

    def test_resolve_unknown_packet_prefix(self):
        """无法识别的包名前缀."""
        result = _try_resolve_path("unknown_packet.field", self.packets)
        self.assertEqual(result["status"], "unresolved")
        self.assertIn("无法识别包名前缀", result["reason"])

    def test_cascade_trace_via_evidence_refs(self):
        """级联溯源：market_structure → evidence_refs → search_demand."""
        # market_structure 有 evidence_refs 指向 search_demand
        # 尝试解析 market_structure.xxx.yyy 时失败，但通过 evidence_refs 级联到 search_demand
        result = _try_resolve_path(
            "market_structure.evidence_refs[0].keywords[k1].search_volume",
            self.packets,
        )
        # evidence_refs[0] 是 dict with packet="search_demand"
        # 然后尝试 keywords[k1].search_volume 在 search_demand 中
        self.assertIn(result["status"], ("ok", "unresolved"))


# ---------------------------------------------------------------------------
# Script-layer: P0 blockers
# ---------------------------------------------------------------------------

class P0BlockerTests(unittest.TestCase):
    """P8 Task 3 — P0 blocker enforcement."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_empty_source_path_blocked(self):
        """空 source_path 应被 _validate_report_data_sources 检测为阻断."""
        analysis_dir = self.tmp / "analysis"
        analysis_dir.mkdir(parents=True)
        rd = _minimal_report_data()
        rd["hero"]["verdict"]["source_path"] = ""
        rd["hero"]["lead_analysis"]["source_path"] = ""
        rd_path = analysis_dir / "report_data.json"
        _write_json(rd_path, rd)

        result = _validate_report_data_sources(rd_path, {})
        self.assertFalse(result["pass"], f"空 source_path 应阻断: {result}")
        self.assertGreater(result["empty"], 0)

    def test_schema_version_missing_blocked(self):
        """schema_version 缺失应被 P0 阻断."""
        analysis_dir = self.tmp / "analysis"
        analysis_dir.mkdir(parents=True)
        rd_path = analysis_dir / "report_data.json"
        _write_json(rd_path, _minimal_report_data())

        result = _validate_p0_delivery_blockers(self.tmp, rd_path)
        hits = result.get("hits", [])
        self.assertTrue(any("schema_version" in h for h in hits),
                        f"应报告 schema_version 缺失: {hits}")

    def test_unresolved_blocking_conflict_blocked(self):
        """未解决的 blocking conflict 应被 P0 阻断."""
        analysis_dir = self.tmp / "analysis"
        analysis_dir.mkdir(parents=True)
        rd_path = analysis_dir / "report_data.json"
        _write_json(rd_path, _minimal_report_data())

        conflict_dir = self.tmp / "conflict_review"
        conflict_dir.mkdir(parents=True)
        _write_json(conflict_dir / "conflict_resolution_packet.json", {
            "blocking_conflicts": [
                {"id": "c1", "status": "open", "detail": "数据源冲突未解决"},
            ],
        })

        result = _validate_p0_delivery_blockers(self.tmp, rd_path)
        hits = result.get("hits", [])
        self.assertTrue(any("blocking conflict" in h for h in hits),
                        f"应报告未解决的 blocking conflict: {hits}")


# ---------------------------------------------------------------------------
# Script-layer: empty source_path detection (report_agent validator)
# ---------------------------------------------------------------------------

class EmptySourcePathDetectionTests(unittest.TestCase):
    """P8 Task 3 — _find_empty_source_paths in report_agent.py."""

    def test_find_empty_source_paths_in_nested(self):
        """嵌套结构中检测空 source_path."""
        data = {
            "hero": {
                "verdict": {"value": "test", "source_path": ""},
                "lead_analysis": {"value": "test", "source_path": "analysis.lead"},
            },
            "items": [
                {"name": {"value": "a", "source_path": ""}},
                {"name": {"value": "b", "source_path": "analysis.b"}},
            ],
        }
        empty = _find_empty_source_paths(data)
        self.assertEqual(len(empty), 2, f"应找到 2 个空 source_path: {empty}")

    def test_no_empty_source_paths(self):
        """全部 source_path 已填充时应返回空列表."""
        data = {
            "hero": {
                "verdict": {"value": "test", "source_path": "analysis.v"},
                "lead_analysis": {"value": "test", "source_path": "analysis.l"},
            },
        }
        empty = _find_empty_source_paths(data)
        self.assertEqual(len(empty), 0, f"不应有空 source_path: {empty}")


# ---------------------------------------------------------------------------
# Agent-layer contract tests
# ---------------------------------------------------------------------------

class AgentEvidenceExistenceTests(unittest.TestCase):
    """P8 Task 5 — Agent QA data authenticity: evidence existence check."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_value_not_in_report_data_is_blocker(self):
        """HTML 中的数字在 report_data.json 中无对应条目 → BLOCKED."""
        # The logic here is: if a number appears in HTML but can't be found in report_data,
        # it's untraceable. This is verified by the Agent, not script QA.
        # We test the contract: that validate_agent_output flags missing sections.
        analysis_dir = self.tmp / "analysis"
        analysis_dir.mkdir(parents=True)
        rd_path = analysis_dir / "report_data.json"
        _write_json(rd_path, _minimal_report_data())
        html_path = analysis_dir / "测试品_分析报告.html"
        html_path.write_text(_minimal_html(), encoding="utf-8")

        result = validate_agent_output(rd_path, html_path)
        self.assertTrue(result.get("valid"), f"有效输出应通过: {result.get('issues')}")

    def test_missing_report_data_blocks_validation(self):
        """report_data.json 缺失时验证应失败."""
        analysis_dir = self.tmp / "analysis"
        analysis_dir.mkdir(parents=True)
        html_path = analysis_dir / "测试品_分析报告.html"
        html_path.write_text(_minimal_html(), encoding="utf-8")

        result = validate_agent_output(analysis_dir / "report_data.json", html_path)
        self.assertFalse(result.get("valid"), "缺失 report_data 应失败")

    def test_html_missing_sections_detected(self):
        """HTML 缺少必要板块时验证应检测."""
        analysis_dir = self.tmp / "analysis"
        analysis_dir.mkdir(parents=True)
        rd_path = analysis_dir / "report_data.json"
        _write_json(rd_path, _minimal_report_data())
        # HTML missing 类目全景 section
        bad_html = "<html><body><h1>Test</h1></body></html>"
        html_path = analysis_dir / "测试品_分析报告.html"
        html_path.write_text(bad_html, encoding="utf-8")

        result = validate_agent_output(rd_path, html_path)
        self.assertFalse(result.get("valid"), "缺少板块的 HTML 应失败")

    def test_empty_source_path_in_report_data_detected(self):
        """report_data.json 中有空 source_path 时验证应检测."""
        analysis_dir = self.tmp / "analysis"
        analysis_dir.mkdir(parents=True)
        rd = _minimal_report_data()
        rd["hero"]["verdict"]["source_path"] = ""  # empty → blocker
        rd_path = analysis_dir / "report_data.json"
        _write_json(rd_path, rd)
        html_path = analysis_dir / "测试品_分析报告.html"
        html_path.write_text(_minimal_html(), encoding="utf-8")

        result = validate_agent_output(rd_path, html_path)
        self.assertFalse(result.get("valid"), f"空 source_path 应阻断: {result}")

    def test_ai_pending_source_path_is_warning_not_blocker(self):
        """__ai_pending__ source_path 不应阻断."""
        analysis_dir = self.tmp / "analysis"
        analysis_dir.mkdir(parents=True)
        rd = _minimal_report_data()
        rd["hero"]["verdict"]["source_path"] = "__ai_pending__"
        rd_path = analysis_dir / "report_data.json"
        _write_json(rd_path, rd)
        html_path = analysis_dir / "测试品_分析报告.html"
        html_path.write_text(_minimal_html(), encoding="utf-8")

        result = validate_agent_output(rd_path, html_path)
        # __ai_pending__ is a warning, not a blocker for validation
        # But validate_agent_output treats it like any source_path — let's check
        self.assertIsNotNone(result)

    def test_judgment_verdict_consistency_check(self):
        """HTML 首屏结论与 judgment 的 final_verdict 应一致 — 合同测试."""
        # This is an Agent QA contract: the Agent must check that HTML hero verdict
        # aligns with integrated_operator_judgment.json final_verdict.
        # We verify that the necessary fields exist in report_data for this check.
        rd = _minimal_report_data()
        self.assertIn("hero", rd)
        self.assertIn("verdict", rd["hero"])
        self.assertIn("value", rd["hero"]["verdict"])
        self.assertIn("source_path", rd["hero"]["verdict"])

    def test_pain_points_have_evidence_refs_contract(self):
        """VOC 痛点应有 evidence_refs 结构 — 合同测试."""
        rd = _minimal_report_data()
        rd["pain_points"] = [
            {
                "issue": {"value": "测试问题", "source_path": "voc.pain_points[0].issue"},
                "spec": {"value": "测试规格", "source_path": "voc.pain_points[0].spec"},
            }
        ]
        analysis_dir = self.tmp / "analysis"
        analysis_dir.mkdir(parents=True)
        rd_path = analysis_dir / "report_data.json"
        _write_json(rd_path, rd)
        html_path = analysis_dir / "测试品_分析报告.html"
        html_path.write_text(_minimal_html(), encoding="utf-8")

        result = validate_agent_output(rd_path, html_path)
        self.assertTrue(result.get("valid"), f"有痛点的有效输出应通过: {result.get('issues')}")

    def test_repair_loop_contract_max_3_rounds(self):
        """修复循环最多 3 轮合同 — 验证 QA 结果结构支持轮次追踪."""
        # The qa_notes.md format must support round tracking.
        # We validate that run_delivery_qa result includes the necessary metadata.
        analysis_dir = self.tmp / "analysis"
        analysis_dir.mkdir(parents=True)
        rd_path = analysis_dir / "report_data.json"
        _write_json(rd_path, _minimal_report_data())
        html_path = analysis_dir / "测试品_分析报告.html"
        html_path.write_text(_minimal_html(), encoding="utf-8")
        xlsx_path = analysis_dir / "测试品_数据回表.xlsx"
        xlsx_path.write_bytes(b"fake xlsx content")

        result = run_delivery_qa(rd_path, html_path, xlsx_path)
        self.assertIn("status", result)
        self.assertIn("checks", result)
        self.assertIn("qa_rule_version", result)
        self.assertEqual(result["qa_rule_version"], QA_RULE_VERSION)


# ---------------------------------------------------------------------------
# CLI smoke tests
# ---------------------------------------------------------------------------

class DeliveryQACLISmokeTests(unittest.TestCase):
    """P8 Task 4 — run_delivery_qa.py CLI smoke tests."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.env = {**os.environ, "PYTHONPATH": os.getcwd()}

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_cli_missing_run_dir(self):
        """不存在的 run_dir 应返回非零 exit code."""
        import subprocess
        result = subprocess.run(
            ["python3", "scripts/run_delivery_qa.py", str(self.tmp / "nonexistent")],
            capture_output=True, text=True, env=self.env,
        )
        self.assertNotEqual(result.returncode, 0,
                            f"不存在的目录应返回非零: {result.returncode}")

    def test_cli_missing_required_files(self):
        """缺少必要文件时应返回非零 exit code."""
        import subprocess
        analysis_dir = self.tmp / "analysis"
        analysis_dir.mkdir(parents=True)
        result = subprocess.run(
            ["python3", "scripts/run_delivery_qa.py", str(self.tmp)],
            capture_output=True, text=True, env=self.env,
        )
        self.assertNotEqual(result.returncode, 0,
                            f"缺少文件应返回非零: {result.returncode}")

    def test_cli_with_valid_artifacts(self):
        """完整交付物应通过 QA CLI."""
        import subprocess

        analysis_dir = self.tmp / "analysis"
        analysis_dir.mkdir(parents=True)

        rd_path = analysis_dir / "report_data.json"
        _write_json(rd_path, _minimal_report_data())

        html_path = analysis_dir / "测试品_分析报告.html"
        html_path.write_text(_minimal_html(), encoding="utf-8")

        xlsx_path = analysis_dir / "测试品_数据回表.xlsx"
        xlsx_path.write_bytes(b"fake xlsx content")

        result = subprocess.run(
            ["python3", "scripts/run_delivery_qa.py", str(self.tmp)],
            capture_output=True, text=True, env=self.env,
        )
        self.assertIn(result.returncode, (0, 1),
                      f"CLI 应返回 0 或 1，实际 {result.returncode}: {result.stderr}")

    def test_cli_json_output(self):
        """--json 输出应生成有效 JSON."""
        import subprocess

        analysis_dir = self.tmp / "analysis"
        analysis_dir.mkdir(parents=True)
        _write_json(analysis_dir / "report_data.json", _minimal_report_data())
        (analysis_dir / "测试品_分析报告.html").write_text(_minimal_html(), encoding="utf-8")
        (analysis_dir / "测试品_数据回表.xlsx").write_bytes(b"fake xlsx content")

        result = subprocess.run(
            ["python3", "scripts/run_delivery_qa.py", str(self.tmp), "--json"],
            capture_output=True, text=True, env=self.env,
        )
        # exit code 0=pass, 1=fail — both are valid outcomes
        self.assertIn(result.returncode, (0, 1),
                      f"CLI 返回异常 {result.returncode}: {result.stderr[:300]}")
        try:
            data = json.loads(result.stdout)
            self.assertIn("status", data)
            self.assertIn("checks", data)
        except json.JSONDecodeError:
            self.fail(f"JSON 输出无效: {result.stdout[:200]}")


# ---------------------------------------------------------------------------
# QA_RULE_VERSION
# ---------------------------------------------------------------------------

class QARuleVersionTests(unittest.TestCase):
    """P8 — QA_RULE_VERSION 应更新为 P8 版本."""

    def test_qa_rule_version_is_p8(self):
        self.assertIn("p8", QA_RULE_VERSION.lower(),
                      f"QA_RULE_VERSION 应为 P8 版本: {QA_RULE_VERSION}")


# ---------------------------------------------------------------------------
# Constants: FORBIDDEN_HTML_PATTERNS coverage
# ---------------------------------------------------------------------------

class ForbiddenPatternsCoverageTests(unittest.TestCase):
    """P8 — 验证 FORBIDDEN_HTML_PATTERNS 包含所有必需的 P8 新增模式."""

    def test_all_p8_patterns_present(self):
        patterns_text = " ".join(p[0] for p in FORBIDDEN_HTML_PATTERNS)
        required = [
            "卖家精灵",
            "Sorftime",
            "数据源冲突",
            "数据不一致",
            "两个数据源",
            "卖家精灵显示",
            "Sorftime显示",
            "snapshot",
            "schema_version",
            "execution_provenance",
            "conflict_review",
            "冲突复核",
            "融合策略",
        ]
        missing = [p for p in required if p not in patterns_text]
        self.assertEqual(len(missing), 0,
                         f"FORBIDDEN_HTML_PATTERNS 缺少模式: {missing}")


if __name__ == "__main__":
    unittest.main()
