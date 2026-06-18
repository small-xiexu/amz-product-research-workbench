# Evidence Packet 契约

Evidence Packet 是多 Agent 协作的交接单位。每个数据源专家 Agent 只输出证据包，不直接给最终 Go/No-Go。资深亚马逊运营主 Agent 只能基于这些证据包和 `research_package.json` 做综合判断。

## 通用结构

```json
{
  "packet_id": "market_structure_evidence",
  "packet_version": "P30.1",
  "agent_role": "Market Structure Agent",
  "source_scope": ["SellerSprite"],
  "created_at": "YYYY-MM-DD",
  "input_refs": [
    {
      "type": "file",
      "path": "runs/<run_id>/import_manifest.json"
    }
  ],
  "facts": [],
  "derived_metrics": [],
  "insights_for_handoff": [],
  "data_gaps": [],
  "confidence": "high | medium | low",
  "lineage": []
}
```

## 字段说明

| 字段 | 必填 | 说明 |
|---|---|---|
| `packet_id` | 是 | 固定证据包 ID，如 `market_structure_evidence` |
| `agent_role` | 是 | 产出该包的 Agent 角色 |
| `source_scope` | 是 | 该包允许使用的数据源范围 |
| `input_refs` | 是 | 原始文件、MCP 工具返回或中间 JSON |
| `facts` | 是 | 可直接追溯的数据事实，禁止写主观结论 |
| `derived_metrics` | 否 | 由 facts 计算出的聚合指标 |
| `insights_for_handoff` | 否 | 给主 Agent 的解释性观察，必须标事实/推断 |
| `data_gaps` | 是 | 缺失字段、样本不足、冲突数据和影响 |
| `confidence` | 是 | 对该证据包整体可靠性的判断 |
| `lineage` | 是 | 指向原始 JSON 字段、Excel Sheet、评论 ID 或 MCP 工具 |

## 标准证据包

| Packet | 产出 Agent | 数据范围 |
|---|---|---|
| `market_structure_evidence` | Market Structure Agent | 卖家精灵市场、Top100、ABA、关键词反查 |
| `search_demand_evidence` | Search Demand Agent | Sorftime 类目、关键词、趋势、竞品流量词 |
| `voc_evidence` | VOC Evidence Agent | 评论插件、评论证据、痛点到规格映射 |
| `supply_chain_evidence` | Supply Chain Agent | 1688 中国站、供应商、采购价、现货形态 |
| `profit_compliance_evidence` | Profit Compliance Agent | 利润、知产、合规、退货风险 |
| `integrated_operator_judgment` | Lead Operator Agent | 只读以上证据包和 `research_package.json` |
| `delivery_qa_result` | Delivery QA Agent | 最终交付物、校验结果和证据边界 |

## 越权规则

- 专家 Agent 不输出 `go_nogo_verdict`、`final_decision`、`route_priority`。
- 专家 Agent 可以写 `evidence_strength`，不能写“建议立项”。
- 主 Agent 不新增原始数字；需要数字时必须引用 Evidence Packet 或 `research_package.json`。
- QA Agent 不改商业判断，只判断是否有证据、是否违反边界、是否可交付。
- 任一证据包 `confidence=low` 时，主 Agent 必须在最终判断里说明影响。

## 缺证据处理

缺证据不能静默跳过，必须写入 `data_gaps`：

| 场景 | 写法 |
|---|---|
| Top100 不完整 | 标记为阻塞，不进入正式深挖 |
| 评论样本不足 | 输出需要补抓的 ASIN 和目标评论数 |
| 1688 样本无效 | 说明剔除原因，不参与采购价区间 |
| 利润/合规未回填 | 主 Agent 只能给 Wait/观察/待补 |
| 数据源冲突 | 同时列出冲突事实，交由主 Agent 解释或标待验证 |

## 与现有产物关系

P30 不新增强制运行时格式，也不改变 CLI。Evidence Packet 先作为 Skill 和报告写作的协作契约：

- 代码层已有 `build_research_data_packet()` 负责结构化数据。
- `research_package.json` 仍是正式报告唯一事实源。
- Agent 在对话和文档层按 Evidence Packet 组织证据。
- 后续如需自动多 Agent 调度，可把这些字段落成独立 JSON 文件。
