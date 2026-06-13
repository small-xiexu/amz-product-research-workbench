# 架构优化计划（依赖倒置修复 + 候选池渲染拆分）

更新日期：2026-06-13

承接 `render_report拆分计划.md`。本轮修两个已验证的结构性问题。

## 问题清单

### A. Workflow 反向依赖 scripts（依赖倒置）
`packages/research_core/workflows/product_research_workflow.py` 与 `tests/` 直接
`from scripts.X import ...`，业务逻辑住在入口层 `scripts/`，被上层反向 import。
违反"CLI 薄壳"原则，且挡住网页/API 演进。

涉及 9 个模块：`apply_ip_compliance_review`、`apply_profit_review`、
`build_candidate_pool_from_import_manifest`、`build_ip_compliance_template`、
`build_profit_template`、`build_research_package_from_candidate`、
`build_review_voc_from_plugin_export`、`inspect_manual_exports`、
`validate_research_outputs`。

修法：业务逻辑下沉到 `packages/research_core/pipeline/`，`scripts/<name>.py` 退化为
薄壳（`from packages.research_core.pipeline.<name> import main`）；Workflow / tests
改依赖 `pipeline`，不再依赖 `scripts`。

### B. `render_candidate_pool.py`（1375 行）是"下一个 render_report"
未复用新拆出的 `formatting.py`，自造格式化函数；从 `render_report._write_xlsx`
取（依赖门面而非真身）。

修法：复用 `formatting`/`constants`/`workbook`，并按 R1–R5 方法论按需拆分。

## 不可破坏的对外契约
- `python3 scripts/<name>.py ...` 全部 CLI 入口保持可用
- 既有调用方零行为变化；两组真实样例交付校验通过

## 验收命令
```bash
python3 -m compileall -q packages scripts tests
python3 -m unittest discover -v
python3 scripts/run_research_workflow.py 卖家精灵导出_刮窗器_20260608 /tmp/arch_check --site US --task-name 架构验证
python3 scripts/validate_research_outputs.py /tmp/arch_check
git diff --check
```

## 批次台账

- [x] A1 新建 `pipeline/` 包，下沉 9 个业务模块
  - 状态：已完成
  - 产物：`packages/research_core/pipeline/`（9 个业务模块 + `__init__.py`），去掉了 `sys.path` 引导块
- [x] A2 scripts 改薄壳，Workflow / tests 改依赖 pipeline
  - 状态：已完成
  - 改动：9 个 `scripts/<name>.py` 退化为薄壳（`from packages.research_core.pipeline.<name> import main`）；`product_research_workflow.py` 与 `tests/test_regression.py` 的 `from scripts.X` 全部改为 `from packages.research_core.pipeline.X`；`grep from scripts packages tests` 已无残留
- [x] A3 全量回归 + 两组真实样例校验
  - 状态：已完成
  - 验收：`compileall` 通过；`unittest` 22 项全通过；CLI 薄壳 `--help` / `inspect_manual_exports` 实跑正常；牵引绳 + 刮窗器两组真实样例（含 VOC）完整流程跑通并通过 `validate_research_outputs.py`（12 章完整）；`git diff --check` 干净
- [x] B1 `render_candidate_pool.py` 复用 formatting/constants/workbook
  - 状态：已完成
  - 改动：`_write_xlsx` 改从 `packages.report_renderer.workbook` 导入（不再依赖 render_report 门面）；本地与 `formatting._display_value` 字节级一致的 `_display_value` 已删除并复用 formatting；`_number` / `_percent` / `_format_precheck_generated_at` 为候选池特有行为（None→“待补/待填”），保留本地
- [x] B2 `render_candidate_pool.py` 按职责拆分
  - 状态：已完成
  - 产物：`candidate_pool/` 包 = `shared.py`(235) + `markdown.py`(194) + `dashboard.py`(704) + `workbook.py`(319) + `__init__.py`(32)；`render_candidate_pool.py` 收敛为 19 行薄门面
  - 验收：AST 闭包分析归类（shared 12 / md 8 / db 12 / wb 12）；预审产物 **逐字节比对一致**（report.md / summary.md / dashboard.html / candidate_pool.json 完全一致，Excel sheets 一致且 0 单元格差异）；`compileall` + `unittest` 22 项全通过；候选池已无对 `render_report` 的依赖；`git diff --check` 干净

## 收尾总结

本轮修复两个结构性问题：

1. **依赖倒置（A）**：9 个业务模块从 `scripts/` 下沉到 `packages/research_core/pipeline/`，`scripts/` 退化为薄壳 CLI；Workflow / tests 改依赖 `pipeline`，彻底消除"上层反向 import 入口层"。为后续网页/API 复用业务逻辑扫清障碍。
2. **候选池巨型文件（B）**：`render_candidate_pool.py` 1375 → 19 行薄门面，拆为 `candidate_pool/` 包；去掉对 render_report 门面的依赖和重复格式化；预审产物逐字节不变。

验证手段：AST 闭包分析保证移动闭合无环；真实样例完整回归 + 交付校验；候选池产物逐字节 diff。全程未改任何业务行为。

## 追加批次

- [x] C `market_structure_rules.py`（662 行）按职责拆分
  - 状态：已完成
  - 依据：AST 依赖图为干净 DAG 无环（`shared` 纯叶子；`tagging/quality/opportunity` 仅依赖 shared；`distribution` 依赖 shared+opportunity；entry 依赖全部）
  - 产物：`rules/market_structure/` 包 = `shared.py`(84) + `tagging.py`(223) + `quality.py`(101) + `opportunity.py`(130) + `distribution.py`(202) + `__init__.py`(129)；`market_structure_rules.py` 收敛为 6 行门面（`import *` 全量 re-export，向后兼容 42 个公开名）
  - 验收：门面导入正常；`compileall` + `unittest` 22 项全通过；用刮窗器 manifest 重建候选池，剔除时间戳字段后与基线 **逐字节一致**（计算结果完全不变）；`git diff --check` 干净

## 暂不优化（经评估后明确不做）

- **全局 dict → dataclass 类型化**：当前数据全程以裸 dict 在 6 个数据契约间流转。改造需触碰几乎所有模块（pipeline、rules、renderer、contracts），回归面极大，而 V1 骨架阶段已有 JSON Schema + 契约校验 + 22 项回归兜底，类型化的边际收益有限、风险/成本高。判定为**高成本低 ROI，暂不做**；待进入网页/API 实体化、数据结构趋稳后，再以"按数据包逐个引入 dataclass + 适配层"的方式渐进迁移，不一次性大改。

