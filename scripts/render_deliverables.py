#!/usr/bin/env python3
"""Render and validate formal research deliverables from a research package."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.report_renderer.dashboard import render_dashboard
from packages.report_renderer.html_report import render_report_html
from packages.report_renderer.markdown import render_markdown, render_summary
from packages.report_renderer.workbook import render_data_workbook
from packages.research_core.pipeline.validate_research_outputs import (
    ValidationResult,
    render_result,
    validate_workflow_output,
)


MODES = ("all", "report", "html", "dashboard", "xlsx", "validate")


def render_deliverables(
    research_package_path: str | Path,
    output_dir: str | Path,
    mode: str = "all",
    validate: bool = True,
) -> ValidationResult | None:
    if mode not in MODES:
        raise ValueError(f"unsupported render mode: {mode}")
    out = Path(output_dir).expanduser().resolve()

    if mode == "validate":
        return validate_workflow_output(out)

    package = _load_research_package(Path(research_package_path).expanduser().resolve())
    out.mkdir(parents=True, exist_ok=True)

    if mode == "all":
        _write_research_package_copy(package, out)
        _write_report_markdown(package, out)
        _write_report_html(package, out)
        _write_dashboard(package, out)
        _write_workbook(package, out)
        _write_summary(package, out)
        return validate_workflow_output(out) if validate else None
    if mode == "report":
        _write_report_markdown(package, out)
    elif mode == "html":
        _write_report_html(package, out)
    elif mode == "dashboard":
        _write_dashboard(package, out)
    elif mode == "xlsx":
        _write_workbook(package, out)
    return None


def _load_research_package(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("research_package.json root must be an object")
    return data


def _write_research_package_copy(package: dict[str, Any], output_dir: Path) -> None:
    (output_dir / "research_package.json").write_text(
        json.dumps(package, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _write_report_markdown(package: dict[str, Any], output_dir: Path) -> None:
    (output_dir / "report.md").write_text(render_markdown(package), encoding="utf-8")


def _write_report_html(package: dict[str, Any], output_dir: Path) -> None:
    (output_dir / "report.html").write_text(render_report_html(package), encoding="utf-8")


def _write_dashboard(package: dict[str, Any], output_dir: Path) -> None:
    (output_dir / "dashboard.html").write_text(render_dashboard(package), encoding="utf-8")


def _write_workbook(package: dict[str, Any], output_dir: Path) -> None:
    render_data_workbook(package, output_dir / "data.xlsx")


def _write_summary(package: dict[str, Any], output_dir: Path) -> None:
    (output_dir / "summary.md").write_text(render_summary(package), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render formal report deliverables from research_package.json.")
    parser.add_argument("research_package_json", help="Path to research_package.json.")
    parser.add_argument("output_dir", help="Output directory. Usually the workflow final_report directory.")
    parser.add_argument("--mode", choices=MODES, default="all", help="Render mode. Default: all.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = render_deliverables(args.research_package_json, args.output_dir, args.mode)
    if result is not None:
        print(render_result(result), end="")
        return 0 if result.ok else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
