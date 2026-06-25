# 卖家精灵 MCP 工具完整参考

> 来源：https://open.sellersprite.com/api/1 （编号切换 1～61）
> 提取日期：2026-06-24
> 共计 44 个 MCP 工具

---

## 公共约定

| 项目 | 说明 |
|------|------|
| API 网关 | `https://api.sellersprite.com` |
| 鉴权方式 | Header: `secret-key` + `Content-Type: application/json;charset=utf-8` |
| 公共返回格式 | `{ "code": "OK", "message": "...", "data": {...} }` |
| Token 优化 | 所有 MCP 工具支持 `returnFields` 参数选择性返回字段 |
| 并发限制 | 40 次/分钟 |
| 数据上限 | 同一查询条件最多返回 TOP 2000 条 |
| 可用次数查询 | `GET /v1/visits`（返回当月剩余次数） |

### 公共错误码

| Code | 含义 |
|------|------|
| `OK` | 成功 |
| `ERROR_URL_NOT_FOUND` | URL 未找到 |
| `ERROR_SERVER_INTERNAL` | 服务器内部错误 |
| `ERROR_PARAM` | 参数错误 |
| `ERROR_SECRET_KEY` | 秘钥错误 |
| `ERROR_SECRET_KEY_OVERDUE` | 秘钥过期 |
| `ERROR_VISIT_MAX` | 访问次数已达上限 |
| `ERROR_SECRET_KEY_INVALID` | 秘钥无效 |

---

## 一、竞品查询

### 1. competitor_lookup — 查竞品

- **文档页**: `/api/1`
- **方法**: `POST`
- **路径**: `/v1/product/competitor-lookup`
- **描述**: 查目标 ASIN 的销量和销额等详细数据

| # | 参数 | 类型 | 必填 | 说明 |
|---|------|------|------|------|
| 1 | `marketplace` | String | ✓ | 市场编码，见附录表 1.2 |
| 2 | `month` | String | | 查询月份，yyyyMM 格式（如 202507） |
| 3 | `brand` | String | | 品牌 |
| 4 | `sellerName` | String | | 卖家名称 |
| 5 | `asins` | List | | ASIN 列表，最多 40 个 |
| 6 | `nodeIdPath` | String | | 类目节点 ID 字符串 |
| 7 | `nodeIdPathEqual` | boolean | | true=精确类目，false=当前及子类目（默认 false） |
| 8 | `keyword` | String | | 关键词 |
| 9 | `matchType` | Integer | | 匹配方式：1=词组，2=模糊（默认），3=精准 |
| 10 | `variation` | String | | N=包含变体，Y=排除变体 |
| 11 | `page` | Integer | | 页码，默认 1 |
| 12 | `size` | Integer | | 每页条数，默认 50，最大 100 |
| 13 | `order.field` | String | | 排序字段，默认 total_units，见表 1.6 |
| 14 | `order.desc` | boolean | | true=降序（默认），false=升序 |

---

## 二、选产品

### 2. product_research — 选产品

- **文档页**: `/api/2`
- **方法**: `POST`
- **路径**: `/v1/product/research`
- **描述**: 根据销量销额增长等各个维度设定条件来筛选产品

| # | 参数 | 类型 | 必填 | 说明 |
|---|------|------|------|------|
| 1 | `marketplace` | String | ✓ | 市场编码 |
| 2 | `month` | String | | 查询月份，yyyyMM 格式 |
| 3 | `keyword` | String | | 关键字 |
| 4 | `includeSellers` | String | | 包含卖家 |
| 5 | `excludeSellers` | String | | 排除卖家 |
| 6 | `matchType` | Integer | | 匹配方式：1=词组，2=模糊（默认），3=精准 |
| 7 | `excludeKeywords` | String | | 排除的关键字 |
| 8～9 | `minPrice` / `maxPrice` | Float | | 价格区间 |
| 10～11 | `minRating` / `maxRating` | Float | | 评分区间 |
| 12～13 | `minRatings` / `maxRatings` | Integer | | 评分数区间 |
| 14～15 | `minRatingsCv` / `maxRatingsCv` | Integer | | 月新增评分数区间 |
| 16～17 | `minSellers` / `maxSellers` | Integer | | 卖家数量区间 |
| 18～19 | `minProfit` / `maxProfit` | Float | | 毛利率区间 |
| 20～21 | `minBsr` / `maxBsr` | Integer | | 大类 BSR 排名区间 |
| 22～23 | `minBsrCv` / `maxBsrCv` | Integer | | BSR 增长数区间 |
| 24～25 | `minBsrCr` / `maxBsrCr` | Float | | BSR 增长率区间 |
| 26～27 | `minUnits` / `maxUnits` | Integer | | 月销量区间 |
| 28～29 | `minAmzUnit` / `maxAmzUnit` | Integer | | 子体月销量区间 |
| 30～31 | `minRevenue` / `maxRevenue` | Float | | 月销售额区间 |
| 32～33 | `minRevenueCr` / `maxRevenueCr` | Float | | 月销售额增长率区间 |
| 34～35 | `minUnitsCr` / `maxUnitsCr` | Float | | 月销量增长率区间 |
| 36 | `weightUnit` | String | | 重量单位，默认 g |
| 37～38 | `minWeights` / `maxWeights` | Float | | 重量区间 |
| 39～40 | `minVariations` / `maxVariations` | Integer | | 变体数区间 |
| 41 | `filterSub` | String | | 是否筛选子类目，Y=是 |
| 42～43 | `minSubBsrRank` / `maxSubBsrRank` | Integer | | 子类排名区间 |
| 44 | `includeBrands` | String | | 包含品牌 |
| 45 | `excludeBrands` | String | | 排除品牌 |
| 46 | `nodeIdPaths` | List | | 类目节点字符串列表 |
| 47 | `nodeIdPathEqual` | boolean | | true=精确类目，false=当前及子类目 |
| 48 | `availableMonth` | Integer | | 上架月份 |
| 49 | `dimensionType` | String | | 尺寸类型，逗号分隔 |
| 50～51 | `minFba` / `maxFba` | Float | | FBA 运费区间 |
| 52～53 | `minLqs` / `maxLqs` | Float | | Listing 质量分区间 |
| 54 | `sellerNation` | String | | 卖家所属地，逗号分隔 |
| 55 | `badgeBS` | String | | 有 Best Seller 标识：Y |
| 56 | `badgeAC` | String | | 有 Amazon's Choice 标识：Y |
| 57 | `badgeNR` | String | | 有 New Release 标识：Y |
| 58 | `fulfillment` | String | | 配送方式：AMZ/FBA/FBM，逗号分隔 |
| 59 | `variation` | String | | N=含变体，Y=不含变体 |
| 60 | `page` | Integer | | 页码，默认 1，最多 2000 条 |
| 61 | `size` | Integer | | 每页条数，默认 50，最大 100 |
| 62 | `order.field` | String | | 排序字段，默认 total_units |
| 63 | `order.desc` | boolean | | true=降序（默认），false=升序 |

