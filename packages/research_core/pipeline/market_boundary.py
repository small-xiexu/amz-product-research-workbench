"""Market boundary audit: detecting broad keywords, competitor relevance, and anchor terms.

This module replaces the previous hardcoded blocklists (_BROAD_KEYWORD_PATTERNS,
_MARKET_NOISE_TERMS) with generic linguistic heuristics and anchor-threshold matching.
"""

from __future__ import annotations

import re
from typing import Any
from packages.research_core.pipeline.shared import _dedupe_strings, _TITLE_NOISE_TOKENS

# 不再使用具体品类噪音词列表。
# 代之以锚点匹配门槛：如果锚点词充足但产品零命中，即为噪音。
# 具体逻辑见 _competitor_market_relevance。

_GENERIC_CATEGORY_NOUNS = {
    "accessories",
    "supplies",
    "goods",
    "household",
    "essentials",
    "products",
    "items",
    "tools",
    "equipment",
    "gear",
    "stuff",
    "things",
    "collection",
    "series",
    "line",
    "range",
}


def _apply_market_boundary_quality(candidate: dict[str, Any]) -> dict[str, Any]:
    cleaned = dict(candidate)
    audit = _build_market_boundary_audit(cleaned)
    cleaned["competitor_candidates"] = _filtered_competitor_candidates(cleaned, audit)
    cleaned["next_review_voc_asins"] = _filtered_review_voc_asins(cleaned, audit)
    cleaned["market_boundary_audit"] = audit
    return cleaned


def _build_market_boundary_audit(candidate: dict[str, Any]) -> dict[str, Any]:
    anchors = _market_anchor_terms(candidate)
    groups = candidate.get("competitor_candidates", {}) if isinstance(candidate.get("competitor_candidates"), dict) else {}
    total_count = 0
    excluded: list[dict[str, Any]] = []
    suspect: list[dict[str, Any]] = []
    relevant_count = 0
    for group_key, items in groups.items():
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            total_count += 1
            relevance = _competitor_market_relevance(item, anchors)
            row = {
                "asin": item.get("asin"),
                "title": item.get("title"),
                "group": group_key,
                "status": relevance["status"],
                "reason": relevance["reason"],
                "matched_terms": relevance["matched_terms"],
            }
            if relevance["status"] == "剔除":
                excluded.append(row)
            elif relevance["status"] == "需复核":
                suspect.append(row)
            else:
                relevant_count += 1
    top_keyword = str((candidate.get("demand_evidence", {}) or {}).get("top_keyword") or "").strip()
    broad_keyword = top_keyword if _is_broad_market_keyword(top_keyword) else ""
    notes: list[str] = []
    if broad_keyword:
        notes.append(f"核心词「{broad_keyword}」过宽，不能作为目标小类成交词。")
    if excluded:
        notes.append(f"竞品池剔除 {len(excluded)} 个明显非同类样本。")
    if suspect:
        notes.append(f"仍有 {len(suspect)} 个边界样本需要运营复核。")
    quality_status = "待清洗" if excluded or broad_keyword else ("需复核" if suspect else "通过")
    return {
        "quality_status": quality_status,
        "anchor_terms": anchors["phrases"][:12],
        "anchor_tokens": anchors["tokens"][:12],
        "broad_keyword": broad_keyword,
        "total_competitor_count": total_count,
        "relevant_competitor_count": relevant_count,
        "suspect_competitor_count": len(suspect),
        "excluded_competitor_count": len(excluded),
        "excluded_samples": excluded[:12],
        "suspect_samples": suspect[:12],
        "notes": notes,
    }


