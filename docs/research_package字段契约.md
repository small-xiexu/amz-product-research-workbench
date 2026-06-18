# research_package 字段契约

`research_package.json` 是正式报告、Dashboard、Excel、Web 页面和多 Agent 协作的唯一事实源。本项目不新增平行 `payload_v2`；所有下游展示都从 `research_package.json` 投影，不从 Markdown/HTML 反解析事实。

## 生成边界

| 层级 | 负责方 | 产出 | 允许内容 | 禁止内容 |
|---|---|---|---|---|
| 数据包层 | 脚本 / Data Pipeline | `build_research_data_packet()` | 清洗、补全、标注、聚合、数值统计、lineage | Go/No-Go、策略建议、商业判断文本 |
| 专家证据层 | 数据源专家 Agent | Evidence Packet | 单源事实、派生指标、置信度、缺口、待补动作 | 最终决策、路线优先级、跨源结论 |
| 洞察层 | Lead Operator Agent | `ai_analysis`、`decision_review`、`status_card` 等 | 综合判断、路线优先级、行动建议、风险解释 | 捏造数据包中不存在的数字 |
| 交付层 | Report Renderer / QA | report、HTML、Dashboard、Excel | 展示、回表、校验、证据边界检查 | 新增事实、覆盖主 Agent 判断 |

## 顶层字段

| 字段 | 类型 | 来源 | 用途 | 最低要求 |
|---|---|---|---|---|
| `metadata` | object | 脚本 | 任务身份、站点、数据源 | 必须含 `site`、`seed_keyword_or_category`、`data_sources` |
| `constraints` | object | 运营输入 / 脚本 | 禁区、偏好、边界 | 缺失时报告必须标待补 |
| `raw_sources` | object | 脚本 | 原始来源引用 | 不存大段正文，只存来源、路径、摘要 |
| `normalized_tables` | object | 脚本 | 候选、Top100、VOC 证据等标准表 | `candidate`、`top100` 必须存在 |
| `market_analysis` | object | 脚本 + 数据包层 | 市场规模、价格带、品牌集中度 | 必须含 `market_size`、`price_band`、`brand_concentration` |
| `market_structure` | object | 脚本 | 属性定义、Top100 打标、分布、交叉分析 | 正式深挖需包含属性分布和交叉分析 |
| `keyword_analysis` | object | 脚本 / Sorftime Agent | 搜索需求、趋势、ABA/Sorftime 信号 | 冲突时必须保留冲突说明 |
| `competitor_selection_logic` | array | 脚本 + 主 Agent | 竞品选择逻辑 | 非空；每项必须有 ASIN 和选择理由 |
| `competitor_pool` | object | 脚本 | Top10、新品、结构补充竞品 | 竞品角色要可回表 |
| `voc_analysis` | object | VOC Agent | 评论范围、痛点、亮点、证据 | 接入评论包时必须含 `summary` |
| `profit_reference` | object | 脚本 / 利润模板 | 利润数字、成本拆分、1688 粗估 | 未回填时必须形成 gating reason |
| `return_risk` | object | 脚本 / 模板 | 退货率和退货风险 | 缺失时标待补 |
| `ip_screening` | object | 人工模板 | 知产初筛 | 不替代专业结论 |
| `compliance_screening` | object | 人工模板 | 合规认证预判 | 不替代专业结论 |
| `ip_compliance_review` | object | 人工模板 | 知产/合规复核汇总 | 未回填时禁止强 Go |
| `decision_review` | object | Lead Operator Agent | 评分卡、事实/推断/待补/行动 | 必须含 `go_nogo_scorecard` |
| `status_card` | object | Lead Operator Agent | 当前状态、理由、下一步 | 报告首章和摘要使用 |
| `ai_analysis` | object | Lead Operator Agent | 资深运营综合分析 | `persona` 必须是资深亚马逊运营专家口径 |
| `workflow_trace` | object | 交互流程 | 暂停点、运营确认、决策记录 | 交互流程启用时必须回表 |

## 关键字段契约

### metadata

```json
{
  "candidate_id": "cand-001",
  "candidate_pool_id": "pool-001",
  "site": "US",
  "seed_keyword_or_category": "hands free dog leash",
  "product_shape": "免手持宠物牵引绳",
  "data_sources": ["卖家精灵", "Sorftime MCP", "评论插件", "1688 插件"]
}
```

约束：

