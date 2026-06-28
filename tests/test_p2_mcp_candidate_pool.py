from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from packages.research_core.contracts import validate_candidate_pool
from packages.research_core.pipeline.build_mcp_candidate_pool import P2ContractError, run_candidate_pool
from packages.research_core.pipeline.quick_market_check import run_quick_market_check
from tests.agent_output_fixtures import write_agent_candidate_pool



ROOT = Path(__file__).resolve().parents[1]
P1_FIXTURES = ROOT / "tests" / "fixtures" / "p1_quick_check"


class P2McpCandidatePoolTests(unittest.TestCase):
    def test_continue_gate_builds_candidate_pool(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = _seed_run(Path(tmpdir))
            run_quick_market_check(run_dir, snapshot_source_dir=P1_FIXTURES)
            write_agent_candidate_pool(run_dir)

            outputs = run_candidate_pool(run_dir)

            candidate_pool = _load_json(outputs["candidate_pool"])
            progress = _load_json(outputs["progress"])

        validate_candidate_pool(candidate_pool)
        self.assertEqual(candidate_pool["source_stage"], "market_quick_check")
        self.assertEqual(candidate_pool["pool_status"], "ready_for_route_matrix")
        self.assertTrue(candidate_pool["evidence_refs"])
        self.assertGreaterEqual(len(candidate_pool["candidates"]), 1)
        self.assertTrue(
            any("quick_market_gate.json" in ref for ref in candidate_pool["evidence_refs"])
        )
        self.assertTrue(any("quick_check/sellersprite_quick_evidence_packet.json" in ref for ref in candidate_pool["evidence_refs"]))
        self.assertEqual(progress["stages"]["stage_4_candidate_pool"]["status"], "done")
        self.assertIn("candidate_pool.json", progress["completed_artifacts"])
        self.assertFalse((run_dir / "route_matrix_confirm.json").exists())

    def test_watch_gate_builds_needs_user_candidate_pool(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = _seed_run(Path(tmpdir))
            run_quick_market_check(run_dir, snapshot_source_dir=P1_FIXTURES)
            gate_path = run_dir / "quick_check" / "quick_market_gate.json"
            gate = _load_json(gate_path)
            gate["gate_result"] = "watch"
            gate["gate_reasons"] = ["边界仍需复核"]
            gate["next_action"] = {"type": "needs_user", "description": "review boundary"}
            gate_path.write_text(json.dumps(gate, ensure_ascii=False, indent=2), encoding="utf-8")
            write_agent_candidate_pool(run_dir)

            outputs = run_candidate_pool(run_dir)
            candidate_pool = _load_json(outputs["candidate_pool"])
            progress = _load_json(outputs["progress"])

        self.assertEqual(candidate_pool["pool_status"], "needs_user_review")
        self.assertTrue(all(candidate["readiness_status"] == "needs_user_review" for candidate in candidate_pool["candidates"]))
        self.assertEqual(progress["stages"]["stage_4_candidate_pool"]["status"], "needs_user")
        self.assertEqual(progress["next_action"]["type"], "needs_user")

    def test_stop_gate_builds_blocked_candidate_pool(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = _seed_run(Path(tmpdir))
            run_quick_market_check(run_dir, snapshot_source_dir=P1_FIXTURES)
            gate_path = run_dir / "quick_check" / "quick_market_gate.json"
            gate = _load_json(gate_path)
            gate["gate_result"] = "stop"
            gate["gate_reasons"] = ["阻塞级缺口"]
            gate["next_action"] = {"type": "stop", "description": "stop here"}
            gate_path.write_text(json.dumps(gate, ensure_ascii=False, indent=2), encoding="utf-8")
            write_agent_candidate_pool(run_dir)

            outputs = run_candidate_pool(run_dir)
            candidate_pool = _load_json(outputs["candidate_pool"])
            progress = _load_json(outputs["progress"])

        self.assertEqual(candidate_pool["pool_status"], "excluded")
        self.assertTrue(all(candidate["readiness_status"] == "excluded" for candidate in candidate_pool["candidates"]))
        self.assertTrue(all(candidate["status"] == "先放弃" for candidate in candidate_pool["candidates"]))
        self.assertEqual(progress["stages"]["stage_4_candidate_pool"]["status"], "blocked")
        self.assertTrue(progress["global_blockers"])
        self.assertFalse((run_dir / "route_matrix_confirm.json").exists())

    def test_schema_validation_failure_does_not_mark_done(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = _seed_run(Path(tmpdir))
            run_quick_market_check(run_dir, snapshot_source_dir=P1_FIXTURES)
            workflow_path = run_dir / "workflow_state.json"
            workflow = _load_json(workflow_path)
            workflow.pop("stage", None)
            workflow_path.write_text(json.dumps(workflow, ensure_ascii=False, indent=2), encoding="utf-8")
            write_agent_candidate_pool(run_dir)

            with self.assertRaises(P2ContractError):
                run_candidate_pool(run_dir)

            progress = _load_json(run_dir / "progress.json")

        self.assertEqual(progress["stages"]["stage_4_candidate_pool"]["status"], "failed")
        self.assertNotIn("candidate_pool.json", progress.get("completed_artifacts", []))
        self.assertFalse((run_dir / "candidate_pool.json").exists())

    def test_new_entry_does_not_depend_on_legacy_fused_script(self) -> None:
        module_text = (ROOT / "packages" / "research_core" / "pipeline" / "build_mcp_candidate_pool.py").read_text(encoding="utf-8")
        script_text = (ROOT / "scripts" / "build_mcp_candidate_pool.py").read_text(encoding="utf-8")

        self.assertNotIn("build_fused_candidate_pool", module_text)
        self.assertNotIn("build_fused_candidate_pool", script_text)

    def test_missing_agent_candidate_pool_fails_without_generation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = _seed_run(Path(tmpdir))
            run_quick_market_check(run_dir, snapshot_source_dir=P1_FIXTURES)

            with self.assertRaises(P2ContractError):
                run_candidate_pool(run_dir)

            progress = _load_json(run_dir / "progress.json")

        self.assertEqual(progress["stages"]["stage_4_candidate_pool"]["status"], "failed")
        self.assertIn("candidate_pool.json 应由主 Agent 生成", progress["stages"]["stage_4_candidate_pool"]["last_error"])
        self.assertFalse((run_dir / "candidate_pool.json").exists())


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
