# P4 MCP 能力映射与最小字段烟测

更新日期：2026-06-24

本文件用于 P4 双 MCP 深挖与冲突复核的契约映射。它只记录工具能力、字段口径、可比性和职责边界，不承载任何选品结论，不生成正式 P4 evidence packet。

真实 smoke 样本只保存在临时 run 目录；具体 run 路径见 P4 计划文件。通用引用格式如下：

- `runs/<run_id>/mcp_probe/sellersprite_probe_raw.json`
- `runs/<run_id>/mcp_probe/sorftime_probe_raw.json`
- `runs/<run_id>/mcp_probe/mcp_probe_summary.json`

## 调研依据

- `docs/CLI双MCP多Agent选品技术方案.md`
- `docs/sellersprite_mcp_tools_reference.md`
- `docs/sorftime-mcp-工具调用策略.md`
- `docs/plans/CLI双MCP多Agent选品P3路线矩阵确认实施计划.md`
- `runs/<run_id>/mcp_probe/` 最小字段 smoke 结果

## 结论原则

P4 推荐分工是“主责 + 交叉验证”，不是绝对二分。

- SellerSprite 主产 `market_structure/market_structure_evidence_packet.json`，但也覆盖竞品、产品、ASIN 详情、销量趋势、关键词、流量、评论和 Keepa。
- Sorftime 主产 `search_demand/search_demand_evidence_packet.json`，但也覆盖实时类目、类目 Top100、类目趋势、参考 ASIN、ASIN 流量词、竞品关键词和热销特征。
- 双方都可以作为 `cross_check_source`。Conflict Resolver 必须先比较 `metric_basis`，再判断是否存在可比较冲突。

## SellerSprite 工具能力分组

| 分组 | 代表工具 | P4 适合承载的证据 |
|---|---|---|
| 市场结构 | `market_research`、`market_research_statistics`、`market_product_concentration`、`market_brand_concentration`、`market_seller_concentration`、`market_seller_type`、`market_seller_location`、`market_price_distribution`、`market_ratings_count`、`market_rating_distribution`、`market_product_demand_trend` | 市场容量、销量 / 销售额结构、价格带、评分 / 评论门槛、商品 / 品牌 / 卖家集中度、新品占比、卖家类型与地区分布 |
| 竞品 / 产品 | `competitor_lookup`、`product_research`、`traffic_listing` | 竞品池、产品筛选、Top 产品结构、卖家 / 品牌结构、关联竞品、价格 / 评论 / 配送过滤 |
| ASIN 详情与趋势 | `asin_detail`、`asin_sales_trend`、`asin_coupon_trend`、`asin_detail_with_coupon_trend`、`asin_prediction`、`bsr_prediction`、`keepa_info` | ASIN 类目、价格、评分、评论数、父子体、变体、卖家、配送、BSR、销量趋势、优惠趋势、Keepa 历史趋势 |
| 关键词 / 流量 | `traffic_keyword`、`traffic_extend`、`traffic_source`、`traffic_keyword_stat`、`traffic_listing_stat`、`keyword_research`、`keyword_research_trends`、`keyword_miner`、`keyword_order`、`aba_research_weekly`、`aba_research_monthly`、`aba_research_trend` | 关键词搜索量、购买量、转化率、自然排名、广告排名、流量占比、ABA 排名 / 点击 / 转化、出单词、拓展词 |
| VOC / 评论 | `review` | P4 只做轻量评论字段观察或 VOC readiness，不替代 P5 评论插件 VOC |
| 趋势 / 预测 | `keyword_research_trends`、`aba_research_trend`、`google_trend`、`keepa_info`、`asin_prediction`、`bsr_prediction`、`market_listing_trend`、`market_product_demand_trend` | 搜索趋势、ABA 趋势、站外趋势、ASIN / BSR 预测、Listing 上架趋势、市场需求趋势 |

## Sorftime 工具能力分组