---

## 三、ASIN 详情与趋势

### 3. asin_detail — ASIN 详情

- **文档页**: `/api/3`
- **方法**: `GET`
- **路径**: `/v1/asin/{marketplace}/{asin}`
- **描述**: ASIN 详情信息集中展示（上架日期、BSR 排名、A+、五点描述等）

| # | 参数 | 类型 | 必填 | 说明 |
|---|------|------|------|------|
| 1 | `marketplace` | String | ✓ | 市场编码（路径参数） |
| 2 | `asin` | String | ✓ | ASIN（路径参数） |

### 4. asin_coupon_trend — ASIN 优惠趋势

- **文档页**: `/api/56`
- **方法**: `GET`
- **路径**: `/v1/asin/{marketplace}/{asin}/coupon-trend`
- **描述**: ASIN 的优惠趋势数据

| # | 参数 | 类型 | 必填 | 说明 |
|---|------|------|------|------|
| 1 | `marketplace` | String | ✓ | 市场编码（路径参数） |
| 2 | `asin` | String | ✓ | ASIN（路径参数） |

### 5. asin_detail_with_coupon_trend — ASIN 详情及优惠趋势

- **文档页**: `/api/57`
- **方法**: `GET`
- **路径**: `/v1/asin/{marketplace}/{asin}/with-coupon-trend`
- **描述**: ASIN 详情 + 优惠趋势合并查询

| # | 参数 | 类型 | 必填 | 说明 |
|---|------|------|------|------|
| 1 | `marketplace` | String | ✓ | 市场编码（路径参数） |
| 2 | `asin` | String | ✓ | ASIN（路径参数） |

### 6. asin_sales_trend — ASIN 销量趋势

- **文档页**: `/api/61`
- **方法**: `GET`
- **路径**: `/v1/asin/{marketplace}/{asin}/sales-trend`
- **描述**: 查询 ASIN 父体、子体的销量和销售额趋势数据

| # | 参数 | 类型 | 必填 | 说明 |
|---|------|------|------|------|
| 1 | `marketplace` | String | ✓ | 市场编码（路径参数） |
| 2 | `asin` | String | ✓ | ASIN（路径参数） |

### 7. asin_prediction — ASIN 销量预测

- **文档页**: `/api/27`
- **方法**: `GET`
- **路径**: `/v1/sales/prediction/asin`
- **描述**: 输入 ASIN 进行销量预测

| # | 参数 | 类型 | 必填 | 说明 |
|---|------|------|------|------|
| 1 | `marketplace` | String | ✓ | 市场编码 |
| 2 | `asin` | String | ✓ | ASIN |

### 8. bsr_prediction — BSR 销量预测

- **文档页**: `/api/26`
- **方法**: `GET`
- **路径**: `/v1/sales/prediction/bsr`
- **描述**: 根据 BSR 值预测销量

| # | 参数 | 类型 | 必填 | 说明 |
|---|------|------|------|------|
| 1 | `marketplace` | String | ✓ | 市场编码 |
| 2 | `bsr` | Integer | ✓ | 大类排名 |
| 3 | `categoryId` | String | ✓ | 一级类目节点 ID |

---

## 四、关键词分析

### 9. traffic_keyword — 关键词反查（流量词列表）

- **文档页**: `/api/14`
- **方法**: `POST`
- **路径**: `/v1/traffic/keyword`
- **描述**: 查询 ASIN 近 30 天内进入过搜索结果前 3 页的所有搜索流量词

| # | 参数 | 类型 | 必填 | 说明 |
|---|------|------|------|------|
| 1 | `marketplace` | String | ✓ | 市场编码 |
| 2 | `asin` | String | ✓ | ASIN |
| 3 | `keyword` | String | | 关键词过滤 |
| 4 | `month` | String | | 历史月份，不传默认最近 30 天 |
| 5 | `badges` | List | | 流量词类型，见表 1.10 |
| 6 | `trafficKeywordTypes` | List | | 流量占比类型，见表 2.0 |
| 7 | `conversionKeywordTypes` | List | | 流量转化类型，见表 2.1 |
| 8 | `page` | Integer | | 页码，默认 1 |
| 9 | `size` | Integer | | 每页条数，默认 50，最大 100，最多 2000 条 |
| 10 | `order.field` | String | | 排序字段，默认 rankPosition |
| 11 | `order.desc` | Boolean | | false=升序 |

### 10. keyword_research — 关键词选品

- **文档页**: `/api/10`
- **方法**: `POST`
- **路径**: `/v1/keyword-research`
- **描述**: 通过关键词的月搜索量、购买率等数据，找出细分市场商机

| # | 参数 | 类型 | 必填 | 说明 |
|---|------|------|------|------|
| 1 | `marketplace` | String | ✓ | 市场编码 |
| 2 | `month` | String | | 筛选日期，yyyyMM 格式，支持近 24 个月 |
| 3 | `departments` | List | | 类目 code 列表 |
| 4 | `keywords` | String | | 关键词 |
| 5 | `excludeKeywords` | String | | 排除的关键字 |
| 6～7 | `minSearches` / `maxSearches` | Integer | | 月搜索量区间 |
| 8～9 | `minSearchesCr` / `maxSearchesCr` | Float | | 月搜索量增长率区间 |
| 10～11 | `minProducts` / `maxProducts` | Integer | | 商品数区间 |
| 12～13 | `minPurchases` / `maxPurchases` | Integer | | 购买量区间 |
| 14～15 | `minPurchaseRate` / `maxPurchaseRate` | Float | | 购买率区间 |
| 16 | `withYearlyGrowth` | Boolean | | 新细分市场，默认 false |
| 17～18 | `minSearchMonthCv` / `maxSearchMonthCv` | Integer | | 月搜索同比增长值区间 |
| 19～20 | `minSearchMonthCr` / `maxSearchMonthCr` | Float | | 月搜索同比增长率区间 |
| 21～22 | `minSearchNearlyCv` / `maxSearchNearlyCv` | Integer | | 近 3 个月增长值区间 |
| 23～24 | `minSearchNearlyCr` / `maxSearchNearlyCr` | Float | | 近 3 个月增长率区间 |
| 25 | `marketPeriod` | String | | 市场周期，见表 1.7 |
| 26～27 | `minAvgPrice` / `maxAvgPrice` | Float | | 均价区间 |
| 28～29 | `minRatings` / `maxRatings` | Integer | | 评分数区间 |
| 30～31 | `minRating` / `maxRating` | Float | | 评分值区间 |
| 32～33 | `minBid` / `maxBid` | Float | | PPC 竞价区间 |
| 34～35 | `minAraClickRate` / `maxAraClickRate` | Float | | 点击集中度区间 |
| 36～37 | `minGoodsValue` / `maxGoodsValue` | Float | | 货流值区间 |
| 38～39 | `minSupplyDemandRatio` / `maxSupplyDemandRatio` | Float | | 供需比区间 |
| 40～41 | `minWordCount` / `maxWordCount` | Integer | | 单词个数区间 |
| 42 | `page` | Integer | | 页码，默认 1 |
| 43 | `size` | Integer | | 每页条数，默认 15，最大 15 |
| 44 | `order.field` | String | | 排序字段，见表 1.8 |
| 45 | `order.desc` | boolean | | true=降序（默认），false=升序 |

