# 多 Agent 调度规则

本项目采用受控多 Agent：数据源专家 Agent 只产 Evidence Packet，Lead Operator 统一做市场机会判断，Report Writer 写用户版报告，Delivery QA 检查交付边界。

## 调度表

| 阶段 | 是否 spawn | 触发条件 | Agent | 产物 |
|---|---|---|---|---|
| Stage 0-5 | 默认不 spawn | 常规交互推进 | 主 Agent 串行按专家口径执行 | `workflow_state.json`、`candidate_pool.json`、`route_matrix_confirm.json` |
| Stage 6 VOC | 可 spawn | 评论导出已导入，或路线多、样本多 | VOC Evidence Agent | `review_voc/voc_evidence_packet.json` |
| Stage 7 市场机会 | 默认自动 spawn 数据源 Agent（如工具可用） | Search Demand、Market Structure、VOC 已完成或缺口明确 | Search Demand Agent、Market Structure Agent、VOC Evidence Agent、Report Writer、Delivery QA Agent | `analysis/analysis_report.html`、`analysis/analysis_report.xlsx`、`analysis/analysis_evidence_packet.json` |

## Stage 7 推荐顺序

1. Search Demand Agent：用 Sorftime 深扫类目、核心词、长尾词、P0/P1 ASIN 流量词、自然位和热销特征。
2. Market Structure Agent：用卖家精灵 Top100、ABA、关键词反查和市场分析整理市场结构证据。
3. VOC Evidence Agent：把评论痛点翻译成产品规格、样品测试项和 Listing 风险提示。
4. Lead Operator Agent：读取全部 Evidence Packet，产出 professional analysis memo、市场机会评分、路线优先级和下一步动作。
5. Report Writer：把 memo 和 evidence 写成用户版 HTML/Excel。
6. Delivery QA Agent：检查文件、证据、越权和通用模板风险。

## 降级规则

如果运行环境没有真实子 Agent 工具、子 Agent 执行失败，或用户明确要求串行，允许主 Agent 按同一 Agent 口径串行执行，并必须在 `execution_provenance`、`run_status_audit` 和 QA 结果中标明 `serial_fallback`。

降级不代表不能交付，但报告必须说明：

- 哪些证据是真实工具/脚本产出。
- 哪些证据是主 Agent 串行整理。
- 哪些数据缺口会影响市场机会判断。

## 越权规则

- Search Demand / Market Structure / VOC Evidence Agent 不输出最终路线优先级。
- Lead Operator 不清洗原始数据，不新增原始数字。
- Report Writer 不修改 Lead Operator 判断。
- Delivery QA 不改判断，只给 error/warning 和待补建议。

## 输出边界

用户版报告只展示业务语言，不展示 Agent、MCP、tool、spawn、packet 等内部术语。内部 Evidence Packet 可以保留执行来源和工具参数，供 QA 与后续恢复使用。
