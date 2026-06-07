# 卖家精灵导出/API/MCP 工具映射

V1 首选卖家精灵手动导出的 Excel/CSV 或整理表。HTTP API 和 MCP Code 只作为后续自动化增强，不作为首版必须购买的能力。

## 接入原则

| 项 | 口径 |
|---|---|
| V1 主来源 | 卖家精灵手动导出 Excel/CSV 或整理表 |
| 导出记录 | 每份文件记录站点、功能页面、筛选条件、导出时间和原始文件名 |
| 后续 API 网关 | `https://api.sellersprite.com` |
| 后续 API 认证 | Header 使用 `secret-key` |
| 后续请求追踪 | Header 使用 `x-request-id` |
| 后续内容类型 | `Content-Type: application/json;charset=utf-8` |
| 密钥保存 | 只放本地环境变量，不写入仓库、样例或报告 |
| 兜底方式 | 未拿到 API Key/MCP 时，继续使用 mock 或卖家精灵导出数据 |

## V1 手动导出入口

| 目标 | 卖家精灵手动导出入口 | 输出 |
|---|---|---|
| 发现候选市场/类目/关键词 | 选市场、产品类目、关键词选品 | 候选市场、类目、关键词 |
| Top100/商品池 | 选产品/产品调研、查竞品 | 商品池、竞品池 |
| 市场统计 | 选市场统计、市场规模、销量销售额统计 | 市场规模、基础指标 |
| 集中度 | 商品集中度、品牌集中度、卖家集中度 | 商品/品牌/卖家集中度 |
| 价格/评分/评论分布 | 价格分布、评分值分布、评分数分布 | 价格带、评论门槛 |
| 新品和生命周期 | 上架时间分布、上架趋势、商品需求趋势 | 新品占比、生命周期 |
| ASIN 详情与趋势 | ASIN 详情、销量趋势、BSR/销量预测、Keepa、优惠趋势 | 上架、BSR、销量、价格、优惠 |
| 关键词与流量 | 关键词选品、关键词挖掘、关键词反查、拓展流量词、ABA | 搜索量、趋势、流量词、广告竞争参考 |
| 评论/VOC | 自有评论插件 Excel 优先；卖家精灵评论导出兜底 | 评论样本和 VOC 证据 |
| 商标 | 全球商标库列表/详情 | 商标初筛 |

以下 HTTP API 和 MCP Code 仅用于后续自动化替换手动导出层。

## 后续候选发现 API/MCP

| 目标 | 首选 HTTP API | 可选 MCP Code | 输出 |
|---|---|---|---|
| 发现候选市场/类目/关键词 | `POST /v1/market/research`、`GET /v1/product/node`、`POST /v1/keyword-research` | `market_research`、`product_node`、`keyword_research` | 候选市场、类目、关键词 |
| Top100/商品池 | `POST /v1/product/research`、`POST /v1/product/competitor-lookup` | `product_research`、`competitor_lookup` | 商品池、竞品池 |
| 市场统计 | `POST /v1/market/statistics` | `market_research_statistics` | 市场规模、销量、销售额等基础指标 |

## 后续市场结构 API/MCP

| 目标 | 首选 HTTP API | 可选 MCP Code | 输出 |
|---|---|---|---|
| 商品集中度 | `POST /v1/market/goods` | `market_product_concentration` | CR5/CR10、头部商品集中度 |
| 品牌集中度 | `POST /v1/market/brand` | `market_brand_concentration` | 品牌集中度 |
| 卖家集中度 | `POST /v1/market/seller` | `market_seller_concentration` | 卖家集中度 |
| 卖家所属地 | `POST /v1/market/seller/location` | `market_seller_country_distribution` | 中国卖家占比等 |
| 卖家类型 | `POST /v1/market/seller/type` | `market_seller_type_concentration` | FBA/FBM、Amazon 自营等 |
| 价格分布 | `POST /v1/market/price` | `market_price_distribution` | 价格带和价格真空带 |
| 评分分布 | `POST /v1/market/rating`、`POST /v1/market/ratings` | `market_rating_distribution`、`market_ratings_count_distribution` | 评分值、评论数门槛 |
| 新品和生命周期 | `POST /v1/market/shelf/time`、`POST /v1/market/shelf/trend`、`POST /v1/market/performance` | `market_listing_date_distribution`、`market_listing_trend_distribution`、`market_product_demand_trend` | 新品占比、上架趋势、需求趋势 |

