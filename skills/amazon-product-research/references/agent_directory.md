# Agent 完整目录

亚马逊选品研究流水线共 16 个 Agent 角色，按阶段分层协作。本文档是唯一的 Agent 信息总索引——角色、职责、输入输出、调度规则、越权边界均在此统一定义。

---

## 架构总览

```text
                    ┌──────────────────────────┐
                    │    Stage 2-3 市场快验      │
                    │  SellerSprite Quick (1)   │
                    │  Sorftime Quick     (2)   │  ← 并行
                    └────────────┬─────────────┘
                                 │ gate=continue
                    ┌────────────▼─────────────┐
                    │    Stage 4-5 候选+路线     │
                    │  主 Agent 产出（非 spawn）  │
                    └────────────┬─────────────┘
                                 │
                    ┌────────────▼─────────────┐
                    │    Stage 6 双 MCP 深挖     │
                    │  Market Structure   (3)   │
                    │  Search Demand      (4)   │  ← 并行
                    └────────────┬─────────────┘
                                 │
                    ┌────────────▼─────────────┐
                    │    Stage 7 冲突复核（脚本） │
                    └────────────┬─────────────┘
                                 │
                    ┌────────────▼─────────────┐
                    │    Stage 8 VOC 评论分析    │
                    │  VOC Evidence       (5)   │
                    └────────────┬─────────────┘
                                 │
                    ┌────────────▼─────────────┐
                    │    Stage 9 六维评价         │
                    │  Market Demand      (6)   │
                    │  Competition        (7)   │
                    │  Price Band         (8)   │  ← 6 并行
                    │  VOC Opportunity    (9)   │
                    │  Risk              (10)   │
                    │  Data Quality      (11)   │
                    └────────────┬─────────────┘
                                 │
                    ┌────────────▼─────────────┐
                    │    Stage 10a 深度分析       │
                    │  Route Strategy    (12)   │  ← 并行
                    │  Growth & Risk     (13)   │
                    └────────────┬─────────────┘
                                 │
                    ┌────────────▼─────────────┐
                    │    Stage 10b 决策合成       │
                    │  Lead Operator     (14)   │
                    └────────────┬─────────────┘
                                 │
                    ┌────────────▼─────────────┐
                    │    Stage 11-12 报告生成    │
                    │  Report Generation (15)   │
                    └────────────┬─────────────┘
                                 │
                    ┌────────────▼─────────────┐
                    │    Stage 13 QA 门禁        │
                    │  Delivery QA       (16)   │  ← 强制 spawn
                    └──────────────────────────┘
```

---

## Agent 分类

### 数据采集 Agent（5 个）

负责从 MCP 工具和评论导出中采集原始数据，产出 Evidence Packet。

| # | Agent | 阶段 | 数据源 | 产出 |
|---|---|---|---|---|
| 1 | SellerSprite Quick Agent | 2 | 卖家精灵 MCP | `quick_check/sellersprite_quick_evidence_packet.json` |
| 2 | Sorftime Quick Agent | 2 | Sorftime MCP | `quick_check/sorftime_quick_evidence_packet.json` |
| 3 | Market Structure Agent | 6 | 卖家精灵 MCP | `market_structure/market_structure_evidence_packet.json` |
| 4 | Search Demand Agent | 6 | Sorftime MCP | `search_demand/search_demand_evidence_packet.json` |
| 5 | VOC Evidence Agent | 8 | 评论插件导出 | `review_voc/voc_evidence_packet.json` |

### 评价 Agent（6 个）

负责从单一维度对证据包打分（0-100），输出结构化评价 JSON。

| # | Agent | 阶段 | 输入 | 产出 |
|---|---|---|---|---|
| 6 | Market Demand Evaluation Agent | 9 | Market Structure + Search Demand | `evaluations/market_demand_evaluation.json` |
| 7 | Competition Evaluation Agent | 9 | Market Structure | `evaluations/competition_evaluation.json` |
| 8 | Price Band Opportunity Evaluation Agent | 9 | Market Structure | `evaluations/price_profit_evaluation.json` |
| 9 | VOC Opportunity Evaluation Agent | 9 | VOC Evidence | `evaluations/voc_opportunity_evaluation.json` |
| 10 | Risk Evaluation Agent | 9 | 全部证据 + Conflict Review | `evaluations/risk_evaluation.json` |
| 11 | Data Quality Evaluation Agent | 9 | 全部证据 + MCP Snapshots | `evaluations/data_quality_evaluation.json` |

