#!/usr/bin/env python3
"""Initialize workflow_state.json from Stage 1 intent or progress.json — CLI entry.

Usage:
  python3 scripts/init_workflow_state.py <run_dir> [--intent "目标品类方向描述"] [--mode exploration|targeted] [--site US]

Run directory naming convention: runs/YYYYMMDD_中文品类方向
Example: runs/20260625_宠物牵引绳
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.research_core.pipeline.init_workflow_state import init_workflow_state

_RUN_DIR_NAME_PATTERN = re.compile(
    r"^\d{8}_[^_]+$"
)


def _validate_run_dir_name(name: str) -> str | None:
    """Return an error message if the run directory name is invalid, else None.

    Convention: YYYYMMDD_中文品类方向
    """
    if not _RUN_DIR_NAME_PATTERN.match(name):
        return (
            f"run_dir name '{name}' 不符合命名规范。"
            f"期望格式: YYYYMMDD_中文品类方向 (如 20260625_宠物牵引绳)\n"
            f"  - 前 8 位必须是数字日期 (YYYYMMDD)\n"
            f"  - 下划线后为品类方向名称\n"
            f"  - 站点信息请用 --site 参数指定，不要写在目录名中"
        )
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Initialize workflow_state.json.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Run directory naming: runs/YYYYMMDD_中文品类方向",
    )
    parser.add_argument("run_dir", type=Path, help="Run directory (e.g. runs/20260625_宠物牵引绳)")
    parser.add_argument("--intent", type=str, default=None, help="目标品类方向描述")
    parser.add_argument("--mode", choices=["exploration", "targeted"], default="targeted")
    parser.add_argument("--site", default="US", help="目标站点 (default: US)")
    args = parser.parse_args(argv)

    run_dir: Path = args.run_dir.expanduser().resolve()
    if not run_dir.is_dir():
        print(f"ERROR: run_dir not found: {run_dir}", file=sys.stderr)
        return 2

    name_error = _validate_run_dir_name(run_dir.name)
    if name_error:
        print(f"ERROR: {name_error}", file=sys.stderr)
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
