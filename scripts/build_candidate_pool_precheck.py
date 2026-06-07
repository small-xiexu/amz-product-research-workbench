#!/usr/bin/env python3
"""Build candidate-pool precheck outputs from candidate_pool.json."""

from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.report_renderer.render_candidate_pool import build_outputs


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: build_candidate_pool_precheck.py <candidate_pool_json> <output_dir>")
        return 1
    build_outputs(sys.argv[1], sys.argv[2])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