| 分组 | 代表工具 | P4 适合承载的证据 |
|---|---|---|
| 类目搜索 | `search_categories_broadly`、`category_search_from_product_name` | 候选类目发现、路线对应 nodeId、类目边界初筛 |
| 类目 Top100 | `category_report`、`category_report_from_history` | Top100 代表 ASIN、价格带、销量 / 销售额、评论门槛、品牌 / 卖家集中度、历史样本对比 |
| 类目趋势 | `category_trend`、`category_report_from_history` | 类目销量趋势、新品占比趋势、Top3 集中度趋势、Amazon 自营占比趋势 |
| 关键词详情 | `keyword_detail`、`keyword_trend` | 关键词月搜 / 周搜、CPC、竞品数量、旺季、搜索量趋势 |
| 关键词扩展 | `keyword_extends`、`keyword_list` | 相关词、长尾词、场景词、混池词、无明确种子词时的探索词 |
| 关键词搜索结果 | `keyword_search_results` | 自然位结果、搜索意图、混池风险、首页产品构成、代表 ASIN |
| ASIN 流量词 | `product_traffic_terms` | ASIN 自然 / 广告曝光词、曝光位置、曝光时间、关键词量级 |
| 竞品关键词 | `competitor_product_keywords` | 竞品自然位关键词、关键词月搜索量、自然曝光位置 |
| 热销特征 | `similar_product_feature`、`potential_product` | 热销共同特征、规格 / 卖点观察、潜力新品或相邻候选 ASIN |
| 参考 ASIN / 产品详情 | `product_detail`、`product_trend`、`product_reviews`、`product_report` | ASIN 详情、月销量 / 月销额趋势、价格 / 排名趋势、轻量评论；`product_report` 只作为流程提示，不作为直接事实字段 |

## P4 推荐主责

### SellerSprite 主责

| 指标 | 推荐工具 | 说明 |
|---|---|---|
| 市场容量 | `market_research`、`market_research_statistics` | 主看类目容量、均值、Top 结构和可做空间 |
| 销量 / 销售额 | `market_research`、`product_research`、`competitor_lookup`、`asin_sales_trend` | 类目 / 商品 / ASIN 口径分开记录 |
| 价格带 | `market_research`、`market_price_distribution`、`product_research`、`asin_detail` | 必须记录币种、价格单位和样本范围 |
| 集中度 | `market_product_concentration`、`market_brand_concentration`、`market_seller_concentration`、`market_research` | 商品、品牌、卖家集中度分开，不混成一个指标 |
| 评论门槛 | `market_ratings_count`、`market_rating_distribution`、`market_research`、`asin_detail` | 区分评分数、评论数和评论文本数 |
| 竞品结构 | `competitor_lookup`、`product_research`、`traffic_listing` | 结合 P3 route matrix 的路线样本，不做最终 Go / No-Go |
| ASIN 经营数据 | `asin_detail`、`asin_sales_trend`、`asin_coupon_trend`、`keepa_info` | 价格、评分、评论、BSR、父子体、变体、配送、优惠、趋势 |

### Sorftime 主责

| 指标 | 推荐工具 | 说明 |
|---|---|---|
| 实时类目 | `category_search_from_product_name`、`search_categories_broadly` | 用于发现候选类目和路线边界 |
| 参考 ASIN | `category_report`、`potential_product`、`keyword_search_results`、`product_detail` | 用于生成深挖样本，不替代候选池决策 |
| 搜索结果自然位 | `keyword_search_results` | 主看搜索意图、首页产品构成和混池 |
| 关键词需求 | `keyword_detail`、`keyword_trend`、`keyword_extends`、`keyword_list` | 月搜 / 周搜、CPC、趋势、扩展词和长尾词 |
| 关键词混池 | `keyword_search_results`、`keyword_extends`、`competitor_product_keywords` | 识别排除词、旁支路线和混池风险 |
| ASIN 流量词 | `product_traffic_terms` | 自然 / 广告曝光位置和曝光时间 |
| 热销特征 | `similar_product_feature`、`category_report` | 热销产品共同特征、规格和卖点观察 |

## 双源交叉验证字段

| 字段 | SellerSprite 侧 | Sorftime 侧 | 比较前提 |
|---|---|---|---|
| 类目边界 | `product_node`、`asin_detail`、`market_research` | `category_search_from_product_name`、`category_report`、`product_detail` | 同站点，node path / leaf node / 排名类目分开记录 |
| 代表 ASIN | `competitor_lookup`、`product_research`、`traffic_listing` | `category_report`、`keyword_search_results`、`potential_product` | 同路线、同样本角色，记录样本来源和覆盖范围 |
| 价格带 | `market_price_distribution`、`market_research`、`product_research`、`asin_detail` | `category_report`、`product_detail`、`keyword_search_results` | 同币种、同价格单位、同样本范围 |
| 评论门槛 | `market_ratings_count`、`market_rating_distribution`、`asin_detail` | `category_report`、`product_detail` | 区分 ratings、reviews、review text |
| 销量 / 趋势 | `market_research`、`product_research`、`asin_sales_trend`、`keepa_info` | `category_report`、`product_detail`、`product_trend`、`category_trend` | 同时间窗、同父子体口径、同类目或 ASIN |
| 关键词意图 | `traffic_keyword`、`keyword_miner`、`keyword_order` | `keyword_detail`、`keyword_search_results`、`keyword_extends` | 同关键词、同站点、自然 / 广告口径分开 |
| 流量词 | `traffic_keyword`、`traffic_extend`、`traffic_source` | `product_traffic_terms`、`competitor_product_keywords` | 同 ASIN、同关键词、曝光位置和流量占比分开 |
| 混池风险 | `product_research`、`traffic_keyword`、`market_research` | `keyword_search_results`、`category_report`、`similar_product_feature` | 样本范围明确，混池标签可追溯 |

