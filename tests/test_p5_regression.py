"""P5-4 regression: end-to-end cross-stage chain and boundary verification.

These tests complement the existing per-stage tests (70 tests across 3 files).
They focus on what per-stage tests can't cover: cross-stage data flow,
progress accumulation, and stage ordering enforcement.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

from packages.research_core.contracts import (
    P5_STAGE_ID,
    validate_review_asin_batch,
    validate_review_voc_package_p5,
    validate_voc_evidence_packet,
    validate_voc_gate,
)
from packages.research_core.pipeline.build_conflict_review import run_conflict_review
from packages.research_core.pipeline.build_mcp_candidate_pool import run_candidate_pool
from packages.research_core.pipeline.build_review_asin_batch import (
    P5AsinBatchError,
    run_review_asin_batch,
)
from packages.research_core.pipeline.build_review_voc_package import (
    P5VocPackageError,
    run_review_voc_package,
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
from packages.research_core.pipeline.build_voc_gate import (
    P5GateError,
    run_voc_gate,
)
from packages.research_core.pipeline.quick_market_check import run_quick_market_check


ROOT = Path(__file__).resolve().parents[1]
P1_FIXTURES = ROOT / "tests" / "fixtures" / "p1_quick_check"


class P5EndToEndChainTests(unittest.TestCase):
    """Run P5-1 → P5-2 → P5-3 sequentially, verify all 4 outputs and progress chain."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self._tmp = Path(self._tmpdir.name)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def _seed_p4_done(self) -> Path:
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

    # ── E2E golden path ─────────────────────────────────────────────

    def test_e2e_all_four_outputs_delivered(self) -> None:
        """P5-1 → P5-2 → P5-3 produces all 4 artifacts."""
        run_dir = self._seed_p4_done()

        # P5-1
        run_review_asin_batch(run_dir)
        self.assertTrue((run_dir / "review_voc" / "review_asin_batch.json").exists())

        # P5-2
        xlsx = self._write_review_xlsx(35)
        run_review_voc_package(run_dir, xlsx)
        self.assertTrue((run_dir / "review_voc" / "review_voc_package.json").exists())

        # P5-3
        run_voc_gate(run_dir)
        self.assertTrue((run_dir / "review_voc" / "voc_evidence_packet.json").exists())
        self.assertTrue((run_dir / "review_voc" / "voc_gate.json").exists())

    def test_e2e_all_outputs_pass_contract_validators(self) -> None:
        """All 4 E2E outputs pass their respective contract validators."""
        run_dir = self._seed_p4_done()
        run_review_asin_batch(run_dir)
        xlsx = self._write_review_xlsx(35)
        run_review_voc_package(run_dir, xlsx)
        run_voc_gate(run_dir)

        batch = load_json(run_dir / "review_voc" / "review_asin_batch.json")
        voc = load_json(run_dir / "review_voc" / "review_voc_package.json")
        evidence = load_json(run_dir / "review_voc" / "voc_evidence_packet.json")
        gate = load_json(run_dir / "review_voc" / "voc_gate.json")

        validate_review_asin_batch(batch)
        validate_review_voc_package_p5(voc)
        validate_voc_evidence_packet(evidence)
        validate_voc_gate(gate)

    # ── Progress chain ──────────────────────────────────────────────

    def test_progress_accumulates_completed_artifacts(self) -> None:
        """completed_artifacts accumulates all 4 outputs across stages."""
        run_dir = self._seed_p4_done()

        run_review_asin_batch(run_dir)
        p1 = load_json(run_dir / "progress.json")
        self.assertIn("review_voc/review_asin_batch.json", p1["completed_artifacts"])

        run_review_voc_package(run_dir, self._write_review_xlsx(35))
        p2 = load_json(run_dir / "progress.json")
        self.assertIn("review_voc/review_asin_batch.json", p2["completed_artifacts"])
        self.assertIn("review_voc/review_voc_package.json", p2["completed_artifacts"])

        run_voc_gate(run_dir)
        p3 = load_json(run_dir / "progress.json")
        self.assertIn("review_voc/review_asin_batch.json", p3["completed_artifacts"])
        self.assertIn("review_voc/review_voc_package.json", p3["completed_artifacts"])
        self.assertIn("review_voc/voc_evidence_packet.json", p3["completed_artifacts"])
        self.assertIn("review_voc/voc_gate.json", p3["completed_artifacts"])

    def test_progress_status_transitions(self) -> None:
        """stage_7_voc_gate transitions: pending → running → done."""
        run_dir = self._seed_p4_done()

        # P5-1: running
        run_review_asin_batch(run_dir)
        p1 = load_json(run_dir / "progress.json")
        self.assertEqual(p1["current_stage"], P5_STAGE_ID)
        stage_7 = p1["stages"].get(P5_STAGE_ID, {})
        self.assertEqual(stage_7.get("status"), "running")
        self.assertEqual(p1["next_action"].get("next_substage"), "P5-2")

        # P5-2: still running
        run_review_voc_package(run_dir, self._write_review_xlsx(35))
        p2 = load_json(run_dir / "progress.json")
        stage_7 = p2["stages"].get(P5_STAGE_ID, {})
        self.assertEqual(stage_7.get("status"), "running")
        self.assertEqual(p2["next_action"].get("next_substage"), "P5-3")

        # P5-3: done
        run_voc_gate(run_dir)
        p3 = load_json(run_dir / "progress.json")
        stage_7 = p3["stages"].get(P5_STAGE_ID, {})
        self.assertEqual(stage_7.get("status"), "done")

    def test_progress_next_action_flows_correctly(self) -> None:
        """next_action flows P5-2 → P5-3 → stage_7_report (or stop/need_more_reviews)."""
        run_dir = self._seed_p4_done()
        run_review_asin_batch(run_dir)
        run_review_voc_package(run_dir, self._write_review_xlsx(35))
        run_voc_gate(run_dir)

        p3 = load_json(run_dir / "progress.json")
        na = p3.get("next_action", {})

        # Must have a valid next_action type
        self.assertIn(na.get("type", ""),
                      {"generate_report", "proceed_with_warnings", "need_more_reviews", "stop"})

    # ── Cross-stage blocking ────────────────────────────────────────

    def test_p5_2_blocked_without_asin_batch(self) -> None:
        """P5-2 cannot run without P5-1 output."""
        run_dir = self._seed_p4_done()
        # Skip P5-1 — no review_asin_batch.json exists
        xlsx = self._write_review_xlsx(5)
        with self.assertRaises((P5VocPackageError, P5AsinBatchError)):
            run_review_voc_package(run_dir, xlsx)

    def test_p5_3_blocked_without_voc_package(self) -> None:
        """P5-3 cannot run without P5-2 output."""
        run_dir = self._seed_p4_done()
        run_review_asin_batch(run_dir)
        # Skip P5-2 — no review_voc_package.json exists
        with self.assertRaises(P5GateError):
            run_voc_gate(run_dir)

    def test_p5_3_blocked_without_p4_conflict_artifacts(self) -> None:
        """P5-3 cannot run without P4 conflict resolution outputs."""
        run_dir = self._seed_p4_done()
        run_review_asin_batch(run_dir)
        run_review_voc_package(run_dir, self._write_review_xlsx(35))
        # Remove P4 conflict artifact
        (run_dir / "conflict_review" / "conflict_resolution_packet.json").unlink()
        with self.assertRaises(P5GateError):
            run_voc_gate(run_dir)

    def test_p5_1_still_runs_without_p5_2_or_p5_3(self) -> None:
        """P5-1 is independent of P5-2/P5-3 — runs fine on its own."""
        run_dir = self._seed_p4_done()
        outputs = run_review_asin_batch(run_dir)
        self.assertTrue(outputs["asin_batch"].exists())

    # ── Cross-stage data flow integrity ─────────────────────────────

    def test_p5_2_package_references_p5_1_batch(self) -> None:
        """P5-2's source_batch_ref points to P5-1's batch."""
        run_dir = self._seed_p4_done()
        run_review_asin_batch(run_dir)
        run_review_voc_package(run_dir, self._write_review_xlsx(35))

        voc = load_json(run_dir / "review_voc" / "review_voc_package.json")
        batch_ref = voc["metadata"].get("source_batch_ref", "")
        self.assertIn("review_asin_batch.json", batch_ref)

    def test_p5_3_evidence_references_p5_2_package(self) -> None:
        """P5-3's evidence packet input_refs includes P5-2's package."""
        run_dir = self._seed_p4_done()
        run_review_asin_batch(run_dir)
        run_review_voc_package(run_dir, self._write_review_xlsx(35))
        run_voc_gate(run_dir)

        evidence = load_json(run_dir / "review_voc" / "voc_evidence_packet.json")
        input_paths = [ref.get("path", "") for ref in evidence.get("input_refs", [])]
        self.assertTrue(any("review_voc_package.json" in p for p in input_paths))

    def test_p5_3_gate_references_p5_3_evidence(self) -> None:
        """P5-3's gate input_refs includes the evidence packet."""
        run_dir = self._seed_p4_done()
        run_review_asin_batch(run_dir)
        run_review_voc_package(run_dir, self._write_review_xlsx(35))
        run_voc_gate(run_dir)

        gate = load_json(run_dir / "review_voc" / "voc_gate.json")
        input_refs = gate.get("input_refs", [])
        self.assertTrue(any("voc_evidence_packet.json" in ref for ref in input_refs))

    # ── Evidence chain integrity ────────────────────────────────────

    def test_evidence_pain_points_have_traceable_refs(self) -> None:
        """Every pain point's evidence_refs traces to review_id + asin + rating."""
        run_dir = self._seed_p4_done()
        run_review_asin_batch(run_dir)
        run_review_voc_package(run_dir, self._write_review_xlsx(35))
        run_voc_gate(run_dir)

        evidence = load_json(run_dir / "review_voc" / "voc_evidence_packet.json")
        for pp in evidence.get("pain_points_by_dimension", []):
            for ref in pp.get("evidence_refs", []):
                self.assertTrue(ref.get("review_id"), f"missing review_id in {pp.get('dimension')}")
                self.assertTrue(ref.get("asin"), f"missing asin in {pp.get('dimension')}")
                self.assertIsNotNone(ref.get("rating"), f"missing rating in {pp.get('dimension')}")
                self.assertTrue(ref.get("source_path"), f"missing source_path in {pp.get('dimension')}")

    def test_gate_decisions_have_actionable_next_steps(self) -> None:
        """Every gate has non-empty required_next_actions."""
        run_dir = self._seed_p4_done()
        run_review_asin_batch(run_dir)
        run_review_voc_package(run_dir, self._write_review_xlsx(35))
        run_voc_gate(run_dir)

        gate = load_json(run_dir / "review_voc" / "voc_gate.json")
        actions = gate.get("required_next_actions", [])
        self.assertGreater(len(actions), 0)
        # All actions are non-empty strings
        for action in actions:
            self.assertTrue(action.strip())

    # ── Scope: no cross-contamination ───────────────────────────────

    def test_p5_2_does_not_produce_p5_3_artifacts(self) -> None:
        """P5-2 leaves no voc_gate or voc_evidence behind."""
        run_dir = self._seed_p4_done()
        run_review_asin_batch(run_dir)
        run_review_voc_package(run_dir, self._write_review_xlsx(35))
        rv = run_dir / "review_voc"
        self.assertFalse((rv / "voc_gate.json").exists())
        self.assertFalse((rv / "voc_evidence_packet.json").exists())

    def test_p5_does_not_produce_report_or_web_artifacts(self) -> None:
        """No HTML, XLSX, or report artifacts in review_voc/ or analysis/."""
        run_dir = self._seed_p4_done()
        run_review_asin_batch(run_dir)
        run_review_voc_package(run_dir, self._write_review_xlsx(35))
        run_voc_gate(run_dir)

        rv = run_dir / "review_voc"
        for name in ["voc_report.md", "voc_summary.md", "voc_evidence.xlsx",
                     "report.html", "report.xlsx"]:
            self.assertFalse((rv / name).exists(), f"{name} should not exist in review_voc/")

        analysis = run_dir / "analysis"
        if analysis.exists():
            html_files = list(analysis.glob("*.html"))
            xlsx_files = list(analysis.glob("*.xlsx"))
            self.assertEqual(len(html_files), 0, "no HTML in analysis/")
            self.assertEqual(len(xlsx_files), 0, "no XLSX in analysis/")


# ── Fixtures ───────────────────────────────────────────────────────────

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
        "errors": [], "data_gaps": [], "created_at": "2026-06-24T00:00:00Z",
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
        "errors": [], "data_gaps": [], "created_at": "2026-06-24T00:00:00Z",
        "retry_policy": {"max_attempts": 1, "reuse_existing_snapshot": True, "allow_network_call": False},
        "force_refresh": False,
        "input_lineage": {"route_refs": ["route_matrix_confirm.json#selected_routes[0]"], "selected_routes": ["<generic_route_ref>"], "nodeId": "<generic_node_id>", "nodeIdPath": "<generic_node_path>", "seed_keyword": "<generic_keyword>", "amzSite": "US"},
    }


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))