### 决策 Agent（3 个）

负责跨维度分析和最终判断。Stage 10a 两个并行，10b 独立决策。

| # | Agent | 阶段 | 职责范围 |
|---|---|---|---|
| 12 | Route Strategy Agent | 10a | 路线竞争分析：路线推荐、路线取舍、竞品对标、竞品弱点、价格带解读 |
| 14 | Lead Operator Agent | 10b | 跨维度权衡 + 最终 Go/No-Go 决策 + 合并 10a 深度分析 |

### 报告与质检 Agent（2 个）

| # | Agent | 阶段 | 职责 |
|---|---|---|---|
| 15 | Report Generation Agent | 12 | 增强 report_data.json + 手写 HTML 报告 |
| 16 | Delivery QA Agent | 13 | 数据真实性交叉验证 + 运营判断质量检查 |

---

## 详细定义

### Agent 1-2: 快验 Agent（Stage 2）

#### SellerSprite Quick Agent
- **定义文件**: `agents/market-structure-agent.md`
- **身份**: 卖家精灵 Quick Agent（Market Structure Agent 的快验模式）
- **职责**: 大盘容量、候选类目、Top 产品结构、价格带、集中度、Review 门槛、混池判断
- **输出**: `quick_check/sellersprite_quick_evidence_packet.json`（17 个必填字段）
- **快照**: `mcp_snapshots/sellersprite_quick_snapshot.json`
- **调度**: 与 Sorftime Quick Agent 并行 spawn
- **不可以**: 不写最终 Go/No-Go、不替 Sorftime 判断搜索需求

#### Sorftime Quick Agent
- **定义文件**: `agents/search-demand-agent.md`
- **身份**: Sorftime Quick Agent（Search Demand Agent 的快验模式）
- **职责**: 关键词搜索量、搜索意图匹配、混池判断、候选类目、相似品、类目趋势
- **输出**: `quick_check/sorftime_quick_evidence_packet.json`（17 个必填字段）
- **快照**: `mcp_snapshots/sorftime_quick_snapshot.json`
- **调度**: 与 SellerSprite Quick Agent 并行 spawn
- **不可以**: 不写最终 Go/No-Go、不用关键词搜索量替代市场销量

---

### Agent 3: Market Structure Agent（Stage 6）
- **定义文件**: `agents/market-structure-agent.md`
- **角色**: 资深亚马逊市场结构分析师
- **职责**: 验证参考 ASIN、候选类目、价格带、集中度和新品机会。必须覆盖每条保留路线的参考 ASIN，不能只查主路线所在类目
- **输入**: `mcp_snapshots/sellersprite_deep_snapshot.json`、`candidate_pool.json`、`route_matrix_confirm.json`
- **输出**: `market_structure/market_structure_evidence_packet.json`，包含 14 个必填 section：`reference_asin_pool`、`category_landscape`、`asin_category_mapping`、`market_size_by_category_role`、`price_band_opportunity`、`brand_concentration`、`product_concentration`、`seller_structure`、`new_release_opportunity`、`keyword_competitor_validation`、`route_market_fit`、`top100_quality`、`data_gaps`
- **快照**: `mcp_snapshots/sellersprite_deep_snapshot.json`
- **调度**: 与 Search Demand Agent 并行 spawn。保留路线 > 8 条时启用分片串行
- **强约束**:
  - Top100 不完整必须写入 `data_gaps`
  - 价格机会必须按价格段表达，禁止只写均价
  - 不做 Go/No-Go、不替 Sorftime 判断搜索、不替 VOC 判断痛点

---

