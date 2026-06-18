#!/usr/bin/env python3
"""Normalize 1688 plugin CSV/JSON exports into research-workbench supply-chain files."""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any
from urllib.parse import urlsplit


TEXT_SCREENING_STATUSES = {"qualified", "partial"}
DEFAULT_SOURCE_SITE = "1688中国站"
DEFAULT_VISUAL_QUEUE_LIMIT = 50
DETAIL_PASS_SCORE = 6
DETAIL_REVIEWED_STATUSES = {"detail_structured_pass", "detail_structured_partial", "detail_structured_fail"}
VISUAL_REVIEWED_STATUSES = {"visual_confirmed", "visual_partial", "visual_rejected", "visual_reviewed"}


def _price_range(value: Any) -> tuple[float | None, float | None]:
    numbers = [float(match) for match in re.findall(r"\d+(?:\.\d+)?", str(value or "").replace(",", ""))]
    if not numbers:
        return None, None
    return min(numbers), max(numbers)


def _currency_price_range(*values: Any) -> tuple[float | None, float | None]:
    numbers: list[float] = []
    for value in values:
        items = value if isinstance(value, list) else [value]
        for item in items:
            text = str(item or "").replace(",", "")
            for match in re.finditer(r"[¥￥]\s*(\d+(?:\s*\.\s*\d+)?)", text):
                marker_index = match.start()
                if marker_index > 0 and text[marker_index - 1] in {"+", "＋"}:
                    continue
                normalized = re.sub(r"\s+", "", match.group(1))
                if "." in normalized:
                    integer, decimal = normalized.split(".", 1)
                    normalized = f"{integer}.{decimal[:2]}"
                elif len(normalized) > 3:
                    # 1688 SKU text sometimes joins price and stock, e.g. ¥31271
                    # means a ¥31 SKU followed by inventory 271. Do not treat it
                    # as a real procurement price.
                    continue
                try:
                    numbers.append(float(normalized))
                except ValueError:
                    continue
    if not numbers:
        return None, None
    return min(numbers), max(numbers)


def _merge_price_ranges(*ranges: tuple[float | None, float | None]) -> tuple[float | None, float | None]:
    lows = [low for low, _ in ranges if low is not None]
    highs = [high for _, high in ranges if high is not None]
    return (min(lows) if lows else None, max(highs) if highs else None)


def _conservative_price(low: float | None, high: float | None) -> float | None:
    if high is not None:
        return high
    return low


def _effective_price_range(item: dict[str, Any]) -> tuple[float | None, float | None]:
    detail_low = item.get("detail_price_cny_min")
    detail_high = item.get("detail_price_cny_max")
    if detail_low is not None or detail_high is not None:
        return detail_low, detail_high
    return item.get("price_cny_min"), item.get("price_cny_max")


