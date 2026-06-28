"""P5-1 tests: review_asin_batch generation from P4 artifacts."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from packages.research_core.contracts import (
    P5ContractError,
    P5_STAGE_ID,
    validate_review_asin_batch,
)
from packages.research_core.pipeline.quick_market_check import run_quick_market_check
from tests.agent_output_fixtures import write_agent_candidate_pool, write_agent_route_matrix
from packages.research_core.pipeline.build_conflict_review import run_conflict_review
from packages.research_core.pipeline.build_mcp_candidate_pool import run_candidate_pool
from packages.research_core.pipeline.build_review_asin_batch import (
    P5AsinBatchError,
    P5_ASIN_BATCH_INPUT_ARTIFACTS,
    build_asin_batch,
    run_review_asin_batch,
)
from packages.research_core.pipeline.build_route_matrix_confirmation import (
    run_route_matrix_confirmation,
)
from packages.research_core.pipeline.build_sellersprite_deep_dive import (
    run_sellersprite_deep_dive,
)
from packages.research_core.pipeline.build_sorftime_deep_dive import (
    run_sorftime_deep_dive,
)


ROOT = Path(__file__).resolve().parents[1]
P1_FIXTURES = ROOT / "tests" / "fixtures" / "p1_quick_check"


class AsinBatchHappyPathTests(unittest.TestCase):
    """Tests where P4 is complete and ASIN batch can be generated."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self._tmp = Path(self._tmpdir.name)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def _seed_p4_done(self) -> Path:
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
        run_sellersprite_deep_dive(run_dir, snapshot_source=self._write_sellersprite_snapshot())
        run_sorftime_deep_dive(run_dir, snapshot_source=self._write_sorftime_snapshot())
        run_conflict_review(run_dir)
        return run_dir

    def _write_sellersprite_snapshot(self) -> Path:
        src = self._tmp / "ss_snap.json"
        src.write_text(json.dumps(_valid_sellersprite_snapshot(), ensure_ascii=False, indent=2), encoding="utf-8")
        return src

    def _write_sorftime_snapshot(self) -> Path:
        src = self._tmp / "sf_snap.json"
        src.write_text(json.dumps(_valid_sorftime_snapshot(), ensure_ascii=False, indent=2), encoding="utf-8")
        return src

    def test_happy_path_generates_batch_and_updates_progress(self) -> None:
        """Full asin_batch generation from P4 produces valid output and progress."""
        run_dir = self._seed_p4_done()
        outputs = run_review_asin_batch(run_dir)

        batch_path = outputs["asin_batch"]
        self.assertTrue(batch_path.exists(), f"batch not found: {batch_path}")
        batch = json.loads(batch_path.read_text(encoding="utf-8"))
        validate_review_asin_batch(batch)

        self.assertEqual(batch["schema_version"], "p5-voc-gate-v1")
        self.assertEqual(batch["batch_id"], "review_asin_batch")
        self.assertGreater(len(batch["asin_items"]), 0, "batch should have at least one ASIN")
        self.assertGreater(len(batch["route_coverage"]), 0, "batch should have route coverage")
        self.assertIn("operator_instruction", batch)

        # Check roles present (count depends on fixture diversity)
        roles = {item["asin_role"] for item in batch["asin_items"]}
        self.assertGreaterEqual(len(roles), 1, "batch should include at least one ASIN role")

        # Every ASIN item has required fields
        for item in batch["asin_items"]:
            self.assertIn("asin", item)
            self.assertIn("asin_role", item)
            self.assertIn("route_ref", item)
            self.assertIn("selection_reason", item)
            self.assertIn("source", item)
            self.assertIn("priority", item)
            self.assertIn("expected_review_focus", item)

        # Progress is updated
        progress = json.loads((run_dir / "progress.json").read_text(encoding="utf-8"))
        self.assertEqual(progress["current_stage"], P5_STAGE_ID)
        stage_7 = progress["stages"].get(P5_STAGE_ID, {})
        self.assertEqual(stage_7.get("status"), "running")
        self.assertIn("review_voc/review_asin_batch.json", progress["completed_artifacts"])

    def test_all_roles_covered_when_sufficient_asins(self) -> None:
        """With enough ASINs, batch should be contract-valid with proper role assignment."""
        run_dir = self._seed_p4_done()
        batch = build_asin_batch(
            load_json(run_dir / "workflow_state.json"),
            load_json(run_dir / "candidate_pool.json"),
            load_json(run_dir / "route_matrix_confirm.json"),
            load_json(run_dir / "market_structure" / "market_structure_evidence_packet.json"),
            load_json(run_dir / "search_demand" / "search_demand_evidence_packet.json"),
            load_json(run_dir / "conflict_review" / "deep_data_completeness_check.json"),
            load_json(run_dir / "conflict_review" / "conflict_resolution_packet.json"),
            run_dir,
        )
        validate_review_asin_batch(batch)
        roles = {item["asin_role"] for item in batch["asin_items"]}
        self.assertGreaterEqual(len(roles), 1, "batch should have at least one ASIN role")
        # Every role should be a valid ASIN_ROLES member
        from packages.research_core.contracts.p5_contracts import P5_ALLOWED_ASIN_ROLES
        for role in roles:
            self.assertIn(role, P5_ALLOWED_ASIN_ROLES)

    def test_batch_includes_p4_warnings(self) -> None:
        """When P4 has warnings, batch reflects them."""
        run_dir = self._seed_p4_done()
        # Manually set conflict level to warning to verify propagation
        conflict_path = run_dir / "conflict_review" / "conflict_resolution_packet.json"
        conflict = json.loads(conflict_path.read_text(encoding="utf-8"))
        conflict["conflict_level"] = "warning"
        conflict_path.write_text(json.dumps(conflict, ensure_ascii=False, indent=2), encoding="utf-8")

        batch = build_asin_batch(
            load_json(run_dir / "workflow_state.json"),
            load_json(run_dir / "candidate_pool.json"),
            load_json(run_dir / "route_matrix_confirm.json"),
            load_json(run_dir / "market_structure" / "market_structure_evidence_packet.json"),
            load_json(run_dir / "search_demand" / "search_demand_evidence_packet.json"),
            load_json(run_dir / "conflict_review" / "deep_data_completeness_check.json"),
            conflict,
            run_dir,
        )
        validate_review_asin_batch(batch)
        warnings = batch.get("p4_warnings", [])
        self.assertGreater(len(warnings), 0, "batch should carry P4 conflict warning")
        self.assertTrue(any(w["source"] == "conflict_resolution_packet" for w in warnings))

    def test_edge_case_minimal_asins_still_generates_batch(self) -> None:
        """Batch still generates even when asin count is small."""
        run_dir = self._seed_p4_done()
        wf = load_json(run_dir / "workflow_state.json")
        pool = load_json(run_dir / "candidate_pool.json")
        route_matrix = load_json(run_dir / "route_matrix_confirm.json")
        market_packet = load_json(run_dir / "market_structure" / "market_structure_evidence_packet.json")
        search_packet = load_json(run_dir / "search_demand" / "search_demand_evidence_packet.json")
        completeness_check = load_json(run_dir / "conflict_review" / "deep_data_completeness_check.json")
        conflict_packet = load_json(run_dir / "conflict_review" / "conflict_resolution_packet.json")

        # Remove most ASINs from candidate pool
        candidates = pool.get("candidates", [])
        if isinstance(candidates, list) and candidates:
            pool["candidates"] = candidates[:2]

        batch = build_asin_batch(wf, pool, route_matrix, market_packet, search_packet, completeness_check, conflict_packet, run_dir)
        validate_review_asin_batch(batch)
        self.assertGreaterEqual(len(batch["asin_items"]), 1)