## 单源字段

| 类型 | 推荐主证据 | 原因 |
|---|---|---|
| SellerSprite 单源主证据 | ABA 周 / 月选品、ABA 趋势、SellerSprite 选市场集中度子工具、Keepa 历史趋势、BSR 销量预测、Google 趋势、优惠趋势 | Sorftime 没有同口径字段或样本范围不同，只能作为背景或趋势辅助 |
| Sorftime 单源主证据 | 实时类目搜索、`category_trend` 指定指标、`keyword_search_results` 自然位结构、`product_traffic_terms` 曝光时间、`competitor_product_keywords` 自然位关键词、`similar_product_feature` 热销特征 | SellerSprite 可交叉部分关键词和 ASIN 指标，但不应替代这些工具的实时搜索 / 类目特征口径 |
| 不作为 P4 主证据 | Sorftime `product_report`、任一工具的空字段结果、P4 轻量评论文本 | `product_report` 是分析步骤提示；空字段只能进 `data_gaps`；正式 VOC 在 P5 |

## 最小字段 smoke 摘要

P4-0b 已重新生成独立 smoke run，具体 run 路径见 P4 计划文件；通用引用格式如下：

- `runs/<run_id>/mcp_probe/sellersprite_probe_raw.json`
- `runs/<run_id>/mcp_probe/sorftime_probe_raw.json`
- `runs/<run_id>/mcp_probe/mcp_probe_summary.json`

SellerSprite P4-0b 已复测代表工具：`competitor_lookup`、`product_research`、`asin_detail`、`asin_sales_trend`、`market_research`、`market_research_statistics`、`market_product_concentration`、`market_brand_concentration`、`market_price_distribution`、`market_seller_concentration`、`keyword_research`、`traffic_keyword`、`review`、`asin_prediction`。

- `asin_detail` 可返回 ASIN、标题、价格、评分、评论数、品牌、卖家、类目路径、父体和变体字段。
- `asin_sales_trend` 仍能返回丰富的嵌套 ASIN 画像字段，但顶层销量 / 销售额 / 历史价格趋势字段再次为空；P4 不应把它作为销量趋势硬依赖。
- `market_research` 可返回类目销量、均价、平均评分数、平均评分、配送 / 自营占比；销售额、集中度和新品字段仍有缺口。
- `market_product_concentration` 可返回头部商品样本和销量字段；销售额占比、销量占比等比例字段缺口明显。
- `market_brand_concentration` 可返回品牌和销量字段；品牌商品数、销售额、新品和占比字段缺口明显。
- `market_price_distribution` 网络切换后补充复测已恢复，可返回价格桶对应的商品数、销量、销售额和销量占比；本次选择字段下价格桶标签为空，P4 需要补全标签请求或写入 `data_gaps`。
- `market_seller_concentration` 网络切换后补充复测已恢复，可返回卖家排名、商品数、均价、评分 / 评论、销量、销售额和占比字段；适合作为 SellerSprite 卖家集中度主证据。
- `keyword_research` 可返回搜索量、购买量、购买率、商品数、均价、PPC、点击集中度、供需比等数值字段；但关键词文本字段可能为空，必须保留请求关键词或上游 lineage。
- `traffic_keyword` 本轮调用成功但返回低信息空值对象；正式 P4 只能作为可选交叉源，不能替代 Sorftime ASIN 流量词。
- `review` 可返回评论标题和内容，但星级、日期等字段可能为空；正式 VOC 仍走 P5 评论插件。
- `competitor_lookup` 精确 ASIN 模式在初测中发生 transport error，网络切换后补充复测已恢复；可用于竞品身份、价格、评分、卖家、品牌、配送和类目路径，销量 / 销售额 / BSR / 上架时间字段仍为空，不能作为销量主证据。
- `asin_prediction` 仍不稳定或低信息；正式 P4 不应把预测字段作为必需证据，只能作为可选风险上下文。

