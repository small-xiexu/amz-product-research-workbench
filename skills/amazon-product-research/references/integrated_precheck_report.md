# Stage 7 市场机会报告契约

本契约定义多数据源市场机会报告的固定交付阶段。目标不是输出后置落地流程，也不是模板字段回填，而是由 Lead Operator 先产出资深亚马逊运营专家 professional analysis memo，再由 Report Writer 把 memo 和全部 evidence 写成用户可 review 的市场机会报告。

## 阶段定位

Stage 7 名称固定为：`多数据源市场机会报告`。

输入条件：

- Stage 5 路线矩阵已确认。
- Stage 6 评论 VOC 已完成，或明确写明评论样本缺口。
- Sorftime 深扫已完成，或明确写明未调用的关键词、ASIN、类目和影响。
- 卖家精灵市场结构已完成，或明确写明 Top100、ABA、关键词反查等缺口。

输出用途：

- 让运营先 review 产品机会、路线、关键词、竞品和 VOC 风险。
- 帮运营知道自己打开哪些 ASIN/关键词/评论重点看。
- 明确下一轮补数和继续研究优先级。
- 不输出后置落地结论；样品、产品方案和商业测算只作为待验证动作。

职责边界：

- 数据源专家 Agent 只产 evidence、缺口、置信度和待补动作；不输出最终报告，不输出最终进入结论。
- Lead Operator 必须产出 professional analysis memo：解释需求、市场、VOC、数据缺口和结论原因。
- Report Writer 是报告生成专家，只把 memo + 全部 evidence 改写成用户可读 HTML/Excel；不新增数字，不改商业判断。
- 模板只负责版式、章节、字段和证据落位，禁止硬编码当前商品、ASIN、关键词或类目。
- 所有数据源 Evidence Packet 必须写入 `execution_provenance`。若是历史导入、脚本补包或主流程降级，也要明确标注，禁止留空或伪装成子 Agent 执行。
- VOC 口径以“主要评论地区”判断用户市场，不以“采集入口站点”判断。若目标站入口只能看到少量评论，可以从其他站点入口采集，但报告必须显示采集入口和主要评论地区；只有当主要评论地区与目标市场不匹配或占比不足时，才建议按目标站补采。

## 固定产物

所有产物必须落在本轮 run 的 `analysis/` 目录：

| 文件 | 用途 |
|---|---|
| `analysis_report.html` | 主报告，给运营直接 review |
| `analysis_report.xlsx` | 表格版，给运营筛选路线、竞品、关键词、VOC、评分卡和证据审计 |
| `analysis_evidence_packet.json` | 主 Agent 综合判断结构化证据 |
| `report_writer_narrative.json` | 可选但推荐，由 Report Writer Agent 生成用户可读叙事；脚本只负责渲染和兜底 |
| `delivery_qa_result.json` | QA Agent 对报告完整性、证据边界和越权问题的检查结果 |

如果项目仍保留旧的 `final_report/*` 五件套，Stage 7 可以兼容生成，但用户 review 的主入口必须是 `analysis_report.html`。

## 数据源映射

| 数据源 | 负责 Agent | 报告用途 |
|---|---|---|
| Sorftime MCP | Search Demand Agent | 市场实时验证、类目混池、关键词需求、竞品流量词、自然位、长尾词、热销特征 |
| 卖家精灵 | Market Structure Agent | Top100、销量、价格带、评论门槛、新品信号、ABA、关键词反查 |
| 评论 VOC | VOC Evidence Agent | 差评痛点、好评驱动、痛点到规格/测试项映射 |
| 主 Agent | Lead Operator Agent | 资深亚马逊运营专家综合判断，不复述数据流水账 |
| 报告生成 | Report Writer | 将 professional analysis memo + evidence 写成通俗、有结论、有数据支撑、有下一步动作的用户报告 |
| QA | Delivery QA Agent | 检查文件、来源、越权、硬缺口和报告可读性 |

用户版 `analysis_report.html` / `analysis_report.xlsx` 不展示 Agent、MCP、tool、internal execution、spawn、packet 等内部执行术语。需要表达来源时，用“市场数据”“搜索需求数据”“评论 VOC”等用户能理解的名称。

## HTML 报告结构

`analysis_report.html` 至少包含以下章节：

1. **首屏结论**
   - `继续看 / 谨慎继续 / 暂缓`
   - 资深运营一句话理由
   - 当前最大机会
   - 当前最大风险
   - 下一步最小动作

2. **资深运营综合分析**
   - 以资深亚马逊运营专家口吻写。
   - 必须来自 Lead Operator 的 professional analysis memo，并综合 Sorftime、卖家精灵、VOC 和全部 evidence。
   - 必须回答：需求是否真实、竞争是否能切入、产品形态是否清晰、VOC 能否转规格、为什么现在还不能直接强结论、用户 review 时看什么。
   - 事实、推断、风险、待补动作分开写。

