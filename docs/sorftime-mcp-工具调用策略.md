# Sorftime MCP 工具调用策略

更新日期：2026-06-12

## 定位

Sorftime MCP 在选品系统中的角色是**双阶段使用**：

1. **早期快探**：在卖家精灵数据到位之前或期间，Claude 先用 Sorftime 快速摸清方向的趋势和关键词信号
2. **深度验证**：候选方向确认后，做关键词流量、竞品词包、趋势的深度交叉验证

两个阶段使用不同工具，积分消耗和目的也不同。

---

## 三源分工一览

| 数据源 | 职责 | 模式一（模糊探索）调用时机 | 模式二（指定方向）调用时机 |
|---|---|---|---|
| 卖家精灵手动导入 | 大盘扫描、Top100 完整明细、ABA、退货率 | 阶段一结束后宽扫导出 | Sorftime 快验通过后定向导出 |
| Sorftime MCP | 类目趋势、关键词量级、竞品流量词 | 与卖家精灵导出**并行**初探 + 候选确认后深验 | 卖家精灵导出**前**快验 + 候选确认后深验 |
| 自有评论插件 | 大批量 VOC、痛点/差评证据链 | 候选进入「继续看/试做」后 | 同左 |

---

## 工具清单与调用时机

### 模式一——并行初探工具（运营导出卖家精灵期间同步调用）

> 目标：在运营操作导出的 10-20 分钟内，形成初步方向假设，等卖家精灵数据到位后直接合并。

| 工具 | 目的 | 积分 |
|---|---|---|
| `category_search_from_product_name` × 2-3 方向 | 定位各候选方向的类目节点，获取 nodeId | 1/次 |
| `category_report` × 2-3 方向 | 拉取实时 Top100 完整数据（销量、价格、集中度、新品占比） | 1/次 |
| `keyword_detail` × 主方向 2-3 主词 | 核心词搜索量 + CPC + 竞争密度 | 1/词 |
| `ali1688_similar_product` × 主方向 | 查询 1688 中国站人民币粗采购价，提前判断利润空间 | 1 |

典型消耗：6-10 积分。

### 模式二——前置验证工具（卖家精灵导出前先跑）

> 目标：6-8 积分内给出快验结论，如果方向有问题，在运营导出前就告知，避免无效操作。

| 工具 | 目的 | 积分 |
|---|---|---|
| `category_search_from_product_name` | 从产品名定位 Amazon 类目节点 | 1 |
| `category_report` | 拉取实时 Top100（销量/价格/集中度/新品占比，一次替代多次 category_trend） | 1 |
| `keyword_detail` × 2-3 主词 | 搜索量 + CPC + 首页竞品数量 | 1/词 |
| `ali1688_similar_product` | 1688 中国站采购价粗估 | 1 |

典型消耗：5-7 积分。

快验结论输出格式（固定）：

```
方向快验：[品类名]
- 趋势：增长 / 衰退 / 均衡（XX 月数据）
- 主词量级：[词]，月搜索约 X 万，CPC $Y
- 竞争密度：首页约 Z 个竞品
- 初步结论：值得继续 / 建议调整方向 / 建议放弃 + 1-2 句理由
```

快验通过后，给出定向导出建议：
- 具体关键词 2-3 个（这些词做 Top100 和 ABA 导出）
- 是否需要「选市场」宽扫（通常模式二不需要）

### 候选方向确认后（两种模式共用）

| 工具 | 调用时机 | 目的 | 积分 |
|---|---|---|---|
| `keyword_detail` / `keyword_trend` | 候选方向确认，进入深挖 | 关键词趋势 + CPC，与卖家精灵 ABA 交叉 | 1/词 |
| `keyword_extends` | 主关键词确定后 | 延伸词，发现混池词和长尾机会 | 1 |
| `keyword_search_results` | 候选边界校准后 | 首页竞品结构，与卖家精灵 Top100 对比 | 1 |
| `product_traffic_terms` | 确定重点竞品 ASIN 后 | 竞品靠哪些词拿流量，找词位空隙 | 1/ASIN |
| `competitor_product_keywords` | 同上 | 提取竞品词包，找可借鉴的流量词 | 1/ASIN |
| `potential_product` | 候选主线确认后 | 找潜力新品、向周边延展补充候选池（`similar_product` 工具不存在，统一用此替代） | 1 |
| `similar_product_feature` | 方向确认、准备深挖报告时 | 同类热销品共有特征，指导卖点提炼 | **5（谨慎调用）** |
| `product_detail` | 需要验证特定 ASIN 数据时 | 补充竞品详情字段 | 1/ASIN |
| `product_trend` | 重点竞品确定后 | 竞品 24 个月销量趋势 | 1/ASIN |

