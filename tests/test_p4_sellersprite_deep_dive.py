from __future__ import annotations

import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from packages.research_core.contracts import validate_deep_snapshot, validate_p4_evidence_packet
from packages.research_core.pipeline.build_mcp_candidate_pool import run_candidate_pool
from packages.research_core.pipeline.build_route_matrix_confirmation import run_route_matrix_confirmation
from packages.research_core.pipeline.build_sellersprite_deep_dive import (
    P4SellerSpriteError,
    run_sellersprite_deep_dive,
)
from packages.research_core.pipeline.quick_market_check import run_quick_market_check
from tests.agent_output_fixtures import write_agent_candidate_pool, write_agent_route_matrix


ROOT = Path(__file__).resolve().parents[1]
P1_FIXTURES = ROOT / "tests" / "fixtures" / "p1_quick_check"


class P4SellerSpriteDeepDiveTests(unittest.TestCase):
    def test_confirmed_p3_run_builds_sellersprite_market_structure_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = _seed_p3_confirmed_run(Path(tmpdir))
            snapshot_source = Path(tmpdir) / "generic_sellersprite_deep_snapshot.json"
            snapshot_source.write_text(
                json.dumps(_valid_sellersprite_snapshot(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            outputs = run_sellersprite_deep_dive(run_dir, snapshot_source=snapshot_source)
            snapshot = _load_json(outputs["sellersprite_deep_snapshot"])
            packet = _load_json(outputs["market_structure_evidence_packet"])
            progress = _load_json(outputs["progress"])

        validate_deep_snapshot(snapshot, expected_source_name="sellersprite")
        validate_p4_evidence_packet(packet, expected_primary_source="sellersprite")
        self.assertEqual(packet["packet_id"], "market_structure_evidence_packet")
        self.assertEqual(packet["primary_source"], "sellersprite")
        self.assertIn("sorftime", packet["cross_check_sources"])
        self.assertEqual(
            {item["item_type"] for item in packet["evidence_items"]},
            {
                "market_capacity",
                "price_band",
                "seller_concentration",
                "competitor_structure",
                "asin_operating_data",
                "review_threshold",
                "category_boundary",
            },
        )
        self.assertEqual(progress["stages"]["stage_6_deep_dive"]["status"], "running")
        self.assertEqual(progress["next_action"]["next_substage"], "P4-3")
        self.assertIn("mcp_snapshots/sellersprite_deep_snapshot.json", progress["completed_artifacts"])
        self.assertIn("market_structure/market_structure_evidence_packet.json", progress["completed_artifacts"])

    def test_route_matrix_not_confirmed_blocks_without_p4_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = _seed_p3_confirmed_run(Path(tmpdir))
            route_path = run_dir / "route_matrix_confirm.json"
            route_packet = _load_json(route_path)
            route_packet["decision"] = "revise_candidate_pool"
            route_path.write_text(json.dumps(route_packet, ensure_ascii=False, indent=2), encoding="utf-8")

            with self.assertRaises(P4SellerSpriteError):
                run_sellersprite_deep_dive(run_dir, snapshot_source=_write_snapshot_source(Path(tmpdir)))

            progress = _load_json(run_dir / "progress.json")

        self.assertEqual(progress["stages"]["stage_6_deep_dive"]["status"], "blocked")
        self.assertFalse((run_dir / "mcp_snapshots" / "sellersprite_deep_snapshot.json").exists())
        self.assertFalse((run_dir / "market_structure" / "market_structure_evidence_packet.json").exists())

    def test_p3_completeness_blocker_blocks_without_p4_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = _seed_p3_confirmed_run(Path(tmpdir))
            completeness_path = run_dir / "data_completeness_check.json"
            completeness = _load_json(completeness_path)
            completeness["overall_level"] = "blocker"
            completeness_path.write_text(json.dumps(completeness, ensure_ascii=False, indent=2), encoding="utf-8")

            with self.assertRaises(P4SellerSpriteError):
                run_sellersprite_deep_dive(run_dir, snapshot_source=_write_snapshot_source(Path(tmpdir)))

            progress = _load_json(run_dir / "progress.json")

        self.assertEqual(progress["stages"]["stage_6_deep_dive"]["status"], "blocked")
        self.assertFalse((run_dir / "mcp_snapshots" / "sellersprite_deep_snapshot.json").exists())
        self.assertFalse((run_dir / "market_structure" / "market_structure_evidence_packet.json").exists())

    def test_empty_snapshot_fields_are_recorded_as_data_gaps(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = _seed_p3_confirmed_run(Path(tmpdir))
            snapshot = _valid_sellersprite_snapshot()
            snapshot["tool_results"][1]["raw_result"] = {"code": "OK", "rows_sample": [{"priceRange": None, "products": None}]}
            snapshot_source = _write_snapshot_source(Path(tmpdir), snapshot)

            outputs = run_sellersprite_deep_dive(run_dir, snapshot_source=snapshot_source)
            packet = _load_json(outputs["market_structure_evidence_packet"])

        self.assertTrue(
            any(
                gap.get("type") == "empty_or_missing_fields" and gap.get("evidence_type") == "price_band"
                for gap in packet["data_gaps"]
                if isinstance(gap, dict)
            )
        )

    def test_tool_failure_is_recorded_as_errors_and_data_gaps(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = _seed_p3_confirmed_run(Path(tmpdir))
            snapshot = _valid_sellersprite_snapshot()
            snapshot["tool_calls"][2]["status"] = "error"
            snapshot["tool_results"][2]["status"] = "error"
            snapshot["tool_results"][2]["normalized_preview"] = {"error": "generic failure"}
            snapshot["errors"] = [
                {
                    "type": "tool_unavailable",
                    "tool_name": "market_seller_concentration",
                    "message": "generic failure",
                }
            ]
            snapshot_source = _write_snapshot_source(Path(tmpdir), snapshot)

            outputs = run_sellersprite_deep_dive(run_dir, snapshot_source=snapshot_source)
            saved_snapshot = _load_json(outputs["sellersprite_deep_snapshot"])
            packet = _load_json(outputs["market_structure_evidence_packet"])

        self.assertTrue(saved_snapshot["errors"])
        self.assertTrue(
            any(
                gap.get("type") in {"snapshot_error", "tool_result_unavailable"}
                for gap in packet["data_gaps"]
                if isinstance(gap, dict)
            )
        )

    def test_every_evidence_item_and_metric_has_metric_basis_ref(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = _seed_p3_confirmed_run(Path(tmpdir))
            outputs = run_sellersprite_deep_dive(run_dir, snapshot_source=_write_snapshot_source(Path(tmpdir)))
            packet = _load_json(outputs["market_structure_evidence_packet"])

        self.assertTrue(all(item.get("metric_basis_ref") for item in packet["evidence_items"]))
        self.assertTrue(all(metric.get("metric_basis_ref") for metric in packet["derived_metrics"].values()))

    def test_p4_2_does_not_generate_downstream_or_other_source_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = _seed_p3_confirmed_run(Path(tmpdir))
            run_sellersprite_deep_dive(run_dir, snapshot_source=_write_snapshot_source(Path(tmpdir)))
            progress = _load_json(run_dir / "progress.json")

        forbidden_paths = [
            run_dir / "mcp_snapshots" / "sorftime_deep_snapshot.json",
            run_dir / "search_demand" / "search_demand_evidence_packet.json",
            run_dir / "conflict_review" / "deep_data_completeness_check.json",
            run_dir / "conflict_review" / "conflict_resolution_packet.json",
            run_dir / "review_voc",
            run_dir / "evaluations",
            run_dir / "analysis" / "report_data.json",
        ]
        self.assertFalse(any(path.exists() for path in forbidden_paths))
        self.assertFalse((run_dir / "analysis").exists() and list((run_dir / "analysis").glob("*.html")))
        self.assertFalse((run_dir / "analysis").exists() and list((run_dir / "analysis").glob("*.xlsx")))
        self.assertNotEqual(progress["next_action"].get("stage_id"), "stage_7_voc_gate")
        self.assertNotIn("conflict_review/conflict_resolution_packet.json", progress.get("completed_artifacts", []))

    def test_existing_sellersprite_snapshot_is_reused_when_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = _seed_p3_confirmed_run(Path(tmpdir))
            target = run_dir / "mcp_snapshots" / "sellersprite_deep_snapshot.json"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(_valid_sellersprite_snapshot(), ensure_ascii=False, indent=2), encoding="utf-8")

            outputs = run_sellersprite_deep_dive(run_dir)
            snapshot = _load_json(outputs["sellersprite_deep_snapshot"])

        validate_deep_snapshot(snapshot, expected_source_name="sellersprite")

    def test_probe_raw_snapshot_can_be_normalized(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = _seed_p3_confirmed_run(Path(tmpdir))
            probe_source = Path(tmpdir) / "generic_probe_raw.json"
            probe_source.write_text(json.dumps(_generic_probe_raw(), ensure_ascii=False, indent=2), encoding="utf-8")

            outputs = run_sellersprite_deep_dive(run_dir, snapshot_source=probe_source)
            snapshot = _load_json(outputs["sellersprite_deep_snapshot"])
            packet = _load_json(outputs["market_structure_evidence_packet"])

        validate_deep_snapshot(snapshot, expected_source_name="sellersprite")
        validate_p4_evidence_packet(packet, expected_primary_source="sellersprite")
        self.assertTrue(snapshot["data_gaps"])


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
    write_agent_candidate_pool(run_dir)
    run_candidate_pool(run_dir)
    write_agent_route_matrix(run_dir)
    run_route_matrix_confirmation(run_dir)
    return run_dir


def _write_snapshot_source(root: Path, snapshot: dict | None = None) -> Path:
    source = root / "generic_sellersprite_deep_snapshot.json"
    source.write_text(json.dumps(snapshot or _valid_sellersprite_snapshot(), ensure_ascii=False, indent=2), encoding="utf-8")
    return source


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
            _tool_call("call-market", "market_research", {"marketplace": "US", "nodeIdPath": "<generic_node_path>"}),
            _tool_call("call-price", "market_price_distribution", {"marketplace": "US", "nodeIdPath": "<generic_node_path>"}),
            _tool_call("call-seller", "market_seller_concentration", {"marketplace": "US", "nodeIdPath": "<generic_node_path>"}),
            _tool_call("call-product", "product_research", {"marketplace": "US", "keyword": "<generic_keyword>"}),
            _tool_call("call-asin", "asin_detail", {"marketplace": "US", "asin": "<generic_asin>"}),
            _tool_call("call-ratings", "market_ratings_count", {"marketplace": "US", "nodeIdPath": "<generic_node_path>"}),
            _tool_call("call-boundary", "competitor_lookup", {"marketplace": "US", "asins": ["<generic_asin>"]}),
        ],
        "tool_results": [
            _tool_result(
                "result-market",
                "call-market",
                "market_research",
                {
                    "code": "OK",
                    "data": {
                        "nodeIdPath": "<generic_node_path>",
                        "totalUnits": 1000,
                        "avgPrice": 24.5,
                        "avgRatings": 500,
                        "avgRating": 4.4,
                    },
                },
            ),
            _tool_result(
                "result-price",
                "call-price",
                "market_price_distribution",
                {
                    "code": "OK",
                    "rows_sample": [
                        {
                            "priceRange": "<generic_price_band>",
                            "products": 10,
                            "units": 250,
                            "revenue": 6000,
                            "unitsRatio": 0.25,
                        }
                    ],
                },
            ),
            _tool_result(
                "result-seller",
                "call-seller",
                "market_seller_concentration",
                {
                    "code": "OK",
                    "rows_sample": [
                        {
                            "sellerName": "<generic_seller>",
                            "products": 5,
                            "totalUnits": 300,
                            "totalRevenue": 7200,
                            "totalUnitsRatio": 0.3,
                            "totalRevenueRatio": 0.31,
                        }
                    ],
                },
            ),
            _tool_result(
                "result-product",
                "call-product",
                "product_research",
                {
                    "code": "OK",
                    "items_sample": [
                        {
                            "asin": "<generic_asin>",
                            "brand": "<generic_brand>",
                            "sellerName": "<generic_seller>",
                            "price": 24.5,
                            "ratings": 500,
                            "rating": 4.4,
                            "nodeIdPath": "<generic_node_path>",
                            "totalUnits": 300,
                        }
                    ],
                },
            ),
            _tool_result(
                "result-asin",
                "call-asin",
                "asin_detail",
                {
                    "code": "OK",
                    "data": {
                        "asin": "<generic_asin>",
                        "price": 24.5,
                        "rating": 4.4,
                        "ratings": 500,
                        "reviews": 80,
                        "sellerName": "<generic_seller>",
                        "brand": "<generic_brand>",
                        "nodeIdPath": "<generic_node_path>",
                        "parentAsin": "<generic_parent_asin>",
                        "variations": 3,
                        "fulfillment": "FBA",
                    },
                },
            ),
            _tool_result(
                "result-ratings",
                "call-ratings",
                "market_ratings_count",
                {
                    "code": "OK",
                    "rows_sample": [{"ratings": 500, "rating": 4.4, "reviews": 80}],
                },
            ),
            _tool_result(
                "result-boundary",
                "call-boundary",
                "competitor_lookup",
                {
                    "code": "OK",
                    "items_sample": [{"asin": "<generic_asin>", "nodeIdPath": "<generic_node_path>", "price": 24.5}],
                },
            ),
        ],
        "errors": [],
        "data_gaps": [],
        "created_at": "2026-06-24T00:00:00Z",
        "retry_policy": {"max_attempts": 1, "reuse_existing_snapshot": True, "allow_network_call": False},
        "force_refresh": False,
        "input_lineage": {
            "route_refs": ["route_matrix_confirm.json#selected_routes[0]"],
            "selected_routes": ["<generic_route_ref>"],
            "nodeIdPath": "<generic_node_path>",
        },
    }


def _generic_probe_raw() -> dict:
    return {
        "probe_run_id": "generic_probe",
        "created_at": "2026-06-24T00:00:00Z",
        "source_name": "sellersprite_mcp",
        "probe_inputs": {
            "site": "US",
            "keyword": "<generic_keyword>",
            "asin": "<generic_asin>",
            "node_id_path": "<generic_node_path>",
        },
        "tool_calls": [
            {
                "tool_name": "mcp__sellersprite_mcp.market_research",
                "status": "success_with_gaps",
                "request": {"marketplace": "US", "nodeIdPath": "<generic_node_path>"},
                "raw_result_sample": {"code": "OK", "data": {"totalUnits": 1000, "avgPrice": 24.5, "nodeIdPath": "<generic_node_path>"}},
                "missing_or_unstable_fields": ["totalAmount"],
            },
            {
                "tool_name": "mcp__sellersprite_mcp.market_price_distribution",
                "status": "success_with_bucket_label_gap",
                "request": {"marketplace": "US", "nodeIdPath": "<generic_node_path>"},
                "raw_result_sample": {"code": "OK", "rows_sample": [{"priceRange": None, "products": 10, "units": 250}]},
                "missing_or_unstable_fields": ["priceRange"],
            },
            {
                "tool_name": "mcp__sellersprite_mcp.market_seller_concentration",
                "status": "failed",
                "request": {"marketplace": "US", "nodeIdPath": "<generic_node_path>"},
                "error": {"type": "tool_unavailable", "message": "generic failure"},
            },
            {
                "tool_name": "mcp__sellersprite_mcp.asin_detail",
                "status": "success",
                "request": {"marketplace": "US", "asin": "<generic_asin>"},
                "raw_result_sample": {"code": "OK", "data": {"asin": "<generic_asin>", "price": 24.5, "ratings": 500, "rating": 4.4, "nodeIdPath": "<generic_node_path>"}},
            },
        ],
    }


def _tool_call(call_id: str, tool_name: str, params: dict) -> dict:
    return {
        "call_id": call_id,
        "tool_name": tool_name,
        "params": params,
        "status": "success",
        "started_at": "2026-06-24T00:00:00Z",
        "finished_at": "2026-06-24T00:00:01Z",
    }


def _tool_result(result_id: str, call_id: str, tool_name: str, raw_result: dict) -> dict:
    return {
        "result_id": result_id,
        "call_id": call_id,
        "tool_name": tool_name,
        "status": "success",
        "raw_result": raw_result,
    }


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))
