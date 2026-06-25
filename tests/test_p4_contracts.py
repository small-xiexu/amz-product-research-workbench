from __future__ import annotations

import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from packages.research_core.contracts import (
    P4ContractError,
    P4_SCHEMA_VERSION,
    P4_STAGE_ID,
    validate_conflict_resolution_packet,
    validate_deep_data_completeness_check,
    validate_deep_snapshot,
    validate_metric_basis_comparable,
    validate_p4_evidence_packet,
    validate_p4_preconditions,
    validate_p4_progress_state,
)
from packages.research_core.pipeline.build_mcp_candidate_pool import run_candidate_pool
from packages.research_core.pipeline.build_route_matrix_confirmation import run_route_matrix_confirmation
from packages.research_core.pipeline.quick_market_check import run_quick_market_check


ROOT = Path(__file__).resolve().parents[1]
P1_FIXTURES = ROOT / "tests" / "fixtures" / "p1_quick_check"


class P4ContractTests(unittest.TestCase):
    def test_p4_preconditions_pass_after_p3_confirm(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = _seed_p3_confirmed_run(Path(tmpdir))

            validate_p4_preconditions(run_dir)

            self.assertFalse((run_dir / "review_voc").exists())
            self.assertFalse((run_dir / "evaluations").exists())
            self.assertFalse((run_dir / "analysis" / "report_data.json").exists())
            self.assertFalse(list((run_dir / "analysis").glob("*.html")) if (run_dir / "analysis").exists() else [])
            self.assertFalse(list((run_dir / "analysis").glob("*.xlsx")) if (run_dir / "analysis").exists() else [])

    def test_p4_preconditions_fail_when_route_matrix_not_confirmed(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = _seed_p3_confirmed_run(Path(tmpdir))
            route_matrix_path = run_dir / "route_matrix_confirm.json"
            route_matrix = _load_json(route_matrix_path)
            route_matrix["decision"] = "revise_candidate_pool"
            route_matrix_path.write_text(json.dumps(route_matrix, ensure_ascii=False, indent=2), encoding="utf-8")

            with self.assertRaises(P4ContractError):
                validate_p4_preconditions(run_dir)

    def test_p4_preconditions_fail_when_p3_completeness_has_blocker(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = _seed_p3_confirmed_run(Path(tmpdir))
            completeness_path = run_dir / "data_completeness_check.json"
            completeness = _load_json(completeness_path)
            completeness["overall_level"] = "blocker"
            completeness_path.write_text(json.dumps(completeness, ensure_ascii=False, indent=2), encoding="utf-8")

            with self.assertRaises(P4ContractError):
                validate_p4_preconditions(run_dir)

    def test_p4_preconditions_fail_when_stage_5_not_done(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = _seed_p3_confirmed_run(Path(tmpdir))
            progress_path = run_dir / "progress.json"
            progress = _load_json(progress_path)
            progress["stages"]["stage_5_route_matrix"]["status"] = "needs_user"
            progress_path.write_text(json.dumps(progress, ensure_ascii=False, indent=2), encoding="utf-8")

            with self.assertRaises(P4ContractError):
                validate_p4_preconditions(run_dir)

    def test_deep_snapshot_requires_routes_and_selected_routes(self) -> None:
        snapshot = _deep_snapshot("sellersprite")
        validate_deep_snapshot(snapshot, expected_source_name="sellersprite")

        snapshot["route_refs"] = []
        with self.assertRaises(P4ContractError):
            validate_deep_snapshot(snapshot, expected_source_name="sellersprite")

    def test_p4_evidence_packet_requires_metric_basis_on_items_and_metrics(self) -> None:
        packet = _p4_evidence_packet("market_structure_evidence_packet", "sellersprite", "sorftime")
        validate_p4_evidence_packet(packet, expected_primary_source="sellersprite")

        bad_item_packet = deepcopy(packet)
        bad_item_packet["evidence_items"][0].pop("metric_basis_ref")
        with self.assertRaises(P4ContractError):
            validate_p4_evidence_packet(bad_item_packet, expected_primary_source="sellersprite")

        bad_metric_packet = deepcopy(packet)
        bad_metric_packet["derived_metrics"]["generic_metric"].pop("metric_basis_ref")
        with self.assertRaises(P4ContractError):
            validate_p4_evidence_packet(bad_metric_packet, expected_primary_source="sellersprite")

    def test_metric_basis_comparable_ignores_source_identity_but_checks_basis_fields(self) -> None:
        sellersprite_basis = _metric_basis("sellersprite", "seller_tool")
        sorftime_basis = _metric_basis("sorftime", "sorftime_tool")

        result = validate_metric_basis_comparable(sellersprite_basis, sorftime_basis)

        self.assertTrue(result["comparable"], result)
        self.assertIn("source_name", result["required_fields"])
        self.assertNotIn("source_name", result["compared_fields"])

        sorftime_basis["data_window"] = "7d"
        result = validate_metric_basis_comparable(sellersprite_basis, sorftime_basis)
        self.assertFalse(result["comparable"])
        self.assertTrue(any(item["field"] == "data_window" for item in result["mismatches"]))

    def test_conflict_packet_keeps_non_comparable_basis_out_of_comparable_conflicts(self) -> None:
        packet = _conflict_packet_with_basis_mismatch()
        validate_conflict_resolution_packet(packet)

        bad_packet = deepcopy(packet)
        bad_packet["comparable_conflicts"].append(
            {
                "conflict_id": "conflict-generic-metric",
                "metric_name": "generic_metric",
                "field": "generic_metric",
                "severity": "material",
                "status": "needs_normalization",
                "primary_value": 100,
                "secondary_value": 130,
                "relative_delta": 0.3,
                "metric_basis_check_id": "basis-check-generic",
                "evidence_refs": ["conflict_review/conflict_resolution_packet.json#metric_basis_checks[0]"],
            }
        )

        with self.assertRaises(P4ContractError):
            validate_conflict_resolution_packet(bad_packet)

    def test_p4_progress_done_rejects_deep_completeness_blocker(self) -> None:
        progress = _progress_with_stage_6_done()
        deep_completeness = _deep_completeness_check("blocker")
        conflict = _conflict_packet("none")

        with self.assertRaises(P4ContractError):
            validate_p4_progress_state(progress, deep_completeness, conflict)

    def test_p4_progress_done_rejects_conflict_blocker(self) -> None:
        progress = _progress_with_stage_6_done()
        deep_completeness = _deep_completeness_check("acceptable")
        conflict = _conflict_packet("blocker")

        with self.assertRaises(P4ContractError):
            validate_p4_progress_state(progress, deep_completeness, conflict)

    def test_stage_6_done_with_blockers_fails_p4_preconditions(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = _seed_p3_confirmed_run(Path(tmpdir))
            conflict_dir = run_dir / "conflict_review"
            conflict_dir.mkdir()
            (conflict_dir / "deep_data_completeness_check.json").write_text(
                json.dumps(_deep_completeness_check("blocker"), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            (conflict_dir / "conflict_resolution_packet.json").write_text(
                json.dumps(_conflict_packet("none"), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            progress_path = run_dir / "progress.json"
            progress = _load_json(progress_path)
            progress["stages"][P4_STAGE_ID] = _stage_6_done_state()
            progress_path.write_text(json.dumps(progress, ensure_ascii=False, indent=2), encoding="utf-8")

            with self.assertRaises(P4ContractError):
                validate_p4_preconditions(run_dir)

    def test_valid_deep_completeness_and_conflict_packets_pass(self) -> None:
        validate_deep_data_completeness_check(_deep_completeness_check("warning"))
        validate_conflict_resolution_packet(_conflict_packet("warning"))


def _seed_p3_confirmed_run(root: Path) -> Path:
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
    run_quick_market_check(run_dir, snapshot_source_dir=P1_FIXTURES)
    run_candidate_pool(run_dir)
    run_route_matrix_confirmation(run_dir)
    return run_dir


def _deep_snapshot(source_name: str) -> dict:
    return {
        "schema_version": P4_SCHEMA_VERSION,
        "snapshot_id": f"{source_name}-deep-snapshot",
        "run_id": "20260624_generic_direction",
        "source_name": source_name,
        "source_doc_refs": ["docs/references/p4_mcp_capability_mapping.md#p4-recommended-split"],
        "route_refs": ["route_matrix_confirm.json#selected_routes[0]"],
        "selected_routes": ["<generic_route_ref>"],
        "tool_calls": [
            {
                "call_id": "call-generic-1",
                "tool_name": "generic_deep_tool",
                "params": {"input_ref": "route_matrix_confirm.json#selected_routes[0]"},
                "status": "success",
                "started_at": "2026-06-24T00:00:00Z",
                "finished_at": "2026-06-24T00:00:01Z",
            }
        ],
        "tool_results": [
            {
                "result_id": "result-generic-1",
                "call_id": "call-generic-1",
                "tool_name": "generic_deep_tool",
                "status": "success",
                "raw_result_ref": "mcp_snapshots/generic_raw.json#tool_results[0]",
            }
        ],
        "errors": [],
        "data_gaps": [],
        "created_at": "2026-06-24T00:00:01Z",
        "retry_policy": {"max_attempts": 1, "reuse_existing_snapshot": True},
        "force_refresh": False,
        "input_lineage": {"route_ref": "route_matrix_confirm.json#selected_routes[0]"},
    }


def _p4_evidence_packet(packet_id: str, primary_source: str, cross_source: str) -> dict:
    basis_id = f"{primary_source}_generic_basis"
    return {
        "schema_version": P4_SCHEMA_VERSION,
        "packet_id": packet_id,
        "run_id": "20260624_generic_direction",
        "primary_source": primary_source,
        "cross_check_sources": [cross_source],
        "source_snapshot_refs": [f"mcp_snapshots/{primary_source}_deep_snapshot.json#tool_results[0]"],
        "route_refs": ["route_matrix_confirm.json#selected_routes[0]"],
        "selected_routes": ["<generic_route_ref>"],
        "evidence_items": [
            {
                "item_id": "item-generic-1",
                "item_type": "generic_signal",
                "facts": {"generic_metric": {"value": 100}},
                "metric_basis_ref": basis_id,
                "evidence_refs": [f"mcp_snapshots/{primary_source}_deep_snapshot.json#tool_results[0]"],
                "source_refs": [f"mcp_snapshots/{primary_source}_deep_snapshot.json#tool_calls[0]"],
            }
        ],
        "derived_metrics": {
            "generic_metric": {
                "value": 100,
                "metric_basis_ref": basis_id,
                "evidence_refs": [f"mcp_snapshots/{primary_source}_deep_snapshot.json#tool_results[0]"],
            }
        },
        "metric_basis": {basis_id: _metric_basis(primary_source, f"{primary_source}_deep_tool")},
        "data_gaps": [],
        "blocking_gaps": [],
        "confidence": "medium",
        "source_refs": [f"mcp_snapshots/{primary_source}_deep_snapshot.json#tool_results[0]"],
        "created_at": "2026-06-24T00:00:01Z",
    }


def _deep_completeness_check(level: str) -> dict:
    return {
        "schema_version": P4_SCHEMA_VERSION,
        "packet_id": "deep_data_completeness_check",
        "run_id": "20260624_generic_direction",
        "source_packets": [
            "market_structure/market_structure_evidence_packet.json#packet",
            "search_demand/search_demand_evidence_packet.json#packet",
        ],
        "source_snapshots": [
            "mcp_snapshots/sellersprite_deep_snapshot.json#snapshot",
            "mcp_snapshots/sorftime_deep_snapshot.json#snapshot",
        ],
        "route_checks": [
            {
                "route_ref": "route_matrix_confirm.json#selected_routes[0]",
                "status": "checked",
                "gap_level": level,
                "evidence_refs": ["market_structure/market_structure_evidence_packet.json#evidence_items[0]"],
            }
        ],
        "source_coverage": {
            "sellersprite": {"status": "available"},
            "sorftime": {"status": "available"},
        },
        "metric_coverage": {"generic_metric": {"status": "covered"}},
        "node_mapping_status": {"generic_route": {"status": "mapped"}},
        "completeness_level": level,
        "data_gaps": [] if level != "blocker" else [{"field": "generic_metric", "severity": "blocker"}],
        "blocking_gaps": [] if level != "blocker" else [{"field": "generic_metric", "severity": "blocker"}],
        "required_next_actions": ["继续 P4 冲突复核"] if level != "blocker" else ["补齐 P4 深挖缺口后重跑"],
        "evidence_refs": ["market_structure/market_structure_evidence_packet.json#evidence_items[0]"],
        "created_at": "2026-06-24T00:00:02Z",
    }


def _conflict_packet(level: str) -> dict:
    packet = {
        "schema_version": P4_SCHEMA_VERSION,
        "packet_id": "conflict_resolution_packet",
        "run_id": "20260624_generic_direction",
        "source_packets": [
            "market_structure/market_structure_evidence_packet.json#packet",
            "search_demand/search_demand_evidence_packet.json#packet",
        ],
        "source_snapshots": [
            "mcp_snapshots/sellersprite_deep_snapshot.json#snapshot",
            "mcp_snapshots/sorftime_deep_snapshot.json#snapshot",
        ],
        "metric_basis_checks": [
            {
                "check_id": "basis-check-generic",
                "metric_name": "generic_metric",
                "primary_basis": _metric_basis("sellersprite", "seller_tool"),
                "secondary_basis": _metric_basis("sorftime", "sorftime_tool"),
            }
        ],
        "comparable_conflicts": [],
        "non_comparable_items": [],
        "basis_mismatches": [],
        "conflict_level": level,
        "blocking_gaps": [] if level != "blocker" else [{"field": "generic_metric", "severity": "blocking"}],
        "required_next_actions": ["进入 P5 前确认 P4 产物"] if level != "blocker" else ["先解决 P4 blocking conflict"],
        "evidence_refs": ["conflict_review/conflict_resolution_packet.json#metric_basis_checks[0]"],
        "created_at": "2026-06-24T00:00:03Z",
    }
    if level == "warning":
        packet["comparable_conflicts"].append(
            {
                "conflict_id": "conflict-generic-warning",
                "metric_name": "generic_metric",
                "field": "generic_metric",
                "severity": "minor",
                "status": "accepted",
                "primary_value": 100,
                "secondary_value": 104,
                "relative_delta": 0.04,
                "metric_basis_check_id": "basis-check-generic",
                "evidence_refs": ["conflict_review/conflict_resolution_packet.json#metric_basis_checks[0]"],
            }
        )
    return packet


def _conflict_packet_with_basis_mismatch() -> dict:
    packet = _conflict_packet("warning")
    packet["metric_basis_checks"][0]["secondary_basis"]["data_window"] = "7d"
    packet["metric_basis_checks"][0]["comparable"] = False
    packet["comparable_conflicts"] = []
    packet["basis_mismatches"] = [
        {
            "metric_name": "generic_metric",
            "field": "data_window",
            "mismatches": [{"field": "data_window", "primary": "30d", "secondary": "7d"}],
        }
    ]
    return packet


def _metric_basis(source_name: str, tool_name: str) -> dict:
    return {
        "source_name": source_name,
        "tool_name": tool_name,
        "site": "US",
        "marketplace": "US",
        "currency": "USD",
        "time_window": "30d",
        "data_window": "30d",
        "sample_scope": "<generic_sample_scope>",
        "metric_unit": "units",
        "aggregation_unit": "route",
        "parent_child_basis": "unknown",
        "collection_method": "deep_snapshot",
        "collected_at": "2026-06-24T00:00:01Z",
        "input_lineage": {"route_ref": "route_matrix_confirm.json#selected_routes[0]"},
    }


def _progress_with_stage_6_done() -> dict:
    return {
        "schema_version": "p0-contract-v1",
        "current_stage": P4_STAGE_ID,
        "stages": {
            "stage_5_route_matrix": {
                "status": "done",
                "attempts": 1,
                "input_artifacts": ["candidate_pool.json"],
                "output_artifacts": ["route_matrix_confirm.json", "data_completeness_check.json"],
                "validation_checks": [{"name": "p3_route_matrix", "pass": True}],
                "resume_policy": {"reuse_existing_artifacts": True, "allow_repeat_mcp_call": False},
            },
            P4_STAGE_ID: _stage_6_done_state(),
        },
        "updated_at": "2026-06-24T00:00:04Z",
        "global_blockers": [],
        "next_action": {"type": "next_stage", "description": "进入 P5 VOC Gate", "stage_id": "stage_7_voc_gate"},
        "completed_artifacts": [
            "route_matrix_confirm.json",
            "data_completeness_check.json",
            "conflict_review/deep_data_completeness_check.json",
            "conflict_review/conflict_resolution_packet.json",
        ],
    }


def _stage_6_done_state() -> dict:
    return {
        "status": "done",
        "attempts": 1,
        "input_artifacts": ["route_matrix_confirm.json", "data_completeness_check.json"],
        "output_artifacts": [
            "mcp_snapshots/sellersprite_deep_snapshot.json",
            "mcp_snapshots/sorftime_deep_snapshot.json",
            "market_structure/market_structure_evidence_packet.json",
            "search_demand/search_demand_evidence_packet.json",
            "conflict_review/deep_data_completeness_check.json",
            "conflict_review/conflict_resolution_packet.json",
        ],
        "validation_checks": [{"name": "p4_contracts", "pass": True}],
        "resume_policy": {"reuse_existing_artifacts": True, "allow_repeat_mcp_call": False},
    }


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))