## 后续竞品与趋势 API/MCP

| 目标 | 首选 HTTP API | 可选 MCP Code | 输出 |
|---|---|---|---|
| ASIN 详情 | `GET /v1/asin/{marketplace}/{asin}` | `asin_detail` | 上架、类目、价格、评论等基础信息 |
| ASIN 销量预测 | `GET /v1/sales/prediction/asin` | `asin_prediction` | ASIN 月销量预测 |
| BSR 销量预测 | `GET /v1/sales/prediction/bsr` | `bsr_prediction` | BSR 对应销量预测 |
| Keepa 趋势 | `GET /v1/keepa/{marketplace}/{asin}` | `keepa_info` | 价格、BSR、评论等趋势 |
| 优惠趋势 | `GET /v1/asin/{marketplace}/{asin}/coupon-trend` | `asin_coupon_trend` | Coupon/折扣趋势 |
| 销量趋势 | `GET /v1/asin/{marketplace}/{asin}/sales-trend` | `asin_sales_trend` | 销量趋势 |

## 后续关键词与流量 API/MCP

| 目标 | 首选 HTTP API | 可选 MCP Code | 输出 |
|---|---|---|---|
| 关键词选品 | `POST /v1/keyword-research` | `keyword_research` | 关键词机会 |
| 关键词趋势 | `POST /v1/keyword-research/trends` | `keyword_research_trends` | 搜索趋势 |
| 关键词挖掘 | `POST /v1/keyword/miner` | `keyword_miner` | 品类词、属性词、长尾词 |
| 关键词反查 | `POST /v1/traffic/keyword` | `traffic_keyword` | ASIN 流量词 |
| 拓展流量词 | `POST /v1/traffic/extend` | `traffic_extend` | 关联流量词 |
| 流量来源 | `POST /v1/traffic/source` | `traffic_source` | 关键词流向 |
| 关联流量列表 | `POST /v1/traffic/listing/page` | `traffic_listing` | 关联 ASIN/流量列表 |
| ABA 数据 | `POST /v1/aba/research/weekly`、`POST /v1/aba/research/monthly`、`POST /v1/aba/research/trends` | `aba_research_weekly`、`aba_research_monthly`、`aba_research_trend` | ABA 关键词和趋势 |
| Google 趋势 | `GET /v1/google/trends` | `google_trend` | 站外趋势参考 |

## 后续评论、商标与风险 API/MCP

| 目标 | 首选 HTTP API | 可选 MCP Code | 输出 |
|---|---|---|---|
| 评论样本 | `POST /v1/review` | `review` | 评论兜底样本；深挖仍优先自有评论插件 Excel |
| 商标数据范围 | `GET /v1/global/brand/range` | `trademark_country_list` | 可查国家/地区 |
| 商标列表 | `POST /v1/global/brand/list` | `trademark_list` | 商标初筛列表 |
| 商标详情 | `GET /v1/global/brand/detail` | `trademark_detail` | 商标详情 |

## 实现注意

1. TOP2000 或页面数据过多时，要通过类目、价格带、BSR、排名或销量分段导出。
2. 手动导出、API 和 MCP 字段可能不完全一致，落库时先转成项目自己的标准字段。
3. API Key/MCP 未确认前，不阻塞本地 mock 和手动导入数据链路。
4. 卖家精灵商标能力只能解决商标初筛，专利仍需 USPTO、Google Patents、WIPO 等入口人工复核。
