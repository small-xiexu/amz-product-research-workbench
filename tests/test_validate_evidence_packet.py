"""Tests for scripts/validate_evidence_packet.py — Stage 6 产出后契约校验。"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.validate_evidence_packet import (
    validate_evidence_packet,
    _check_facts_structure,
    _check_route_coverage,
    _check_top_level_fields,
)


class ValidateEvidencePacketTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self._tmp = Path(self._tmpdir.name)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def _make_run_dir(self) -> Path:
        run_dir = self._tmp / "test_run"
        run_dir.mkdir()
        (run_dir / "route_matrix_confirm.json").write_text(
            json.dumps({
                "route_matrix": [
                    {"name": "主线-基础款", "status": "confirmed"},
                    {"name": "升级款", "status": "confirmed"},
                    {"name": "排除项", "status": "excluded"},
                ]
            }, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return run_dir

    def _write_packet(self, run_dir: Path, packet_name: str, data: dict) -> None:
        subdir = run_dir / packet_name
        subdir.mkdir(exist_ok=True)
        (subdir / f"{packet_name}_evidence_packet.json").write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def _good_packet(self, packet_name: str = "market_structure") -> dict:
        return {
            "schema_version": "p4-deep-contract-v1",
            "packet_id": f"{packet_name}_evidence_packet",
            "run_id": "test",
            "primary_source": "sellersprite" if packet_name == "market_structure" else "sorftime",
            "evidence_items": [{
                "item_id": "ei1",
                "item_type": "market_overview",
                "facts": [
                    {"id": "f1", "value": "some value"},
                    {"id": "f2", "value": 42},
                ],
                "evidence_refs": ["ref1"],
                "source_refs": ["src1"],
            }],
            "route_refs": ["主线-基础款"],
            "selected_routes": ["升级款"],
            "data_gaps": [],
            "confidence": "high",
        }

    # ── Top-level field checks ────────────────────────────────────────

    def test_good_packet_passes(self) -> None:
        run_dir = self._make_run_dir()
        self._write_packet(run_dir, "market_structure", self._good_packet())
        ok, errors = validate_evidence_packet(run_dir, "market_structure")
        self.assertTrue(ok, f"Expected pass, got: {errors}")

    def test_missing_top_level_fields_detected(self) -> None:
        run_dir = self._make_run_dir()
        bad = self._good_packet()
        del bad["evidence_items"]
        del bad["data_gaps"]
        self._write_packet(run_dir, "market_structure", bad)
        ok, errors = validate_evidence_packet(run_dir, "market_structure")
        self.assertFalse(ok)
        self.assertTrue(any("evidence_items" in e for e in errors))
        self.assertTrue(any("data_gaps" in e for e in errors))

    def test_empty_evidence_items_detected(self) -> None:
        run_dir = self._make_run_dir()
        bad = self._good_packet()
        bad["evidence_items"] = []
        self._write_packet(run_dir, "market_structure", bad)
        ok, errors = validate_evidence_packet(run_dir, "market_structure")
        self.assertFalse(ok)
        self.assertTrue(any("为空" in e for e in errors))

    # ── Facts structure checks ────────────────────────────────────────

    def test_bare_string_in_facts_list_detected(self) -> None:
        run_dir = self._make_run_dir()
        bad = self._good_packet()
        bad["evidence_items"] = [{
            "item_id": "ei1",
            "item_type": "market_overview",
            "facts": [
                {"id": "f1", "value": "ok"},
                "bare string in facts!",
            ],
            "evidence_refs": ["ref1"],
            "source_refs": ["src1"],
        }]
        self._write_packet(run_dir, "market_structure", bad)
        ok, errors = validate_evidence_packet(run_dir, "market_structure")
        self.assertFalse(ok)
        self.assertTrue(any("非 dict" in e for e in errors))

    def test_fact_missing_id_allowed_by_relaxed_contract(self) -> None:
        run_dir = self._make_run_dir()
        packet = self._good_packet()
        packet["evidence_items"] = [{
            "item_id": "ei1",
            "item_type": "market_overview",
            "facts": [{"value": "no id here"}],
            "evidence_refs": ["ref1"],
            "source_refs": ["src1"],
        }]
        self._write_packet(run_dir, "market_structure", packet)
        ok, errors = validate_evidence_packet(run_dir, "market_structure")
        self.assertTrue(ok, f"Relaxed facts contract should allow dict facts without id: {errors}")

    def test_facts_as_dict_with_bare_string_value_allowed_by_relaxed_contract(self) -> None:
        run_dir = self._make_run_dir()
        packet = self._good_packet()
        packet["evidence_items"] = [{
            "item_id": "ei1",
            "item_type": "market_overview",
            "facts": {"f1": "bare string value", "f2": {"value": 42, "source_path": "x"}},
            "evidence_refs": ["ref1"],
            "source_refs": ["src1"],
        }]
        self._write_packet(run_dir, "market_structure", packet)
        ok, errors = validate_evidence_packet(run_dir, "market_structure")
        self.assertTrue(ok, f"Relaxed facts contract should allow dict facts with scalar values: {errors}")

    # ── Route coverage checks ─────────────────────────────────────────

    def test_missing_route_coverage_detected(self) -> None:
        run_dir = self._make_run_dir()
        bad = self._good_packet()
        bad["route_refs"] = []
        bad["selected_routes"] = []
        self._write_packet(run_dir, "market_structure", bad)
        ok, errors = validate_evidence_packet(run_dir, "market_structure")
        self.assertFalse(ok)
        self.assertTrue(any("未覆盖" in e for e in errors))

    def test_excluded_routes_not_required(self) -> None:
        run_dir = self._make_run_dir()
        good = self._good_packet()
        good["route_refs"] = ["主线-基础款"]
        good["selected_routes"] = ["升级款"]
        self._write_packet(run_dir, "market_structure", good)
        ok, errors = validate_evidence_packet(run_dir, "market_structure")
        self.assertTrue(ok, f"Excluded routes should NOT be required: {errors}")

    # ── Error cases ──────────────────────────────────────────────────

    def test_missing_packet_file_reports_error(self) -> None:
        run_dir = self._make_run_dir()
        ok, errors = validate_evidence_packet(run_dir, "market_structure")
        self.assertFalse(ok)
        self.assertTrue(any("不存在" in e for e in errors))

    def test_unknown_packet_type_reports_error(self) -> None:
        run_dir = self._make_run_dir()
        ok, errors = validate_evidence_packet(run_dir, "unknown_type")
        self.assertFalse(ok)
        self.assertTrue(any("未知" in e for e in errors))

    def test_search_demand_packet_validates_too(self) -> None:
        run_dir = self._make_run_dir()
        self._write_packet(run_dir, "search_demand", self._good_packet("search_demand"))
        ok, errors = validate_evidence_packet(run_dir, "search_demand")
        self.assertTrue(ok, f"Expected pass, got: {errors}")

    # ── Module-level helpers ──────────────────────────────────────────

    def test_top_level_fields_empty_list_ok(self) -> None:
        errors = _check_top_level_fields(
            {"schema_version": "1", "packet_id": "x", "run_id": "r",
             "primary_source": "s", "evidence_items": [{"item_id": "x", "item_type": "t",
             "facts": [], "evidence_refs": ["r"], "source_refs": ["s"]}],
             "route_refs": ["a"], "selected_routes": ["b"],
             "data_gaps": [], "confidence": "high"},
            "test_packet",
        )
        self.assertFalse(errors, f"Unexpected errors: {errors}")

    def test_route_coverage_skips_when_no_route_matrix(self) -> None:
        run_dir = self._tmp / "no_routes"
        run_dir.mkdir()
        errors = _check_route_coverage(
            {"route_refs": [], "selected_routes": []}, run_dir, "test"
        )
        self.assertEqual(len(errors), 1)
        self.assertIn("SKIP", errors[0])


if __name__ == "__main__":
    unittest.main()
