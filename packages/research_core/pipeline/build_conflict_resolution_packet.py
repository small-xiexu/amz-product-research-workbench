#!/usr/bin/env python3
"""Build conflict resolution packet from dual evidence packets.

Compares overlapping fields between market_structure (卖家精灵 primary) and
search_demand (Sorftime primary) evidence packets, grades conflicts as
minor / material / blocking, and applies default priority rules.

Usage:
  python3 -m packages.research_core.pipeline.build_conflict_resolution_packet <run_dir>
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

# 默认优先口径：按指标类型决定以哪个数据源为准
DEFAULT_PRIORITY = {
    # 卖家精灵优先
    "monthly_units": "seller_sprite",
    "monthly_sales": "seller_sprite",
    "top100": "seller_sprite",
    "price_band": "seller_sprite",
    "price_distribution": "seller_sprite",
    "concentration": "seller_sprite",
    "brand_concentration": "seller_sprite",
    "seller_concentration": "seller_sprite",
    "product_concentration": "seller_sprite",
    "review_distribution": "seller_sprite",
    "rating_distribution": "seller_sprite",
    "aba": "seller_sprite",
    "aba_keywords": "seller_sprite",
    # Sorftime 优先
    "keyword_search_volume": "sorftime",
    "keyword_trend": "sorftime",
    "keyword_extends": "sorftime",
    "category_trend": "sorftime",
    "traffic_keywords": "sorftime",
    "asin_traffic": "sorftime",
    "competitor_keywords": "sorftime",
    "natural_position": "sorftime",
    "category_tree": "sorftime",
    # 交叉验证
    "price": "cross_check",
    "rating": "cross_check",
    "review_count": "cross_check",
    "category": "cross_check",
}

# 冲突阈值：{field: (material_pct, blocking_pct)}
CONFLICT_THRESHOLDS: dict[str, tuple[float, float]] = {
    "price": (0.10, 0.20),
    "review_count": (0.15, 0.25),
    "monthly_units": (0.20, 0.40),
    "monthly_sales": (0.20, 0.40),
    "rating": (0.06, 0.10),
    "category": (0, 0),
}


def build_conflict_resolution_packet(run_dir: Path) -> dict[str, Any]:
    """Compare dual-source evidence packets and produce conflict resolution."""
    market = _load_packet(run_dir / "market_structure" / "market_structure_evidence_packet.json")
    search = _load_packet(run_dir / "search_demand" / "search_demand_evidence_packet.json")

    conflicts: list[dict] = []
    blocking_conflicts: list[dict] = []
    basis_mismatches: list[dict] = []

    # Extract comparable fields from both packets
    market_facts = _flatten_facts(market.get("facts", []))
    search_facts = _flatten_facts(search.get("facts", []))

    # Also check derived_metrics
    market_metrics = _flatten_facts(market.get("derived_metrics", []))
    search_metrics = _flatten_facts(search.get("derived_metrics", []))

    all_market = {**market_facts, **market_metrics}
    all_search = {**search_facts, **search_metrics}

    # Find overlapping fields
    for field in set(all_market.keys()) & set(all_search.keys()):
        market_val = all_market[field]
        search_val = all_search[field]

        # Determine priority
        priority = _get_priority(field)
        metric_basis = _extract_metric_basis(market, search, field)

        # Check comparability
        comparability = _check_comparability(market, search, field, metric_basis)
        if not comparability["comparable"]:
            basis_mismatches.append({
                "field": field,
                "reason": comparability["reason"],
                "market_basis": metric_basis.get("market"),
                "search_basis": metric_basis.get("search"),
            })
            continue

        # Compare values
        diff_pct = _calc_difference(market_val, search_val)
        if diff_pct is None:
            continue

        severity = _grade_conflict(field, diff_pct)

        conflict = {
            "conflict_id": f"conflict_{field}",
            "field": field,
            "source_values": {
                "seller_sprite": market_val,
                "sorftime": search_val,
            },
            "difference_pct": round(diff_pct, 3),
            "severity": severity,
            "preferred_source": priority,
            "preferred_value": market_val if priority == "seller_sprite" else search_val,
            "preferred_reason": _preferred_reason(priority, field),
            "metric_basis": metric_basis,
        }

        if severity == "blocking":
            conflict["required_action"] = "暂停，要求补数或人工确认"
            conflict["report_expression_hint"] = _report_hint(field, severity)
            blocking_conflicts.append(conflict)
        elif severity == "material":
            conflict["required_action"] = "触发复核，报告中转成谨慎判断"
            conflict["report_expression_hint"] = _report_hint(field, severity)
        else:
            conflict["required_action"] = "记录但不阻塞"
            conflict["report_expression_hint"] = ""

        conflicts.append(conflict)

    # Check for fields present in only one source
    market_only = set(all_market.keys()) - set(all_search.keys())
    search_only = set(all_search.keys()) - set(all_market.keys())

    single_source_gaps: list[dict] = []
    for field in sorted(market_only):
        single_source_gaps.append({"field": field, "available_in": "seller_sprite", "missing_in": "sorftime"})
    for field in sorted(search_only):
        single_source_gaps.append({"field": field, "available_in": "sorftime", "missing_in": "seller_sprite"})

    return {
        "schema_version": "conflict-resolution-v1",
        "packet_id": "conflict_resolution",
        "stage": "conflict_review",
        "source_types": ["seller_sprite", "sorftime"],
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "conflicts": conflicts,
        "blocking_conflicts": blocking_conflicts,
        "basis_mismatches": basis_mismatches,
        "single_source_gaps": single_source_gaps,
        "summary": {
            "total_conflicts": len(conflicts),
            "blocking": len(blocking_conflicts),
            "material": len([c for c in conflicts if c["severity"] == "material"]),
            "minor": len([c for c in conflicts if c["severity"] == "minor"]),
            "basis_mismatches": len(basis_mismatches),
        },
    }


def _load_packet(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, ValueError):
        return {}


def _flatten_facts(facts: list[Any], prefix: str = "") -> dict[str, Any]:
    """Flatten facts/derived_metrics into {field_name: value} dict."""
    result: dict[str, Any] = {}
    for item in facts:
        if isinstance(item, dict):
            item_id = item.get("id") or item.get("field") or item.get("dimension") or ""
            value = item.get("value")
            if value is not None:
                key = f"{prefix}.{item_id}" if prefix else str(item_id)
                result[key] = value
            for sub_key, sub_val in item.items():
                if sub_key in ("id", "field", "dimension", "evidence_refs", "source"):
                    continue
                if isinstance(sub_val, (int, float, str)) and sub_val != "":
                    full_key = f"{prefix}.{item_id}.{sub_key}" if item_id and prefix else (
                        f"{item_id}.{sub_key}" if item_id else (
                            f"{prefix}.{sub_key}" if prefix else str(sub_key)))
                    result[full_key] = sub_val
    return result


def _get_priority(field: str) -> str:
    """Determine which source takes priority for a given field."""
    for pattern, source in DEFAULT_PRIORITY.items():
        if pattern in field.lower().replace(" ", "_"):
            return source
    return "cross_check"


def _extract_metric_basis(market: dict, search: dict, field: str) -> dict[str, dict]:
    """Extract metric_basis from each source for comparison."""
    def _basis(packet: dict) -> dict:
        return {
            "data_window": packet.get("data_window", "unknown"),
            "source_type": packet.get("source_type", "unknown"),
            "collected_at": packet.get("collected_at", "unknown"),
        }

    return {"market": _basis(market), "search": _basis(search)}


def _check_comparability(market: dict, search: dict, field: str, basis: dict) -> dict:
    """Check if two values are comparable based on their metric_basis."""
    market_basis = basis.get("market", {})
    search_basis = basis.get("search", {})

    # Different data windows → basis_mismatch
    if market_basis.get("data_window") != search_basis.get("data_window"):
        return {
            "comparable": False,
            "reason": f"数据窗口不一致: {market_basis.get('data_window')} vs {search_basis.get('data_window')}",
        }

    # Different source types are expected (seller_sprite vs sorftime), so that's fine
    return {"comparable": True, "reason": ""}


def _calc_difference(val1: Any, val2: Any) -> float | None:
    """Calculate percentage difference between two numeric values."""
    try:
        v1 = float(val1)
        v2 = float(val2)
    except (ValueError, TypeError):
        return None

    if v1 == 0 and v2 == 0:
        return 0.0
    if v1 == 0 or v2 == 0:
        return 1.0

    return abs(v1 - v2) / max(abs(v1), abs(v2))


def _grade_conflict(field: str, diff_pct: float) -> str:
    """Grade conflict severity based on thresholds."""
    for pattern, (material_pct, blocking_pct) in CONFLICT_THRESHOLDS.items():
        if pattern in field.lower().replace(" ", "_"):
            if diff_pct >= blocking_pct:
                return "blocking"
            if diff_pct >= material_pct:
                return "material"
            return "minor"

    # Default thresholds
    if diff_pct >= 0.40:
        return "blocking"
    if diff_pct >= 0.20:
        return "material"
    return "minor"


def _preferred_reason(priority: str, field: str) -> str:
    """Explain why a source is preferred."""
    reasons = {
        "seller_sprite": "卖家精灵在市场结构类数据（销量、销售额、价格带、集中度）上口径更完整",
        "sorftime": "Sorftime 在搜索需求类数据（搜索量、趋势、流量词、自然位）上覆盖更全",
        "cross_check": "双源交叉验证，差异大时需复核",
    }
    return reasons.get(priority, "无明确优先源")


def _report_hint(field: str, severity: str) -> str:
    """Generate report expression hint — translate conflict to business language."""
    hints = {
        "blocking": "数据差异较大，需补充验证后再做判断",
        "material": "数据存在一定差异，报告中应以谨慎语气表达",
    }
    return hints.get(severity, "")


# CLI entry
if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Build conflict resolution packet")
    parser.add_argument("run_dir", type=Path, help="Path to run directory")
    parser.add_argument("-o", "--output", type=Path, default=None, help="Output path (default: run_dir/conflict_review/conflict_resolution_packet.json)")
    args = parser.parse_args()

    run_dir = args.run_dir.expanduser().resolve()
    if not run_dir.is_dir():
        print(f"ERROR: run_dir not found: {run_dir}", file=sys.stderr)
        raise SystemExit(1)

    result = build_conflict_resolution_packet(run_dir)

    output_path = args.output or (run_dir / "conflict_review" / "conflict_resolution_packet.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {output_path}")
    print(f"Conflicts: {result['summary']['total_conflicts']} total, "
          f"{result['summary']['blocking']} blocking, "
          f"{result['summary']['material']} material, "
          f"{result['summary']['minor']} minor")