### Agent 4: Search Demand Agent（Stage 6）
- **定义文件**: `agents/search-demand-agent.md`
- **角色**: 资深亚马逊搜索需求与流量入口分析师
- **职责**: 围绕参考 ASIN 和候选类目生成运营式关键词池。必须为每条保留路线独立采集关键词数据
- **输入**: `mcp_snapshots/sorftime_deep_snapshot.json`、`candidate_pool.json`、`route_matrix_confirm.json`
- **输出**: `search_demand/search_demand_evidence_packet.json`，包含 11 个必填 section：`reference_asin_inputs`、`category_candidates`、`asin_traffic_terms`、`keyword_pool_by_role`、`keyword_validation`、`category_seasonality`、`organic_keyword_positions`、`hot_product_features`、`seller_sprite_conflicts`、`data_gaps`
- **快照**: `mcp_snapshots/sorftime_deep_snapshot.json`
- **关键词分层规则**:
  - `main_traffic` 主要流量词 — 多 ASIN 覆盖、月搜有量
  - `conversion_quality` 转化优质词 — 反查/ABA 转化信号强
  - `traffic` 流量词 — 有搜索量但意图宽
  - `precise_long_tail` 精准长尾词 — 场景/规格明确
  - `mixed_or_excluded` 混池/排除词 — 指向其他产品形态，不删
- **调度**: 与 Market Structure Agent 并行 spawn

---

### Agent 5: VOC Evidence Agent（Stage 8）
- **定义文件**: `agents/voc-evidence-agent.md`
- **角色**: 资深用户痛点产品经理
- **职责**: 从评论原文中挖掘真实痛点、好评驱动和混池信号。把"用户骂什么/夸什么"翻译成产品规格、样品测试项和 Listing 风险提示
- **输入**: `review_voc/review_voc_package.json`、评论插件导出文件、评价 ASIN 清单、路线矩阵
- **输出**: `review_voc/voc_evidence_packet.json`
- **调度**: 运营导出评论后触发，推荐 spawn
- **强约束**:
  - 痛点必须带 `evidence_refs`（review_id + 原文 quote）
  - 有效评论 < 30 条或低分 < 10 条 → 不强出痛点结论
  - 不把 `excluded_reference` 或混池评论混入主推路线结论
  - 不把 HTML AI 报告当作强证据来源

---

### Agent 6: Market Demand Evaluation Agent（Stage 9）
- **定义文件**: `agents/market-demand-evaluation-agent.md`
- **角色**: 专注市场需求评价
- **核心问题**: 需求是否真实、稳定、足够大
- **输入**: Market Structure + Search Demand 证据包
- **输出**: `evaluations/market_demand_evaluation.json`（0-100 评分 + route_breakdown）
- **调度**: 与其他 5 个 Evaluation Agent 并行 spawn
- **不可以**: 不做 Go/No-Go、不把搜索量当市场体量、不混用大类容量做小类判断

---

### Agent 7: Competition Evaluation Agent（Stage 9）
- **定义文件**: `agents/competition-evaluation-agent.md`
- **角色**: 专注竞争结构评价
- **核心问题**: 市场是否头部垄断、评论门槛是否过高、新品能否进入
- **输入**: Market Structure 证据包
- **输出**: `evaluations/competition_evaluation.json`（0-100 评分 + route_breakdown）
- **不可以**: 不做 Go/No-Go、不把"竞争激烈"一句话带过

---

### Agent 8: Price Band Opportunity Evaluation Agent（Stage 9）
- **定义文件**: `agents/price-profit-evaluation-agent.md`
- **角色**: 专注价格带机会评价
- **核心问题**: 价格带是否健康、目标价格段是否有竞争空间、是否存在低价内卷或溢价窗口
- **输入**: Market Structure 证据包
- **输出**: `evaluations/price_profit_evaluation.json`（0-100 评分 + route_breakdown）
- **不可以**: 不给具体定价，不输出 COGS、FOB、采购价、毛利率、FBA 费用、1688 实际报价等后置落地变量

---

### Agent 9: VOC Opportunity Evaluation Agent（Stage 9）
- **定义文件**: `agents/voc-opportunity-evaluation-agent.md`
- **角色**: 专注 VOC 机会评价
- **核心问题**: 用户痛点能否转化为产品差异化机会
- **输入**: VOC Evidence 证据包
- **输出**: `evaluations/voc_opportunity_evaluation.json`（0-100 评分 + P0/P1/P2 优先级排序）
- **不可以**: 不做 Go/No-Go、不把 VOC 机会等同于市场机会、样本不足不强行出结论

---

