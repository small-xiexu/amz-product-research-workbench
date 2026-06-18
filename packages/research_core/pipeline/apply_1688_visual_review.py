#!/usr/bin/env python3
"""Apply URL-based 1688 visual/detail review results to normalized supply-chain files."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ACTION_TO_STATUS = {
    "priority_contact": ("visual_confirmed", "priority_contact"),
    "watchlist_verify_detail": ("visual_partial", "watchlist_verify_detail"),
    "reject_not_target_shape": ("visual_rejected", "reject_not_target_shape"),
}


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _review_by_url(review_result: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in review_result.get("reviewed_items") or []:
        url = str(item.get("url") or "").strip()
        review = item.get("operator_visual_review") if isinstance(item.get("operator_visual_review"), dict) else {}
        if url and review:
            result[url] = review
    return result


def _apply_to_item(item: dict[str, Any], review: dict[str, Any] | None) -> dict[str, Any]:
    if not review:
        return item
    action = str(review.get("recommended_action") or "").strip()
    visual_status, final_status = ACTION_TO_STATUS.get(action, ("visual_reviewed", action or "reviewed"))
    next_item = dict(item)
    next_item["visual_review_status"] = visual_status
    next_item["final_supply_status"] = final_status
    next_item["stage3_visual_detail_review_status"] = visual_status
    next_item["stage3_visual_detail_review_required"] = False
    next_item["operator_visual_review"] = review
    return next_item


def apply_visual_review(
    signal: dict[str, Any],
    candidates_payload: dict[str, Any],
    queue_payload: dict[str, Any],
    review_result: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    reviews = _review_by_url(review_result)
    reviewed_urls = set(reviews)

    candidates = [
        _apply_to_item(item, reviews.get(str(item.get("url") or "").strip()))
        for item in candidates_payload.get("candidates") or []
    ]
    queue = [
        _apply_to_item(item, reviews.get(str(item.get("url") or "").strip()))
        for item in queue_payload.get("visual_review_queue") or []
    ]

    status_counts = Counter(item.get("visual_review_status") or "pending" for item in candidates)
    detail_status_counts = Counter(item.get("detail_review_status") or "pending" for item in candidates)
    queue_status_counts = Counter(item.get("visual_review_status") or "pending" for item in queue)
    reviewed_count = sum(status_counts.get(status, 0) for status in ("visual_confirmed", "visual_partial", "visual_rejected", "visual_reviewed"))
    confirmed_count = status_counts.get("visual_confirmed", 0)
    partial_count = status_counts.get("visual_partial", 0)
    rejected_count = status_counts.get("visual_rejected", 0)

    next_signal = dict(signal)
    next_signal.update(
        {
            "visual_reviewed_count": reviewed_count,
            "visual_confirmed_count": confirmed_count,
            "visual_partial_count": partial_count,
            "visual_rejected_count": rejected_count,
            "visual_pending_count": max(0, len(candidates) - reviewed_count),
            "relevant_supplier_count": confirmed_count,
            "detail_review_status_breakdown": dict(detail_status_counts),
            "visual_review_status_breakdown": dict(status_counts),
            "visual_review_queue_status_breakdown": dict(queue_status_counts),
            "visual_review_result_file": review_result.get("source_queue") or "",
            "visual_review_applied_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    if reviewed_urls:
        next_signal["confidence"] = (
            f"中：已按 URL 回填 {reviewed_count} 条图片/详情远程复核，其中 "
            f"{confirmed_count} 条优先深挖、{partial_count} 条观察、{rejected_count} 条剔除；"
            "仍需供应商确认、样品、真实报价和合规复核。"
        )
        next_signal["note"] = (
            "1688中国站人民币报价不含头程、关税、质检、包装和损耗；"
            "图片/详情远程复核只解决商品形态初判，最终通过仍需供应商确认整套价格、样品质量、包装重量、授权/IP和合规。"
        )

    next_candidates = dict(candidates_payload)
    next_candidates["candidates"] = candidates
    next_candidates["visual_review_applied_at"] = next_signal["visual_review_applied_at"]

    next_queue = dict(queue_payload)
    next_queue["visual_review_queue"] = queue
    next_queue["review_applied_by_url_count"] = len(reviewed_urls)
    next_queue["visual_review_applied_at"] = next_signal["visual_review_applied_at"]
    return next_signal, next_candidates, next_queue


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply 1688 visual review result to supply-chain files.")
    parser.add_argument("supply_chain_signal_json")
    parser.add_argument("supply_chain_candidates_json")
    parser.add_argument("supply_chain_visual_review_queue_json")
    parser.add_argument("visual_review_result_json")
    parser.add_argument("--in-place", action="store_true")
    parser.add_argument("--output-dir", default="")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    signal_path = Path(args.supply_chain_signal_json).expanduser().resolve()
    candidates_path = Path(args.supply_chain_candidates_json).expanduser().resolve()
    queue_path = Path(args.supply_chain_visual_review_queue_json).expanduser().resolve()
    review_path = Path(args.visual_review_result_json).expanduser().resolve()
    signal, candidates, queue = apply_visual_review(
        _read_json(signal_path),
        _read_json(candidates_path),
        _read_json(queue_path),
        _read_json(review_path),
    )
    output_dir = signal_path.parent if args.in_place else Path(args.output_dir).expanduser().resolve()
    if not args.in_place and not args.output_dir:
        raise SystemExit("--output-dir is required unless --in-place is set")
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / signal_path.name, signal)
    _write_json(output_dir / candidates_path.name, candidates)
    _write_json(output_dir / queue_path.name, queue)
    print(f"visual reviewed: {signal.get('visual_reviewed_count', 0)}")
    print(f"visual confirmed: {signal.get('visual_confirmed_count', 0)}")
    print(f"visual partial: {signal.get('visual_partial_count', 0)}")
    print(f"visual rejected: {signal.get('visual_rejected_count', 0)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
