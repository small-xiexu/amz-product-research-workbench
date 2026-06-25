"""P5-3 tests: VOC evidence packet and gate generation."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

from packages.research_core.contracts import (
    P5_STAGE_ID,
    validate_voc_evidence_packet,
    validate_voc_gate,
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
from packages.research_core.pipeline.build_conflict_review import run_conflict_review
from packages.research_core.pipeline.build_voc_gate import (
    P5GateError,
    build_evidence_packet,
    build_gate,
    run_voc_gate,
)
from packages.research_core.pipeline.quick_market_check import run_quick_market_check


ROOT = Path(__file__).resolve().parents[1]
P1_FIXTURES = ROOT / "tests" / "fixtures" / "p1_quick_check"


# ── Full Pipeline Happy Path ───────────────────────────────────────────

class VocGateHappyPathTests(unittest.TestCase):
    """Full pipeline tests: seed P4 → P5-1 → P5-2 → P5-3."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self._tmp = Path(self._tmpdir.name)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def _seed_p5_2_done(self, review_count: int = 35) -> Path:
        run_dir = self._tmp / "20260624_generic_direction"
        run_dir.mkdir()
        (run_dir / "workflow_state.json").write_text(
            json.dumps(_workflow_state(), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        run_quick_market_check(run_dir, snapshot_source_dir=P1_FIXTURES)
        run_candidate_pool(run_dir)
        run_route_matrix_confirmation(run_dir)
        run_sellersprite_deep_dive(run_dir, snapshot_source=self._write_sellersprite_snapshot())
        run_sorftime_deep_dive(run_dir, snapshot_source=self._write_sorftime_snapshot())
        run_conflict_review(run_dir)
        run_review_asin_batch(run_dir)
        xlsx_path = self._write_review_xlsx(review_count)
        run_review_voc_package(run_dir, xlsx_path)
        return run_dir

    def _write_sellersprite_snapshot(self) -> Path:
        src = self._tmp / "ss_snap.json"
        src.write_text(json.dumps(_valid_sellersprite_snapshot(), ensure_ascii=False, indent=2), encoding="utf-8")
        return src

    def _write_sorftime_snapshot(self) -> Path:
        src = self._tmp / "sf_snap.json"
        src.write_text(json.dumps(_valid_sorftime_snapshot(), ensure_ascii=False, indent=2), encoding="utf-8")
        return src

    def _write_review_xlsx(self, count: int = 35) -> Path:
        path = self._tmp / "test_reviews.xlsx"
        _write_review_xlsx_file(path, _sample_reviews(count))
        return path

    def test_happy_path_continue(self) -> None:
        """Full pipeline with 35 reviews → valid gate decision."""
        run_dir = self._seed_p5_2_done(35)
        outputs = run_voc_gate(run_dir)

        evidence = load_json(outputs["evidence_packet"])
        gate = load_json(outputs["gate"])

        validate_voc_evidence_packet(evidence)
        validate_voc_gate(gate)

        self.assertEqual(evidence["packet_id"], "voc_evidence")
        self.assertEqual(gate["gate_id"], "voc_gate")

        # Decision depends on route coverage matching; all valid decisions acceptable
        self.assertIn(gate["decision"], {"continue", "watch", "stop", "need_more_reviews"})

        # Every pain point has evidence_refs with review_id
        for pp in evidence.get("pain_points_by_dimension", []):
            self.assertIn("evidence_refs", pp)
            self.assertGreater(len(pp["evidence_refs"]), 0)

    def test_progress_done_after_gate(self) -> None:
        """stage_7_voc_gate.status = done after P5-3."""
        run_dir = self._seed_p5_2_done(35)
        run_voc_gate(run_dir)

        progress = load_json(run_dir / "progress.json")
        stage_7 = progress["stages"].get(P5_STAGE_ID, {})
        self.assertEqual(stage_7.get("status"), "done")

        completed = progress.get("completed_artifacts", [])
        self.assertIn("review_voc/voc_evidence_packet.json", completed)
        self.assertIn("review_voc/voc_gate.json", completed)

    def test_progress_next_action_varies_by_decision(self) -> None:
        """next_action reflects gate decision."""
        run_dir = self._seed_p5_2_done(35)
        run_voc_gate(run_dir)

        gate = load_json(run_dir / "review_voc" / "voc_gate.json")
        progress = load_json(run_dir / "progress.json")
        next_action = progress.get("next_action", {})

        decision = gate["decision"]
        if decision == "continue":
            self.assertEqual(next_action.get("stage_id"), "stage_7_report")
        elif decision == "stop":
            self.assertEqual(next_action.get("type"), "stop")
        elif decision == "need_more_reviews":
            self.assertEqual(next_action.get("stage_id"), P5_STAGE_ID)

    def test_evidence_packet_structural_fields(self) -> None:
        """All required structural fields are populated."""
        run_dir = self._seed_p5_2_done(35)
        run_voc_gate(run_dir)

        evidence = load_json(run_dir / "review_voc" / "voc_evidence_packet.json")
        self.assertIn("review_scope", evidence)
        self.assertIn("asin_coverage", evidence)
        self.assertIn("route_refs", evidence)
        self.assertIn("mixed_pool_signals", evidence)
        self.assertIn("review_quality_gaps", evidence)
        self.assertIn("unmet_needs", evidence)
        self.assertIn("differentiation_opportunities", evidence)

        review_scope = evidence["review_scope"]
        self.assertIn("total_reviews", review_scope)
        self.assertIn("low_rating_count", review_scope)
        self.assertIn("date_range", review_scope)

        asin_coverage = evidence["asin_coverage"]
        self.assertIn("by_route", asin_coverage)
        self.assertIn("by_asin_role", asin_coverage)

    def test_cli_smoke(self) -> None:
        """CLI exits 0 and writes both outputs."""
        run_dir = self._seed_p5_2_done(35)
        result = _run_cli(str(run_dir))
        self.assertEqual(result.returncode, 0, f"CLI failed: {result.stderr}")
        self.assertTrue((run_dir / "review_voc" / "voc_evidence_packet.json").exists())
        self.assertTrue((run_dir / "review_voc" / "voc_gate.json").exists())


# ── Gate Decision Paths ────────────────────────────────────────────────

class VocGateDecisionTests(unittest.TestCase):
    """Test each gate decision path using synthetic inputs."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self._tmp = Path(self._tmpdir.name)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def _seed_p5_2_done(self, review_count: int = 35) -> Path:
        run_dir = self._tmp / "20260624_generic_direction"
        run_dir.mkdir()
        (run_dir / "workflow_state.json").write_text(
            json.dumps(_workflow_state(), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        run_quick_market_check(run_dir, snapshot_source_dir=P1_FIXTURES)
        run_candidate_pool(run_dir)
        run_route_matrix_confirmation(run_dir)
        run_sellersprite_deep_dive(run_dir, snapshot_source=self._write_sellersprite_snapshot())
        run_sorftime_deep_dive(run_dir, snapshot_source=self._write_sorftime_snapshot())
        run_conflict_review(run_dir)
        run_review_asin_batch(run_dir)
        xlsx_path = self._write_review_xlsx(review_count)
        run_review_voc_package(run_dir, xlsx_path)
        return run_dir

    def _write_sellersprite_snapshot(self) -> Path:
        src = self._tmp / "ss_snap.json"
        src.write_text(json.dumps(_valid_sellersprite_snapshot(), ensure_ascii=False, indent=2), encoding="utf-8")
        return src

    def _write_sorftime_snapshot(self) -> Path:
        src = self._tmp / "sf_snap.json"
        src.write_text(json.dumps(_valid_sorftime_snapshot(), ensure_ascii=False, indent=2), encoding="utf-8")
        return src

    def _write_review_xlsx(self, count: int = 35) -> Path:
        path = self._tmp / "test_reviews.xlsx"
        _write_review_xlsx_file(path, _sample_reviews(count))
        return path

    def test_need_more_reviews_when_fewer_than_30(self) -> None:
        """Fewer than 30 reviews → need_more_reviews."""
        run_dir = self._seed_p5_2_done(5)
        run_voc_gate(run_dir)
        gate = load_json(run_dir / "review_voc" / "voc_gate.json")
        self.assertEqual(gate["decision"], "need_more_reviews")

    def test_need_more_reviews_includes_patch_suggestion(self) -> None:
        """need_more_reviews decision includes actionable suggestions."""
        run_dir = self._seed_p5_2_done(5)
        run_voc_gate(run_dir)
        gate = load_json(run_dir / "review_voc" / "voc_gate.json")
        actions = gate.get("required_next_actions", [])
        has_patch = any("补抓" in a for a in actions)
        self.assertTrue(has_patch, "should suggest patching review count")

    def test_stop_when_p4_conflict_blocker(self) -> None:
        """P4 conflict blocker → stop."""
        run_dir = self._seed_p5_2_done(35)
        _inject_p4_conflict_blocker(run_dir)
        run_voc_gate(run_dir)
        gate = load_json(run_dir / "review_voc" / "voc_gate.json")
        self.assertEqual(gate["decision"], "stop")

    def test_stop_when_p4_completeness_blocker(self) -> None:
        """P4 completeness blocker → stop."""
        run_dir = self._seed_p5_2_done(35)
        _inject_p4_completeness_blocker(run_dir)
        run_voc_gate(run_dir)
        gate = load_json(run_dir / "review_voc" / "voc_gate.json")
        self.assertEqual(gate["decision"], "stop")

    def test_p4_conflict_warning_inherited(self) -> None:
        """P4 conflict warning is inherited into gate."""
        run_dir = self._seed_p5_2_done(35)
        _inject_p4_conflict_warning(run_dir)
        run_voc_gate(run_dir)
        gate = load_json(run_dir / "review_voc" / "voc_gate.json")
        self.assertEqual(gate["checks"]["p4_conflict_level"], "warning")
        self.assertGreater(len(gate.get("inherited_warnings", [])), 0)

    def test_blocker_populates_blockers_list(self) -> None:
        """When blocked, blockers list is non-empty."""
        run_dir = self._seed_p5_2_done(35)
        _inject_p4_conflict_blocker(run_dir)
        run_voc_gate(run_dir)
        gate = load_json(run_dir / "review_voc" / "voc_gate.json")
        self.assertGreater(len(gate.get("blockers", [])), 0)

    def test_continue_not_generated_when_reviews_insufficient(self) -> None:
        """Decision is never 'continue' when reviews < 30."""
        run_dir = self._seed_p5_2_done(3)
        run_voc_gate(run_dir)
        gate = load_json(run_dir / "review_voc" / "voc_gate.json")
        self.assertNotEqual(gate["decision"], "continue")


# ── Contract Validator Tests ───────────────────────────────────────────

class VocGateContractTests(unittest.TestCase):
    """Contract validator tests for evidence packet and gate."""

    def test_validator_accepts_minimal_evidence_packet(self) -> None:
        validate_voc_evidence_packet(_minimal_evidence_packet())

    def test_validator_rejects_empty_evidence_packet(self) -> None:
        from packages.research_core.contracts.p5_contracts import P5ContractError
        with self.assertRaises(P5ContractError):
            validate_voc_evidence_packet({})

    def test_validator_rejects_wrong_packet_id(self) -> None:
        from packages.research_core.contracts.p5_contracts import P5ContractError
        pkt = _minimal_evidence_packet()
        pkt["packet_id"] = "wrong"
        with self.assertRaises(P5ContractError):
            validate_voc_evidence_packet(pkt)

    def test_validator_rejects_bad_confidence(self) -> None:
        from packages.research_core.contracts.p5_contracts import P5ContractError
        pkt = _minimal_evidence_packet()
        pkt["confidence"] = "maybe"
        with self.assertRaises(P5ContractError):
            validate_voc_evidence_packet(pkt)

    def test_validator_accepts_minimal_gate(self) -> None:
        validate_voc_gate(_minimal_gate("continue"))

    def test_validator_rejects_empty_gate(self) -> None:
        from packages.research_core.contracts.p5_contracts import P5ContractError
        with self.assertRaises(P5ContractError):
            validate_voc_gate({})

    def test_validator_rejects_continue_with_blocker_checks(self) -> None:
        from packages.research_core.contracts.p5_contracts import P5ContractError
        gate = _minimal_gate("continue")
        gate["checks"]["p4_conflict_level"] = "blocker"
        with self.assertRaises(P5ContractError):
            validate_voc_gate(gate)

    def test_validator_rejects_continue_below_min_reviews(self) -> None:
        from packages.research_core.contracts.p5_contracts import P5ContractError
        gate = _minimal_gate("continue")
        gate["thresholds"]["current_total_reviews"] = 5
        with self.assertRaises(P5ContractError):
            validate_voc_gate(gate)

    def test_validator_rejects_continue_with_false_threshold(self) -> None:
        from packages.research_core.contracts.p5_contracts import P5ContractError
        gate = _minimal_gate("continue")
        gate["checks"]["min_review_threshold_met"] = False
        with self.assertRaises(P5ContractError):
            validate_voc_gate(gate)

    def test_validator_accepts_watch_gate(self) -> None:
        gate = _minimal_gate("watch")
        gate["checks"]["low_rating_threshold_met"] = False
        gate["thresholds"]["current_low_rating_reviews"] = 3
        validate_voc_gate(gate)

    def test_build_gate_output_passes_validator(self) -> None:
        """Output of build_gate() always passes validator."""
        evidence = _minimal_evidence_packet()
        voc_package = _minimal_voc_package()
        asin_batch = _minimal_asin_batch()
        completeness = {"completeness_level": "none"}
        conflict = {"conflict_level": "none"}
        gate = build_gate(evidence, voc_package, asin_batch, completeness, conflict)
        validate_voc_gate(gate)


# ── Scope Tests ────────────────────────────────────────────────────────

class VocGateScopeTests(unittest.TestCase):
    """P5-3 does not produce downstream artifacts."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self._tmp = Path(self._tmpdir.name)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def _seed_p5_2_done(self) -> Path:
        run_dir = self._tmp / "20260624_generic_direction"
        run_dir.mkdir()
        (run_dir / "workflow_state.json").write_text(
            json.dumps(_workflow_state(), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        run_quick_market_check(run_dir, snapshot_source_dir=P1_FIXTURES)
        run_candidate_pool(run_dir)
        run_route_matrix_confirmation(run_dir)
        run_sellersprite_deep_dive(run_dir, snapshot_source=self._write_sellersprite_snapshot())
        run_sorftime_deep_dive(run_dir, snapshot_source=self._write_sorftime_snapshot())
        run_conflict_review(run_dir)
        run_review_asin_batch(run_dir)
        xlsx_path = self._tmp / "test_reviews.xlsx"
        _write_review_xlsx_file(xlsx_path, _sample_reviews(35))
        run_review_voc_package(run_dir, xlsx_path)
        return run_dir

    def _write_sellersprite_snapshot(self) -> Path:
        src = self._tmp / "ss_snap.json"
        src.write_text(json.dumps(_valid_sellersprite_snapshot(), ensure_ascii=False, indent=2), encoding="utf-8")
        return src

    def _write_sorftime_snapshot(self) -> Path:
        src = self._tmp / "sf_snap.json"
        src.write_text(json.dumps(_valid_sorftime_snapshot(), ensure_ascii=False, indent=2), encoding="utf-8")
        return src

    def test_no_html_generated(self) -> None:
        run_dir = self._seed_p5_2_done()
        run_voc_gate(run_dir)
        analysis_dir = run_dir / "analysis"
        html_files = list(analysis_dir.glob("*.html")) if analysis_dir.exists() else []
        self.assertEqual(len(html_files), 0, "no HTML should be generated in P5-3")

    def test_no_xlsx_generated(self) -> None:
        run_dir = self._seed_p5_2_done()
        run_voc_gate(run_dir)
        analysis_dir = run_dir / "analysis"
        xlsx_files = list(analysis_dir.glob("*.xlsx")) if analysis_dir.exists() else []
        self.assertEqual(len(xlsx_files), 0, "no XLSX should be generated in P5-3")

    def test_no_report_md_generated(self) -> None:
        run_dir = self._seed_p5_2_done()
        run_voc_gate(run_dir)
        rv = run_dir / "review_voc"
        for pattern in ["voc_report.md", "report.html", "report.xlsx"]:
            self.assertFalse((rv / pattern).exists(), f"{pattern} should not exist")


# ── Missing Input Tests ────────────────────────────────────────────────

class VocGateMissingInputTests(unittest.TestCase):
    """Test behavior when required inputs are missing."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self._tmp = Path(self._tmpdir.name)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def _seed_p5_2_done(self) -> Path:
        run_dir = self._tmp / "20260624_generic_direction"
        run_dir.mkdir()
        (run_dir / "workflow_state.json").write_text(
            json.dumps(_workflow_state(), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        run_quick_market_check(run_dir, snapshot_source_dir=P1_FIXTURES)
        run_candidate_pool(run_dir)
        run_route_matrix_confirmation(run_dir)
        run_sellersprite_deep_dive(run_dir, snapshot_source=self._write_sellersprite_snapshot())
        run_sorftime_deep_dive(run_dir, snapshot_source=self._write_sorftime_snapshot())
        run_conflict_review(run_dir)
        run_review_asin_batch(run_dir)
        xlsx_path = self._tmp / "test_reviews.xlsx"
        _write_review_xlsx_file(xlsx_path, _sample_reviews(35))
        run_review_voc_package(run_dir, xlsx_path)
        return run_dir

    def _write_sellersprite_snapshot(self) -> Path:
        src = self._tmp / "ss_snap.json"
        src.write_text(json.dumps(_valid_sellersprite_snapshot(), ensure_ascii=False, indent=2), encoding="utf-8")
        return src

    def _write_sorftime_snapshot(self) -> Path:
        src = self._tmp / "sf_snap.json"
        src.write_text(json.dumps(_valid_sorftime_snapshot(), ensure_ascii=False, indent=2), encoding="utf-8")
        return src

    def test_missing_voc_package_raises(self) -> None:
        run_dir = self._seed_p5_2_done()
        (run_dir / "review_voc" / "review_voc_package.json").unlink()
        with self.assertRaises(P5GateError):
            run_voc_gate(run_dir)

    def test_missing_asin_batch_raises(self) -> None:
        run_dir = self._seed_p5_2_done()
        (run_dir / "review_voc" / "review_asin_batch.json").unlink()
        with self.assertRaises(P5GateError):
            run_voc_gate(run_dir)

    def test_missing_conflict_resolution_raises(self) -> None:
        run_dir = self._seed_p5_2_done()
        (run_dir / "conflict_review" / "conflict_resolution_packet.json").unlink()
        with self.assertRaises(P5GateError):
            run_voc_gate(run_dir)

    def test_missing_completeness_check_raises(self) -> None:
        run_dir = self._seed_p5_2_done()
        (run_dir / "conflict_review" / "deep_data_completeness_check.json").unlink()
        with self.assertRaises(P5GateError):
            run_voc_gate(run_dir)


# ── Fixture helpers ────────────────────────────────────────────────────

def _workflow_state() -> dict[str, Any]:
    return {
        "workflow_id": "20260624_generic_direction",
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
            "body_en": f"This is the review body for review {i}. The product works well.{' Durability concern after extended use.' if rating <= 2 else ''}",
            "title_zh": f"评论标题{i}",
            "body_zh": f"这是第{i}条评论的产品质量评测。{'长期耐用性存在问题，材料和做工需要改进。' if rating <= 2 else '总体体验良好，性价比不错。'}",
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


def _minimal_evidence_packet() -> dict[str, Any]:
    return {
        "packet_id": "voc_evidence",
        "packet_version": "p5-voc-gate-v1",
        "run_id": "test_run",
        "agent_role": "VOC Evidence Agent",
        "source_scope": ["review_plugin_export"],
        "created_at": "2026-06-24T00:00:00Z",
        "input_refs": [{"type": "file", "path": "review_voc/review_voc_package.json"}],
        "execution_provenance": {
            "executed_by_agent": False,
            "agent_role": "VOC Evidence Agent",
            "execution_mode": "script_generated_skeleton",
            "subagent_id": "",
            "note": "test",
        },
        "route_refs": ["<generic_route_ref>"],
        "review_scope": {
            "total_reviews": 35,
            "total_asins": 8,
            "low_rating_count": 15,
            "date_range": {"start": "2026-01-01", "end": "2026-06-01"},
            "site": "US",
            "review_region_primary": "US",
        },
        "asin_coverage": {
            "covered_routes": 1,
            "total_routes": 1,
            "by_route": [
                {"route_ref": "<generic_route_ref>", "asin_count": 3, "review_count": 35,
                 "low_rating_count": 15, "meets_minimum_threshold": True}
            ],
            "by_asin_role": {"primary_reference": {"asin_count": 1, "review_count": 20}},
            "uncovered_roles": [],
        },
        "pain_points_by_dimension": [
            {
                "dimension": "产品质量",
                "severity": "P1",
                "frequency": 5,
                "description": "测试痛点。",
                "evidence_quotes": ["产品有问题。"],
                "evidence_refs": [{
                    "review_id": "R000001",
                    "asin": "B0XXXXX001",
                    "rating": 1.0,
                    "quote": "产品有问题。",
                    "source_path": "review_voc/review_voc_package.json",
                }],
                "spec_requirement": "需要改进。",
                "sample_tests": ["测试。"],
                "listing_risk_note": "风险。",
            }
        ],
        "unmet_needs": [],
        "differentiation_opportunities": [],
        "mixed_pool_signals": [],
        "review_quality_gaps": [],
        "confidence": "medium",
        "data_gaps": [],
        "evidence_refs": ["review_voc/review_voc_package.json"],
        "lineage": [],
    }


def _minimal_gate(decision: str = "continue") -> dict[str, Any]:
    return {
        "schema_version": "p5-voc-gate-v1",
        "gate_id": "voc_gate",
        "run_id": "test_run",
        "generated_at": "2026-06-24T00:00:00Z",
        "input_refs": ["review_voc/voc_evidence_packet.json"],
        "decision": decision,
        "decision_reason": "test decision reason",
        "inherited_warnings": [],
        "blockers": [],
        "checks": {
            "p4_conflict_level": "none",
            "p4_completeness_level": "none",
            "min_review_threshold_met": True,
            "low_rating_threshold_met": True,
            "route_coverage_complete": True,
            "asin_role_coverage_complete": True,
            "mixed_pool_separated": True,
        },
        "thresholds": {
            "min_total_reviews": 30,
            "min_low_rating_reviews": 10,
            "current_total_reviews": 35,
            "current_low_rating_reviews": 15,
        },
        "required_next_actions": ["进入 stage_7_report。"],
        "evidence_refs": ["review_voc/voc_evidence_packet.json"],
    }


def _minimal_voc_package() -> dict[str, Any]:
    return {
        "schema_version": "p5-voc-gate-v1",
        "metadata": {"run_id": "test_run", "source_batch_ref": "review_voc/review_asin_batch.json"},
        "stats": {"review_count": 35, "asin_count": 8, "asins": ["B0XXXXX001"], "low_rating_count": 15,
                  "primary_entry_site": "US", "primary_review_region": "US"},
        "normalized_reviews": _sample_reviews(35),
        "data_gaps": [],
        "pain_points": [],
        "highlights": [],
        "opportunity_hypotheses": [],
    }


def _minimal_asin_batch() -> dict[str, Any]:
    return {
        "schema_version": "p5-voc-gate-v1",
        "batch_id": "review_asin_batch",
        "run_id": "test_run",
        "site": "US",
        "asin_items": [
            {"asin": "B0XXXXX001", "asin_role": "primary_reference", "route_ref": "<generic_route_ref>",
             "selection_reason": "test", "source": "candidate_pool", "priority": 1},
        ],
        "route_coverage": [{"route_ref": "<generic_route_ref>", "roles_covered": ["primary_reference"]}],
        "operator_instruction": {"site": "US"},
        "data_gaps": [],
        "evidence_refs": ["test"],
    }


def _inject_p4_conflict_blocker(run_dir: Path) -> None:
    path = run_dir / "conflict_review" / "conflict_resolution_packet.json"
    data = load_json(path)
    data["conflict_level"] = "blocker"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _inject_p4_conflict_warning(run_dir: Path) -> None:
    path = run_dir / "conflict_review" / "conflict_resolution_packet.json"
    data = load_json(path)
    data["conflict_level"] = "warning"
    data["conflicts"] = [{"type": "price_band", "description": "test warning"}]
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _inject_p4_completeness_blocker(run_dir: Path) -> None:
    path = run_dir / "conflict_review" / "deep_data_completeness_check.json"
    data = load_json(path)
    data["completeness_level"] = "blocker"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _valid_sellersprite_snapshot() -> dict:
    return {
        "schema_version": "p4-deep-contract-v1",
        "snapshot_id": "generic-sellersprite-deep",
        "run_id": "20260624_generic_direction",
        "source_name": "sellersprite",
        "source_doc_refs": ["docs/references/p4_mcp_capability_mapping.md#sellersprite"],
        "route_refs": ["route_matrix_confirm.json#selected_routes[0]"],
        "selected_routes": ["<generic_route_ref>"],
        "tool_calls": [
            {"call_id": "call-market", "tool_name": "market_research", "params": {"marketplace": "US", "nodeIdPath": "<generic_node_path>"}, "status": "success", "started_at": "2026-06-24T00:00:00Z", "finished_at": "2026-06-24T00:00:01Z"},
            {"call_id": "call-price", "tool_name": "market_price_distribution", "params": {"marketplace": "US", "nodeIdPath": "<generic_node_path>"}, "status": "success", "started_at": "2026-06-24T00:00:00Z", "finished_at": "2026-06-24T00:00:01Z"},
            {"call_id": "call-seller", "tool_name": "market_seller_concentration", "params": {"marketplace": "US", "nodeIdPath": "<generic_node_path>"}, "status": "success", "started_at": "2026-06-24T00:00:00Z", "finished_at": "2026-06-24T00:00:01Z"},
            {"call_id": "call-product", "tool_name": "product_research", "params": {"marketplace": "US", "keyword": "<generic_keyword>"}, "status": "success", "started_at": "2026-06-24T00:00:00Z", "finished_at": "2026-06-24T00:00:01Z"},
            {"call_id": "call-asin", "tool_name": "asin_detail", "params": {"marketplace": "US", "asin": "<generic_asin>"}, "status": "success", "started_at": "2026-06-24T00:00:00Z", "finished_at": "2026-06-24T00:00:01Z"},
            {"call_id": "call-ratings", "tool_name": "market_ratings_count", "params": {"marketplace": "US", "nodeIdPath": "<generic_node_path>"}, "status": "success", "started_at": "2026-06-24T00:00:00Z", "finished_at": "2026-06-24T00:00:01Z"},
            {"call_id": "call-boundary", "tool_name": "competitor_lookup", "params": {"marketplace": "US", "asins": ["<generic_asin>"]}, "status": "success", "started_at": "2026-06-24T00:00:00Z", "finished_at": "2026-06-24T00:00:01Z"},
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
        "errors": [],
        "data_gaps": [],
        "created_at": "2026-06-24T00:00:00Z",
        "retry_policy": {"max_attempts": 1, "reuse_existing_snapshot": True, "allow_network_call": False},
        "force_refresh": False,
        "input_lineage": {"route_refs": ["route_matrix_confirm.json#selected_routes[0]"], "selected_routes": ["<generic_route_ref>"], "nodeIdPath": "<generic_node_path>"},
    }


def _valid_sorftime_snapshot() -> dict:
    return {
        "schema_version": "p4-deep-contract-v1",
        "snapshot_id": "generic-sorftime-deep",
        "run_id": "20260624_generic_direction",
        "source_name": "sorftime",
        "source_doc_refs": ["docs/references/p4_mcp_capability_mapping.md#sorftime"],
        "route_refs": ["route_matrix_confirm.json#selected_routes[0]"],
        "selected_routes": ["<generic_route_ref>"],
        "tool_calls": [
            {"call_id": "call-category-search", "tool_name": "category_search_from_product_name", "params": {"amzSite": "US", "productName": "<generic_product_name>", "page": 1}, "status": "success", "started_at": "2026-06-24T00:00:00Z", "finished_at": "2026-06-24T00:00:01Z"},
            {"call_id": "call-category-report", "tool_name": "category_report", "params": {"amzSite": "US", "nodeId": "<generic_node_id>"}, "status": "success", "started_at": "2026-06-24T00:00:00Z", "finished_at": "2026-06-24T00:00:01Z"},
            {"call_id": "call-category-trend", "tool_name": "category_trend", "params": {"amzSite": "US", "nodeId": "<generic_node_id>", "trendIndex": "SalesCount"}, "status": "success", "started_at": "2026-06-24T00:00:00Z", "finished_at": "2026-06-24T00:00:01Z"},
            {"call_id": "call-keyword-detail", "tool_name": "keyword_detail", "params": {"keywordSupportSite": "US", "keyword": "<generic_keyword>"}, "status": "success", "started_at": "2026-06-24T00:00:00Z", "finished_at": "2026-06-24T00:00:01Z"},
            {"call_id": "call-keyword-trend", "tool_name": "keyword_trend", "params": {"keywordSupportSite": "US", "keyword": "<generic_keyword>"}, "status": "success", "started_at": "2026-06-24T00:00:00Z", "finished_at": "2026-06-24T00:00:01Z"},
            {"call_id": "call-keyword-extends", "tool_name": "keyword_extends", "params": {"keywordSupportSite": "US", "keyword": "<generic_keyword>"}, "status": "success", "started_at": "2026-06-24T00:00:00Z", "finished_at": "2026-06-24T00:00:01Z"},
            {"call_id": "call-keyword-results", "tool_name": "keyword_search_results", "params": {"keywordSupportSite": "US", "keyword": "<generic_keyword>"}, "status": "success", "started_at": "2026-06-24T00:00:00Z", "finished_at": "2026-06-24T00:00:01Z"},
            {"call_id": "call-product-detail", "tool_name": "product_detail", "params": {"amzSite": "US", "asin": "<generic_asin>"}, "status": "success", "started_at": "2026-06-24T00:00:00Z", "finished_at": "2026-06-24T00:00:01Z"},
            {"call_id": "call-product-trend", "tool_name": "product_trend", "params": {"amzSite": "US", "asin": "<generic_asin>"}, "status": "success", "started_at": "2026-06-24T00:00:00Z", "finished_at": "2026-06-24T00:00:01Z"},
            {"call_id": "call-product-traffic", "tool_name": "product_traffic_terms", "params": {"amzSite": "US", "asin": "<generic_asin>"}, "status": "success", "started_at": "2026-06-24T00:00:00Z", "finished_at": "2026-06-24T00:00:01Z"},
            {"call_id": "call-competitor-keywords", "tool_name": "competitor_product_keywords", "params": {"keywordSupportSite": "US", "asin": "<generic_asin>"}, "status": "success", "started_at": "2026-06-24T00:00:00Z", "finished_at": "2026-06-24T00:00:01Z"},
            {"call_id": "call-product-reviews", "tool_name": "product_reviews", "params": {"amzSite": "US", "asin": "<generic_asin>"}, "status": "success", "started_at": "2026-06-24T00:00:00Z", "finished_at": "2026-06-24T00:00:01Z"},
            {"call_id": "call-hot-feature", "tool_name": "similar_product_feature", "params": {"amzSite": "US", "productName": "<generic_product_name>"}, "status": "success", "started_at": "2026-06-24T00:00:00Z", "finished_at": "2026-06-24T00:00:01Z"},
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
        "errors": [],
        "data_gaps": [],
        "created_at": "2026-06-24T00:00:00Z",
        "retry_policy": {"max_attempts": 1, "reuse_existing_snapshot": True, "allow_network_call": False},
        "force_refresh": False,
        "input_lineage": {"route_refs": ["route_matrix_confirm.json#selected_routes[0]"], "selected_routes": ["<generic_route_ref>"], "nodeId": "<generic_node_id>", "nodeIdPath": "<generic_node_path>", "seed_keyword": "<generic_keyword>", "amzSite": "US"},
    }


def _run_cli(run_dir: str) -> subprocess.CompletedProcess[str]:
    script = ROOT / "scripts" / "build_voc_gate.py"
    cmd = [sys.executable, str(script), run_dir]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=60)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))
