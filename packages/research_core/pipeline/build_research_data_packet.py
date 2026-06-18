#!/usr/bin/env python3
"""Build the structured data packet used before insight generation."""

from __future__ import annotations

import copy
import json
from collections import Counter
from pathlib import Path
from typing import Any

from packages.research_core.pipeline.cross_analysis import build_cross_analysis
from packages.research_core.pipeline.parse_top100_dimensions import parse_top100_dimensions
from packages.research_core.pipeline.build_research_package_from_candidate import (
    _build_competitor_deep_dive,
    _build_review_sources,
    _build_voc_analysis,
    _brand_concentration_text,
    _collect_voc_evidence,
    _competitor_items,
    _market_size_text,
    _new_listing_text,
    _price_band_text,
    _return_rate_text,
    _select_candidate,
    _seller_concentration_text,
    _supply_chain_purchase_cost_text,
)


DIMENSION_RULE_KEYS = (
    "top100_dimension_rules",
    "dimension_rules",
    "attribute_dimension_rules",
    "attribute_rules",
)
DIMENSION_RULE_PATH_KEYS = tuple(f"{key}_path" for key in DIMENSION_RULE_KEYS)
CROSS_CONFIG_KEYS = (
    "top100_cross_config",
    "cross_analysis_config",
    "attribute_cross_config",
    "cross_config",
)
CROSS_CONFIG_PATH_KEYS = tuple(f"{key}_path" for key in CROSS_CONFIG_KEYS)


