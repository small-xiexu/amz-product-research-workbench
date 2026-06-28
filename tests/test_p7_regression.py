"""P7 regression tests: judgment E2E, progress flow, CLI smoke, scope boundaries.

These tests complement test_p7_contracts.py (contract-level tests).
They verify the integrated_operator_judgment pipeline seeded from P4→P5→P6.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

from packages.research_core.contracts import (
    P7_STAGE_ID,
    P7_SCHEMA_VERSION,
    validate_integrated_judgment,
)
from packages.research_core.pipeline.build_conflict_review import run_conflict_review
from packages.research_core.pipeline.build_evaluation_summary import (
    run_evaluations,
)
from packages.research_core.pipeline.build_integrated_judgment import (
    build_integrated_judgment,
    run_integrated_judgment,
    update_progress,
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
from packages.research_core.pipeline.quick_market_check import run_quick_market_check
from tests.agent_output_fixtures import write_agent_candidate_pool, write_agent_route_matrix

ROOT = Path(__file__).resolve().parents[1]
P1_FIXTURES = ROOT / "tests" / "fixtures" / "p1_quick_check"

_PYTHONPATH = str(ROOT)

def _cli_env() -> dict:
    import os
    env = os.environ.copy()
    env["PYTHONPATH"] = _PYTHONPATH + (":" + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    return env

# ── E2E golden path ────────────────────────────────────────────────────────

class P7EndToEndTests(unittest.TestCase):
    """Seed P4 → P5 → P6 → P7, verify judgment output."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self._tmp = Path(self._tmpdir.name)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def _seed_p6_done(self) -> Path:
        """Seed full P4→P5→P6 pipeline, return run_dir."""
        run_dir = self._tmp / "20260625_generic_direction"
        run_dir.mkdir()
        (run_dir / "workflow_state.json").write_text(
            json.dumps(_workflow_state(), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        run_quick_market_check(run_dir, snapshot_source_dir=P1_FIXTURES)
        write_agent_candidate_pool(run_dir)
        run_candidate_pool(run_dir)
        write_agent_route_matrix(run_dir)
        run_route_matrix_confirmation(run_dir)
        run_sellersprite_deep_dive(run_dir, snapshot_source=self._write_sellersprite_snapshot())
        run_sorftime_deep_dive(run_dir, snapshot_source=self._write_sorftime_snapshot())
        run_conflict_review(run_dir)
        run_review_asin_batch(run_dir)
        run_review_voc_package(run_dir, self._write_review_xlsx(35))
        run_voc_gate(run_dir)
        _write_agent_evaluations(run_dir)
        run_evaluations(run_dir)
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

    # ── Golden path ──────────────────────────────────────────────────

    def test_e2e_judgment_output_exists(self) -> None:
        """P6 → P7 produces integrated_operator_judgment.json."""
        run_dir = self._seed_p6_done()
        run_integrated_judgment(run_dir)

        output_path = run_dir / "analysis" / "integrated_operator_judgment.json"
        self.assertTrue(output_path.exists())

    def test_judgment_passes_contract(self) -> None:
        """integrated_operator_judgment passes validate_integrated_judgment."""
        run_dir = self._seed_p6_done()
        judgment = build_integrated_judgment(run_dir)
        validate_integrated_judgment(judgment)

    def test_skeleton_fails_final_judgment_contract(self) -> None:
        """Delivery judgment contract rejects unfilled skeleton fields."""
        from packages.research_core.pipeline.judgment_contract import validate_judgment_structure

        run_dir = self._seed_p6_done()
        judgment = build_integrated_judgment(run_dir)
        result = validate_judgment_structure(judgment)
        self.assertFalse(result["pass"])
        self.assertTrue(any("Lead Operator Agent 未完成最终判断" in issue for issue in result["issues"]))

    def test_skeleton_blocks_until_lead_operator_runs(self) -> None:
        """Script skeleton keeps final_verdict blocked until Lead Operator fills it."""
        run_dir = self._seed_p6_done()
        judgment = build_integrated_judgment(run_dir)
        self.assertEqual(judgment["final_verdict"], "blocked")
        self.assertEqual(judgment["execution_provenance"]["execution_mode"], "script_generated_skeleton")

    def test_judgment_has_valid_confidence(self) -> None:
        """confidence is high/medium/low."""
        run_dir = self._seed_p6_done()
        judgment = build_integrated_judgment(run_dir)
        self.assertIn(judgment["confidence"], {"high", "medium", "low"})

    def test_judgment_has_non_empty_verdict_reason(self) -> None:
        """verdict_reason is a non-empty string."""
        run_dir = self._seed_p6_done()
        judgment = build_integrated_judgment(run_dir)
        self.assertTrue(judgment["verdict_reason"].strip())

    def test_judgment_has_recommended_route(self) -> None:
        """recommended_route contains a route name."""
        run_dir = self._seed_p6_done()
        judgment = build_integrated_judgment(run_dir)
        route = judgment["recommended_route"]
        self.assertTrue(
            (isinstance(route, dict) and route.get("name"))
            or (isinstance(route, str) and route.strip())
        )

    def test_judgment_has_next_actions(self) -> None:
        """required_next_actions is non-empty."""
        run_dir = self._seed_p6_done()
        judgment = build_integrated_judgment(run_dir)
        self.assertGreater(len(judgment["required_next_actions"]), 0)

    def test_judgment_has_constraints_applied(self) -> None:
        """constraints_applied is non-empty."""
        run_dir = self._seed_p6_done()
        judgment = build_integrated_judgment(run_dir)
        self.assertGreater(len(judgment["constraints_applied"]), 0)

    def test_judgment_has_evidence_refs(self) -> None:
        """evidence_refs references evaluation outputs."""
        run_dir = self._seed_p6_done()
        judgment = build_integrated_judgment(run_dir)
        self.assertGreater(len(judgment["evidence_refs"]), 0)

    def test_execution_provenance_is_script_generated_skeleton(self) -> None:
        """Judgment skeleton is script-generated, not real agent execution."""
        run_dir = self._seed_p6_done()
        judgment = build_integrated_judgment(run_dir)
        prov = judgment.get("execution_provenance", {})
        self.assertFalse(prov.get("executed_by_agent"))
        self.assertEqual(prov.get("execution_mode"), "script_generated_skeleton")

    # ── Verdict rules ─────────────────────────────────────────────────

    def test_script_does_not_apply_evaluation_summary_verdict_range(self) -> None:
        """Skeleton does not turn P6 verdict range into final decision."""
        run_dir = self._seed_p6_done()
        judgment = build_integrated_judgment(run_dir)
        self.assertEqual(judgment["final_verdict"], "blocked")
        self.assertIn("Lead Operator Agent", judgment["verdict_reason"])

    def test_biggest_opportunity_waits_for_lead_operator(self) -> None:
        """Script does not identify biggest opportunity."""
        run_dir = self._seed_p6_done()
        judgment = build_integrated_judgment(run_dir)
        opp = judgment["biggest_opportunity"]
        self.assertEqual(opp.get("dimension"), "__ai_judgment__")
        self.assertEqual(opp.get("detail"), "__ai_judgment__")

    def test_biggest_risk_waits_for_lead_operator(self) -> None:
        """Script does not identify biggest risk."""
        run_dir = self._seed_p6_done()
        judgment = build_integrated_judgment(run_dir)
        risk = judgment["biggest_risk"]
        self.assertEqual(risk.get("dimension"), "__ai_judgment__")
        self.assertEqual(risk.get("detail"), "__ai_judgment__")

    # ── Progress flow ─────────────────────────────────────────────────

    def test_progress_stage_9_waits_for_agents(self) -> None:
        """stage_9_report.status stays running after skeleton generation."""
        run_dir = self._seed_p6_done()
        judgment = build_integrated_judgment(run_dir)
        update_progress(run_dir, judgment)

        with open(run_dir / "progress.json", encoding="utf-8") as f:
            progress = json.load(f)
        stage_9 = progress["stages"].get(P7_STAGE_ID, {})
        self.assertEqual(stage_9.get("status"), "running")

    def test_progress_completed_artifacts_excludes_skeleton_judgment(self) -> None:
        """completed_artifacts does not treat skeleton as final judgment."""
        run_dir = self._seed_p6_done()
        judgment = build_integrated_judgment(run_dir)
        update_progress(run_dir, judgment)

        with open(run_dir / "progress.json", encoding="utf-8") as f:
            progress = json.load(f)
        completed = progress.get("completed_artifacts", [])
        self.assertNotIn("analysis/integrated_operator_judgment.json", completed)

    def test_progress_next_action_mentions_ai_step(self) -> None:
        """next_action guides AI to enhance report_data."""
        run_dir = self._seed_p6_done()
        judgment = build_integrated_judgment(run_dir)
        update_progress(run_dir, judgment)

        with open(run_dir / "progress.json", encoding="utf-8") as f:
            progress = json.load(f)
        next_action = progress.get("next_action", {})
        self.assertIn(next_action.get("type", ""), ["ai_step", "P7"])

    # ── Error / missing input cases ────────────────────────────────────

    def test_missing_evaluations_dir_handled(self) -> None:
        """Judgment gracefully handles missing evaluations/ dir."""
        run_dir = self._seed_p6_done()
        import shutil
        shutil.rmtree(run_dir / "evaluations")
        judgment = build_integrated_judgment(run_dir)
        # Should still produce a valid judgment structure (graceful degradation)
        self.assertEqual(judgment["final_verdict"], "blocked")
        # Without evaluations, skeleton confidence remains low.
        self.assertEqual(judgment["confidence"], "low")

    def test_missing_route_matrix_handled(self) -> None:
        """Judgment handles missing route_matrix_confirm.json."""
        run_dir = self._seed_p6_done()
        (run_dir / "route_matrix_confirm.json").unlink()
        judgment = build_integrated_judgment(run_dir)
        route = judgment["recommended_route"]
        # Should provide a fallback with unknown role
        self.assertTrue(isinstance(route, dict))
        self.assertIn("role", route)

    # ── Scope boundaries ────────────────────────────────────────────

    def test_p7_does_not_produce_html(self) -> None:
        """P7 script does not generate HTML."""
        run_dir = self._seed_p6_done()
        judgment = build_integrated_judgment(run_dir)
        html_files = list(run_dir.glob("**/*.html"))
        self.assertEqual(len(html_files), 0,
                        "P7 should not generate HTML (AI responsibility)")

    def test_p7_does_not_produce_xlsx(self) -> None:
        """P7 script does not generate XLSX."""
        run_dir = self._seed_p6_done()
        judgment = build_integrated_judgment(run_dir)
        xlsx_files = list(run_dir.glob("**/*.xlsx"))
        self.assertEqual(len(xlsx_files), 0,
                        "P7 should not generate XLSX (report stage responsibility)")

    def test_judgment_is_deterministic(self) -> None:
        """Same inputs produce the same verdict."""
        run_dir = self._seed_p6_done()
        j1 = build_integrated_judgment(run_dir)
        j2 = build_integrated_judgment(run_dir)
        self.assertEqual(j1["final_verdict"], j2["final_verdict"])

    # ── CLI smoke ─────────────────────────────────────────────────────

    def test_cli_smoke_help(self) -> None:
        """CLI with no args prints usage info."""
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "build_integrated_judgment.py")],
            capture_output=True, text=True, env=_cli_env(),
        )
        self.assertNotEqual(result.returncode, 0)

    def test_cli_smoke_nonexistent_dir(self) -> None:
        """CLI with nonexistent path returns error."""
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "build_integrated_judgment.py"),
             "/nonexistent/dir"],
            capture_output=True, text=True, env=_cli_env(),
        )
        self.assertNotEqual(result.returncode, 0)

    def test_cli_smoke_success(self) -> None:
        """CLI runs successfully on a seeded run directory."""
        run_dir = self._seed_p6_done()
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "build_integrated_judgment.py"),
             str(run_dir)],
            capture_output=True, text=True, env=_cli_env(),
        )
        self.assertEqual(result.returncode, 0,
                       f"CLI failed: {result.stderr}")
        self.assertTrue(
            (run_dir / "analysis" / "integrated_operator_judgment.json").exists()
        )
        self.assertIn("skeleton only", result.stdout)

    def test_validate_verdict_rejects_script_skeleton(self) -> None:
        """Final verdict validation blocks skeleton output before Lead Operator."""
        run_dir = self._seed_p6_done()
        run_integrated_judgment(run_dir)
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "validate_judgment.py"),
                str(run_dir),
                "--check-verdict",
            ],
            capture_output=True,
            text=True,
            env=_cli_env(),
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Lead Operator Agent 未完成最终判断", result.stdout)

    def test_cli_no_evaluations_dir_returns_error(self) -> None:
        """CLI returns error when evaluations/ is missing."""
        run_dir = self._seed_p6_done()
        import shutil
        shutil.rmtree(run_dir / "evaluations")
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "build_integrated_judgment.py"),
             str(run_dir)],
            capture_output=True, text=True, env=_cli_env(),
        )
        self.assertNotEqual(result.returncode, 0)

    # ── VOC degradation mode ─────────────────────────────────────────────

    def _seed_p6_with_review_count(self, review_count: int) -> Path:
        """Seed P4→P5→P6 with a specific review count."""
        run_dir = self._tmp / f"20260625_degraded_{review_count}"
        run_dir.mkdir()
        (run_dir / "workflow_state.json").write_text(
            json.dumps(_workflow_state(), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        run_quick_market_check(run_dir, snapshot_source_dir=P1_FIXTURES)
        write_agent_candidate_pool(run_dir)
        run_candidate_pool(run_dir)
        write_agent_route_matrix(run_dir)
        run_route_matrix_confirmation(run_dir)
        run_sellersprite_deep_dive(run_dir, snapshot_source=self._write_sellersprite_snapshot())
        run_sorftime_deep_dive(run_dir, snapshot_source=self._write_sorftime_snapshot())
        run_conflict_review(run_dir)
        run_review_asin_batch(run_dir)
        run_review_voc_package(run_dir, self._write_review_xlsx(review_count))
        run_voc_gate(run_dir)
        _write_agent_evaluations(run_dir)
        run_evaluations(run_dir)
        # Populate voc_evidence_packet with synthetic pain points (simulating AI agent output).
        # The script-generated package has pain_points=[], but real pipeline has AI-filled ones.
        voc_packet_path = run_dir / "review_voc" / "voc_evidence_packet.json"
        voc_packet = json.loads(voc_packet_path.read_text(encoding="utf-8"))
        facts = voc_packet.setdefault("facts", {})
        facts["pain_points"] = [
            {
                "priority": "P0",
                "dimension": "durability",
                "review_count": 5,
                "evidence_quotes": ["easily broken", "poor material", "lasted only 2 weeks"],
            },
            {
                "priority": "P1",
                "dimension": "noise_level",
                "review_count": 3,
                "evidence_quotes": ["too loud", "noisy operation"],
            },
        ]
        voc_packet_path.write_text(json.dumps(voc_packet, ensure_ascii=False, indent=2), encoding="utf-8")
        return run_dir

    def test_voc_degradation_adds_data_note_to_voc_to_spec(self) -> None:
        """When < 30 reviews, each voc_to_spec entry gets data_note."""
        run_dir = self._seed_p6_with_review_count(12)
        judgment = build_integrated_judgment(run_dir)
        voc_entries = judgment.get("voc_to_spec", [])
        self.assertGreater(len(voc_entries), 0, "voc_to_spec should not be empty")
        for i, entry in enumerate(voc_entries):
            self.assertIn("data_note", entry,
                         f"voc_to_spec[{i}] missing data_note in degradation mode")
            self.assertIn("样本不足", entry["data_note"],
                         f"voc_to_spec[{i}].data_note should mention sample insufficiency")
            self.assertIn("12", entry["data_note"],
                         f"voc_to_spec[{i}].data_note should include review count")

    def test_voc_degradation_not_applied_when_reviews_sufficient(self) -> None:
        """When >= 30 reviews, degradation fields are NOT present."""
        run_dir = self._seed_p6_with_review_count(35)
        judgment = build_integrated_judgment(run_dir)
        voc_entries = judgment.get("voc_to_spec", [])
        for i, entry in enumerate(voc_entries):
            self.assertNotIn("data_note", entry,
                            f"voc_to_spec[{i}] should not have data_note when reviews sufficient")
    def test_voc_degradation_no_gate_file_no_crash(self) -> None:
        """When voc_gate.json is missing, degradation gracefully defaults (no crash)."""
        run_dir = self._seed_p6_with_review_count(35)
        # Remove voc_gate.json to simulate missing gate
        (run_dir / "review_voc" / "voc_gate.json").unlink()
        judgment = build_integrated_judgment(run_dir)
        # Should still produce valid voc_to_spec without crashing
        voc_entries = judgment.get("voc_to_spec", [])
        self.assertIsInstance(voc_entries, list)

# ── Full chain: P6 → P7 → report seed ─────────────────────────────────────

class P7FullChainTests(unittest.TestCase):
    """Verify P7 judgment integrates with the report generation flow."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self._tmp = Path(self._tmpdir.name)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_judgment_plus_analysis_packet_chain(self) -> None:
        """P7 judgment + analysis packet + seed = full chain ready for AI."""
        run_dir = self._tmp / "20260625_generic_chain"
        run_dir.mkdir()
        (run_dir / "workflow_state.json").write_text(
            json.dumps(_workflow_state(), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        run_quick_market_check(run_dir, snapshot_source_dir=P1_FIXTURES)
        write_agent_candidate_pool(run_dir)
        run_candidate_pool(run_dir)
        write_agent_route_matrix(run_dir)
        run_route_matrix_confirmation(run_dir)
        run_sellersprite_deep_dive(run_dir, snapshot_source=self._write_ss(run_dir))
        run_sorftime_deep_dive(run_dir, snapshot_source=self._write_sf(run_dir))
        run_conflict_review(run_dir)
        run_review_asin_batch(run_dir)
        run_review_voc_package(run_dir, self._write_rx(run_dir, 35))
        run_voc_gate(run_dir)
        _write_agent_evaluations(run_dir)
        run_evaluations(run_dir)
        run_integrated_judgment(run_dir)

        # Verify all P6 + P7 artifacts exist
        eval_dir = run_dir / "evaluations"
        self.assertTrue(eval_dir.exists())
        for dim in ["market_demand", "competition", "price_profit",
                     "voc_opportunity", "risk", "data_quality"]:
            self.assertTrue(
                (eval_dir / f"{dim}_evaluation.json").exists(),
                f"Missing evaluation: {dim}"
            )
        self.assertTrue(
            (run_dir / "analysis" / "integrated_operator_judgment.json").exists()
        )

    def _write_ss(self, run_dir: Path) -> Path:
        path = self._tmp / "ss_snap.json"
        path.write_text(json.dumps(_valid_sellersprite_snapshot(), ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def _write_sf(self, run_dir: Path) -> Path:
        path = self._tmp / "sf_snap.json"
        path.write_text(json.dumps(_valid_sorftime_snapshot(), ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def _write_rx(self, run_dir: Path, count: int = 35) -> Path:
        path = self._tmp / "test_reviews.xlsx"
        _write_review_xlsx_file(path, _sample_reviews(count))
        return path

# ── Fixtures ───────────────────────────────────────────────────────────────

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
        "workflow_id": "20260625_generic_direction",
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
        "run_id": "20260625_generic_direction",
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
        "run_id": "20260625_generic_direction",
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
