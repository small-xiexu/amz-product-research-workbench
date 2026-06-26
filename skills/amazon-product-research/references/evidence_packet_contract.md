# Evidence Packet 契约

Evidence Packet 是多 Agent 协作的交接单位。每个数据源专家 Agent 只输出证据包，不直接给最终进入结论。资深亚马逊运营主 Agent 只能基于这些证据包和 `report_data.json` 做综合市场机会判断。

## 通用结构

```json
{
  "packet_id": "market_structure_evidence",
  "packet_version": "market-precheck-v2",
  "agent_role": "Market Structure Agent",
  "source_scope": ["SellerSprite"],
  "created_at": "YYYY-MM-DD",
  "input_refs": [
    {
      "type": "file",
      "path": "runs/<run_id>/import_manifest.json"
    }
  ],
  "execution_provenance": {
    "executed_by_agent": true,
    "agent_role": "Market Structure Agent",
    "execution_mode": "real_subagent_spawn",
    "subagent_id": "",
    "note": ""
  },
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
| `execution_provenance` | 是 | 说明该包由真实子 Agent、主 Agent 串行降级、脚本生成或历史导入；用于 QA 检查证据来源 |
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
| `integrated_operator_judgment` | Senior Operator Agent | 基于 P6 多评价结果输出最终综合判断，不生成报告 |
| `report_data` | 脚本 `build_analysis_report.py` 生成 seed，Report Generation Agent 增强 | 唯一数据中枢，所有事实含 `source_path` 溯源，供 HTML 和 XLSX 使用 |
| `delivery_qa_result` | Delivery QA Agent | 最终交付物、校验结果和证据边界 |

## 通用业务对象

以下对象可出现在多个 Evidence Packet 中。字段名必须稳定，便于报告、QA 和脚本回表；缺字段时必须在 `data_gaps` 写清影响。

### `reference_asin_pool`

用于说明本轮参考竞品从哪里来、为什么相似、属于哪条路线。不能只列 ASIN。

| 字段 | 必填 | 说明 |
|---|---|---|
| `asin` | 是 | 参考 ASIN |
| `route_ref` | 是 | 所属产品路线 |
| `asin_role` | 是 | `primary_reference` / `high_sales_benchmark` / `new_release_sample` / `premium_benchmark` / `painpoint_reference` / `excluded_reference` |
| `similarity_reason` | 是 | 与目标路线相似或被排除的原因 |
| `source_type` | 是 | `seller_sprite_search` / `seller_sprite_top100` / `sorftime_search_results` / `sorftime_category_report` / `manual_review` |
| `source_refs` | 是 | 文件、Sheet、行号、工具调用 ID 或 URL |
| `category_path` | 否 | 可见类目路径 |
| `category_role` | 否 | 大类 / 小类 / 混池 / 对照 / 排除 |
| `price` | 否 | 当前价或价格区间 |
| `monthly_sales` | 否 | 月销量 |
| `rating_count` | 否 | 评论数 |
| `confidence` | 是 | `high` / `medium` / `low` |
| `lineage` | 是 | 可回表证据 |

### `category_landscape`

**多类目全景（Stage 1 / Stage 7 必填）**。一个品类可能分布在多个亚马逊细分类目下，必须全部列出，不能只看一个类目就出结论。

| 字段 | 必填 | 说明 |
|---|---|---|
| `category_name` | 是 | 亚马逊细分类目名 |
| `node_id` | 是 | 类目 nodeId |
| `category_path` | 否 | 所属上级类目路径 |
| `top100_monthly_sales` | 是 | 该类目 Top100 月销量 |
| `top100_monthly_revenue` | 是 | 该类目 Top100 月销额 |
| `product_count_in_category` | 是 | 该类目下目标品类（不是总品数）的竞品数 |
| `representative_asins` | 是 | 该类目下目标品类的代表 ASIN 及月销 |
| `avg_price` | 否 | 类目均价 |
| `category_fit` | 是 | `primary_battlefield`（主战场） / `secondary_battlefield`（次要战场） / `miscategorized`（错误挂载） / `mixed_excluded`（混杂排除） |
| `reason` | 是 | 1-2 句判断理由 |
| `lineage` | 是 | 数据来源（Sorftime category_report / product_detail ASIN 反查 / 卖家精灵类目映射） |

### `category_candidates`

用于分开表达候选大类、小类、混池、对照和排除类目。关键词映射类目只能是候选来源之一。

| 字段 | 必填 | 说明 |
|---|---|---|
| `category_name` | 是 | 类目名 |
| `node_id` | 否 | Amazon / Sorftime nodeId |
| `category_path` | 否 | 类目路径 |
| `category_role` | 是 | `broad_market` / `subcategory_market` / `mixed_pool` / `benchmark` / `excluded` |
| `source_type` | 是 | `asin_category_mapping` / `category_search` / `seller_sprite_market` / `keyword_mapping` / `manual_review` |
| `source_refs` | 是 | 对应 ASIN、关键词、文件、Sheet 或工具调用 |
| `matched_asin_count` | 否 | 命中的参考 ASIN 数 |
| `matched_asins` | 否 | 命中的参考 ASIN |
| `evidence_strength` | 是 | `strong` / `medium` / `weak` |
| `risk_tags` | 否 | 混池、类目过宽、品牌垄断、样本不足等标签 |
| `recommended_use` | 是 | `analyze_capacity` / `analyze_entry` / `benchmark_only` / `exclude` / `needs_manual_review` |
| `lineage` | 是 | 可回表证据 |

### `asin_category_mapping`

用于把参考 ASIN 反推到大小类目，避免只靠关键词决定类目。

| 字段 | 必填 | 说明 |
|---|---|---|
| `asin` | 是 | 参考 ASIN |
| `route_ref` | 是 | 所属产品路线 |
| `category_path` | 是 | 类目路径或可见类目文本 |
| `node_id` | 否 | 类目节点 |
| `bsr_rank` | 否 | BSR 或类目排名 |
| `category_role` | 是 | 大类 / 小类 / 混池 / 对照 / 排除 |
| `mapping_source` | 是 | 卖家精灵、Sorftime、页面目视或脚本解析 |
| `conflict_note` | 否 | 与关键词映射或其他 ASIN 类目冲突时说明 |
| `lineage` | 是 | 可回表证据 |

### `keyword_pool_by_role`

用于表达系统自动整理出的运营式关键词池。必须保留来源，不得把系统扩展词写成人工精选词。

| 角色 | 中文名 | 用途 |
|---|---|---|
| `main_traffic` | 主要流量词 | 判断大入口是否有量；不能单独定义市场 |
| `conversion_quality` | 转化优质词 | 优先验证点击/转化更接近目标路线的词 |
| `traffic` | 流量词 | 观察流量相关性和混池边界 |
| `precise_long_tail` | 精准长尾词 | 验证小类目、规格、场景或 Listing 方向 |
| `mixed_or_excluded` | 混池/排除词 | 记录不进入主判断的词和排除原因 |

每个关键词对象至少包含 `keyword`、`keyword_role`、`source_type`、`source_refs`、`route_refs`、`matched_asin_count`、`monthly_search_volume`、`cpc`、`competition_count`、`click_or_conversion_signal`、`mix_pool_tags`、`recommended_action`、`reason` 和 `lineage`。

### `price_band_opportunity`

价格机会必须按价格段表达，禁止只写均价。

| 字段 | 必填 | 说明 |
|---|---|---|
| `category_ref` | 是 | 所属候选类目或路线 |
| `price_band` | 是 | 价格段 |
| `product_count` | 是 | 商品数 |
| `sales_share` | 否 | 销量占比 |
| `revenue_share` | 否 | 销售额占比 |
| `median_rating_count` | 否 | 评论中位数 |
| `top3_product_share` | 否 | Top3 商品占比 |
| `top3_brand_share` | 否 | Top3 品牌占比 |
| `new_release_count` | 否 | 新品样本数 |
| `low_review_winner_count` | 否 | 低评论仍有销量的样本数 |
| `opportunity_level` | 是 | `strong` / `watch` / `weak` |
| `reason` | 是 | 机会或风险解释 |
| `lineage` | 是 | 可回表证据 |

### `new_release_opportunity`

用于判断小类目是否适合推新品榜。

| 字段 | 必填 | 说明 |
|---|---|---|
| `category_ref` | 是 | 小类目或路线 |
| `new_release_count` | 否 | 新品数量 |
| `new_release_sales_share` | 否 | 新品销量占比 |
| `new_release_revenue_share` | 否 | 新品销售额占比 |
| `low_review_samples` | 否 | 低评论有销量样本 |
| `launch_period` | 否 | 新品时间窗口 |
| `ranking_entry_signal` | 是 | `strong` / `watch` / `weak` / `unknown` |
| `risk_tags` | 否 | 评论门槛高、头部垄断、价格带不匹配、样本不足等 |
| `lineage` | 是 | 可回表证据 |

## 执行来源要求

所有 Agent / 脚本产出的 Evidence Packet 必须写入 `execution_provenance`。`executed_by_agent=false` 并不代表证据不可用，但必须说明来源模式和影响。

当运行环境支持子 Agent 且用户要求多 Agent 时，Stage 7 的 `search_demand_evidence` 应由 Search Demand Agent 真实子 Agent 产出。主 Agent 可以在 Stage 1 快探中直接调用 Sorftime，但 Stage 7 Sorftime 深扫不能静默由主 Agent 代跑；如因工具不可用降级，必须在 `execution_provenance.execution_mode = "serial_fallback"` 和 `data_gaps` 中说明，并由 QA 标记为待补。

Route Matrix、workflow_state 等非 Evidence Packet 文件不强制 `executed_by_agent=true`；若被 `report_data.json` 的 `source_path` 引用，应在来源审计里标明为 `workflow_state`、`route_matrix`、`legacy_import` 或 `script_generated`。

## 越权规则

- 专家 Agent 不输出 `final_decision`、`route_priority`。
- 专家 Agent 可以写 `evidence_strength`，不能写“建议立项”。
- 主 Agent 不新增原始数字；需要数字时必须引用 Evidence Packet、MCP 快照、结构化中间文件或 `report_data.json`。
- Stage 7 的内部 `analysis_packet` 可以使用 `继续看 / 谨慎继续 / 暂缓` 短判词；写入 `report_data.json` 时必须映射为 `hero.verdict` 的正式三值，并说明数据缺口和结论边界。
- QA Agent 不改商业判断，只判断是否有证据、是否违反边界、是否可交付。
- 任一证据包 `confidence=low` 时，主 Agent 必须在最终判断里说明影响。

## 缺证据处理

缺证据不能静默跳过，必须写入 `data_gaps`：

| 场景 | 写法 |
|---|---|
| Top100 不完整 | 标记为阻塞，不进入正式深挖 |
| 评论样本不足 | 输出需要补抓的 ASIN 和目标评论数 |
| 数据源冲突 | 同时列出冲突事实，交由主 Agent 解释或标待验证 |
| 小类边界不清 | 标记候选类目、混池词和需要补查的代表 ASIN |
| 关键词证据不足 | 标记缺少主查词、长尾词、反查词或 ABA 交叉验证 |

## Stage 7 市场机会特殊要求

Stage 7 生成 `<中文品名>_分析报告.html` 前，至少要有以下证据结构；如果某项缺失，必须在 `data_gaps` 和 HTML 报告中说明影响：

| 证据 | 必备内容 |
|---|---|
| `search_demand_evidence` | 候选类目、参考 ASIN 流量词、竞品关键词、运营式关键词池、自然位、热销特征、类目淡旺季、混池风险 |
| `market_structure_evidence` | 参考 ASIN 池、候选大/小类、ASIN 类目反推、Top100、ABA、关键词反查、价格带机会、评论门槛、新品机会 |
| `voc_evidence` | 高频痛点、正向驱动、痛点到规格/测试映射 |
| `report_data` | 主 Agent 详细综合分析、参考 ASIN 和类目选择、小类目机会、关键词分层解释、市场机会结论、人工 review 指南、下一步补数条件 |

Stage 7 真实多 Agent 执行时还必须满足：

- `search_demand_evidence.execution_provenance.executed_by_agent = true`
- `search_demand_evidence.execution_provenance.execution_mode = "real_subagent_spawn"`
- `search_demand_evidence.execution_provenance.agent_role = "Search Demand Agent"`

`report_data.json` 必须声明：

- `packet_id = "report_data"`
- `run_id` 与 run 目录名一致
- `generated_at` 使用 ISO 时间戳
- `hero.verdict` 只能是 `建议进入小批量验证`、`建议补齐数据后再评估` 或 `建议暂停推进`
- 顶层 `evidence_sources` 列出全部读取的 Evidence Packet 和关键输入文件，至少包含 `name`、`path`、`exists`、`packet_id`、`confidence`、`execution_mode`、`provenance_note`
- `hero.lead_analysis` 明确回答市场需求、竞争切入、产品形态、VOC 到规格和为什么还不能强结论
- `hero.evidence_sources` 列出支撑 Hero 判断的来源名称
- `category_panorama.categories[]` 使用 `category_landscape` 统一字段：`category_name`、`node_id`、`category_path`、`top100_monthly_sales`、`top100_monthly_revenue`、`product_count_in_category`、`representative_asins`、`avg_price`、`category_role`、`reason`、`lineage`
- `data_sources` 列出本轮报告读取的数据包、关键输入文件、数据缺口和口径说明
- 11 个必填板块：`hero`、`category_panorama`、`data_sources`、`competitors`、`pain_points`、`price_bands`、`keywords`、`risks`、`advantages`、`gonogo_conditions`、`next_steps`
- 所有事实值必须标注 `source_path`，可追溯到证据包具体字段

## 与运行时和现有产物关系

Evidence Packet 是真实子 Agent 和主 Agent 的交接格式；当运行环境不支持子 Agent 时，也作为主 Agent 串行执行专家口径的输出格式。它不改变既有 CLI 的基础产物，但允许在对应目录落成独立 JSON 文件：

- 代码层已有 `build_research_data_packet()` 负责结构化数据。
- `report_data.json` 是正式报告唯一事实源。
- 子 Agent 或主 Agent 串行执行时，均按 Evidence Packet 组织证据。
- 调度规则见 `references/multi_agent_dispatch.md`。
