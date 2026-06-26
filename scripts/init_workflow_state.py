#!/usr/bin/env python3
"""Initialize workflow_state.json from Stage 1 intent or progress.json.

Usage:
  python3 scripts/init_workflow_state.py <run_dir> [--intent "目标品类方向描述"] [--mode exploration|targeted] [--site US]

If progress.json exists in run_dir, the script derives fields from it.
Otherwise, --intent is required and serves as the initial_intent.
"""

from __future__ import annotations

import argparse
import json
import sys
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

    # Try to derive from progress.json
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Initialize workflow_state.json.")
    parser.add_argument("run_dir", type=Path, help="Run directory (e.g. runs/20260625_sample)")
    parser.add_argument("--intent", type=str, default=None, help="目标品类方向描述")
    parser.add_argument("--mode", choices=["exploration", "targeted"], default="targeted")
    parser.add_argument("--site", default="US", help="目标站点 (default: US)")
    args = parser.parse_args(argv)

    run_dir: Path = args.run_dir.expanduser().resolve()
    if not run_dir.is_dir():
        print(f"ERROR: run_dir not found: {run_dir}", file=sys.stderr)
        return 2

    try:
        workflow_state = init_workflow_state(run_dir, args.intent, args.mode, args.site)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    out_path = run_dir / "workflow_state.json"
    out_path.write_text(json.dumps(workflow_state, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Created: {out_path}")
    print(f"  workflow_id: {workflow_state['workflow_id']}")
    print(f"  mode: {workflow_state['mode']}")
    print(f"  initial_intent: {workflow_state['initial_intent']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
