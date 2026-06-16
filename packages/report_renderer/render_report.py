"""选品报告渲染门面。

历史上本模块是一个 3000+ 行的巨型文件，混合了 CSS 样式、HTML 看板、
Markdown 报告和 Excel 底表四类职责。现已按职责拆分为：

- ``packages.report_renderer.constants``：报告共享常量
- ``packages.report_renderer.formatting``：无状态格式化工具
- ``packages.report_renderer.markdown``：Markdown 正式报告（12 章）
- ``packages.report_renderer.html_report``：HTML 正式报告（12 章网页）
- ``packages.report_renderer.dashboard``：HTML 看板（``style`` + ``sections``）
- ``packages.report_renderer.workbook``：Excel 数据底表

本模块只保留 ``build_outputs`` 编排入口，并对外 re-export 既有公开符号，
保证 ``from packages.report_renderer.render_report import ...`` 的旧调用方零改动。
"""

from __future__ import annotations

import json
from pathlib import Path

# 向后兼容 re-export（调用方仍从本模块导入这些符号）
from packages.report_renderer.constants import FORMAL_REPORT_SECTION_TITLES
from packages.report_renderer.markdown import render_markdown, render_summary
from packages.report_renderer.html_report import render_report_html
from packages.report_renderer.dashboard import render_dashboard
from packages.report_renderer.workbook import _write_xlsx, render_data_workbook

__all__ = [
    "build_outputs",
    "render_markdown",
    "render_report_html",
    "render_summary",
    "render_dashboard",
    "render_data_workbook",
    "FORMAL_REPORT_SECTION_TITLES",
    "_write_xlsx",
]


def build_outputs(input_path: str, output_dir: str) -> None:
    package = json.loads(Path(input_path).read_text(encoding="utf-8"))
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "research_package.json").write_text(
        json.dumps(package, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (out / "report.md").write_text(render_markdown(package), encoding="utf-8")
    (out / "report.html").write_text(render_report_html(package), encoding="utf-8")
    (out / "summary.md").write_text(render_summary(package), encoding="utf-8")
    (out / "dashboard.html").write_text(render_dashboard(package), encoding="utf-8")
    render_data_workbook(package, out / "data.xlsx")


if __name__ == "__main__":
    raise SystemExit("Use build_outputs(input_path, output_dir) from a wrapper script.")