### 11. keyword_research_trends — 关键词选品-趋势数据

- **文档页**: `/api/11`
- **方法**: `POST`
- **路径**: `/v1/keyword-research/trends`
- **描述**: 查询关键词的历史趋势数据

| # | 参数 | 类型 | 必填 | 说明 |
|---|------|------|------|------|
| 1 | `marketplace` | String | ✓ | 市场编码 |
| 2 | `keyword` | String | ✓ | 关键词 |

### 12. keyword_miner — 关键词挖掘

- **文档页**: `/api/6`
- **方法**: `POST`
- **路径**: `/v1/keyword/miner`
- **描述**: 拓展关键词的衍生词以及含有该词根的长尾关键词

| # | 参数 | 类型 | 必填 | 说明 |
|---|------|------|------|------|
| 1 | `marketplace` | String | ✓ | 市场编码 |
| 2 | `historyDate` | String | | 历史日期，yyyyMM 格式，最近 30 天不传 |
| 3 | `keyword` | String | ✓ | 关键词 |
| 4 | `keywordList` | List | | 批量查询关键词 |
| 5～6 | `minSearch` / `maxSearch` | Integer | | 搜索量区间 |
| 7～8 | `minPurchases` / `maxPurchases` | Integer | | 购买量区间 |
| 9～10 | `minPurchasesRate` / `maxPurchasesRate` | Float | | 购买率区间 |
| 11～12 | `minSPR` / `maxSPR` | Integer | | SPR 区间 |
| 13～14 | `minTitleDensity` / `maxTitleDensity` | Integer | | 标题密度区间 |
| 15～16 | `minRelevancy` / `maxRelevancy` | Float | | 相关度区间（0～100） |
| 17～18 | `minSearchRank` / `maxSearchRank` | Integer | | 搜索排名区间 |
| 19～20 | `minProducts` / `maxProducts` | Integer | | 商品数区间 |
| 21～22 | `minSupplyDemandRatio` / `maxSupplyDemandRatio` | Float | | 供需比区间 |
| 23～24 | `minAdProducts` / `maxAdProducts` | Integer | | 广告竞品数区间 |
| 25～26 | `minWordCount` / `maxWordCount` | Integer | | 单词个数区间 |
| 27～28 | `minMonopolyClickRate` / `maxMonopolyClickRate` | Float | | 点击集中度区间 |
| 29～30 | `minBid` / `maxBid` | Float | | PPC 竞价区间 |
| 31～32 | `minPrice` / `maxPrice` | Float | | 均价区间 |
| 33～34 | `minRatings` / `maxRatings` | Integer | | 评分数区间 |
| 35～36 | `minRating` / `maxRating` | Float | | 评分值区间 |
| 37 | `amazonChoice` | Boolean | | 亚马逊推荐词 |
| 38 | `filterRootWord` | Integer | | 过滤词根：0=包含所有，1=只包含词根 |
| 39 | `matchType` | Integer | | 匹配类型：2=广泛匹配，3=词组匹配 |
| 40 | `includeKeywords` | List | | 包含的词 |
| 41 | `excludeKeywords` | List | | 排除的词 |
| 42 | `page` | Integer | | 页码，默认 1 |
| 43 | `size` | Integer | | 每页条数，默认 50，最大 100 |
| 44 | `order.field` | String | | 排序字段 |
| 45 | `order.desc` | boolean | | true=降序（默认），false=升序 |

### 13. traffic_extend — 拓展流量词

- **文档页**: `/api/46`
- **方法**: `POST`
- **路径**: `/v1/traffic/extend`
- **描述**: 多个 ASIN 在近 30 天内进入过搜索结果前 3 页的所有搜索流量词

| # | 参数 | 类型 | 必填 | 说明 |
|---|------|------|------|------|
| 1 | `marketplace` | String | ✓ | 市场编码 |
| 2 | `historyDate` | String | | 历史日期，yyyyMM 格式 |
| 3 | `asinList` | List | ✓ | ASIN 列表，最多 20 |
| 4 | `queryType` | Integer | | 查询方式：0=所有变体，1=畅销变体，2=当前变体（默认） |
| 5～6 | `minSearches` / `maxSearches` | Integer | | 月搜索量区间 |
| 7～8 | `minSearchRank` / `maxSearchRank` | Integer | | 搜索排名区间 |
| 9～10 | `minPurchases` / `maxPurchases` | Integer | | 购买量区间 |
| 11～12 | `minPurchaseRate` / `maxPurchaseRate` | Float | | 购买率区间 |
| 13～14 | `minProducts` / `maxProducts` | Integer | | 商品数区间 |
| 15～16 | `minSupplyDemandRatio` / `maxSupplyDemandRatio` | Float | | 供需比区间 |
| 17～18 | `minBid` / `maxBid` | Float | | PPC 竞价区间 |
| 19～20 | `minAdProducts` / `maxAdProducts` | Integer | | 广告竞品数区间 |
| 21～22 | `minAvgPrice` / `maxAvgPrice` | Float | | 均价区间 |
| 23～24 | `minWordCount` / `maxWordCount` | Integer | | 单词个数区间 |
| 25 | `includeKeywords` | List | | 包含的词 |
| 26 | `excludeKeywords` | List | | 排除的词 |
| 27～28 | `minSPR` / `maxSPR` | Integer | | SPR 区间 |
| 29～30 | `minTitleDensity` / `maxTitleDensity` | Integer | | 标题密度区间 |
| 31～32 | `minMonopolyClickRate` / `maxMonopolyClickRate` | Float | | 点击集中度区间 |
| 33～34 | `minTrafficPercentage` / `maxTrafficPercentage` | Float | | 流量占比区间 |
| 35～36 | `minConversionRate` / `maxConversionRate` | Float | | 转化率区间 |
| 37～38 | `minCompetitors` / `maxCompetitors` | Integer | | ASIN 数区间 |
| 39 | `amazonChoice` | Boolean | | 亚马逊推荐词 |
| 40 | `page` | Integer | | 页码，默认 1 |
| 41 | `size` | Integer | | 每页条数，默认 50，最大 50 |
| 42 | `order.field` | String | | 排序字段，见表 2.5 |
| 43 | `order.desc` | boolean | | true=降序（默认），false=升序 |

