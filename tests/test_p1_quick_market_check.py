from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from packages.research_core.pipeline.quick_market_check import (
    P1ContractError,
    build_quick_market_gate,
    build_quick_packet,
    run_quick_market_check,
    validate_mcp_snapshot,
    validate_progress,
    validate_quick_gate,
    validate_quick_packet,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "p1_quick_check"


class P1QuickMarketCheckTests(unittest.TestCase):
    def test_sellersprite_quick_snapshot_builds_quick_packet(self) -> None:
        snapshot = _load_fixture("sellersprite_quick_snapshot.json")

        validate_mcp_snapshot(snapshot, "sellersprite")
        packet = build_quick_packet(snapshot, "sellersprite")
        validate_quick_packet(packet, "sellersprite")

        self.assertEqual(packet["packet_id"], "sellersprite_quick_evidence_packet")
        self.assertEqual(packet["source_type"], "sellersprite_mcp")
        self.assertEqual(packet["support_level"], "strong")
        self.assertEqual(packet["metric_basis"]["aggregation_unit"], "category")
        self.assertIn("mcp_snapshots/sellersprite_quick_snapshot.json#tool_calls[0]", packet["evidence_refs"])

    def test_sorftime_quick_snapshot_builds_quick_packet(self) -> None:
        snapshot = _load_fixture("sorftime_quick_snapshot.json")

        validate_mcp_snapshot(snapshot, "sorftime")
        packet = build_quick_packet(snapshot, "sorftime")
        validate_quick_packet(packet, "sorftime")

        self.assertEqual(packet["packet_id"], "sorftime_quick_evidence_packet")
        self.assertEqual(packet["source_type"], "sorftime_mcp")
        self.assertEqual(packet["support_level"], "moderate")
        self.assertEqual(packet["metric_basis"]["aggregation_unit"], "keyword")
        self.assertIn("mcp_snapshots/sorftime_quick_snapshot.json#tool_calls[0]", packet["evidence_refs"])

    def test_run_quick_market_check_from_fixture_snapshots_writes_p1_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = _create_run_dir(Path(tmpdir))

            outputs = run_quick_market_check(run_dir, snapshot_source_dir=FIXTURES)

            for path in outputs.values():
                self.assertTrue(path.exists(), path)
            self.assertFalse((run_dir / "candidate_pool.json").exists())

            gate = _load_json(run_dir / "quick_check" / "quick_market_gate.json")
            progress = _load_json(run_dir / "progress.json")
            validate_quick_gate(gate)
            validate_progress(progress)

        self.assertEqual(gate["gate_result"], "continue")
        self.assertIn("both_supported", gate["rule_hits"])
        self.assertEqual(progress["stages"]["stage_2_market_quick_check"]["status"], "done")
        self.assertEqual(progress["stages"]["stage_3_quick_gate"]["status"], "done")
        self.assertIn("quick_check/quick_market_gate.json", progress["completed_artifacts"])

    def test_quick_gate_watch_when_material_mixed_pool(self) -> None:
        sellersprite = build_quick_packet(_load_fixture("sellersprite_quick_snapshot.json"), "sellersprite")
        sorftime = build_quick_packet(_load_fixture("sorftime_quick_snapshot.json"), "sorftime")
        sorftime["mixed_pool_level"] = "material"

        gate = build_quick_market_gate(sellersprite, sorftime)
        validate_quick_gate(gate)

        self.assertEqual(gate["gate_result"], "watch")
        self.assertIn("material_mixed_pool", gate["rule_hits"])

    def test_quick_gate_stop_when_blocking_gaps_exist(self) -> None:
        sellersprite = build_quick_packet(_load_fixture("sellersprite_quick_snapshot.json"), "sellersprite")
        sorftime = build_quick_packet(_load_fixture("sorftime_quick_snapshot.json"), "sorftime")
        sellersprite["blocking_gaps"] = [{"type": "missing_required_quick_call", "severity": "blocking"}]

        gate = build_quick_market_gate(sellersprite, sorftime)
        validate_quick_gate(gate)

        self.assertEqual(gate["gate_result"], "stop")
        self.assertEqual(gate["rule_hits"], ["blocking_gaps"])

    def test_schema_failure_writes_failed_progress_and_does_not_mark_done(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            run_dir = _create_run_dir(root)
            source_dir = root / "snapshots"
            source_dir.mkdir()
            shutil.copyfile(
                FIXTURES / "sorftime_quick_snapshot.json",
                source_dir / "sorftime_quick_snapshot.json",
            )
            broken = _load_fixture("sellersprite_quick_snapshot.json")
            broken.pop("tool_calls")
            (source_dir / "sellersprite_quick_snapshot.json").write_text(
                json.dumps(broken, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            with self.assertRaises(P1ContractError):
                run_quick_market_check(run_dir, snapshot_source_dir=source_dir)

            progress = _load_json(run_dir / "progress.json")

        validate_progress(progress)
        self.assertEqual(progress["stages"]["stage_2_market_quick_check"]["status"], "failed")
        self.assertEqual(progress["stages"]["stage_3_quick_gate"]["status"], "pending")
        self.assertEqual(progress["completed_artifacts"], [])


def _create_run_dir(root: Path) -> Path:
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
                    "marketplace": "US",
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


def _load_fixture(name: str) -> dict:
    return _load_json(FIXTURES / name)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))
