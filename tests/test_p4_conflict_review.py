from __future__ import annotations

import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from packages.research_core.contracts import (
    P4_STAGE_ID,
    validate_conflict_resolution_packet,
    validate_deep_data_completeness_check,
)
from packages.research_core.pipeline.build_conflict_review import (
    P4ConflictReviewError,
    run_conflict_review,
)
from packages.research_core.pipeline.build_mcp_candidate_pool import run_candidate_pool
from packages.research_core.pipeline.build_route_matrix_confirmation import run_route_matrix_confirmation
from packages.research_core.pipeline.build_sellersprite_deep_dive import run_sellersprite_deep_dive
from packages.research_core.pipeline.build_sorftime_deep_dive import run_sorftime_deep_dive
from packages.research_core.pipeline.quick_market_check import run_quick_market_check
from tests.agent_output_fixtures import write_agent_candidate_pool, write_agent_route_matrix


ROOT = Path(__file__).resolve().parents[1]
P1_FIXTURES = ROOT / "tests" / "fixtures" / "p1_quick_check"


class P4ConflictReviewTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self._tmp = Path(self._tmpdir.name)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def _seed_full_p4_run(self) -> Path:
        run_dir = _seed_p3_confirmed_run(self._tmp)
        ss_source = self._tmp / "ss_snapshot.json"
        sf_source = self._tmp / "sf_snapshot.json"
        ss_source.write_text(json.dumps(_valid_sellersprite_snapshot(), ensure_ascii=False, indent=2), encoding="utf-8")
        sf_source.write_text(json.dumps(_valid_sorftime_snapshot(), ensure_ascii=False, indent=2), encoding="utf-8")
        run_sellersprite_deep_dive(run_dir, snapshot_source=ss_source)
        run_sorftime_deep_dive(run_dir, snapshot_source=sf_source)
        return run_dir

    # ---- test 1: P3 confirmed run generates both completeness and conflict packets ----

    def test_confirmed_p3_run_generates_completeness_and_conflict_packet(self) -> None:
        run_dir = self._seed_full_p4_run()

        outputs = run_conflict_review(run_dir)

        completeness = _load_json(outputs["deep_data_completeness_check"])
        conflict = _load_json(outputs["conflict_resolution_packet"])
        progress = _load_json(outputs["progress"])

        validate_deep_data_completeness_check(completeness)
        validate_conflict_resolution_packet(conflict)

        self.assertEqual(completeness["packet_id"], "deep_data_completeness_check")
        self.assertIn("market_structure/market_structure_evidence_packet.json", completeness["source_packets"][0])
        self.assertIn("search_demand/search_demand_evidence_packet.json", completeness["source_packets"][1])
        self.assertIn("sellersprite_deep_snapshot.json", completeness["source_snapshots"][0])
        self.assertIn("sorftime_deep_snapshot.json", completeness["source_snapshots"][1])
        self.assertTrue(len(completeness["route_checks"]) >= 1)
        self.assertIn(completeness["completeness_level"], {"acceptable", "warning", "blocker"})

        self.assertEqual(conflict["packet_id"], "conflict_resolution_packet")
        self.assertTrue(len(conflict["metric_basis_checks"]) >= 1)
        self.assertIn(conflict["conflict_level"], {"none", "warning", "blocker"})

        self.assertEqual(progress["stages"][P4_STAGE_ID]["status"], "done")
        self.assertEqual(progress["next_action"]["stage_id"], "stage_7_voc_gate")
        self.assertIn("conflict_review/deep_data_completeness_check.json", progress["completed_artifacts"])
        self.assertIn("conflict_review/conflict_resolution_packet.json", progress["completed_artifacts"])

    # ---- test 2: route matrix not confirm blocks ----

    def test_route_matrix_not_confirm_blocks_without_p4_outputs(self) -> None:
        run_dir = self._seed_full_p4_run()
        route_path = run_dir / "route_matrix_confirm.json"
        route_packet = _load_json(route_path)
        route_packet["decision"] = "revise_candidate_pool"
        route_path.write_text(json.dumps(route_packet, ensure_ascii=False, indent=2), encoding="utf-8")

        with self.assertRaises(P4ConflictReviewError):
            run_conflict_review(run_dir)

        progress = _load_json(run_dir / "progress.json")
        self.assertIn(progress["stages"][P4_STAGE_ID]["status"], ("blocked", "failed"))
        self.assertFalse((run_dir / "conflict_review" / "deep_data_completeness_check.json").exists())
        self.assertFalse((run_dir / "conflict_review" / "conflict_resolution_packet.json").exists())

    # ---- test 3: P3 completeness blocker blocks ----

    def test_p3_completeness_blocker_blocks_without_p4_outputs(self) -> None:
        run_dir = self._seed_full_p4_run()
        completeness_path = run_dir / "data_completeness_check.json"
        completeness = _load_json(completeness_path)
        completeness["overall_level"] = "blocker"
        completeness_path.write_text(json.dumps(completeness, ensure_ascii=False, indent=2), encoding="utf-8")

        with self.assertRaises(P4ConflictReviewError):
            run_conflict_review(run_dir)

        progress = _load_json(run_dir / "progress.json")
        self.assertIn(progress["stages"][P4_STAGE_ID]["status"], ("blocked", "failed"))
        self.assertFalse((run_dir / "conflict_review" / "deep_data_completeness_check.json").exists())
        self.assertFalse((run_dir / "conflict_review" / "conflict_resolution_packet.json").exists())

    # ---- test 4: dual-source same-basis metrics enter comparable_conflicts ----

    def test_dual_source_same_basis_metrics_enter_comparable_conflicts(self) -> None:
        run_dir = self._seed_full_p4_run()
        outputs = run_conflict_review(run_dir)
        conflict = _load_json(outputs["conflict_resolution_packet"])

        self.assertIsInstance(conflict["comparable_conflicts"], list)
        self.assertIsInstance(conflict["metric_basis_checks"], list)
        for check in conflict["metric_basis_checks"]:
            if check.get("comparable"):
                self.assertTrue(check["comparability"]["comparable"])
                self.assertEqual(check["comparability"]["mismatches"], [])

    # ---- test 5: different basis auto-lands in basis_mismatches / non_comparable_items ----

    def test_different_basis_auto_lands_in_basis_mismatches(self) -> None:
        run_dir = self._seed_full_p4_run()
        market_path = run_dir / "market_structure" / "market_structure_evidence_packet.json"
        market_packet = _load_json(market_path)
        for basis in market_packet.get("metric_basis", {}).values():
            if isinstance(basis, dict):
                basis["data_window"] = "7d"
                basis["time_window"] = "7d"
                break
        market_path.write_text(json.dumps(market_packet, ensure_ascii=False, indent=2), encoding="utf-8")

        outputs = run_conflict_review(run_dir)
        conflict = _load_json(outputs["conflict_resolution_packet"])

        has_mismatch_or_non_comparable = bool(conflict.get("basis_mismatches") or conflict.get("non_comparable_items"))
        self.assertTrue(has_mismatch_or_non_comparable,
                        "different basis should produce basis_mismatches or non_comparable_items")

    # ---- test 6: completeness blocker or conflict blocker prevents stage_6 done ----

    def test_deep_completeness_blocker_prevents_stage_6_done(self) -> None:
        run_dir = self._seed_full_p4_run()
        # Remove one snapshot to trigger completeness blocker
        (run_dir / "mcp_snapshots" / "sorftime_deep_snapshot.json").unlink()
        # Write a broken snapshot
        broken = {
            "schema_version": "p4-deep-contract-v1",
            "snapshot_id": "broken",
            "run_id": "test",
            "source_name": "sorftime",
            "source_doc_refs": ["doc"],
            "route_refs": [],
            "selected_routes": [],
            "tool_calls": [],
            "tool_results": [],
            "errors": [],
            "data_gaps": [],
            "created_at": "2026-06-24T00:00:00Z",
            "retry_policy": {},
            "force_refresh": False,
            "input_lineage": {},
        }
        (run_dir / "mcp_snapshots" / "sorftime_deep_snapshot.json").write_text(
            json.dumps(broken, ensure_ascii=False, indent=2), encoding="utf-8")

        with self.assertRaises((P4ConflictReviewError, Exception)):
            run_conflict_review(run_dir)

        progress = _load_json(run_dir / "progress.json")
        stage_6 = progress["stages"].get(P4_STAGE_ID, {})
        self.assertNotEqual(stage_6.get("status"), "done")

    def test_conflict_blocker_prevents_stage_6_done(self) -> None:
        run_dir = self._seed_full_p4_run()
        # Artificially create a blocking conflict by skewing values beyond thresholds
        search_path = run_dir / "search_demand" / "search_demand_evidence_packet.json"
        search_packet = _load_json(search_path)
        for item in search_packet.get("evidence_items", []):
            if item.get("item_type") == "category_search":
                facts = item.setdefault("facts", {})
                norm = facts.setdefault("normalized_value", {})
                field_vals = norm.setdefault("field_values", {})
                field_vals["Top100产品月销量"] = "1"
                field_vals["平均价格"] = "999999"
                break
        search_path.write_text(json.dumps(search_packet, ensure_ascii=False, indent=2), encoding="utf-8")

        with self.assertRaises(P4ConflictReviewError):
            run_conflict_review(run_dir)

        progress = _load_json(run_dir / "progress.json")
        stage_6 = progress["stages"].get(P4_STAGE_ID, {})
        self.assertNotEqual(stage_6.get("status"), "done")

    # ---- test 7: does not generate VOC / evaluations / report / HTML / XLSX ----

    def test_p4_4_does_not_generate_downstream_artifacts(self) -> None:
        run_dir = self._seed_full_p4_run()
        run_conflict_review(run_dir)

        forbidden_paths = [
            run_dir / "review_voc",
            run_dir / "evaluations",
            run_dir / "analysis" / "report_data.json",
        ]
        self.assertFalse(any(path.exists() for path in forbidden_paths))
        self.assertFalse((run_dir / "analysis").exists() and list((run_dir / "analysis").glob("*.html")))
        self.assertFalse((run_dir / "analysis").exists() and list((run_dir / "analysis").glob("*.xlsx")))

    # ---- test 8: idempotent re-run when conflict_review artifacts exist ----

    def test_existing_conflict_review_artifacts_can_be_repeated(self) -> None:
        run_dir = self._seed_full_p4_run()

        outputs_1 = run_conflict_review(run_dir)
        outputs_2 = run_conflict_review(run_dir)

        c1 = _load_json(outputs_1["conflict_resolution_packet"])
        c2 = _load_json(outputs_2["conflict_resolution_packet"])
        self.assertEqual(c1["packet_id"], c2["packet_id"])
        self.assertEqual(c1["conflict_level"], c2["conflict_level"])

        p1 = _load_json(outputs_1["progress"])
        self.assertEqual(p1["stages"][P4_STAGE_ID]["status"], "done")

    # ---- test 9: artifacts pass contract validators ----

    def test_artifacts_pass_contract_validators(self) -> None:
        run_dir = self._seed_full_p4_run()
        outputs = run_conflict_review(run_dir)

        completeness = _load_json(outputs["deep_data_completeness_check"])
        conflict = _load_json(outputs["conflict_resolution_packet"])

        validate_deep_data_completeness_check(completeness)
        validate_conflict_resolution_packet(conflict)


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
            _tool_result("result-market", "call-market", "market_research",
                         {"code": "OK", "data": {"nodeIdPath": "<generic_node_path>", "totalUnits": 1402826, "avgPrice": 23.27, "avgRatings": 11994, "avgRating": 4.59}}),
            _tool_result("result-price", "call-price", "market_price_distribution",
                         {"code": "OK", "rows_sample": [{"priceRange": "<generic_price_band>", "products": 10, "units": 250, "revenue": 6000, "unitsRatio": 0.25}]}),
            _tool_result("result-seller", "call-seller", "market_seller_concentration",
                         {"code": "OK", "rows_sample": [{"sellerName": "<generic_seller>", "products": 5, "totalUnits": 300, "totalRevenue": 7200, "totalUnitsRatio": 0.3, "totalRevenueRatio": 0.31}]}),
            _tool_result("result-product", "call-product", "product_research",
                         {"code": "OK", "items_sample": [{"asin": "<generic_asin>", "brand": "<generic_brand>", "sellerName": "<generic_seller>", "price": 24.5, "ratings": 500, "rating": 4.4, "nodeIdPath": "<generic_node_path>", "totalUnits": 300}]}),
            _tool_result("result-asin", "call-asin", "asin_detail",
                         {"code": "OK", "data": {"asin": "<generic_asin>", "price": 34.99, "rating": 4.7, "ratings": 116354, "reviews": 80, "sellerName": "<generic_seller>", "brand": "<generic_brand>", "nodeIdPath": "<generic_node_path>", "parentAsin": "<generic_parent_asin>", "variations": 3, "fulfillment": "FBA"}}),
            _tool_result("result-ratings", "call-ratings", "market_ratings_count",
                         {"code": "OK", "rows_sample": [{"ratings": 11994, "rating": 4.59, "reviews": 80}]}),
            _tool_result("result-boundary", "call-boundary", "competitor_lookup",
                         {"code": "OK", "items_sample": [{"asin": "<generic_asin>", "nodeIdPath": "<generic_node_path>", "price": 24.5}]}),
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
            _tool_call("call-category-search", "category_search_from_product_name", {"amzSite": "US", "productName": "<generic_product_name>", "page": 1}),
            _tool_call("call-category-report", "category_report", {"amzSite": "US", "nodeId": "<generic_node_id>"}),
            _tool_call("call-category-trend", "category_trend", {"amzSite": "US", "nodeId": "<generic_node_id>", "trendIndex": "SalesCount"}),
            _tool_call("call-keyword-detail", "keyword_detail", {"keywordSupportSite": "US", "keyword": "<generic_keyword>"}),
            _tool_call("call-keyword-trend", "keyword_trend", {"keywordSupportSite": "US", "keyword": "<generic_keyword>"}),
            _tool_call("call-keyword-extends", "keyword_extends", {"keywordSupportSite": "US", "keyword": "<generic_keyword>"}),
            _tool_call("call-keyword-results", "keyword_search_results", {"keywordSupportSite": "US", "keyword": "<generic_keyword>"}),
            _tool_call("call-product-detail", "product_detail", {"amzSite": "US", "asin": "<generic_asin>"}),
            _tool_call("call-product-trend", "product_trend", {"amzSite": "US", "asin": "<generic_asin>"}),
            _tool_call("call-product-traffic", "product_traffic_terms", {"amzSite": "US", "asin": "<generic_asin>"}),
            _tool_call("call-competitor-keywords", "competitor_product_keywords", {"keywordSupportSite": "US", "asin": "<generic_asin>"}),
            _tool_call("call-product-reviews", "product_reviews", {"amzSite": "US", "asin": "<generic_asin>"}),
            _tool_call("call-hot-feature", "similar_product_feature", {"amzSite": "US", "productName": "<generic_product_name>"}),
        ],
        "tool_results": [
            _tool_result("result-category-search", "call-category-search", "category_search_from_product_name",
                         [{"nodeid": "3395091", "类目名称": "Generic Bottles", "Top100产品月销量": "1402826", "Top100产品月销额": "38113406.99", "平均星级": "4.59", "平均评价数量": "11994.52", "平均价格": "23.270000",
                           "销量前3的产品月销量占比": "47.67%", "销量前3的品牌月销量占比": "64.13%", "销量前3的卖家月销量占比": "84.24%"}]),
            _tool_result("result-category-report", "call-category-report", "category_report",
                         {"Top100产品_sample": [{"ASIN": "<generic_asin>", "月销量": "379466", "月销额": "13277515.34", "品牌": "<generic_brand>", "价格": 34.99, "评论数": 116354, "星级": 4.7, "卖家": "<generic_seller>"}],
                          "类目统计报告_sample": {"nodeid": "<generic_node_id>", "top100产品月销量": "3039427", "top100产品月销额": "84902657.07",
                                               "top3_product_sales_volume_share": "销量前三的产品月销量占比:37.22%", "top3_brands_sales_volume_share": "销量前三的品牌月销量占比:78.92%",
                                               "top3_seller_sales_volume_share": "销量前三的卖家月销量占比:92.35%", "amazonOwned_sales_volume_share": "亚马逊自营月销量占比:87.62%",
                                               "average_price": "销量前的80%产品平均价格：22.179", "median_price": "销量前的80%产品中位价格：9.49"}}),
            _tool_result("result-category-trend", "call-category-trend", "category_trend",
                         {"series_sample": ["2024年06月=1232094", "2026年06月=717226"]}),
            _tool_result("result-keyword-detail", "call-keyword-detail", "keyword_detail",
                         {"关键词": "<generic_keyword>", "周搜索量": "368705", "周搜索排名": "103", "月搜索量": "1397364", "推荐cpc竞价": "0.35", "词搜索量旺季": "8月", "搜索结果竞品数量": "144105",
                          "top5_product_sample": [{"asin": "<generic_asin>", "price": 34.97, "monthly_sales": "本产品月销量：372207（占比：12.49%）", "brand": "<generic_brand>", "seller": "<generic_seller>"}]}),
            _tool_result("result-keyword-trend", "call-keyword-trend", "keyword_trend",
                         {"关键词": "<generic_keyword>", "搜索量趋势_sample": ["2024年06月搜索量2364427", "2026年05月搜索量1526641"],
                          "搜索排名趋势_sample": ["2024年06月搜索排名29", "2026年05月搜索排名105"], "推荐竞价趋势_sample": ["2024年07月cpc推荐竞价0.90", "2026年05月cpc推荐竞价0.35"]}),
            _tool_result("result-keyword-extends", "call-keyword-extends", "keyword_extends",
                         [{"关键词": "<generic_keyword>", "周搜索量": 368705, "周搜索排名": 103, "月搜索量": 1397364, "cpc推荐竞价": "0.35", "季节性": "搜索量旺季:8月"}]),
            _tool_result("result-keyword-results", "call-keyword-results", "keyword_search_results",
                         {"Top100产品_sample": [{"ASIN": "<generic_asin>", "标题": "<generic_title>", "价格": 34.99, "月销量": 379466, "品牌": "<generic_brand>", "卖家": "<generic_seller>"}]}),
            _tool_result("result-product-detail", "call-product-detail", "product_detail",
                         {"ASIN": "<generic_asin>", "价格": 34.99, "月销量": "379466", "月销额": "13277515.34", "星级": 4.7, "评价数": 116354, "卖家": "<generic_seller>", "品牌": "<generic_brand>", "类目": "<generic_category>", "nodeId": "<generic_node_id>"}),
            _tool_result("result-product-trend", "call-product-trend", "product_trend",
                         {"series_sample": ["2024年06月=1232094", "2026年06月=717226"]}),
            _tool_result("result-product-traffic", "call-product-traffic", "product_traffic_terms",
                         {"keywords_sample": [{"关键词": "<generic_keyword>", "自然位": 3, "搜索量": 368705, "曝光时间": "2026-06"}]}),
            _tool_result("result-competitor-keywords", "call-competitor-keywords", "competitor_product_keywords",
                         {"keywords_sample": [{"关键词": "<generic_keyword>", "自然位": 8, "搜索量": 368705}]}),
            _tool_result("result-product-reviews", "call-product-reviews", "product_reviews",
                         {"reviews_sample": [{"rating": 4, "title": "<generic_title>", "date": "2026-06-01", "content": "<generic_review>"}]}),
            _tool_result("result-hot-feature", "call-hot-feature", "similar_product_feature",
                         {"features_sample": [{"特征": "<generic_feature>", "占比": "40%"}]}),
        ],
        "errors": [],
        "data_gaps": [],
        "created_at": "2026-06-24T00:00:00Z",
        "retry_policy": {"max_attempts": 1, "reuse_existing_snapshot": True, "allow_network_call": False},
        "force_refresh": False,
        "input_lineage": {"route_refs": ["route_matrix_confirm.json#selected_routes[0]"], "selected_routes": ["<generic_route_ref>"], "nodeId": "<generic_node_id>", "nodeIdPath": "<generic_node_path>", "seed_keyword": "<generic_keyword>", "amzSite": "US"},
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


def _tool_result(result_id: str, call_id: str, tool_name: str, raw_result: Any) -> dict:
    return {
        "result_id": result_id,
        "call_id": call_id,
        "tool_name": tool_name,
        "status": "success",
        "raw_result": raw_result,
    }


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))
