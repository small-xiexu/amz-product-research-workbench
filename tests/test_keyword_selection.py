"""Unit tests for keyword selection and broad-keyword detection logic."""

import math
import unittest

from packages.research_core.pipeline.build_candidate_pool_from_import_manifest import (
    _extract_asin_from_filename,
    _pick_core_keyword,
)


class ExtractAsinFromFilenameTests(unittest.TestCase):
    def test_extracts_asin_from_standard_filename(self) -> None:
        self.assertEqual(
            _extract_asin_from_filename("ReverseASIN-US-B01C6KUNZI-Last-30-days.xlsx"),
            "B01C6KUNZI",
        )

    def test_extracts_asin_with_spaces_and_parens(self) -> None:
        self.assertEqual(
            _extract_asin_from_filename("ReverseASIN-US-B0BZZDPPRX-Last-30-days (2).xlsx"),
            "B0BZZDPPRX",
        )

    def test_returns_empty_for_no_asin(self) -> None:
        self.assertEqual(_extract_asin_from_filename("some_other_file.xlsx"), "")

    def test_returns_empty_for_empty_string(self) -> None:
        self.assertEqual(_extract_asin_from_filename(""), "")


class PickCoreKeywordTests(unittest.TestCase):
    def _make_record(self, keyword: str, search_volume: float, source_file: str) -> dict:
        return {
            "关键词": keyword,
            "月搜索量": search_volume,
            "__source_file": source_file,
        }

    def test_picks_keyword_with_highest_cross_asin_score(self) -> None:
        """Keyword shared by more ASINs should win over high-volume single-ASIN keyword."""
        records = [
            self._make_record("window squeegee", 80000, "ReverseASIN-US-ASIN000001-Last-30-days.xlsx"),
            self._make_record("window squeegee", 75000, "ReverseASIN-US-ASIN000002-Last-30-days.xlsx"),
            self._make_record("window squeegee", 70000, "ReverseASIN-US-ASIN000003-Last-30-days.xlsx"),
            self._make_record("car accessories", 835000, "ReverseASIN-US-ASIN000001-Last-30-days.xlsx"),
        ]
        result = _pick_core_keyword(records, None)
        self.assertEqual(result.get("关键词"), "window squeegee")

    def test_aba_match_boosts_keyword(self) -> None:
        """Keyword matching ABA signal gets boosted."""
        records = [
            self._make_record("shower squeegee", 140000, "ReverseASIN-US-ASIN000001-Last-30-days.xlsx"),
            self._make_record("shower squeegee", 140000, "ReverseASIN-US-ASIN000002-Last-30-days.xlsx"),
            self._make_record("window cleaner", 47268, "ReverseASIN-US-ASIN000001-Last-30-days.xlsx"),
            self._make_record("window cleaner", 47268, "ReverseASIN-US-ASIN000002-Last-30-days.xlsx"),
            self._make_record("window cleaner", 47268, "ReverseASIN-US-ASIN000003-Last-30-days.xlsx"),
        ]
        # Without ABA, window cleaner should win (3 ASINs vs 2)
        result_no_aba = _pick_core_keyword(records, None)
        self.assertEqual(result_no_aba.get("关键词"), "window cleaner")

        # With ABA boost on shower squeegee, it should win
        aba_signal = {"top_keywords": [{"keyword": "shower squeegee"}]}
        result_with_aba = _pick_core_keyword(records, aba_signal)
        self.assertEqual(result_with_aba.get("关键词"), "shower squeegee")

    def test_returns_empty_for_empty_records(self) -> None:
        self.assertEqual(_pick_core_keyword([], None), {})

    def test_skips_records_without_keyword(self) -> None:
        records = [
            {"关键词": "", "月搜索量": 100, "__source_file": "ReverseASIN-US-ASIN000001-Last-30-days.xlsx"},
        ]
        self.assertEqual(_pick_core_keyword(records, None), {})

    def test_skips_records_without_asin(self) -> None:
        records = [
            {"关键词": "test", "月搜索量": 100, "__source_file": "no_asin_here.xlsx"},
        ]
        self.assertEqual(_pick_core_keyword(records, None), {})

    def test_higher_volume_record_chosen_for_same_keyword(self) -> None:
        """When same keyword appears in multiple ASINs, use record with highest volume."""
        records = [
            self._make_record("window squeegee", 50000, "ReverseASIN-US-ASIN000001-Last-30-days.xlsx"),
            self._make_record("window squeegee", 90000, "ReverseASIN-US-ASIN000002-Last-30-days.xlsx"),
        ]
        result = _pick_core_keyword(records, None)
        self.assertEqual(result.get("月搜索量"), 90000)


if __name__ == "__main__":
    unittest.main()
