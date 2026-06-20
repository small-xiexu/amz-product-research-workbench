#!/usr/bin/env python3
"""Scan reusable product-research assets for case-specific hardcoding.

This guard is intentionally scoped to reusable source assets. Per-run data,
manual imports, eval fixtures, and historical plans may contain real product
terms; templates, agents, scripts, and renderer code should not.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence


DEFAULT_INCLUDE_PATHS = (
    "skills/amazon-product-research",
    "packages",
    "scripts",
    "docs",
)

DEFAULT_EXCLUDE_PATHS = (
    ".git",
    ".codex",
    ".agents",
    "__pycache__",
    ".pytest_cache",
    ".venv",
    "node_modules",
    "runs",
    "imports",
    "tmp",
    "output",
    "outputs",
    "backups",
    "docs/plans",
    "docs/optimization/plans",
    "skills/amazon-product-research/evals",
    "scripts/check_generic_redlines.py",
)

TEXT_SUFFIXES = {
    ".cfg",
    ".css",
    ".csv",
    ".html",
    ".ini",
    ".js",
    ".json",
    ".jsx",
    ".md",
    ".py",
    ".sh",
    ".sql",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".yaml",
    ".yml",
}

ALLOW_MARKERS = (
    "generic-redline: allow",
    "generic-redline allow",
    "generic_redline_allow",
)

DEFAULT_REDLINE_TERMS: Mapping[str, Sequence[str]] = {}

ASIN_RE = re.compile(r"\bB[0-9A-Z]{9}\b", re.IGNORECASE)
NODE_ID_KEYS = {"nodeid", "node_id"}
ASIN_KEYS = {"asin", "asins", "representative_asins", "low_review_samples", "sample_asins"}
BRAND_SELLER_KEYS = {
    "brand",
    "brand_name",
    "seller",
    "seller_name",
    "supplier",
    "supplier_name",
    "store",
    "store_name",
    "storename",
}
CATEGORY_KEYWORDS_KEYS = {
    "category_name",
    "category_ref",
    "category_path",
    "primary_category",
    "subcategory",
    "subcategory_name",
    "keyword",
    "keywords",
    "top_keyword",
    "main_keyword",
    "search_name",
    "searchname",
    "product_name",
    "productname",
    "market_label",
}
ROUTE_PRODUCT_TERM_KEYS = {
    "candidate_name",
    "profile_id",
    "route_name",
    "route_label",
    "task_name",
    "target_product",
    "target_route",
}
TOKEN_SKIP_VALUES = {
    "us",
    "usa",
    "amazon",
    "amz",
    "fba",
    "fbm",
    "rmb",
    "cny",
    "usd",
    "true",
    "false",
    "none",
    "null",
    "strong",
    "medium",
    "weak",
    "high",
    "low",
    "main_check",
    "supplement_check",
    "exclude",
    "primary_reference",
    "high_sales_benchmark",
    "new_release_sample",
    "premium_benchmark",
    "painpoint_reference",
    "excluded_reference",
    "base_core",
    "upgraded_core",
    "scenario_specialized",
    "bundle_or_set",
    "feature_material_upgrade",
    "adjacent_or_watch",
    "broad_market",
    "subcategory_market",
    "mixed_pool",
    "watch",
    "keep",
    "primary",
    "secondary",
    "category_report",
    "category_report_from_history",
    "category_trend",
    "product_traffic_terms",
    "competitor_product_keywords",
    "keyword_extends",
    "keyword_detail",
    "similar_product_feature",
    "potential_product",
    "search_categories_broadly",
    "category_search_from_product_name",
}
RUN_TOKEN_FILE_SUFFIXES = {".json", ".md", ".txt"}
RUN_TOKEN_EXCLUDE_DIRS = {
    "inputs",
    "seller_sprite",
    "reviews",
    "review",
    "1688",
    "exports",
    "raw",
    "attachments",
}
MAX_RUN_TOKEN_FILE_BYTES = 1_000_000


@dataclass(frozen=True)
class RedlineViolation:
    path: str
    line: int
    group: str
    token: str
    text: str


def load_token_file(path: Path) -> dict[str, list[str]]:
    """Load extra redline tokens from a JSON list or group-to-list object."""

    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return {"custom": [str(item) for item in payload if str(item).strip()]}
    if isinstance(payload, dict):
        if "groups" in payload and isinstance(payload["groups"], dict):
            payload = payload["groups"]
        groups: dict[str, list[str]] = {}
        for group, values in payload.items():
            if isinstance(values, list):
                groups[str(group)] = [str(item) for item in values if str(item).strip()]
            elif isinstance(values, str) and values.strip():
                groups[str(group)] = [values]
        return groups
    raise ValueError(f"Unsupported token file format: {path}")


def merge_terms(
    base_terms: Mapping[str, Sequence[str]] = DEFAULT_REDLINE_TERMS,
    custom_terms: Iterable[str] = (),
    token_files: Iterable[Path] = (),
    run_dirs: Iterable[Path] = (),
) -> dict[str, tuple[str, ...]]:
    groups: dict[str, list[str]] = {
        group: [term for term in terms if term.strip()]
        for group, terms in base_terms.items()
    }
    extra = [term for term in custom_terms if term.strip()]
    if extra:
        groups.setdefault("custom", []).extend(extra)
    for token_file in token_files:
        for group, terms in load_token_file(token_file).items():
            groups.setdefault(group, []).extend(terms)
    for run_dir in run_dirs:
        for group, terms in collect_run_redline_terms(run_dir).items():
            groups.setdefault(group, []).extend(terms)
    return {group: tuple(dict.fromkeys(terms)) for group, terms in groups.items()}


def useful_case_token(value: str, allow_short: bool = False) -> bool:
    token = " ".join(value.strip().split())
    if not token:
        return False
    folded = token.casefold()
    if folded in TOKEN_SKIP_VALUES:
        return False
    if token.startswith("<") and token.endswith(">"):
        return False
    if ASIN_RE.fullmatch(token):
        return True
    if token.startswith("http://") or token.startswith("https://"):
        return False
    if "/" in token and len(token.split()) <= 2:
        return False
    if len(token) > 80:
        return False
    if allow_short:
        return len(token) >= 3
    cjk_count = sum(1 for char in token if "\u4e00" <= char <= "\u9fff")
    if cjk_count >= 3:
        return True
    if " " in token and len(token) >= 8:
        return True
    return len(token) >= 12


def add_term(groups: dict[str, set[str]], group: str, value: object, allow_short: bool = False) -> None:
    if value is None:
        return
    if isinstance(value, (int, float)):
        value = str(value)
    if not isinstance(value, str):
        return
    token = " ".join(value.strip().split())
    if useful_case_token(token, allow_short=allow_short):
        groups.setdefault(group, set()).add(token)


def add_terms_from_value(
    groups: dict[str, set[str]],
    group: str,
    value: object,
    allow_short: bool = False,
) -> None:
    if isinstance(value, list):
        for item in value:
            add_terms_from_value(groups, group, item, allow_short=allow_short)
        return
    if isinstance(value, dict):
        return
    add_term(groups, group, value, allow_short=allow_short)


def collect_run_json_terms(payload: object, groups: dict[str, set[str]], key_hint: str = "") -> None:
    if isinstance(payload, dict):
        for key, value in payload.items():
            normalized_key = str(key).casefold()
            normalized_key_no_dash = normalized_key.replace("-", "_")
            if isinstance(value, str):
                for asin in ASIN_RE.findall(value):
                    add_term(groups, "run_asins", asin, allow_short=True)
            if normalized_key_no_dash in NODE_ID_KEYS:
                add_term(groups, "run_node_ids", value, allow_short=True)
            elif normalized_key_no_dash in ASIN_KEYS or normalized_key_no_dash.endswith("_asin"):
                if isinstance(value, list):
                    for item in value:
                        add_term(groups, "run_asins", item, allow_short=True)
                else:
                    add_term(groups, "run_asins", value, allow_short=True)
            elif normalized_key_no_dash in BRAND_SELLER_KEYS:
                add_terms_from_value(groups, "run_brands_sellers", value, allow_short=True)
            elif normalized_key_no_dash in CATEGORY_KEYWORDS_KEYS:
                add_terms_from_value(groups, "run_keywords_categories", value)
            elif normalized_key_no_dash in ROUTE_PRODUCT_TERM_KEYS:
                add_terms_from_value(groups, "run_route_or_product_terms", value)
            collect_run_json_terms(value, groups, normalized_key_no_dash)
    elif isinstance(payload, list):
        for item in payload:
            collect_run_json_terms(item, groups, key_hint)
    elif isinstance(payload, str):
        for asin in ASIN_RE.findall(payload):
            add_term(groups, "run_asins", asin, allow_short=True)


def collect_run_text_terms(text: str, groups: dict[str, set[str]]) -> None:
    for asin in ASIN_RE.findall(text):
        add_term(groups, "run_asins", asin, allow_short=True)


def collect_run_redline_terms(run_dir: Path | str) -> dict[str, tuple[str, ...]]:
    run_path = Path(run_dir).resolve()
    groups: dict[str, set[str]] = {}
    if not run_path.exists():
        raise FileNotFoundError(f"run-dir not found: {run_path}")

    add_term(groups, "run_identity", run_path.name)
    for marker in ("manual_", "product_", "research_"):
        if marker in run_path.name:
            add_term(groups, "run_identity", run_path.name.split(marker, 1)[-1])

    for path in run_path.rglob("*"):
        if not path.is_file() or not looks_textual(path):
            continue
        if any(part in RUN_TOKEN_EXCLUDE_DIRS for part in path.relative_to(run_path).parts):
            continue
        if path.suffix.lower() not in RUN_TOKEN_FILE_SUFFIXES:
            continue
        try:
            if path.stat().st_size > MAX_RUN_TOKEN_FILE_BYTES:
                continue
        except OSError:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        collect_run_text_terms(text, groups)
        if path.suffix.lower() == ".json":
            try:
                collect_run_json_terms(json.loads(text), groups)
            except json.JSONDecodeError:
                continue

    limits = {
        "run_asins": 250,
        "run_node_ids": 100,
        "run_keywords_categories": 200,
        "run_route_or_product_terms": 120,
        "run_brands_sellers": 100,
        "run_identity": 20,
    }
    return {
        group: tuple(sorted(values, key=str.casefold)[: limits.get(group, 100)])
        for group, values in groups.items()
    }


def latest_run_dir(root: Path) -> Path | None:
    runs_dir = root / "runs"
    if not runs_dir.exists() or not runs_dir.is_dir():
        return None
    candidates = [path for path in runs_dir.iterdir() if path.is_dir()]
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def should_exclude(path: Path, root: Path, excludes: Sequence[str]) -> bool:
    rel = path.relative_to(root)
    rel_posix = rel.as_posix()
    parts = set(rel.parts)
    for pattern in excludes:
        normalized = pattern.strip("/")
        if not normalized:
            continue
        if normalized in parts:
            return True
        if rel_posix == normalized or rel_posix.startswith(normalized + "/"):
            return True
        if fnmatch.fnmatch(rel_posix, normalized):
            return True
    return False


def looks_textual(path: Path) -> bool:
    if path.suffix.lower() in TEXT_SUFFIXES:
        return True
    if path.suffix:
        return False
    try:
        chunk = path.read_bytes()[:2048]
    except OSError:
        return False
    return b"\0" not in chunk


def iter_scan_files(root: Path, includes: Sequence[str], excludes: Sequence[str]) -> Iterable[Path]:
    for include in includes:
        target = (root / include).resolve()
        if not target.exists():
            continue
        if target.is_file():
            if not should_exclude(target, root, excludes) and looks_textual(target):
                yield target
            continue
        for path in target.rglob("*"):
            if not path.is_file():
                continue
            if should_exclude(path, root, excludes):
                continue
            if looks_textual(path):
                yield path


def line_has_allow_marker(line: str, previous_line: str = "") -> bool:
    text = f"{previous_line}\n{line}".lower()
    return any(marker in text for marker in ALLOW_MARKERS)


def scan_file(path: Path, root: Path, term_groups: Mapping[str, Sequence[str]]) -> list[RedlineViolation]:
    violations: list[RedlineViolation] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError:
        return violations

    previous_line = ""
    for line_number, line in enumerate(lines, start=1):
        if line_has_allow_marker(line, previous_line):
            previous_line = line
            continue
        folded = line.casefold()
        for group, terms in term_groups.items():
            for token in terms:
                if token_matches_line(line, folded, token, group):
                    violations.append(
                        RedlineViolation(
                            path=path.relative_to(root).as_posix(),
                            line=line_number,
                            group=group,
                            token=token,
                            text=line.strip()[:220],
                        )
                    )
        previous_line = line
    return violations


def token_matches_line(line: str, folded_line: str, token: str, group: str) -> bool:
    # Short brand/seller tokens often collide with programming words, for
    # example a brand named "Method" versus a variable named "method".
    # Keep catching exact hardcoding, but avoid lowercase identifier noise.
    if group == "run_brands_sellers" and len(token) < 8:
        return token in line
    return token.casefold() in folded_line


def scan_generic_redlines(
    root: Path | str = ".",
    includes: Sequence[str] = DEFAULT_INCLUDE_PATHS,
    excludes: Sequence[str] = DEFAULT_EXCLUDE_PATHS,
    term_groups: Mapping[str, Sequence[str]] | None = None,
) -> list[RedlineViolation]:
    root_path = Path(root).resolve()
    terms = term_groups or DEFAULT_REDLINE_TERMS
    violations: list[RedlineViolation] = []
    for path in iter_scan_files(root_path, includes, excludes):
        violations.extend(scan_file(path, root_path, terms))
    return sorted(violations, key=lambda item: (item.path, item.line, item.group, item.token))


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fail when reusable product-research assets contain case-specific hardcoding."
    )
    parser.add_argument("--root", default=".", help="Repository root to scan. Defaults to current directory.")
    parser.add_argument(
        "--include",
        action="append",
        dest="includes",
        help="Path to include. Can be repeated. Defaults to reusable product-research assets.",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="Extra path/pattern to exclude. Can be repeated.",
    )
    parser.add_argument(
        "--no-default-excludes",
        action="store_true",
        help="Use only --exclude patterns instead of built-in excludes.",
    )
    parser.add_argument("--token", action="append", default=[], help="Extra case-specific token to block.")
    parser.add_argument(
        "--token-file",
        action="append",
        type=Path,
        default=[],
        help="JSON token file: either a list, a group-to-list object, or {'groups': {...}}.",
    )
    parser.add_argument(
        "--run-dir",
        action="append",
        type=Path,
        default=[],
        help="Run artifact directory used to derive ASIN/category/keyword/brand redline tokens.",
    )
    parser.add_argument(
        "--allow-empty-token-set",
        action="store_true",
        help="Return success even when no redline tokens are provided or derived.",
    )
    parser.add_argument(
        "--no-auto-run-dir",
        action="store_true",
        help="Do not derive tokens from the latest runs/<run_id> directory when no tokens are passed.",
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    root = Path(args.root).resolve()
    includes = tuple(args.includes or DEFAULT_INCLUDE_PATHS)
    excludes = tuple(args.exclude if args.no_default_excludes else (*DEFAULT_EXCLUDE_PATHS, *args.exclude))
    run_dirs = list(args.run_dir)
    if not run_dirs and not args.token and not args.token_file and not args.no_auto_run_dir:
        auto_run_dir = latest_run_dir(root)
        if auto_run_dir is not None:
            run_dirs.append(auto_run_dir)
    terms = merge_terms(DEFAULT_REDLINE_TERMS, args.token, args.token_file, run_dirs)
    if not any(terms.values()) and not args.allow_empty_token_set:
        message = "generic_redline: NO_TOKENS. Pass --run-dir, --token-file, --token, or keep a runs/<run_id> directory."
        if args.json:
            print(json.dumps({"status": "no_tokens", "violation_count": 0, "violations": []}, ensure_ascii=False))
        else:
            print(message)
        return 2
    violations = scan_generic_redlines(root=root, includes=includes, excludes=excludes, term_groups=terms)

    if args.json:
        print(
            json.dumps(
                {
                    "status": "fail" if violations else "ok",
                    "violation_count": len(violations),
                    "violations": [asdict(item) for item in violations],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    elif violations:
        print("generic_redline: FAIL")
        print("Reusable assets contain case-specific product research terms:")
        for item in violations:
            print(f"- {item.path}:{item.line} [{item.group}] {item.token!r} :: {item.text}")
        print()
        print("Move case facts into runs/<run_id>/ artifacts, fixtures, or pass a narrow waiver marker.")
    else:
        print("generic_redline: OK")

    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
