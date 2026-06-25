# amazon-product-research

Codex 版亚马逊交互式选品主入口。

这个 Skill 不是网页工作台，也不是一次性报告生成器。它的目标是让 Codex 按运营节奏推进选品：先理解意图，再通过双 MCP（卖家精灵 + Sorftime）自动采集市场数据，最后生成可追溯的市场机会报告。运营不再需要手动导出卖家精灵报表——MCP 全链路已跑通。

## 当前主线（MCP 主路径）

```text
运营意图
-> Codex 判断无方向探索/指定方向深挖
-> 双 MCP 市场快验（卖家精灵 + Sorftime）
-> 快验门控（继续/观察/暂停）
-> MCP 候选池
-> 路线矩阵确认
-> 双 MCP 深挖 + 冲突复核
-> 评论 VOC
-> 多评价 Agent
-> 资深运营专家判断
-> 报告 + QA
```

执行上采用受控多 Agent 分工：

```text
卖家精灵市场结构 Agent
Sorftime 搜索需求 Agent
评论 VOC Agent
        ↓
6 个评价 Agent（并行）
        ↓
Lead Operator Agent（资深运营专家综合判断）
        ↓
Report Generation Agent（report_data + HTML 报告）
        ↓
脚本（生成 XLSX + QA）
        ↓
Delivery QA Agent（强制独立 spawn）
        ↓
运营 review + 下一轮补数
```

这不是全阶段自动开 Agent，而是受控调度：Stage 0-5 默认由主 Agent 串行推进；Stage 6 以后在运行环境支持时，按 `references/multi_agent_dispatch.md` 启动 VOC、Sorftime 深扫、市场结构等专家 Agent。数据源专家 Agent 只产 Evidence Packet，资深运营专家 Agent 输出 `integrated_operator_judgment.json`，Report Generation Agent 基于 seed 和 judgment 生成 `report_data.json` 与 HTML，脚本只跑 XLSX 和 QA。

Web 页面暂不作为主线。等 Codex 版闭环稳定后，再把 Web 作为外壳接入同一套脚本和产物。

## 关键原则

| 原则 | 要求 |
|---|---|
| AI 带运营走 | Codex 主动判断下一步，不让运营猜流程 |
| 关键点暂停 | 方向、边界、ASIN、评论批次和最终判断必须让运营确认 |
| 数据不编造 | 不足就标注待补，不用推断填空 |
| 证据可追溯 | 结论必须能指向 MCP、卖家精灵、评论、人工输入或脚本产物 |
| 多 Agent 不越权 | 数据源专家只输出证据包，最终判断由资深运营专家 Agent 统一整合，报告由 Report Generation Agent 生成 |
| 市场机会先行 | 报告只判断是否值得继续研究，不输出后置落地结论 |
| Web 后置 | 当前只跑 Codex + MCP + 本地脚本 |

## 常用入口

| 场景 | 命令/文件 |
|---|---|
| 市场快验 | `python3 scripts/run_quick_market_check.py <run_dir>` |
| MCP 候选池 | `python3 scripts/build_mcp_candidate_pool.py <run_dir>` |
| 路线矩阵确认 | `python3 scripts/build_route_matrix_confirm.py <run_dir>` |
| 深挖 + 冲突复核 | `python3 scripts/build_sellersprite_deep_dive.py <run_dir> && python3 scripts/build_sorftime_deep_dive.py <run_dir> && python3 scripts/build_conflict_review.py <run_dir>` |
| 运行报告 Agent | `python3 scripts/run_report_agent.py <run_dir>` |
| 全量报告 + QA | `python3 -m packages.research_core.pipeline.build_analysis_report <run_dir>` |
| 运行 Delivery QA | `python3 scripts/run_delivery_qa.py <run_dir>` |

## Legacy 回退（MCP 不可用时）

以下入口仅在 MCP 服务不可用时用于人工兜底，不作为主路径：

| 场景 | 命令 |
|---|---|
| 盘点卖家精灵导出 | `python3 scripts/inspect_manual_exports.py <导出文件夹> <manifest.json>` |

## 推荐运行目录

每次真实调试单独建一个 run 目录：

```text
runs/<yyyymmdd>_<中文品类方向>/
├── mcp_snapshots/
├── quick_check/
├── inputs/
│   ├── seller_sprite/
│   └── reviews/
├── mcp/
├── candidate_pool.json
├── route_matrix_confirm.json
├── market_structure/
├── search_demand/
├── conflict_review/
├── review_voc/
├── evaluations/
├── analysis/
│   ├── <中文品名>_分析报告.html
│   ├── <中文品名>_数据回表.xlsx
│   ├── report_data.json
│   └── delivery_qa_result.json
├── research_package.json
└── workflow_summary.md
```

## 相关说明

- 主流程：`SKILL.md`
- Agent 分工：`agents/`
- Evidence Packet 契约：`references/evidence_packet_contract.md`
- 多 Agent 调度：`references/multi_agent_dispatch.md`
- Codex 跑通手册：`references/codex_runbook.md`
- 产物契约：`references/artifact_contract.md`
- 全局链路文档：`skills/amazon-product-research/SKILL.md`
