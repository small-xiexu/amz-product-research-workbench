"""P4 regression tests covering end-to-end pipeline, CLI smoke, progress chain, and blocker coverage."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from packages.research_core.contracts import (
    P4_STAGE_ID,
    validate_conflict_resolution_packet,
    validate_deep_data_completeness_check,
    validate_deep_snapshot,
    validate_p4_evidence_packet,
)
from packages.research_core.pipeline.build_conflict_review import run_conflict_review
from packages.research_core.pipeline.build_mcp_candidate_pool import run_candidate_pool
from packages.research_core.pipeline.build_route_matrix_confirmation import run_route_matrix_confirmation
from packages.research_core.pipeline.build_sellersprite_deep_dive import (
    P4SellerSpriteError,
    run_sellersprite_deep_dive,
)
from packages.research_core.pipeline.build_sorftime_deep_dive import (
    P4SorftimeError,
    run_sorftime_deep_dive,
)
from packages.research_core.pipeline.quick_market_check import run_quick_market_check
from tests.agent_output_fixtures import write_agent_candidate_pool, write_agent_route_matrix


ROOT = Path(__file__).resolve().parents[1]
P1_FIXTURES = ROOT / "tests" / "fixtures" / "p1_quick_check"


class P4EndToEndTests(unittest.TestCase):
    """End-to-end tests: P1→P2→P3→P4-2→P4-3→P4-4 full pipeline."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self._tmp = Path(self._tmpdir.name)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def _seed_p3_confirmed(self) -> Path:
        run_dir = self._tmp / "20260624_generic_direction"
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

    def _write_sellersprite_snapshot(self) -> Path:
        src = self._tmp / "ss_snap.json"
        src.write_text(json.dumps(_valid_sellersprite_snapshot(), ensure_ascii=False, indent=2), encoding="utf-8")
        return src

    def _write_sorftime_snapshot(self) -> Path:
        src = self._tmp / "sf_snap.json"
        src.write_text(json.dumps(_valid_sorftime_snapshot(), ensure_ascii=False, indent=2), encoding="utf-8")
        return src

    # ---- End-to-end tests ----

    def test_full_pipeline_p1_through_p4_4_produces_all_artifacts(self) -> None:
        """P1→P2→P3→P4-2→P4-3→P4-4 full pipeline produces all 6 P4 artifacts."""
        run_dir = self._seed_p3_confirmed()

        # P4-2 SellerSprite
        ss_outputs = run_sellersprite_deep_dive(run_dir, snapshot_source=self._write_sellersprite_snapshot())
        self.assertTrue((run_dir / "mcp_snapshots" / "sellersprite_deep_snapshot.json").exists())
        self.assertTrue((run_dir / "market_structure" / "market_structure_evidence_packet.json").exists())
        ss_progress = _load_json(ss_outputs["progress"])
        self.assertEqual(ss_progress["stages"][P4_STAGE_ID]["status"], "running")
        self.assertEqual(ss_progress["next_action"]["next_substage"], "P4-3")

        # P4-3 Sorftime
        sf_outputs = run_sorftime_deep_dive(run_dir, snapshot_source=self._write_sorftime_snapshot())
        self.assertTrue((run_dir / "mcp_snapshots" / "sorftime_deep_snapshot.json").exists())
        self.assertTrue((run_dir / "search_demand" / "search_demand_evidence_packet.json").exists())
        sf_progress = _load_json(sf_outputs["progress"])
        self.assertEqual(sf_progress["stages"][P4_STAGE_ID]["status"], "running")
        self.assertEqual(sf_progress["next_action"]["next_substage"], "P4-4")

        # P4-4 Conflict Review
        cr_outputs = run_conflict_review(run_dir)
        self.assertTrue((run_dir / "conflict_review" / "deep_data_completeness_check.json").exists())
        self.assertTrue((run_dir / "conflict_review" / "conflict_resolution_packet.json").exists())
        cr_progress = _load_json(cr_outputs["progress"])
        self.assertEqual(cr_progress["stages"][P4_STAGE_ID]["status"], "done")
        self.assertEqual(cr_progress["next_action"]["stage_id"], "stage_7_voc_gate")

        # All artifacts pass contract validation
        validate_deep_snapshot(_load_json(run_dir / "mcp_snapshots" / "sellersprite_deep_snapshot.json"), expected_source_name="sellersprite")
        validate_deep_snapshot(_load_json(run_dir / "mcp_snapshots" / "sorftime_deep_snapshot.json"), expected_source_name="sorftime")
        validate_p4_evidence_packet(_load_json(run_dir / "market_structure" / "market_structure_evidence_packet.json"), expected_primary_source="sellersprite")
        validate_p4_evidence_packet(_load_json(run_dir / "search_demand" / "search_demand_evidence_packet.json"), expected_primary_source="sorftime")
        validate_deep_data_completeness_check(_load_json(run_dir / "conflict_review" / "deep_data_completeness_check.json"))
        validate_conflict_resolution_packet(_load_json(run_dir / "conflict_review" / "conflict_resolution_packet.json"))

    def test_full_pipeline_stage_6_stays_running_until_p4_4_completes(self) -> None:
        """P4-2 and P4-3 must NOT mark stage_6 as done; only P4-4 marks it done."""
        run_dir = self._seed_p3_confirmed()

        run_sellersprite_deep_dive(run_dir, snapshot_source=self._write_sellersprite_snapshot())
        p1 = _load_json(run_dir / "progress.json")
        self.assertNotEqual(p1["stages"][P4_STAGE_ID]["status"], "done")

        run_sorftime_deep_dive(run_dir, snapshot_source=self._write_sorftime_snapshot())
        p2 = _load_json(run_dir / "progress.json")
        self.assertNotEqual(p2["stages"][P4_STAGE_ID]["status"], "done")

        run_conflict_review(run_dir)
        p3 = _load_json(run_dir / "progress.json")
        self.assertEqual(p3["stages"][P4_STAGE_ID]["status"], "done")
        self.assertEqual(p3["next_action"]["stage_id"], "stage_7_voc_gate")

    # ---- Blocker tests ----

    def test_missing_sellersprite_snapshot_blocks_p4_2(self) -> None:
        """Missing SS snapshot file blocks P4-2 without marking stage_6 done."""
        run_dir = self._seed_p3_confirmed()
        progress_before = _load_json(run_dir / "progress.json")

        with self.assertRaises(P4SellerSpriteError):
            run_sellersprite_deep_dive(run_dir)

        progress = _load_json(run_dir / "progress.json")
        self.assertNotEqual(progress["stages"].get(P4_STAGE_ID, {}).get("status"), "done")

    def test_missing_sorftime_snapshot_blocks_p4_3(self) -> None:
        """Missing SF snapshot file blocks P4-3 without marking stage_6 done."""
        run_dir = self._seed_p3_confirmed()
        run_sellersprite_deep_dive(run_dir, snapshot_source=self._write_sellersprite_snapshot())

        # Remove snapshot source before running
        with self.assertRaises(P4SorftimeError):
            run_sorftime_deep_dive(run_dir)

        progress = _load_json(run_dir / "progress.json")
        self.assertNotEqual(progress["stages"].get(P4_STAGE_ID, {}).get("status"), "done")

    def test_missing_evidence_packet_blocks_p4_4(self) -> None:
        """Missing a deep evidence packet blocks P4-4 without marking stage_6 done."""
        run_dir = self._seed_p3_confirmed()
        run_sellersprite_deep_dive(run_dir, snapshot_source=self._write_sellersprite_snapshot())
        # Don't run P4-3 — search_demand evidence packet won't exist

        from packages.research_core.pipeline.build_conflict_review import P4ConflictReviewError
        with self.assertRaises(P4ConflictReviewError):
            run_conflict_review(run_dir)

        progress = _load_json(run_dir / "progress.json")
        self.assertNotEqual(progress["stages"].get(P4_STAGE_ID, {}).get("status"), "done")

    # ---- Scope verification ----

    def test_full_pipeline_produces_no_downstream_artifacts(self) -> None:
        """Full P4 pipeline must not produce VOC, evaluations, report, HTML, or XLSX."""
        run_dir = self._seed_p3_confirmed()
        run_sellersprite_deep_dive(run_dir, snapshot_source=self._write_sellersprite_snapshot())
        run_sorftime_deep_dive(run_dir, snapshot_source=self._write_sorftime_snapshot())
        run_conflict_review(run_dir)

        forbidden = [
            "review_voc",
            "evaluations",
        ]
        for name in forbidden:
            self.assertFalse((run_dir / name).exists(), f"forbidden path exists: {name}")

        analysis = run_dir / "analysis"
        if analysis.exists():
            self.assertFalse(list(analysis.glob("*.html")), "HTML should not exist in P4")
            self.assertFalse(list(analysis.glob("*.xlsx")), "XLSX should not exist in P4")
            report_data = analysis / "report_data.json"
            # May have been seeded by P0/P1/P2/P3 but P4-4 should not create it
            self.assertFalse(report_data.exists(), "report_data.json should not exist in P4 pipeline")

    def test_full_pipeline_artifacts_pass_contract_validators(self) -> None:
        """All 6 P4 artifacts pass their respective contract validators."""
        run_dir = self._seed_p3_confirmed()
        run_sellersprite_deep_dive(run_dir, snapshot_source=self._write_sellersprite_snapshot())
        run_sorftime_deep_dive(run_dir, snapshot_source=self._write_sorftime_snapshot())
        run_conflict_review(run_dir)

        validate_deep_snapshot(_load_json(run_dir / "mcp_snapshots" / "sellersprite_deep_snapshot.json"), expected_source_name="sellersprite")
        validate_p4_evidence_packet(_load_json(run_dir / "market_structure" / "market_structure_evidence_packet.json"), expected_primary_source="sellersprite")
        validate_deep_snapshot(_load_json(run_dir / "mcp_snapshots" / "sorftime_deep_snapshot.json"), expected_source_name="sorftime")
        validate_p4_evidence_packet(_load_json(run_dir / "search_demand" / "search_demand_evidence_packet.json"), expected_primary_source="sorftime")
        validate_deep_data_completeness_check(_load_json(run_dir / "conflict_review" / "deep_data_completeness_check.json"))
        validate_conflict_resolution_packet(_load_json(run_dir / "conflict_review" / "conflict_resolution_packet.json"))

    # ---- Progress chain verification ----

    def test_progress_completed_artifacts_accumulate_correctly(self) -> None:
        """completed_artifacts list grows correctly across P4-2 → P4-3 → P4-4."""
        run_dir = self._seed_p3_confirmed()

        run_sellersprite_deep_dive(run_dir, snapshot_source=self._write_sellersprite_snapshot())
        p1 = _load_json(run_dir / "progress.json")
        self.assertIn("mcp_snapshots/sellersprite_deep_snapshot.json", p1["completed_artifacts"])
        self.assertIn("market_structure/market_structure_evidence_packet.json", p1["completed_artifacts"])

        run_sorftime_deep_dive(run_dir, snapshot_source=self._write_sorftime_snapshot())
        p2 = _load_json(run_dir / "progress.json")
        self.assertIn("mcp_snapshots/sorftime_deep_snapshot.json", p2["completed_artifacts"])
        self.assertIn("search_demand/search_demand_evidence_packet.json", p2["completed_artifacts"])

        run_conflict_review(run_dir)
        p3 = _load_json(run_dir / "progress.json")
        self.assertIn("conflict_review/deep_data_completeness_check.json", p3["completed_artifacts"])
        self.assertIn("conflict_review/conflict_resolution_packet.json", p3["completed_artifacts"])

        # All 6 P4 artifacts should be present
        self.assertIn("mcp_snapshots/sellersprite_deep_snapshot.json", p3["completed_artifacts"])
        self.assertIn("mcp_snapshots/sorftime_deep_snapshot.json", p3["completed_artifacts"])

    def test_progress_global_blockers_cleared_on_success(self) -> None:
        """P4-4 success should clear global_blockers."""
        run_dir = self._seed_p3_confirmed()
        run_sellersprite_deep_dive(run_dir, snapshot_source=self._write_sellersprite_snapshot())
        run_sorftime_deep_dive(run_dir, snapshot_source=self._write_sorftime_snapshot())
        run_conflict_review(run_dir)

        progress = _load_json(run_dir / "progress.json")
        self.assertEqual(progress.get("global_blockers", []), [])
        self.assertEqual(progress.get("current_stage"), P4_STAGE_ID)


