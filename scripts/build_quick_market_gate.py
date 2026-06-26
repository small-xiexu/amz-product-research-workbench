#!/usr/bin/env python3
"""Generate quick_market_gate.json from two quick evidence packets.

Usage:
  python3 scripts/build_quick_market_gate.py <run_dir>

Expects:
  run_dir/quick_check/sellersprite_quick_evidence_packet.json
  run_dir/quick_check/sorftime_quick_evidence_packet.json

Writes:
  run_dir/quick_check/quick_market_gate.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.research_core.pipeline.quick_market_check import (
    QUICK_CHECK_DIR,
    SOURCE_CONFIG,
    build_quick_market_gate,
    validate_quick_gate,
    validate_quick_packet,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate quick_market_gate.json.")
    parser.add_argument("run_dir", type=Path, help="Run directory (e.g. runs/20260625_sample)")
    args = parser.parse_args(argv)

    run_dir: Path = args.run_dir.expanduser().resolve()
    quick_dir = run_dir / QUICK_CHECK_DIR

    if not quick_dir.is_dir():
        print(f"ERROR: quick_check directory not found: {quick_dir}", file=sys.stderr)
        print("Run Quick Agents first, then fill contract with fill_quick_packet_contract.py", file=sys.stderr)
        return 2

    # Load and validate both quick packets
    packets = {}
    for source, config in SOURCE_CONFIG.items():
        packet_path = quick_dir / config["packet_name"]
        if not packet_path.is_file():
            print(f"ERROR: missing {packet_path}", file=sys.stderr)
            return 2
        try:
            packet = json.loads(packet_path.read_text(encoding="utf-8"))
            validate_quick_packet(packet, source)
            packets[source] = packet
            print(f"  [{source}] validated OK")
        except Exception as exc:
            print(f"ERROR validating {packet_path}: {exc}", file=sys.stderr)
            print(f"  → Run: python3 scripts/fill_quick_packet_contract.py {packet_path} --source {source}", file=sys.stderr)
            return 2

    # Build gate
    gate = build_quick_market_gate(packets["sellersprite"], packets["sorftime"])

    # Validate gate
    try:
        validate_quick_gate(gate)
    except Exception as exc:
        print(f"ERROR: generated gate failed validation: {exc}", file=sys.stderr)
        return 2

    out_path = quick_dir / "quick_market_gate.json"
    out_path.write_text(json.dumps(gate, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nGate result: {gate.get('gate_result', '?').upper()}")
    print(f"Gate reason: {gate.get('reason', 'N/A')}")
    print(f"Output: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
