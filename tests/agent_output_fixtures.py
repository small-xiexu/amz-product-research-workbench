"""Test-only helpers that simulate main-Agent-authored pipeline artifacts.

Production P2/P3 scripts validate Agent outputs; they do not generate business
judgment artifacts. Tests use these helpers to write deterministic stand-ins
before exercising the validators and downstream stages.
"""

from __future__ import annotations

import json
from pathlib import Path

from packages.research_core.pipeline._utils import load_json
from packages.research_core.pipeline.build_mcp_candidate_pool import (
    SOURCE_CONFIG,
    build_candidate_pool,
    _load_quick_gate,
    _load_quick_packet,
)
from packages.research_core.pipeline.build_route_matrix_confirmation import (
    build_route_matrix_confirm,
)


def write_agent_candidate_pool(run_dir: Path) -> Path:
    """Write a deterministic candidate_pool.json as if authored by the main Agent."""
    workflow_state = load_json(run_dir / "workflow_state.json")
    packets = {
        source_name: _load_quick_packet(run_dir, source_name)
        for source_name in SOURCE_CONFIG
    }
    gate = _load_quick_gate(run_dir)
    candidate_pool = build_candidate_pool(workflow_state, packets, gate, run_dir)
    candidate_pool.setdefault("generation_provenance", {})
    candidate_pool["generation_provenance"].update(
        {
            "execution_mode": "agent_fixture",
            "agent_role": "Main Agent",
            "build_strategy": "agent_generated_test_fixture",
        }
    )
    output_path = run_dir / "candidate_pool.json"
    output_path.write_text(
        json.dumps(candidate_pool, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return output_path


def write_agent_route_matrix(run_dir: Path) -> Path:
    """Write a deterministic route_matrix_confirm.json as if authored by the main Agent."""
    route_matrix = build_route_matrix_confirm(run_dir)
    route_matrix.setdefault("generation_provenance", {})
    route_matrix["generation_provenance"].update(
        {
            "execution_mode": "agent_fixture",
            "agent_role": "Main Agent",
            "build_strategy": "agent_generated_test_fixture",
        }
    )
    output_path = run_dir / "route_matrix_confirm.json"
    output_path.write_text(
        json.dumps(route_matrix, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return output_path
