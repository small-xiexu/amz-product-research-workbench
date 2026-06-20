# Sorftime MCP 工具调用策略

更新日期：2026-06-20

Sorftime MCP 用来补齐 Amazon 实时类目、参考 ASIN、关键词需求、自然位、类目趋势和热销特征。调用目标是提高判断质量，不以节省积分或减少调用为主要约束。

核心顺序：

```text
Stage 1 快探 -> Stage 5.1 评论前轻量路线校准 -> Stage 7 正式深扫

初始方向/种子词 -> 候选类目 -> 参考 ASIN -> ASIN 反查词 -> 运营式关键词池 -> 类目/词/VOC 交叉验证
```

## 数据分工

| 数据源 | 主要用途 | 不能替代 |
|---|---|---|
| Sorftime MCP | 类目搜索、类目 Top100、类目趋势、关键词详情、关键词扩展、关键词搜索结果、ASIN 流量词、竞品关键词、热销特征 | 卖家精灵 ABA、卖家精灵完整 Top100、评论 VOC |
| 卖家精灵 | 市场容量、Top100 历史明细、关键词反查、ABA、价格带、集中度、新品榜/新品样本 | Sorftime 实时类目、ASIN 流量词、MCP 工具快探 |
| 评论插件 | 差评痛点、好评驱动、规格/测试项 | 搜索量、类目容量、价格带分布 |

## Stage 1 快探

Stage 1 的目标是建立候选 ASIN 和候选类目，不用关键词直接定义市场。

| 工具 | 调用对象 | 输出用途 |
|---|---|---|
| `category_search_from_product_name` | 每个候选方向/路线英文抽象名 | 找候选类目和 nodeId |
| `category_report` | 每个候选类目 nodeId | 看 Top100 体量、价格、集中度、新品、代表 ASIN |
| `keyword_search_results` | 种子词、路线词、候选词 | 看搜索结果是否为相似产品，识别混池 |
| `keyword_detail` | 种子词、路线词、候选词 | 记录月搜、CPC、竞争量，只作需求信号 |

建议补充：

| 工具 | 使用条件 | 输出用途 |
|---|---|---|
| `potential_product` | 需要找潜力新品或相邻候选 | 补参考 ASIN 和新品观察样本 |
| `similar_product_feature` | 已有较明确路线，需要看热销共同特征 | 补产品规格和卖点观察 |
| `category_trend` / `category_report_from_history` | 需要初步判断淡旺季 | 看类目销量趋势，不用关键词趋势替代 |

Stage 1 输出到快探结论时，必须包含：

- 候选参考 ASIN：ASIN、路线、角色、相似原因、来源。
- 候选类目池：类目名、nodeId、角色、来源、风险标签。
- 关键词入口：只说明用于找竞品或验证流量。
- 主要混池：场景、产品形态、品牌、材质、耗材、配件等。
- 价格带上下文：候选市场价格分布、销量集中带、目标切入口。
- 卖家精灵下一步导出清单：大类、小类、参考 ASIN、反查词、ABA、新品数据。

## Stage 5.1 评论前轻量路线校准

Stage 5.1 的目标是在评论插件采集前校正路线边界和 VOC ASIN 批次。它不追求完整深扫，不输出最终机会判断，也不能替代 Stage 7 的 `search_demand_evidence`。

默认输出：

```text
runs/<run_id>/mcp/route_sorftime_calibration.json
```

| 模块 | 必调或复用工具 | 最低覆盖 | 判断用途 |
|---|---|---|---|
| 候选类目 | `category_report`、`category_trend` 或 `category_report_from_history` | 入围小类或混池高风险类目 | 判断路线是否落在同一市场、是否有淡旺季或集中度风险 |
| 代表 ASIN | `product_traffic_terms` | 2-3 个 ASIN：主线标杆、高客单/升级、新品或低评有量样本 | 判断 VOC ASIN 是否代表真实流量入口 |
| 核心词扩展 | `keyword_extends` | 1-2 个核心词 | 发现场景词、长尾词、混池词和排除词 |
| 关键词详情 | `keyword_detail` | 主线词、场景词或精准长尾词 | 快速判断词量、CPC、竞争量和产品意图 |
| 混池复核 | `keyword_search_results` 或 `competitor_product_keywords` | 混池词、升级款词或场景词按需补查 | 决定是否降级、对照或排除 |

输出必须包含：

- 路线边界：保留、观察、合并、排除。
- VOC ASIN 批次调整：保留、补抓、替换、对照或排除。
- Stage 7 深扫待办：类目、ASIN、关键词。
- `data_gaps`：工具不可用、样本不足、返回异常或需要运营补导的点。