### 14. aba_research_weekly — ABA 数据选品-按周

- **文档页**: `/api/19`
- **方法**: `POST`
- **路径**: `/v1/aba/research/weekly`
- **描述**: 根据关键词的周参数来筛选产品

| # | 参数 | 类型 | 必填 | 说明 |
|---|------|------|------|------|
| 1 | `marketplace` | String | ✓ | 市场编码 |
| 2 | `date` | String | | 为空查最新周，格式 yyyyMMdd（周六日期） |
| 3 | `departments` | List | | 类目列表 |
| 4 | `excludeKeywords` | String | | 排除关键词 |
| 5 | `includeKeywords` | String | | 包含关键词 |
| 6 | `exactFlag` | Boolean | | 是否精确匹配 |
| 7 | `rankGrowthValue` | Integer | | 搜索增长量 |
| 8 | `rankGrowthRate` | Double | | 搜索增长率 |
| 9～10 | `minRankGrowthRate` / `maxRankGrowthRate` | Double | | 排名增长率区间 |
| 11～12 | `minSearchRank` / `maxSearchRank` | Integer | | 排名区间 |
| 13～14 | `minSearches` / `maxSearches` | Integer | | 搜索量区间 |
| 15～16 | `minMonopolyClickRate` / `maxMonopolyClickRate` | Double | | 点击集中度区间 |
| 17～18 | `minConversionRate` / `maxConversionRate` | Double | | 转化占比区间 |
| 19～20 | `minWordCount` / `maxWordCount` | Integer | | 单词数区间 |
| 21～22 | `minSPR` / `maxSPR` | Integer | | SPR 区间 |
| 23～24 | `minTitleDensity` / `maxTitleDensity` | Integer | | 标题密度区间 |
| 25～26 | `minClicks` / `maxClicks` | Integer | | 点击量区间 |
| 27～28 | `minImpressions` / `maxImpressions` | Integer | | 展示量区间 |
| 29 | `searchModel` | Integer | | 搜索模式：1=热门，2=异动，3=持续增长，4=快速飙升，5=潜力，6=长尾（默认 1） |
| 30 | `page` | Integer | | 页码，默认 1 |
| 31 | `size` | Integer | | 每页条数，默认 40，最大 40 |
| 32 | `order.field` | String | | 排序字段，见表 2.4 |
| 33 | `order.desc` | boolean | | true=降序（默认），false=升序 |

### 15. aba_research_monthly — ABA 数据选品-按月

- **文档页**: `/api/20`
- **方法**: `POST`
- **路径**: `/v1/aba/research/monthly`
- **描述**: 根据关键词的月度参数来筛选产品

| # | 参数 | 类型 | 必填 | 说明 |
|---|------|------|------|------|
| 1 | `marketplace` | String | ✓ | 市场编码 |
| 2 | `date` | String | | 为空查最近 30 天，格式 yyyyMM |
| 3 | `departments` | List | | 类目列表 |
| 4 | `excludeKeywords` | String | | 排除关键词 |
| 5 | `includeKeywords` | String | | 包含关键词 |
| 6 | `exactFlag` | Boolean | | 是否精确匹配 |
| 7～8 | `minRankGrowthRate` / `maxRankGrowthRate` | Double | | 排名增长率区间 |
| 9～10 | `minSearchRank` / `maxSearchRank` | Integer | | 排名区间 |
| 11～12 | `minSearches` / `maxSearches` | Integer | | 搜索量区间 |
| 13～14 | `minMonopolyClickRate` / `maxMonopolyClickRate` | Double | | 点击集中度区间 |
| 15～16 | `minConversionRate` / `maxConversionRate` | Double | | 转化占比区间 |
| 17～18 | `minWordCount` / `maxWordCount` | Integer | | 单词数区间 |
| 19～20 | `minSPR` / `maxSPR` | Integer | | SPR 区间 |
| 21～22 | `minTitleDensity` / `maxTitleDensity` | Integer | | 标题密度区间 |
| 23～24 | `minClicks` / `maxClicks` | Integer | | 点击量区间 |
| 25～26 | `minImpressions` / `maxImpressions` | Integer | | 展示量区间 |
| 27 | `searchModel` | Integer | | 搜索模式：1=热门，2=异动，3=持续增长，4=快速飙升，5=潜力，6=长尾 |
| 28 | `page` | Integer | | 页码，默认 1 |
| 29 | `size` | Integer | | 每页条数，默认 15，最大 15 |
| 30 | `order.field` | String | | 排序字段，见表 2.4 |
| 31 | `order.desc` | boolean | | true=降序（默认），false=升序 |

### 16. aba_research_trend — ABA 数据选品-关键词趋势

- **文档页**: `/api/60`
- **方法**: `POST`
- **路径**: `/v1/aba/research/trends`
- **描述**: 查询关键词的历史趋势数据

| # | 参数 | 类型 | 必填 | 说明 |
|---|------|------|------|------|
| 1 | `marketplace` | String | ✓ | 市场编码 |
| 2 | `keyword` | String | ✓ | 关键词 |
| 3 | `timeGranularity` | String | | 时间粒度：W=周，M=月 |

### 17. keyword_order — 出单词反查

- **文档页**: `/api/24`
- **方法**: `POST`
- **路径**: `/v1/keyword-order`
- **描述**: 反查目标 ASIN 的 Top 出单词，用于优化 Listing 或精准广告投放

