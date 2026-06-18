from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


CONFIDENCE_RANK = {"low": 1, "medium": 2, "high": 3}


def normalize_text(value: Any) -> str:
    text = str(value or "").lower()
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def parse_top100_dimensions(
    products: list[dict[str, Any]],
    rules_config: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    dimensions = rules_config.get("dimensions", [])
    if not isinstance(dimensions, list):
        raise ValueError("rules.dimensions must be a list")

    parsed_products: list[dict[str, Any]] = []
    uncertain_products: list[dict[str, Any]] = []

    for product in products:
        parsed = dict(product)
        title = str(product.get("title") or product.get("Title") or "")
        text = normalize_text(title)
        parsed_dimensions: dict[str, Any] = {}
        uncertain_dimensions: list[str] = []

        for dimension in dimensions:
            if not isinstance(dimension, dict):
                continue
            label = str(dimension.get("label") or dimension.get("name") or "").strip()
            if not label:
                continue
            result = _parse_dimension(text, dimension)
            parsed_dimensions[label] = result
            if result.get("parse_confidence") == "low":
                uncertain_dimensions.append(label)

        parsed["parsed_dimensions"] = parsed_dimensions
        parsed_products.append(parsed)

        if uncertain_dimensions:
            uncertain_products.append(
                {
                    "asin": product.get("asin") or product.get("ASIN") or "",
                    "title": title,
                    "uncertain_dimensions": uncertain_dimensions,
                }
            )

    return parsed_products, uncertain_products


def _parse_dimension(text: str, dimension: dict[str, Any]) -> dict[str, Any]:
    default_value = dimension.get("default", "未知")
    rules = dimension.get("rules", [])
    if not isinstance(rules, list):
        rules = []

    for rule in rules:
        if not isinstance(rule, dict) or rule.get("type") != "regex":
            continue
        pattern = rule.get("pattern")
        if not isinstance(pattern, str):
            continue
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return {
                "value": _resolve_regex_value(match, str(rule.get("value", "$0"))),
                "parse_confidence": _normalize_confidence(rule.get("confidence"), "high"),
                "matched_rule": "regex",
                "dimension_name": dimension.get("name", ""),
            }

    for rule in rules:
        if not isinstance(rule, dict) or rule.get("type") != "keyword":
            continue
        keywords = rule.get("keywords", [])
        if isinstance(keywords, str):
            keywords = [keywords]
        if not isinstance(keywords, list):
            continue
        for keyword in keywords:
            keyword_text = normalize_text(keyword)
            if keyword_text and keyword_text in text:
                return {
                    "value": rule.get("value", keyword),
                    "parse_confidence": _normalize_confidence(rule.get("confidence"), "medium"),
                    "matched_rule": "keyword",
                    "matched_keyword": keyword,
                    "dimension_name": dimension.get("name", ""),
                }

    return {
        "value": default_value,
        "parse_confidence": "low",
        "matched_rule": "default",
        "dimension_name": dimension.get("name", ""),
    }


def _resolve_regex_value(match: re.Match[str], template: str) -> str:
    def replace(ref_match: re.Match[str]) -> str:
        index = int(ref_match.group(1))
        try:
            return match.group(index) or ""
        except IndexError:
            return ""

    return re.sub(r"\$(\d+)", replace, template)


def _normalize_confidence(value: Any, default: str) -> str:
    text = str(value or default).lower()
    return text if text in CONFIDENCE_RANK else default


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
    parser = argparse.ArgumentParser(description="Parse Top100 product dimensions with external JSON rules.")
    parser.add_argument("--input", required=True, help="Top100 product JSON path.")
    parser.add_argument("--rules", required=True, help="Dimension rules JSON path.")
    parser.add_argument("--output", required=True, help="Parsed products JSON output path.")
    parser.add_argument("--uncertain", required=True, help="Uncertain products JSON output path.")
    args = parser.parse_args(argv)

    products = read_products(Path(args.input))
    rules = json.loads(Path(args.rules).read_text(encoding="utf-8"))
    parsed, uncertain = parse_top100_dimensions(products, rules)

    Path(args.output).write_text(json.dumps(parsed, ensure_ascii=False, indent=2), encoding="utf-8")
    Path(args.uncertain).write_text(json.dumps(uncertain, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
