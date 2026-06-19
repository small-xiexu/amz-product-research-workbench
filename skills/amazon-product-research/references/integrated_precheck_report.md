# Stage 7 综合预审报告契约

本契约定义 1688 数据导入后、利润/FBA/合规回填前的固定交付阶段。目标不是输出供应商问询流程，也不是模板字段回填，而是由 Lead Operator 先产出资深亚马逊运营专家 professional analysis memo，再由 Report Writer 把 memo 和全部 evidence 写成用户可 review 的综合预审报告。

## 阶段定位

Stage 7 名称固定为：`多数据源综合预审报告`。

输入条件：

- Stage 5 路线矩阵已确认。
- Stage 6 评论 VOC 已完成，或明确写明评论样本缺口。
- 1688 采集数据已导入，或明确写明供应链缺口。
- Sorftime 深扫已完成，或明确写明未调用的关键词、ASIN、类目和影响。

输出用途：

- 让运营先 review 产品机会、路线、供应链候选和风险。
- 帮运营知道自己打开哪些供应商/ASIN/关键词重点看。
- 明确利润回填字段，作为 Stage 8 的输入准备。
- 不强制要求供应商问询和资料回传；这些只作为可选补充动作。

职责边界：

- 数据源专家 Agent 只产 evidence、缺口、置信度和待补动作；不输出最终报告，不输出最终 Go/Wait/No-Go。
- Lead Operator 必须产出 professional analysis memo：解释需求、市场、VOC、供应链、利润/合规缺口和结论原因。
- Report Writer 是报告生成专家，只把 memo + 全部 evidence 改写成用户可读 HTML/Excel；不新增数字，不改商业判断。
- 模板只负责版式、章节、字段和证据落位，禁止硬编码当前商品、ASIN、关键词、供应商或类目。
- 1688 / Supply Chain Agent 的结构化预筛不等于图片视觉复核完成。除非 evidence 明确写入已完成图片内容判断、样品或人工视觉确认，否则报告必须显示“视觉/样品待人工确认”，推荐对象只能叫“优先 review 候选”，不能叫“已确认供应商”。
- 所有数据源 Evidence Packet 必须写入 `execution_provenance`。若是历史导入、脚本补包或主流程降级，也要明确标注，禁止留空或伪装成子 Agent 执行。
- VOC 口径以“主要评论地区”判断用户市场，不以“采集入口站点”判断。若美国站入口只能看到少量评论，可以从其他站点入口采集，但报告必须显示采集入口和主要评论地区；只有当主要评论地区与目标市场不匹配或占比不足时，才建议按目标站补采。

## 固定产物

所有产物必须落在本轮 run 的 `analysis/` 目录：

| 文件 | 用途 |
|---|---|
| `analysis_report.html` | 主报告，给运营直接 review |
| `analysis_report.xlsx` | 表格版，给运营筛选路线、竞品、关键词、1688 候选和待填利润字段 |
| `analysis_evidence_packet.json` | 主 Agent 综合判断结构化证据，供 Stage 8/9 继续读取 |
| `report_writer_narrative.json` | 可选但推荐，由 Report Writer Agent 生成用户可读叙事；脚本只负责渲染和兜底 |
| `delivery_qa_result.json` | QA Agent 对报告完整性、证据边界和越权问题的检查结果 |

如果项目仍保留旧的 `final_report/*` 五件套，Stage 7 可以兼容生成，但用户 review 的主入口必须是 `analysis_report.html`。

## 数据源映射

| 数据源 | 负责 Agent | 报告用途 |
|---|---|---|
| Sorftime MCP | Search Demand Agent | 市场实时验证、类目混池、关键词需求、竞品流量词、自然位、长尾词、热销特征、1688 粗采购信号 |
| 卖家精灵 | Market Structure Agent | Top100、销量、价格带、评论门槛、新品信号、ABA、关键词反查 |
| 评论 VOC | VOC Evidence Agent | 差评痛点、好评驱动、痛点到规格/测试项映射 |
| 1688 插件 / Sorftime 1688 | Supply Chain Agent | 采购价区间、候选款/候选供应商、可供应形态、混池/低质样本、可承接规格 |
| 主 Agent | Lead Operator Agent | 资深亚马逊运营专家综合判断，不复述数据流水账 |
| 报告生成 | Report Writer | 将 professional analysis memo + evidence 写成通俗、有结论、有数据支撑、有下一步动作的用户报告 |
| QA | Delivery QA Agent | 检查文件、来源、越权、硬缺口和报告可读性 |

