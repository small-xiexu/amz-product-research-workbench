"""Fill P4 evidence packet contract from Agent's free-form deep dive output.

Reads the Agent's free-form deep dive JSON, fills the P4 evidence
packet contract (required fields + evidence_items structure).
"""

from __future__ import annotations

from datetime import datetime, timezone

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

    # --- evidence_items ---
    if not packet.get("evidence_items"):
        packet["evidence_items"] = _build_evidence_items(packet, source)

    # --- derived_metrics ---
    if "derived_metrics" not in packet or not isinstance(packet.get("derived_metrics"), dict):
        packet["derived_metrics"] = {}

    # --- metric_basis ---
    metric_basis = packet.get("metric_basis", {})
    if not isinstance(metric_basis, dict):
        metric_basis = {}
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
            "input_lineage": {"filled_by": "build_deep_evidence_packet"},
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
