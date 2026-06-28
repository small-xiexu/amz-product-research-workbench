from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from packages.research_core.pipeline.build_route_matrix_confirmation import (
    P3ContractError,
    run_route_matrix_confirmation,
)
from packages.research_core.pipeline.build_mcp_candidate_pool import run_candidate_pool
from packages.research_core.pipeline.quick_market_check import run_quick_market_check
from tests.agent_output_fixtures import write_agent_candidate_pool, write_agent_route_matrix



ROOT = Path(__file__).resolve().parents[1]
P1_FIXTURES = ROOT / "tests" / "fixtures" / "p1_quick_check"


class P3RouteMatrixConfirmationTests(unittest.TestCase):
    def test_confirm_builds_route_matrix_and_data_completeness(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = _seed_run(Path(tmpdir))
            run_quick_market_check(run_dir, snapshot_source_dir=P1_FIXTURES)
            write_agent_candidate_pool(run_dir)
            run_candidate_pool(run_dir)
            write_agent_route_matrix(run_dir)

            outputs = run_route_matrix_confirmation(run_dir)
            route_packet = _load_json(outputs["route_matrix_confirm"])
            completeness = _load_json(outputs["data_completeness_check"])
            progress = _load_json(outputs["progress"])

        self.assertEqual(route_packet["decision"], "confirm")
        self.assertTrue(route_packet["selected_routes"])
        self.assertIn(completeness["overall_level"], {"acceptable", "warning"})
        self.assertEqual(progress["stages"]["stage_5_route_matrix"]["status"], "done")
        self.assertEqual(progress["stages"]["stage_4_candidate_pool"]["status"], "done")
        self.assertIn("route_matrix_confirm.json", progress["completed_artifacts"])
        self.assertIn("data_completeness_check.json", progress["completed_artifacts"])
        self.assertEqual(route_packet["voc_readiness"]["status"], "light_prepared")
        self.assertTrue(route_packet["voc_readiness"]["needs_voc_validation"])
        self.assertFalse(any("review_voc" in str(item) for item in route_packet.get("evidence_refs", [])))

    def test_revise_candidate_pool_when_complete_but_no_selected_route(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = _seed_run(Path(tmpdir))
            run_quick_market_check(run_dir, snapshot_source_dir=P1_FIXTURES)
            write_agent_candidate_pool(run_dir)
            run_candidate_pool(run_dir)
            candidate_pool_path = run_dir / "candidate_pool.json"
            candidate_pool = _load_json(candidate_pool_path)
            for candidate in candidate_pool.get("candidates", []):
                candidate["readiness_status"] = "needs_user_review"
                candidate["status"] = "观察"
            candidate_pool["pool_status"] = "needs_user_review"
            candidate_pool_path.write_text(json.dumps(candidate_pool, ensure_ascii=False, indent=2), encoding="utf-8")
            write_agent_route_matrix(run_dir)

            outputs = run_route_matrix_confirmation(run_dir)
            route_packet = _load_json(outputs["route_matrix_confirm"])
            completeness = _load_json(outputs["data_completeness_check"])
            progress = _load_json(outputs["progress"])

        self.assertEqual(route_packet["decision"], "revise_candidate_pool")
        self.assertEqual(completeness["overall_level"], "warning")
        self.assertEqual(progress["stages"]["stage_4_candidate_pool"]["status"], "needs_user")
        self.assertEqual(progress["stages"]["stage_5_route_matrix"]["status"], "needs_user")
        self.assertEqual(progress["next_action"]["type"], "needs_user")

    def test_stop_when_all_candidates_excluded(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = _seed_run(Path(tmpdir))
            run_quick_market_check(run_dir, snapshot_source_dir=P1_FIXTURES)
            write_agent_candidate_pool(run_dir)
            run_candidate_pool(run_dir)
            candidate_pool_path = run_dir / "candidate_pool.json"
            candidate_pool = _load_json(candidate_pool_path)
            candidate_pool["pool_status"] = "excluded"
            for candidate in candidate_pool.get("candidates", []):
                candidate["readiness_status"] = "excluded"
                candidate["status"] = "先放弃"
                candidate["support_level"] = "negative"
            candidate_pool_path.write_text(json.dumps(candidate_pool, ensure_ascii=False, indent=2), encoding="utf-8")
            write_agent_route_matrix(run_dir)

            outputs = run_route_matrix_confirmation(run_dir)
            route_packet = _load_json(outputs["route_matrix_confirm"])
            progress = _load_json(outputs["progress"])

        self.assertEqual(route_packet["decision"], "stop")
        self.assertEqual(progress["stages"]["stage_5_route_matrix"]["status"], "blocked")
        self.assertEqual(progress["stages"]["stage_4_candidate_pool"]["status"], "blocked")
        self.assertEqual(progress["next_action"]["type"], "blocked")

    def test_data_completeness_blocker_prevents_confirm(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = _seed_run(Path(tmpdir))
            run_quick_market_check(run_dir, snapshot_source_dir=P1_FIXTURES)
            write_agent_candidate_pool(run_dir)
            run_candidate_pool(run_dir)
            quick_path = run_dir / "quick_check" / "sellersprite_quick_evidence_packet.json"
            quick = _load_json(quick_path)
            quick["blocking_gaps"] = [{"type": "missing_required_quick_call", "severity": "blocking"}]
            quick_path.write_text(json.dumps(quick, ensure_ascii=False, indent=2), encoding="utf-8")
            write_agent_route_matrix(run_dir)

            outputs = run_route_matrix_confirmation(run_dir)
            route_packet = _load_json(outputs["route_matrix_confirm"])
            completeness = _load_json(outputs["data_completeness_check"])

        self.assertEqual(completeness["overall_level"], "blocker")
        self.assertIn(route_packet["decision"], {"revise_candidate_pool", "stop"})
        self.assertNotEqual(route_packet["decision"], "confirm")

    def test_schema_failure_does_not_mark_done(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = _seed_run(Path(tmpdir))
            run_quick_market_check(run_dir, snapshot_source_dir=P1_FIXTURES)
            write_agent_candidate_pool(run_dir)
            run_candidate_pool(run_dir)
            candidate_pool_path = run_dir / "candidate_pool.json"
            candidate_pool = _load_json(candidate_pool_path)
            candidate_pool.pop("candidates", None)
            candidate_pool_path.write_text(json.dumps(candidate_pool, ensure_ascii=False, indent=2), encoding="utf-8")

            with self.assertRaises(P3ContractError):
                run_route_matrix_confirmation(run_dir)

            progress = _load_json(run_dir / "progress.json")

        self.assertEqual(progress["stages"]["stage_5_route_matrix"]["status"], "failed")
        self.assertFalse((run_dir / "route_matrix_confirm.json").exists())
        self.assertFalse((run_dir / "data_completeness_check.json").exists())

    def test_missing_candidate_pool_fails_without_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = _seed_run(Path(tmpdir))
            run_quick_market_check(run_dir, snapshot_source_dir=P1_FIXTURES)

            with self.assertRaises(P3ContractError):
                run_route_matrix_confirmation(run_dir)

            progress = _load_json(run_dir / "progress.json")

        self.assertEqual(progress["stages"]["stage_5_route_matrix"]["status"], "failed")
        self.assertIn("candidate_pool.json is required", progress["stages"]["stage_5_route_matrix"]["last_error"])
        self.assertFalse((run_dir / "route_matrix_confirm.json").exists())
        self.assertFalse((run_dir / "data_completeness_check.json").exists())


def _seed_run(root: Path) -> Path:
    run_dir = root / "20260624_generic_direction"
    run_dir.mkdir()
    (run_dir / "workflow_state.json").write_text(
        json.dumps(
            {
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
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return run_dir


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))
