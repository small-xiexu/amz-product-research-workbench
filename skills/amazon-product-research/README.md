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

这是受控多 Agent 调度：Stage 2-3（快验）和 Stage 6（深挖）默认并行 spawn；Stage 9（六维评价）推荐并行 spawn；Stage 10（资深判断）推荐独立 spawn；Stage 13（QA）强制独立 spawn。详细规则见 `references/multi_agent_dispatch.md`。数据源专家 Agent 只产 Evidence Packet，Lead Operator Agent 输出最终判断，Report Generation Agent 生成 `report_data.json` 与 HTML，脚本跑 XLSX 和 QA。

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
| 初始化 workflow_state | `python3 scripts/init_workflow_state.py <run_dir> --intent "品类方向"` |
| 补齐 Quick Packet 契约 | `python3 scripts/fill_quick_packet_contract.py <packet.json> --source sellersprite\|sorftime` |
| 生成 Quick Gate | `python3 scripts/build_quick_market_gate.py <run_dir>` |
| 流程编排 (Stage 1-4) | `python3 scripts/run_pipeline.py <run_dir> --intent "品类方向"` |
| MCP 候选池 | `python3 scripts/build_mcp_candidate_pool.py <run_dir>` |
| 路线矩阵确认 | `python3 scripts/build_route_matrix_confirm.py <run_dir> [--force-confirm]` |
| 补齐 Deep Snapshot 契约 | `python3 scripts/build_deep_snapshot.py <mcp_dump.json> --source sellersprite\|sorftime` |
| 补齐 Deep Evidence Packet 契约 | `python3 scripts/build_deep_evidence_packet.py <agent_output.json> --source sellersprite\|sorftime` |
| 深挖 + 冲突复核 | `python3 scripts/build_conflict_review.py <run_dir>` |
| ASIN 批次 + VOC Gate | `python3 scripts/build_review_asin_batch.py <run_dir> && python3 scripts/build_voc_gate.py <run_dir>` |
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
│   ├── <中文品名>_决策工具包.xlsx
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