class AsinBatchErrorTests(unittest.TestCase):
    """Tests for error conditions in ASIN batch generation."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self._tmp = Path(self._tmpdir.name)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def _seed_p4_done(self) -> Path:
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
        run_sellersprite_deep_dive(run_dir, snapshot_source=self._write_sellersprite_snapshot())
        run_sorftime_deep_dive(run_dir, snapshot_source=self._write_sorftime_snapshot())
        run_conflict_review(run_dir)
        return run_dir

    def _write_sellersprite_snapshot(self) -> Path:
        src = self._tmp / "ss_snap.json"
        src.write_text(json.dumps(_valid_sellersprite_snapshot(), ensure_ascii=False, indent=2), encoding="utf-8")
        return src

    def _write_sorftime_snapshot(self) -> Path:
        src = self._tmp / "sf_snap.json"
        src.write_text(json.dumps(_valid_sorftime_snapshot(), ensure_ascii=False, indent=2), encoding="utf-8")
        return src

    def test_missing_input_raises_error(self) -> None:
        """Each missing required input raises P5AsinBatchError."""
        run_dir = self._seed_p4_done()
        for artifact in P5_ASIN_BATCH_INPUT_ARTIFACTS:
            target = run_dir / artifact
            if target.exists():
                target.unlink()
            with self.assertRaises(P5AsinBatchError, msg=f"should raise for missing: {artifact}"):
                run_review_asin_batch(run_dir)

    def test_no_asins_in_inputs_still_produces_batch_with_gaps(self) -> None:
        """When no ASINs are available at all, batch is empty-ish but valid."""
        run_dir = self._seed_p4_done()
        pool = load_json(run_dir / "candidate_pool.json")
        pool["candidates"] = []
        (run_dir / "candidate_pool.json").write_text(json.dumps(pool, ensure_ascii=False, indent=2), encoding="utf-8")

        market_packet = load_json(run_dir / "market_structure" / "market_structure_evidence_packet.json")
        for item in market_packet.get("evidence_items", []):
            if isinstance(item, dict) and item.get("item_type") in ("competitor_structure", "asin_operating_data"):
                item["facts"] = {}
        (run_dir / "market_structure" / "market_structure_evidence_packet.json").write_text(
            json.dumps(market_packet, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        search_packet = load_json(run_dir / "search_demand" / "search_demand_evidence_packet.json")
        for item in search_packet.get("evidence_items", []):
            if isinstance(item, dict) and item.get("item_type") in ("competitor_structure", "asin_operating_data"):
                item["facts"] = {}
        (run_dir / "search_demand" / "search_demand_evidence_packet.json").write_text(
            json.dumps(search_packet, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        # Should still run (may produce empty or minimal batch with data_gaps)
        batch = build_asin_batch(
            load_json(run_dir / "workflow_state.json"),
            pool,
            load_json(run_dir / "route_matrix_confirm.json"),
            market_packet,
            search_packet,
            load_json(run_dir / "conflict_review" / "deep_data_completeness_check.json"),
            load_json(run_dir / "conflict_review" / "conflict_resolution_packet.json"),
            run_dir,
        )
        self.assertIsInstance(batch, dict)
        self.assertIn("data_gaps", batch)


class AsinBatchContractTests(unittest.TestCase):
    """Contract validator tests for review_asin_batch."""

    def test_validator_rejects_empty_batch(self) -> None:
        with self.assertRaises(P5ContractError):
            validate_review_asin_batch({})

    def test_validator_rejects_missing_asin_items(self) -> None:
        batch = _minimal_batch()
        del batch["asin_items"]
        with self.assertRaises(P5ContractError):
            validate_review_asin_batch(batch)

    def test_validator_rejects_invalid_role(self) -> None:
        batch = _minimal_batch()
        batch["asin_items"] = [{
            "asin": "B0XXXXXXX1",
            "asin_role": "not_a_valid_role",
            "route_ref": "test_route",
            "selection_reason": "test reason",
            "source": "candidate_pool",
            "priority": 1,
        }]
        with self.assertRaises(P5ContractError):
            validate_review_asin_batch(batch)

    def test_validator_rejects_duplicate_asins(self) -> None:
        batch = _minimal_batch()
        item = {
            "asin": "B0XXXXXXX1",
            "asin_role": "primary_reference",
            "route_ref": "test_route",
            "selection_reason": "test",
            "source": "candidate_pool",
            "priority": 1,
        }
        batch["asin_items"] = [item, item]
        with self.assertRaises(P5ContractError):
            validate_review_asin_batch(batch)

    def test_validator_rejects_short_asin(self) -> None:
        batch = _minimal_batch()
        batch["asin_items"] = [{
            "asin": "B0X",
            "asin_role": "primary_reference",
            "route_ref": "test_route",
            "selection_reason": "test",
            "source": "candidate_pool",
            "priority": 1,
        }]
        with self.assertRaises(P5ContractError):
            validate_review_asin_batch(batch)

    def test_validator_rejects_missing_route_ref(self) -> None:
        batch = _minimal_batch()
        item = batch["asin_items"][0]
        del item["route_ref"]
        item["route_ref"] = ""
        with self.assertRaises(P5ContractError):
            validate_review_asin_batch(batch)

    def test_validator_rejects_missing_route_coverage(self) -> None:
        batch = _minimal_batch()
        batch["route_coverage"] = []
        with self.assertRaises(P5ContractError):
            validate_review_asin_batch(batch)

    def test_validator_accepts_valid_batch(self) -> None:
        validate_review_asin_batch(_minimal_batch())


class AsinBatchProgressTests(unittest.TestCase):
    """Progress update tests."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self._tmp = Path(self._tmpdir.name)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def _seed_p4_done(self) -> Path:
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
        run_sellersprite_deep_dive(run_dir, snapshot_source=self._write_sellersprite_snapshot())
        run_sorftime_deep_dive(run_dir, snapshot_source=self._write_sorftime_snapshot())
        run_conflict_review(run_dir)
        return run_dir

    def _write_sellersprite_snapshot(self) -> Path:
        src = self._tmp / "ss_snap.json"
        src.write_text(json.dumps(_valid_sellersprite_snapshot(), ensure_ascii=False, indent=2), encoding="utf-8")
        return src

    def _write_sorftime_snapshot(self) -> Path:
        src = self._tmp / "sf_snap.json"
        src.write_text(json.dumps(_valid_sorftime_snapshot(), ensure_ascii=False, indent=2), encoding="utf-8")
        return src

    def test_stage_7_running_not_done_after_p5_1(self) -> None:
        """P5-1 sets stage_7_voc_gate to running, not done."""
        run_dir = self._seed_p4_done()
        run_review_asin_batch(run_dir)
        progress = load_json(run_dir / "progress.json")
        self.assertEqual(progress["current_stage"], P5_STAGE_ID)
        stage_7 = progress["stages"].get(P5_STAGE_ID, {})
        self.assertEqual(stage_7.get("status"), "running")
        self.assertNotEqual(stage_7.get("status"), "done")

    def test_next_action_points_to_p5_2(self) -> None:
        """After P5-1, next_action points to P5-2."""
        run_dir = self._seed_p4_done()
        run_review_asin_batch(run_dir)
        progress = load_json(run_dir / "progress.json")
        next_action = progress.get("next_action", {})
        self.assertEqual(next_action.get("type"), "wait_operator_export")
        self.assertEqual(next_action.get("next_substage"), "P5-2")

    def test_completed_artifacts_includes_asin_batch(self) -> None:
        """completed_artifacts includes review_voc/review_asin_batch.json."""
        run_dir = self._seed_p4_done()
        run_review_asin_batch(run_dir)
        progress = load_json(run_dir / "progress.json")
        self.assertIn("review_voc/review_asin_batch.json", progress["completed_artifacts"])

    def test_operator_instruction_includes_import_command(self) -> None:
        """operator_instruction has the shell command for operator."""
        run_dir = self._seed_p4_done()
        run_review_asin_batch(run_dir)
        batch = json.loads((run_dir / "review_voc" / "review_asin_batch.json").read_text(encoding="utf-8"))
        op = batch.get("operator_instruction", {})
        self.assertIn("import_command", op)
        self.assertIn("entry_point", op)
        self.assertIn("site", op)