| # | 参数 | 类型 | 必填 | 说明 |
|---|------|------|------|------|
| 1 | `marketplace` | String | ✓ | 市场编码 |
| 2 | `asins` | List | ✓ | ASIN 列表，最大 20 |
| 3 | `reverseType` | String | ✓ | 反查模式：W=周，M=月 |
| 4 | `date` | String | | 周格式 yyyyMMdd，月格式 yyyyMM |
| 5 | `conversionType` | List | | 转化类型：E=转化优质词，S=转化平稳词，L=转化流失词，I=无效曝光词 |
| 6 | `variation` | List | | 是否查询变体：Y=否，N=是 |
| 7 | `page` | Integer | | 页码，默认 1 |
| 8 | `size` | Integer | | 每页条数，固定 50 |
| 9 | `order.field` | String | | 排序字段，见表 2.6 |
| 10 | `order.desc` | Boolean | | false=升序 |

---

## 五、流量分析

### 18. traffic_listing — 关联流量列表

- **文档页**: `/api/16`
- **方法**: `POST`
- **路径**: `/v1/traffic/listing/page`
- **描述**: 查询产品及其变体的关联流量来源

| # | 参数 | 类型 | 必填 | 说明 |
|---|------|------|------|------|
| 1 | `marketplace` | String | ✓ | 市场编码 |
| 2 | `asinList` | List | ✓ | ASIN 列表 |
| 3 | `relations` | List | ✓ | 关联类型，见表 2.2 |
| 4 | `variations` | Boolean | | 是否查询变体，默认 false |
| 5 | `page` | Integer | | 页码，默认 1 |
| 6 | `size` | Integer | | 每页条数，默认 50 |
| 7 | `order.field` | String | | 排序字段，见表 2.2 |
| 8 | `order.desc` | Boolean | | true=降序（默认），false=升序 |

### 19. traffic_keyword_stat — 流量词统计

- **文档页**: `/api/13`
- **方法**: `GET`
- **路径**: `/v1/traffic/keyword/stat/{marketplace}/{asin}`
- **描述**: 查询 ASIN 的流量词统计数据

| # | 参数 | 类型 | 必填 | 说明 |
|---|------|------|------|------|
| 1 | `marketplace` | String | ✓ | 市场编码（路径参数） |
| 2 | `asin` | String | ✓ | ASIN（路径参数） |
| 3 | `month` | String | | 查询月份 |

### 20. traffic_listing_stat — 关联流量统计

- **文档页**: `/api/15`
- **方法**: `GET`
- **路径**: `/v1/traffic/listing/stat/{marketplace}/{asin}`
- **描述**: 查询 ASIN 的关联流量统计数据

| # | 参数 | 类型 | 必填 | 说明 |
|---|------|------|------|------|
| 1 | `marketplace` | String | ✓ | 市场编码 |
| 2 | `asinList` | List | | ASIN 列表 |

### 21. traffic_source — 查流量来源（关键词流向）

- **文档页**: `/api/17`
- **方法**: `POST`
- **路径**: `/v1/traffic/source`
- **描述**: 查关键词或 ASIN 带来曝光的 ASIN 或关键词

| # | 参数 | 类型 | 必填 | 说明 |
|---|------|------|------|------|
| 1 | `marketplace` | String | ✓ | 市场编码 |
| 2 | `q` | String | ✓ | ASIN 或关键词 |
| 3 | `month` | String | ✓ | 筛选日期，yyyyMM 格式 |
| 4 | `page` | Integer | | 页码，默认 1 |
| 5 | `size` | Integer | | 每页条数，默认 50，最大 100 |
| 6 | `order.field` | String | | 排序字段，见表 2.4 |
| 7 | `order.desc` | boolean | | true=降序（默认），false=升序 |

---

## 六、选市场

### 22. market_research — 选市场列表

- **文档页**: `/api/29`
- **方法**: `POST`
- **路径**: `/v1/market/research`
- **描述**: 查询细分类目的市场分析数据（参数最多，共 72 个）

| # | 参数 | 类型 | 必填 | 说明 |
|---|------|------|------|------|
| 1 | `marketplace` | String | ✓ | 站点编码 |
| 2 | `month` | String | | 筛选日期，默认最近 30 天 |
| 3 | `topNum` | Integer | | 头部 Listing 数量，默认 10 |
| 4 | `newProduct` | Integer | | 新品定义，默认 3 |
| 5 | `nodeIdPath` | String | | 类目节点 ID 路径 |
| 6 | `departmentKeyword` | String | | 类目关键字 |
| 7～8 | `minAvgUnits` / `maxAvgUnits` | Integer | | 月均销量区间 |
| 9～10 | `minAvgRevenue` / `maxAvgRevenue` | Float | | 月均销售额区间 |
| 11～12 | `minAvgRatings` / `maxAvgRatings` | Integer | | 平均评分数区间 |
| 13～14 | `minAvgRating` / `maxAvgRating` | Float | | 平均评分值区间 |
| 15～16 | `minAvgBsr` / `maxAvgBsr` | Integer | | 平均 BSR 排名区间 |
| 17～18 | `minAvgPrice` / `maxAvgPrice` | Float | | 平均价格区间 |
| 19～20 | `minWeight` / `maxWeight` | Float | | 重量区间 |
| 21～22 | `minVolume` / `maxVolume` | Float | | 体积区间 |
| 23～24 | `minAvgProfit` / `maxAvgProfit` | Float | | 平均毛利率区间 |
| 25～26 | `minTopAvgUnits` / `maxTopAvgUnits` | Integer | | 头部月均销量区间 |
| 27～28 | `minTopAvgRevenue` / `maxTopAvgRevenue` | Float | | 头部月均销售额区间 |
| 29～30 | `minTopAvgBsr` / `maxTopAvgBsr` | Integer | | 头部平均 BSR 区间 |
| 31～32 | `minGoodsCount` / `maxGoodsCount` | Integer | | 商品数量区间 |
| 33～34 | `minBrands` / `maxBrands` | Integer | | 品牌数量区间 |
| 35～36 | `minSellers` / `maxSellers` | Integer | | 卖家数量区间 |
| 37～38 | `minAvgSellers` / `maxAvgSellers` | Float | | 平均卖家数量区间 |
| 39～40 | `minGoodsCrn` / `maxGoodsCrn` | Float | | 商品集中度区间 |
| 41～42 | `minBrandCrn` / `maxBrandCrn` | Float | | 品牌集中度区间 |
| 43～44 | `minSellerCrn` / `maxSellerCrn` | Float | | 卖家集中度区间 |
| 45～46 | `minEbcProportion` / `maxEbcProportion` | Float | | A+ 数量占比区间 |
| 47～48 | `minFbaProportion` / `maxFbaProportion` | Float | | FBA 占比区间 |
| 49～50 | `minFbmProportion` / `maxFbmProportion` | Float | | FBM 占比区间 |
| 51～52 | `minAmazonSelfProportion` / `maxAmazonSelfProportion` | Float | | Amazon 自营占比区间 |
| 53 | `sellerLocation` | String | | 卖家所属地，逗号分隔 |
| 54～55 | `minNewProportion` / `maxNewProportion` | Float | | 新品数量占比区间 |
| 56～57 | `minNewCount` / `maxNewCount` | Integer | | 新品数量区间 |
| 58～59 | `minNewAvgRatings` / `maxNewAvgRatings` | Integer | | 新品平均评分数区间 |
| 60～61 | `minNewAvgPrice` / `maxNewAvgPrice` | Float | | 新品平均价格区间 |
| 62～63 | `minNewAvgRating` / `maxNewAvgRating` | Float | | 新品平均星级区间 |
| 64～65 | `minNewAvgUnits` / `maxNewAvgUnits` | Float | | 新品月均销量区间 |
| 66～67 | `minNewAvgRevenue` / `maxNewAvgRevenue` | Float | | 新品月均销售额区间 |
| 68 | `page` | Integer | | 页码，默认 1 |
| 69 | `size` | Integer | | 每页条数，默认 50，最大 200 |
| 70 | `order.field` | String | | 排序字段，见表 1.6 |
| 71 | `order.desc` | boolean | | true=降序（默认），false=升序 |

