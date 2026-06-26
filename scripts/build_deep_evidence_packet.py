#!/usr/bin/env python3
"""Fill P4 evidence packet contract from Agent's free-form deep dive output — CLI entry.

Usage:
  python3 scripts/build_deep_evidence_packet.py <agent_output.json> --source sellersprite|sorftime [--out <path>]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.research_core.pipeline.build_deep_evidence_packet import (
    SOURCE_META,
    build_evidence_packet,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fill P4 evidence packet contract from agent output.")
    parser.add_argument("input_file", type=Path, help="Agent deep dive output JSON")
    parser.add_argument("--source", required=True, choices=["sellersprite", "sorftime"])
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--out", type=Path, default=None, help="Output path (default: auto-derived)")
    args = parser.parse_args(argv)

    input_path: Path = args.input_file.expanduser().resolve()
    if not input_path.is_file():
        print(f"ERROR: input file not found: {input_path}", file=sys.stderr)
        return 2

    meta = SOURCE_META[args.source]
    agent_output = json.loads(input_path.read_text(encoding="utf-8"))
    packet = build_evidence_packet(agent_output, args.source, args.run_id)

    out_path = args.out or (input_path.parent / meta["output_subdir"] / meta["output_file"])
    out_path = Path(out_path).expanduser().resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(packet, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Packet ID: {packet['packet_id']}")
    print(f"Evidence items: {len(packet.get('evidence_items', []))}")
    print(f"Output: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