用户版 `analysis_report.html` / `analysis_report.xlsx` 不展示 Agent、MCP、tool、internal execution、spawn、packet 等内部执行术语。需要表达来源时，用“市场数据”“搜索需求数据”“评论 VOC”“供应链数据”“利润/合规复核”等用户能理解的名称。

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
   - 必须来自 Lead Operator 的 professional analysis memo，并综合 Sorftime、卖家精灵、VOC、1688 和全部 evidence。
   - 必须回答：需求是否真实、竞争是否能切入、产品形态是否清晰、VOC 能否转规格、供应链是否能承接、利润/合规缺口是什么、为什么现在还不能直接强 Go、用户 review 时看什么。
   - 事实、推断、风险、待补动作分开写。
   - 用户版必须可扫读：长段落要拆成“结论 / 证据 / 风险 / 动作”或类似结构，不允许整块堆叠专业长文。

3. **证据边界**
   - 说明本轮已经由系统/Agent 完成了哪些数据复核。
   - 说明哪些能力仍未完成，例如 1688 图片视觉、样品、利润、FBA、合规、系统侧来源记录、VOC 评论地区覆盖。
   - 这部分是通用报告结构，不得写死成当前类目。

4. **Sorftime 市场验证**
   - 类目和混池判断。
   - Top100 体量、价格带、集中度。
   - 核心词、长尾词、CPC、季节性、竞品流量词。
   - 代表 ASIN 的自然位/流量入口。

5. **卖家精灵关键词与竞品验证**
   - Top100、ABA、关键词反查、搜索结果。
   - 新品信号、评论门槛、价格带与卖家结构。
   - 与 Sorftime 冲突或互相印证的地方。

6. **VOC 差评痛点与规格翻译**
   - 高频痛点。
   - 正向购买理由。
   - 痛点到产品规格、样品测试项、供应链验证项的映射。

7. **1688 供应链匹配**
   - 推荐优先看的候选款/候选供应商。
   - 候补候选和剔除原因。
   - 采购价、MOQ、规格、图片/详情页证据、链接。
   - 能承接哪些 VOC 规格，哪些仍缺证据。
   - 章节名称和文案必须区分“结构化预筛 / 优先 review 候选”和“视觉确认 / 样品确认”。视觉未完成时，不能写成供应商已复核完成。

8. **多数据源交叉判断**
   - 每个数据源的证据强度、关键发现、缺口。
   - 资深运营如何从多源证据得到当前结论。

9. **人工 Review 指南**
   - 运营应优先打开哪些 ASIN、关键词、1688 链接。
   - 看哪些字段、哪些图片、哪些混池迹象。
   - 不要求运营回传供应商资料；回传只作为可选增强。

10. **利润回填说明**
   - Stage 8 的输入文件：`profit_review_template.xlsx`。
   - 需要回填字段：目标售价、采购价、MOQ、包装尺寸、单套重量、头程/FBA、入库配置费、广告费率、退货/损耗、合规/专利备注。
   - 未回填前只能 `Wait/谨慎继续/待补`，不能强 Go。

11. **下一步进入利润/FBA/合规的条件**
    - 运营 review 完报告。
    - 认可 1-3 个候选产品形态或供应链方向。
    - 利润关键字段可填写或已回填。
    - 没有明显合规/侵权硬阻断。

## Excel 报表结构

`analysis_report.xlsx` 至少包含这些 Sheet：

