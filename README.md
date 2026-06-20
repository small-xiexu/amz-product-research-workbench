# AMZ Product Research Workbench

亚马逊选品全流程工作台方案。

当前方向：输入模糊选品意图，系统主动发现候选品，再逐层筛选、深挖、生成报告和看板。不是让运营先找好产品，再让系统写报告。

当前阶段先沉淀产品路线、业务流程和技术方案，不直接开发完整应用。后续按 `候选品发现 Skill + 本地报告生成器 -> 轻量网页工作台 -> 完整选品应用` 演进。

## 当前目标

- V1 采用三源融合：卖家精灵手动导出（广域候选池）+ Sorftime MCP（类目/关键词/竞品深度验证）+ 自有评论插件（VOC 证据链）。
- 主产品体验是 AI 与运营交互式推进：AI 判断当前阶段、下一步动作、是否需要运营决策；最终报告沉淀整个交互过程。
- 当前已跑通 `卖家精灵导出文件夹 -> 候选品池 -> 可选 Sorftime 深度验证 -> 可选评论 VOC -> 深挖报告`。
- 生成正式交付物：Markdown 主报告、HTML 正式报告、Excel 数据底表。
- 保留 Excel 数据底表和可追溯证据链。
- 自有评论插件已通过 Excel/HTML 文件导入方式接入重点候选深挖。

## 当前架构

| 层 | 位置 | 职责 |
|---|---|---|
| 交互式流程入口 | `scripts/plan_interactive_workflow.py` | 生成/更新 `workflow_state` 和下一步动作卡 |
| 批量回归入口 | `scripts/run_research_workflow.py` | 数据齐全后重跑完整报告，用于回归和开发验证 |
| Workflow 应用层 | `packages/research_core/workflows/` | 交互式状态推进 + 批量报告编排 |
| Contracts 契约层 | `packages/research_core/contracts/` | 在关键节点校验 `import_manifest`、`candidate_pool`、`research_package` 等数据包结构 |
| Core 规则层 | `packages/research_core/` | Adapter、统一 Schema、字段合并、市场结构等可复用规则 |
| Renderer 输出层 | `packages/report_renderer/` | 生成 Markdown、HTML 正式报告、Excel 数据底表；已按 `markdown` / `html_report` / `workbook` / `formatting` / `constants` 分模块，`render_report.py` 仅为薄门面 |
| Skills 分析层 | `skills/` | 约束 Claude 如何基于结构化数据做市场/VOC/深挖判断 |

主体验优先调用 `packages.research_core.workflows.create_initial_state()` / `plan_next_action()` / `advance_stage()` 维护交互状态；`run_research_workflow()` 保留为批量重跑和回归工具。新增第三方数据源优先落在 `packages/research_core/adapters/` 和 `merge_strategy.py`。

## 文档索引

| 文档 | 用途 |
|---|---|
| `docs/plans/V1选品系统实施计划.md` | 唯一进度台账，下次恢复任务先看这里 |
| `docs/选品系统方向锚点.md` | 项目方向主锚点，防止偏成“录入产品做报告” |
| `skills/amazon-product-research/SKILL.md` | 当前主流程入口，定义运营式调研、手动采集、多 Agent 调度和阶段推进规则 |
| `skills/market-scan/SKILL.md` | 候选发现和市场扫描 |
| `skills/candidate-deep-dive/SKILL.md` | 重点候选深挖、Sorftime 验证和正式报告生成 |
| `skills/review-voc-analysis/SKILL.md` | 评论 VOC 分析 |
| `packages/research_core/workflows/` | 交互式状态推进和批量报告编排，可被 CLI/网页/API 复用 |
| `packages/research_core/contracts/` | 核心数据包结构校验 |
| `packages/research_core/` | 统一数据结构、Adapter、状态规则 |
| `packages/report_renderer/` | Markdown、HTML 正式报告和 Excel 底表渲染 |
| `scripts/` | 本地 CLI 入口和兼容工具脚本 |
| `examples/` | 最小输入样例和 mock 数据包 |
| `requirements.txt` | 本地脚本依赖，当前主要用于读取 Excel |
| `docs/V1范围冻结.md` | 冻结第一版要做什么、不做什么、输出什么 |
| `docs/字段来源表.md` | 每个字段来自手动导出、MCP、手填、系统计算还是人工复核 |
| `docs/卖家精灵导出指令完整性规范.md` | 卖家精灵真实菜单入口、导出对象和字段要求 |
| `docs/评论VOC导出指令完整性规范.md` | 评价插件采集口径，用户侧只需要 ASIN 清单 |
| `docs/自有评论插件对接方案.md` | 自有评论插件 Excel/HTML 导出如何接入选品系统 |
| `docs/多数据源适配器架构设计.md` | 新数据源接入 Adapter 的设计边界 |
| `docs/sorftime-mcp-工具调用策略.md` | Sorftime MCP 调用时机、参数和数据写入口径 |
| `docs/架构原则.md` | 脚本、Workflow、Skill、报告层的职责边界 |
| `docs/分析模式库.md` | Claude 做市场/VOC/深挖判断时使用的分析模式 |
| `docs/亚马逊选品全流程产品路线图.md` | 产品目标、阶段规划、V0-V5 演进路线 |

