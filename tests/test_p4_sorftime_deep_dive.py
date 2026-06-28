from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from packages.research_core.contracts import validate_deep_snapshot, validate_p4_evidence_packet
from packages.research_core.pipeline.build_mcp_candidate_pool import run_candidate_pool
from packages.research_core.pipeline.build_route_matrix_confirmation import run_route_matrix_confirmation
from packages.research_core.pipeline.build_sorftime_deep_dive import (
    P4SorftimeError,
    run_sorftime_deep_dive,
)
from packages.research_core.pipeline.quick_market_check import run_quick_market_check
from tests.agent_output_fixtures import write_agent_candidate_pool, write_agent_route_matrix


ROOT = Path(__file__).resolve().parents[1]
P1_FIXTURES = ROOT / "tests" / "fixtures" / "p1_quick_check"


class P4SorftimeDeepDiveTests(unittest.TestCase):
    def test_confirmed_p3_run_builds_sorftime_search_demand_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = _seed_p3_confirmed_run(Path(tmpdir))
            snapshot_source = Path(tmpdir) / "generic_sorftime_deep_snapshot.json"
            snapshot_source.write_text(
                json.dumps(_valid_sorftime_snapshot(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            outputs = run_sorftime_deep_dive(run_dir, snapshot_source=snapshot_source)
            snapshot = _load_json(outputs["sorftime_deep_snapshot"])
            packet = _load_json(outputs["search_demand_evidence_packet"])
            progress = _load_json(outputs["progress"])

        validate_deep_snapshot(snapshot, expected_source_name="sorftime")
        validate_p4_evidence_packet(packet, expected_primary_source="sorftime")
        self.assertEqual(packet["packet_id"], "search_demand_evidence_packet")
        self.assertEqual(packet["primary_source"], "sorftime")
        self.assertIn("sellersprite", packet["cross_check_sources"])
        self.assertEqual(
            {item["item_type"] for item in packet["evidence_items"]},
            {
                "category_search",
                "category_top100",
                "category_trend",
                "keyword_detail",
                "keyword_trend",
                "keyword_expansion",
                "keyword_search_results",
                "asin_traffic_terms",
                "competitor_keywords",
                "hot_product_features",
                "product_detail",
                "product_reviews",
            },
        )
        self.assertEqual(progress["stages"]["stage_6_deep_dive"]["status"], "running")
        self.assertEqual(progress["next_action"]["next_substage"], "P4-4")
        self.assertIn("mcp_snapshots/sorftime_deep_snapshot.json", progress["completed_artifacts"])
        self.assertIn("search_demand/search_demand_evidence_packet.json", progress["completed_artifacts"])

    def test_route_matrix_not_confirmed_blocks_without_p4_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = _seed_p3_confirmed_run(Path(tmpdir))
            route_path = run_dir / "route_matrix_confirm.json"
            route_packet = _load_json(route_path)
            route_packet["decision"] = "stop"
            route_path.write_text(json.dumps(route_packet, ensure_ascii=False, indent=2), encoding="utf-8")

            with self.assertRaises(P4SorftimeError):
                run_sorftime_deep_dive(run_dir, snapshot_source=_write_snapshot_source(Path(tmpdir)))

            progress = _load_json(run_dir / "progress.json")

        self.assertEqual(progress["stages"]["stage_6_deep_dive"]["status"], "blocked")
        self.assertFalse((run_dir / "mcp_snapshots" / "sorftime_deep_snapshot.json").exists())
        self.assertFalse((run_dir / "search_demand" / "search_demand_evidence_packet.json").exists())

    def test_p3_completeness_blocker_blocks_without_p4_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = _seed_p3_confirmed_run(Path(tmpdir))
            completeness_path = run_dir / "data_completeness_check.json"
            completeness = _load_json(completeness_path)
            completeness["overall_level"] = "blocker"
            completeness_path.write_text(json.dumps(completeness, ensure_ascii=False, indent=2), encoding="utf-8")

            with self.assertRaises(P4SorftimeError):
                run_sorftime_deep_dive(run_dir, snapshot_source=_write_snapshot_source(Path(tmpdir)))

            progress = _load_json(run_dir / "progress.json")

        self.assertEqual(progress["stages"]["stage_6_deep_dive"]["status"], "blocked")
        self.assertFalse((run_dir / "mcp_snapshots" / "sorftime_deep_snapshot.json").exists())
        self.assertFalse((run_dir / "search_demand" / "search_demand_evidence_packet.json").exists())

    def test_empty_snapshot_fields_are_recorded_as_data_gaps(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = _seed_p3_confirmed_run(Path(tmpdir))
            snapshot = _valid_sorftime_snapshot()
            snapshot["tool_results"][1]["raw_result"] = {"code": "OK", "Top100产品_sample": [{"Top100产品.价格": None}]}
            snapshot_source = _write_snapshot_source(Path(tmpdir), snapshot)

            outputs = run_sorftime_deep_dive(run_dir, snapshot_source=snapshot_source)
            packet = _load_json(outputs["search_demand_evidence_packet"])

        self.assertTrue(
            any(
                gap.get("type") == "empty_or_missing_fields" and gap.get("evidence_type") == "category_top100"
                for gap in packet["data_gaps"]
                if isinstance(gap, dict)
            )
        )

    def test_tool_failure_is_recorded_as_errors_and_data_gaps(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = _seed_p3_confirmed_run(Path(tmpdir))
            snapshot = _valid_sorftime_snapshot()
            snapshot["tool_calls"][3]["status"] = "error"
            snapshot["tool_results"][3]["status"] = "error"
            snapshot["tool_results"][3]["normalized_preview"] = {"error": "generic failure"}
            snapshot["errors"] = [
                {
                    "type": "tool_unavailable",
                    "tool_name": "keyword_detail",
                    "message": "generic failure",
                }
            ]
            snapshot_source = _write_snapshot_source(Path(tmpdir), snapshot)

            outputs = run_sorftime_deep_dive(run_dir, snapshot_source=snapshot_source)
            saved_snapshot = _load_json(outputs["sorftime_deep_snapshot"])
            packet = _load_json(outputs["search_demand_evidence_packet"])

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
            outputs = run_sorftime_deep_dive(run_dir, snapshot_source=_write_snapshot_source(Path(tmpdir)))
            packet = _load_json(outputs["search_demand_evidence_packet"])

        self.assertTrue(all(item.get("metric_basis_ref") for item in packet["evidence_items"]))
        self.assertTrue(all(metric.get("metric_basis_ref") for metric in packet["derived_metrics"].values()))

    def test_p4_3_does_not_generate_downstream_or_other_source_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = _seed_p3_confirmed_run(Path(tmpdir))
            run_sorftime_deep_dive(run_dir, snapshot_source=_write_snapshot_source(Path(tmpdir)))
            progress = _load_json(run_dir / "progress.json")

        forbidden_paths = [
            run_dir / "mcp_snapshots" / "sellersprite_deep_snapshot.json",
            run_dir / "market_structure" / "market_structure_evidence_packet.json",
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

    def test_existing_sorftime_snapshot_is_reused_when_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = _seed_p3_confirmed_run(Path(tmpdir))
            target = run_dir / "mcp_snapshots" / "sorftime_deep_snapshot.json"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(_valid_sorftime_snapshot(), ensure_ascii=False, indent=2), encoding="utf-8")

            outputs = run_sorftime_deep_dive(run_dir)
            snapshot = _load_json(outputs["sorftime_deep_snapshot"])

        validate_deep_snapshot(snapshot, expected_source_name="sorftime")

    def test_probe_raw_snapshot_can_be_normalized(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = _seed_p3_confirmed_run(Path(tmpdir))
            probe_source = Path(tmpdir) / "generic_probe_raw.json"
            probe_source.write_text(json.dumps(_generic_probe_raw(), ensure_ascii=False, indent=2), encoding="utf-8")

            outputs = run_sorftime_deep_dive(run_dir, snapshot_source=probe_source)
            snapshot = _load_json(outputs["sorftime_deep_snapshot"])
            packet = _load_json(outputs["search_demand_evidence_packet"])

        validate_deep_snapshot(snapshot, expected_source_name="sorftime")
        validate_p4_evidence_packet(packet, expected_primary_source="sorftime")
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
    source = root / "generic_sorftime_deep_snapshot.json"
    source.write_text(json.dumps(snapshot or _valid_sorftime_snapshot(), ensure_ascii=False, indent=2), encoding="utf-8")
    return source


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
            _tool_result(
                "result-category-search",
                "call-category-search",
                "category_search_from_product_name",
                [
                    {
                        "nodeid": "3395091",
                        "类目名称": "Generic Bottles",
                        "Top100产品月销量": "1402826",
                        "Top100产品月销额": "38113406.99",
                        "平均星级": "4.59",
                        "平均评价数量": "11994.52",
                        "平均价格": "23.270000",
                        "销量前3的产品月销量占比": "47.67%",
                        "销量前3的品牌月销量占比": "64.13%",
                        "销量前3的卖家月销量占比": "84.24%",
                    }
                ],
            ),
            _tool_result(
                "result-category-report",
                "call-category-report",
                "category_report",
                {
                    "Top100产品_sample": [
                        {
                            "ASIN": "<generic_asin>",
                            "月销量": "379466",
                            "月销额": "13277515.34",
                            "品牌": "<generic_brand>",
                            "价格": 34.99,
                            "评论数": 116354,
                            "星级": 4.7,
                            "卖家": "<generic_seller>",
                        }
                    ],
                    "类目统计报告_sample": {
                        "nodeid": "<generic_node_id>",
                        "top100产品月销量": "3039427",
                        "top100产品月销额": "84902657.07",
                        "top3_product_sales_volume_share": "销量前三的产品月销量占比:37.22%",
                        "top3_brands_sales_volume_share": "销量前三的品牌月销量占比:78.92%",
                        "top3_seller_sales_volume_share": "销量前三的卖家月销量占比:92.35%",
                        "amazonOwned_sales_volume_share": "亚马逊自营月销量占比:87.62%",
                        "average_price": "销量前的80%产品平均价格：22.179",
                        "median_price": "销量前的80%产品中位价格：9.49",
                    },
                },
            ),
            _tool_result(
                "result-category-trend",
                "call-category-trend",
                "category_trend",
                {"series_sample": ["2024年06月=1232094", "2026年06月=717226"]},
            ),
            _tool_result(
                "result-keyword-detail",
                "call-keyword-detail",
                "keyword_detail",
                {
                    "关键词": "<generic_keyword>",
                    "周搜索量": "368705",
                    "周搜索排名": "103",
                    "月搜索量": "1397364",
                    "推荐cpc竞价": "0.35",
                    "词搜索量旺季": "8月",
                    "搜索结果竞品数量": "144105",
                    "top5_product_sample": [
                        {"asin": "<generic_asin>", "price": 34.97, "monthly_sales": "本产品月销量：372207（占比：12.49%）", "brand": "<generic_brand>", "seller": "<generic_seller>"}
                    ],
                },
            ),
            _tool_result(
                "result-keyword-trend",
                "call-keyword-trend",
                "keyword_trend",
                {
                    "关键词": "<generic_keyword>",
                    "搜索量趋势_sample": ["2024年06月搜索量2364427", "2026年05月搜索量1526641"],
                    "搜索排名趋势_sample": ["2024年06月搜索排名29", "2026年05月搜索排名105"],
                    "推荐竞价趋势_sample": ["2024年07月cpc推荐竞价0.90", "2026年05月cpc推荐竞价0.35"],
                },
            ),
            _tool_result(
                "result-keyword-extends",
                "call-keyword-extends",
                "keyword_extends",
                [{"关键词": "<generic_keyword>", "周搜索量": 368705, "周搜索排名": 103, "月搜索量": 1397364, "cpc推荐竞价": "0.35", "季节性": "搜索量旺季:8月"}],
            ),
            _tool_result(
                "result-keyword-results",
                "call-keyword-results",
                "keyword_search_results",
                {
                    "Top100产品_sample": [
                        {"ASIN": "<generic_asin>", "标题": "<generic_title>", "价格": 34.99, "月销量": 379466, "品牌": "<generic_brand>", "卖家": "<generic_seller>"}
                    ]
                },
            ),
            _tool_result(
                "result-product-detail",
                "call-product-detail",
                "product_detail",
                {
                    "ASIN": "<generic_asin>",
                    "价格": 34.99,
                    "月销量": "379466",
                    "月销额": "13277515.34",
                    "星级": 4.7,
                    "评价数": 116354,
                    "卖家": "<generic_seller>",
                    "品牌": "<generic_brand>",
                    "类目": "<generic_category>",
                    "nodeId": "<generic_node_id>",
                },
            ),
            _tool_result("result-product-trend", "call-product-trend", "product_trend", {"series_sample": ["2024年06月=1232094", "2026年06月=717226"]}),
            _tool_result("result-product-traffic", "call-product-traffic", "product_traffic_terms", {"keywords_sample": [{"关键词": "<generic_keyword>", "自然位": 3, "搜索量": 368705, "曝光时间": "2026-06"}]}),
            _tool_result("result-competitor-keywords", "call-competitor-keywords", "competitor_product_keywords", {"keywords_sample": [{"关键词": "<generic_keyword>", "自然位": 8, "搜索量": 368705}]}),
            _tool_result("result-product-reviews", "call-product-reviews", "product_reviews", {"reviews_sample": [{"rating": 4, "title": "<generic_title>", "date": "2026-06-01", "content": "<generic_review>"}]}),
            _tool_result("result-hot-feature", "call-hot-feature", "similar_product_feature", {"features_sample": [{"特征": "<generic_feature>", "占比": "40%"}]}),
        ],
        "errors": [],
        "data_gaps": [],
        "created_at": "2026-06-24T00:00:00Z",
        "retry_policy": {"max_attempts": 1, "reuse_existing_snapshot": True, "allow_network_call": False},
        "force_refresh": False,
        "input_lineage": {
            "route_refs": ["route_matrix_confirm.json#selected_routes[0]"],
            "selected_routes": ["<generic_route_ref>"],
            "nodeId": "<generic_node_id>",
            "nodeIdPath": "<generic_node_path>",
            "seed_keyword": "<generic_keyword>",
            "amzSite": "US",
        },
    }


def _generic_probe_raw() -> dict:
    return {
        "probe_run_id": "generic_probe",
        "created_at": "2026-06-24T00:00:00Z",
        "source_name": "sorftime_mcp",
        "probe_inputs": {
            "site": "US",
            "amzSite": "US",
            "keyword": "<generic_keyword>",
            "productName": "<generic_product_name>",
            "asin": "<generic_asin>",
            "node_id": "<generic_node_id>",
            "node_id_path": "<generic_node_path>",
        },
        "tool_calls": [
            {
                "tool_name": "mcp__sorftime_server.category_search_from_product_name",
                "status": "success",
                "request": {"amzSite": "US", "productName": "<generic_product_name>", "page": 1},
                "raw_result_sample": [{"nodeid": "3395091", "类目名称": "Generic Bottles", "Top100产品月销量": "1402826", "平均价格": "23.27"}],
                "available_fields": ["nodeid", "类目名称", "Top100产品月销量", "平均价格"],
            },
            {
                "tool_name": "mcp__sorftime_server.category_report",
                "status": "success",
                "request": {"amzSite": "US", "nodeId": "<generic_node_id>"},
                "raw_result_sample": {"Top100产品_sample": [{"ASIN": "<generic_asin>", "月销量": "379466", "价格": 34.99}]},
                "available_fields": ["Top100产品.ASIN", "Top100产品.月销量", "Top100产品.价格"],
            },
            {
                "tool_name": "mcp__sorftime_server.keyword_detail",
                "status": "success",
                "request": {"keywordSupportSite": "US", "keyword": "<generic_keyword>"},
                "raw_result_sample": {"关键词": "<generic_keyword>", "月搜索量": "1397364", "推荐cpc竞价": "0.35"},
                "available_fields": ["关键词", "月搜索量", "推荐cpc竞价"],
            },
            {
                "tool_name": "mcp__sorftime_server.product_traffic_terms",
                "status": "failed",
                "request": {"amzSite": "US", "asin": "<generic_asin>"},
                "error": {"type": "transport_send_error", "message": "generic failure"},
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
