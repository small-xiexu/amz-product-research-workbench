#!/usr/bin/env python3
"""Audit a product research run and print current stage, gaps, and next actions."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.research_core.pipeline.audit_run_status import audit_run_status


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit one runs/<run_id> directory.")
    parser.add_argument("run_dir", help="Run directory, for example runs/<run_id>.")
    parser.add_argument("--output", help="Optional JSON output path. Defaults to <run_dir>/run_status_audit.json.")
    parser.add_argument("--json", action="store_true", help="Print full JSON instead of a short summary.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run_dir = Path(args.run_dir).expanduser().resolve()
    audit = audit_run_status(run_dir)
    output = Path(args.output).expanduser().resolve() if args.output else run_dir / "audit_run_status.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if args.json:
        print(json.dumps(audit, ensure_ascii=False, indent=2))
    else:
        print(f"Run audit: {audit['summary']}")
        print(f"Wrote {output}")
        for action in audit.get("next_actions", [])[:3]:
            next_step = action.get("next_step") or action.get("reason")
            print(f"- {action.get('label')}: {next_step}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