class P4CliSmokeTests(unittest.TestCase):
    """CLI smoke tests: run through scripts/build_*.py with temporary run directories."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self._tmp = Path(self._tmpdir.name)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def _seed_p3_confirmed(self) -> Path:
        run_dir = self._tmp / "20260624_generic_direction"
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

    def _write_sellersprite_snapshot(self) -> Path:
        src = self._tmp / "ss_snap.json"
        src.write_text(json.dumps(_valid_sellersprite_snapshot(), ensure_ascii=False, indent=2), encoding="utf-8")
        return src

    def _write_sorftime_snapshot(self) -> Path:
        src = self._tmp / "sf_snap.json"
        src.write_text(json.dumps(_valid_sorftime_snapshot(), ensure_ascii=False, indent=2), encoding="utf-8")
        return src

    def _run_cli(self, script_name: str, *args: str) -> subprocess.CompletedProcess[str]:
        script_path = ROOT / "scripts" / script_name
        cmd = [sys.executable, str(script_path)] + list(args)
        return subprocess.run(cmd, capture_output=True, text=True, timeout=60)

    def test_cli_sellersprite_deep_dive_smoke(self) -> None:
        """scripts/build_sellersprite_deep_dive.py runs successfully."""
        run_dir = self._seed_p3_confirmed()
        ss_src = self._write_sellersprite_snapshot()

        result = self._run_cli("build_sellersprite_deep_dive.py", str(run_dir), "--snapshot-source", str(ss_src))
        self.assertEqual(result.returncode, 0, f"CLI failed: {result.stderr}")

        self.assertTrue((run_dir / "mcp_snapshots" / "sellersprite_deep_snapshot.json").exists())
        self.assertTrue((run_dir / "market_structure" / "market_structure_evidence_packet.json").exists())

    def test_cli_sorftime_deep_dive_smoke(self) -> None:
        """scripts/build_sorftime_deep_dive.py runs successfully."""
        run_dir = self._seed_p3_confirmed()
        run_sellersprite_deep_dive(run_dir, snapshot_source=self._write_sellersprite_snapshot())
        sf_src = self._write_sorftime_snapshot()

        result = self._run_cli("build_sorftime_deep_dive.py", str(run_dir), "--snapshot-source", str(sf_src))
        self.assertEqual(result.returncode, 0, f"CLI failed: {result.stderr}")

        self.assertTrue((run_dir / "mcp_snapshots" / "sorftime_deep_snapshot.json").exists())
        self.assertTrue((run_dir / "search_demand" / "search_demand_evidence_packet.json").exists())

    def test_cli_conflict_review_smoke(self) -> None:
        """scripts/build_conflict_review.py runs successfully."""
        run_dir = self._seed_p3_confirmed()
        run_sellersprite_deep_dive(run_dir, snapshot_source=self._write_sellersprite_snapshot())
        run_sorftime_deep_dive(run_dir, snapshot_source=self._write_sorftime_snapshot())

        result = self._run_cli("build_conflict_review.py", str(run_dir))
        self.assertEqual(result.returncode, 0, f"CLI failed: {result.stderr}")

        self.assertTrue((run_dir / "conflict_review" / "deep_data_completeness_check.json").exists())
        self.assertTrue((run_dir / "conflict_review" / "conflict_resolution_packet.json").exists())

    def test_cli_full_chain_smoke(self) -> None:
        """Full CLI chain: build_sellersprite → build_sorftime → build_conflict_review."""
        run_dir = self._seed_p3_confirmed()
        ss_src = self._write_sellersprite_snapshot()
        sf_src = self._write_sorftime_snapshot()

        r1 = self._run_cli("build_sellersprite_deep_dive.py", str(run_dir), "--snapshot-source", str(ss_src))
        self.assertEqual(r1.returncode, 0, f"SS CLI failed: {r1.stderr}")

        r2 = self._run_cli("build_sorftime_deep_dive.py", str(run_dir), "--snapshot-source", str(sf_src))
        self.assertEqual(r2.returncode, 0, f"SF CLI failed: {r2.stderr}")

        r3 = self._run_cli("build_conflict_review.py", str(run_dir))
        self.assertEqual(r3.returncode, 0, f"CR CLI failed: {r3.stderr}")

        # All 6 artifacts are on disk
        self.assertTrue((run_dir / "mcp_snapshots" / "sellersprite_deep_snapshot.json").exists())
        self.assertTrue((run_dir / "market_structure" / "market_structure_evidence_packet.json").exists())
        self.assertTrue((run_dir / "mcp_snapshots" / "sorftime_deep_snapshot.json").exists())
        self.assertTrue((run_dir / "search_demand" / "search_demand_evidence_packet.json").exists())
        self.assertTrue((run_dir / "conflict_review" / "deep_data_completeness_check.json").exists())
        self.assertTrue((run_dir / "conflict_review" / "conflict_resolution_packet.json").exists())

        progress = _load_json(run_dir / "progress.json")
        self.assertEqual(progress["stages"][P4_STAGE_ID]["status"], "done")
        self.assertEqual(progress["next_action"]["stage_id"], "stage_7_voc_gate")


# ---- Shared fixtures (generic, no hard-coded ASINs/keywords/brands) ----

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


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))
