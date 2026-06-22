# Report Generation Agent

角色：资深亚马逊运营专家报告生成器。

职责：读 4 份证据包，先写 `report_data.json`（事实提取 + 来源标注），再对着它手写 `analysis_report.html`。不在 `report_data.json` 里的数字禁止出现在 HTML 中。

## 调度

- 触发条件：Stage 7，4 份证据包齐全。
- 执行方式：由主 Agent 按本文件口径串行执行。不 spawn 子 Agent（报告必须由同一专家视角统稿）。
- 允许写入：`analysis/report_data.json`、`analysis/analysis_report.html`。
- 禁止写入：证据包、原始数据、XLSX、QA 结果。
- 证据契约：HTML 中的所有数字必须能从 `report_data.json` 追溯到具体证据包字段。

## 输入

| 输入 | 路径 | 用途 |
|---|---|---|
| 路线配置 | `route_matrix_confirm.json` | Hero 路线名、竞品表路线分组 |
| 市场结构证据 | `market_structure/market_structure_evidence_packet.json` | 类目数据、竞品池、价格带 |
| 搜索需求证据 | `search_demand/search_demand_evidence_packet.json` | 类目全景、关键词数据、趋势 |
| VOC 证据 | `review_voc/voc_evidence_packet.json` | 痛点、亮点、机会假设 |

## 两步生成流程（强制执行）

### 第一步：生成 `analysis/report_data.json`

从 4 份证据包中提取所有将出现在 HTML 中的事实数据，写入 `report_data.json`。每个事实必须标注 `source_path`（JSON 路径，指向证据包中的具体字段）。

**这不是可选步骤。** 在 `report_data.json` 写完并通过自检之前，禁止开始写 HTML。

### 第二步：对着 `report_data.json` 写 `analysis/analysis_report.html`

HTML 中出现的每一个数字、百分比、金额、ASIN 数量、评论条数，必须能在 `report_data.json` 中找到对应条目。如果你需要写一个数字但 `report_data.json` 中没有，回到第一步补充它。

## report_data.json 结构

