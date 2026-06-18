#!/usr/bin/env python3
"""Apply normalized 1688 supply-chain signal to a candidate_pool."""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


VISUAL_STATUS_LABELS = {
    "visual_confirmed": "优先联系",
    "visual_partial": "观察待核",
    "visual_rejected": "剔除错品",
}


def _select_candidate(candidates: list[dict[str, Any]], candidate_id: str = "") -> int:
    if not candidates:
        raise ValueError("candidate_pool has no candidates")
    if not candidate_id:
        return 0
    for index, candidate in enumerate(candidates):
        if candidate.get("candidate_id") == candidate_id:
            return index
    raise ValueError(f"candidate_id not found: {candidate_id}")


def apply_supply_chain_signal(
    candidate_pool: dict[str, Any],
    signal: dict[str, Any],
    *,
    candidate_id: str = "",
    candidates_file: str = "",
) -> dict[str, Any]:
    result = json.loads(json.dumps(candidate_pool, ensure_ascii=False))
    candidates = result.get("candidates") or []
    target_index = _select_candidate(candidates, candidate_id)
    candidate = candidates[target_index]
    profit_space = candidate.get("preliminary_profit_space") or {}
    data_quality = candidate.get("data_quality") or {}
    conservative_cny = signal.get("conservative_purchase_price_cny") or signal.get("purchase_price_cny_max")
    conservative_text = f"；保守估算按 RMB {conservative_cny}" if conservative_cny is not None else ""

    profit_space["supply_chain_signal"] = signal
    profit_space["cogs_signal"] = (
        f"1688中国站人民币采购价区间 RMB {signal.get('purchase_price_cny_min', '待补')}"
        f"-{signal.get('purchase_price_cny_max', '待补')}；"
        f"{conservative_text.lstrip('；') if conservative_text else '保守估算价待补'}；"
        f"RMB报价有效样本 {signal.get('supplier_count', 0)} 条；"
        f"视觉待复核 {signal.get('visual_review_queue_count', 0)} 条"
    )
    if signal.get("conservative_purchase_price_usd") is not None:
        profit_space["estimated_purchase_cost_usd"] = signal.get("conservative_purchase_price_usd")
    elif signal.get("purchase_price_usd_avg") is not None:
        profit_space["estimated_purchase_cost_usd"] = signal.get("purchase_price_usd_avg")

    data_quality["supply_chain_signal"] = {
        "enabled": True,
        "source_tool": signal.get("source_tool", "1688_supply_chain_harvester"),
        "source_site": signal.get("source_site", "1688中国站"),
        "supplier_count": signal.get("supplier_count"),
        "relevant_supplier_count": signal.get("relevant_supplier_count"),
        "evidence_count": signal.get("evidence_count"),
        "candidates_file": candidates_file,
        "note": signal.get("note", ""),
    }

    missing_data = [item for item in candidate.get("missing_data", []) if item not in {"采购价", "1688供应链复核"}]
    if "利润测算" not in missing_data and any(item in missing_data for item in ("FBA费用", "头程费用", "入库配置费")):
        pass
    candidate["missing_data"] = missing_data
    candidate["preliminary_profit_space"] = profit_space
    candidate["data_quality"] = data_quality
    refs = list(candidate.get("source_refs") or [])
    if "1688_supply_chain_harvester" not in refs:
        refs.append("1688_supply_chain_harvester")
    candidate["source_refs"] = refs

    metadata = result.get("metadata") or {}
    data_sources = list(metadata.get("data_sources") or [])
    if "1688_supply_chain_harvester" not in data_sources:
        data_sources.append("1688_supply_chain_harvester")
    metadata["data_sources"] = data_sources
    metadata["supply_chain_applied_at"] = signal.get("generated_at") or datetime.now(timezone.utc).isoformat()
    result["metadata"] = metadata
    candidates[target_index] = candidate
    result["candidates"] = candidates
    return result


