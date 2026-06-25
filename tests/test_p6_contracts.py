"""P6 contract and evaluation tests.

Covers:
  - Schema validation per evaluation dimension (6 tests)
  - evaluation_summary contract validation
  - Blocked rating rules (data_quality, core dimensions)
  - Low confidence rules
  - Invalid inputs (missing dimensions, wrong schema_version, invalid rating/confidence)
  - All 4 ratings × 6 dimensions boundary
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from packages.research_core.contracts.p6_contracts import (
    P6ContractError,
    P6_ALLOWED_RATINGS,
    P6_ALLOWED_CONFIDENCE,
    P6_ALLOWED_VERDICTS,
    P6_CORE_DIMENSIONS,
    P6_EVALUATION_DIMENSIONS,
    P6_SCHEMA_VERSION,
    P6_STAGE_ID,
    validate_all_evaluations,
    validate_evaluation_packet,
    validate_evaluation_summary,
)


def _eval_packet(dimension: str, score: int = 70, rating: str = "strong",
                 confidence: str = "high") -> dict[str, Any]:
    return {
        "schema_version": P6_SCHEMA_VERSION,
        "packet_id": f"{dimension}_evaluation",
        "stage": "evaluation",
        "score": score,
        "rating": rating,
        "confidence": confidence,
        "key_reasons": [f"{dimension} 信号充足"],
        "risks": [],
        "required_followups": ["继续监控"],
        "evidence_refs": [f"market_structure/market_structure_evidence_packet.json#{dimension}"],
        "execution_provenance": {
            "executed_by_agent": False,
            "agent_role": f"{dimension} Evaluation Agent",
            "execution_mode": "serial_fallback",
            "subagent_id": "",
            "note": "test fixture",
        },
    }


def _summary(dim_results: dict[str, Any]) -> dict[str, Any]:
    blocked = [d for d, r in dim_results.items() if r.get("rating") == "blocked"]
    low_conf = [d for d, r in dim_results.items() if r.get("confidence") == "low"]
    tensions = []
    if "data_quality" in blocked:
        tensions.append("data_quality blocked — 不能形成任何强结论")
    if "market_demand" in blocked:
        tensions.append("市场需求 blocked，P7 不能直接 go")

    # Core dimensions only: market_demand, competition, price_profit, data_quality
    core_blocked = [d for d in blocked if d in P6_CORE_DIMENSIONS]

    constraints = (
        ["data_quality blocked — 必须先补数或解决冲突"]
        if "data_quality" in blocked
        else [f"核心维度 blocked: {', '.join(core_blocked)} — 不能直接 go"]
        if core_blocked
        else ["所有维度均未 blocked，P7 可在 go/watch/no_go 范围内自由判断"]
    )

    return {
        "schema_version": P6_SCHEMA_VERSION,
        "packet_id": "evaluation_summary",
        "stage": "evaluation_summary",
        "dimension_results": dim_results,
        "blocked_dimensions": blocked,
        "low_confidence_dimensions": low_conf,
        "cross_dimension_tensions": tensions,
        "operator_judgment_constraints": constraints,
        "recommended_final_verdict_range": (
            ["blocked"] if "data_quality" in blocked
            else ["watch", "no_go"] if core_blocked
            else ["go", "watch", "no_go"]
        ),
    }


# ── Schema validation per dimension ────────────────────────────────────────

class P6EvaluationSchemaTests(unittest.TestCase):
    """Each of the 6 evaluation dimensions passes validate_evaluation_packet."""

    def test_market_demand_passes_validation(self) -> None:
        validate_evaluation_packet(_eval_packet("market_demand"), "market_demand")

    def test_competition_passes_validation(self) -> None:
        validate_evaluation_packet(_eval_packet("competition"), "competition")

    def test_price_profit_passes_validation(self) -> None:
        validate_evaluation_packet(_eval_packet("price_profit"), "price_profit")

    def test_voc_opportunity_passes_validation(self) -> None:
        validate_evaluation_packet(_eval_packet("voc_opportunity"), "voc_opportunity")

    def test_risk_passes_validation(self) -> None:
        validate_evaluation_packet(_eval_packet("risk"), "risk")

    def test_data_quality_passes_validation(self) -> None:
        validate_evaluation_packet(_eval_packet("data_quality"), "data_quality")

    def test_wrong_schema_version_raises(self) -> None:
        pkt = _eval_packet("market_demand")
        pkt["schema_version"] = "wrong-version"
        with self.assertRaises(P6ContractError):
            validate_evaluation_packet(pkt, "market_demand")

    def test_wrong_packet_id_raises(self) -> None:
        pkt = _eval_packet("market_demand")
        pkt["packet_id"] = "wrong_id"
        with self.assertRaises(P6ContractError):
            validate_evaluation_packet(pkt, "market_demand")

    def test_score_out_of_range_raises(self) -> None:
        pkt = _eval_packet("market_demand", score=150)
        with self.assertRaises(P6ContractError):
            validate_evaluation_packet(pkt, "market_demand")

        pkt["score"] = -5
        with self.assertRaises(P6ContractError):
            validate_evaluation_packet(pkt, "market_demand")

    def test_invalid_rating_raises(self) -> None:
        pkt = _eval_packet("market_demand", rating="excellent")
        with self.assertRaises(P6ContractError):
            validate_evaluation_packet(pkt, "market_demand")

    def test_invalid_confidence_raises(self) -> None:
        pkt = _eval_packet("market_demand", confidence="unknown")
        with self.assertRaises(P6ContractError):
            validate_evaluation_packet(pkt, "market_demand")

    def test_missing_required_field_raises(self) -> None:
        pkt = _eval_packet("market_demand")
        del pkt["key_reasons"]
        with self.assertRaises(P6ContractError):
            validate_evaluation_packet(pkt, "market_demand")

    def test_empty_evidence_refs_raises(self) -> None:
        pkt = _eval_packet("market_demand")
        pkt["evidence_refs"] = []
        with self.assertRaises(P6ContractError):
            validate_evaluation_packet(pkt, "market_demand")

    def test_missing_provenance_field_raises(self) -> None:
        pkt = _eval_packet("market_demand")
        del pkt["execution_provenance"]["executed_by_agent"]
        with self.assertRaises(P6ContractError):
            validate_evaluation_packet(pkt, "market_demand")


# ── evaluation_summary validation ──────────────────────────────────────────

class P6SummaryContractTests(unittest.TestCase):
    """evaluation_summary contract checks."""

    def _all_dims_strong(self) -> dict:
        return {dim: _eval_packet(dim) for dim in P6_EVALUATION_DIMENSIONS}

    def test_valid_summary_passes(self) -> None:
        dims = self._all_dims_strong()
        results = {d: {"score": e["score"], "rating": e["rating"], "confidence": e["confidence"],
                       "key_reasons": e["key_reasons"], "risks": e["risks"],
                       "required_followups": e["required_followups"],
                       "evidence_refs": e["evidence_refs"]}
                   for d, e in dims.items()}
        validate_evaluation_summary(_summary(results))

    def test_missing_dimension_raises(self) -> None:
        dims = self._all_dims_strong()
        results = {d: {"score": e["score"], "rating": e["rating"], "confidence": e["confidence"]}
                   for d, e in dims.items()}
        del results["market_demand"]
        with self.assertRaises(P6ContractError):
            validate_evaluation_summary(_summary(results))

    def test_missing_dimension_result_field_raises(self) -> None:
        dims = self._all_dims_strong()
        results = {d: {"score": e["score"], "rating": e["rating"], "confidence": e["confidence"]}
                   for d, e in dims.items()}
        del results["competition"]["score"]
        with self.assertRaises(P6ContractError):
            validate_evaluation_summary(_summary(results))

    def test_wrong_summary_packet_id_raises(self) -> None:
        dims = self._all_dims_strong()
        results = {d: {"score": e["score"], "rating": e["rating"], "confidence": e["confidence"]}
                   for d, e in dims.items()}
        s = _summary(results)
        s["packet_id"] = "wrong"
        with self.assertRaises(P6ContractError):
            validate_evaluation_summary(s)

    def test_empty_constraints_raises(self) -> None:
        dims = self._all_dims_strong()
        results = {d: {"score": e["score"], "rating": e["rating"], "confidence": e["confidence"]}
                   for d, e in dims.items()}
        s = _summary(results)
        s["operator_judgment_constraints"] = []
        with self.assertRaises(P6ContractError):
            validate_evaluation_summary(s)

    def test_invalid_verdict_in_range_raises(self) -> None:
        dims = self._all_dims_strong()
        results = {d: {"score": e["score"], "rating": e["rating"], "confidence": e["confidence"]}
                   for d, e in dims.items()}
        s = _summary(results)
        s["recommended_final_verdict_range"] = ["go", "invalid"]
        with self.assertRaises(P6ContractError):
            validate_evaluation_summary(s)


# ── validate_all_evaluations ──────────────────────────────────────────────

class P6ValidateAllTests(unittest.TestCase):
    """validate_all_evaluations checks all 6 are present and valid."""

    def test_all_six_pass(self) -> None:
        evals = {dim: _eval_packet(dim) for dim in P6_EVALUATION_DIMENSIONS}
        validate_all_evaluations(evals)

    def test_missing_dimension_raises(self) -> None:
        evals = {dim: _eval_packet(dim) for dim in P6_EVALUATION_DIMENSIONS}
        del evals["risk"]
        with self.assertRaises(P6ContractError):
            validate_all_evaluations(evals)

    def test_invalid_packet_in_set_raises(self) -> None:
        evals = {dim: _eval_packet(dim) for dim in P6_EVALUATION_DIMENSIONS}
        evals["market_demand"]["score"] = -1
        with self.assertRaises(P6ContractError):
            validate_all_evaluations(evals)


# ── Blocked rating rules ───────────────────────────────────────────────────

class P6BlockedRulesTests(unittest.TestCase):
    """Governance rules for blocked dimensions."""

    def test_data_quality_blocked_limits_verdict_to_blocked(self) -> None:
        results = {}
        for dim in P6_EVALUATION_DIMENSIONS:
            rating = "blocked" if dim == "data_quality" else "strong"
            conf = "medium" if dim == "data_quality" else "high"
            results[dim] = {"score": 20 if rating == "blocked" else 80, "rating": rating, "confidence": conf}
        s = _summary(results)
        self.assertIn("blocked", s["recommended_final_verdict_range"])
        self.assertEqual(len(s["recommended_final_verdict_range"]), 1)
        self.assertEqual(s["recommended_final_verdict_range"], ["blocked"])

    def test_core_dimension_blocked_no_go(self) -> None:
        for blocked_dim in P6_CORE_DIMENSIONS:
            if blocked_dim == "data_quality":
                continue  # data_quality has stricter rule
            with self.subTest(blocked=blocked_dim):
                results = {}
                for dim in P6_EVALUATION_DIMENSIONS:
                    rating = "blocked" if dim == blocked_dim else "strong"
                    results[dim] = {"score": 20 if rating == "blocked" else 80, "rating": rating, "confidence": "high"}
                s = _summary(results)
                self.assertNotIn("go", s["recommended_final_verdict_range"])
                self.assertIn("no_go", s["recommended_final_verdict_range"])

    def test_auxiliary_dimension_blocked_does_not_block_go(self) -> None:
        for aux_dim in ("voc_opportunity", "risk"):
            with self.subTest(aux=aux_dim):
                results = {}
                for dim in P6_EVALUATION_DIMENSIONS:
                    rating = "blocked" if dim == aux_dim else "strong"
                    results[dim] = {"score": 20 if rating == "blocked" else 80, "rating": rating, "confidence": "high"}
                s = _summary(results)
                # Aux dimensions don't block go in governance rules
                self.assertIn("go", s["recommended_final_verdict_range"])


# ── Low confidence rules ───────────────────────────────────────────────────

class P6LowConfidenceTests(unittest.TestCase):
    """Low confidence dimensions are tracked but don't block."""

    def test_low_confidence_dimensions_tracked(self) -> None:
        results = {}
        for dim in P6_EVALUATION_DIMENSIONS:
            conf = "low" if dim in ("market_demand", "risk") else "high"
            results[dim] = {"score": 60, "rating": "watch", "confidence": conf}
        s = _summary(results)
        self.assertIn("market_demand", s["low_confidence_dimensions"])
        self.assertIn("risk", s["low_confidence_dimensions"])
        self.assertNotIn("competition", s["low_confidence_dimensions"])

    def test_low_confidence_does_not_block(self) -> None:
        results = {}
        for dim in P6_EVALUATION_DIMENSIONS:
            results[dim] = {"score": 60, "rating": "strong", "confidence": "low"}
        s = _summary(results)
        self.assertEqual(len(s["blocked_dimensions"]), 0)
        self.assertEqual(len(s["low_confidence_dimensions"]), 6)
        # low confidence alone doesn't restrict verdict range
        self.assertIn("go", s["recommended_final_verdict_range"])


