# AMZ Product Research Workbench

亚马逊选品全流程工作台方案。

当前方向：输入模糊选品意图，系统主动发现候选品，再逐层筛选、深挖、生成报告和看板。不是让运营先找好产品、填完成本，再让系统写报告。

当前阶段先沉淀产品路线、业务流程和技术方案，不直接开发完整应用。后续按 `候选品发现 Skill + 本地报告生成器 -> 轻量网页工作台 -> 完整选品应用` 演进。

## 当前目标

- V1 采用三源融合：卖家精灵手动导出（广域候选池）+ Sorftime MCP（类目/关键词/竞品深度验证）+ 自有评论插件（VOC 证据链）。
- 当前已跑通 `卖家精灵导出文件夹 -> 候选品池 -> 可选 Sorftime 深度验证 -> 可选评论 VOC -> 利润复核模板 -> 知产/合规初筛模板 -> 深挖报告`。
- 生成选品报告四件套：主报告、摘要、HTML 看板、Excel 数据底表。
- 保留 Excel 数据底表和可追溯证据链。
- 利润、退货、知产、合规等关键判断保留人工复核。
- 自有评论插件已通过 Excel/HTML 文件导入方式接入重点候选深挖。

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
| `docs/字段来源表.md` | 每个字段来自手动导出、MCP、手填、系统计算还是人工复核 |
| `docs/卖家精灵手动导出数据清单.md` | 没有 MCP 时，AI 指挥用户从卖家精灵导出哪些数据 |
| `docs/自有评论插件对接方案.md` | 自有评论插件 Excel/HTML 导出如何接入选品系统 |
| `docs/静态报告Mock.md` | 报告、摘要、看板的静态样式骨架 |
| `docs/亚马逊选品全流程产品路线图.md` | 产品目标、阶段规划、V0-V5 演进路线 |
| `docs/亚马逊运营选品自查工具速读版.md` | 快速理解项目方向和 V1 边界 |
| `docs/亚马逊运营选品自查工具流程方案.md` | 业务流程、判断逻辑、利润/退货/合规规则 |
| `docs/亚马逊运营选品自查工具技术方案.md` | 技术架构、目录规划、数据包、版本和验收 |
| `docs/知产与合规检索入口库.md` | 知产、商标、合规早期筛查入口 |

## 本地验证

优先使用一键完整流程：

```bash
python3 scripts/run_research_workflow.py \
  卖家精灵导出样例_美国站_宠物牵引绳_20260607 \
  /tmp/research_workbench_workflow \
  --site US \
  --task-name 美国站宠物牵引绳样例 \
  --review-input /Users/sxie/Downloads/B07R56CBWX-multi-2026-06-07.xlsx \
  --review-input /Users/sxie/Downloads/B07R56CBWX-multi-2026-06-07-report.html
```

输出：

- `/tmp/research_workbench_workflow/import_manifest.json`
- `/tmp/research_workbench_workflow/candidate_pool.json`
- `/tmp/research_workbench_workflow/review_voc/review_voc_package.json`
- `/tmp/research_workbench_workflow/research_package.json`
- `/tmp/research_workbench_workflow/profit_review_template.xlsx`
- `/tmp/research_workbench_workflow/ip_compliance_review_template.xlsx`
- `/tmp/research_workbench_workflow/final_report/report.md`
- `/tmp/research_workbench_workflow/final_report/summary.md`
- `/tmp/research_workbench_workflow/final_report/dashboard.html`
- `/tmp/research_workbench_workflow/final_report/data.xlsx`
- `/tmp/research_workbench_workflow/workflow_summary.md`

生成后必须运行正式交付校验：

```bash
python3 scripts/validate_research_outputs.py /tmp/research_workbench_workflow
```

校验器会检查正式报告四件套、`workflow_summary`、Excel 关键 Sheet、Top100 行数、12 章报告结构、属性/交叉分析、竞品选择逻辑、VOC 证据链和七维 Go/Wait/No-Go 评分卡。利润或知产/合规未回填时，评分卡只能输出 Wait/观察/待补，不能给强 Go。