def build_research_data_packet(
    candidate_pool: dict[str, Any],
    candidate_id: str | None,
    voc_package: dict[str, Any] | None = None,
    route_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    candidate = copy.deepcopy(_select_candidate(candidate_pool.get("candidates", []), candidate_id))
    if route_profile:
        candidate = {**candidate, "product_route_profile": copy.deepcopy(route_profile)}

    metadata = candidate_pool.get("metadata", {}) if isinstance(candidate_pool.get("metadata"), dict) else {}
    source_brief = candidate_pool.get("source_brief", {}) if isinstance(candidate_pool.get("source_brief"), dict) else {}
    profit_space = candidate.get("preliminary_profit_space", {}) if isinstance(candidate.get("preliminary_profit_space"), dict) else {}
    supply_chain_signal = profit_space.get("supply_chain_signal", {}) if isinstance(profit_space.get("supply_chain_signal"), dict) else {}
    competitor_candidates = candidate.get("competitor_candidates", {}) if isinstance(candidate.get("competitor_candidates"), dict) else {}
    market_structure = _build_packet_market_structure(candidate_pool, candidate)
    candidate["market_structure"] = market_structure

    voc_review_sources = _build_review_sources(voc_package)
    return {
        "data_packet_version": "P28.4",
        "metadata": {
            "site": metadata.get("site", source_brief.get("site", "US")),
            "seed_keyword_or_category": candidate.get("name", "未命名候选方向"),
            "product_shape": f"{candidate.get('candidate_type', 'candidate')}：{candidate.get('reason', '')}",
            "generated_at": metadata.get("generated_at", ""),
            "data_sources": metadata.get("data_sources", []) + candidate.get("source_refs", []),
            "candidate_id": candidate.get("candidate_id"),
            "candidate_pool_id": metadata.get("pool_id"),
        },
        "constraints": {
            "exclusion_rules": source_brief.get("exclusion_rules", []),
            "preference_rules": source_brief.get("preference_rules", {}),
        },
        "operator_inputs": {
            "target_price_range": profit_space.get("price_band", "待补"),
            "purchase_cost": _supply_chain_purchase_cost_text(supply_chain_signal),
            "exchange_rate": "待补",
            "fba_fee": "待补",
            "storage_fee": "按建议售价 3% 待算",
            "inbound_placement_fee": "待补",
            "ad_rate_assumption": 0.2,
            "return_rate_assumption": "待补",
        },
        "product_flags": candidate.get("risk_flags", []),
        "raw_sources": {
            "candidate_pool": {
                "pool_id": metadata.get("pool_id"),
                "candidate_id": candidate.get("candidate_id"),
                "source_refs": candidate.get("source_refs", []),
            },
            "review_voc_package": voc_review_sources,
        },
        "normalized_tables": {
            "candidate": candidate,
            "top100": _top100_products(candidate, market_structure),
            "top_product_tags": market_structure.get("tagged_products", []),
            "voc_evidence": _collect_voc_evidence(voc_package),
        },
        "market_structure": market_structure,
        "market_analysis": {
            "market_size": _market_size_text(candidate),
            "price_band": _price_band_text(candidate),
            "brand_concentration": _brand_concentration_text(candidate),
            "seller_concentration": _seller_concentration_text(candidate),
            "new_listing_ratio": _new_listing_text(candidate),
            "return_rate": _return_rate_text(candidate),
            "sorftime_category_report": candidate.get("demand_evidence", {}).get("sorftime_category_report", {}),
        },
        "keyword_analysis": {
            "search_signal": candidate.get("demand_evidence", {}).get("search_signal", "待填"),
            "trend_signal": candidate.get("demand_evidence", {}).get("trend_signal", "待填"),
        },
        "competitor_pool": {
            "top10": _competitor_items(competitor_candidates.get("top10", [])),
            "recent_winners": _competitor_items(competitor_candidates.get("recent_winners", [])),
            "structure_supplement": _competitor_items(competitor_candidates.get("structure_supplement", [])),
        },
        "profit_reference": {
            "base_fba_gross_profit": "待补",
            "base_fba_margin": "待补",
            "post_ads_returns_gross_profit": "待补",
            "post_ads_returns_margin": "待补",
            "preliminary_profit_space": profit_space,
            "supply_chain_signal": profit_space.get("supply_chain_signal", {}),
        },
        "return_risk": candidate.get("return_risk", {}),
        "ip_screening": candidate.get("ip_compliance_risk", {}),
        "compliance_screening": candidate.get("ip_compliance_risk", {}),
        "review_sources": voc_review_sources,
        "voc_analysis": _build_voc_analysis(voc_package),
        "competitor_deep_dive": _build_competitor_deep_dive(competitor_candidates),
        "workspace_views": {
            "candidate_card": candidate,
        },
        "excel_sheets": {
            "data_source": "data.xlsx",
        },
        "lineage": {
            "candidate_pool_id": metadata.get("pool_id"),
            "candidate_id": candidate.get("candidate_id"),
            "top100_source_count": len(candidate.get("top_products", []) or []),
            "market_structure_source": "candidate_pool.market_structure",
            "voc_source_count": len(_collect_voc_evidence(voc_package)),
        },
    }


def _build_packet_market_structure(candidate_pool: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    market_structure = copy.deepcopy(candidate.get("market_structure", {}))
    if not isinstance(market_structure, dict):
        market_structure = {}

    rules_config = _find_config(candidate_pool, candidate, DIMENSION_RULE_KEYS, DIMENSION_RULE_PATH_KEYS)
    cross_config = _find_config(candidate_pool, candidate, CROSS_CONFIG_KEYS, CROSS_CONFIG_PATH_KEYS)
    if not rules_config and not cross_config:
        return market_structure

    products = _top100_products(candidate, market_structure)
    parsed_products = products
    if isinstance(rules_config, dict):
        parsed_products, uncertain_products = parse_top100_dimensions(products, rules_config)
        tagged_products = _products_with_parsed_tags(parsed_products)
        market_structure["tagged_products"] = tagged_products
        market_structure["attribute_definitions"] = _merge_by_dimension(
            _attribute_definitions_from_rules(rules_config),
            market_structure.get("attribute_definitions", []),
        )
        market_structure["attribute_distributions"] = _merge_by_dimension(
            _parsed_attribute_distributions(parsed_products, rules_config),
            market_structure.get("attribute_distributions", []),
        )
        market_structure["pending_label_items"] = _merge_pending_label_items(
            _pending_label_items_from_uncertain(parsed_products, uncertain_products),
            market_structure.get("pending_label_items", []),
        )
        market_structure["parsed_dimension_uncertain_products"] = uncertain_products
        market_structure["scripted_dimension_parse"] = {
            "enabled": True,
            "dimension_count": len(rules_config.get("dimensions", [])) if isinstance(rules_config.get("dimensions"), list) else 0,
            "uncertain_product_count": len(uncertain_products),
        }
    elif market_structure.get("tagged_products"):
        parsed_products = [item for item in market_structure.get("tagged_products", []) if isinstance(item, dict)]

    if isinstance(cross_config, dict):
        cross_result = build_cross_analysis(parsed_products, cross_config)
        market_structure["cross_analysis"] = _decorate_cross_analysis(cross_result)
        market_structure["scripted_cross_analysis"] = {
            "enabled": True,
            "pair_count": len(cross_result),
        }
        market_structure["gap_candidates"] = _gap_candidates_from_cross_analysis(cross_result)

    return market_structure


def _find_config(
    candidate_pool: dict[str, Any],
    candidate: dict[str, Any],
    value_keys: tuple[str, ...],
    path_keys: tuple[str, ...],
) -> dict[str, Any] | None:
    containers = [
        candidate,
        candidate.get("market_structure", {}) if isinstance(candidate.get("market_structure"), dict) else {},
        candidate_pool.get("metadata", {}) if isinstance(candidate_pool.get("metadata"), dict) else {},
        candidate_pool,
    ]
    for container in containers:
        if not isinstance(container, dict):
            continue
        for key in value_keys:
            value = container.get(key)
            if isinstance(value, dict):
                return value
        for key in path_keys:
            value = container.get(key)
            if isinstance(value, str) and value.strip():
                return _read_json_config(value, candidate_pool)
    return None


def _read_json_config(value: str, candidate_pool: dict[str, Any]) -> dict[str, Any] | None:
    path = Path(value).expanduser()
    if not path.is_absolute():
        base = _config_base_dir(candidate_pool)
        path = base / path
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else None


def _config_base_dir(candidate_pool: dict[str, Any]) -> Path:
    metadata = candidate_pool.get("metadata", {}) if isinstance(candidate_pool.get("metadata"), dict) else {}
    for key in ("config_base_dir", "source_folder"):
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            return Path(value).expanduser()
    return Path.cwd()


def _top100_products(candidate: dict[str, Any], market_structure: dict[str, Any]) -> list[dict[str, Any]]:
    products = candidate.get("top_products", [])
    tagged = market_structure.get("tagged_products", [])
    if isinstance(products, list) and products:
        rows = [copy.deepcopy(item) for item in products if isinstance(item, dict)]
        if isinstance(tagged, list):
            tagged_by_asin = {
                str(item.get("asin") or item.get("ASIN") or ""): item
                for item in tagged
                if isinstance(item, dict) and (item.get("asin") or item.get("ASIN"))
            }
            for row in rows:
                tagged_row = tagged_by_asin.get(str(row.get("asin") or row.get("ASIN") or ""))
                if not tagged_row:
                    continue
                for key in ("attribute_tags", "tag_confidence", "tag_notes", "parsed_dimensions"):
                    if key not in row and key in tagged_row:
                        row[key] = copy.deepcopy(tagged_row[key])
        return rows
    if isinstance(tagged, list):
        return [copy.deepcopy(item) for item in tagged if isinstance(item, dict)]
    return []


def _products_with_parsed_tags(products: list[dict[str, Any]]) -> list[dict[str, Any]]:
    tagged_products: list[dict[str, Any]] = []
    for product in products:
        tagged = copy.deepcopy(product)
        tags = dict(tagged.get("attribute_tags", {})) if isinstance(tagged.get("attribute_tags"), dict) else {}
        parsed = tagged.get("parsed_dimensions", {})
        confidences: list[str] = []
        notes: list[str] = []
        if isinstance(parsed, dict):
            for label, item in parsed.items():
                if not isinstance(item, dict):
                    continue
                tags[str(label)] = item.get("value", "未知")
                confidence = str(item.get("parse_confidence") or "")
                if confidence:
                    confidences.append(confidence)
                if confidence == "low":
                    notes.append(f"{label} 为低置信度，需运营复核。")
        tagged["attribute_tags"] = tags
        tagged["tag_confidence"] = _combined_confidence(confidences, tagged.get("tag_confidence"))
        existing_notes = tagged.get("tag_notes") if isinstance(tagged.get("tag_notes"), list) else []
        tagged["tag_notes"] = [*existing_notes, *notes]
        tagged_products.append(tagged)
    return tagged_products


def _combined_confidence(confidences: list[str], fallback: Any) -> str:
    if "low" in confidences:
        return "低"
    if "medium" in confidences:
        return "中"
    if "high" in confidences:
        return "高"
    return str(fallback or "待确认")


def _attribute_definitions_from_rules(rules_config: dict[str, Any]) -> list[dict[str, str]]:
    definitions: list[dict[str, str]] = []
    for dimension in rules_config.get("dimensions", []):
        if not isinstance(dimension, dict):
            continue
        label = str(dimension.get("label") or dimension.get("name") or "").strip()
        if not label:
            continue
        definitions.append(
            {
                "dimension": label,
                "label": str(dimension.get("name") or label),
                "rule": _rule_summary(dimension),
            }
        )
    return definitions


def _rule_summary(dimension: dict[str, Any]) -> str:
    rules = dimension.get("rules", [])
    if not isinstance(rules, list):
        return "外置规则：默认低置信回退"
    regex_count = sum(1 for rule in rules if isinstance(rule, dict) and rule.get("type") == "regex")
    keyword_count = sum(1 for rule in rules if isinstance(rule, dict) and rule.get("type") == "keyword")
    return f"外置规则：regex {regex_count} 条，keyword {keyword_count} 组，默认值 {dimension.get('default', '未知')}"


def _parsed_attribute_distributions(products: list[dict[str, Any]], rules_config: dict[str, Any]) -> list[dict[str, Any]]:
    distributions: list[dict[str, Any]] = []
    dimensions = rules_config.get("dimensions", [])
    if not isinstance(dimensions, list):
        return distributions
    for dimension in dimensions:
        if not isinstance(dimension, dict):
            continue
        key = str(dimension.get("label") or dimension.get("name") or "").strip()
        if not key:
            continue
        label = str(dimension.get("name") or key)
        counter: Counter[str] = Counter()
        for product in products:
            parsed = product.get("parsed_dimensions", {})
            value = "未知"
            if isinstance(parsed, dict):
                item = parsed.get(key)
                if isinstance(item, dict):
                    value = str(item.get("value") or "未知")
                elif item not in (None, ""):
                    value = str(item)
            counter[value] += 1
        total = sum(counter.values())
        buckets = [
            {"value": value, "count": count, "share": count / total if total else 0}
            for value, count in counter.most_common()
        ]
        distributions.append(
            {
                "dimension": key,
                "label": label,
                "total": total,
                "buckets": buckets,
                "summary": _distribution_summary(label, buckets),
            }
        )
    return distributions


def _distribution_summary(label: str, buckets: list[dict[str, Any]]) -> str:
    if not buckets:
        return f"{label} 暂无可用分布。"
    top = buckets[0]
    return f"{label}最多为 {top.get('value')}，样本 {top.get('count')} 个。"


def _merge_by_dimension(preferred: list[dict[str, Any]], existing: Any) -> list[dict[str, Any]]:
    merged = [item for item in preferred if isinstance(item, dict)]
    seen = {str(item.get("dimension")) for item in merged}
    if isinstance(existing, list):
        for item in existing:
            if not isinstance(item, dict):
                continue
            dimension = str(item.get("dimension"))
            if dimension in seen:
                continue
            seen.add(dimension)
            merged.append(item)
    return merged


def _pending_label_items_from_uncertain(
    products: list[dict[str, Any]],
    uncertain_products: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_asin = {str(item.get("asin") or item.get("ASIN") or ""): item for item in products}
    pending: list[dict[str, Any]] = []
    for item in uncertain_products:
        asin = str(item.get("asin") or "")
        product = by_asin.get(asin, {})
        dimensions = item.get("uncertain_dimensions", [])
        pending.append(
            {
                "asin": asin,
                "title": item.get("title") or product.get("title"),
                "price": product.get("price"),
                "monthly_units": product.get("monthly_units") or product.get("monthly_sales"),
                "product_route": "待确认",
                "tag_confidence": "低",
                "tag_notes": [f"外置规则低置信维度：{', '.join(str(dim) for dim in dimensions)}"],
                "uncertain_dimensions": dimensions,
            }
        )
    return pending


def _merge_pending_label_items(preferred: list[dict[str, Any]], existing: Any) -> list[dict[str, Any]]:
    rows = [item for item in preferred if isinstance(item, dict)]
    seen = {str(item.get("asin")) for item in rows if item.get("asin")}
    if isinstance(existing, list):
        for item in existing:
            if not isinstance(item, dict):
                continue
            asin = str(item.get("asin") or "")
            if asin and asin in seen:
                continue
            if asin:
                seen.add(asin)
            rows.append(item)
    return rows


def _decorate_cross_analysis(cross_result: list[dict[str, Any]]) -> list[dict[str, Any]]:
    decorated: list[dict[str, Any]] = []
    for item in cross_result:
        matrix = item.get("matrix", []) if isinstance(item.get("matrix"), list) else []
        gaps = item.get("gaps", []) if isinstance(item.get("gaps"), list) else []
        gap_index = {
            (gap.get("dim1_value"), gap.get("dim2_value")): gap.get("gap_type")
            for gap in gaps
            if isinstance(gap, dict)
        }
        cells = []
        for cell in matrix:
            if not isinstance(cell, dict):
                continue
            count = _to_number(cell.get("count"))
            total_sales = _to_number(cell.get("total_sales"))
            cells.append(
                {
                    "row": cell.get("dim1_value"),
                    "column": cell.get("dim2_value"),
                    "count": cell.get("count"),
                    "avg_price": "",
                    "avg_monthly_units": round(total_sales / count, 2) if count else 0,
                    "avg_rating": "",
                    "sample_asins": cell.get("products", []),
                    "opportunity_type": gap_index.get((cell.get("dim1_value"), cell.get("dim2_value")), ""),
                    "interpretation": "",
                }
            )
        blank_count = sum(1 for gap in gaps if isinstance(gap, dict) and gap.get("gap_type") == "空白")
        thin_count = sum(1 for gap in gaps if isinstance(gap, dict) and gap.get("gap_type") == "薄供给")
        decorated.append(
            {
                **item,
                "label": f"{item.get('dim1')} x {item.get('dim2')}",
                "row_dimension": item.get("dim1"),
                "column_dimension": item.get("dim2"),
                "purpose": "外置配置交叉矩阵",
                "cells": cells[:20],
                "summary": f"共 {len(matrix)} 个组合，空白 {blank_count} 个，薄供给 {thin_count} 个。",
            }
        )
    return decorated


def _gap_candidates_from_cross_analysis(cross_result: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in cross_result:
        for gap in item.get("gaps", []):
            if not isinstance(gap, dict):
                continue
            rows.append(
                {
                    "cross_dimension": f"{item.get('dim1')} x {item.get('dim2')}",
                    "combination": f"{gap.get('dim1_value')} x {gap.get('dim2_value')}",
                    "gap_type": gap.get("gap_type"),
                    "count": gap.get("count"),
                    "total_sales": gap.get("total_sales"),
                    "total_revenue": gap.get("total_revenue"),
                    "sample_asins": gap.get("products", []),
                }
            )
    return rows


def _to_number(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
