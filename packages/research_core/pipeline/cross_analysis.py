from __future__ import annotations

import argparse
import json
from collections import defaultdict
from itertools import product
from pathlib import Path
from typing import Any


def build_cross_analysis(
    products: list[dict[str, Any]],
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    pairs = config.get("pairs", [])
    if not isinstance(pairs, list):
        raise ValueError("config.pairs must be a list")
    return [_analyze_pair(products, pair) for pair in pairs if isinstance(pair, dict)]


def _analyze_pair(products: list[dict[str, Any]], pair: dict[str, Any]) -> dict[str, Any]:
    dim1 = str(pair.get("dim1") or "").strip()
    dim2 = str(pair.get("dim2") or "").strip()
    if not dim1 or not dim2:
        raise ValueError("each pair must include dim1 and dim2")
    threshold = _to_int(pair.get("scarcity_threshold"), 2)

    dim1_values = sorted(_dimension_values(products, dim1))
    dim2_values = sorted(_dimension_values(products, dim2))
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for item in products:
        groups[(_dimension_value(item, dim1), _dimension_value(item, dim2))].append(item)

    matrix: list[dict[str, Any]] = []
    gaps: list[dict[str, Any]] = []
    for value1, value2 in product(dim1_values, dim2_values):
        items = groups.get((value1, value2), [])
        cell = _cell(dim1, dim2, value1, value2, items)
        matrix.append(cell)
        if cell["count"] == 0:
            gaps.append({**cell, "gap_type": "空白"})
        elif cell["count"] <= threshold:
            gaps.append({**cell, "gap_type": "薄供给"})

    gaps.sort(key=lambda item: (item["count"], -float(item["total_sales"] or 0)))
    return {
        "dim1": dim1,
        "dim2": dim2,
        "scarcity_threshold": threshold,
        "matrix": matrix,
        "gaps": gaps,
    }


def _cell(dim1: str, dim2: str, value1: str, value2: str, products: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "dim1": dim1,
        "dim2": dim2,
        "dim1_value": value1,
        "dim2_value": value2,
        "count": len(products),
        "total_sales": sum(_number(item, "monthly_sales", "monthly_units") for item in products),
        "total_revenue": sum(_number(item, "monthly_revenue", "monthly_revenue_usd") for item in products),
        "products": [
            str(item.get("asin") or item.get("ASIN") or "")
            for item in products[:5]
            if item.get("asin") or item.get("ASIN")
        ],
    }


def _dimension_values(products: list[dict[str, Any]], dimension: str) -> set[str]:
    values = {_dimension_value(item, dimension) for item in products}
    return {value for value in values if value}


def _dimension_value(product: dict[str, Any], dimension: str) -> str:
    parsed = product.get("parsed_dimensions")
    if isinstance(parsed, dict):
        item = parsed.get(dimension)
        if isinstance(item, dict):
            return str(item.get("value") or "未知")
        if item not in (None, ""):
            return str(item)
    tags = product.get("attribute_tags")
    if isinstance(tags, dict) and tags.get(dimension) not in (None, ""):
        return str(tags.get(dimension))
    if product.get(dimension) not in (None, ""):
        return str(product.get(dimension))
    return "未知"


def _number(product: dict[str, Any], *keys: str) -> float:
    for key in keys:
        value = product.get(key)
        if value in (None, ""):
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return 0.0


def _to_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def read_products(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        for key in ("products", "top100", "items", "records", "data"):
            value = data.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    raise ValueError("input must be a product list or object containing products/top100/items/records/data")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build cross-dimension matrix from parsed Top100 products.")
    parser.add_argument("--input", required=True, help="Parsed products JSON path.")
    parser.add_argument("--config", required=True, help="Cross analysis config JSON path.")
    parser.add_argument("--output", required=True, help="Cross analysis JSON output path.")
    args = parser.parse_args(argv)

    products = read_products(Path(args.input))
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    result = build_cross_analysis(products, config)
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