### Agent 10: Risk Evaluation Agent（Stage 9）
- **定义文件**: `agents/risk-evaluation-agent.md`
- **角色**: 专注风险评价
- **核心问题**: 合规、季节性、退货率、体积/运费、售后、同质化——六大类结构性风险
- **输入**: 全部证据包 + Data Quality 冲突裁决结果
- **输出**: `evaluations/risk_evaluation.json`（0-100 评分）
- **不可以**: 不做 Go/No-Go、不夸大不在证据中的风险、不自行解读冲突（引用 Data Quality 裁决）

---

### Agent 11: Data Quality Evaluation Agent（Stage 9）
- **定义文件**: `agents/data-quality-evaluation-agent.md`
- **角色**: 评价体系的第一道关 + 冲突裁决唯一出口
- **核心问题**: 样本是否足够、是否混池、冲突如何裁决
- **输入**: 全部证据包 + MCP Snapshots + Conflict Review
- **输出**: `evaluations/data_quality_evaluation.json`（0-100 评分 + `conflict_adjudication`）
- **冲突裁决**: 对 material/blocking 冲突归因并裁决，输出统一口径，下游不再各自解读
- **不可以**: 不做 Go/No-Go、不因数据差直接判死——只说明需要补数

---

### Agent 12: Route Strategy Agent（Stage 10a）
- **定义文件**: `agents/route-strategy-agent.md`
- **角色**: 资深亚马逊选品与竞品策略分析师
- **职责**: 聚焦供给端分析——路线竞争分析、竞品对标、价格带解读。必须回查原始证据
- **输入**: Market Demand / Competition / Price Band 评价 + Market Structure + VOC 证据包 + route_matrix
- **输出**: `analysis/integrated_operator_judgment.json` 的 5 个字段：
  1. `route_recommendation` — 路线优先级 + 理由
  2. `route_tradeoff` — 路线取舍分析
  3. `competitor_benchmark` — 竞品对标（至少 3 个 ASIN）
  4. `competitor_weakness_map` — 竞品弱点地图（有 VOC 原文支撑）
  5. `price_band_analysis` — 价格带分布解读
- **调度**: 与 Growth & Risk Agent 并行 spawn

---

### Agent 13: Growth & Risk Agent（Stage 10a）
- **定义文件**: `agents/growth-risk-agent.md`
- **角色**: 资深亚马逊运营增长与风控分析师
- **职责**: 聚焦需求端和风控端分析。必须回查原始证据
- **输入**: VOC Opportunity / Risk / Data Quality 评价 + Search Demand + Market Structure + VOC 证据包
- **输出**: `analysis/integrated_operator_judgment.json` 的 5 个字段：
  1. `voc_to_spec` — VOC 痛点 → 产品规格推导
  2. `keyword_strategy` — 关键词策略（主攻/可测/否定）
  3. `risk_mitigation` — 风险缓解路径
  5. `validation_roadmap` — 下一步验证路线图
- **调度**: 与 Route Strategy Agent 并行 spawn
- **VOC 降级规则**: 有效评论 < 30 条 → 自动标注 `data_note`，不强推规格结论
- **不可以**: 不做 final_verdict、不涉及路线推荐/竞品对标

---

### Agent 14: Lead Operator Agent（Stage 10b）
- **定义文件**: `agents/lead-operator-agent.md`
- **角色**: 资深亚马逊运营专家——唯一有权输出最终 Go/No-Go 的 Agent
- **职责**: 读取 6 份 Evaluation + Stage 10a 的 10 个深度字段 + 全部证据包，做跨维度权衡
- **输入**: 6 份 `evaluations/*.json` + evaluation_summary + 10a 输出 + 全部证据包
- **输出**: `analysis/integrated_operator_judgment.json` 的**决策摘要字段** + 合并 10a 深度分析：
  - `final_verdict`: `go` / `watch` / `no_go` / `blocked`
  - `verdict_reason`: 综合判断理由（2-4 段，讲清维度间张力）
  - `confidence`: `high` / `medium` / `low`
  - `biggest_opportunity` / `biggest_risk`
  - `required_next_actions` / `operator_constraints`
