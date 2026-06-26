#!/usr/bin/env python3
"""Fill missing contract fields in Agent-generated quick evidence packets — CLI entry.

Usage:
  python3 scripts/fill_quick_packet_contract.py <agent_output.json> --source sellersprite|sorftime [--snapshot-dir mcp_snapshots]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.research_core.pipeline.fill_quick_packet_contract import fill_contract


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fill missing contract fields in Agent-generated quick evidence packet.")
    parser.add_argument("input_file", type=Path, help="Agent-generated JSON file")
    parser.add_argument("--source", required=True, choices=["sellersprite", "sorftime"], help="Data source")
    parser.add_argument("--snapshot-dir", type=Path, default=None, help="MCP snapshot directory (for evidence_refs)")
    parser.add_argument("--out", type=Path, default=None, help="Output path (default: overwrite input)")
    args = parser.parse_args(argv)

    input_path: Path = args.input_file.expanduser().resolve()
    if not input_path.is_file():
        print(f"ERROR: input file not found: {input_path}", file=sys.stderr)
        return 2

    agent_output = json.loads(input_path.read_text(encoding="utf-8"))
    snapshot_dir = str(args.snapshot_dir) if args.snapshot_dir else None
    filled = fill_contract(agent_output, args.source, snapshot_dir)

    out_path = args.out or input_path
    out_path.write_text(json.dumps(filled, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Output: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
