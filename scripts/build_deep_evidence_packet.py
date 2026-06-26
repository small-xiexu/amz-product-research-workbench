#!/usr/bin/env python3
"""Fill P4 evidence packet contract from Agent's free-form deep dive output.

Usage:
  python3 scripts/build_deep_evidence_packet.py <agent_output.json> --source sellersprite|sorftime [--out <path>]

The script reads the Agent's free-form deep dive JSON, fills the P4 evidence
packet contract (16 required fields + evidence_items structure), and writes
to market_structure/market_structure_evidence_packet.json or
search_demand/search_demand_evidence_packet.json.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

P4_SCHEMA_VERSION = "p4-deep-contract-v1"
CONFIDENCE_LEVELS = {"high", "medium", "low"}

SOURCE_META = {
    "sellersprite": {
        "packet_id": "market_structure_evidence_packet",
        "primary_source": "sellersprite",
        "cross_check_sources": ["sorftime"],
        "snapshot_ref": "mcp_snapshots/sellersprite_deep_snapshot.json",
        "output_subdir": "market_structure",
        "output_file": "market_structure_evidence_packet.json",
    },
    "sorftime": {
        "packet_id": "search_demand_evidence_packet",
        "primary_source": "sorftime",
        "cross_check_sources": ["sellersprite"],
        "snapshot_ref": "mcp_snapshots/sorftime_deep_snapshot.json",
        "output_subdir": "search_demand",
        "output_file": "search_demand_evidence_packet.json",
    },
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _as_list(value: object) -> list:
    if isinstance(value, list):
        return value
    return []


def _first_text(*values: object) -> str:
    for v in values:
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def _coerce_enum(value: str, allowed: set[str], fallback: str) -> str:
    return value if value in allowed else fallback


def build_evidence_packet(
    agent_output: dict,
    source: str,
    run_id: str | None = None,
    route_refs: list[str] | None = None,
) -> dict:
    """Fill P4 evidence packet contract from agent free-form output."""
    meta = SOURCE_META[source]
    now = _now_iso()
    packet = dict(agent_output)

    # --- fixed contract fields ---
    packet["schema_version"] = P4_SCHEMA_VERSION
    packet["packet_id"] = meta["packet_id"]
    packet["run_id"] = run_id or packet.get("run_id") or "unknown"
    packet["primary_source"] = meta["primary_source"]
    packet["cross_check_sources"] = meta["cross_check_sources"]
    packet["source_snapshot_refs"] = [meta["snapshot_ref"]]
    packet["created_at"] = packet.get("created_at") or now

    # --- route_refs / selected_routes ---
    if route_refs is None:
        route_refs = _as_list(packet.get("route_refs") or packet.get("selected_routes") or [])
    if not route_refs:
        route_refs = ["<primary_route>"]
    packet["route_refs"] = [str(r) for r in route_refs]
    packet["selected_routes"] = [str(r) for r in route_refs]

    # --- evidence_items: wrap agent facts into evidence_items if missing ---
    if not packet.get("evidence_items"):
        packet["evidence_items"] = _build_evidence_items(packet, source)

    # --- derived_metrics ---
    if "derived_metrics" not in packet or not isinstance(packet.get("derived_metrics"), dict):
        packet["derived_metrics"] = {}

    # --- metric_basis ---
    metric_basis = packet.get("metric_basis", {})
    if not isinstance(metric_basis, dict):
        metric_basis = {}
    # Fill per-source basis entry
    basis_key = f"{source}_deep"
    if basis_key not in metric_basis:
        metric_basis[basis_key] = {
            "source_name": source,
            "tool_name": "mcp_deep_dive",
            "site": "US",
            "marketplace": "US",
            "currency": "USD",
            "time_window": "30d",
            "data_window": "30d",
            "sample_scope": "Top100",
            "metric_unit": "units",
            "aggregation_unit": "category",
            "parent_child_basis": "unknown",
            "collection_method": "mcp_agent_deep_dive",
            "collected_at": now,
            "input_lineage": {"filled_by": "build_deep_evidence_packet.py"},
        }
    packet["metric_basis"] = metric_basis

    # --- confidence ---
    packet["confidence"] = _coerce_enum(
        str(packet.get("confidence", "")).lower(), CONFIDENCE_LEVELS, "medium"
    )

    # --- gaps ---
    if "data_gaps" not in packet or not isinstance(packet.get("data_gaps"), list):
        packet["data_gaps"] = []
    if "blocking_gaps" not in packet or not isinstance(packet.get("blocking_gaps"), list):
        packet["blocking_gaps"] = []

    # --- source_refs ---
    if not packet.get("source_refs"):
        packet["source_refs"] = [
            meta["snapshot_ref"],
            f"{meta['output_subdir']}/{meta['output_file']}",
        ]

    return packet


def _build_evidence_items(packet: dict, source: str) -> list[dict]:
    """Build evidence_items from agent's free-form facts structure."""
    items: list[dict] = []
    facts = packet.get("facts", {})

    # Try to extract from reference_asin_pool (market structure agent)
    asin_pool = facts.get("reference_asin_pool") or packet.get("reference_asin_pool") or []
    for entry in _as_list(asin_pool):
        if not isinstance(entry, dict):
            continue
        asin = entry.get("asin", "")
        items.append({
            "item_type": "asin_operating_data",
            "source": source,
            "item_ref": f"reference_asin_pool::{asin}",
            "facts": {
                "raw_value": entry,
                "normalized_value": {},
            },
            "metric_basis_ref": f"{source}_deep",
            "route_refs": [str(entry.get("route_ref", "<primary_route>"))],
            "confidence": "medium",
        })

    # Try to extract from keyword_pool_by_role (search demand agent)
    keyword_pool = facts.get("keyword_pool_by_role") or packet.get("keyword_pool_by_role") or {}
    for role, keywords in (keyword_pool.items() if isinstance(keyword_pool, dict) else []):
        for kw in _as_list(keywords):
            if not isinstance(kw, dict):
                continue
            items.append({
                "item_type": "competitor_structure",
                "source": source,
                "item_ref": f"keyword_pool::{kw.get('keyword', '')}",
                "facts": {
                    "raw_value": kw,
                    "normalized_value": {},
                },
                "metric_basis_ref": f"{source}_deep",
                "route_refs": _as_list(kw.get("route_refs", [])),
                "confidence": kw.get("confidence", "medium"),
            })

    # Fallback: wrap entire facts as one evidence item
    if not items and facts:
        items.append({
            "item_type": "competitor_structure",
            "source": source,
            "item_ref": "agent_facts_full",
            "facts": {
                "raw_value": facts,
                "normalized_value": {},
            },
            "metric_basis_ref": f"{source}_deep",
            "route_refs": ["<primary_route>"],
            "confidence": "medium",
        })

    return items


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
