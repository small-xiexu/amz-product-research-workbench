#!/usr/bin/env python3
"""Merge a Sorftime verification JSON into an existing candidate_pool.json.

Usage (Claude runs this after calling Sorftime MCP tools in conversation):

    python3 scripts/apply_sorftime_verification.py \\
        <candidate_pool.json> \\
        <sorftime_verification.json> \\
        [--candidate-id <id>]  # defaults to first candidate

The sorftime_verification.json must follow this schema:

{
  "verified_at": "2026-06-11",
  "category_trend": {
    "trend_direction": "增长 | 衰退 | 均衡 | 季节性",
    "monthly_sales_24m": [...],
    "top3_concentration_trend": "集中 | 分散 | 恶化",
    "new_product_share_trend": "上升 | 下降 | 均衡"
  },
  "keyword_verification": [
    {
      "keyword": "window squeegee",
      "weekly_search_volume": 45000,
      "monthly_search_volume": 180000,
      "cpc": 1.2,
      "seasonality": "均衡 | 旺季Q4",
      "competitor_count": 12000,
      "trend_direction": "增长"
    }
  ],
  "traffic_terms": {
    "asin": "B0XXXXX",
    "top_traffic_words": ["window squeegee"],
    "gap_opportunities": ["2 in 1 window cleaning tool"]
  },
  "category_report_snapshot": {
    "category_name": "Squeegees",
    "nodeId": "2245500011",
    "products": [
      {
        "asin": "B0XXXXX",
        "title": "Sample product",
        "brand": "Sample",
        "price": 19.99,
        "monthly_sales": 1200,
        "rating": 4.5,
        "rating_count": 300,
        "listing_days": 120
      }
    ]
  },
  "supply_chain_signal": {
    "searchName": "刮窗器",
    "exchange_rate": 7.2,
    "products": [
      {
        "title": "1688 sample",
        "price": "12-18",
        "supplier": "示例供应商"
      }
    ]
  }
}

Claude should write this JSON to a file and then call this script.
The updated candidate_pool.json is written back in place (original is preserved
as candidate_pool.pre_sorftime.json).
"""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from build_candidate_pool_from_import_manifest import merge_sorftime_signals


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Merge Sorftime verification results into an existing candidate_pool.json."
    )
    parser.add_argument("candidate_pool", help="Path to candidate_pool.json.")
    parser.add_argument("sorftime_verification", help="Path to sorftime_verification.json.")
    parser.add_argument("--candidate-id", default="", help="Candidate ID to update. Defaults to first candidate.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    pool_path = Path(args.candidate_pool).expanduser().resolve()
    sv_path = Path(args.sorftime_verification).expanduser().resolve()

    if not pool_path.exists():
        raise SystemExit(f"candidate_pool.json not found: {pool_path}")
    if not sv_path.exists():
        raise SystemExit(f"sorftime_verification.json not found: {sv_path}")

    pool = json.loads(pool_path.read_text(encoding="utf-8"))
    sorftime_verification = json.loads(sv_path.read_text(encoding="utf-8"))

    candidates = pool.get("candidates", [])
    if not candidates:
        raise SystemExit("candidate_pool has no candidates")

    target_idx = 0
    if args.candidate_id:
        for i, c in enumerate(candidates):
            if c.get("candidate_id") == args.candidate_id:
                target_idx = i
                break
        else:
            raise SystemExit(f"candidate_id not found: {args.candidate_id}")

    backup_path = pool_path.with_name(pool_path.stem + ".pre_sorftime.json")
    shutil.copy2(pool_path, backup_path)

    candidates[target_idx] = merge_sorftime_signals(candidates[target_idx], sorftime_verification)
    pool["candidates"] = candidates

    metadata = pool.get("metadata", {})
    metadata["discovery_mode"] = "mixed"
    metadata["sorftime_verified_at"] = sorftime_verification.get("verified_at", datetime.now(timezone.utc).date().isoformat())
    pool["metadata"] = metadata

    pool_path.write_text(json.dumps(pool, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    candidate_name = candidates[target_idx].get("name", "")
    print(f"Updated candidate: {candidates[target_idx].get('candidate_id')} / {candidate_name}")
    print(f"Backup saved: {backup_path}")
    print(f"candidate_pool.json updated in place: {pool_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