利润模板填好并保存后，再回填生成带利润测算的报告。`--profit-template` 传入的是已填写保存后的模板路径，可以是原模板直接填写保存，也可以另存为一份：

```bash
python3 scripts/run_research_workflow.py \
  卖家精灵导出样例_美国站_宠物牵引绳_20260607 \
  /tmp/research_workbench_workflow_with_profit \
  --site US \
  --task-name 美国站宠物牵引绳样例 \
  --review-input /Users/sxie/Downloads/B07R56CBWX-multi-2026-06-07.xlsx \
  --review-input /Users/sxie/Downloads/B07R56CBWX-multi-2026-06-07-report.html \
  --profit-template /tmp/research_workbench_workflow/filled_profit_review_template.xlsx
```

知产/合规模板填好并保存后，再回填生成带初筛结果的报告。`--ip-compliance-template` 传入的是已填写保存后的模板路径：

```bash
python3 scripts/run_research_workflow.py \
  卖家精灵导出样例_美国站_宠物牵引绳_20260607 \
  /tmp/research_workbench_workflow_with_ip_compliance \
  --site US \
  --task-name 美国站宠物牵引绳样例 \
  --review-input /Users/sxie/Downloads/B07R56CBWX-multi-2026-06-07.xlsx \
  --review-input /Users/sxie/Downloads/B07R56CBWX-multi-2026-06-07-report.html \
  --ip-compliance-template /tmp/research_workbench_workflow/filled_ip_compliance_review_template.xlsx
```

利润和知产/合规可以同时回填：

```bash
python3 scripts/run_research_workflow.py \
  卖家精灵导出样例_美国站_宠物牵引绳_20260607 \
  /tmp/research_workbench_workflow_full \
  --site US \
  --task-name 美国站宠物牵引绳样例 \
  --review-input /Users/sxie/Downloads/B07R56CBWX-multi-2026-06-07.xlsx \
  --review-input /Users/sxie/Downloads/B07R56CBWX-multi-2026-06-07-report.html \
  --profit-template /tmp/research_workbench_workflow/filled_profit_review_template.xlsx \
  --ip-compliance-template /tmp/research_workbench_workflow/filled_ip_compliance_review_template.xlsx
```

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

python3 scripts/validate_research_outputs.py /tmp/amz_p20_regression_dog

python3 scripts/run_research_workflow.py \
  卖家精灵导出_刮窗器_20260608 \
  /tmp/amz_p20_regression_window \
  --site US \
  --task-name P20刮窗器回归 \
  --review-input 评价导出_刮窗器_20260609/B0BKTM56C3-multi-2026-06-09.xlsx \
  --review-input 评价导出_刮窗器_20260609/B0BKTM56C3-multi-2026-06-09-report.html

python3 scripts/validate_research_outputs.py /tmp/amz_p20_regression_window
```

也可以分开执行：

```bash
python3 scripts/build_profit_template.py \
  /tmp/research_workbench_workflow/research_package.json \
  /tmp/profit_review_template.xlsx

python3 scripts/apply_profit_review.py \
  /tmp/research_workbench_workflow/research_package.json \
  /tmp/filled_profit_review_template.xlsx \
  /tmp/research_package_with_profit.json

python3 scripts/build_ip_compliance_template.py \
  /tmp/research_workbench_workflow/research_package.json \
  /tmp/ip_compliance_review_template.xlsx

python3 scripts/apply_ip_compliance_review.py \
  /tmp/research_workbench_workflow/research_package.json \
  /tmp/filled_ip_compliance_review_template.xlsx \
  /tmp/research_package_with_ip_compliance.json
```

只验证报告渲染器时使用最小 mock：

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
11. 新增利润复核模板和回填计算。
12. 新增知产/合规初筛模板和人工回填闭环。

## 暂不包含

- 不包含完整应用代码。
- 不包含卖家精灵 MCP 调用实现。
- 不包含自有评论插件源码。
- 不包含历史调研数据、备份文件和临时输出。