## 开发校验

开发完成后运行：

```bash
scripts/dev_verify.sh
```

如果本轮有真实 run 目录，传入 run 路径，让红线扫描从本轮数据中提取 ASIN、关键词、品类和品牌 token：

```bash
scripts/dev_verify.sh runs/<run_id>
```

本仓库提供 pre-commit 配置：

```bash
pre-commit install
```

提交前会自动执行 Python 编译检查、通用硬编码红线扫描和 `git diff --check`。

## 交互式流程状态

生成第一张下一步动作卡：

```bash
python3 scripts/plan_interactive_workflow.py \
  /tmp/workflow_state.json \
  --mode targeted_deep_dive \
  --intent "窗户刮水器二合一工具" \
  --site US \
  --workflow-id window-squeegee-001
```

输出：

- `/tmp/workflow_state.json`
- 当前阶段
- 是否需要运营决策
- AI 应该问运营的问题
- 下一步动作卡

交互推进后生成最终报告时，把当前状态文件传给批量重跑入口：

```bash
python3 scripts/run_research_workflow.py \
  卖家精灵导出样例_美国站_宠物牵引绳_20260607 \
  /tmp/research_workbench_workflow \
  --site US \
  --task-name 美国站宠物牵引绳样例 \
  --workflow-state /tmp/workflow_state.json
```

最终 `report.md` 会在 12 章结构内记录交互式流程状态、下一步动作和关键决策记录；`data.xlsx` 会新增 `交互决策记录` Sheet。

## 本地验证

一键完整流程用于数据齐全后的报告重跑和回归验证：

```bash
python3 scripts/run_research_workflow.py \
  卖家精灵导出样例_美国站_宠物牵引绳_20260607 \
  /tmp/research_workbench_workflow \
  --site US \
  --task-name 美国站宠物牵引绳样例 \
  --review-input /Users/sxie/Downloads/B07R56CBWX-multi-2026-06-07.xlsx \
  --review-input /Users/sxie/Downloads/B07R56CBWX-multi-2026-06-07-report.html \
  --workflow-state /tmp/workflow_state.json
```

输出：

- `/tmp/research_workbench_workflow/import_manifest.json`
- `/tmp/research_workbench_workflow/candidate_pool.json`
- `/tmp/research_workbench_workflow/review_voc/review_voc_package.json`
- `/tmp/research_workbench_workflow/research_package.json`
- `/tmp/research_workbench_workflow/final_report/report.md`
- `/tmp/research_workbench_workflow/final_report/report.html`
- `/tmp/research_workbench_workflow/final_report/data.xlsx`
- `/tmp/research_workbench_workflow/workflow_summary.md`

生成后必须运行正式交付校验：

```bash
python3 scripts/render_deliverables.py \
  /tmp/research_workbench_workflow/research_package.json \
  /tmp/research_workbench_workflow/final_report \
  --mode validate
```

校验器会检查正式报告五件套、`workflow_summary`、Excel 关键 Sheet、Top100 行数、12 章报告结构、网页版报告结构、属性/交叉分析、竞品选择逻辑、VOC 证据链和 Go/Wait/No-Go 评分卡。

如果已经有 `research_package.json`，可以用统一入口一次生成全部正式交付物并自动校验：

```bash
python3 scripts/render_deliverables.py \
  /tmp/research_workbench_workflow/research_package.json \
  /tmp/research_workbench_workflow/final_report \
  --mode all
```

`--mode` 也支持 `report`、`html`、`dashboard`、`xlsx`、`validate`，用于只重渲染某一类交付物或只跑校验。

## P20 回归样例

当前默认用两组真实样例回归正式深挖链路：

