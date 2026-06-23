# Report Generation Agent

角色：资深亚马逊运营专家报告生成器。

职责：读 4 份证据包，先写 `report_data.json`（事实提取 + 来源标注），再对着它手写 `<中文品名>_分析报告.html`。不在 `report_data.json` 里的数字禁止出现在 HTML 中。

## 反捏造红线（最高优先级）

**以下行为绝对禁止。违反对应着 QA 阻断、报告驳回、运营决策被误导。**

| # | 禁令 | 说明 |
|---|---|---|
| 1 | **禁止凭空编造数字** | HTML 中每一个数字、百分比、金额、销量、评分数、搜索量，必须能在 `report_data.json` 中找到对应条目，进而通过 `source_path` 追溯到证据包原始字段。推导型估算（如“预计月销约 3000”）必须标注推断依据和计算逻辑。 |
| 2 | **禁止篡改来源数据** | 不得对证据包中的数值进行四舍五入、放大缩小、或选择性引用。如需归一化（如单位换算），必须保留原始值和换算方式。 |
| 3 | **禁止模糊溯源** | `source_path` 必须指向证据包中的具体字段（如 `market_structure.market_size.primary_market.overview_all.月均销量`），不允许笼统指向整个包或板块。 |
| 4 | **禁止遗漏占位符替换** | Seed 中的 `"source_path": "__ai_pending__"` 应尽量替换为真实路径。若证据包确实无对应数据，允许保留 `__ai_pending__`（QA 记 warning），但禁止改为空字符串 `""`（会触发阻断）。 |
| 5 | **禁止跨源混淆** | 不得将 Sorftime 数据标注为卖家精灵来源，或将不同 ASIN、不同类目、不同时间段的数据混用。 |
| 6 | **禁止以偏概全** | 单一 ASIN 的数据不能代表整个类目；Top10 样本不能表述为“市场普遍”。样本量和统计口径必须随数据一起引用。 |
| 7 | **禁止用关键词搜索量代替市场体量** | 月搜索量 ≠ 月销量。两者必须分开陈述，各自标注来源。

## 调度

- 触发条件：Stage 7，4 份证据包齐全。
- 执行方式：由主 Agent 按本文件口径串行执行。不 spawn 子 Agent（报告必须由同一专家视角统稿）。
- 允许写入：`analysis/report_data.json`、`analysis/<中文品名>_分析报告.html`。
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

**`__ai_pending__` 标记**：seed 阶段脚本无法确定的字段会标记为 `"source_path": "__ai_pending__"`。增强 `report_data.json` 时应尽量替换为真实路径；若证据包中确实不存在对应数据，允许保留 `__ai_pending__`（QA 记 warning 不阻断），但 HTML 中对应位置应标注"数据待补充"或留空，禁止将 `__ai_pending__` 或 `source_path` 等内部标记暴露给用户。空字符串 `""` source_path 会被 QA 阻断，必须填充或保留 `__ai_pending__`。

### 第二步：对着 `report_data.json` 写 `analysis/<中文品名>_分析报告.html`

HTML 中出现的每一个数字、百分比、金额、ASIN 数量、评论条数，必须能在 `report_data.json` 中找到对应条目。如果你需要写一个数字但 `report_data.json` 中没有，回到第一步补充它。

### CSS 与 HTML 骨架强制约束（禁止手写 CSS）

**`<style>` 块必须从 `skills/amazon-product-research/references/report_template.css` 完整复制粘贴。不允许修改任何 CSS 值、类名、变量名，不允许自己写新的 CSS。** 这保证所有品类的报告视觉风格完全一致。

唯一允许的 CSS 微调：
- `@media` 查询中的断点值可以根据实际内容调整
- 如果某品类确实不需要某个 CSS 组件（如 warn insight-card、price-band），可以保留 CSS 但不使用对应 HTML 类名

**HTML 骨架必须遵循以下结构，类名必须与 CSS 完全匹配：**

```html
<body>
<div class="page">

<section class="hero">
  <div class="eyebrow">Market Precheck · 类目名 (NodeID) · 日期</div>
  <h1>产品名</h1>
  <div class="verdict">建议进入小批量验证</div>
  <p class="lead">一句话总结...</p>
  <div class="hero-grid">
    <div class="hero-metric">
      <div class="label">标签</div>
      <div class="value">值</div>
    </div>
    <!-- ×6 -->
  </div>
</section>

<section class="section">
  <h2>板块标题</h2>
  <p class="subtitle">副标题</p>
  <!-- 内容 -->
</section>

<!-- 更多 section ... -->
</div>
</body>
```

**类名速查表（只允许用这些，不能发明新类名）：**

