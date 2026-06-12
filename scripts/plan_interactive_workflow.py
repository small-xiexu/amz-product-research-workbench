#!/usr/bin/env python3
"""Create or advance an interactive product research workflow state."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.research_core.workflows import create_initial_state, workflow_state_from_dict, plan_next_action


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plan the next AI/operator action for product research.")
    parser.add_argument("output_path", help="Path to write workflow_state.json.")
    parser.add_argument("--mode", choices=["broad_discovery", "targeted_deep_dive"], default="targeted_deep_dive")
    parser.add_argument("--intent", default="", help="Operator's original product research intent.")
    parser.add_argument("--site", default="US", help="Amazon marketplace.")
    parser.add_argument("--workflow-id", default="workflow-interactive-draft", help="Stable workflow id.")
    parser.add_argument("--input-state", default="", help="Existing workflow_state.json to re-plan.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_path = Path(args.output_path).expanduser().resolve()
    if args.input_state:
        state_path = Path(args.input_state).expanduser().resolve()
        data = json.loads(state_path.read_text(encoding="utf-8"))
        state = plan_next_action(workflow_state_from_dict(data))
    else:
        if not args.intent.strip():
            raise SystemExit("--intent is required when --input-state is not provided")
        state = create_initial_state(
            workflow_id=args.workflow_id,
            mode=args.mode,
            initial_intent=args.intent,
            site=args.site,
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(state.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote workflow state: {output_path}")
    print(f"Stage: {state.stage}")
    print(f"Decision required: {state.decision_required}")
    print(f"Question: {state.operator_question}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
