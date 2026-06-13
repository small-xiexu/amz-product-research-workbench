"""候选池预审渲染包。"""

from __future__ import annotations

import json
from pathlib import Path

from packages.report_renderer.candidate_pool.markdown import render_markdown, render_summary
from packages.report_renderer.candidate_pool.dashboard import render_dashboard
from packages.report_renderer.candidate_pool.workbook import render_data_workbook

__all__ = [
    "build_outputs",
    "render_markdown",
    "render_summary",
    "render_dashboard",
    "render_data_workbook",
]


def build_outputs(input_path: str, output_dir: str) -> None:
    candidate_pool = json.loads(Path(input_path).read_text(encoding="utf-8"))
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "candidate_pool.json").write_text(
        json.dumps(candidate_pool, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (out / "precheck_report.md").write_text(render_markdown(candidate_pool), encoding="utf-8")
    (out / "precheck_summary.md").write_text(render_summary(candidate_pool), encoding="utf-8")
    (out / "precheck_dashboard.html").write_text(render_dashboard(candidate_pool), encoding="utf-8")
    render_data_workbook(candidate_pool, out / "precheck_data.xlsx")