| 作用 | 类名 | 用法 |
|---|---|---|
| 页面容器 | `.page` | `<div class="page">` |
| Hero 区 | `.hero` | `<section class="hero">` |
| Hero 子元素 | `.eyebrow` `.verdict` `.lead` | Hero 内直接子元素 |
| Hero 指标网格 | `.hero-grid` → `.hero-metric` → `.label` / `.value` | 6 列网格 |
| 内容卡片 | `.section` → `h2` `.subtitle` | 每个内容板块 |
| 洞察卡片行 | `.insight-row` → `.insight-card` `.good`/`.warn` → `h4` `p` | 2 列布局 |
| 表格 | `table` `th` `td`（无额外类名） | 标准表格 |
| 标签 | `.tag` `.tag-green` `.tag-amber` `.tag-red` `.tag-gray` | 只有 4 色 |
| 价格柱状图 | `.price-band` → `.price-bar` → `.bar` + `.label` | 竖柱图。`.bar` 高度必须使用 `bar_height` 值（单位 px），颜色必须使用 `opportunity_level` 映射：strong→#059669, watch→#d97706, weak→#dc2626。禁止硬编码高度或颜色。 |
| 风险列表 | `.risk-list` → `li` → `.severity` | 风险/优势列表 |
| 下一步 | `.next-steps` → `.next-step` → `.num` `h4` `p` | 3 列网格 |
| Go/No-Go 表 | `table.go-nogo` | 前置条件表 |

## report_data.json 结构