- `data_sources` 必须是非空数组。
- 报告标题只使用清洗后的 `seed_keyword_or_category` / 产品方向，不把“测试、验证、MCP、1688、UI”等流程词放进标题。
- Web 页面可直接读取 `site`、`seed_keyword_or_category`、`product_shape` 作为首屏上下文。

### market_analysis

必须回答“市场大不大、价格带在哪、头部是否集中”：

| 字段 | 含义 |
|---|---|
| `market_size` | 市场规模文本或结构化摘要 |
| `price_band` | 主力价格带、均价或区间 |
| `brand_concentration` | Top 品牌/卖家集中度 |
| `seller_concentration` | 卖家结构或中国卖家占比 |
| `new_listing_ratio` | 新品占比/新品友好度 |
| `return_rate` | 退货率或待补状态 |
| `sorftime_category_report` | Sorftime 类目快照，保留 nodeId、样本数、均价、新品等 |

### market_structure

必须承接 P28 的脚本化能力：

| 字段 | 含义 |
|---|---|
| `attribute_definitions` | 属性维度定义和规则 |
| `parsed_top_products` / `top_products` | Top 商品打标结果 |
| `pending_label_items` | 低置信度或待人工确认标签 |
| `attribute_distributions` | 单维分布，报告“属性分布”使用 |
| `cross_analysis` | 交叉矩阵和缺口 |
| `opportunity_judgments` | 真机会/伪机会/待验证及下一步 |
| `data_quality` | Top100 完整性、重复、缺字段、异常值 |
| `lineage` | 聚合数字来源 |

约束：

- 属性打标低置信度不能静默当事实。
- 交叉分析里的空白/薄供给必须解释原因，不能只标状态。
- `opportunity_judgments` 是“机会证据判断”，最终 Go/Wait/No-Go 仍由 `decision_review` 承担。

### competitor_selection_logic

每项建议结构：

```json
{
  "asin": "B0EXAMPLE01",
  "brand": "Brand A",
  "title": "Product title",
  "competitor_type": "量级标杆",
  "selection_reason": "Top 销量且覆盖主力价格带",
  "covered_dimensions": ["价格带", "形态", "功能"],
  "price_usd": 29.99,
  "monthly_units": 1200,
  "rating": 4.4,
  "rating_count": 860
}
```

约束：

- 必须非空。
- 至少覆盖量级标杆、近半年新品、功能差异、价格带、痛点参考中的多类角色。
- VOC ASIN 批次应能回到这里或 `competitor_pool`。

### voc_analysis

接入评论插件时必须含 `summary`：

```json
{
  "summary": {
    "review_count": 120,
    "asin_count": 6,
    "low_rating_count": 32,
    "media_review_count": 8
  },
  "pain_points": [],
  "highlights": [],
  "opportunity_hypotheses": []
}
```

约束：

- 每个痛点必须能追溯到 `review_id`、ASIN、评分、原文片段。
- 每个痛点维度必须映射到产品规格或供应商验证动作；不能映射时标“待转化为产品规格”。
- VOC Agent 不直接给 Go/No-Go。

### profit_reference

必须区分“1688 粗估”和“运营利润模板回填”：

| 字段 | 含义 |
|---|---|
| `supply_chain_signal` | 1688 中国站 RMB/CNY 采购价信号，只作粗估 |
| `cost_breakdown` | 运营回填后的成本拆分 |
| `base_fba_gross_profit` | 基础 FBA 毛利 |
| `post_ads_returns_gross_profit` | 扣广告/退货后毛利 |
| `missing_fields` | 未回填字段 |
| `status` | 已复核 / 待补 |

约束：

- 1688 信号只能来自 `1688.com` RMB/CNY 样本。
- 未回填关键利润字段时，`decision_review.go_nogo_scorecard` 必须受 gating 限制。

### decision_review

建议结构：

```json
{
  "facts": [],
  "inferences": [],
  "missing_inputs": [],
  "action_items": [],
  "risk_matrix": [],
  "go_nogo_scorecard": {
    "decision": "WAIT",
    "weighted_score": 6.8,
    "gating_reasons": ["利润未回填", "知产/合规未复核"],
    "dimensions": {
      "市场规模": {"score": 8, "weight": 0.15, "note": "Top100 月销量充足"},
      "利润可行性": {"score": 0, "weight": 0.2, "note": "待回填"}
    }
  }
}
```

合法结论：

- `GO`
- `CONDITIONAL GO`
- `HOLD`
- `WAIT`
- `NO-GO`

约束：

- 利润或合规未回填时不能强 Go。
- `facts` 和 `inferences` 必须分开。
- 评分卡数字必须能追溯到数据包或 Evidence Packet。