## Stage 7 深扫

Stage 7 的目标是支撑市场机会报告。即使 Stage 1 已经调用过、Stage 5.1 已经完成轻量校准，也要围绕确认路线、参考 ASIN Top5/Top10、候选大小类目和运营式关键词池补齐证据。

| 模块 | 必调或复用工具 | 最低覆盖 |
|---|---|---|
| 候选类目 | `category_search_from_product_name`、`category_report` | 入围路线的大类、小类、混池/对照类目 |
| 类目淡旺季 | `category_trend` 或 `category_report_from_history` | 候选大类和小类；至少销量趋势，必要时补新品占比/集中度趋势 |
| 搜索结果混池 | `keyword_search_results` | 主查词、补查词、关键长尾词 |
| 关键词详情 | `keyword_detail` | 主查词、补查词、场景词、精准长尾词 |
| 关键词扩展 | `keyword_extends` | 核心词；扩展词必须标来源，不能写成人工精选词 |
| ASIN 流量词 | `product_traffic_terms` | 每条保留路线 Top5/Top10 参考 ASIN，至少主推代表、高销量对照、新品样本、高客单对照 |
| 竞品自然位词 | `competitor_product_keywords` | 主推/升级路线参考 ASIN |
| 热销特征 | `similar_product_feature` | 最终入围路线 |

Stage 7 输出必须落到 `search_demand_evidence`，至少包含：

- `reference_asin_inputs`
- `category_candidates`
- `asin_traffic_terms`
- `keyword_pool_by_role`
- `keyword_validation`
- `category_seasonality`
- `hot_product_features`
- `seller_sprite_conflicts`
- `data_gaps`

## 关键词分层规则

| 角色 | 来源优先级 | 用途 |
|---|---|---|
| `main_traffic` | 多个参考 ASIN 命中 + 搜索结果相似 + 有量 | 看大入口，不直接定义市场 |
| `conversion_quality` | 参考 ASIN 反查 + ABA/卖家精灵交叉验证 | 优先验证转化质量 |
| `traffic` | 有量但意图较宽或混池轻微 | 观察，不直接进主结论 |
| `precise_long_tail` | 长尾、场景/规格明确、与路线贴近 | 验证小类目和 Listing 方向 |
| `mixed_or_excluded` | 搜索结果或 ASIN 命中其他形态/场景 | 排除或对照，必须保留证据 |

每个关键词必须记录：

- `keyword`
- `keyword_role`
- `source_type`
- `source_refs`
- `route_refs`
- `matched_asin_count`
- `matched_asins`
- `monthly_search_volume`
- `cpc`
- `competition_count`
- `organic_positions`
- `click_or_conversion_signal`
- `mix_pool_tags`
- `recommended_action`
- `reason`
- `confidence`
- `lineage`

## 工具参数速查

### 站点参数

| 参数名 | 适用工具 |
|---|---|
| `amzSite` | `search_categories_broadly`、`category_search_from_product_name`、`category_trend`、`category_report`、`category_report_from_history`、`product_traffic_terms`、`similar_product_feature`、`potential_product` |
| `keywordSupportSite` | `keyword_list`、`keyword_detail`、`keyword_trend`、`keyword_extends`、`keyword_search_results`、`competitor_product_keywords` |

站点值统一用大写：`US` / `GB` / `DE` / `CA` / `JP`。

### 类目工具

#### `search_categories_broadly`

无方向时广域扫类目，按月销量倒序。

```text
常用可选：
  amzSite: "<站点>"
  month_sales_volume_min: <最小月销量>
  top3Product_sales_share_max: <Top3 商品占比上限>
  amazonOwned_sales_share_max: <Amazon 自营占比上限>
  newproduct_sales_share_min: <新品销量占比下限>
```

#### `category_search_from_product_name`

从品类名/路线名定位候选类目，获取 nodeId。

```text
必填：
  productName: "<英文品类名或路线抽象名>"
常用可选：
  amzSite: "<站点>"
```

#### `category_report`

查询指定类目实时 Top100 产品报告，常用于补 ASIN、价格、销量、评分、评论数、上架时间、品牌、卖家。

```text
必填：
  nodeId: "<类目节点ID>"
常用可选：
  amzSite: "<站点>"
```

#### `category_report_from_history`

查询指定历史时间段的 Top100 数据，最长 40 天。用于对比旺季和淡季产品结构。

```text
必填：
  nodeId: "<类目节点ID>"
  startDate: "<yyyy-MM-dd>"
  endDate: "<yyyy-MM-dd>"
常用可选：
  amzSite: "<站点>"
```

#### `category_trend`

查类目历史趋势数据。nodeId 来自类目搜索或类目报告。