Sorftime P4-0b 已复测代表工具：`category_search_from_product_name`、`category_report`、`category_trend`、`keyword_detail`、`keyword_trend`、`keyword_extends`、`keyword_search_results`、`product_detail`、`product_trend`、`product_traffic_terms`、`competitor_product_keywords`、`product_reviews`、`similar_product_feature`。

- `category_search_from_product_name` 可返回候选类目、Top100 销量 / 销额、平均价格、平均评价、Top3 集中度、新品占比和自营占比。
- `category_report` 可返回 Top100 产品、价格、销量 / 销售额、品牌、卖家、评论数、评分、类目统计和集中度。
- `category_trend` 可返回类目销量等趋势序列；适合作为类目淡旺季和趋势交叉。
- `keyword_detail` / `keyword_trend` / `keyword_extends` 可返回搜索量、搜索排名、CPC、旺季、竞品数量、趋势序列和拓展词。
- `keyword_search_results` 可返回自然位产品、价格、销量、品牌、卖家和 Top100 销量占比。
- `product_detail` / `product_trend` 可返回 ASIN 详情、月销量 / 月销额字段和趋势序列，但 `product_detail` 需要自然语言字段解析。
- `product_traffic_terms` / `competitor_product_keywords` 可返回 ASIN 流量词、自然 / 广告曝光位置、曝光时间和关键词搜索量。
- `product_reviews` 可返回评论属性、日期、星级、标题和文本；P4 只做轻量 readiness，正式 VOC 仍在 P5。
- `similar_product_feature` 可返回热销特征及占比，但宽泛产品名可能漂移到相邻语义，正式 P4 必须使用路线化输入并与类目 / 搜索结果交叉。

## Metric Basis 设计建议

P4 deep evidence 中每个数值型 fact 或 derived metric 必须带 `metric_basis`。在兼容 P0 字段的基础上，P4 建议固定以下字段：

| 字段 | 是否必填 | 说明 |
|---|---|---|
| `source_name` | 是 | `sellersprite` / `sorftime` |
| `tool_name` | 是 | MCP 工具名 |
| `site` | 是 | 工具入参站点 |
| `marketplace` | 是 | P0 兼容字段，与 `site` 保持一致或记录映射 |
| `currency` | 是 | 价格、销售额币种；未知时必须写 `unknown` 和缺口原因 |
| `time_window` | 是 | 工具表达的业务时间窗，如实时快照、近 30 天、月度、历史区间 |
| `data_window` | 是 | P0 兼容字段，可与 `time_window` 同步 |
| `sample_scope` | 是 | Top100、SERP 前 3 页、ASIN、父体、子体、类目节点、关键词池 |
| `metric_unit` | 是 | currency、units、rank、percent、rating、rating_count、review_text_count 等 |
| `aggregation_unit` | 是 | `asin` / `parent_asin` / `child_asin` / `keyword` / `category` / `route` / `serp` |
| `parent_child_basis` | 是 | 子体、父体、变体合并、未知 |
| `collection_method` | 是 | 实时快照、历史趋势、预测、搜索结果、类目 Top100、评论抽样等 |
| `collected_at` | 是 | MCP 调用或 snapshot 生成时间 |
| `input_lineage` | 是 | 请求关键词、ASIN、类目节点、路线 ID 或上游 candidate / route 引用 |
| `node_mapping_status` | 建议 | 类目搜索节点、SellerSprite 节点、Sorftime Top100 节点是否已映射 |
| `retry_count` | 建议 | MCP 调用重试次数 |
| `error_type` | 建议 | 工具失败、传输异常、空字段、低信息返回等 |
| `raw_value` | 建议 | 原始字符串或原始数值 |
| `normalized_value` | 建议 | 归一化后的可比较数值 |
| `normalization_notes` | 建议 | 单位换算、文本解析、字段空值说明 |

## Conflict Resolution 可比较字段

P4 `conflict_resolution_packet` 建议先覆盖以下冲突类型：