### 23. market_research_statistics — 选市场-统计

- **文档页**: `/api/30`
- **方法**: `POST`
- **路径**: `/v1/market/statistics`
- **描述**: 查询类目下的统计数据

| # | 参数 | 类型 | 必填 | 说明 |
|---|------|------|------|------|
| 1 | `marketplace` | String | ✓ | 站点编码 |
| 2 | `month` | String | | 筛选日期，默认最近 30 天 |
| 3 | `topN` | Integer | | 头部 Listing 数量，默认 10 |
| 4 | `newProduct` | Integer | | 新品定义 |
| 5 | `nodeIdPath` | String | ✓ | 节点 ID 路径字符串 |

### 24. market_product_concentration — 选市场-商品集中度

- **文档页**: `/api/31`
- **方法**: `POST`
- **路径**: `/v1/market/goods`
- **描述**: 查询市场商品集中度（头部 ASIN 销量占比）

| # | 参数 | 类型 | 必填 | 说明 |
|---|------|------|------|------|
| 1 | `marketplace` | String | ✓ | 站点编码 |
| 2 | `month` | String | | 筛选日期 |
| 3 | `asins` | List | | 筛选 ASIN |
| 4 | `topN` | Integer | | 头部数量，默认 10 |
| 5 | `newProduct` | Integer | | 新品定义 |
| 6 | `nodeIdPath` | String | ✓ | 节点 ID 路径字符串 |

### 25. market_brand_concentration — 选市场-品牌集中度

- **文档页**: `/api/32`
- **方法**: `POST`
- **路径**: `/v1/market/brand`
- **描述**: 查询市场品牌集中度

| # | 参数 | 类型 | 必填 | 说明 |
|---|------|------|------|------|
| 1 | `marketplace` | String | ✓ | 站点编码 |
| 2 | `month` | String | | 筛选日期 |
| 3 | `topN` | Integer | | 头部数量，默认 10 |
| 4 | `newProduct` | Integer | | 新品定义 |
| 5 | `nodeIdPath` | String | ✓ | 节点 ID 路径字符串 |

### 26. market_seller_concentration — 选市场-卖家集中度

- **文档页**: `/api/33`
- **方法**: `POST`
- **路径**: `/v1/market/seller`
- **描述**: 查询市场卖家集中度

| # | 参数 | 类型 | 必填 | 说明 |
|---|------|------|------|------|
| 1 | `marketplace` | String | ✓ | 站点编码 |
| 2 | `month` | String | | 筛选日期 |
| 3 | `topN` | Integer | | 头部数量，默认 10 |
| 4 | `newProduct` | Integer | | 新品定义 |
| 5 | `nodeIdPath` | String | ✓ | 节点 ID 路径字符串 |

### 27. market_seller_type — 选市场-卖家类型分布

- **文档页**: `/api/34`
- **方法**: `POST`
- **路径**: `/v1/market/seller/type`
- **描述**: 查询市场卖家类型分布（自营/FBA/FBM 等）

| # | 参数 | 类型 | 必填 | 说明 |
|---|------|------|------|------|
| 1 | `marketplace` | String | ✓ | 站点编码 |
| 2 | `month` | String | | 筛选日期 |
| 3 | `topN` | Integer | | 头部数量，默认 10 |
| 4 | `newProduct` | Integer | | 新品定义 |
| 5 | `nodeIdPath` | String | ✓ | 节点 ID 路径字符串 |

### 28. market_seller_location — 选市场-卖家所属地分布

- **文档页**: `/api/35`
- **方法**: `POST`
- **路径**: `/v1/market/seller/location`
- **描述**: 查询市场卖家所属地分布

| # | 参数 | 类型 | 必填 | 说明 |
|---|------|------|------|------|
| 1 | `marketplace` | String | ✓ | 站点编码 |
| 2 | `month` | String | | 筛选日期 |
| 3 | `topN` | Integer | | 头部数量，默认 10 |
| 4 | `newProduct` | Integer | | 新品定义 |
| 5 | `nodeIdPath` | String | ✓ | 节点 ID 路径字符串 |

### 29. market_product_demand_trend — 选市场-商品需求趋势

- **文档页**: `/api/36`
- **方法**: `POST`
- **路径**: `/v1/market/performance`
- **描述**: 查询市场商品需求趋势（含退货率、搜索购买比、浏览量等）

| # | 参数 | 类型 | 必填 | 说明 |
|---|------|------|------|------|
| 1 | `marketplace` | String | ✓ | 市场 ID |
| 2 | `month` | String | | 筛选日期，最早 2021 年 7 月 |
| 3 | `topN` | Integer | | 头部数量，默认 10 |
| 4 | `newProduct` | Integer | | 新品定义 |
| 5 | `nodeIdPath` | String | ✓ | 节点 ID 路径字符串 |

### 30. market_listing_time — 选市场-上架时间分布

- **文档页**: `/api/37`
- **方法**: `POST`
- **路径**: `/v1/market/shelf/time`
- **描述**: 查询市场上架时间分布

