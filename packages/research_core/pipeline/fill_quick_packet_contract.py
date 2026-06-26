"""Fill missing contract fields in Agent-generated quick evidence packets.

Reads the Agent's free-form JSON, auto-derives contract fields, and returns
a contract-compliant packet.
"""

from __future__ import annotations

from datetime import datetime, timezone

SCHEMA_VERSION = "evidence-packet-v1"
CONFIDENCE_LEVELS = {"high", "medium", "low"}
SUPPORT_LEVELS = {"strong", "moderate", "weak", "negative"}
MIXED_POOL_LEVELS = {"none", "mild", "material", "blocking"}
DEMAND_SIGNAL_LEVELS = {"strong", "moderate", "weak", "unknown"}
PRICE_BAND_HEALTH = {"strong", "moderate", "weak", "blocking", "unknown"}
CATEGORY_BOUNDARY_CLARITY = {"clear", "moderate", "weak", "blocking", "unknown"}

SOURCE_META = {
    "sellersprite": {
        "packet_id": "sellersprite_quick_evidence_packet",
        "source_type": "sellersprite_mcp",
        "snapshot_file": "sellersprite_quick_snapshot.json",
    },
    "sorftime": {
        "packet_id": "sorftime_quick_evidence_packet",
        "source_type": "sorftime_mcp",
        "snapshot_file": "sorftime_quick_snapshot.json",
    },
}


def _coerce_enum(value: str, allowed: set[str], fallback: str) -> str:
    return value if value in allowed else fallback


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def fill_contract(agent_output: dict, source: str, snapshot_dir: str | None = None) -> dict:
    """Fill contract fields from agent output, preserving all agent content."""
    meta = SOURCE_META[source]
    packet = dict(agent_output)

    # --- fixed contract fields ---
    packet.setdefault("schema_version", SCHEMA_VERSION)
    packet["packet_id"] = meta["packet_id"]
    packet["stage"] = "market_quick_check"
    packet["depth"] = "quick"
    packet["source_type"] = meta["source_type"]

    # --- confidence ---
    confidence = _coerce_enum(str(packet.get("confidence", "")).lower(), CONFIDENCE_LEVELS, "medium")
    packet["confidence"] = confidence

    # --- support_level ---
    support = _coerce_enum(str(packet.get("support_level", "")).lower(), SUPPORT_LEVELS, "weak")
    packet["support_level"] = support

    # --- mixed_pool_level ---
    mixed = _coerce_enum(str(packet.get("mixed_pool_level", "")).lower(), MIXED_POOL_LEVELS, "none")
    packet["mixed_pool_level"] = mixed

    # --- demand_signal_level ---
    demand = _coerce_enum(str(packet.get("demand_signal_level", "")).lower(), DEMAND_SIGNAL_LEVELS, "unknown")
    packet["demand_signal_level"] = demand

    # --- price_band_health ---
    _price_health_map = {"healthy": "strong", "watch": "moderate", "good": "strong", "poor": "weak"}
    raw_ph = str(packet.get("price_band_health", "")).lower().strip()
    raw_ph = _price_health_map.get(raw_ph, raw_ph)
    price_health = _coerce_enum(raw_ph, PRICE_BAND_HEALTH, "unknown")
    packet["price_band_health"] = price_health

    # --- category_boundary_clarity ---
    _boundary_map = {"partial": "moderate", "fuzzy": "unknown", "mixed": "weak", "unclear": "weak"}
    raw_boundary = str(packet.get("category_boundary_clarity", "")).lower().strip()
    raw_boundary = _boundary_map.get(raw_boundary, raw_boundary)
    boundary = _coerce_enum(raw_boundary, CATEGORY_BOUNDARY_CLARITY, "unknown")
    packet["category_boundary_clarity"] = boundary

    # --- blocking_gaps ---
    if "blocking_gaps" not in packet or not isinstance(packet["blocking_gaps"], list):
        packet["blocking_gaps"] = []

    # --- facts ---
    facts = packet.get("facts", [])
    if not isinstance(facts, list):
        facts = []
    packet["facts"] = facts

    # --- data_gaps ---
    gaps = packet.get("data_gaps", [])
    if not isinstance(gaps, list):
        gaps = []
    packet["data_gaps"] = gaps

    # --- metric_basis ---
    metric_basis = packet.get("metric_basis", {})
    if not isinstance(metric_basis, dict):
        metric_basis = {}
    metric_basis["marketplace"] = metric_basis.get("marketplace") or packet.get("marketplace") or "US"
    metric_basis["currency"] = metric_basis.get("currency") or "USD"
    metric_basis["data_window"] = metric_basis.get("data_window") or "30d"
    metric_basis["aggregation_unit"] = metric_basis.get("aggregation_unit") or meta.get("aggregation_unit") or "category"
    metric_basis["sample_scope"] = metric_basis.get("sample_scope") or "Top100"
    metric_basis["collected_at"] = metric_basis.get("collected_at") or _now_iso()
    packet["metric_basis"] = metric_basis

    # --- evidence_refs ---
    evidence_refs = packet.get("evidence_refs", [])
    if not isinstance(evidence_refs, list):
        evidence_refs = []
    if snapshot_dir:
        evidence_refs.append(f"mcp_snapshots/{meta['snapshot_file']}#tool_calls")
        for i, ref in enumerate(evidence_refs):
            if "#" not in str(ref):
                evidence_refs[i] = f"mcp_snapshots/{meta['snapshot_file']}#{ref}"
    else:
        evidence_refs.append(f"mcp_snapshots/{meta['snapshot_file']}#tool_calls")
    packet["evidence_refs"] = evidence_refs

    # --- execution_provenance ---
    provenance = packet.get("execution_provenance", {})
    if not isinstance(provenance, dict):
        provenance = {}
    provenance.setdefault("execution_mode", "real_subagent_spawn")
    provenance.setdefault("agent_role", f"{source} Quick Agent")
    provenance.setdefault("filled_by_script", "fill_quick_packet_contract.py")
    provenance.setdefault("filled_at", _now_iso())
    packet["execution_provenance"] = provenance

    # --- candidate_seeds ---
    seeds = packet.get("candidate_seeds", [])
    if not isinstance(seeds, list):
        seeds = []
    packet.setdefault("candidate_seeds", seeds)
    if len(seeds) == 0:
        facts = packet.get("facts", [])
        if not isinstance(facts, list):
            facts = []
        packet["facts"] = facts
        packet["_candidate_seeds_empty"] = True

    return packet
