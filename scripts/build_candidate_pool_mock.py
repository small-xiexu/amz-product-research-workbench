#!/usr/bin/env python3
"""Build a deterministic mock candidate pool from a selection brief."""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any


def build_candidate_pool(brief: dict[str, Any]) -> dict[str, Any]:
    site = brief.get("site", "US")
    brief_id = brief.get("brief_id", "brief-mock")
    scope = brief.get("search_scope", {})
    scope_text = _scope_text(scope)
    risk_text = " ".join(
        [
            " ".join(brief.get("exclusion_rules", [])),
            " ".join(brief.get("product_flags", [])),
            json.dumps(brief.get("risk_tolerance", {}), ensure_ascii=False),
        ]
    )

    candidates = []
    if _contains_any(scope_text, ["家居", "收纳", "home", "organizer"]):
        candidates.append(_home_storage_candidate())
    if _contains_any(scope_text, ["户外", "露营", "应急", "outdoor", "camping"]):
        candidates.append(_camping_accessory_candidate(risk_text))
    if not candidates:
        candidates.append(_generic_lightweight_candidate())

    summary = _summary(candidates)
    return {
        "metadata": {
            "pool_id": f"pool-{brief_id}",
            "site": site,
            "generated_at": brief.get("created_at", ""),
            "discovery_mode": "mock",
            "data_sources": ["operator-input", "mock"],
        },
        "source_brief": {
            "brief_id": brief_id,
            "site": site,
            "search_scope": scope,
            "exclusion_rules": brief.get("exclusion_rules", []),
            "preference_rules": brief.get("preference_rules", {}),
        },
        "summary": summary,
        "candidates": candidates,
    }


def _scope_text(scope: dict[str, Any]) -> str:
    parts = [str(scope.get("free_text", ""))]
    for key in ("categories", "keywords", "scenarios"):
        parts.extend(str(item) for item in scope.get(key, []))
    return " ".join(parts).lower()


def _contains_any(text: str, needles: list[str]) -> bool:
    return any(needle.lower() in text for needle in needles)


def _base_candidate(candidate_id: str, name: str, status: str, reason: str) -> dict[str, Any]:
    return {
        "candidate_id": candidate_id,
        "name": name,
        "candidate_type": "product_direction",
        "status": status,
        "reason": reason,
        "appearance_reason": [],
        "demand_evidence": {
            "search_signal": "待用卖家精灵导出数据验证",
            "trend_signal": "待验证",
            "top100_signal": "待用 Top100 验证",
            "source_refs": ["mock"],
            "confidence": "低",
        },
        "competition_structure": {
            "price_band": "待填",
            "brand_concentration": "待填",
            "seller_concentration": "待填",
            "review_threshold": "待填",
            "notes": "需要真实数据验证。",
        },
        "new_listing_opportunity": {
            "signal": "待验证",
            "recent_asins": [],
            "threshold_note": "真实数据阶段看近半年上架且 BSR 前100或月销量达到 Top100 中位数20%的 ASIN。",
        },
        "preliminary_profit_space": {
            "price_band": "待验证",
            "size_weight_assumption": "待验证",
            "fee_pressure": "待验证",
            "confidence": "低",
        },
        "risk_flags": [],
        "return_risk": {"level": "待确认", "source": "待卖家精灵类目退货率"},
        "ip_compliance_risk": {"level": "待确认"},
        "data_quality": {
            "completeness": "mock only",
            "variant_policy": "真实数据阶段需标记多 SKU/变体口径",
        },
        "missing_data": ["Top100", "关键词搜索量", "类目退货率", "竞品池", "知产/合规初筛"],
        "next_step": "导入卖家精灵手动导出数据后验证；MCP 后续增强。",
        "source_refs": ["mock:candidate_pool"],
    }


def _home_storage_candidate() -> dict[str, Any]:
    candidate = _base_candidate(
        "cand-wall-organizer-hooks",
        "轻量墙面收纳挂钩/轨道配件",
        "继续看",
        "符合轻小、非强认证、家居收纳场景，适合进入真实数据验证。",
    )
    candidate["appearance_reason"] = ["匹配家居收纳方向", "初步不触发强认证", "有组合规格和场景化溢价空间"]
    candidate["preliminary_profit_space"].update(
        {
            "price_band": "10-30 USD 假设",
            "size_weight_assumption": "轻小假设",
            "fee_pressure": "低到中，待 FBA 和头程复核",
        }
    )
    candidate["risk_flags"] = ["同质化待验证", "低价内卷待验证"]
    return candidate


def _camping_accessory_candidate(risk_text: str) -> dict[str, Any]:
    status = "观察"
    risk_flags = ["季节性待验证", "合规待确认"]
    if _contains_any(risk_text.lower(), ["带电", "电池", "battery"]):
        risk_flags.insert(0, "带电/电池风险")

    candidate = _base_candidate(
        "cand-camping-accessory",
        "露营/应急场景轻小配件",
        status,
        "匹配户外和应急场景，但需要先确认是否触发带电、季节性或强认证风险。",
    )
    candidate["candidate_type"] = "scenario_direction"
    candidate["appearance_reason"] = ["匹配户外露营场景", "可能有应急备用需求"]
    candidate["preliminary_profit_space"].update(
        {
            "price_band": "10 USD 以上假设",
            "size_weight_assumption": "轻小到中等，待确认",
            "fee_pressure": "中，待合规和物流复杂度验证",
        }
    )
    candidate["risk_flags"] = risk_flags
    candidate["ip_compliance_risk"] = {"level": "中", "notes": "带电或含电池时需前置合规复核。"}
    candidate["missing_data"] = ["是否带电/电池", "Top100", "关键词趋势", "CPC", "合规材料"]
    candidate["next_step"] = "先用卖家精灵手动导出数据判断是否有非带电、轻小配件切入点；MCP 后续增强。"
    return candidate


def _generic_lightweight_candidate() -> dict[str, Any]:
    candidate = _base_candidate(
        "cand-generic-lightweight-accessory",
        "轻小非强认证配件方向",
        "观察",
        "当前方向过宽，先生成占位候选，等待卖家精灵手动导出数据替换为真实候选。",
    )
    candidate["appearance_reason"] = ["初始意图未给明确大类", "按轻小和非强认证偏好保留观察"]
    candidate["risk_flags"] = ["方向过宽", "需要广域扫描"]
    candidate["missing_data"] = ["候选市场", "关键词池", "Top100", "竞品池", "风险初筛"]
    return candidate


def _summary(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    counts = {"继续看": 0, "试做": 0, "观察": 0, "先放弃": 0}
    for candidate in candidates:
        counts[candidate["status"]] += 1
    return {
        "total_candidates": len(candidates),
        "continue_count": counts["继续看"],
        "trial_count": counts["试做"],
        "watch_count": counts["观察"],
        "drop_count": counts["先放弃"],
        "key_gaps": ["缺真实 Top100 数据", "缺类目退货率", "缺知产/合规初筛"],
    }


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: build_candidate_pool_mock.py <selection_brief_json> <output_json>")
        return 1

    brief_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])
    brief = json.loads(brief_path.read_text(encoding="utf-8"))
    candidate_pool = build_candidate_pool(brief)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(candidate_pool, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