```json
{
  "packet_id": "report_data",
  "run_id": "runs目录名",
  "generated_at": "ISO时间戳",
  "evidence_sources": [
    {
      "name": {"value": "Search Demand / Sorftime", "source_path": "analysis.source_packets[0].name"},
      "path": {"value": "search_demand/search_demand_evidence_packet.json", "source_path": "analysis.source_packets[0].path"},
      "exists": {"value": true, "source_path": "analysis.source_packets[0].exists"},
      "packet_id": {"value": "search_demand_evidence", "source_path": "analysis.source_packets[0].packet_id"},
      "confidence": {"value": "medium", "source_path": "analysis.source_packets[0].confidence"},
      "execution_mode": {"value": "real_subagent_spawn | serial_fallback | script_generated", "source_path": "analysis.source_packets[0].execution_mode"},
      "provenance_note": {"value": "来源说明", "source_path": "analysis.source_packets[0].provenance_note"}
    }
  ],

  "hero": {
    "verdict": "建议进入小批量验证 | 建议补齐数据后再评估 | 建议暂停推进",
    "lead_analysis": "首屏引导语（运营判断，2-3句）",
    "evidence_sources": ["Search Demand / Sorftime", "Market Structure / 卖家精灵", "VOC Evidence", "Route Matrix"],
    "metrics": {
      "target_market":          {"value": "类目名", "source_path": "market_structure.market_size.primary_market.market_label"},
      "monthly_demand":         {"value": "N units", "source_path": "market_structure.market_size.primary_market.overview_all.月均销量"},
      "core_search_volume":     {"value": "~N",  "source_path": "analysis._derived.core_search_volume"},
      "avg_price":              {"value": "$X.XX",  "source_path": "analysis.seller_sprite_validation.primary_market.avg_price_usd"},
      "recommended_price":      {"value": "$X-XX", "source_path": "analysis._derived.recommended_price"},
      "avg_rating":             {"value": "X.X", "source_path": "market_structure.market_size.primary_market.avg_rating 或 Top100加权计算"}
    }
  },

  "category_panorama": {
    "categories": [
      {
        "category_name": {"value": "类目名", "source_path": "analysis.category_opportunity.category_candidates[0].category_name"},
        "node_id": {"value": "node_id", "source_path": "analysis.category_opportunity.category_candidates[0].node_id"},
        "category_path": {"value": "类目路径", "source_path": "analysis.category_opportunity.category_candidates[0].category_path"},
        "top100_monthly_sales": {"value": "N", "source_path": "analysis.seller_sprite_validation.primary_market.avg_monthly_units"},
        "top100_monthly_revenue": {"value": "N", "source_path": "analysis.seller_sprite_validation.primary_market.avg_monthly_revenue_usd"},
        "product_count_in_category": {"value": "N", "source_path": "analysis.seller_sprite_validation.primary_market.sample_count"},
        "representative_asins": [
          {"asin": "B0XXXXXXXX", "monthly_sales": "N", "source_path": "analysis.reference_asin_pool[0]"}
        ],
        "avg_price": {"value": "N", "source_path": "analysis.seller_sprite_validation.primary_market.avg_price_usd"},
        "category_role": {"value": "broad_market | subcategory_market | mixed_pool | excluded", "source_path": "analysis.category_opportunity.category_candidates[0].category_role"},
        "reason": "1-2句类目判断理由",
        "lineage": ["analysis.category_opportunity.category_candidates[0]"]
      }
    ]
  },

  "data_sources": {
    "source_packets": [
      {
        "name": {"value": "Market Structure / 卖家精灵", "source_path": "analysis.source_packets[1].name"},
        "path": {"value": "market_structure/market_structure_evidence_packet.json", "source_path": "analysis.source_packets[1].path"},
        "exists": {"value": true, "source_path": "analysis.source_packets[1].exists"},
        "packet_id": {"value": "market_structure_evidence", "source_path": "analysis.source_packets[1].packet_id"},
        "confidence": {"value": "medium", "source_path": "analysis.source_packets[1].confidence"},
        "execution_mode": {"value": "real_subagent_spawn | serial_fallback | script_generated", "source_path": "analysis.source_packets[1].execution_mode"},
        "provenance_note": {"value": "来源说明", "source_path": "analysis.source_packets[1].provenance_note"}
      }
    ],
    "critical_inputs": {
      "route_matrix": "route_matrix_confirm.json",
      "workflow_state": "workflow_state.json"
    },
    "data_gaps": [],
    "freshness_note": "以 Evidence Packet 和关键输入文件的生成时间为准；缺失口径必须写入 data_gaps。"
  },

  "competitors": [
    {
      "asin": {"value": "B0XXXXXXXX", "source_path": "analysis.reference_asin_pool[0].asin"},
      "brand": {"value": "品牌名", "source_path": "analysis.reference_asin_pool[0].brand"},
      "monthly_sales": {"value": "N", "source_path": "analysis.reference_asin_pool[0].monthly_sales"},
      "price": {"value": "N", "source_path": "analysis.reference_asin_pool[0].price"},
      "rating_count": {"value": "N", "source_path": "analysis.reference_asin_pool[0].rating_count"},
      "rating": {"value": "N", "source_path": "analysis.reference_asin_pool[0].rating"},
      "route": {"value": "路线名", "source_path": "analysis.reference_asin_pool[0].route_ref"},
      "asin_role": {"value": "primary_reference | high_sales_benchmark | new_release_sample | premium_benchmark | painpoint_reference | excluded_reference", "source_path": "analysis.reference_asin_pool[0].asin_role"},
      "judgment": "运营判断（1句，基于证据的解读）"
    }
  ],

  "pain_points": [
    {
      "priority": "P0 | P1 | P2",
      "dimension": {"value": "痛点维度名", "source_path": "analysis.voc_spec_translation.pain_points[0].dimension"},
      "review_count": {"value": "N", "source_path": "analysis.voc_spec_translation.pain_points[0].review_count"},
      "asins_affected_count": {"value": "N", "source_path": "analysis.voc_spec_translation.pain_points[0].asins_affected"},
      "issue_description": "竞品出了什么问题（基于 evidence_quotes 的运营解读）",
      "spec_requirement": "你的产品应该做到（基于 spec_requirement 的运营建议）"
    }
  ],

  "price_bands": [
    {
      "band": {"value": "价格段", "source_path": "analysis.category_opportunity.price_band_opportunity[0].price_band"},
      "unit_share": {"value": "N", "source_path": "analysis.category_opportunity.price_band_opportunity[0].sales_share"},
      "product_count": {"value": "N", "source_path": "analysis.category_opportunity.price_band_opportunity[0].product_count"},
      "opportunity_level": {"value": "strong | watch | weak", "source_path": "analysis.category_opportunity.price_band_opportunity[0].opportunity_level"},
      "bar_height": {"value": "N", "source_path": "analysis.category_opportunity.price_band_opportunity[0].bar_height"},
      "judgment": "机会判断（1句）"
    }
  ],

  "keywords": [
    {
      "role": "main_traffic | conversion_quality | precise_long_tail | mixed_or_excluded",
      "keyword": {"value": "关键词", "source_path": "analysis.keyword_pool.roles.main_traffic[0].keyword"},
      "monthly_search_volume": {"value": "N", "source_path": "analysis.keyword_pool.roles.main_traffic[0].monthly_search_volume"},
      "cpc": {"value": "N", "source_path": "analysis.keyword_pool.roles.main_traffic[0].cpc"},
      "competitor_count": {"value": "N", "source_path": "analysis.keyword_pool.roles.main_traffic[0].competitor_count"},
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
  ]
}
```

## 数据溯源表（每个板块写什么，从哪个证据包取）

