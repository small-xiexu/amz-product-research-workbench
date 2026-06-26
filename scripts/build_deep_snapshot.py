#!/usr/bin/env python3
"""Fill deep snapshot contract from Agent's raw MCP tool calls/results — CLI entry.

Usage:
  python3 scripts/build_deep_snapshot.py <agent_mcp_dump.json> --source sellersprite|sorftime [--run-id <id>] [--out <path>]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.research_core.pipeline.build_deep_snapshot import build_deep_snapshot


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fill deep snapshot contract from agent MCP dump.")
    parser.add_argument("input_file", type=Path, help="Agent MCP dump JSON file")
    parser.add_argument("--source", required=True, choices=["sellersprite", "sorftime"])
    parser.add_argument("--run-id", default=None, help="Run ID (default: derived from input)")
    parser.add_argument("--out", type=Path, default=None, help="Output path (default: mcp_snapshots/<source>_deep_snapshot.json)")
    args = parser.parse_args(argv)

    input_path: Path = args.input_file.expanduser().resolve()
    if not input_path.is_file():
        print(f"ERROR: input file not found: {input_path}", file=sys.stderr)
        return 2

    agent_dump = json.loads(input_path.read_text(encoding="utf-8"))
    snapshot = build_deep_snapshot(agent_dump, args.source, args.run_id)

    out_path = args.out or (input_path.parent / "mcp_snapshots" / f"{args.source}_deep_snapshot.json")
    out_path = Path(out_path).expanduser().resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Tool calls: {len(snapshot['tool_calls'])}, Results: {len(snapshot['tool_results'])}")
    print(f"Output: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
