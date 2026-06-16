# amazon-product-research

Codex 版亚马逊交互式选品主入口。

这个 Skill 不是网页工作台，也不是一次性报告生成器。它的目标是让 Codex 按运营节奏推进选品：先理解意图，再决定调 MCP、让运营导出卖家精灵、导入评论、补利润/合规，最后生成可追溯报告。

## 当前主线

```text
运营意图
-> Codex 判断无方向探索/指定方向深挖
-> Sorftime MCP 快验
-> 卖家精灵导出清单
-> 导出文件盘点
-> 候选池
-> 评论 ASIN 批次
-> 评论 VOC
-> 利润/合规待补
-> 最终报告和校验
```

Web 页面暂不作为主线。等 Codex 版闭环稳定后，再把 Web 作为外壳接入同一套脚本和产物。

## 关键原则

| 原则 | 要求 |
|---|---|
| AI 带运营走 | Codex 主动判断下一步，不让运营猜流程 |
| 关键点暂停 | 方向、边界、ASIN、利润/合规、最终决策必须让运营确认 |
| 数据不编造 | 不足就标注待补，不用推断填空 |
| 证据可追溯 | 结论必须能指向 MCP、卖家精灵、评论、人工输入或脚本产物 |
| Web 后置 | 当前只跑 Codex + MCP + 本地脚本 |

## 常用入口

| 场景 | 命令/文件 |
|---|---|
| 生成交互状态 | `python3 scripts/plan_interactive_workflow.py <workflow_state.json> --mode <mode> --intent <intent> --site US` |
| 盘点卖家精灵导出 | `python3 scripts/inspect_manual_exports.py <导出文件夹> <manifest.json>` |
| 数据齐全后重跑报告 | `python3 scripts/run_research_workflow.py <导出文件夹> <输出目录> --site US --task-name <任务名>` |
| 校验最终交付 | `python3 scripts/validate_research_outputs.py <输出目录>` |

## 推荐运行目录

每次真实调试单独建一个 run 目录：

```text
runs/<yyyymmdd>_<direction>/
├── inputs/
│   ├── seller_sprite/
│   └── reviews/
├── mcp/
├── workflow_state.json
├── import_manifest.json
├── candidate_pool.json
├── review_voc/
├── research_package.json
├── final_report/
└── workflow_summary.md
```

## 相关说明

- 主流程：`SKILL.md`
- Agent 分工：`agents/`
- Codex 跑通手册：`references/codex_runbook.md`
- 产物契约：`references/artifact_contract.md`
- 全局链路文档：`docs/Codex选品链路.md`