| 冲突类型 | 可比较字段 | 前置条件 |
|---|---|---|
| 市场容量冲突 | 类目月销量、类目月销售额、Top100 销量 / 销售额 | 同站点、同类目节点或已映射类目、同样本范围、同时间窗 |
| 类目边界冲突 | node path、leaf node、类目排名路径、路线候选类目 | 同 ASIN 或同路线，父子体和类目层级已标注 |
| 关键词意图冲突 | SERP 产品构成、Top 产品标题 / 类目、混池比例、排除词 | 同关键词、同站点、自然 / 广告位置范围明确 |
| 销量 / 销售额口径冲突 | ASIN 月销量、月销额、类目 Top100 月销量 / 销额 | 同 ASIN 或同类目、同时间窗、同父子体口径 |
| 价格带冲突 | ASIN 价格、均价、中位价、Top 样本价格段 | 同币种、同价格单位、同样本范围 |
| 竞品样本冲突 | 代表 ASIN、品牌、卖家、自然位 ASIN、类目 Top100 | 同关键词 / 类目 / 路线范围，样本角色可解释 |
| 数据缺口冲突 | 核心字段为空、工具失败、返回低信息 | 记录工具名、字段名、影响阶段和复核动作 |

## Conflict Resolution 不可比较字段

| 字段或指标 | 不可直接比较原因 | 处理 |
|---|---|---|
| SellerSprite 商品筛选结果 vs Sorftime 自然位搜索结果 | 样本来源不同，前者是筛选 / 类目产品池，后者是 SERP 自然位 | 只做方向性混池参考，不做数值冲突 |
| SellerSprite 类目市场销量 vs Sorftime category_report Top100 | 类目路径、Top 范围和时间窗可能不同 | 先做 node 映射和 sample_scope 对齐 |
| 关键词搜索量周口径 vs 月口径 | 时间窗口不同 | 归一化或标记 `basis_mismatch` |
| ASIN 父体销量 vs 子体销量 | aggregation_unit 不同 | 记录 `parent_child_basis`，未统一前不计算差异 |
| ratings vs reviews vs 评论文本数 | 字段语义不同 | 分别建 metric，不直接相减 |
| BSR / 类目排名 / 搜索位排名 | 排名系统不同 | 记录 `collection_method`，只做趋势或位置语义判断 |
| 毛利 / 毛利率 | 成本假设不在 P4 主契约内 | 可做运营参考，不作为核心冲突 |
| 评论文本痛点 | P4 不是正式 VOC 阶段 | 只作为 VOC readiness，不进入痛点结论 |
| 预测字段 vs 历史实绩字段 | 数据性质不同 | 预测只能做风险提示，不和实绩直接判冲突 |

## P4 正式实现建议

- P4 正式实现必须先落 `mcp_snapshots/sellersprite_deep_snapshot.json` 和 `mcp_snapshots/sorftime_deep_snapshot.json`，再由 Adapter 生成 evidence packet。
- `market_structure_evidence_packet` 以 SellerSprite 为主责源，但要吸收 Sorftime `category_report`、`product_detail`、`product_trend` 作为交叉验证。
- `search_demand_evidence_packet` 以 Sorftime 为主责源，但要吸收 SellerSprite `traffic_keyword`、`keyword_research`、`keyword_miner`、ABA 工具作为交叉验证。
- P4-0b 网络切换后补充复测显示，SellerSprite `market_research`、`market_price_distribution`、`market_seller_concentration` 可作为市场结构主入口；`competitor_lookup` 精确 ASIN 可作为竞品身份 / 详情证据，但不作为销量主证据；`asin_prediction` 仍只做可选上下文。所有 SellerSprite 调用仍必须带重试、错误留痕和字段级 `data_gaps`。
- P4-0b 后，Sorftime `category_report`、`category_trend`、`product_detail`、`product_trend`、`product_traffic_terms` 和 `competitor_product_keywords` 可作为强交叉源，但必须解析中文字段和文本型数值。
- P4 必须增加 node mapping：类目搜索得到的 node、路线矩阵确认的类目、SellerSprite node path、Sorftime `category_report` node 未对齐前，不得直接比较类目容量或集中度。
- Adapter 必须保留 `raw_value`、`normalized_value`、`metric_basis`、`data_gaps` 和 `evidence_refs`。
- 工具成功但字段为空时，不得静默丢弃；必须写入 `data_gaps`。
- 工具失败时，必须记录 `errors[].tool_name`、`errors[].error_type`、`required_action` 和可替代交叉源。
- Conflict Resolver 不直接比较不同来源数字；先比较 `metric_basis`，不一致时输出 `basis_mismatch`。
- P4 不生成 VOC、evaluations、integrated judgment、report_data、HTML 或 XLSX。