- **治理规则（不可逾越）**:
  - 任一核心维度目标路线 `blocked` → 该路线不能 Go
  - `data_quality` 目标路线 `blocked` → 只能"补数后再判断"
  - 合规/知产 `blocked` → 所有路线不能 Go
  - Stage 10a 10 字段任一为 `__ai_judgment__` → `blocked`，打回 10a
- **不可以**: 不做 Go/No-Go 以外的深度分析、不机械加分、不省略 10a 字段

---

### Agent 15: Report Generation Agent（Stage 12）
- **定义文件**: `agents/report-generation-agent.md`
- **角色**: 资深亚马逊运营专家报告生成器
- **职责**: 读取 seed + judgment + 证据包 → 增强 `report_data.json`（转录判断，不新增数字） → 手写 `<中文品名>_分析报告.html`
- **HTML 报告结构**: Hero → 类目全景 → 核心竞品 → 用户痛点→产品规格 → 价格带分布 → 关键词与流量策略 → 风险与下一步
- **反捏造红线**: 禁止凭空编造数字、禁止篡改来源数据、禁止模糊溯源、禁止跨源混淆、禁止以偏概全
- **视觉规范**: 绿色 Hero、卡片分区、4 种标签、1100px 宽。遵循 `references/report_design_spec.md`
- **不可以**: 不新增证据包外数字、不把推断当事实、不出现内部术语（Agent/MCP/tool/spawn/packet）

---

### Agent 16: Delivery QA Agent（Stage 13）
- **定义文件**: `agents/delivery-qa-agent.md`
- **角色**: 独立交付质量与数据真实性检查员
- **职责**: 数据真实性三级交叉核对（HTML → report_data → evidence → MCP snapshot）
- **阻断规则（7 条）**: 数字无法溯源、与证据不一致、证据包无此字段、凭空捏造、跨源混淆、空 source_path、HTML/XLSX 不一致
- **质量检查（8 条）**: 首屏结论一致性、竞品判词对齐、痛点有证据、价格带有依据、关键词有搜索量、风险可追溯、下一步可追溯、优势有支撑
- **调度**: **强制独立 spawn，不可降级为 serial_fallback**
- **修复循环**: 最多 3 轮。3 轮后仍 BLOCKED → `progress.json` 标记 `blocked`，需人工介入
- **不可以**: 不重写判断、不改数据、不写 report_data.json/HTML/XLSX、只写 `qa_notes.md`

---

## 调度规则速查

| 阶段 | Agent | 调度方式 | 可降级 |
|---|---|---|---|
| Stage 2 | SellerSprite Quick + Sorftime Quick | **并行 spawn** | 是 |
| Stage 6 | Market Structure + Search Demand | **并行 spawn** | 是（但需标注 serial_fallback） |
| Stage 8 | VOC Evidence | 推荐 spawn | 是 |
| Stage 9 | 6 Evaluation Agents | **推荐并行 spawn** | 是 |
| Stage 10a | Route Strategy + Growth & Risk | **并行 spawn** | 是 |
| Stage 10b | Lead Operator | 推荐 spawn | 是 |
| Stage 12 | Report Generation | 主 Agent 串行（不 spawn） | N/A |
| Stage 13 | Delivery QA | **强制 spawn** | **否**（不可降级） |

---

## 越权规则（硬边界）

| Agent 类别 | 可以做 | 不可以做 |
|---|---|---|
| 数据采集 Agent | 产出证据、标注缺口和置信度 | 不输出 Go/No-Go、不写正式报告 |
| 评价 Agent | 打分（0-100）、列风险、给 route_breakdown | 不输出 Go/No-Go、不重算证据包数字 |
| Lead Operator Agent | 跨维度权衡 + 最终 Go/No-Go | 不生成 HTML、不重做 10a 深度分析 |
| Report Generation Agent | 转录判断、手写 HTML | 不新增证据包外数字、不篡改事实 |
| Delivery QA Agent | 交叉验证、写 qa_notes.md | 不改判断、不改数据、不可降级 |

---

## 相关文档

- `SKILL.md` — 完整流程定义
- `multi_agent_dispatch.md` — 多 Agent 调度规则
- `artifact_contract.md` — 产物目录与契约 schema
- `evidence_packet_contract.md` — Evidence Packet 交接契约
- `report_design_spec.md` — 报告视觉设计规范
- `agents/` — 各 Agent 详细定义文件
