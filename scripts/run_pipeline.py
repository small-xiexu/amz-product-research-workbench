#!/usr/bin/env python3
"""End-to-end pipeline orchestrator for Stages 1-4.

Usage:
  python3 scripts/run_pipeline.py <run_dir> --intent "目标品类方向" [--mode targeted|exploration] [--site US]

Stages executed:
  1. init_workflow_state.py  — 生成 workflow_state.json
  2. (Quick Agents run via Claude Code — manual step)
  3. fill_quick_packet_contract.py x2  — 补齐契约字段
  4. build_quick_market_gate.py  — 生成门控
  5. build_mcp_candidate_pool.py  — 生成候选池

If Quick Agents haven't run yet, the script stops after Stage 1 with instructions.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent

STAGES = [
    {
        "name": "Stage 1 — workflow_state.json",
        "script": "init_workflow_state.py",
        "args": lambda run_dir, intent, mode, site: [
            str(run_dir), "--intent", intent, "--mode", mode, "--site", site,
        ],
        "output": "workflow_state.json",
    },
    {
        "name": "Quick Agents (manual)",
        "skip": True,
        "note": "在 Claude Code 中 spawn 卖家精灵 Quick Agent 和 Sorftime Quick Agent，"
               "分别输出到 quick_check/sellersprite_quick_evidence_packet.json 和 "
               "quick_check/sorftime_quick_evidence_packet.json",
    },
    {
        "name": "Stage 3 — fill sellersprite packet contract",
        "script": "fill_quick_packet_contract.py",
        "args": lambda run_dir, *_a: [
            str(run_dir / "quick_check" / "sellersprite_quick_evidence_packet.json"),
            "--source", "sellersprite",
        ],
        "output": "quick_check/sellersprite_quick_evidence_packet.json",
    },
    {
        "name": "Stage 3 — fill sorftime packet contract",
        "script": "fill_quick_packet_contract.py",
        "args": lambda run_dir, *_a: [
            str(run_dir / "quick_check" / "sorftime_quick_evidence_packet.json"),
            "--source", "sorftime",
        ],
        "output": "quick_check/sorftime_quick_evidence_packet.json",
    },
    {
        "name": "Stage 3 — build quick market gate",
        "script": "build_quick_market_gate.py",
        "args": lambda run_dir, *_a: [str(run_dir)],
        "output": "quick_check/quick_market_gate.json",
    },
    {
        "name": "Stage 4 — build candidate pool",
        "script": "build_mcp_candidate_pool.py",
        "args": lambda run_dir, *_a: [str(run_dir)],
        "output": "candidate_pool.json",
    },
]


def run_stage(script_name: str, args: list[str], run_dir: Path, stage_name: str) -> int:
    script_path = SCRIPTS_DIR / script_name
    if not script_path.is_file():
        print(f"  [SKIP] script not found: {script_path}")
        return 0
    cmd = [sys.executable, str(script_path)] + args
    print(f"  Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(run_dir.parent), capture_output=False)
    return result.returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run pipeline stages 1-4.")
    parser.add_argument("run_dir", type=Path, help="Run directory (e.g. runs/20260625_sample)")
    parser.add_argument("--intent", required=True, help="目标品类方向描述")
    parser.add_argument("--mode", choices=["exploration", "targeted"], default="targeted")
    parser.add_argument("--site", default="US")
    parser.add_argument("--from-stage", type=int, default=1, help="Start from this stage (1-5)")
    args = parser.parse_args(argv)

    run_dir: Path = args.run_dir.expanduser().resolve()
    run_dir.mkdir(parents=True, exist_ok=True)

    intent: str = args.intent
    mode: str = args.mode
    site: str = args.site

    failed = False
    for i, stage in enumerate(STAGES, start=1):
        if i < args.from_stage:
            continue
        if stage.get("skip"):
            print(f"\n[{stage['name']}]")
            print(f"  {stage['note']}")
            continue

        print(f"\n[{stage['name']}]")
        output_path = run_dir / stage["output"] if stage.get("output") else None
        if output_path and output_path.exists():
            print(f"  [SKIP] {stage['output']} already exists")
            continue

        stage_args = stage["args"](run_dir, intent, mode, site)
        rc = run_stage(stage["script"], stage_args, run_dir, stage["name"])
        if rc != 0:
            print(f"  [FAIL] exit code {rc}")
            failed = True
            break

    if failed:
        print(f"\nPipeline stopped. Fix the error above and re-run with --from-stage.")
        return 1
    print(f"\nPipeline complete. Next: review candidate_pool.json with operator.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