```text
必填：
  nodeId: "<类目节点ID>"
常用可选：
  amzSite: "<站点>"
  trendIndex: "SalesCount"
```

常用 `trendIndex`：

| 值 | 用途 |
|---|---|
| `SalesCount` | 类目销量趋势 |
| `NewProductSalesAmountShare` | 新品销售额占比趋势 |
| `Top3ProductSalesAmountShare` | Top3 商品集中度趋势 |
| `AmazonSalesAmountShare` | Amazon 自营占比趋势 |

### 关键词工具

#### `keyword_detail`

查单个关键词的月搜索量、周搜索量、CPC、首页竞品数。

```text
必填：
  keyword: "<关键词>"
常用可选：
  keywordSupportSite: "<站点>"
```

#### `keyword_trend`

查关键词历史搜索量趋势。只能说明搜索热度，不能替代类目淡旺季。

```text
必填：
  keyword: "<关键词>"
常用可选：
  keywordSupportSite: "<站点>"
```

#### `keyword_extends`

从核心词延展相关词，发现长尾词、场景词和混池词。

```text
必填：
  keyword: "<核心词>"
常用可选：
  keywordSupportSite: "<站点>"
  page: <页码>
```

#### `keyword_search_results`

查关键词自然位搜索结果产品清单，用于判断该词是否被相似产品覆盖。

```text
必填：
  keyword: "<关键词>"
常用可选：
  keywordSupportSite: "<站点>"
  positionType: 1
  page: <页码>
```

#### `keyword_list`

热搜词榜单。无明确种子词时可探索，但不能直接当市场结论。

```text
常用可选：
  keywordSupportSite: "<站点>"
  search_volume_min: <最小搜索量>
```

### 竞品工具

#### `product_traffic_terms`

反查某 ASIN 靠哪些词曝光在前 3 页。

```text
必填：
  asin: "<参考 ASIN>"
常用可选：
  amzSite: "<站点>"
  page: <页码>
```

#### `competitor_product_keywords`

查某 ASIN 的竞品在各核心词下的自然位曝光，评估流量获取能力和竞争强度。

```text
必填：
  asin: "<参考 ASIN>"
常用可选：
  keywordSupportSite: "<站点>"
  page: <页码>
```

#### `potential_product`

搜索潜力新品，补充候选 ASIN 池。

```text
常用可选：
  amzSite: "<站点>"
  searchName: "<英文品类词或路线词>"
  month_sales_volume_min: <最小月销量>
  price_min: <最低价>
  price_max: <最高价>
```

注意：该工具站点支持范围以 MCP 实际返回为准；不支持时写入 `data_gaps`。

#### `similar_product_feature`

查同类热销品共有特征，用于提炼规格、卖点和体验验证项。

```text
必填：
  productName: "<英文品类名或路线抽象名>"
常用可选：
  amzSite: "<站点>"
```

## 已知陷阱

| 问题 | 说明 |
|---|---|
| `similar_product` 工具不存在 | 用 `potential_product` 替代 |
| `category_trend` 参数名是 `nodeId` | 驼峰格式，写成 `node_id` 会报错 |
| 站点参数两套 | 类目/竞品流量工具用 `amzSite`，关键词工具用 `keywordSupportSite` |
| `category_trend` 单次单指标 | 多指标需要多次调用 |
| 关键词趋势不是类目淡旺季 | 关键词只能代表搜索热度，产品淡旺季看类目/市场数据 |
| 扩展词不是人工精选词 | `keyword_extends` 产出的词必须保留来源和置信度 |

## 写入对象

Sorftime 输出优先写入 `search_demand_evidence`，必要时同步给候选池或分析包。

```json
{
  "search_demand_evidence": {
    "reference_asin_inputs": [],
    "category_candidates": [],
    "asin_traffic_terms": [],
    "keyword_pool_by_role": {
      "main_traffic": [],
      "conversion_quality": [],
      "traffic": [],
      "precise_long_tail": [],
      "mixed_or_excluded": []
    },
    "keyword_validation": [],
    "category_seasonality": [],
    "hot_product_features": [],
    "seller_sprite_conflicts": [],
    "data_gaps": []
  }
}
```

## 调用自检

- 是否先建立参考 ASIN，再反查关键词。
- 是否同时覆盖候选大类、小类、混池/对照类目。
- 是否把关键词分成主要流量词、转化优质词、流量词、精准长尾词、混池/排除词。
- 是否把扩展词标成系统扩展来源。
- 是否分开展示类目淡旺季和关键词搜索热度。
- 是否保留了混池词和排除原因。
- 是否把未调用、失败、数据不足写入 `data_gaps`。
