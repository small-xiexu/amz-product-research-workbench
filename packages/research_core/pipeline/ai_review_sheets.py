#!/usr/bin/env python3
"""AI 审核脚本无法自动识别的 sheet，生成 overrides 供候选池构建使用。

流程：
  1. inspect_manual_exports.py 生成 import_manifest.json
  2. 本模块 find_review_candidates() 提取 unknown / 缺必需字段的 sheet
  3. Claude 审核后输出 sheet_overrides.json
  4. build_candidate_pool_from_import_manifest.py --sheet-overrides 应用校正
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

KNOWN_ROLES = [
    "market_overview",
    "product_concentration",
    "brand_concentration",
    "seller_concentration",
    "seller_type_distribution",
    "seller_location_distribution",
    "a_plus_video_distribution",
    "market_demand_signal",
    "listing_age_distribution",
    "listing_year_distribution",
    "rating_count_distribution",
    "rating_value_distribution",
    "price_distribution",
    "market_keyword_trend",
    "market_sales_trend",
    "brand_summary",
    "seller_summary",
    "reverse_asin_keywords",
    "aba_keywords",
    "aba_keyword_trend",
    "unique_words",
    "notes",
    "skip",
]


def find_review_candidates(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    """从 manifest 中提取脚本无法确定角色或缺必需字段的 sheet。"""
    candidates: list[dict[str, Any]] = []
    for file_entry in manifest.get("files", []):
        for sheet in file_entry.get("sheets", []):
            role = sheet.get("detected_role", "")
            missing = sheet.get("missing_required_fields", [])
            if role == "unknown" or missing:
                candidates.append({
                    "file_name": file_entry["file_name"],
                    "relative_path": file_entry.get("relative_path", ""),
                    "sheet_name": sheet["sheet_name"],
                    "detected_role": role,
                    "headers": sheet.get("headers", []),
                    "missing_required_fields": missing,
                    "sample_rows": sheet.get("sample_rows", []),
                })
    return candidates


def apply_overrides(manifest: dict[str, Any], overrides: list[dict[str, Any]]) -> int:
    """将 AI 审核的 overrides 写入 manifest（原地修改）。返回成功应用的条数。"""
    lookup: dict[tuple[str, str], dict[str, Any]] = {}
    for ov in overrides:
        key = (ov.get("file_name", ""), ov.get("sheet_name", ""))
        lookup[key] = ov

    applied = 0
    for file_entry in manifest.get("files", []):
        fn = file_entry.get("file_name", "")
        for sheet in file_entry.get("sheets", []):
            key = (fn, sheet["sheet_name"])
            override = lookup.get(key)
            if not override:
                continue

            new_role = override.get("corrected_role", "")
            if new_role == "skip":
                sheet["detected_role"] = "notes"
                sheet["ai_skip"] = True
                applied += 1
            elif new_role and new_role != sheet.get("detected_role", ""):
                if new_role not in KNOWN_ROLES:
                    print(f"WARNING: sheet_overrides 中 corrected_role='{new_role}' 不在 KNOWN_ROLES 中，"
                          f"已跳过 (file={fn}, sheet={sheet['sheet_name']})")
                    continue
                sheet["detected_role"] = new_role
                sheet["ai_corrected_role"] = True
                applied += 1

            remap = override.get("column_remap")
            if remap:
                sheet["column_remap"] = remap

    return applied