> ⚠️ 早期已调用过的 `category_trend` / `keyword_detail`，深挖阶段可直接复用，不重复调用。

---

## 工具参数速查

> Claude 在 Skill 中直接调用 MCP 工具时，按此表填参数，无需每次 ToolSearch 查 schema。

### 站点参数说明（重要）

两套不同的站点参数名，**混用会静默失效**：

| 参数名 | 适用工具 |
|---|---|
| `amzSite` | `search_categories_broadly`、`category_search_from_product_name`、`category_trend`、`category_report`、`category_report_from_history`、`product_traffic_terms`、`similar_product_feature`、`potential_product` |
| `keywordSupportSite` | `keyword_list`、`keyword_detail`、`keyword_trend`、`keyword_extends`、`keyword_search_results`、`competitor_product_keywords` |

站点值统一用大写：`US` / `GB` / `DE` / `CA` / `JP` 等。

---

### 类目工具

#### `search_categories_broadly`
无方向时广域扫类目，按月销量倒序。

```
必填：无
常用可选：
  amzSite: "US"
  month_sales_volume_min: 50000        # 过滤太小的类目
  top3Product_sales_share_max: 0.4     # 排除垄断类目（Top3 占比 < 40%）
  amazonOwned_sales_share_max: 0.1     # 排除亚马逊自营强势类目
  newproduct_sales_share_min: 0.03     # 新品有机会（新品占比 > 3%）
```

#### `category_search_from_product_name`
从品类名/产品名定位细分类目，获取 nodeId。

```
必填：productName: "window squeegee"   # 英文品类名
常用可选：
  amzSite: "US"
```

#### `category_report` ⭐ 主力工具
查询指定类目**实时** Top100 产品完整数据报告（ASIN、价格、月销量、评分、评论数、上架时间、品牌、卖家）。**比 category_trend 数据量大得多，一次调用替代多次 category_trend。**

```
必填：nodeId: "2245500011"             # 注意驼峰：nodeId
常用可选：
  amzSite: "US"
```

#### `category_report_from_history`
查询指定类目**指定历史时间段**的 Top100 数据（最长 40 天）。用于对比旺季 vs 淡季产品结构。

```
必填：
  nodeId: "2245500011"
  startDate: "2025-10-01"            # 格式 yyyy-MM-dd
  endDate: "2025-10-31"              # 与 startDate 间隔不超过 40 天
常用可选：
  amzSite: "US"
```

#### `category_trend`
查类目历史趋势数据（24 个月）。**nodeId 来自上一步的返回值。**

```
必填：nodeId: "2245500011"             # 注意驼峰：nodeId，不是 node_id
常用可选：
  amzSite: "US"
  trendIndex: "SalesCount"            # 默认月销量；其他可选值：
                                      # NewProductSalesAmountShare（新品占比）
                                      # Top3ProductSalesAmountShare（Top3 集中度）
                                      # AmazonSalesAmountShare（亚马逊自营占比）
```

> 每次只返回一个 trendIndex 的数据，多维度需多次调用。快验时只调 `SalesCount` 即可。

---

### 关键词工具

#### `keyword_detail`
查单个关键词的月搜索量、周搜索量、CPC、首页竞品数。

```
必填：keyword: "window squeegee with extension pole"
常用可选：
  keywordSupportSite: "US"
```

#### `keyword_trend`
查关键词历史搜索量趋势（判断是增长/衰退/季节性）。

