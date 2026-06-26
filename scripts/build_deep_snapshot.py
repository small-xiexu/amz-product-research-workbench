#!/usr/bin/env python3
"""Fill deep snapshot contract from Agent's raw MCP tool calls/results.

Usage:
  python3 scripts/build_deep_snapshot.py <agent_mcp_dump.json> --source sellersprite|sorftime [--run-id <id>] [--out <path>]

The script reads the Agent's free-form MCP tool call log, fills the 15-field
deep snapshot contract (P4 schema), and writes to the output path.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

P4_SCHEMA_VERSION = "p4-deep-contract-v1"
SOURCE_NAMES = {"sellersprite", "sorftime"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _as_list(value: object) -> list:
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return list(value.values())
    return []


def build_deep_snapshot(
    agent_dump: dict,
    source_name: str,
    run_id: str | None = None,
    route_refs: list[str] | None = None,
) -> dict:
    """Build a contract-compliant deep snapshot from agent's raw MCP dump."""
    now = _now_iso()

    # --- tool_calls ---
    raw_calls = _as_list(agent_dump.get("tool_calls") or agent_dump.get("calls") or [])
    tool_calls = []
    for i, call in enumerate(raw_calls):
        if not isinstance(call, dict):
            continue
        tool_calls.append({
            "call_id": call.get("call_id") or call.get("id") or f"call_{i:03d}",
            "tool_name": call.get("tool_name") or call.get("tool") or "unknown",
            "params": call.get("params") or call.get("arguments") or {},
            "status": call.get("status") or "success",
            "started_at": call.get("started_at") or call.get("timestamp") or now,
            "finished_at": call.get("finished_at") or call.get("timestamp") or now,
        })

    # --- tool_results ---
    raw_results = _as_list(agent_dump.get("tool_results") or agent_dump.get("results") or [])
    tool_results = []
    for i, result in enumerate(raw_results):
        if not isinstance(result, dict):
            continue
        entry = {
            "result_id": result.get("result_id") or result.get("id") or f"result_{i:03d}",
            "call_id": result.get("call_id") or result.get("ref") or f"call_{i:03d}",
            "tool_name": result.get("tool_name") or result.get("tool") or "unknown",
            "status": result.get("status") or "success",
        }
        # Pick the richest data carrier
        for key in ("raw_result", "data", "result", "response"):
            if key in result:
                entry["raw_result"] = result[key]
                break
        if "raw_result" not in entry and "error" in result:
            entry["raw_result"] = {"error": result["error"]}
        if "raw_result" not in entry:
            entry["raw_result_ref"] = f"mcp_snapshots/{source_name}_deep_snapshot.json#tool_results[{i}]"
        tool_results.append(entry)

    # --- data_gaps ---
    data_gaps = _as_list(agent_dump.get("data_gaps") or [])

    # --- errors ---
    errors = _as_list(agent_dump.get("errors") or [])
    for r in tool_results:
        if r.get("status") == "error":
            errors.append({"call_id": r.get("call_id"), "detail": r.get("raw_result", {})})

    # --- source_doc_refs ---
    source_doc_refs = _as_list(agent_dump.get("source_doc_refs") or agent_dump.get("source_refs") or [])
    if not source_doc_refs:
        source_doc_refs = [f"mcp_snapshots/{source_name}_deep_snapshot.json"]

    # --- route_refs ---
    if route_refs is None:
        route_refs = _as_list(agent_dump.get("route_refs") or agent_dump.get("selected_routes") or [])
    if not route_refs:
        route_refs = ["<primary_route>"]

    # --- selected_routes ---
    selected_routes = _as_list(agent_dump.get("selected_routes") or route_refs)

    snapshot_id = f"{source_name}_deep_snapshot"

    return {
        "schema_version": P4_SCHEMA_VERSION,
        "snapshot_id": snapshot_id,
        "run_id": run_id or agent_dump.get("run_id") or "unknown",
        "source_name": source_name,
        "source_doc_refs": [str(r) for r in source_doc_refs],
        "route_refs": [str(r) for r in route_refs],
        "selected_routes": [str(r) for r in selected_routes],
        "tool_calls": tool_calls,
        "tool_results": tool_results,
        "errors": [e if isinstance(e, dict) else {"detail": str(e)} for e in errors],
        "data_gaps": [g if isinstance(g, dict) else {"description": str(g)} for g in data_gaps],
        "created_at": now,
        "retry_policy": {
            "max_retries": 0,
            "retry_strategy": "manual",
            "force_refresh_allowed": False,
        },
        "force_refresh": False,
        "input_lineage": {
            "derived_from": agent_dump.get("source_file") or "agent_mcp_dump",
            "filled_by": "build_deep_snapshot.py",
            "filled_at": now,
        },
    }


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

    missing = [k for k in [
        "schema_version", "snapshot_id", "run_id", "source_name", "source_doc_refs",
        "route_refs", "selected_routes", "tool_calls", "tool_results", "errors",
        "data_gaps", "created_at", "retry_policy", "force_refresh", "input_lineage",
    ] if k not in agent_dump]
    print(f"Filled {len(missing)} missing snapshot fields. Tool calls: {len(snapshot['tool_calls'])}, Results: {len(snapshot['tool_results'])}")
    print(f"Output: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
