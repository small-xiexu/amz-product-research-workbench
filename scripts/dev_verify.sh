#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

RUN_DIR="${1:-}"

python3 -m compileall -q packages scripts tests
python3 -m unittest discover -v
python3 scripts/check_generic_redlines.py --token-file tests/fixtures/generic_redline_tokens.json --no-auto-run-dir

if [[ -n "$RUN_DIR" ]]; then
  python3 scripts/check_generic_redlines.py --run-dir "$RUN_DIR"
fi

git diff --check
