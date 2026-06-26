"""Initialize workflow_state.json from Stage 1 intent or progress.json.

Generates a contract-compliant workflow_state.json for a new run directory.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_workflow_state(
    run_dir: Path,
    intent: str | None = None,
    mode: str = "targeted",
    site: str = "US",
) -> dict:
    """Generate a contract-compliant workflow_state.json."""
    run_id = run_dir.name
    progress_path = run_dir / "progress.json"

    if progress_path.is_file():
        progress = json.loads(progress_path.read_text(encoding="utf-8"))
        intent = intent or progress.get("context_brief", "")
        pending = progress.get("pending_questions", [])
    else:
        pending = []

    if not intent:
        raise ValueError(
            "intent is required — provide --intent or ensure progress.json exists with context_brief"
        )

    workflow_state = {
        "workflow_id": run_id,
        "mode": mode,
        "stage": "market_quick_check",
        "initial_intent": intent,
        "site": site,
        "known_inputs": {
            "site": site,
            "intent": intent,
            "mode": mode,
        },
        "missing_inputs": pending,
        "next_actions": [
            {
                "stage": "market_quick_check",
                "recommended_action": {
                    "action": "run_dual_quick_agents",
                    "description": "启动卖家精灵 Quick Agent 和 Sorftime Quick Agent 并行快验",
                    "input_required": False,
                },
            }
        ],
        "evidence_refs": [],
        "decision_log": [
            {
                "decision_id": f"{run_id}_stage1_intent",
                "stage": "intent_collection",
                "actor": "operator",
                "decision": f"确认方向: {intent}",
                "decided_at": _now_iso(),
            }
        ],
    }
    return workflow_state