```json
{
  "packet_id": "report_data",
  "generated_at": "ISO时间戳",
  "evidence_sources": {
    "route_matrix": "route_matrix_confirm.json",
    "market_structure": "market_structure/market_structure_evidence_packet.json",
    "search_demand": "search_demand/search_demand_evidence_packet.json",
    "voc": "review_voc/voc_evidence_packet.json"
  },

  "hero": {
    "verdict": "建议进入小批量验证 | 建议补齐数据后再评估 | 建议暂停推进",
    "lead_analysis": "首屏引导语（运营判断，2-3句）",
    "metrics": {
      "细分TAM":           {"value": "$X.XXM", "source_path": "market_structure.market_size.primary_market.overview_all.月均销售额($)"},
      "大类TAM":           {"value": "$X.XM",  "source_path": "search_demand.facts[f8,f9,f10] 月销额加总"},
      "细分均价":           {"value": "$X.XX",  "source_path": "market_structure.market_size.primary_market.overview_all.平均价格($)"},
      "目标材质竞品数":      {"value": "N",      "source_path": "search_demand.facts[f2].note 或 keyword_demand[biothane].competitor_count"},
      "VOC覆盖":           {"value": "N ASIN / M 条", "source_path": "voc.review_stats.total_reviews + asin_count"}
    }
  },

  "category_panorama": {
    "categories": [
      {
        "name": "类目名",
        "nodeId": {"value": "nodeId", "source_path": "search_demand.facts[].value.nodeId"},
        "top100_monthly_units": {"value": "172183", "source_path": "search_demand.f8.value.top100_monthly_units"},
        "top100_monthly_revenue": {"value": "$1,920,773", "source_path": "market_structure.market_size.primary_market.overview_all.月均销售额($)"},
        "average_price": {"value": "$13.37", "source_path": "search_demand.f8.value.average_price"},
        "top3_product_share": {"value": "28.06%", "source_path": "search_demand.f8.value.top3_product_units_share"},
        "top3_brand_share": {"value": "33.08%", "source_path": "search_demand.f8.value.top3_brand_units_share"},
        "amazon_owned_share": {"value": "10.28%", "source_path": "search_demand.f8.value.amazon_owned_share"},
        "low_reviews_share": {"value": "5.68%", "source_path": "search_demand.f8.value.low_reviews_share"},
        "judgment": "主战场 | 次要战场 | 错误挂载 | 混杂排除"
      }
    ]
  },

  "competitors": [
    {
      "asin": {"value": "B0XXXXXXXX", "source_path": "market_structure.reference_asin_pool[].asin"},
      "brand": {"value": "品牌名", "source_path": "market_structure.reference_asin_pool[].similarity_reason 中提取"},
      "monthly_sales": {"value": "N", "source_path": "market_structure.reference_asin_pool[].monthly_sales"},
      "price": {"value": "$X.XX", "source_path": "market_structure.reference_asin_pool[].price"},
      "rating_count": {"value": "N", "source_path": "market_structure.reference_asin_pool[].rating_count"},
      "rating": {"value": "X.X", "source_path": "从 market_structure 或 Sorftime product_detail 获取"},
      "route": {"value": "路线名", "source_path": "market_structure.reference_asin_pool[].route_ref"},
      "asin_role": {"value": "primary_reference | ...", "source_path": "market_structure.reference_asin_pool[].asin_role"},
      "judgment": "运营判断（1句，基于证据的解读）"
    }
  ],

  "pain_points": [
    {
      "priority": "P0 | P1 | P2",
      "dimension": {"value": "痛点维度名", "source_path": "voc.pain_points_by_dimension[].dimension"},
      "review_count": {"value": "30+", "source_path": "voc.pain_points_by_dimension[].review_count"},
      "asins_affected_count": {"value": "8/8", "source_path": "voc.pain_points_by_dimension[].asins_affected 数组长度"},
      "issue_description": "竞品出了什么问题（基于 evidence_quotes 的运营解读）",
      "spec_requirement": "你的产品应该做到（基于 spec_requirement 的运营建议）"
    }
  ],

  "price_bands": [
    {
      "band": "$X-Y",
      "unit_share": {"value": "N%", "source_path": "market_structure.price_band.primary_market_distribution_grouped[band].unit_share"},
      "product_count": {"value": "~N", "source_path": "market_structure.price_band.primary_market_distribution_grouped[band].product_count"},
      "opportunity_level": {"value": "strong | watch | weak", "source_path": "market_structure.price_band.primary_market_distribution_grouped[band].opportunity_level"},
      "judgment": "机会判断（1句）"
    }
  ],

  "keywords": [
    {
      "role": "主攻意图词 | 可测词 | 明确否定词",
      "keyword": {"value": "关键词", "source_path": "search_demand.keyword_demand[].keyword"},
      "monthly_search_volume": {"value": "N", "source_path": "search_demand.keyword_demand[].monthly_search_volume"},
      "cpc": {"value": "$X.XX", "source_path": "search_demand.keyword_demand[].cpc"},
      "competitor_count": {"value": "N", "source_path": "search_demand.keyword_demand[].competitor_count"},
      "low_review_share": {"value": "N%", "source_path": "search_demand.facts[].note 中提取"},
      "strategy": "策略说明（运营判断，1-2句）"
    }
  ],

  "risks": [
    {
      "severity": "高 | 中 | 低",
      "description": "风险描述（运营判断）",
      "evidence_basis": "支撑此判断的证据（引用证据包中的具体数据或 data_gaps）"
    }
  ],

  "advantages": [
    {
      "severity": "强 | 中",
      "description": "优势描述（运营判断）",
      "evidence_basis": "支撑此判断的证据"
    }
  ],

  "gonogo_conditions": [
    {
      "condition": "条件名",
      "go_threshold": "Go 阈值",
      "nogo_threshold": "No-Go 红线",
      "current_status": "待验证 | 未开始 | 已通过"
    }
  ],

  "next_steps": [
    {
      "order": 1,
      "title": "步骤标题",
      "description": "具体动作（运营建议）"
    }
  ],

  "data_sources": {
    "sorftime_date": "2026-06-21",
    "seller_sprite_date": "2026-06-21",
    "review_export_date": "2026-06-21",
    "voe_review_count": {"value": "645", "source_path": "voc.review_stats.total_reviews"},
    "voe_low_rating_count": {"value": "129", "source_path": "voc.review_stats.low_rating_count"},
    "voe_asin_count": {"value": "8", "source_path": "voc.review_stats.asin_count"},
    "voe_date_range": {"value": "2021-06 至 2026-06", "source_path": "voc.review_stats.date_range"}
  }
}
```

