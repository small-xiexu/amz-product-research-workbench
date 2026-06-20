"""VOC (Voice of Customer) analysis — review evidence extraction and summarization."""

from __future__ import annotations

from typing import Any

from packages.research_core.pipeline.market_text import _fmt_number, _positive_count


def _build_review_sources(voc_package: dict[str, Any] | None) -> dict[str, Any]:
    if not voc_package:
        return {}
    metadata = voc_package.get("metadata", {})
    summary = voc_package.get("summary", {})
    return {
        "package_id": metadata.get("package_id"),
        "source_type": metadata.get("source_type"),
        "source_files": metadata.get("source_files", []),
        "generated_at": metadata.get("generated_at"),
        "summary": summary,
        "collection_context": summary.get("collection_context", {}),
        "ai_report_reference": voc_package.get("ai_report_reference", {}),
    }

def _voc_summary(voc_package: dict[str, Any] | None) -> dict[str, Any]:
    if not voc_package:
        return {}
    for key in ("summary", "stats"):
        value = voc_package.get(key)
        if isinstance(value, dict):
            return value
    voc_analysis = voc_package.get("voc_analysis", {})
    if isinstance(voc_analysis, dict) and isinstance(voc_analysis.get("summary"), dict):
        return voc_analysis["summary"]
    return {}

def _voc_risk_basis(summary: dict[str, Any], first_pain: str) -> str:
    parts = [f"已接入 {_fmt_number(_positive_count(summary.get('review_count')))} 条评论"]
    asin_count = _positive_count(summary.get("asin_count"))
    low_rating_count = _positive_count(summary.get("low_rating_count"))
    media_review_count = _positive_count(summary.get("media_review_count"))
    if asin_count:
        parts.append(f"覆盖 {_fmt_number(asin_count)} 个 ASIN")
    if low_rating_count:
        parts.append(f"低分 {_fmt_number(low_rating_count)} 条")
    if media_review_count:
        parts.append(f"含图/视频 {_fmt_number(media_review_count)} 条")
    suffix = f"首要痛点：{first_pain}" if first_pain else "原始评论证据已入库，待进一步归纳首要痛点"
    return "，".join(parts) + f"；{suffix}"

def _build_voc_analysis(voc_package: dict[str, Any] | None) -> dict[str, Any]:
    if not voc_package:
        return {}
    summary = voc_package.get("summary", {})
    pain_points = _trim_findings(voc_package.get("pain_points", []), finding_limit=8, evidence_limit=5)
    highlights = _trim_findings(voc_package.get("highlights", []), finding_limit=6, evidence_limit=5)
    if not pain_points:
        pain_points = _derive_voc_findings_from_reviews(voc_package)
    return {
        "summary": summary,
        "source_scope": {
            "entry_site": summary.get("primary_entry_site", ""),
            "primary_review_region": summary.get("primary_review_region", ""),
            "entry_site_distribution": summary.get("entry_site_distribution", []),
            "review_region_distribution": summary.get("review_region_distribution", []),
            "note": summary.get("source_scope_note", ""),
        },
        "pain_points": pain_points,
        "highlights": highlights,
        "opportunity_hypotheses": voc_package.get("opportunity_hypotheses", [])[:8],
        "evidence_policy": "评论结论必须追溯到 review_id、ASIN、评分和评论链接；自动归纳只作初筛，需运营复核。",
    }

def _derive_voc_findings_from_reviews(voc_package: dict[str, Any], limit: int = 6) -> list[dict[str, Any]]:
    reviews = [item for item in voc_package.get("normalized_reviews", []) if isinstance(item, dict)]
    if not reviews:
        return []
    rated_reviews = [review for review in reviews if review_rating_sort_key(review) < 9]
    low_rating_reviews = [review for review in rated_reviews if review_rating_sort_key(review) <= 3]
    if not low_rating_reviews:
        return []
    average_rating = sum(review_rating_sort_key(review) for review in rated_reviews) / len(rated_reviews) if rated_reviews else 0.0
    low_rating_share = len(low_rating_reviews) / len(rated_reviews) if rated_reviews else 0.0
    evidence = []
    for review in sorted(low_rating_reviews, key=review_rating_sort_key)[:limit]:
        evidence.append(
            {
                "review_id": review.get("review_id"),
                "asin": review.get("asin"),
                "rating": review.get("rating"),
                "snippet": review_snippet(review),
                "url": review.get("url"),
                "site": review.get("site"),
                "review_region": review.get("review_region"),
                "review_date": review.get("review_date"),
            }
        )
    return [
        {
            "name": "低分评论概览",
            "review_count": len(low_rating_reviews),
            "severity": "高" if low_rating_share >= 0.25 else "中",
            "description": (
                f"已接入 {len(rated_reviews)} 条可评分评论，平均评分 {average_rating:.1f}，"
                f"低分评论占比 {low_rating_share:.1%}；脚本不自动分配品类主题，需由分析层阅读原文归纳痛点。"
            ),
            "evidence": evidence,
        }
    ]