3. **品类选择推导链路**
   - 固定回答“为什么最后选择这个品类/主线，而不是看起来像随便挑的”。
   - 必须按通用链路展示：初始约束 -> 候选入口/种子词 -> 候选类目反推 -> 参考 ASIN 验证 -> 关键词/ABA/自然位交叉 -> 混池/排除项 -> 多源收敛结论。
   - 每一步都要写清：事实证据、运营含义、收敛动作；不能只写结论。
   - 必须展示被排除或降级的候选方向、类目或关键词，以及排除原因。

4. **证据边界**
   - 说明本轮已经由系统/Agent 完成了哪些数据复核。
   - 说明哪些能力仍未完成，例如样品、系统侧来源记录、VOC 评论地区覆盖、代表 ASIN 不足等。

5. **Sorftime 市场验证**
   - 类目和混池判断。
   - Top100 体量、价格带、集中度。
   - 核心词、长尾词、CPC、季节性、竞品流量词。
   - 代表 ASIN 的自然位/流量入口。

6. **卖家精灵关键词与竞品验证**
   - Top100、ABA、关键词反查、搜索结果。
   - 新品信号、评论门槛、价格带与卖家结构。
   - 与 Sorftime 冲突或互相印证的地方。

7. **VOC 差评痛点与规格翻译**
   - 高频痛点。
   - 正向购买理由。
   - 痛点到产品规格、样品测试项或 Listing 风险提示的映射。

8. **多数据源交叉判断**
   - 每个数据源的证据强度、关键发现、缺口。
   - 资深运营如何从多源证据得到当前结论。

9. **市场机会评分**
   - 固定 8 维：市场规模、竞争格局、需求清晰度、小类边界清晰度、新品友好度、VOC证据质量、退货/体验风险、数据完整度。
   - 明确权重、分数、依据和限制原因。

10. **风险与待验证项**
    - 运营应优先打开哪些 ASIN、关键词和评论证据。
    - 看哪些字段、哪些图片、哪些混池迹象。

11. **继续研究优先级**
    - 哪 1-2 条路线优先继续，哪些观察，哪些放弃。
    - 每条路线的下一轮补数动作。

12. **下一步动作与证据附录**
    - 文件、证据、数据缺口和后续动作。

## Excel 报表结构

`analysis_report.xlsx` 至少包含这些 Sheet：

| Sheet | 内容 |
|---|---|
| `Executive Summary` | 结论、机会、风险、下一步 |
| `Category Derivation` | 品类选择推导链路、排除/降级候选、来源追溯 |
| `Route Matrix` | 路线、角色、证据强度、市场/VOC 状态、资深运营判断 |
| `Sorftime` | 类目、关键词、长尾词、竞品流量词、自然位、热销特征 |
| `SellerSprite` | Top100、ABA、关键词反查、竞品池摘要 |
| `VOC Spec Map` | 痛点、频次、证据评论、规格/测试映射 |
| `Market Scorecard` | 市场机会评分卡、限制原因和继续研究优先级 |
| `Evidence Handoff` | 各数据源 evidence 的关键发现、缺口、置信度 |

## `analysis_evidence_packet.json`

固定结构：

```json
{
  "packet_id": "analysis_evidence_packet",
  "agent_role": "Lead Operator Agent",
  "persona": "资深亚马逊运营专家",
  "stage": "market_opportunity_review",
  "verdict": "继续看 | 谨慎继续 | 暂缓",
  "one_sentence_reason": "",
  "source_packets": [],
  "professional_analysis_memo": {
    "category_selection_derivation": "",
    "demand_context": "",
    "market_context": "",
    "voc_context": "",
    "risk_gaps": "",
    "conclusion_rationale": "",
    "next_actions": []
  },
  "lead_operator_analysis": {
    "market_demand": "",
    "competition_entry": "",
    "product_shape": "",
    "voc_to_spec": "",
    "why_not_strong_conclusion_yet": ""
  },
  "category_selection_derivation": {
    "selected_category": "",
    "confidence": "high | medium | low",
    "steps": [
      {
        "name": "初始约束 | 候选类目反推 | 参考 ASIN 验证 | 关键词交叉 | 混池排除 | 多源收敛",
        "evidence": [],
        "implication": "",
        "decision": "",
        "lineage": []
      }
    ],
    "rejected_alternatives": [],
    "source_refs": []
  },
  "route_judgment": [],
  "recommended_review_targets": [],
  "market_scorecard": {},
  "blocking_gaps": [],
  "next_stage_entry_conditions": [],
  "confidence": "high | medium | low",
  "lineage": []
}
```

## 缺证据表达

- 系统没有采集、解析或交叉验证到：写“系统侧待补”。
- 需要用户打开 ASIN、关键词结果页、详情页或评论上下文目视判断：写“人工 review 待补”。
- 只有用户确实未提供必要输入、文件或确认时，才写“用户输入缺失”。

## 禁止项

- 禁止把某个品类、ASIN、关键词写进通用模板。
- 禁止只输出单源报告，忽略 Sorftime、卖家精灵和 VOC。
- 禁止把各 Agent 结论简单拼接成流水账；必须由主 Agent 给出综合运营判断。
- 禁止把后置落地结论写成当前阶段已验证事实。
- 禁止在用户版报告展示 Agent、MCP、tool、internal execution、spawn、packet 等内部执行术语。
