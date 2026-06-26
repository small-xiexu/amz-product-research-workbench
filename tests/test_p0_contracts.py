from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from packages.research_core.contracts import (
    classify_numeric_conflict,
    decide_quick_gate,
    should_reuse_existing_artifacts,
    summarize_evaluation_constraints,
)
from packages.research_core.pipeline.build_report_seed import main as build_report_seed_main
from packages.research_core.pipeline.constants import REQUIRED_SECTION_MARKERS
from packages.research_core.pipeline.delivery_qa import (
    _has_required_operator_sections,
    _validate_report_data_sources,
    _validate_p0_delivery_blockers,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "p0_contracts"


class P0ContractTests(unittest.TestCase):
    def test_quick_gate_watch_overrides_continue_when_mixed_pool_material(self) -> None:
        sellersprite = _load_fixture("sellersprite_quick_packet.min.json")
        sorftime = _load_fixture("sorftime_quick_packet.min.json")

        result = decide_quick_gate(sellersprite, sorftime)

        self.assertEqual(result["gate_result"], "watch")
        self.assertIn("material_mixed_pool", result["rule_hits"])

    def test_quick_gate_stop_has_highest_priority(self) -> None:
        sellersprite = _load_fixture("sellersprite_quick_packet.min.json")
        sorftime = _load_fixture("sorftime_quick_packet.min.json")
        sellersprite["blocking_gaps"] = [{"field": "category", "impact": "missing"}]
        sorftime["support_level"] = "strong"

        result = decide_quick_gate(sellersprite, sorftime)

        self.assertEqual(result["gate_result"], "stop")
        self.assertEqual(result["rule_hits"], ["blocking_gaps"])

    def test_conflict_resolver_checks_metric_basis_before_threshold(self) -> None:
        basis = {
            "marketplace": "US",
            "currency": "USD",
            "data_window": "30d",
            "aggregation_unit": "asin",
            "sample_scope": "top100",
        }
        other_basis = {**basis, "data_window": "7d"}

        result = classify_numeric_conflict("monthly_units", 100, 160, basis, other_basis)

        self.assertEqual(result["severity"], "basis_mismatch")
        self.assertEqual(result["status"], "needs_normalization")

    def test_conflict_resolver_applies_default_threshold_after_basis_match(self) -> None:
        basis = {
            "marketplace": "US",
            "currency": "USD",
            "data_window": "30d",
            "aggregation_unit": "asin",
            "sample_scope": "top100",
        }

        result = classify_numeric_conflict("monthly_units", 100, 130, basis, basis)

        self.assertEqual(result["severity"], "material")
        self.assertFalse(result["blocks_delivery"])

    def test_evaluation_summary_blocks_direct_go_for_data_quality(self) -> None:
        result = summarize_evaluation_constraints(
            {
                "dimension_results": {
                    "data_quality": {
                        "rating": "blocked",
                        "confidence": "medium",
                    },
                    "market_demand": {
                        "rating": "strong",
                        "confidence": "low",
                    },
                }
            }
        )

        self.assertFalse(result["can_direct_go"])
        self.assertEqual(result["recommended_final_verdict_range"], ["blocked"])
        self.assertIn("market_demand", result["low_confidence_dimensions"])

    def test_progress_resume_reuses_done_artifacts_without_mcp_repeat(self) -> None:
        progress = _load_fixture("progress.min.json")
        stage = progress["stages"]["stage_2_market_quick_check"]

        reusable = should_reuse_existing_artifacts(stage, set(progress["completed_artifacts"]))

        self.assertTrue(reusable)

    def test_delivery_qa_no_longer_requires_data_source_section(self) -> None:
        self.assertNotIn("数据来源与口径", REQUIRED_SECTION_MARKERS)
        html = _operator_report_html()
        with tempfile.TemporaryDirectory() as tmpdir:
            html_path = Path(tmpdir) / "report.html"
            html_path.write_text(html, encoding="utf-8")

            self.assertTrue(_has_required_operator_sections(html_path))

    def test_reference_docs_do_not_reintroduce_legacy_stage7_report_contract(self) -> None:
        report_agent = (
            ROOT / "skills" / "amazon-product-research" / "agents" / "report-generation-agent.md"
        ).read_text(encoding="utf-8")
        artifact_contract = (
            ROOT / "skills" / "amazon-product-research" / "references" / "artifact_contract.md"
        ).read_text(encoding="utf-8")
        quality_sample = (
            ROOT / "skills" / "amazon-product-research" / "references" / "report_quality_sample.md"
        ).read_text(encoding="utf-8")

        self.assertNotIn("完整 8 板块数据溯源表", report_agent)
        self.assertNotIn("8 个板块完整", artifact_contract)
        self.assertNotIn("决策建议书，8 个板块", artifact_contract)
        self.assertNotIn("## 3. 数据来源与口径", quality_sample)
        self.assertNotIn("数据来源：卖家精灵 + Sorftime", quality_sample)
        self.assertNotIn("数据来源与口径", REQUIRED_SECTION_MARKERS)

    def test_delivery_qa_blocks_unresolved_p0_governance_items(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir) / "generic_run"
            analysis_dir = run_dir / "analysis"
            (run_dir / "conflict_review").mkdir(parents=True)
            (run_dir / "evaluations").mkdir()
            analysis_dir.mkdir()
            report_data = analysis_dir / "report_data.json"
            report_data.write_text(json.dumps({"schema_version": "p0-contract-v1"}), encoding="utf-8")
            (run_dir / "conflict_review" / "conflict_resolution_packet.json").write_text(
                json.dumps(
                    {
                        "schema_version": "p0-contract-v1",
                        "blocking_conflicts": [
                            {
                                "conflict_id": "conflict-1",
                                "status": "needs_review",
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (run_dir / "evaluations" / "evaluation_summary.json").write_text(
                json.dumps(
                    {
                        "schema_version": "p0-contract-v1",
                        "dimension_results": {
                            "data_quality": {
                                "rating": "blocked",
                                "confidence": "medium",
                            }
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (run_dir / "progress.json").write_text(
                json.dumps(
                    {
                        "schema_version": "p0-contract-v1",
                        "stages": {
                            "stage_2_market_quick_check": {
                                "status": "running",
                            }
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            result = _validate_p0_delivery_blockers(run_dir, report_data)

        self.assertFalse(result["pass"])
        self.assertTrue(any("blocking conflict" in hit for hit in result["hits"]))
        self.assertTrue(any("data_quality=blocked" in hit for hit in result["hits"]))
        self.assertTrue(any("progress.json" in hit for hit in result["hits"]))

    def test_report_data_source_path_resolves_to_loaded_packet(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir) / "generic_run"
            analysis_dir = run_dir / "analysis"
            analysis_dir.mkdir(parents=True)
            report_data = analysis_dir / "report_data.json"
            report_data.write_text(
                json.dumps(
                    {
                        "run_id": "generic_run",
                        "evidence_sources": [],
                        "hero": {
                            "metrics": {
                                "avg_price": {
                                    "value": 24.5,
                                    "source_path": "analysis.market.primary.avg_price",
                                }
                            }
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            packets = {
                "analysis": {
                    "market": {
                        "primary": {
                            "avg_price": 24.5,
                        }
                    }
                }
            }

            result = _validate_report_data_sources(report_data, packets)

        self.assertTrue(result["pass"], result)
        self.assertEqual(result["resolved"], 1)
        self.assertEqual(result["unresolved"], 0)

    def test_build_report_seed_writes_seed_without_formal_report_data(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir) / "20260624_generic_direction"
            (run_dir / "search_demand").mkdir(parents=True)
            (run_dir / "market_structure").mkdir()
            (run_dir / "review_voc").mkdir()
            (run_dir / "analysis").mkdir()
            (run_dir / "search_demand" / "search_demand_evidence_packet.json").write_text(
                json.dumps(
                    {
                        "packet_id": "search_demand_evidence",
                        "confidence": "medium",
                        "keyword_pool_by_role": {},
                        "data_gaps": [],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (run_dir / "market_structure" / "market_structure_evidence_packet.json").write_text(
                json.dumps(
                    {
                        "packet_id": "market_structure_evidence",
                        "confidence": "medium",
                        "market_size": {},
                        "route_market_fit": [],
                        "data_gaps": [],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (run_dir / "review_voc" / "voc_evidence_packet.json").write_text("{}", encoding="utf-8")
            (run_dir / "workflow_state.json").write_text("{}", encoding="utf-8")

            exit_code = build_report_seed_main([str(run_dir)])

            self.assertEqual(exit_code, 0)
            self.assertTrue((run_dir / "analysis" / "report_data.seed.json").exists())
            self.assertTrue((run_dir / "analysis" / "analysis_packet.json").exists())
            self.assertFalse((run_dir / "analysis" / "report_data.json").exists())
            self.assertFalse(any((run_dir / "analysis").glob("*_分析报告.html")))
            self.assertFalse(any((run_dir / "analysis").glob("*_决策工具包.xlsx")))
            self.assertFalse((run_dir / "analysis" / "delivery_qa_result.json").exists())


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _operator_report_html() -> str:
    return (
        '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
        "<style>body{font-family:sans-serif}</style></head><body>"
        '<section class="hero"><div class="verdict">建议补齐数据后再评估</div></section>'
        "<section><h2>类目全景</h2></section>"
        "<section><h2>核心竞品</h2></section>"
        "<section><h2>用户痛点</h2></section>"
        "<section><h2>价格带分布</h2></section>"
        "<section><h2>关键词与流量策略</h2></section>"
        '<section><h2>风险与下一步</h2><table class="go-nogo"></table></section>'
        "</body></html>"
    )


if __name__ == "__main__":
    unittest.main()