def _filtered_competitor_candidates(candidate: dict[str, Any], audit: dict[str, Any]) -> dict[str, Any]:
    anchors = {
        "phrases": audit.get("anchor_terms", []),
        "tokens": audit.get("anchor_tokens", []),
    }
    groups = candidate.get("competitor_candidates", {}) if isinstance(candidate.get("competitor_candidates"), dict) else {}
    cleaned: dict[str, Any] = {}
    for group_key, items in groups.items():
        if not isinstance(items, list):
            cleaned[group_key] = items
            continue
        kept: list[dict[str, Any]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            relevance = _competitor_market_relevance(item, anchors)
            if relevance["status"] == "剔除":
                continue
            kept.append(
                {
                    **item,
                    "market_boundary_status": relevance["status"],
                    "market_boundary_reason": relevance["reason"],
                    "market_boundary_terms": relevance["matched_terms"],
                }
            )
        cleaned[group_key] = kept
    return cleaned


def _filtered_review_voc_asins(candidate: dict[str, Any], audit: dict[str, Any]) -> list[dict[str, Any]]:
    items = candidate.get("next_review_voc_asins")
    if not isinstance(items, list):
        return []
    anchors = {
        "phrases": audit.get("anchor_terms", []),
        "tokens": audit.get("anchor_tokens", []),
    }
    result: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        relevance = _competitor_market_relevance(item, anchors)
        if relevance["status"] == "剔除":
            continue
        result.append(
            {
                **item,
                "market_boundary_status": relevance["status"],
                "market_boundary_reason": relevance["reason"],
                "market_boundary_terms": relevance["matched_terms"],
            }
        )
    return result


def _market_anchor_terms(candidate: dict[str, Any]) -> dict[str, list[str]]:
    demand = candidate.get("demand_evidence", {}) if isinstance(candidate.get("demand_evidence"), dict) else {}
    raw_terms: list[str] = []
    for key in ("aba_top_search_term", "top_keyword"):
        value = demand.get(key)
        if value and not _is_broad_market_keyword(str(value)):
            raw_terms.append(str(value))
    aba_signal = demand.get("aba_keyword_signal", {}) if isinstance(demand.get("aba_keyword_signal"), dict) else {}
    top_keywords = aba_signal.get("top_keywords") if isinstance(aba_signal.get("top_keywords"), list) else []
    for item in top_keywords[:10]:
        if isinstance(item, dict) and item.get("keyword"):
            raw_terms.append(str(item.get("keyword")))
    sf_keywords = demand.get("sorftime_keyword_verification") if isinstance(demand.get("sorftime_keyword_verification"), list) else []
    for item in sf_keywords[:10]:
        if isinstance(item, dict) and item.get("keyword"):
            raw_terms.append(str(item.get("keyword")))
    category = demand.get("sorftime_category_report", {}) if isinstance(demand.get("sorftime_category_report"), dict) else {}
    if category.get("category_name"):
        raw_terms.append(str(category.get("category_name")))
    title_token_counts: dict[str, int] = {}
    title_sources = []
    market_structure = candidate.get("market_structure", {}) if isinstance(candidate.get("market_structure"), dict) else {}
    for source in (candidate.get("top_products"), market_structure.get("tagged_products")):
        if isinstance(source, list):
            title_sources.extend(item for item in source[:120] if isinstance(item, dict))
    for item in title_sources:
        title = _normalize_market_text(item.get("title") or item.get("Title") or "")
        for token in re.findall(r"[a-z0-9]+", title):
            if len(token) >= 4 and token not in _TITLE_NOISE_TOKENS:
                title_token_counts[token] = title_token_counts.get(token, 0) + 1

    phrases: list[str] = []
    tokens: list[str] = []
    for term in raw_terms:
        clean = _normalize_market_text(term)
        if not clean or _is_broad_market_keyword(clean):
            continue
        if len(clean) >= 4:
            phrases.append(clean)
        for token in re.findall(r"[a-z0-9]+", clean.lower()):
            if len(token) >= 4 and token not in _TITLE_NOISE_TOKENS:
                tokens.append(token)
    frequent_title_tokens = [
        token
        for token, count in sorted(title_token_counts.items(), key=lambda item: (-item[1], item[0]))
        if count >= 2
    ]
    tokens.extend(frequent_title_tokens[:12])
    return {
        "phrases": _dedupe_strings(phrases)[:16],
        "tokens": _dedupe_strings(tokens)[:16],
    }


def _competitor_market_relevance(item: dict[str, Any], anchors: dict[str, list[str]]) -> dict[str, Any]:
    text = _normalize_market_text(
        " ".join(str(item.get(key) or "") for key in ("title", "brand", "note", "seller"))
    )
    phrases = [str(term).lower() for term in anchors.get("phrases", []) if term]
    tokens = [str(term).lower() for term in anchors.get("tokens", []) if term]
    matched_phrases = [term for term in phrases if term and term in text]
    matched_tokens = [term for term in tokens if term and re.search(rf"\b{re.escape(term)}\b", text)]
    if matched_phrases or len(matched_tokens) >= 2:
        status = "相关"
    elif matched_tokens:
        status = "需复核"
    else:
        status = "剔除"
    reason_parts = []
    if matched_phrases or matched_tokens:
        reason_parts.append(f"命中锚点：{', '.join((matched_phrases + matched_tokens)[:5])}")
    if status == "剔除":
        reason_parts.append("未命中目标小类锚点")
    reason = "；".join(reason_parts)
    return {
        "status": status,
        "reason": reason or "需要运营复核是否属于目标小类",
        "matched_terms": _dedupe_strings(matched_phrases + matched_tokens)[:8],
        "noise_terms": [],
    }


def _normalize_market_text(value: Any) -> str:
    text = re.sub(r"[_/\\-]+", " ", str(value or "").lower())
    text = re.sub(r"[^a-z0-9\u4e00-\u9fff\s]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _is_broad_market_keyword(value: str) -> bool:
    """判断关键词是否为品类标签而非具体产品词。

    用通用语言学规则：单名词或「修饰词 + 品类名词」结构视为过宽。
    例如 "accessories" 等品类标签词会被识别，
    但具体产品词不会。
    完全不依赖具体 Amazon 类目名称。
    """
    text = _normalize_market_text(value)
    if not text:
        return False
    words = text.split()
    if not words:
        return False
    # 1-2 个词且最后一个词是品类标签 → 过宽
    if len(words) <= 2 and words[-1] in _GENERIC_CATEGORY_NOUNS:
        return True
    # 单个品类标签词 → 过宽
    if len(words) == 1 and words[0] in _GENERIC_CATEGORY_NOUNS:
        return True
    return False