```
必填：keyword: "window squeegee"
常用可选：
  keywordSupportSite: "US"
```

#### `keyword_extends`
从主词延展相关词，发现长尾词和混池词。

```
必填：keyword: "window squeegee"
常用可选：
  keywordSupportSite: "US"
  page: 1                             # 每页 20 条
```

#### `keyword_search_results`
查关键词自然位搜索结果产品清单（首页竞品结构）。

```
必填：keyword: "window squeegee"
常用可选：
  keywordSupportSite: "US"
  positionType: 1                     # 1=仅自然位（默认），2=仅广告，0=全部
  page: 1
```

#### `keyword_list`
热搜词榜单（无特定关键词时探索用）。

```
必填：无
常用可选：
  keywordSupportSite: "US"
  search_volume_min: 10000            # 过滤太冷门的词
```

---

### 竞品工具

#### `product_traffic_terms`
反查某 ASIN 靠哪些词曝光在前 3 页（含自然位+广告）。

```
必填：asin: "B0CDBVC1W7"
常用可选：
  amzSite: "US"
  page: 1                             # 每页 20 条，一般第 1 页够用
```

#### `competitor_product_keywords`
查某 ASIN 的竞品在各核心词下的**自然位**曝光（评估流量能力）。

```
必填：asin: "B0CDBVC1W7"
常用可选：
  keywordSupportSite: "US"
  page: 1
```

> `product_traffic_terms` vs `competitor_product_keywords`：
> - 前者：这个产品在哪些词有曝光 → 用于找词位空隙
> - 后者：这个产品的竞品在核心词下排名如何 → 用于评估竞争强度

#### `potential_product`
搜索潜力新品，补充候选池。

```
必填：无
常用可选：
  amzSite: "US"                       # 注意：只支持 US/GB/DE
  searchName: "window squeegee"       # 品类关键词
  month_sales_volume_min: 1000
  price_min: 15
  price_max: 60
```

#### `similar_product_feature`
查同类热销品共有特征（卖点提炼用）。**消耗 5 积分，谨慎调用。**

```
必填：productName: "window squeegee"  # 品类英文名
常用可选：
  amzSite: "US"
```

#### `ali1688_similar_product` ⭐ 供应链 / 利润信号
在 1688 中国站搜索同类采购货源，返回人民币采购价区间和供应商信息。**用于早期粗估采购价，提前判断利润空间是否存在，不替代运营手填的精确利润复核。**

采购价口径：

- 当前访问方式：通过 Sorftime MCP `ali1688_similar_product` 间接查询 1688，不在项目内直接抓取 `https://www.1688.com/` 页面。
- 原始来源必须是 **1688 中国站**：入口口径为 `https://www.1688.com/`，商品详情页可接受 `https://detail.1688.com/offer/...` 等 `*.1688.com` 链接。
- 默认只看 **1688 中国站 RMB 报价**。
- 价格字段按人民币 RMB/CNY 解析；折 USD 只作报告展示，不作为原始采购价来源。
- `searchName` 必须优先使用中文品类词，例如“免手持狗绳 腰带牵引绳”。
- 优先筛“一件代发 / 现货 / 跨境 / 包邮 / 48 小时发货”等供应链信号。
- 返回价不等于最终到手成本，还要补 SKU 实际价、运费、包装、头程、关税、质检、损耗。
- **禁止用 Alibaba 国际站 USD 报价替代 1688 中国站采购价。** 非 `1688.com` 来源或币种不是 RMB/CNY 的样本，只能记录为待复核/无效样本，不进入采购价区间。

```
必填：searchName: "刮窗器"            # 中文品类名
```

> ⚠️ 无站点参数。返回数据为 1688 中国站人民币报价，需自行折算美元并估算头程/关税成本。

---

### ⚠️ 已知陷阱