### ai_analysis

主 Agent 洞察字段，必须以资深亚马逊运营负责人视角输出：

| 字段 | 含义 |
|---|---|
| `persona` | 固定为资深亚马逊运营专家/负责人口径 |
| `data_source_scope` | 本轮综合了哪些数据源 |
| `decision_principle` | 决策原则，尤其是 gating 限制 |
| `thesis` | 一句话综合判断 |
| `insights` | 市场、VOC、供应链、运营卡点等洞察 |
| `product_route_matrix` | 产品路线矩阵摘要 |
| `route_deep_dive_plan` | 路线级小深挖计划 |

约束：

- 可以做商业判断，但不得新增未来源的数字。
- 必须说明哪些证据是事实，哪些是推断或待验证。
- 必须覆盖市场进入、VOC/产品规格、供应链承接和运营卡点。

## Evidence Packet 对应关系

| Evidence Packet | 写入或支撑字段 | 产出 Agent |
|---|---|---|
| `market_structure_evidence` | `market_analysis`、`market_structure` | Market Structure Agent |
| `search_demand_evidence` | `keyword_analysis`、`normalized_tables.candidate.demand_evidence` | Search Demand Agent |
| `voc_evidence` | `voc_analysis`、`normalized_tables.voc_evidence` | VOC Evidence Agent |
| `supply_chain_evidence` | `profit_reference.supply_chain_signal`、`raw_sources.supply_chain` | Supply Chain Agent |
| `profit_compliance_evidence` | `profit_reference`、`ip_compliance_review`、`return_risk` | Profit Compliance Agent |
| `integrated_operator_judgment` | `decision_review`、`status_card`、`ai_analysis` | Lead Operator Agent |
| `delivery_qa_result` | `workflow_summary`、校验输出 | Delivery QA Agent |

## 12 章报告映射

| 报告章节 | 主要字段 | Excel 回表 |
|---|---|---|
| Executive Summary / 当前结论 | `status_card`、`decision_review`、`report_summary`、`ai_analysis` | `状态卡`、`Go_No-Go评分卡` |
| 数据来源与口径 | `metadata`、`raw_sources`、`workflow_trace` | `数据来源说明`、`调研边界` |
| 候选方向与边界 | `metadata`、`constraints`、`normalized_tables.candidate` | `调研边界`、`产品路线矩阵` |
| 市场结构与数据质量 | `market_analysis`、`market_structure.data_quality` | `市场结构`、`Top100原始明细`、`数据质量检查` |
| 关键词与需求信号 | `keyword_analysis`、`demand_evidence` | `市场结构`、`数据来源说明` |
| 产品属性分布与交叉分析 | `market_structure.attribute_distributions`、`cross_analysis` | `属性定义`、`Top商品打标`、`属性分布`、`属性交叉分析` |
| 竞品池与竞品选择逻辑 | `competitor_selection_logic`、`competitor_pool` | `竞品选择逻辑`、`竞品池` |
| 评论 VOC 与真实痛点 | `voc_analysis`、`normalized_tables.voc_evidence` | `评论VOC`、`VOC证据` |
| 利润复核 | `profit_reference`、`operator_inputs` | `利润参考结果`、`利润成本拆分`、`供应链粗估` |
| 知产/合规/退货风险 | `return_risk`、`ip_screening`、`compliance_screening` | `退货风险`、`知产合规复核` |
| Go/Wait/No-Go 决策检查 | `decision_review`、`status_card` | `Go_No-Go评分卡`、`决策检查`、`风险矩阵` |
| 下一步动作与证据附录 | `status_card`、`decision_review`、`workflow_trace` | `状态卡`、`交互决策记录` |

## Web 接入建议

后续 Web 不需要重新定义业务 schema，优先直接消费 `research_package.json`：

- 首屏：`metadata`、`status_card`、`ai_analysis.thesis`
- 市场页：`market_analysis`、`market_structure`
- 路线页：`ai_analysis.product_route_matrix`、`ai_analysis.route_deep_dive_plan`
- 竞品页：`competitor_selection_logic`、`competitor_pool`
- VOC 页：`voc_analysis`
- 供应链/利润页：`profit_reference.supply_chain_signal`、`profit_reference`
- 风险页：`return_risk`、`ip_compliance_review`、`decision_review.risk_matrix`
- 决策页：`decision_review.go_nogo_scorecard`、`status_card.next_step`

Web 只负责交互和展示；不能在前端补造业务事实。
