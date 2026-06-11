#!/usr/bin/env python3
"""Build a hand-fill profit review template for one research package."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.report_renderer.render_report import _write_xlsx
from packages.research_core.rules.profit_rules import DEFAULT_AD_RATE, DEFAULT_COMMISSION_RATE, DEFAULT_STORAGE_FEE_RATE


INPUT_ROWS = [
    {
        "field": "sale_price",
        "label": "建议售价",
        "currency": "站点币种",
        "required": "是",
        "default": "",
        "note": "运营填写；可先参考竞品价格带。",
    },
    {
        "field": "purchase_cost_cny",
        "label": "采购价",
        "currency": "人民币",
        "required": "是",
        "default": "",
        "note": "运营/供应链填写。",
    },
    {
        "field": "exchange_rate",
        "label": "站点汇率",
        "currency": "人民币/站点币种",
        "required": "是",
        "default": "",
        "note": "例如美元站填 7.2，表示 1 美元 = 7.2 元人民币。",
    },
    {
        "field": "fba_fee",
        "label": "FBA费用",
        "currency": "站点币种",
        "required": "是",
        "default": "",
        "note": "运营手填，以亚马逊后台/收入计算器为准。",
    },
    {
        "field": "first_leg_shipping_cny",
        "label": "头程费用",
        "currency": "人民币",
        "required": "二选一",
        "default": "",
        "note": "可直接填写头程费用；若留空，则填写实际重/体积重/渠道自动估算。",
    },
    {
        "field": "actual_weight_g",
        "label": "实际重量",
        "currency": "克",
        "required": "二选一",
        "default": "",
        "note": "用于估算头程费用，和体积重取较大值。",
    },
    {
        "field": "volume_weight_g",
        "label": "体积重",
        "currency": "克",
        "required": "二选一",
        "default": "",
        "note": "用于估算头程费用，和实际重取较大值。",
    },
    {
        "field": "first_leg_channel",
        "label": "头程渠道",
        "currency": "",
        "required": "二选一",
        "default": "US_MATSON",
        "note": "可选：US_MATSON、US_STANDARD_SEA、CA_EXPRESS、CA_TRUCK_SEA。",
    },
    {
        "field": "inbound_placement_fee_cny",
        "label": "入库配置费",
        "currency": "人民币",
        "required": "是",
        "default": "",
        "note": "运营手填；不确定则保持空，系统标记待补，不默认 0。",
    },
    {
        "field": "commission_rate",
        "label": "佣金率",
        "currency": "比例",
        "required": "否",
        "default": DEFAULT_COMMISSION_RATE,
        "note": "默认 15%，精算以 Amazon 后台费率表为准。",
    },
    {
        "field": "storage_fee_rate",
        "label": "仓储费率",
        "currency": "比例",
        "required": "否",
        "default": DEFAULT_STORAGE_FEE_RATE,
        "note": "早期简化估算：建议售价 * 3%。",
    },
    {
        "field": "ad_rate",
        "label": "新品广告费率",
        "currency": "比例",
        "required": "否",
        "default": DEFAULT_AD_RATE,
        "note": "新品默认 20%，可调整。",
    },
    {
        "field": "return_rate",
        "label": "退货率",
        "currency": "比例",
        "required": "否",
        "default": "",
        "note": "优先用卖家精灵市场/类目退货率；留空时系统尝试从 research_package 取值。",
    },
    {
        "field": "operator_notes",
        "label": "备注",
        "currency": "",
        "required": "否",
        "default": "",
        "note": "填写供应链、报价、精算来源等备注。",
    },
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a profit review template from research_package.json.")
    parser.add_argument("research_package_json")
    parser.add_argument("output_xlsx")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    package_path = Path(args.research_package_json).expanduser().resolve()
    output_path = Path(args.output_xlsx).expanduser().resolve()
    package = json.loads(package_path.read_text(encoding="utf-8"))
    render_profit_template(package, output_path)
    print(f"Wrote profit template: {output_path}")
    return 0


def render_profit_template(package: dict[str, Any], output_path: Path) -> None:
    meta = package.get("metadata", {})
    market = package.get("market_analysis", {})
    return_risk = package.get("return_risk", {})
    _write_xlsx(
        output_path,
        [
            (
                "填写说明",
                [
                    ["项", "值"],
                    ["候选方向", meta.get("seed_keyword_or_category", "")],
                    ["站点", meta.get("site", "")],
                    ["价格带参考", market.get("price_band", "")],
                    ["市场退货率", return_risk.get("market_return_rate", "")],
                    ["类目退货率", return_risk.get("category_return_rate", "")],
                    ["说明", "只填写「利润输入」Sheet 的 value 列；空值会在回填时标记待补。"],
                ],
            ),
            ("利润输入", profit_input_rows(package)),
            (
                "字段口径",
                [
                    ["字段", "口径"],
                    ["建议售价/FBA费用", "按站点币种填写，例如美国站填美元。"],
                    ["采购价/头程/入库配置费", "按人民币填写，系统用站点汇率换算成站点币种。"],
                    ["头程费用", "可直接填人民币头程费用；或填实际重、体积重、头程渠道让系统估算。"],
                    ["仓储费", "默认按建议售价 3% 简化估算。"],
                    ["广告费", "默认按建议售价 20% 估算。"],
                    ["退货损失", "默认按建议售价 * 退货率估算。"],
                ],
            ),
        ],
    )


def profit_input_rows(package: dict[str, Any]) -> list[list[Any]]:
    rows: list[list[Any]] = [["field", "label", "value", "填写口径", "是否必填", "default", "note"]]
    return_rate = default_return_rate(package)
    for item in INPUT_ROWS:
        default = item["default"]
        if item["field"] == "return_rate" and return_rate is not None:
            default = return_rate
        rows.append(
            [
                item["field"],
                item["label"],
                default,
                item["currency"],
                item["required"],
                item["default"],
                item["note"],
            ]
        )
    return rows


def default_return_rate(package: dict[str, Any]) -> float | None:
    return_risk = package.get("return_risk", {})
    for key in ("category_return_rate", "market_return_rate"):
        value = return_risk.get(key)
        if isinstance(value, (int, float)):
            return float(value)
    return None


if __name__ == "__main__":
    raise SystemExit(main())