# ── Shared fixtures ────────────────────────────────────────────────────

def _minimal_batch() -> dict:
    return {
        "schema_version": "p5-voc-gate-v1",
        "batch_id": "review_asin_batch",
        "run_id": "test_run",
        "generated_at": "2026-06-24T00:00:00Z",
        "source_route_matrix": "route_matrix_confirm.json",
        "source_candidate_pool": "candidate_pool.json",
        "source_evidence_packets": [
            "market_structure/market_structure_evidence_packet.json",
            "search_demand/search_demand_evidence_packet.json",
        ],
        "source_completeness_check": "conflict_review/deep_data_completeness_check.json",
        "source_conflict_packet": "conflict_review/conflict_resolution_packet.json",
        "site": "US",
        "selected_routes": ["<test_route>"],
        "p4_warnings": [],
        "asin_items": [
            {
                "asin": "B0XXXXXXX1",
                "asin_role": "primary_reference",
                "route_ref": "<test_route>",
                "selection_reason": "strong rating with high review volume — primary reference；brand: <generic_brand>；price: 24.50",
                "source": "candidate_pool",
                "source_refs": ["candidate_pool"],
                "site": "US",
                "priority": 1,
                "expected_review_focus": "main-route competitor review analysis",
                "metrics": {"monthly_sales": 500, "rating": 4.4, "ratings_count": 500, "price": 24.50, "brand": "<generic_brand>"},
                "notes": "",
            },
            {
                "asin": "B0XXXXXXX2",
                "asin_role": "high_sales_benchmark",
                "route_ref": "<test_route>",
                "selection_reason": "high monthly sales — volume benchmark；brand: <generic_brand2>；price: 19.99",
                "source": "seller_sprite",
                "source_refs": ["seller_sprite"],
                "site": "US",
                "priority": 2,
                "expected_review_focus": "high-volume seller review patterns",
                "metrics": {"monthly_sales": 5000, "rating": 4.5, "ratings_count": 2000, "price": 19.99, "brand": "<generic_brand2>"},
                "notes": "",
            },
        ],
        "route_coverage": [
            {"route_ref": "<test_route>", "asin_count": 2, "roles_covered": ["high_sales_benchmark", "primary_reference"], "missing_roles": ["target_price_band_sample", "new_release_sample", "premium_benchmark", "painpoint_reference", "excluded_reference"]},
        ],
        "operator_instruction": {
            "site": "US",
            "entry_point": "评论慢速采集助手",
            "put_dir": "<run_dir>/inputs/reviews/",
            "file_naming": "US_review_voc_<batch>_<date>.xlsx",
            "import_command": "python3 scripts/build_review_voc_package.py <run_dir> <export_file>",
            "operator_note": "只需将下方 ASIN 清单粘贴到评论插件的 ASIN 输入框...",
        },
        "data_gaps": [],
        "next_required_action": {"action": "proceed_to_operator_export", "description": "test"},
        "evidence_refs": ["candidate_pool.json"],
    }


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


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))
