# 卖家精灵导出/MCP 工具映射

V1 首选卖家精灵手动导出的 Excel/CSV 或整理表。后续自动化只保留 MCP Code，不再规划 HTTP API 接入。

## 接入原则

| 项 | 口径 |
|---|---|
| V1 主来源 | 卖家精灵手动导出 Excel/CSV 或整理表 |
| 后续自动化 | 卖家精灵 MCP |
| 导出记录 | 每份文件记录站点、功能页面、筛选条件、导出时间和原始文件名 |
| 兜底方式 | 未接 MCP 时，继续使用 mock 或卖家精灵导出数据 |

## 手动导出与 MCP 对照

| 目标 | V1 手动导出入口 | 后续 MCP Code | 输出 |
|---|---|---|---|
| 发现候选市场/类目/关键词 | 选市场、产品类目、关键词选品 | `market_research`、`product_node`、`keyword_research` | 候选市场、类目、关键词 |
| Top100/商品池 | 选产品/产品调研、查竞品 | `product_research`、`competitor_lookup` | 商品池、竞品池 |
| 市场统计 | 选市场统计、市场规模、销量销售额统计 | `market_research_statistics` | 市场规模、基础指标 |
| 集中度 | 商品集中度、品牌集中度、卖家集中度 | `market_product_concentration`、`market_brand_concentration`、`market_seller_concentration` | 商品/品牌/卖家集中度 |
| 卖家画像 | 卖家类型、卖家所属地 | `market_seller_country_distribution`、`market_seller_type_concentration` | 中国卖家占比、FBA/FBM、Amazon 自营等 |
| 价格/评分/评论分布 | 价格分布、评分值分布、评分数分布 | `market_price_distribution`、`market_rating_distribution`、`market_ratings_count_distribution` | 价格带、评论门槛 |
| 新品和生命周期 | 上架时间分布、上架趋势、商品需求趋势 | `market_listing_date_distribution`、`market_listing_trend_distribution`、`market_product_demand_trend` | 新品占比、生命周期 |
| ASIN 详情与趋势 | ASIN 详情、销量趋势、BSR/销量预测、Keepa、优惠趋势 | `asin_detail`、`asin_prediction`、`bsr_prediction`、`keepa_info`、`asin_coupon_trend`、`asin_sales_trend` | 上架、BSR、销量、价格、优惠 |
| 关键词与流量 | 关键词选品、关键词挖掘、关键词反查、拓展流量词、ABA | `keyword_research`、`keyword_miner`、`traffic_keyword`、`traffic_source`、`traffic_listing`、`traffic_extend`、`aba_research_weekly`、`aba_research_monthly` | 搜索量、趋势、流量词、广告竞争参考 |
| 评论/VOC | 自有评论插件 Excel 优先；卖家精灵评论导出兜底 | `review` | 评论样本和 VOC 证据 |
| 商标 | 全球商标库列表/详情 | `trademark_country_list`、`trademark_list`、`trademark_detail` | 商标风险初筛 |

## 实现注意

1. Top2000 或页面数据过多时，要通过类目、价格带、BSR、排名或销量分段导出。
2. 手动导出和 MCP 字段可能不完全一致，落库时先转成项目自己的标准字段。
3. MCP 未接入前，不阻塞本地 mock 和手动导入链路。
4. 卖家精灵商标能力只能解决商标初筛，专利仍需 USPTO、Google Patents、WIPO 等入口人工复核。