| Sheet | 内容 |
|---|---|
| `Executive Summary` | 结论、机会、风险、下一步、利润待补字段 |
| `Route Matrix` | 路线、角色、证据强度、市场/VOC/供应链状态、资深运营判断 |
| `Sorftime` | 类目、关键词、长尾词、竞品流量词、自然位、热销特征 |
| `SellerSprite` | Top100、ABA、关键词反查、竞品池摘要 |
| `VOC Spec Map` | 痛点、频次、证据评论、规格/测试映射 |
| `1688 Candidates` | 候选款/供应商、价格、MOQ、链接、规格、推荐动作、剔除原因 |
| `Evidence Handoff` | 各数据源 evidence 的关键发现、缺口、置信度 |
| `Profit Backfill` | Stage 8 需要运营填写的字段和来源提示 |

## `analysis_evidence_packet.json`

固定结构：

```json
{
  "packet_id": "analysis_evidence_packet",
  "agent_role": "Lead Operator Agent",
  "persona": "资深亚马逊运营专家",
  "stage": "integrated_precheck",
  "verdict": "继续看 | 谨慎继续 | 暂缓",
  "one_sentence_reason": "",
  "source_packets": [],
  "professional_analysis_memo": {
    "demand_context": "",
    "market_context": "",
    "voc_context": "",
    "supply_chain_context": "",
    "profit_compliance_gaps": "",
    "conclusion_rationale": "",
    "next_actions": []
  },
  "lead_operator_analysis": {
    "market_demand": "",
    "competition_entry": "",
    "product_shape": "",
    "voc_to_spec": "",
    "supply_chain_fit": "",
    "why_not_strong_go_yet": ""
  },
  "route_judgment": [],
  "recommended_review_targets": [],
  "profit_backfill_fields": [],
  "blocking_gaps": [],
  "next_stage_entry_conditions": [],
  "confidence": "high | medium | low",
  "lineage": []
}
```

## 缺证据表达

- 系统没有采集、解析或交叉验证到：写“系统侧待补”。
- 需要用户打开 ASIN、关键词结果页、1688 链接、图片、详情页或评论上下文目视判断：写“人工 review 待补”。
- 只有用户确实未提供必要输入、文件或确认时，才写“用户输入缺失”。
- 禁止把系统侧缺口包装成“请用户补基础数据”；用户下一步应是 review 报告、回填利润/合规字段或按报告打开重点链接核验。

## `report_writer_narrative.json`

该文件由 Report Writer Agent 生成，属于表达层。它读取 Lead Operator 的 professional analysis memo 和所有 Evidence Packet，把分析写成用户能看懂的报告叙事。它不新增事实数字，不改变主 Agent 的商业结论。

```json
{
  "source": "report_writer_agent",
  "headline": "资深运营预审结论：谨慎继续",
  "one_sentence": "给用户看的通俗一句话结论",
  "principle": "为什么现在这样判断",
  "analysis_cards": [
    {
      "title": "市场是否值得继续看",
      "body": "带数据支撑的运营解释"
    },
    {
      "title": "产品机会在哪里",
      "body": "带 VOC/竞品/供应链依据的解释"
    },
    {
      "title": "供应链现在能说明什么",
      "body": "说明候选款能证明什么、不能证明什么"
    },
    {
      "title": "为什么还不能直接立项",
      "body": "利润/FBA/合规/样品/人工 review 等卡点"
    }
  ],
  "review_reader_note": "告诉用户先看哪里、怎么读这份报告"
}
```

Report Writer Agent 禁止：

- 硬编码当前商品、ASIN、关键词、供应商或类目。
- 展示 Agent、MCP、tool、execution、page 参数等内部术语。
- 把缺失证据误写成需要用户补基础数据。
- 为了文案顺滑而编造 Evidence Packet 中不存在的数字。

## 禁止项

- 禁止把某个品类、ASIN、供应商、关键词写进通用模板。
- 禁止只输出供应链报告，忽略 Sorftime、卖家精灵和 VOC。
- 禁止把各 Agent 结论简单拼接成流水账；必须由主 Agent 给出综合运营判断。
- 禁止在利润/FBA/合规未回填时写强 Go。
- 禁止把供应商问询和资料回传做成强制流程；只能作为可选补充。
- 禁止在用户版报告展示 Agent、MCP、tool、internal execution、spawn、packet 等内部执行术语。
