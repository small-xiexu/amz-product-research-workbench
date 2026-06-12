from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from openpyxl import load_workbook

from packages.report_renderer.xlsx_writer import write_xlsx
from packages.research_core.adapters import SorftimeAdapter, SortimeAdapter
from scripts.apply_ip_compliance_review import apply_ip_compliance_review, next_step_for
from scripts.apply_profit_review import apply_profit_review
from scripts.build_candidate_pool_from_import_manifest import build_candidate_pool


ROOT = Path(__file__).resolve().parents[1]


class RegressionTests(unittest.TestCase):
    def test_sorftime_adapter_name_and_legacy_alias(self) -> None:
        snapshot = {
            "fetched_at": "2026-06-12T00:00:00Z",
            "product_list": [{"asin": "B000000001", "title": "Sample", "monthly_sales": 120}],
            "keyword_data": [{"keyword": "sample keyword", "monthly_search_volume": 1000}],
            "category_trend": {"category_name": "Sample Category", "trend_direction": "增长"},
        }

        self.assertIs(SortimeAdapter, SorftimeAdapter)
        adapter = SorftimeAdapter(snapshot)
        self.assertEqual(adapter.fetch_products()[0].asin, "B000000001")
        self.assertEqual(adapter.fetch_keywords()[0].keyword, "sample keyword")
        self.assertEqual(adapter.fetch_category().category_name, "Sample Category")  # type: ignore[union-attr]

    def test_ip_compliance_next_step_is_actionable(self) -> None:
        self.assertIn("补齐知产/合规初筛字段", next_step_for("待复核", ["产品用途"], []))
        self.assertIn("先处理待复核项", next_step_for("待复核", [], ["知产：外观专利"]))
        self.assertIn("专业复核", next_step_for("高", [], []))
        self.assertIn("继续结合利润复核", next_step_for("低", [], []))

    def test_apply_ip_compliance_review_updates_next_step(self) -> None:
        package = _load_json("examples/minimal_research_package.json")
        review = {
            "product_flags": {
                "product_usage": "户外照明",
                "user_group": "成人",
                "material_coating": "塑料",
                "package_instruction_plan": "说明书",
            },
            "ip_rows": [
                {"risk_type": "商标", "result": "低", "evidence_note": "未发现明显冲突。"},
            ],
            "compliance_rows": [
                {"product_attribute": "带电/电子产品", "result": "中", "evidence_note": "需确认认证资料。"},
            ],
        }

        updated = apply_ip_compliance_review(package, review)
        next_step = updated["ip_compliance_review"]["next_step"]
        self.assertIn("打样前", next_step)
        self.assertEqual(updated["status_card"]["next_step"], next_step)

    def test_profit_review_marks_missing_required_costs(self) -> None:
        package = _load_json("examples/minimal_research_package.json")
        updated = apply_profit_review(
            package,
            {
                "sale_price": 19.99,
                "purchase_cost_cny": 30,
                "exchange_rate": 7.2,
                "fba_fee": 4.5,
            },
        )

        missing = updated["profit_review"]["missing_fields"]
        self.assertIn("头程费用", missing)
        self.assertIn("入库配置费", missing)
        self.assertEqual(updated["profit_reference"]["status"], "待补")

    def test_xlsx_writer_produces_readable_workbook(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "sample.xlsx"
            write_xlsx(output, [("长Sheet名称/需要清理[]:*?", [["标题", "说明"], ["A", "中文内容"]])])
            workbook = load_workbook(output, read_only=True, data_only=True)

            self.assertEqual(workbook.sheetnames[0], "长Sheet名称_需要清理_____")
            sheet = workbook[workbook.sheetnames[0]]
            self.assertEqual(sheet["A2"].value, "A")
            self.assertEqual(sheet["B2"].value, "中文内容")

    @unittest.skipUnless(
        (ROOT / "卖家精灵导出样例_美国站_宠物牵引绳_20260607").exists(),
        "local SellerSprite sample folder is ignored and may be absent",
    )
    def test_manual_export_sample_builds_candidate_pool(self) -> None:
        from scripts.inspect_manual_exports import build_manifest

        source = ROOT / "卖家精灵导出样例_美国站_宠物牵引绳_20260607"
        with tempfile.TemporaryDirectory() as tmp:
            copied_source = Path(tmp) / source.name
            shutil.copytree(source, copied_source, ignore=shutil.ignore_patterns(".DS_Store"))
            manifest = build_manifest(copied_source, "美国站宠物牵引绳样例", "US")
            candidate_pool = build_candidate_pool(manifest)

        self.assertEqual(candidate_pool["summary"]["total_candidates"], 1)
        candidate = candidate_pool["candidates"][0]
        self.assertTrue(candidate["candidate_id"].startswith("cand-"))
        self.assertGreaterEqual(len(candidate.get("top_products", [])), 1)


def _load_json(relative_path: str) -> dict:
    return json.loads((ROOT / relative_path).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