| # | 参数 | 类型 | 必填 | 说明 |
|---|------|------|------|------|
| 1 | `marketplace` | String | ✓ | 站点编码 |
| 2 | `month` | String | | 筛选日期 |
| 3 | `topN` | Integer | | 头部数量，默认 10 |
| 4 | `newProduct` | Integer | | 新品定义 |
| 5 | `nodeIdPath` | String | ✓ | 节点 ID 路径字符串 |

### 31. market_listing_trend — 选市场-上架趋势分布

- **文档页**: `/api/38`
- **方法**: `POST`
- **路径**: `/v1/market/shelf/trend`
- **描述**: 查询市场上架趋势分布

| # | 参数 | 类型 | 必填 | 说明 |
|---|------|------|------|------|
| 1 | `marketplace` | String | ✓ | 站点编码 |
| 2 | `month` | String | | 筛选日期 |
| 3 | `topN` | Integer | | 头部数量，默认 10 |
| 4 | `newProduct` | Integer | | 新品定义 |
| 5 | `nodeIdPath` | String | ✓ | 节点 ID 路径字符串 |

### 32. market_ratings_count — 选市场-评分数分布

- **文档页**: `/api/39`
- **方法**: `POST`
- **路径**: `/v1/market/reviews`
- **描述**: 查询市场评分数分布

| # | 参数 | 类型 | 必填 | 说明 |
|---|------|------|------|------|
| 1 | `marketplace` | String | ✓ | 站点编码 |
| 2 | `month` | String | | 筛选日期 |
| 3 | `topN` | Integer | | 头部数量，默认 10 |
| 4 | `newProduct` | Integer | | 新品定义 |
| 5 | `nodeIdPath` | String | ✓ | 节点 ID 路径字符串 |

### 33. market_rating_distribution — 选市场-评分值分布

- **文档页**: `/api/40`
- **方法**: `POST`
- **路径**: `/v1/market/rating`
- **描述**: 查询市场评分值分布

| # | 参数 | 类型 | 必填 | 说明 |
|---|------|------|------|------|
| 1 | `marketplace` | String | ✓ | 站点编码 |
| 2 | `month` | String | | 筛选日期 |
| 3 | `topN` | Integer | | 头部数量，默认 10 |
| 4 | `newProduct` | Integer | | 新品定义 |
| 5 | `nodeIdPath` | String | ✓ | 节点 ID 路径字符串 |

### 34. market_price_distribution — 选市场-价格分布

- **文档页**: `/api/41`
- **方法**: `POST`
- **路径**: `/v1/market/price`
- **描述**: 查询市场价格分布

| # | 参数 | 类型 | 必填 | 说明 |
|---|------|------|------|------|
| 1 | `marketplace` | String | ✓ | 站点编码 |
| 2 | `month` | String | | 筛选日期 |
| 3 | `topN` | Integer | | 头部数量，默认 10 |
| 4 | `newProduct` | Integer | | 新品定义 |
| 5 | `nodeIdPath` | String | ✓ | 节点 ID 路径字符串 |

### 35. market_ebc_distribution — 选市场-A+ 视频分布

- **文档页**: `/api/42`
- **方法**: `POST`
- **路径**: `/v1/market/ebc`
- **描述**: 查询市场 A+ 和视频分布

| # | 参数 | 类型 | 必填 | 说明 |
|---|------|------|------|------|
| 1 | `marketplace` | String | ✓ | 站点编码 |
| 2 | `month` | String | | 筛选日期 |
| 3 | `topN` | Integer | | 头部数量，默认 10 |
| 4 | `newProduct` | Integer | | 新品定义 |
| 5 | `nodeIdPath` | String | ✓ | 节点 ID 路径字符串 |

---

## 七、其他

### 36. product_node — 查产品类目

- **文档页**: `/api/9`
- **方法**: `GET`
- **路径**: `/v1/product/node`
- **描述**: 查询类目 ID、名称、所有节点名称及类目下产品数量

| # | 参数 | 类型 | 必填 | 说明 |
|---|------|------|------|------|
| 1 | `marketplace` | String | ✓ | 市场编码 |
| 2 | `nodeIdPath` | String | | 类目节点 ID 字符串 |
| 3 | `keyword` | String | | 搜索关键字（nodeId 或类目名称） |
| 4 | `month` | String | | 查询历史月份类目，yyyyMM 格式 |

### 37. google_trend — 谷歌趋势

- **文档页**: `/api/12`
- **方法**: `GET`
- **路径**: `/v1/google/trends`
- **描述**: 关键词的谷歌趋势

| # | 参数 | 类型 | 必填 | 说明 |
|---|------|------|------|------|
| 1 | `marketplace` | String | ✓ | 市场编码 |
| 2 | `keyword` | String | | 关键字 |
| 3 | `googleProp` | String | | 类别：web=网页搜索，shoppingCart=谷歌购物 |
| 4 | `monthly` | boolean | | 按月份，默认 false |

### 38. keepa_info — 商品趋势详情（Keepa）

- **文档页**: `/api/22`
- **方法**: `GET`
- **路径**: `/v1/keepa/{marketplace}/{asin}`
- **描述**: Listing 上架以来各项数据的历史趋势（价格、BSR 排名、评论数、评分数等）

| # | 参数 | 类型 | 必填 | 说明 |
|---|------|------|------|------|
| 1 | `marketplace` | String | ✓ | 市场编码（路径参数） |
| 2 | `asin` | String | ✓ | ASIN（路径参数） |
| 3 | `startTimestamp` | Long | | 趋势数据起始时间戳 |
| 4 | `endTimestamp` | Long | | 趋势数据结束时间戳 |
| 5 | `dailyLatest` | Boolean | | 仅获取每日最新数据 |

### 39. review — 查评论

- **文档页**: `/api/25`
- **方法**: `POST`
- **路径**: `/v1/review`
- **描述**: 获取 Amazon ASIN 评论数据

| # | 参数 | 类型 | 必填 | 说明 |
|---|------|------|------|------|
| 1 | `marketplace` | String | ✓ | 市场编码 |
| 2 | `asin` | String | ✓ | ASIN |
| 3 | `starList` | List | | 评论星级：1～5 |
| 4 | `typeList` | List | | 评论类型：1=图片，2=视频，3=VP，4=vine |
| 5 | `page` | Integer | | 页码，默认 1 |
| 6 | `size` | Integer | | 每页条数，最大 10，默认 5 |