def _trim_findings(findings: list[dict[str, Any]], finding_limit: int, evidence_limit: int) -> list[dict[str, Any]]:
    trimmed = []
    for finding in findings[:finding_limit]:
        trimmed.append(
            {
                **finding,
                "evidence": finding.get("evidence", [])[:evidence_limit],
            }
        )
    return trimmed

def _build_voc_opportunities(voc_package: dict[str, Any] | None, candidate_id: str | None) -> list[dict[str, Any]]:
    if not voc_package:
        return []
    opportunities = []
    for item in voc_package.get("opportunity_hypotheses", [])[:8]:
        opportunities.append(
            {
                "candidate_id": candidate_id,
                "source": "review_voc_package",
                "topic": item.get("name"),
                "hypothesis": item.get("hypothesis"),
                "evidence_review_ids": item.get("evidence_review_ids", []),
                "confidence": item.get("confidence", "待确认"),
            }
        )
    return opportunities

def _collect_voc_evidence(voc_package: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not voc_package:
        return []
    rows: list[dict[str, Any]] = []
    for finding_type, findings in (
        ("痛点", voc_package.get("pain_points", [])),
        ("亮点", voc_package.get("highlights", [])),
    ):
        for finding in findings:
            for evidence in finding.get("evidence", []):
                rows.append(
                    {
                        "finding_type": finding_type,
                        "finding_name": finding.get("name"),
                        "review_count": finding.get("review_count"),
                        "severity": finding.get("severity"),
                        **evidence,
                    }
                )
    return rows or _collect_raw_review_evidence(voc_package)

def _collect_raw_review_evidence(voc_package: dict[str, Any], limit: int = 80) -> list[dict[str, Any]]:
    reviews = [item for item in voc_package.get("normalized_reviews", []) if isinstance(item, dict)]
    reviews.sort(key=lambda item: (review_rating_sort_key(item), -(item.get("helpful_count") or 0)))
    rows: list[dict[str, Any]] = []
    for review in reviews:
        snippet = review_snippet(review)
        if not snippet:
            continue
        rows.append(
            {
                "finding_type": "原始评论",
                "finding_name": "待 Claude 归纳",
                "review_count": "",
                "severity": "待分析",
                "review_id": review.get("review_id"),
                "asin": review.get("asin"),
                "site": review.get("site"),
                "review_region": review.get("review_region"),
                "rating": review.get("rating"),
                "review_date": review.get("review_date"),
                "snippet": snippet,
                "url": review.get("url"),
            }
        )
        if len(rows) >= limit:
            break
    return rows

def review_rating_sort_key(review: dict[str, Any]) -> float:
    rating = review.get("rating")
    if isinstance(rating, (int, float)):
        return float(rating)
    try:
        return float(str(rating).strip())
    except (TypeError, ValueError):
        return 9.0

def review_snippet(review: dict[str, Any], limit: int = 180) -> str:
    text = str(review.get("review_text_zh") or review.get("review_text") or "").strip()
    text = " ".join(text.split())
    return text[:limit]

def _voc_summary_line(voc_package: dict[str, Any] | None) -> str:
    if not voc_package:
        return ""
    summary = voc_package.get("summary", {})
    scope = _voc_scope_text(summary)
    return (
        f"评论 VOC 已接入：共 {summary.get('review_count', 0)} 条评论、"
        f"{summary.get('asin_count', 0)} 个 ASIN，低分评论 {summary.get('low_rating_count', 0)} 条。"
        + (f"{scope}。" if scope else "")
    )

def _voc_dashboard_card(voc_package: dict[str, Any] | None) -> dict[str, Any] | None:
    if not voc_package:
        return None
    summary = voc_package.get("summary", {})
    return {
        "title": "评论 VOC",
        "status": "已接入",
        "review_count": summary.get("review_count", 0),
        "entry_site": summary.get("primary_entry_site", ""),
        "primary_review_region": summary.get("primary_review_region", ""),
        "low_rating_count": summary.get("low_rating_count", 0),
        "analysis_note": "痛点/亮点分析由 Claude 在对话中完成，请读取 normalized_reviews。",
    }

def _voc_scope_text(summary: dict[str, Any]) -> str:
    if not summary:
        return ""
    entry_site = summary.get("primary_entry_site")
    review_region = summary.get("primary_review_region")
    if entry_site and review_region:
        return f"采集入口为「{entry_site}」，评论地区以「{review_region}」为主，入口站点不等同于目标市场"
    if entry_site:
        return f"采集入口为「{entry_site}」，入口站点不等同于目标市场"
    if review_region:
        return f"评论地区以「{review_region}」为主"
    return ""

def _append_sentence(base: str, sentence: str) -> str:
    if not sentence:
        return base
    return f"{base} {sentence}"


# ── 重点竞品深拆卡 ─────────────────────────────────────────────────────────────
