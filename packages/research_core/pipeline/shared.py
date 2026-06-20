"""Shared pipeline utilities — no business judgment, no domain-specific logic."""

from __future__ import annotations

from typing import Any



PREFERRED_STATUSES = ("继续看", "试做", "观察", "先放弃")

_TITLE_NOISE_TOKENS: set[str] = {
    "a",
    "amazon",
    "an",
    "and",
    "border",
    "color",
    "count",
    "cross",
    "extra",
    "factory",
    "for",
    "hot",
    "inch",
    "inches",
    "large",
    "medium",
    "new",
    "ounce",
    "ounces",
    "pack",
    "piece",
    "pound",
    "sale",
    "size",
    "small",
    "the",
    "wholesale",
    "with",
    "亚马逊",
    "厂家",
    "批发",
    "新品",
    "现货",
    "跨境",
}



def _select_candidate(candidates: list[dict[str, Any]], candidate_id: str | None) -> dict[str, Any]:
    if not candidates:
        raise ValueError("candidate_pool.candidates is empty")

    if candidate_id and candidate_id not in ("", "__first__"):
        for candidate in candidates:
            if candidate.get("candidate_id") == candidate_id:
                return candidate
        raise ValueError(f"candidate_id not found: {candidate_id}")

    for status in PREFERRED_STATUSES:
        for candidate in candidates:
            if candidate.get("status") == status:
                return candidate
    return candidates[0]

def _dedupe_strings(items: list[str]) -> list[str]:
    """Keep first occurrence order, deduplicate."""
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        s = str(item).strip()
        if s and s not in seen:
            seen.add(s)
            result.append(s)
    return result
