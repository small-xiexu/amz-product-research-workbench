# render_report.py 拆分计划

更新日期：2026-06-13

`packages/report_renderer/render_report.py` 当前约 3278 行，混了 4 类职责（CSS 样式、HTML 看板、Markdown 报告、Excel 底表）。本计划把它按职责拆成一个包，纯移动不改逻辑，对外符号零变更。

## 不可破坏的对外契约

以下符号必须始终能从 `packages.report_renderer.render_report` 导入（靠 re-export 兜底）：

- `render_markdown`、`render_summary`、`render_dashboard`、`render_data_workbook`
- `build_outputs`
- `FORMAL_REPORT_SECTION_TITLES`
- `_write_xlsx`（被 4 个脚本和 render_candidate_pool 复用）

调用方：`tests/test_regression.py`、`scripts/build_mock_report.py`、`scripts/build_profit_template.py`、`scripts/build_ip_compliance_template.py`、`scripts/build_review_voc_from_plugin_export.py`、`packages/report_renderer/render_candidate_pool.py`、`packages/research_core/workflows/product_research_workflow.py`。

## 目标结构

```
packages/report_renderer/
├─ __init__.py
├─ render_report.py     # 薄门面：re-export + build_outputs
├─ constants.py         # FORMAL_REPORT_SECTION_TITLES、REPORT_EXCEL_SHEET_MAP
├─ formatting.py        # 无状态工具：_format_money/_format_number/_site_currency_code/_safe_float/_median ...
├─ markdown/            # render_markdown / render_summary + _*_markdown_lines
├─ dashboard/           # render_dashboard + style.py(CSS) + _dashboard_*
└─ workbook/            # render_data_workbook + _build_workbook_sheets + _*_rows
```

## 每批验收命令

```bash
python3 -m compileall -q packages scripts tests
python3 -m unittest discover -v
python3 scripts/run_research_workflow.py 卖家精灵导出_刮窗器_20260608 /tmp/refactor_check --site US --task-name 重构验证
python3 scripts/validate_research_outputs.py /tmp/refactor_check
git diff --check
```

## 批次台账

- [x] R1 抽离 `DASHBOARD_STYLE` CSS → `dashboard/style.py`
  - 状态：已完成
  - 产物：`packages/report_renderer/dashboard/__init__.py`、`dashboard/style.py`（579 行 CSS）
  - 改动：`render_report.py` 3278 → 2701 行，CSS 块替换为 `from ...dashboard.style import DASHBOARD_STYLE`
  - 验收：`compileall` 通过；`unittest discover` 22 项全通过；`build_mock_report` 生成的 `dashboard.html` 仍正确注入 CSS（`--panel-soft` 命中 4 处）；`git diff --check` 干净
- [x] R2 抽离共享工具 → `formatting.py`，常量 → `constants.py`
  - 状态：已完成
  - 产物：`formatting.py`（19 个无状态格式化函数，227 行）、`constants.py`（`FORMAL_REPORT_SECTION_TITLES`、`REPORT_EXCEL_SHEET_MAP`，29 行）
  - 改动：`render_report.py` 2701 → 2519 行，顶部从 `constants`/`formatting` 回引；`FORMAL_REPORT_SECTION_TITLES` 仍可从 `render_report` 导入（向后兼容）
  - 修复：`formatting.py` 补 `import json`（`_format_evidence_refs` 依赖）
  - 验收：`compileall` 通过；`unittest` 22 项全通过；刮窗器真实样例完整流程跑通并通过 `validate_research_outputs.py`；`git diff --check` 干净
  - 注：用 AST 调用图确认 19 个函数为完全闭合叶子集，无回调主逻辑，无循环引用
- [x] R3 抽离 Excel `_*_rows` → `workbook/`
  - 状态：已完成（落为单模块 `workbook.py`，与 formatting/constants 风格一致）
  - 产物：`workbook.py`（765 行：全部 `_*_rows` + `render_data_workbook` + `_build_workbook_sheets` + `_write_xlsx` + `_first_finding_name`）
  - 改动：`render_report.py` 2519 → 1853 行；仅回引 `render_data_workbook`、`_write_xlsx`（对外 re-export），说明 Excel 层与报告/看板层近乎零耦合
  - 验收：`compileall` 通过；`unittest` 22 项全通过；刮窗器真实样例完整流程跑通并通过 `validate_research_outputs.py`；`git diff --check` 干净
  - 注：AST 闭包分析确认仅 `_first_finding_name` 被拖入且不被闭包外调用，无循环引用
- [ ] R4 抽离 `_*_markdown_lines` → `markdown/`
  - 状态：待开始
- [x] R5 抽离 `_dashboard_*` → `dashboard/`，`render_report.py` 收敛为薄门面
  - 状态：已完成
  - 产物：`dashboard/sections.py`（991 行：`render_dashboard` + 全部 `_dashboard_*` / `_render_competitor_*` / `_render_info_card*` / `_render_risk_card` 等）；`dashboard/__init__.py` 暴露 `render_dashboard`
  - 改动：`render_report.py` 1170 → 53 行薄门面，仅保留 `build_outputs` + 对外 re-export（`render_markdown`/`render_summary`/`render_dashboard`/`render_data_workbook`/`FORMAL_REPORT_SECTION_TITLES`/`_write_xlsx`）
  - 验收：`compileall` 通过；`unittest` 22 项全通过；牵引绳 + 刮窗器两组真实样例（含评论 VOC）完整流程跑通并通过 `validate_research_outputs.py`（12 章结构完整）；看板 CSS 注入正常；`git diff --check` 干净

## 收尾总结

`render_report.py`：**3278 行 → 53 行薄门面**。按职责拆为 6 个模块：

| 模块 | 行数 | 职责 |
|---|---|---|
| `render_report.py` | 53 | 薄门面：`build_outputs` + 向后兼容 re-export |
| `constants.py` | 29 | 报告共享常量 |
| `formatting.py` | 228 | 19 个无状态格式化工具 |
| `markdown.py` | 772 | Markdown 正式报告（12 章） |
| `dashboard/style.py` | 579 | 看板 CSS |
| `dashboard/sections.py` | 991 | 看板分区渲染 |
| `workbook.py` | 765 | Excel 数据底表 |

- 全程纯移动不改逻辑；调用方与测试零改动（靠 re-export 兜底）。
- 每批用 AST 调用图确认闭包边界，无循环引用。
- 所有验收命令全过；两组真实样例正式交付校验通过。
- 后续可继续：`dashboard/sections.py`（991 行）按 5 个看板分区再拆；`markdown.py`/`workbook.py` 按章节进一步细分。