```bash
python3 scripts/run_research_workflow.py \
  卖家精灵导出样例_美国站_宠物牵引绳_20260607 \
  /tmp/amz_p20_regression_dog \
  --site US \
  --task-name P20宠物牵引绳回归 \
  --review-input 评论插件导出_免手持牵引绳_20260608/B07R56CBWX-multi-2026-06-07.xlsx \
  --review-input 评论插件导出_免手持牵引绳_20260608/B07R56CBWX-multi-2026-06-07-report.html

python3 scripts/render_deliverables.py \
  /tmp/amz_p20_regression_dog/research_package.json \
  /tmp/amz_p20_regression_dog/final_report \
  --mode validate

python3 scripts/run_research_workflow.py \
  卖家精灵导出_刮窗器_20260608 \
  /tmp/amz_p20_regression_window \
  --site US \
  --task-name P20刮窗器回归 \
  --review-input 评价导出_刮窗器_20260609/B0BKTM56C3-multi-2026-06-09.xlsx \
  --review-input 评价导出_刮窗器_20260609/B0BKTM56C3-multi-2026-06-09-report.html

python3 scripts/render_deliverables.py \
  /tmp/amz_p20_regression_window/research_package.json \
  /tmp/amz_p20_regression_window/final_report \
  --mode validate
```

只验证报告渲染器时使用最小 mock：

```bash
python3 scripts/build_mock_report.py examples/minimal_research_package.json /tmp/research_workbench_mock
```

输出：

- `/tmp/research_workbench_mock/research_package.json`
- `/tmp/research_workbench_mock/data.xlsx`
- `/tmp/research_workbench_mock/report.md`
- `/tmp/research_workbench_mock/report.html`

## 手动导出数据盘点

卖家精灵 MCP 接入前，V1 优先读取运营手动导出的 Excel/CSV。

```bash
python3 scripts/inspect_manual_exports.py \
  卖家精灵导出样例_美国站_宠物牵引绳_20260607 \
  /tmp/manual_export_manifest.json \
  --site US \
  --task-name 美国站宠物牵引绳样例
```

脚本会识别搜索结果、市场分析、关键词反查、ABA 关键词等文件，并输出字段缺失检查。

继续生成候选品池：

```bash
python3 scripts/build_candidate_pool_from_import_manifest.py \
  /tmp/manual_export_manifest.json \
  /tmp/manual_export_candidate_pool.json
```

生成候选品池预审输出：

```bash
python3 scripts/build_candidate_pool_precheck.py \
  /tmp/manual_export_candidate_pool.json \
  /tmp/manual_export_precheck
```

输出：

- `/tmp/manual_export_precheck/candidate_pool.json`
- `/tmp/manual_export_precheck/precheck_report.md`
- `/tmp/manual_export_precheck/precheck_summary.md`
- `/tmp/manual_export_precheck/precheck_dashboard.html`
- `/tmp/manual_export_precheck/precheck_data.xlsx`

## 自有评论插件导入

重点候选进入深挖后，读取自有评论插件导出的 Excel，并可附带 HTML AI 报告作为辅助参考。

```bash
python3 scripts/build_review_voc_from_plugin_export.py \
  /tmp/review_voc_hands_free_leashes \
  /Users/sxie/Downloads/B07R56CBWX-multi-2026-06-07.xlsx \
  /Users/sxie/Downloads/B07R56CBWX-multi-2026-06-07-report.html \
  --candidate-id cand-dog-running-leash \
  --candidate-name "Hands Free Leashes"
```

输出：

- `/tmp/review_voc_hands_free_leashes/review_voc_package.json`
- `/tmp/review_voc_hands_free_leashes/voc_report.md`
- `/tmp/review_voc_hands_free_leashes/voc_summary.md`
- `/tmp/review_voc_hands_free_leashes/voc_evidence.xlsx`

合并进重点候选深挖数据包：

```bash
python3 scripts/build_research_package_from_candidate.py \
  /tmp/manual_export_candidate_pool.json \
  /tmp/manual_export_research_package.json \
  cand-dog-running-leash \
  --voc-package /tmp/review_voc_hands_free_leashes/review_voc_package.json
```

## 当前阶段

项目处于 V1 骨架阶段，先完成 `候选品发现 Skill + 本地报告生成器`，不直接做完整应用。

最近步骤：

1. 冻结 V1 范围。
2. 整理字段来源表。
3. 制作静态报告 mock。
4. 搭建 Skill 和 references 骨架。
5. 搭建最小本地报告生成器。
6. 打通卖家精灵手动导出数据到候选品池。
7. 新增候选品池预审输出，用于判断是否进入正式深挖。
8. 接入自有评论插件 Excel/HTML 导出。
9. 将评论 VOC 合并进重点候选深挖报告。
10. 补充决策检查、风险矩阵和一键完整流程脚本。

## 暂不包含

- 不包含完整应用代码。
- 不包含卖家精灵 MCP 调用实现。
- 不包含自有评论插件源码。
- 不包含历史调研数据、备份文件和临时输出。
