"""候选池预审渲染门面（已拆分到 candidate_pool 子包，保留向后兼容入口）。"""

from __future__ import annotations

from packages.report_renderer.candidate_pool import (
    build_outputs,
    render_markdown,
    render_summary,
    render_dashboard,
    render_data_workbook,
)

__all__ = [
    "build_outputs",
    "render_markdown",
    "render_summary",
    "render_dashboard",
    "render_data_workbook",
]