def _load_supply_chain_candidates(signal_path: Path, candidates_file: str) -> list[dict[str, Any]]:
    if not candidates_file:
        return []
    candidates_path = Path(candidates_file)
    if not candidates_path.is_absolute():
        candidates_path = signal_path.parent / candidates_path
    if not candidates_path.exists():
        return []
    try:
        payload = json.loads(candidates_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    candidates = payload.get("candidates")
    return candidates if isinstance(candidates, list) else []


def _supply_chain_review_item(item: dict[str, Any]) -> dict[str, Any]:
    review = item.get("operator_visual_review") if isinstance(item.get("operator_visual_review"), dict) else {}
    status = str(item.get("visual_review_status") or "").strip()
    action = str(review.get("recommended_action") or item.get("final_supply_status") or "").strip()
    sku_texts = item.get("sku_texts") if isinstance(item.get("sku_texts"), list) else []
    sku_options = item.get("sku_options") if isinstance(item.get("sku_options"), list) else []
    return {
        "title": item.get("title"),
        "url": item.get("url"),
        "keyword": item.get("keyword"),
        "price_text": item.get("price_text"),
        "price_cny_min": item.get("price_cny_min"),
        "price_cny_max": item.get("price_cny_max"),
        "detail_price_text": item.get("detail_price_text"),
        "detail_price_cny_min": item.get("detail_price_cny_min"),
        "detail_price_cny_max": item.get("detail_price_cny_max"),
        "conservative_price_cny": item.get("conservative_price_cny"),
        "conservative_price_basis": item.get("conservative_price_basis"),
        "moq_text": item.get("moq_text"),
        "supplier_text": item.get("supplier_text"),
        "supplier_tags": item.get("supplier_tags") or [],
        "sku_texts": sku_texts[:8],
        "sku_options": sku_options[:8],
        "stock_text": item.get("stock_text"),
        "customization_text": item.get("customization_text"),
        "detail_summary": item.get("detail_summary"),
        "detail_text_excerpt": item.get("detail_text_excerpt"),
        "status": status,
        "status_label": VISUAL_STATUS_LABELS.get(status, action or status),
        "recommended_action": action,
        "rationale": review.get("rationale", ""),
        "risk_notes": review.get("risk_notes", []),
        "confidence": review.get("confidence"),
        "image_urls": (item.get("visual_evidence_image_urls") or [])[:3],
    }


def _build_supply_chain_review_summary(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    confirmed = [
        _supply_chain_review_item(item)
        for item in candidates
        if item.get("visual_review_status") == "visual_confirmed"
    ]
    partial = [
        _supply_chain_review_item(item)
        for item in candidates
        if item.get("visual_review_status") == "visual_partial"
    ]
    rejected = [
        _supply_chain_review_item(item)
        for item in candidates
        if item.get("visual_review_status") == "visual_rejected"
    ]
    return {
        "priority_candidates": confirmed,
        "watchlist_candidates": partial,
        "rejected_count": len(rejected),
        "reviewed_count": len(confirmed) + len(partial) + len(rejected),
        "summary": (
            f"图文复核后优先联系 {len(confirmed)} 款，观察待核 {len(partial)} 款，"
            f"剔除错品 {len(rejected)} 款。"
        ),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply 1688 supply-chain signal to candidate_pool.json.")
    parser.add_argument("candidate_pool_json")
    parser.add_argument("supply_chain_signal_json")
    parser.add_argument("--candidate-id", default="")
    parser.add_argument("--candidates-file", default="")
    parser.add_argument("--in-place", action="store_true", help="Update candidate_pool_json in place.")
    parser.add_argument("--output", default="", help="Output path when not using --in-place.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    pool_path = Path(args.candidate_pool_json).expanduser().resolve()
    signal_path = Path(args.supply_chain_signal_json).expanduser().resolve()
    if not pool_path.exists():
        raise SystemExit(f"candidate_pool.json not found: {pool_path}")
    if not signal_path.exists():
        raise SystemExit(f"supply_chain_signal.json not found: {signal_path}")
    pool = json.loads(pool_path.read_text(encoding="utf-8"))
    signal = json.loads(signal_path.read_text(encoding="utf-8"))
    candidates_payload = _load_supply_chain_candidates(signal_path, args.candidates_file)
    if candidates_payload:
        signal["visual_review_candidates"] = _build_supply_chain_review_summary(candidates_payload)
    updated = apply_supply_chain_signal(
        pool,
        signal,
        candidate_id=args.candidate_id,
        candidates_file=args.candidates_file,
    )
    if args.in_place:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        backup_path = pool_path.with_name(f"{pool_path.stem}.pre_1688_supply_chain_{stamp}.json")
        shutil.copy2(pool_path, backup_path)
        output_path = pool_path
        print(f"Backup saved: {backup_path}")
    else:
        if not args.output:
            raise SystemExit("--output is required unless --in-place is set")
        output_path = Path(args.output).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(updated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"candidate_pool updated: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