## 数据溯源表（每个板块写什么，从哪个证据包取）

| 板块 | 事实数据 | 证据包来源 | 具体字段路径 |
|---|---|---|---|
| Hero | 细分TAM | market_structure | `market_size.primary_market.overview_all.月均销售额($)` |
| Hero | 大类TAM | search_demand | `facts[f8,f9,f10]` 月销额加总 |
| Hero | 均价 | market_structure | `market_size.primary_market.overview_all.平均价格($)` |
| Hero | 目标材质竞品数 | search_demand | `facts[f2].note` 或 `keyword_demand[].competitor_count` |
| Hero | VOC覆盖 | voc | `review_stats.total_reviews` + `review_stats.asin_count` |
| 类目全景 | 类目名/NodeId/销量/均价/集中度/自营占比 | search_demand | `facts[f8,f9,f10].value` |
| 类目全景 | 月销额 | market_structure | `market_size.primary_market.overview_all.月均销售额($)` |
| 类目全景 | 趋势/季节性 | search_demand | `trend_signal` |
| 类目全景 | 评论门槛 | market_structure | `derived_metrics[dm_primary_review_threshold]` |
| 核心竞品 | ASIN/价格/月销/评论数/相似理由 | market_structure | `reference_asin_pool[]` |
| 核心竞品 | 评分 | market_structure | `reference_asin_pool[]` 或 Sorftime product_detail |
| 核心竞品 | 路线归属 | market_structure | `reference_asin_pool[].route_ref` |
| 用户痛点 | 痛点维度/issue/severity/提及数/涉及ASIN | voc | `pain_points_by_dimension[]` |
| 用户痛点 | spec_requirement | voc | `pain_points_by_dimension[].spec_requirement` |
| 用户痛点 | evidence_refs | voc | `pain_points_by_dimension[].evidence_refs[]` |
| 价格带 | 价格段/占比/竞品数/机会评级 | market_structure | `price_band.primary_market_distribution_grouped` |
| 关键词 | 关键词/月搜/CPC/竞品数 | search_demand | `keyword_demand[]` |
| 关键词 | 低评论占比 | search_demand | `facts[].note` 中提取 |
| 关键词 | 季节性 | search_demand | `keyword_demand[].seasonality` |
| 风险 | data_gaps | voc + market_structure | `data_gaps[]` |
| 风险 | 集中度/自营占比 | search_demand | `facts[f8,f9,f10].value` |
| 优势 | 蓝海信号/CPC对比 | search_demand | `derived_metrics` + `facts[]` |
| 优势 | 痛点可解决性 | voc | `opportunity_hypotheses[]` |

## 可以做

- 以资深运营专家视角解读数据，给出有依据的判断和建议。
- 对证据包中的事实做运营化翻译（如"CPC $0.96"翻译为"投产比高的广告靶词"）。
- 在 report_data.json 中标注每个事实的 `source_path`。
- 基于 VOC 痛点推导产品规格建议。
- 判断关键词的运营意图分类（主攻/可测/否定）。

