"""P7 contract and integrated judgment tests.

Covers:
  - integrated_operator_judgment validation (valid + error cases)
  - Allowed verdicts and confidence levels
  - Missing required fields
  - Provenance validation
"""

from __future__ import annotations

import unittest
from typing import Any

from packages.research_core.contracts.p7_contracts import (
    P7ContractError,
    P7_ALLOWED_CONFIDENCE,
    P7_ALLOWED_VERDICTS,
    P7_SCHEMA_VERSION,
    P7_STAGE_ID,
    validate_integrated_judgment,
)


def _judgment(
    verdict: str = "go",
    confidence: str = "high",
    recommended_route: Any = None,
) -> dict[str, Any]:
    if recommended_route is None:
        recommended_route = {
            "name": "主线候选",
            "role": "mainline",
            "rationale": "市场需求强，竞争适中",
        }
    return {
        "schema_version": P7_SCHEMA_VERSION,
        "packet_id": "integrated_operator_judgment",
        "stage": P7_STAGE_ID,
        "run_id": "test_run",
        "final_verdict": verdict,
        "verdict_reason": f"基于 6 维评价的综合判断，verdict={verdict}",
        "recommended_route": recommended_route,
        "rejected_routes": [{"name": "备选路线1", "reason": "价格带不匹配"}],
        "biggest_opportunity": {
            "dimension": "market_demand",
            "score": 85,
            "rating": "strong",
            "top_reason": "搜索需求稳定增长",
        },
        "biggest_risk": {
            "dimension": "competition",
            "score": 55,
            "rating": "watch",
            "top_risk": "头部集中度高",
        },
        "required_next_actions": ["补齐数据缺口", "联系供应商打样"],
        "constraints_applied": ["data_quality=acceptable，无blocker"],
        "evidence_refs": [
            "evaluations/market_demand_evaluation.json#score",
            "evaluations/evaluation_summary.json",
        ],
        "confidence": confidence,
        # v2 深度运营分析字段（脚本生成骨架，Agent 填充内容）
        "route_recommendation": {"routes": [{"name": "主线", "role": "mainline", "priority": "high"}]},
        "route_tradeoff": [],
        "competitor_benchmark": [],
        "competitor_weakness_map": [],
        "cold_start_estimate": {"budget_range": "待 Agent 填充"},
        "price_band_analysis": [],
        "voc_to_spec": [],
        "keyword_strategy": {"primary_intent_keywords": [], "test_keywords": [], "negative_keywords": []},
        "risk_mitigation": [],
        "validation_roadmap": [],
        "generated_at": "2026-06-25T00:00:00",
        "execution_provenance": {
            "executed_by_agent": False,
            "agent_role": "Integrated Operator Judgment",
            "execution_mode": "serial_fallback",
            "subagent_id": "",
            "note": "test fixture",
        },
    }


# ── Valid judgment cases ──────────────────────────────────────────────────

class P7ValidJudgmentTests(unittest.TestCase):
    """Valid judgments pass validation."""

    def test_go_verdict_passes(self) -> None:
        validate_integrated_judgment(_judgment("go"))

    def test_watch_verdict_passes(self) -> None:
        validate_integrated_judgment(_judgment("watch"))

    def test_no_go_verdict_passes(self) -> None:
        validate_integrated_judgment(_judgment("no_go"))

    def test_blocked_verdict_passes(self) -> None:
        validate_integrated_judgment(_judgment("blocked"))

    def test_all_confidence_levels(self) -> None:
        for conf in sorted(P7_ALLOWED_CONFIDENCE):
            with self.subTest(confidence=conf):
                validate_integrated_judgment(_judgment(confidence=conf))

    def test_string_recommended_route_passes(self) -> None:
        j = _judgment()
        j["recommended_route"] = "主线候选"
        validate_integrated_judgment(j)


# ── Error cases ───────────────────────────────────────────────────────────

