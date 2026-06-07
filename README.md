# AMZ Product Research Workbench

亚马逊选品全流程工作台方案。

当前方向：输入模糊选品意图，系统主动发现候选品，再逐层筛选、深挖、生成报告和看板。不是让运营先找好产品、填完成本，再让系统写报告。

当前阶段先沉淀产品路线、业务流程和技术方案，不直接开发完整应用。后续按 `候选品发现 Skill + 本地报告生成器 -> 轻量网页工作台 -> 完整选品应用` 演进。

## 当前目标

- V1 数据源优先按卖家精灵手动导出/导入设计；API/MCP 作为后续自动化增强，当前代码先跑通本地样例数据包和报告生成。
- 下一步要把入口从 `research_package` 前移到 `selection_brief`，先生成候选品池。
- 生成选品报告三件套：主报告、摘要、HTML 看板。
- 保留 Excel 数据底表和可追溯证据链。
- 利润、退货、知产、合规等关键判断保留人工复核。
- V2 后接入自有评论插件，做 VOC、改品机会和图片/A+方向深挖。

## 文档索引

| 文档 | 用途 |
|---|---|
| `docs/plans/V1选品系统实施计划.md` | 唯一进度台账，下次恢复任务先看这里 |
| `docs/选品系统方向锚点.md` | 项目方向主锚点，防止偏成“录入产品做报告” |
| `skills/seller-sprite-product-research/SKILL.md` | Skill 主入口，定义流程、规则、输入输出 |
| `skills/seller-sprite-product-research/references/` | 工具映射、数据包结构、决策规则、输出结构 |
| `skills/seller-sprite-product-research/agents/` | 数据管道和洞察职责拆分 |
| `packages/research_core/` | 统一数据结构、利润规则、状态规则 |
| `packages/report_renderer/` | 主报告、摘要、HTML 看板渲染 |
| `scripts/` | 本地生成和验证脚本 |
| `examples/` | 最小输入样例和 mock 数据包 |
| `requirements.txt` | 本地脚本依赖，当前主要用于读取 Excel |
| `docs/V1范围冻结.md` | 冻结第一版要做什么、不做什么、输出什么 |
| `docs/字段来源表.md` | 每个字段来自手动导出、API/MCP、手填、系统计算还是人工复核 |
| `docs/卖家精灵手动导出数据清单.md` | 没有 API/MCP 时，AI 指挥用户从卖家精灵导出哪些数据 |
| `docs/自有评论插件对接方案.md` | 自有评论插件 Excel/HTML 导出如何接入选品系统 |
| `docs/静态报告Mock.md` | 报告、摘要、看板的静态样式骨架 |
| `docs/亚马逊选品全流程产品路线图.md` | 产品目标、阶段规划、V0-V5 演进路线 |
| `docs/亚马逊运营选品自查工具速读版.md` | 快速理解项目方向和 V1 边界 |
| `docs/亚马逊运营选品自查工具流程方案.md` | 业务流程、判断逻辑、利润/退货/合规规则 |
| `docs/亚马逊运营选品自查工具技术方案.md` | 技术架构、目录规划、数据包、版本和验收 |
| `docs/知产与合规检索入口库.md` | 知产、商标、合规早期筛查入口 |

## 本地验证

```bash
python3 scripts/build_mock_report.py examples/minimal_research_package.json /tmp/research_workbench_mock
```

输出：

- `/tmp/research_workbench_mock/research_package.json`
- `/tmp/research_workbench_mock/data.xlsx`
- `/tmp/research_workbench_mock/report.md`
- `/tmp/research_workbench_mock/summary.md`
- `/tmp/research_workbench_mock/dashboard.html`

## 手动导出数据盘点

卖家精灵 API/MCP 额外付费前，V1 优先读取运营手动导出的 Excel/CSV。

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

## 暂不包含

- 不包含完整应用代码。
- 不包含卖家精灵 API/MCP 调用实现。
- 不包含自有评论插件源码。
- 不包含历史调研数据、备份文件和临时输出。