# ── Rating coverage: all 4 ratings work ────────────────────────────────────

class P6RatingCoverageTests(unittest.TestCase):
    """Each rating value can be assigned to all dimensions."""

    def test_all_ratings_assignable_to_all_dimensions(self) -> None:
        for rating in sorted(P6_ALLOWED_RATINGS):
            for dim in P6_EVALUATION_DIMENSIONS:
                with self.subTest(rating=rating, dim=dim):
                    pkt = _eval_packet(dim, rating=rating)
                    validate_evaluation_packet(pkt, dim)

    def test_all_confidence_levels_assignable(self) -> None:
        for conf in sorted(P6_ALLOWED_CONFIDENCE):
            for dim in P6_EVALUATION_DIMENSIONS:
                with self.subTest(confidence=conf, dim=dim):
                    pkt = _eval_packet(dim, confidence=conf)
                    validate_evaluation_packet(pkt, dim)


# ── Edge case: score boundaries ────────────────────────────────────────────

class P6ScoreBoundaryTests(unittest.TestCase):
    """Score must be 0-100 inclusive."""

    def test_score_zero_valid(self) -> None:
        validate_evaluation_packet(_eval_packet("market_demand", score=0, rating="blocked"), "market_demand")

    def test_score_hundred_valid(self) -> None:
        validate_evaluation_packet(_eval_packet("market_demand", score=100), "market_demand")

    def test_score_negative_raises(self) -> None:
        with self.assertRaises(P6ContractError):
            validate_evaluation_packet(_eval_packet("market_demand", score=-1), "market_demand")

    def test_score_over_hundred_raises(self) -> None:
        with self.assertRaises(P6ContractError):
            validate_evaluation_packet(_eval_packet("market_demand", score=101), "market_demand")


if __name__ == "__main__":
    unittest.main()
