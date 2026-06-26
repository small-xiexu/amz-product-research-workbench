#!/usr/bin/env python3
"""Scan reusable product-research assets for case-specific hardcoding — CLI entry."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.research_core.pipeline.check_generic_redlines import (
    DEFAULT_EXCLUDE_PATHS,
    DEFAULT_INCLUDE_PATHS,
    DEFAULT_REDLINE_TERMS,
    merge_terms,
    latest_run_dir,
    scan_generic_redlines,
)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fail when reusable product-research assets contain case-specific hardcoding."
    )
    parser.add_argument("--root", default=".", help="Repository root to scan. Defaults to current directory.")
    parser.add_argument("--include", action="append", dest="includes", help="Path to include. Can be repeated.")
    parser.add_argument("--exclude", action="append", default=[], help="Extra path/pattern to exclude. Can be repeated.")
    parser.add_argument("--no-default-excludes", action="store_true", help="Use only --exclude patterns.")
    parser.add_argument("--token", action="append", default=[], help="Extra case-specific token to block.")
    parser.add_argument("--token-file", action="append", type=Path, default=[], help="JSON token file.")
    parser.add_argument("--run-dir", action="append", type=Path, default=[], help="Run artifact directory for tokens.")
    parser.add_argument("--allow-empty-token-set", action="store_true", help="Succeed even with no tokens.")
    parser.add_argument("--no-auto-run-dir", action="store_true", help="Don't auto-derive tokens from latest run.")
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
        print(json.dumps({
            "status": "fail" if violations else "ok",
            "violation_count": len(violations),
            "violations": [asdict(item) for item in violations],
        }, ensure_ascii=False, indent=2))
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