class P7InvalidJudgmentTests(unittest.TestCase):
    """Invalid judgments raise P7ContractError."""

    def test_wrong_schema_version_raises(self) -> None:
        j = _judgment()
        j["schema_version"] = "wrong-version"
        with self.assertRaises(P7ContractError):
            validate_integrated_judgment(j)

    def test_wrong_packet_id_raises(self) -> None:
        j = _judgment()
        j["packet_id"] = "wrong_id"
        with self.assertRaises(P7ContractError):
            validate_integrated_judgment(j)

    def test_wrong_stage_raises(self) -> None:
        j = _judgment()
        j["stage"] = "wrong_stage"
        with self.assertRaises(P7ContractError):
            validate_integrated_judgment(j)

    def test_invalid_verdict_raises(self) -> None:
        j = _judgment()
        j["final_verdict"] = "maybe"
        with self.assertRaises(P7ContractError):
            validate_integrated_judgment(j)

    def test_invalid_confidence_raises(self) -> None:
        j = _judgment()
        j["confidence"] = "unknown"
        with self.assertRaises(P7ContractError):
            validate_integrated_judgment(j)

    def test_missing_verdict_reason_raises(self) -> None:
        j = _judgment()
        j["verdict_reason"] = ""
        with self.assertRaises(P7ContractError):
            validate_integrated_judgment(j)

    def test_empty_next_actions_raises(self) -> None:
        j = _judgment()
        j["required_next_actions"] = []
        with self.assertRaises(P7ContractError):
            validate_integrated_judgment(j)

    def test_empty_constraints_raises(self) -> None:
        j = _judgment()
        j["constraints_applied"] = []
        with self.assertRaises(P7ContractError):
            validate_integrated_judgment(j)

    def test_empty_evidence_refs_raises(self) -> None:
        j = _judgment()
        j["evidence_refs"] = []
        with self.assertRaises(P7ContractError):
            validate_integrated_judgment(j)

    def test_missing_executed_by_agent_raises(self) -> None:
        j = _judgment()
        del j["execution_provenance"]["executed_by_agent"]
        with self.assertRaises(P7ContractError):
            validate_integrated_judgment(j)

    def test_non_bool_executed_by_agent_raises(self) -> None:
        j = _judgment()
        j["execution_provenance"]["executed_by_agent"] = "yes"
        with self.assertRaises(P7ContractError):
            validate_integrated_judgment(j)

    def test_missing_agent_role_raises(self) -> None:
        j = _judgment()
        j["execution_provenance"]["agent_role"] = ""
        with self.assertRaises(P7ContractError):
            validate_integrated_judgment(j)

    def test_missing_run_id_raises(self) -> None:
        j = _judgment()
        j["run_id"] = ""
        with self.assertRaises(P7ContractError):
            validate_integrated_judgment(j)

    def test_all_verdicts_valid(self) -> None:
        for v in sorted(P7_ALLOWED_VERDICTS):
            with self.subTest(verdict=v):
                validate_integrated_judgment(_judgment(v))


# ── Verdict boundary tests ─────────────────────────────────────────────────

class P7VerdictBoundaryTests(unittest.TestCase):
    """Each verdict value is a valid final_verdict."""

    def test_go_is_allowed(self) -> None:
        self.assertIn("go", P7_ALLOWED_VERDICTS)

    def test_watch_is_allowed(self) -> None:
        self.assertIn("watch", P7_ALLOWED_VERDICTS)

    def test_no_go_is_allowed(self) -> None:
        self.assertIn("no_go", P7_ALLOWED_VERDICTS)

    def test_blocked_is_allowed(self) -> None:
        self.assertIn("blocked", P7_ALLOWED_VERDICTS)


# ── Verdict-specific reason rules ──────────────────────────────────────────

class P7VerdictReasonTests(unittest.TestCase):
    """Verdict reason must match the verdict context."""

    def test_blocked_verdict_mentions_data_quality(self) -> None:
        j = _judgment("blocked")
        j["verdict_reason"] = "数据质量不达标，必须先补数再推进。"
        validate_integrated_judgment(j)

    def test_go_verdict_mentions_strong_signals(self) -> None:
        j = _judgment("go")
        j["verdict_reason"] = "6 项评价维度整体信号偏正面，市场需求、竞争格局均处于 strong 水平。"
        validate_integrated_judgment(j)

    def test_watch_verdict_mentions_weak_signals(self) -> None:
        j = _judgment("watch")
        j["verdict_reason"] = "竞争格局信号偏弱，建议补充数据后再做最终判断。"
        validate_integrated_judgment(j)

    def test_no_go_verdict_mentions_conditions_not_met(self) -> None:
        j = _judgment("no_go")
        j["verdict_reason"] = "核心条件不满足，建议暂缓推进。"
        validate_integrated_judgment(j)


if __name__ == "__main__":
    unittest.main()