| 问题 | 说明 |
|---|---|
| `similar_product` 工具不存在 | 策略文档曾提及，实际 MCP 无此工具；用 `potential_product` 替代 |
| `category_trend` 参数名是 `nodeId` | 驼峰格式，写成 `node_id` 会报错 |
| 站点参数两套 | 类目工具用 `amzSite`，关键词/竞品工具用 `keywordSupportSite`，不可混用 |
| `potential_product` 站点限制 | 只支持 US/GB/DE，其他站点不返回数据 |
| `category_trend` 单次单指标 | 每次只返回一个 `trendIndex`，需要多维度时多次调用 |

---

## 调用原则

1. **初探轻量，深验按需**：初探阶段只调类目和关键词量级，不在方向未定前跑竞品工具。
2. **`similar_product_feature` 限制调用**：消耗 5 积分，只在候选方向已确认、准备正式深挖时调用一次。
3. **关键词工具按词数控制**：主关键词 2-3 个，备选词 1 个，不对大词包逐一跑趋势。
4. **竞品工具按 ASIN 控制**：优先 Top3-5 标杆竞品，不对整个 Top100 逐一跑。
5. **评论不依赖 Sorftime**：`product_reviews` 只有近 1 年最多 100 条，VOC 证据链由自有插件承担。

---

## 数据写入 candidate_pool

Sorftime 验证结论写入 candidate_pool 的 `sorftime_verification` 字段组：

```json
{
  "sorftime_verification": {
    "verified_at": "2026-06-12",
    "early_exploration": {
      "stage": "模式一并行初探 / 模式二前置快验",
      "conclusion": "值得继续 / 建议调整 / 建议放弃",
      "reason": "..."
    },
    "category_trend": {
      "trend_direction": "增长/衰退/均衡/季节性",
      "monthly_sales_24m": [],
      "top3_concentration_trend": "集中/分散/恶化",
      "new_product_share_trend": "上升/下降/均衡"
    },
    "keyword_verification": [
      {
        "keyword": "示例关键词",
        "weekly_search_volume": 0,
        "monthly_search_volume": 0,
        "cpc": 0.0,
        "seasonality": "均衡/旺季Q4",
        "competitor_count": 0,
        "trend_direction": "增长/衰退/均衡"
      }
    ],
    "traffic_terms": {
      "asin": "",
      "top_traffic_words": [],
      "gap_opportunities": []
    },
    "category_report_snapshot": {
      "category_name": "类目名",
      "nodeId": "类目节点",
      "products": [
        {
          "asin": "",
          "title": "",
          "brand": "",
          "price": 0,
          "monthly_sales": 0,
          "rating": 0,
          "rating_count": 0,
          "listing_days": 0
        }
      ]
    },
    "supply_chain_signal": {
      "searchName": "1688 搜索词",
      "source_site": "1688中国站",
      "source_url": "https://www.1688.com/",
      "quote_currency": "RMB",
      "exchange_rate": 7.2,
      "rejected_sample_count": 0,
      "rejection_reasons": [],
      "products": [
        {
          "title": "",
          "price": "12-18",
          "quote_currency": "RMB",
          "supplier": "",
          "url": "https://detail.1688.com/offer/..."
        }
      ]
    }
  }
}
```

写入规则：

| 字段 | 来源工具 | 下游用途 |
|---|---|---|
| `category_report_snapshot` | `category_report` | 生成 `demand_evidence.sorftime_category_report`，补市场规模、Top10 集中度、新品占比和报告市场章节 |
| `supply_chain_signal` | `ali1688_similar_product` | 生成 `preliminary_profit_space.supply_chain_signal`，补利润章节的 1688 中国站人民币粗采购价信号 |

---

## 成本参考

| 阶段 | 典型工具组合 | 消耗 |
|---|---|---|
| 模式一并行初探 | `category_search_from_product_name` × 2-3 + `category_report` × 2-3 + `keyword_detail` × 2-3 + `ali1688_similar_product` | 6-10 积分 |
| 模式二前置快验 | `category_search_from_product_name` + `category_report` + `keyword_detail` × 2-3 + `ali1688_similar_product` | 5-7 积分 |
| 深度验证（共用） | 关键词工具 + 竞品流量词 + `similar_product_feature` | 15-25 积分 |
| **合计（一次完整调研）** | — | **约 20-35 积分** |