| 板块 | 事实数据 | 证据包来源 | 具体字段路径 |
|---|---|---|---|
| Hero | 目标市场 | market_structure | `market_size.primary_market.market_label` |
| Hero | 月销(子市场) | market_structure | `market_size.primary_market.overview_all.月均销量` |
| Hero | 核心词月搜 | keyword_pool (由 search_demand 构建) | `analysis._derived.core_search_volume`（pipeline 从 main_traffic 聚合） |
| Hero | 类目均价 | seller_sprite_validation | `analysis.seller_sprite_validation.primary_market.avg_price_usd` |
| Hero | 推荐定价 | route_judgment | `analysis._derived.recommended_price`（pipeline 从主线 price_range 提取） |
| Hero | 类目均分 | market_structure | `market_size.primary_market.avg_rating` 或 Top100加权计算 |
| 类目全景 | 类目名/NodeId/销量/均价/集中度/自营占比 | search_demand | `facts[f8,f9,f10].value` |
| 类目全景 | 月销额 | market_structure | `market_size.primary_market.overview_all.月均销售额($)` |
| 类目全景 | 趋势/季节性 | search_demand | `trend_signal` |
| 类目全景 | 评论门槛 | market_structure | `derived_metrics[dm_primary_review_threshold]` |
| 类目全景 | 退货率 | seller_sprite | 选市场报告 `商品需求趋势.同类目退货率` |
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
- **不使用抽象路线标签。** 禁止在 HTML 中使用"路线A""路线B""路线1""路线2"等无业务含义的代号。路线名必须使用业务描述词（如"吊扇除尘""蜘蛛网除尘""纯钢丝刷""三合一刷"），让运营一眼看懂每个方向在做什么产品。路线命名应基于 `route_matrix_confirm.json` 中的路线定义或关键词的业务语义。
- **不自创 CSS。** `<style>` 块必须完整复制 `skills/amazon-product-research/references/report_template.css`，禁止修改任何 CSS 值、类名、变量名。禁止发明新的 CSS 类名或 HTML 结构模式。所有报告的视觉风格必须 100% 一致。

## 自检清单（写 HTML 前逐项确认）

- [ ] `report_data.json` 已写完，每个 value 都有 `source_path`
- [ ] 数字口径一致：同一个数字在不同板块出现时值相同（如 172,183 在 Hero 和类目全景中一致）
- [ ] 细分 TAM 和大类 TAM 已分开，数值不同
- [ ] Hero 6 指标按契约顺序：目标市场 / 月销(子市场) / 核心词月搜 / 类目均价 / 推荐定价 / 类目均分
- [ ] 竞品表中所有字段（ASIN/品牌/月销/价格/评论数/评分）都能在证据包中找到
- [ ] 关键词表中所有数字（月搜/CPC/竞品数/低评论占比）都能在 search_demand 中找到
- [ ] 痛点提及条数与 voc_evidence_packet 一致
- [ ] 没有证据包之外的数字或事实性断言
- [ ] 路线标签使用业务描述词（吊扇除尘/纯钢丝刷），无"路线A/B"等抽象代号
- [ ] HTML 视觉规范：内嵌 `<style>` CSS、绿色 Hero、4 种 tag、价格柱状图、Go/No-Go 表
- [ ] **模板合规：`<style>` 块从 report_template.css 完整复制，未修改任何 CSS 值/类名/变量名**
- [ ] **类名合规：HTML 中只出现了类名速查表中的类名，未出现自定义类名（如 `.hero-metric-label` `.container` `.section-card` `.insight-cards` 等）**

## 完整 8 板块数据溯源表（快速对照用）

写每个板块时对照此表，确保不遗漏、不多写：

| # | 板块 | 必须包含 | 数据全部来自 | 常见越权错误 |
|---|---|---|---|---|
| 1 | Hero | verdict + 6 metrics + lead | market_structure + search_demand | 指标遗漏(6缺1)；类目名写错 |
| 2 | 类目全景 | 所有相关类目表 + 4 insight cards | search_demand facts + market_structure | 只写一个类目；月销额数字与Hero不一致 |
| 3 | 数据来源与口径 | 6行数据源表 + 事实/推断说明 | 各证据包 execution_provenance + review_stats | 采样日期写错；样本数写错 |
| 4 | 核心竞品 | ASIN表（含品牌/月销/价格/评论/评分/路线/判断） | market_structure reference_asin_pool | 发明不在证据中的品牌名或子体数 |
| 5 | 用户痛点→产品规格 | P0/P1/P2排序 + 竞品问题 + 产品规格 | voc pain_points_by_dimension | 发明新痛点；修改提及条数 |
| 6 | 价格带分布 | 柱状图 + 价格带表 | market_structure price_band | 硬编码柱高或颜色（必须用 bar_height + opportunity_level）；修改占比数字；发明代表竞品 |
| 7 | 关键词与流量策略 | 主攻/可测/否定三分 + 策略说明 | search_demand keyword_demand + facts | 修改月搜量或CPC；遗漏否定词 |
| 8 | 风险与下一步 | 风险/优势双栏 + Go/No-Go表 + 3步骤 | voc data_gaps + market_structure + 运营判断 | 风险无证据支撑；步骤写空话 |