def _is_1688_url(value: Any) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    parts = urlsplit(text if "://" in text else f"https://{text.lstrip('/')}")
    host = (parts.netloc or "").split("@")[-1].split(":")[0].lower()
    return host == "1688.com" or host.endswith(".1688.com")


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _read_evidence(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    evidence = data.get("evidence")
    if not isinstance(evidence, list):
        raise ValueError(f"1688 evidence JSON missing evidence list: {path}")
    return data


def _clean_json_value(value: Any) -> Any:
    if isinstance(value, str):
        return "".join(ch for ch in value if not 0xD800 <= ord(ch) <= 0xDFFF)
    if isinstance(value, list):
        return [_clean_json_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _clean_json_value(item) for key, item in value.items()}
    return value


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(_clean_json_value(payload), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _csv_url(row: dict[str, Any]) -> str:
    return str(row.get("商品URL") or row.get("商品 URL") or row.get("url") or row.get("URL") or "").strip()


def _evidence_url(item: dict[str, Any]) -> str:
    return str(item.get("sourceUrl") or item.get("source_url") or item.get("url") or "").strip()


def _looks_like_bad_candidate_title(value: Any) -> bool:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if not text or len(text) < 4:
        return True
    patterns = [
        r"^\d+(?:\.\d+)?\s*[万千kK]?\+?\s*(?:件|个|条|套|箱|笔|单)?$",
        r"^\d+(?:\.\d+)?\s*(?:万|千|k|K)\+?\s*(?:件|个|条|套|箱|笔|单)?$",
        r"^(?:已售|月销|成交|近\d+天|回头率|月浏览|全网)\s*[\d.万千kK+%]+\s*(?:件|个|条|套|箱|笔|单)?$",
        r"^(?:7天无理由|七天无理由|退货包运费|极速退款|假一赔\d*|运费险|包邮|首单优惠|新人首单优惠)$",
        r"^(?:元宝可抵|可抵|满\d+减\d+|每\d+减\d+|新人价|首单|低价|限时价|广告)\s*[\d.%折元]*$",
        r"^[≥>]\s*\d+",
    ]
    if any(re.search(pattern, text, re.I) for pattern in patterns):
        return True
    return bool(re.search(r"(验厂报告|找相似|进店|联系|旺旺|咨询|采购咨询|纠纷解决|物流时效|退换体验|品质体验|适用送礼|适用节日)", text))


def _is_probable_product_image_url(value: Any) -> bool:
    url = str(value or "").strip()
    if not url:
        return False
    lowered = url.lower()
    if "gg_dtc" in lowered:
        return False
    if lowered.endswith(".svg") or ".svg" in lowered:
        return False
    tps_match = re.search(r"-tps-(\d+)-(\d+)", lowered)
    if tps_match:
        width, height = (int(tps_match.group(1)), int(tps_match.group(2)))
        if max(width, height) < 200:
            return False
    if "cbu01.alicdn.com/img/ibank/" in lowered:
        return True
    if "/img/ibank/" in lowered:
        return True
    if "img.alicdn.com/imgextra/" in lowered:
        return False
    if any(extension in lowered for extension in (".jpg", ".jpeg", ".png", ".webp")):
        return True
    return False


def _normalize_product_image_url(value: Any) -> str:
    url = str(value or "").strip()
    for suffix in ("_.jpg", "_.png", "_.webp"):
        if url.endswith(suffix):
            return url[: -len(suffix)]
    return url


def _product_image_urls(item: dict[str, Any], *, limit: int = 8) -> list[str]:
    urls: list[str] = []
    for url in (item.get("productImageUrls") or []) + (item.get("imageUrls") or []):
        text = _normalize_product_image_url(url)
        if text and text not in urls and _is_probable_product_image_url(text):
            urls.append(text)
        if len(urls) >= limit:
            break
    return urls


def _compact_dict(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return {str(key): item for key, item in value.items() if item not in (None, "", [], {})}


def _detail_evidence_score(candidate: dict[str, Any]) -> tuple[int, list[str]]:
    score = 0
    flags: list[str] = []
    if candidate.get("detail_price_text"):
        score += 1
    else:
        flags.append("缺少详情价")
    if candidate.get("moq_text"):
        score += 1
    else:
        flags.append("缺少起订量")
    if candidate.get("visual_evidence_image_urls"):
        score += 2
    else:
        flags.append("缺少可复核商品图")
    if candidate.get("sku_texts") or candidate.get("sku_options") or candidate.get("detail_attributes"):
        score += 2
    else:
        flags.append("缺少规格/属性")
    if candidate.get("supplier_text") or candidate.get("supplier_tags") or candidate.get("store_metrics"):
        score += 1
    else:
        flags.append("缺少供应商信号")
    if len(str(candidate.get("detail_text_excerpt") or "")) >= 150:
        score += 1
    else:
        flags.append("详情文本较短")
    return score, flags


def _detail_review(candidate: dict[str, Any]) -> tuple[str, list[str]]:
    flags = list(candidate.get("detail_evidence_flags") or [])
    score = int(candidate.get("detail_evidence_score") or 0)
    price_min = candidate.get("detail_price_cny_min")
    source_price_min = candidate.get("price_cny_min")
    moq_value = _first_int(candidate.get("moq_text"))
    image_count = len(candidate.get("visual_evidence_image_urls") or [])

    if not candidate.get("valid_1688_rmb"):
        flags.append("非1688中国站RMB有效报价")
    if price_min is None:
        flags.append("详情价格无法解析")
    if source_price_min is not None and price_min is not None and abs(float(source_price_min) - float(price_min)) > 3:
        flags.append("搜索价与详情价差异较大")
    if moq_value is None:
        flags.append("起订量无法解析")
    elif moq_value > 50:
        flags.append(f"起订量超过验证上限：{moq_value}")
    if image_count < 2:
        flags.append("可复核商品图不足")

    if score >= DETAIL_PASS_SCORE and not any(flag in flags for flag in ("非1688中国站RMB有效报价", "详情价格无法解析", "起订量无法解析", "可复核商品图不足")):
        return "detail_structured_pass", flags
    if score >= 4 and candidate.get("visual_evidence_image_urls") and price_min is not None:
        return "detail_structured_partial", flags
    return "detail_structured_fail", flags


def _first_int(value: Any) -> int | None:
    match = re.search(r"\d+", str(value or "").replace(",", ""))
    return int(match.group(0)) if match else None


def _text_metric_hits(value: Any) -> tuple[int | None, int | None]:
    match = re.search(r"命中\s*(\d+)\s*/\s*(\d+)", str(value or ""))
    if not match:
        return None, None
    return int(match.group(1)), int(match.group(2))


def _text_blob(item: dict[str, Any]) -> str:
    parts = [
        item.get("title"),
        item.get("keyword"),
        item.get("reason"),
        item.get("category_signal"),
        item.get("tag_signal"),
        item.get("detail_summary"),
        item.get("detail_text_excerpt"),
        item.get("customization_text"),
        item.get("stock_text"),
        " ".join(map(str, item.get("supplier_tags") or [])),
    ]
    return " ".join(str(part or "") for part in parts)


def _contains_any(text: str, words: tuple[str, ...]) -> bool:
    return any(word in text for word in words)


def _list_texts(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    return []


def _split_terms(value: Any) -> list[str]:
    return [
        item.strip()
        for item in re.split(r"[\n,，;；、\t]+", str(value or ""))
        if item.strip()
    ]


def _auto_review_profile(evidence_data: dict[str, Any], candidates: list[dict[str, Any]]) -> dict[str, Any]:
    config = evidence_data.get("config") if isinstance(evidence_data.get("config"), dict) else {}
    keywords = _split_terms(config.get("keywords"))
    category_terms = _split_terms(config.get("categoryTerms"))
    exclude_terms = _split_terms(config.get("excludeTerms"))
    tag_terms = _split_terms(config.get("tags"))
    if not any((keywords, category_terms, exclude_terms, tag_terms)):
        keyword_counts: Counter[str] = Counter()
        for item in candidates:
            for term in _split_terms(item.get("keyword")):
                keyword_counts[term] += 1
        keywords = [term for term, _ in keyword_counts.most_common(8)]
    return {
        "generated_by": "auto_from_plugin_config",
        "feature_groups": [
            {"name": "搜索词", "terms": keywords, "bonus": 6, "missing_penalty": 0},
            {"name": "类目相关词", "terms": category_terms, "bonus": 10, "missing_penalty": -4 if category_terms else 0},
            {"name": "关注标签", "terms": tag_terms, "bonus": 5, "missing_penalty": 0},
        ],
        "negative_terms": [
            {"name": "排除词", "terms": exclude_terms, "penalty": -30}
        ] if exclude_terms else [],
        "strong_positive_terms": [term for term in ["现货", "一件代发", "定制", "跨境", "源头工厂", "超级工厂"] if term in " ".join(tag_terms + category_terms + keywords) or not tag_terms],
        "strong_positive_bonus": 5,
        "soft_negative_terms": [],
        "profile_note": "自动从插件采集条件生成。用于排序复核队列，不代表最终视觉判断。",
    }


def _profile_score(item: dict[str, Any], profile: dict[str, Any] | None) -> tuple[int, list[str]]:
    if not profile:
        return 0, []
    text = _text_blob(item)
    score = 0
    reasons: list[str] = []

    for group in profile.get("feature_groups") or []:
        if not isinstance(group, dict):
            continue
        name = str(group.get("name") or "画像特征")
        terms = _list_texts(group.get("terms"))
        matched = [term for term in terms if term and term in text]
        if matched:
            bonus = int(group.get("bonus", 0) or 0)
            score += bonus
            reasons.append(f"{name}命中：{'/'.join(matched[:3])}")
        elif group.get("missing_penalty") is not None:
            penalty = int(group.get("missing_penalty") or 0)
            score += penalty
            if penalty:
                reasons.append(f"{name}未命中")

    for rule in profile.get("negative_terms") or []:
        if isinstance(rule, dict):
            terms = _list_texts(rule.get("terms"))
            penalty = int(rule.get("penalty", -20) or -20)
            label = str(rule.get("name") or "负向词")
        else:
            terms = [str(rule)]
            penalty = -20
            label = "负向词"
        matched = [term for term in terms if term and term in text]
        if matched:
            score += penalty
            reasons.append(f"{label}命中：{'/'.join(matched[:3])}")

    for term in _list_texts(profile.get("strong_positive_terms")):
        if term in text:
            score += int(profile.get("strong_positive_bonus", 6) or 6)
            reasons.append(f"强正向词：{term}")

    for term in _list_texts(profile.get("soft_negative_terms")):
        if term in text:
            score += int(profile.get("soft_negative_penalty", -8) or -8)
            reasons.append(f"弱负向词：{term}")

    return score, reasons


def _review_priority(item: dict[str, Any], profile: dict[str, Any] | None = None) -> tuple[int, list[str]]:
    score = 0
    reasons: list[str] = []

    status = item.get("text_screening_status") or item.get("screening_status")
    if status == "qualified":
        score += 18
        reasons.append("文本初筛为 qualified")
    elif status == "partial":
        score += 8
        reasons.append("文本初筛为 partial")

    price_signal = item.get("price_signal")
    if price_signal == "符合目标价":
        score += 22
        reasons.append("价格在目标采购价内")
    elif price_signal == "低于目标价":
        score += 8
        reasons.append("价格低于目标采购价，需核实是否低质/配件")
    elif price_signal == "高于目标价":
        score -= 8
        reasons.append("价格高于目标采购价")
    elif not price_signal:
        score -= 4
        reasons.append("缺少价格判断")

    if item.get("valid_1688_rmb"):
        score += 8
        reasons.append("1688 中国站 RMB 报价有效")

    category_hits, category_total = _text_metric_hits(item.get("category_signal"))
    if category_hits is not None and category_total:
        category_score = round(12 * category_hits / category_total)
        score += category_score
        reasons.append(f"类目相关词命中 {category_hits}/{category_total}")

    tag_hits, tag_total = _text_metric_hits(item.get("tag_signal"))
    if tag_hits is not None and tag_total:
        tag_score = round(8 * tag_hits / tag_total)
        score += tag_score
        reasons.append(f"关注标签命中 {tag_hits}/{tag_total}")

    exclude_signal = str(item.get("exclude_signal") or "")
    if "未命中排除词" in exclude_signal:
        score += 8
        reasons.append("未命中排除词")
    elif "命中" in exclude_signal:
        score -= 25
        reasons.append("命中排除词，需谨慎")

    image_count = len(item.get("visual_evidence_image_urls") or [])
    if image_count:
        score += min(12, image_count * 2)
        reasons.append(f"可复核商品图 {image_count} 张")
    else:
        score -= 20
        reasons.append("缺少可复核商品图")

    detail_length = len(str(item.get("detail_summary") or item.get("detail_text_excerpt") or ""))
    if detail_length >= 500:
        score += 8
        reasons.append("详情文本较完整")
    elif detail_length >= 150:
        score += 4
        reasons.append("详情文本可参考")

    if item.get("stock_text"):
        score += 5
        reasons.append("有库存/现货文本")
    if item.get("customization_text"):
        score += 6
        reasons.append("有定制/改款文本")
    if item.get("supplier_tags"):
        score += 4
        reasons.append("有供应商标签")

    detail_score = int(item.get("detail_evidence_score") or 0)
    if detail_score >= 6:
        score += 10
        reasons.append("详情证据完整")
    elif detail_score >= 4:
        score += 5
        reasons.append("详情证据可用")
    elif detail_score:
        score -= 4
        reasons.append("详情证据偏弱")
    else:
        score -= 12
        reasons.append("缺少详情证据")

    blob = _text_blob(item)
    if _contains_any(blob, ("一件代发", "现货", "跨境", "源头工厂", "工厂直营", "定制", "LOGO")):
        score += 8
        reasons.append("含跨境/现货/定制/源头信号")

    moq = _first_int(item.get("moq_text"))
    if moq is not None:
        if moq <= 50:
            score += 6
            reasons.append(f"起订量较友好：{moq}")
        elif moq <= 500:
            score += 2
            reasons.append(f"起订量可接受：{moq}")
        else:
            score -= 4
            reasons.append(f"起订量偏高：{moq}")

    profile_score, profile_reasons = _profile_score(item, profile)
    score += profile_score
    reasons.extend(profile_reasons)

    return score, reasons[:10]


def _merge_rows(csv_rows: list[dict[str, str]], evidence_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    evidence_by_url = {_evidence_url(item): item for item in evidence_items if _evidence_url(item)}
    merged: list[dict[str, Any]] = []
    for row in csv_rows:
        url = _csv_url(row)
        evidence = evidence_by_url.get(url, {})
        status = str(row.get("筛选状态") or evidence.get("sourceStatus") or "").strip()
        if status not in TEXT_SCREENING_STATUSES:
            continue
        source_price = row.get("价格") or evidence.get("sourcePrice") or evidence.get("priceText")
        detail_price = evidence.get("priceText") or source_price
        price_min, price_max = _price_range(source_price)
        detail_header_min, detail_header_max = _price_range(detail_price)
        sku_price_min, sku_price_max = _currency_price_range(
            evidence.get("skuTexts"),
            evidence.get("skuOptions"),
            evidence.get("stockText"),
        )
        detail_price_min, detail_price_max = _merge_price_ranges(
            (detail_header_min, detail_header_max),
            (sku_price_min, sku_price_max),
        )
        conservative_price = _conservative_price(detail_price_min, detail_price_max) or _conservative_price(price_min, price_max)
        candidate = {
            "keyword": row.get("命中搜索词") or evidence.get("sourceKeyword") or "",
            "screening_status": status,
            "text_screening_status": status,
            "text_screening_label": "文本初筛候选",
            "visual_review_status": "pending_visual_detail_review",
            "detail_review_status": "pending_detail_review",
            "final_supply_status": "pending_visual_review",
            "title": row.get("标题") or evidence.get("title") or evidence.get("sourceTitle") or "",
            "price_text": source_price or "",
            "price_cny_min": price_min,
            "price_cny_max": price_max,
            "conservative_price_cny": conservative_price,
            "conservative_price_basis": "详情页页头价和SKU/库存文本中的¥价格区间上限；无详情价时使用搜索价上限",
            "detail_price_text": detail_price or "",
            "detail_price_cny_min": detail_price_min,
            "detail_price_cny_max": detail_price_max,
            "price_signal": row.get("价格判断") or "",
            "category_signal": row.get("类目命中") or "",
            "exclude_signal": row.get("排除词命中") or "",
            "tag_signal": row.get("标签命中") or "",
            "reason": row.get("判断原因") or evidence.get("sourceReason") or "",
            "url": url or evidence.get("url") or "",
            "quote_currency": "RMB",
            "source_site": DEFAULT_SOURCE_SITE,
            "source_tool": "1688_supply_chain_harvester",
            "offer_id": evidence.get("offerId") or "",
            "main_image_url": evidence.get("mainImageUrl") or "",
            "image_urls": evidence.get("imageUrls") or [],
            "product_image_urls": evidence.get("productImageUrls") or [],
            "image_count": evidence.get("imageCount") or len(evidence.get("imageUrls") or []),
            "product_image_count": evidence.get("productImageCount") or len(evidence.get("productImageUrls") or []),
            "visual_evidence_image_urls": _product_image_urls(evidence),
            "moq_text": evidence.get("moqText") or "",
            "sku_texts": evidence.get("skuTexts") or [],
            "sku_options": evidence.get("skuOptions") or [],
            "detail_attributes": _compact_dict(evidence.get("detailAttributes")),
            "specification_count": evidence.get("specificationCount") or 0,
            "supplier_text": evidence.get("supplierText") or "",
            "supplier_tags": evidence.get("supplierTags") or [],
            "store_metrics": _compact_dict(evidence.get("storeMetrics")),
            "shipping_text": evidence.get("shippingText") or "",
            "sold_text": evidence.get("soldText") or "",
            "return_rate_text": evidence.get("returnRateText") or "",
            "stock_text": evidence.get("stockText") or "",
            "customization_text": evidence.get("customizationText") or "",
            "detail_summary": evidence.get("summary") or "",
            "detail_text_excerpt": str(evidence.get("detailText") or "")[:1200],
            "evidence_quality": _compact_dict(evidence.get("evidenceQuality")),
        }
        if _looks_like_bad_candidate_title(candidate["title"]):
            continue
        candidate["valid_1688_rmb"] = _is_1688_url(candidate["url"]) and (
            candidate["price_cny_min"] is not None or candidate["detail_price_cny_min"] is not None
        )
        candidate["visual_evidence_image_count"] = len(candidate["visual_evidence_image_urls"])
        detail_score, detail_flags = _detail_evidence_score(candidate)
        candidate["detail_evidence_score"] = detail_score
        candidate["detail_evidence_flags"] = detail_flags
        detail_status, detail_review_flags = _detail_review(candidate)
        candidate["detail_review_status"] = detail_status
        candidate["detail_review_flags"] = detail_review_flags
        candidate["detail_review_passed"] = detail_status == "detail_structured_pass"
        candidate["stage1_text_screening_passed"] = candidate["text_screening_status"] in TEXT_SCREENING_STATUSES
        candidate["stage2_detail_screening_passed"] = detail_status == "detail_structured_pass"
        candidate["stage3_visual_detail_review_status"] = candidate["visual_review_status"]
        candidate["stage3_visual_detail_review_required"] = True
        candidate["needs_visual_review"] = True
        merged.append(candidate)
    return merged


def _percent(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def _build_signal(
    candidates: list[dict[str, Any]],
    *,
    raw_candidate_count: int,
    evidence_count: int,
    source_files: dict[str, str],
    exchange_rate: float | None = None,
) -> dict[str, Any]:
    valid = [item for item in candidates if item.get("valid_1688_rmb")]
    target_price_records = [item for item in valid if item.get("price_signal") == "符合目标价"] or valid
    target_ranges = [_effective_price_range(item) for item in target_price_records]
    all_ranges = [_effective_price_range(item) for item in valid]
    lows = [low for low, _ in target_ranges if low is not None]
    highs = [high for _, high in target_ranges if high is not None]
    conservative_prices = [
        item["conservative_price_cny"]
        for item in target_price_records
        if item.get("conservative_price_cny") is not None
    ]
    all_lows = [low for low, _ in all_ranges if low is not None]
    all_highs = [high for _, high in all_ranges if high is not None]
    all_conservative_prices = [
        item["conservative_price_cny"]
        for item in valid
        if item.get("conservative_price_cny") is not None
    ]
    detail_lows = [item["detail_price_cny_min"] for item in valid if item.get("detail_price_cny_min") is not None]
    statuses = Counter(item.get("screening_status") or "" for item in candidates)
    detail_statuses = Counter(item.get("detail_review_status") or "" for item in candidates)
    visual_statuses = Counter(item.get("visual_review_status") or "" for item in candidates)
    price_signals = Counter(item.get("price_signal") or "" for item in candidates)
    keywords = Counter(item.get("keyword") or "" for item in candidates)
    supplier_nonempty = sum(1 for item in candidates if item.get("supplier_text"))
    tags_nonempty = sum(1 for item in candidates if item.get("supplier_tags"))
    customization_count = sum(1 for item in candidates if item.get("customization_text"))
    stock_count = sum(1 for item in candidates if item.get("stock_text"))
    image_nonempty = sum(1 for item in candidates if item.get("visual_evidence_image_urls"))
    detail_attribute_nonempty = sum(1 for item in candidates if item.get("detail_attributes"))
    sku_nonempty = sum(1 for item in candidates if item.get("sku_texts") or item.get("sku_options"))
    store_metrics_nonempty = sum(1 for item in candidates if item.get("store_metrics"))
    detail_usable_count = sum(1 for item in candidates if int(item.get("detail_evidence_score") or 0) >= 4)
    detail_pass_count = sum(1 for item in candidates if item.get("detail_review_status") == "detail_structured_pass")
    detail_partial_count = sum(1 for item in candidates if item.get("detail_review_status") == "detail_structured_partial")
    detail_fail_count = sum(1 for item in candidates if item.get("detail_review_status") == "detail_structured_fail")
    visual_reviewed_count = sum(1 for item in candidates if item.get("visual_review_status") in VISUAL_REVIEWED_STATUSES)
    visual_confirmed_count = sum(1 for item in candidates if item.get("visual_review_status") == "visual_confirmed")
    visual_pending_count = max(0, len(candidates) - visual_reviewed_count)
    one_piece_count = sum(1 for item in candidates if "一件代发" in " ".join(map(str, [item.get("reason"), item.get("tag_signal"), item.get("detail_summary"), item.get("detail_text_excerpt")])))
    atomic_keywords: Counter[str] = Counter()
    for keyword, count in keywords.items():
        for part in [text.strip() for text in str(keyword).split("；") if text.strip()]:
            atomic_keywords[part] += count
    avg_cny = round(sum(lows) / len(lows), 2) if lows else None
    conservative_cny = round(max(conservative_prices), 2) if conservative_prices else None
    conservative_usd = (
        round(conservative_cny / exchange_rate, 2)
        if conservative_cny is not None and exchange_rate
        else None
    )
    signal = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_tool": "1688_supply_chain_harvester",
        "source_site": DEFAULT_SOURCE_SITE,
        "source_url": "https://www.1688.com/",
        "quote_currency": "RMB",
        "search_name": "；".join([keyword for keyword, _ in atomic_keywords.most_common(6) if keyword]),
        "raw_supplier_count": raw_candidate_count,
        "supplier_count": len(valid),
        "text_screened_candidate_count": len(candidates),
        "detail_structured_review_count": len(candidates),
        "detail_structured_pass_count": detail_pass_count,
        "detail_structured_partial_count": detail_partial_count,
        "detail_structured_fail_count": detail_fail_count,
        "visual_detail_review_required": True,
        "visual_reviewed_count": visual_reviewed_count,
        "visual_confirmed_count": visual_confirmed_count,
        "visual_pending_count": visual_pending_count,
        "relevant_supplier_count": visual_confirmed_count,
        "target_price_sample_count": len(target_price_records),
        "rejected_sample_count": raw_candidate_count - len(candidates),
        "evidence_count": evidence_count,
        "purchase_price_cny_min": round(min(lows), 2) if lows else None,
        "purchase_price_cny_max": round(max(highs), 2) if highs else None,
        "conservative_purchase_price_cny": conservative_cny,
        "conservative_purchase_price_usd": conservative_usd,
        "conservative_purchase_price_basis": "1688区间报价按上限做保守估算；利润复核默认使用该字段，不使用最低SKU价。",
        "purchase_price_cny_avg": avg_cny,
        "conservative_purchase_price_cny_median": round(median(conservative_prices), 2) if conservative_prices else None,
        "purchase_price_cny_median": round(median(lows), 2) if lows else None,
        "all_candidate_price_cny_min": round(min(all_lows), 2) if all_lows else None,
        "all_candidate_price_cny_max": round(max(all_highs), 2) if all_highs else None,
        "all_candidate_conservative_price_cny": round(max(all_conservative_prices), 2) if all_conservative_prices else None,
        "detail_price_cny_median": round(median(detail_lows), 2) if detail_lows else None,
        "purchase_price_usd_avg": round(avg_cny / exchange_rate, 2) if avg_cny is not None and exchange_rate else None,
        "exchange_rate": exchange_rate,
        "status_breakdown": dict(statuses),
        "text_screening_status_breakdown": dict(statuses),
        "detail_review_status_breakdown": dict(detail_statuses),
        "visual_review_status_breakdown": dict(visual_statuses),
        "price_signal_breakdown": dict(price_signals),
        "keyword_breakdown": dict(keywords),
        "field_coverage": {
            "supplier_text": _percent(supplier_nonempty, len(candidates)),
            "supplier_tags": _percent(tags_nonempty, len(candidates)),
            "customization_text": _percent(customization_count, len(candidates)),
            "stock_text": _percent(stock_count, len(candidates)),
            "visual_evidence_image_urls": _percent(image_nonempty, len(candidates)),
            "detail_attributes": _percent(detail_attribute_nonempty, len(candidates)),
            "sku_options_or_texts": _percent(sku_nonempty, len(candidates)),
            "store_metrics": _percent(store_metrics_nonempty, len(candidates)),
            "usable_detail_evidence": _percent(detail_usable_count, len(candidates)),
        },
        "capability_signals": {
            "customization_count": customization_count,
            "stock_count": stock_count,
            "one_piece_dropship_count": one_piece_count,
        },
        "screening_pipeline": {
            "stage1_text_screening": "CSV搜索结果初筛：标题、关键词、价格、排除词、类目/标签命中。",
            "stage2_detail_structured_review": "详情JSON结构化复核：详情价、起订量、SKU/规格、店铺信号、详情文本和可复核图片覆盖。",
            "stage3_visual_detail_review": "图片+详情内容复核：确认商品形态是否符合本轮目标画像，并按本轮排除词剔除混池商品。",
        },
        "confidence": "中低：CSV初筛和详情结构化复核已完成；图片/详情形态尚未逐品复核，不能视为最终通过供应商。",
        "note": "当前只完成1688中国站CSV初筛与详情JSON结构化复核，报价不含头程、关税、质检、包装和损耗；最终供应链结论必须等图片/详情形态复核和供应商确认后才能给出。",
        "source_files": source_files,
        "sample_products": [
            {
                "title": item.get("title"),
                "price_cny_min": item.get("price_cny_min"),
                "price_cny_max": item.get("price_cny_max"),
                "detail_price_text": item.get("detail_price_text"),
                "detail_price_cny_min": item.get("detail_price_cny_min"),
                "detail_price_cny_max": item.get("detail_price_cny_max"),
                "conservative_price_cny": item.get("conservative_price_cny"),
                "quote_currency": "RMB",
                "supplier": item.get("supplier_text"),
                "url": item.get("url"),
            }
            for item in sorted(valid, key=lambda row: (row.get("screening_status") != "qualified", row.get("price_cny_min") or 999999))[:10]
        ],
    }
    return {key: value for key, value in signal.items() if value not in (None, "", [])}


def _build_visual_review_queue(
    candidates: list[dict[str, Any]],
    *,
    source_files: dict[str, str],
    queue_limit: int = DEFAULT_VISUAL_QUEUE_LIMIT,
    review_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    scored: list[tuple[int, int, dict[str, Any], list[str]]] = []
    for index, candidate in enumerate(candidates):
        score, reasons = _review_priority(candidate, review_profile)
        scored.append((score, index, candidate, reasons))
    scored.sort(key=lambda item: (-item[0], item[1]))
    queue: list[dict[str, Any]] = []
    checklist = _operator_review_checklist(review_profile)
    for rank, (score, _index, candidate, reasons) in enumerate(scored[:queue_limit], start=1):
        queue.append(
            {
                "review_rank": rank,
                "review_priority_score": score,
                "review_priority_reasons": reasons,
                "text_screening_status": candidate.get("text_screening_status"),
                "detail_review_status": candidate.get("detail_review_status"),
                "detail_review_flags": candidate.get("detail_review_flags"),
                "detail_review_passed": candidate.get("detail_review_passed"),
                "visual_review_status": candidate.get("visual_review_status"),
                "final_supply_status": "pending_visual_review",
                "stage1_text_screening_passed": candidate.get("stage1_text_screening_passed"),
                "stage2_detail_screening_passed": candidate.get("stage2_detail_screening_passed"),
                "stage3_visual_detail_review_status": candidate.get("stage3_visual_detail_review_status"),
                "stage3_visual_detail_review_required": True,
                "keyword": candidate.get("keyword"),
                "title": candidate.get("title"),
                "price_text": candidate.get("price_text"),
                "price_cny_min": candidate.get("price_cny_min"),
                "price_cny_max": candidate.get("price_cny_max"),
                "detail_price_text": candidate.get("detail_price_text"),
                "detail_price_cny_min": candidate.get("detail_price_cny_min"),
                "detail_price_cny_max": candidate.get("detail_price_cny_max"),
                "conservative_price_cny": candidate.get("conservative_price_cny"),
                "conservative_price_basis": candidate.get("conservative_price_basis"),
                "price_signal": candidate.get("price_signal"),
                "category_signal": candidate.get("category_signal"),
                "exclude_signal": candidate.get("exclude_signal"),
                "tag_signal": candidate.get("tag_signal"),
                "reason": candidate.get("reason"),
                "url": candidate.get("url"),
                "quote_currency": candidate.get("quote_currency"),
                "source_site": candidate.get("source_site"),
                "offer_id": candidate.get("offer_id"),
                "visual_evidence_image_urls": candidate.get("visual_evidence_image_urls") or [],
                "visual_evidence_image_count": candidate.get("visual_evidence_image_count"),
                "detail_evidence_score": candidate.get("detail_evidence_score"),
                "detail_evidence_flags": candidate.get("detail_evidence_flags"),
                "evidence_quality": candidate.get("evidence_quality"),
                "moq_text": candidate.get("moq_text"),
                "supplier_text": candidate.get("supplier_text"),
                "supplier_tags": candidate.get("supplier_tags"),
                "store_metrics": candidate.get("store_metrics"),
                "shipping_text": candidate.get("shipping_text"),
                "sold_text": candidate.get("sold_text"),
                "stock_text": candidate.get("stock_text"),
                "customization_text": candidate.get("customization_text"),
                "sku_texts": candidate.get("sku_texts"),
                "sku_options": candidate.get("sku_options"),
                "detail_attributes": candidate.get("detail_attributes"),
                "detail_summary": candidate.get("detail_summary"),
                "detail_text_excerpt": candidate.get("detail_text_excerpt"),
                "operator_review_checklist": checklist,
            }
        )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_tool": "1688_supply_chain_harvester",
        "source_site": DEFAULT_SOURCE_SITE,
        "queue_limit": queue_limit,
        "review_queue_count": len(queue),
        "candidate_count": len(candidates),
        "review_required_before_final_supply_pass": True,
        "review_profile": review_profile or {},
        "selection_policy": "按文本初筛状态、目标采购价、排除词、类目/标签命中、可复核商品图、详情完整度、现货/定制/起订量和可选目标画像排序；不代表视觉已通过。",
        "source_files": source_files,
        "visual_review_queue": queue,
    }


def _operator_review_checklist(review_profile: dict[str, Any] | None) -> list[str]:
    target_terms: list[str] = []
    excluded_terms: list[str] = []
    for group in (review_profile or {}).get("feature_groups") or []:
        if not isinstance(group, dict):
            continue
        if str(group.get("name") or "") in {"搜索词", "类目相关词", "关注标签"}:
            target_terms.extend(_list_texts(group.get("terms")))
    for rule in (review_profile or {}).get("negative_terms") or []:
        if isinstance(rule, dict):
            excluded_terms.extend(_list_texts(rule.get("terms")))
        else:
            excluded_terms.append(str(rule))
    target_hint = " / ".join(_dedupe_preserve(target_terms)[:5]) or "本轮目标商品"
    checklist = [
        f"主图/详情图是否符合目标画像：{target_hint}",
        "标题、主图和详情描述是否指向同一个商品形态",
        "价格是否对应可销售整件/整套商品，而不是单配件、低配规格或引流价",
        "SKU/规格里最高配置、最低配置和目标配置是否能分清",
        "是否有可接受的现货、定制、起订量、包装重量和供应商信号",
    ]
    excluded = _dedupe_preserve(excluded_terms)[:6]
    if excluded:
        checklist.insert(1, f"是否命中本轮排除词：{' / '.join(excluded)}")
    else:
        checklist.insert(1, "是否属于目标外观/用途不一致的混池商品，并记录具体差异")
    return checklist


def _dedupe_preserve(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        text = str(item).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def build_supply_chain_outputs(
    candidates_csv: Path,
    evidence_json: Path,
    *,
    exchange_rate: float | None = None,
    visual_queue_limit: int = DEFAULT_VISUAL_QUEUE_LIMIT,
    review_profile: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    csv_rows = _read_csv(candidates_csv)
    evidence_data = _read_evidence(evidence_json)
    evidence_items = evidence_data.get("evidence", [])
    candidates = _merge_rows(csv_rows, evidence_items)
    active_review_profile = review_profile or _auto_review_profile(evidence_data, candidates)
    source_files = {
        "candidates_csv": str(candidates_csv),
        "evidence_json": str(evidence_json),
    }
    signal = _build_signal(
        candidates,
        raw_candidate_count=len(csv_rows),
        evidence_count=len(evidence_items),
        source_files=source_files,
        exchange_rate=exchange_rate,
    )
    visual_queue = _build_visual_review_queue(
        candidates,
        source_files=source_files,
        queue_limit=visual_queue_limit,
        review_profile=active_review_profile,
    )
    signal["visual_review_queue_count"] = visual_queue["review_queue_count"]
    signal["visual_review_required"] = True
    candidate_payload = {
        "generated_at": signal.get("generated_at"),
        "source_tool": "1688_supply_chain_harvester",
        "source_site": DEFAULT_SOURCE_SITE,
        "candidate_count": len(candidates),
        "source_files": source_files,
        "candidates": candidates,
    }
    return signal, candidate_payload, visual_queue


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build normalized supply-chain files from 1688 plugin exports.")
    parser.add_argument("candidates_csv")
    parser.add_argument("evidence_json")
    parser.add_argument("output_dir")
    parser.add_argument("--exchange-rate", type=float, default=None, help="Optional CNY per USD exchange rate.")
    parser.add_argument("--visual-queue-limit", type=int, default=DEFAULT_VISUAL_QUEUE_LIMIT, help="Top N candidates for visual review.")
    parser.add_argument("--review-profile", default="", help="Optional JSON profile for category-specific visual review priority.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    candidates_csv = Path(args.candidates_csv).expanduser().resolve()
    evidence_json = Path(args.evidence_json).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    review_profile = None
    if args.review_profile:
        profile_path = Path(args.review_profile).expanduser().resolve()
        review_profile = json.loads(profile_path.read_text(encoding="utf-8"))
    signal, candidates, visual_queue = build_supply_chain_outputs(
        candidates_csv,
        evidence_json,
        exchange_rate=args.exchange_rate,
        visual_queue_limit=args.visual_queue_limit,
        review_profile=review_profile,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / "supply_chain_signal.json", signal)
    _write_json(output_dir / "supply_chain_candidates.json", candidates)
    _write_json(output_dir / "supply_chain_visual_review_queue.json", visual_queue)
    print(f"supply_chain_signal.json: {output_dir / 'supply_chain_signal.json'}")
    print(f"supply_chain_candidates.json: {output_dir / 'supply_chain_candidates.json'}")
    print(f"supply_chain_visual_review_queue.json: {output_dir / 'supply_chain_visual_review_queue.json'}")
    print(f"candidates: {candidates['candidate_count']}")
    print(f"visual review queue: {visual_queue['review_queue_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
