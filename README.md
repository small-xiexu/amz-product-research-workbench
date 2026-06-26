# AMZ Product Research Workbench

亚马逊选品全流程工作台方案。

当前方向：输入模糊选品意图，系统主动发现候选品，再逐层筛选、深挖、生成决策报告。不是让运营先找好产品，再让系统写报告。

当前处于 Codex 版主线闭环阶段，后续演进方向：Codex 版 -> 轻量网页工作台 -> 完整选品应用。

## 当前目标

- V1 采用双 MCP 融合：卖家精灵 MCP（类目市场/关键词/竞品）+ Sorftime MCP（类目/关键词/竞品深度验证）+ 自有评论插件（VOC 证据链）。
- 主产品体验是 AI 与运营交互式推进：AI 判断当前阶段、下一步动作、是否需要运营决策；最终报告沉淀整个交互过程。
- 当前已跑通完整 13 阶段主链路：`运营意图 -> 双 Agent 快验 -> 快验门控 -> 候选池 -> 路线矩阵确认 -> 双 MCP 深挖 -> 冲突复核 -> VOC 评论分析 -> 六维评价 -> 资深运营综合判断 -> seed 生成 -> 报告生成 -> QA 双层门禁`。
- 最终交付物：`<中文品名>_分析报告.html`（AI 以资深运营专家视角手写）+ `<中文品名>_决策工具包.xlsx`（脚本生成运营决策工具包，5 Sheet）。
- 保留 Excel 数据底表和可追溯证据链。
- 自有评论插件已通过 Excel/HTML 文件导入方式接入 VOC 分析阶段。

## 当前架构

| 层 | 位置 | 职责 |
|---|---|---|
| 交互式流程入口 | `scripts/plan_interactive_workflow.py` | 生成/更新 `workflow_state` 和下一步动作卡 |
| 批量回归入口 | `tests/` (pytest) | 数据齐全后重跑完整报告，用于回归和开发验证 |
| Workflow 应用层 | `packages/research_core/workflows/` | 交互式状态推进 + 批量报告编排 |
| Contracts 契约层 | `packages/research_core/contracts/` | 在关键节点校验 `import_manifest`、`candidate_pool`、`research_package` 等数据包结构 |
| Core 规则层 | `packages/research_core/` | Adapter、统一 Schema、字段合并、市场结构等可复用规则 |
| Renderer 输出层 | `packages/report_renderer/` | 生成 HTML 报告、Excel 数据底表；`xlsx_writer.py` + `constants.py` |
| Skills 分析层 | `skills/` | 约束 Claude 如何基于结构化数据做市场/VOC/深挖判断 |

主体验优先调用 `packages.research_core.workflows.create_initial_state()` / `plan_next_action()` / `advance_stage()` 维护交互状态。新增第三方数据源优先落在 `packages/research_core/adapters/` 和 `merge_strategy.py`。

## 文档索引

| 文档 | 用途 |
|---|---|
| `docs/plans/V1选品系统实施计划.md` | V1 实施计划（已于 2026-06-25 主线闭环，进度现由 `progress.json` 追踪） |
| `docs/选品系统方向锚点.md` | 项目方向主锚点，防止偏成“录入产品做报告” |
| `skills/amazon-product-research/SKILL.md` | 当前唯一主流程入口，覆盖全阶段 |
| `packages/research_core/workflows/` | 交互式状态推进和批量报告编排，可被 CLI/网页/API 复用 |
| `packages/research_core/contracts/` | 核心数据包结构校验 |
| `packages/research_core/` | 统一数据结构、Adapter、状态规则 |
| `packages/report_renderer/` | Markdown、HTML 正式报告和 Excel 底表渲染 |
| `scripts/` | 本地 CLI 入口和兼容工具脚本 |
| `examples/` | 最小输入样例和 mock 数据包 |
| `requirements.txt` | 本地脚本依赖，当前主要用于读取 Excel |
| `docs/字段来源表.md` | 每个字段来自手动导出、MCP、手填、系统计算还是人工复核 |
| `docs/卖家精灵导出指令完整性规范.md` | 卖家精灵真实菜单入口、导出对象和字段要求 |
| `docs/评论VOC导出指令完整性规范.md` | 评价插件采集口径，用户侧只需要 ASIN 清单 |
| `docs/自有评论插件对接方案.md` | 自有评论插件 Excel/HTML 导出如何接入选品系统 |
| `docs/多数据源适配器架构设计.md` | 新数据源接入 Adapter 的设计边界 |
| `docs/sorftime-mcp-工具调用策略.md` | Sorftime MCP 调用时机、参数和数据写入口径 |
| `docs/架构原则.md` | 脚本、Workflow、Skill、报告层的职责边界 |

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

交互推进到 Stage 7 后，AI 以资深运营专家身份手写 `<中文品名>_分析报告.html`，脚本生成 `<中文品名>_决策工具包.xlsx` 运营决策工具包。

## Stage 7 交付

AI 完成 7 阶段分析后，运行脚本生成决策工具包和 QA：

```bash
python3 -m packages.research_core.pipeline.build_analysis_report runs/<yyyymmdd_中文品类方向>
```

产物：
- `analysis/<中文品名>_分析报告.html` — AI 手写决策报告（最终交付）
- `analysis/<中文品名>_决策工具包.xlsx` — 脚本生成运营决策工具包（最终交付）
- `analysis/report_data.json` — 唯一数据中枢，所有事实含 source_path 溯源（中间产物）
- `analysis/delivery_qa_result.json` — QA 校验结果（中间产物）

定期运行通用性扫描：

```bash
python3 scripts/check_generic_redlines.py
```

## 回归测试

```bash
python3 -m unittest tests.test_regression -v
```

## 手动导出数据盘点（Legacy 回退）

MCP 不可用时的 fallback 路径：运营手动导出卖家精灵 Excel/CSV，通过 `scripts/inspect_manual_exports.py` 盘点后构建候选池。详见 Skill 附录。

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

VOC 包可直接用于 Stage 9 六维评价阶段。

## 当前阶段

Codex 版主线已闭环（2026-06-25）。完整 13 阶段流程：运营意图 → 双 Agent 快验 → 门控 → 候选池 → 路线矩阵 → 双 MCP 深挖 → 冲突复核 → VOC → 六维评价 → 资深运营判断 → seed → 报告 → QA 门禁。

已收敛：1 个主 Skill、15 个 Agent、5 个 Reference、2 份最终产物（HTML + XLSX）。

## 暂不包含

- 不包含完整 Web 应用代码（server/ 有骨架）。
- 不包含自有评论插件源码。
- 不包含 1688 供应链、知产合规、利润核算等后置落地模块。
- 不包含历史调研数据、备份文件和临时输出。