## 不可以做

- **不新增数字。** HTML 中的每一个数字、百分比、金额、计数必须有对应的 `source_path`，能在证据包中定位到具体字段。
- **不新增竞品信息。** 竞品的品牌名、子体数、产地、材质细节等如不在证据包中，不得写入 HTML。如果证据包中只有 ASIN 和品牌名，就只能写这两个。
- **不发明痛点。** VOC 痛点只能来自 `voc_evidence_packet.json` 的 `pain_points_by_dimension`，不能根据"行业常识"补充未在证据中出现的痛点。
- **不推测缺失数据。** 如果某个竞品的评分不在证据包中，写"待补"或不写，不能猜一个数字。
- **不把推断当事实。** 定价建议、毛利预估、差异点价值是推断，报告中使用"建议""可考虑""预估"等措辞区分。
- **不复制粘贴 insight 原文。** `insights_for_handoff` 是给主 Agent 看的提示，不能直接抄进 HTML。HTML 里的分析应该基于原始数据重新撰写。
- **不出现内部术语。** HTML 中不出现 Agent、MCP、tool、spawn、packet、pipeline、evidence_packet 等术语。

## 自检清单（写 HTML 前逐项确认）

- [ ] `report_data.json` 已写完，每个 value 都有 `source_path`
- [ ] 数字口径一致：同一个数字在不同板块出现时值相同（如 172,183 在 Hero 和类目全景中一致）
- [ ] 细分 TAM 和大类 TAM 已分开，数值不同
- [ ] Hero 5 指标按契约顺序：细分TAM / 大类TAM / 均价 / 竞品数 / VOC覆盖（不允许用"最大竞品月销"替代）
- [ ] 竞品表中所有字段（ASIN/品牌/月销/价格/评论数/评分）都能在证据包中找到
- [ ] 关键词表中所有数字（月搜/CPC/竞品数/低评论占比）都能在 search_demand 中找到
- [ ] 痛点提及条数与 voc_evidence_packet 一致
- [ ] 没有证据包之外的数字或事实性断言
- [ ] HTML 视觉规范：`<link>` 引用 CSS、绿色 Hero、4 种 tag、价格柱状图、Go/No-Go 表

## 完整 8 板块数据溯源表（快速对照用）

写每个板块时对照此表，确保不遗漏、不多写：

| # | 板块 | 必须包含 | 数据全部来自 | 常见越权错误 |
|---|---|---|---|---|
| 1 | Hero | verdict + 5 metrics + lead | market_structure + search_demand + voc | 大类TAM写成和细分TAM相同；竞品数用错词 |
| 2 | 类目全景 | 所有相关类目表 + 4 insight cards | search_demand facts + market_structure | 只写一个类目；月销额数字与Hero不一致 |
| 3 | 数据来源与口径 | 6行数据源表 + 事实/推断说明 | 各证据包 execution_provenance + review_stats | 采样日期写错；样本数写错 |
| 4 | 核心竞品 | ASIN表（含品牌/月销/价格/评论/评分/路线/判断） | market_structure reference_asin_pool | 发明不在证据中的品牌名或子体数 |
| 5 | 用户痛点→产品规格 | P0/P1/P2排序 + 竞品问题 + 产品规格 | voc pain_points_by_dimension | 发明新痛点；修改提及条数 |
| 6 | 价格带分布 | 柱状图 + 价格带表 | market_structure price_band | 修改占比数字；发明代表竞品 |
| 7 | 关键词与流量策略 | 主攻/可测/否定三分 + 策略说明 | search_demand keyword_demand + facts | 修改月搜量或CPC；遗漏否定词 |
| 8 | 风险与下一步 | 风险/优势双栏 + Go/No-Go表 + 3步骤 | voc data_gaps + market_structure + 运营判断 | 风险无证据支撑；步骤写空话 |
