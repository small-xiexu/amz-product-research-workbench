"""End-to-end pipeline orchestrator for Stages 1-4.

Runs stage scripts in order with idempotency checks and --from-stage resume support.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "scripts"

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


def run_pipeline(
    run_dir: Path,
    intent: str,
    mode: str = "targeted",
    site: str = "US",
    from_stage: int = 1,
) -> int:
    """Run pipeline stages 1-4. Returns exit code (0 = success)."""
    run_dir.mkdir(parents=True, exist_ok=True)
    failed = False

    for i, stage in enumerate(STAGES, start=1):
        if i < from_stage:
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
        print("\nPipeline stopped. Fix the error above and re-run with --from-stage.")
        return 1
    print("\nPipeline complete. Next: review candidate_pool.json with operator.")
    return 0