### 40. 图片文字识别（OCR）

- **文档页**: `/api/44`
- **方法**: `POST`
- **路径**: `/v1/ocr`
- **描述**: 识别图片中的文字，可指定语言

| # | 参数 | 类型 | 必填 | 说明 |
|---|------|------|------|------|
| 1 | `type` | Integer | ✓ | 图片类型：0=远程图片，1=base64，2=图片文件 |
| 2 | `fn` | String | ✓ | 语言：CHINESE=中文，LATIN=拉丁文 |
| 3 | `url` | String | | 远程图片 URL（type=0 时） |
| 4 | `base64` | String | | Base64 字符串（type=1 时） |
| 5 | `image` | File | | 上传文件（type=2 时） |

### 41. trademark_stats — 全球商标库-统计

- **文档页**: `/api/47`
- **方法**: `POST`
- **路径**: `/v1/global/brand/stats`
- **描述**: 查询商标统计数据

| # | 参数 | 类型 | 必填 | 说明 |
|---|------|------|------|------|
| 1 | `office` | List | ✓ | 数据范围 |
| 2 | `text` | String | ✓ | 查询文本 |
| 3 | `imageBase64` | String | | base64 字符串 |
| 4 | `imageFile` | File | | 上传的文件 |

### 42. trademark_list — 全球商标库-列表

- **文档页**: `/api/48`
- **方法**: `POST`
- **路径**: `/v1/global/brand/list`
- **描述**: 查询商标列表数据

| # | 参数 | 类型 | 必填 | 说明 |
|---|------|------|------|------|
| 1 | `office` | List | | 数据范围 |
| 2 | `text` | String | ✓ | 查询文本 |
| 3 | `imageBase64` | String | | base64 字符串 |
| 4 | `imageFile` | File | | 上传的文件 |
| 5 | `brandName` | List | | 品牌名 |
| 6 | `status` | List | | 状态 |
| 7 | `applicant` | List | | 申请人 |
| 8 | `niceClass` | List | | 尼斯分类 |
| 9 | `applicationYear` | List | | 申请年份 |
| 10 | `expiryYear` | List | | 过期年份 |
| 11 | `order.field` | String | | 排序字段，默认相关度 |
| 12 | `order.desc` | Boolean | | true=降序（默认） |
| 13 | `page` | Integer | | 页码 |
| 14 | `size` | Integer | | 每页条数，最大 100 |

### 43. trademark_detail — 全球商标库-详情

- **文档页**: `/api/49`
- **方法**: `GET`
- **路径**: `/v1/global/brand/detail`
- **描述**: 查询商标详细信息

| # | 参数 | 类型 | 必填 | 说明 |
|---|------|------|------|------|
| 1 | `office` | String | ✓ | 数据范围 |
| 2 | `brandId` | String | ✓ | 商标 ID |

### 44. trademark_country_list — 全球商标库-数据范围

- **文档页**: `/api/50`
- **方法**: `GET`
- **路径**: `/v1/global/brand/range`
- **描述**: 查询支持商标查询的国家/地区列表

无请求参数。

---

## 选市场子工具速查

以下 13 个子工具共享相同的参数结构（`marketplace` ✓、`month`、`topN`、`newProduct`、`nodeIdPath` ✓），仅路径和 MCP Code 不同：

| # | MCP Code | 名称 | 路径 |
|---|----------|------|------|
| 23 | `market_research_statistics` | 统计 | `/v1/market/statistics` |
| 24 | `market_product_concentration` | 商品集中度 | `/v1/market/goods` |
| 25 | `market_brand_concentration` | 品牌集中度 | `/v1/market/brand` |
| 26 | `market_seller_concentration` | 卖家集中度 | `/v1/market/seller` |
| 27 | `market_seller_type` | 卖家类型分布 | `/v1/market/seller/type` |
| 28 | `market_seller_location` | 卖家所属地分布 | `/v1/market/seller/location` |
| 29 | `market_product_demand_trend` | 商品需求趋势 | `/v1/market/performance` |
| 30 | `market_listing_time` | 上架时间分布 | `/v1/market/shelf/time` |
| 31 | `market_listing_trend` | 上架趋势分布 | `/v1/market/shelf/trend` |
| 32 | `market_ratings_count` | 评分数分布 | `/v1/market/reviews` |
| 33 | `market_rating_distribution` | 评分值分布 | `/v1/market/rating` |
| 34 | `market_price_distribution` | 价格分布 | `/v1/market/price` |
| 35 | `market_ebc_distribution` | A+视频分布 | `/v1/market/ebc` |

---

## 按选品流程分类

```
运营输入方向
  │
  ├─ 市场快验
  │   ├─ market_research          → 选市场列表
  │   ├─ market_research_statistics → 选市场-统计
  │   └─ market_* (13个子项)      → 集中度/分布/趋势
  │
  ├─ 产品发现
  │   ├─ product_research         → 选产品
  │   ├─ competitor_lookup        → 查竞品
  │   ├─ keyword_research         → 关键词选品
  │   └─ aba_research_weekly/monthly → ABA 选品
  │
  ├─ 产品深挖
  │   ├─ asin_detail              → ASIN 详情
  │   ├─ asin_sales_trend         → ASIN 销量趋势
  │   ├─ asin_prediction          → ASIN 销量预测
  │   ├─ keepa_info               → Keepa 历史趋势
  │   └─ asin_coupon_trend        → 优惠趋势
  │
  ├─ 关键词/流量分析
  │   ├─ traffic_keyword          → 关键词反查
  │   ├─ traffic_extend           → 拓展流量词
  │   ├─ keyword_miner            → 关键词挖掘
  │   ├─ keyword_order            → 出单词反查
  │   ├─ traffic_source           → 流量来源
  │   ├─ traffic_listing          → 关联流量列表
  │   ├─ traffic_keyword_stat     → 流量词统计
  │   └─ traffic_listing_stat     → 关联流量统计
  │
  ├─ VOC / 评论
  │   └─ review                   → 查评论
  │
  ├─ 辅助
  │   ├─ product_node             → 查产品类目
  │   ├─ google_trend             → 谷歌趋势
  │   ├─ bsr_prediction           → BSR 销量预测
  │   ├─ trademark_* (4个)        → 商标查询
  │   └─ OCR                      → 图片文字识别
  │
  └─ 趋势/预测
      ├─ keyword_research_trends  → 关键词趋势
      ├─ aba_research_trend       → ABA 关键词趋势
      └─ asin_detail_with_coupon_trend → 详情+优惠趋势
```
