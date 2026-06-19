# 运营式选品调研流程通用升级

更新日期：2026-06-19

本升级把选品流程从“关键词驱动”改为“相似竞品 ASIN -> 大小类目 -> 反查关键词 -> 价格带/集中度/新品机会”。系统必须自动产出运营会整理的竞品、类目和分层词表，不等待运营提供整理好的词表。Sorftime 和卖家精灵采集默认以判断质量优先，不以节省调用次数或导出数量为目标。

## 通用硬规则

| 规则 | 要求 |
|---|---|
| 禁止硬编码 | 通用流程、Agent、模板、QA 不得写死当前品类、ASIN、关键词、供应商或类目 |
| 数据宁多勿少 | Sorftime 能跑的类目、关键词、ASIN、趋势、特征、1688 粗信号尽量跑全；卖家精灵可导出的市场、Top100、ABA、反查、竞品明细尽量导全 |
| 先 ASIN 后关键词 | 先找卖点/形态相近竞品，再用竞品反查词；关键词扩展只做补充验证 |
| 先类目角色后结论 | 关键词映射出的类目只能是候选类目；最终类目判断必须结合参考 ASIN 的大类、小类、BSR/nodeId 和小类机会 |
| 价格带优先 | 不用单一均价判断机会，必须看价格段销量、销售额、商品数、集中度、评论门槛和新品表现 |
| 季节性分层 | 关键词只能表示搜索热度月份；大类/小类淡旺季必须来自类目或市场趋势 |
| 证据可回表 | 每个结论能追溯到数据源、字段、ASIN、关键词、类目或 Evidence Packet |

## 当前问题清单

| 问题 | 表现 | 通用修正 |
|---|---|---|
| 搜索词不准 | 大词、系统扩展词、竞品反查词、验证词混在一起 | 建立系统自动分层词表，保留来源和用途 |
| 类目不准 | 关键词自动映射类目被当成主类目 | 先输出候选类目池，再用参考 ASIN 反推大小类目 |
| 大小类口径混淆 | 大类容量、小类机会、关键词需求混用 | 报告分为大类观察、小类机会、关键词验证 |
| 竞品选择不运营化 | 没先按卖点相近竞品选 Top5/Top10 | 每条产品路线先建立参考 ASIN 池 |
| 均价参考性弱 | 只给均价，不知道哪个价格段机会更好 | 输出价格带机会表 |
| 淡旺季误用 | 用关键词旺季代表产品淡旺季 | 类目淡旺季和关键词热度分开 |
| 报告表达误导 | 用户看不出哪些是主词、扩展词、混池词 | 词表、类目、竞品、价格带分区展示 |

## 新流程

1. **方向输入**
   - 输入可以是模糊需求、种子词、产品图片、竞品 ASIN、供应链优势或运营假设。
   - 系统只把种子词当入口，不把种子词直接当主市场。

2. **初始候选竞品**
   - 用种子词、类目搜索、相似产品、初始搜索结果找候选 ASIN。
   - 按产品形态、卖点、价格段、套装结构、目标用户、排除项初筛。

3. **参考 ASIN 池**
   - 每条产品路线选 Top5/Top10 参考 ASIN。
   - 路线可包括基础款、升级款、套装款、场景款、材质/功能升级、旁支对照。
   - 每个 ASIN 必须记录选择理由和角色。

4. **大小类目反推**
   - 从参考 ASIN 获取大类、小类、BSR 类目、nodeId、类目路径。
   - 同一 ASIN 可出现多个类目路径，保留全部并标明主路径/旁支路径。
   - 汇总候选类目池，标角色：大类、小类、混池类目、对照类目、排除类目。

5. **小类目机会分析**
   - 对每个候选小类目抓 Top100/Top50、类目趋势、价格带、集中度、新品表现。
   - 判断目标价格段是否有销量，头部集中度是否过高，新品是否能跑出来。
   - 输出“建议主推小类 / 备选小类 / 不建议小类”。

6. **竞品反查关键词**
   - 对参考 ASIN 批量反查关键词。
   - 合并卖家精灵反查、ABA、Sorftime `product_traffic_terms`、`competitor_product_keywords`、`keyword_extends`。
   - 去重后按来源和 ASIN 覆盖数保留证据。

7. **自动整理运营词表**
   - 系统从反查词和扩展词中自动分层。
   - 输出“主要流量词、转化优质词、流量词、精准长尾词、混池/排除词”。
   - 每个词标明推荐动作：主查、补查、观察、排除、待验证。

8. **VOC 与供应链验证**
   - VOC 只在路线和 ASIN 批次确认后抓取。
   - 1688 只判断结构化供应链证据和人工 review 队列，不把搜得到供应商写成最终可做。

9. **综合判断**
   - Lead Operator 只基于类目、参考 ASIN、价格带、词表、VOC、供应链、利润/合规证据输出判断。
   - 利润/FBA/合规未回填前不得给强 Go。

## 数据对象

### 参考 ASIN 池

| 字段 | 说明 |
|---|---|
| `route_id` | 产品路线 ID |
| `route_name` | 通用路线名，不写当前品类硬编码 |
| `asin` | 参考 ASIN |
| `role` | 主推代表 / 高销量对照 / 新品样本 / 高客单对照 / 痛点参考 / 排除参考 |
| `selection_reason` | 为什么选入 |
| `similarity_basis` | 卖点、形态、结构、价格、用户场景、套装组成 |
| `price` / `monthly_units` / `rating_count` | 关键竞争字段 |
| `category_paths` | 大类、小类、BSR/nodeId |
| `data_sources` | 卖家精灵、Sorftime、Amazon 页面、插件等 |
| `data_gaps` | 类目、价格、销量、评论、变体、父子 ASIN 缺口 |

### 候选类目池

| 字段 | 说明 |
|---|---|
| `category_name` | 类目名 |
| `node_id` | nodeId / BSR 节点 |
| `role` | broad_market / target_subcategory / mixed_pool / benchmark / excluded |
| `source` | 关键词映射、ASIN 反推、卖家精灵市场、Sorftime 类目工具 |
| `matched_asins` | 该类目下命中的参考 ASIN |
| `top100_units` | Top100 月销量 |
| `price_band_opportunity` | 价格带机会 |
| `brand_concentration` | 品牌集中度 |
| `product_concentration` | 商品集中度 |
| `new_release_signal` | 新品机会 |
| `seasonality` | 类目淡旺季 |
| `decision` | 主推 / 备选 / 观察 / 排除 |
| `decision_reason` | 决策理由 |

### 运营式关键词池

| 字段 | 说明 |
|---|---|
| `keyword` | 关键词 |
| `keyword_role` | main_traffic / conversion_quality / traffic / precise_long_tail / mixed_or_excluded |
| `source_type` | reverse_asin / ABA / Sorftime traffic terms / Sorftime extends / keyword detail / search result |
| `source_refs` | ASIN、文件、工具参数、行号或 Evidence ID |
| `matched_asin_count` | 命中参考 ASIN 数 |
| `monthly_search_volume` | 月搜索量 |
| `cpc` | CPC |
| `competition_count` | 竞品量 |
| `click_or_conversion_signal` | 点击/转化集中度、自然位、广告位等 |
| `mix_pool_tags` | car、shower、liquid、cloth、screen、floor、brand 等混池标签 |
| `recommended_action` | 主查 / 补查 / 观察 / 排除 / 待验证 |
| `reason` | 分层原因 |

### 价格带机会

| 字段 | 说明 |
|---|---|
| `category_id` | 类目 ID |
| `price_band` | 价格段 |
| `product_count` | 商品数 |
| `unit_share` | 销量占比 |
| `revenue_share` | 销售额占比 |
| `top_brand_share` | 该价格段品牌集中度 |
| `top_product_share` | 该价格段商品集中度 |
| `median_rating_count` | 评论门槛 |
| `new_product_count` | 新品数 |
| `new_product_unit_share` | 新品销量占比 |
| `entry_opportunity` | high / medium / low |
| `basis` | 判断依据 |

## Sorftime 采集策略

| 阶段 | 工具 | 默认策略 |
|---|---|---|
| 候选类目池 | `category_search_from_product_name`、`search_categories_broadly` | 对种子方向、路线词、竞品标题抽象词多轮查询 |
| 小类 Top100 | `category_report` | 候选小类都跑；不因积分省略 |
| 类目淡旺季 | `category_trend`、`category_report_from_history` | 主推和备选小类至少跑销量趋势；必要时补旺季/淡季历史 Top100 |
| 关键词量级 | `keyword_detail` | 对系统整理词表中的主查/补查词跑 |
| 关键词趋势 | `keyword_trend` | 用于搜索热度，不替代类目淡旺季 |
| 扩词 | `keyword_extends` | 作为补充词池和混池识别来源 |
| 首页竞品 | `keyword_search_results` | 验证主查词是否命中目标形态 |
| ASIN 流量词 | `product_traffic_terms` | 参考 ASIN 池优先全跑 |
| 竞品关键词 | `competitor_product_keywords` | 参考 ASIN 池优先全跑 |
| 相似特征 | `similar_product_feature` | 主推路线、备选路线都跑 |
| 1688 粗信号 | `ali1688_similar_product` | 仅作为粗供给信号；采购价和可供形态以供应链 Evidence Packet 为准 |

## 卖家精灵导出策略

| data_role | 首选入口 | 输入 | 用途 |
|---|---|---|---|
| `broad_market` | 大数据选品 / 选市场 | 候选大类、上层类目短词 | 容量、价格带、集中度、新品、趋势 |
| `subcategory_market` | 大数据选品 / 选市场 | 候选小类、ASIN 反推小类 | 小类价格带、集中度、新品机会 |
| `reference_asin_search` | 大数据选品 / 查竞品 | 相似卖点关键词、候选小类、对照词 | 参考 ASIN 池、形态识别、混池判断 |
| `product_candidate_pool` | 大数据选品 / 选产品 | 产品形态词、路线词、候选小类 | 候选商品、新品和低评论样本 |
| `reverse_asin_keywords` | 浏览器插件 / 关键词反查 | 参考 ASIN Top5/Top10 | 自动整理运营词表 |
| `aba_keywords` | 大数据选品 / ABA数据选品 | 主查词、补查词、路线词 | 点击/转化集中度和 Top ASIN 交叉 |
| `keyword_pool_expand` | 大数据选品 / 关键词选品 | 主查词、补查词、路线词 | 补充词池，不替代市场判断 |
| `mixed_pool_benchmark` | 大数据选品 / 查竞品 或 选市场 | 混池类目、混池词、对照 ASIN | 排除边界和对照样本 |

导出指令必须标明每份文件的菜单组、真实入口和 `data_role`，不能只写“卖家精灵入口”或“市场分析/关键词数据”。

## Agent 改造

| Agent | 新职责 |
|---|---|
| Search Demand Agent | 从参考 ASIN 反查和 Sorftime 结果整理运营式关键词池；不得直接用扩展词定义市场 |
| Market Structure Agent | 生成候选类目池、小类机会、价格带机会、集中度、新品机会；标明类目角色 |
| VOC Evidence Agent | 按路线 ASIN 批次抓评论，检查 VOC 是否支持当前路线 |
| Supply Chain Agent | 按路线和 VOC 规格验证 1688 结构化供给；视觉/样品仍标待人工 |
| Lead Operator Agent | 综合类目、ASIN、词表、价格带、VOC、供应链证据，不新增原始数字 |
| Report Writer | 按运营决策顺序展示，不把关键词表当市场结论 |
| Delivery QA Agent | 检查是否完成 ASIN 池、类目反推、词表分层、价格带机会和淡旺季分层 |

## 报告结构

1. 结论摘要：继续看 / 谨慎继续 / 暂缓，说明证据边界。
2. 参考 ASIN 池：每条路线的 Top5/Top10、角色和选择理由。
3. 大小类目选择：候选类目角色、ASIN 命中、主推/备选/排除。
4. 小类目机会对比：销量、价格带、集中度、新品机会、淡旺季。
5. 价格带机会：销量占比、销售额占比、集中度、评论门槛。
6. 运营式关键词池：主要流量词、转化优质词、流量词、精准长尾词、混池/排除词。
7. 关键词验证：月搜、CPC、自然位、混池标签、推荐动作。
8. VOC：痛点、好评驱动、痛点到规格/测试/供应商问询。
9. 1688：候选款结构化预筛、人工 review 队列、供应链缺口。
10. 利润/合规待补：进入强 Go 前需要回填的字段。
11. 下一步动作：补数据、人工 review、样品、利润、合规。

## QA 规则

| 检查项 | 失败条件 |
|---|---|
| 参考 ASIN 池 | 没有按路线列 Top5/Top10 或没有选择理由 |
| 类目反推 | 只用关键词映射类目，没有 ASIN 类目交叉 |
| 类目角色 | 没有区分大类、小类、混池、对照、排除 |
| 关键词分层 | 只列 keyword_detail，未生成运营式关键词池 |
| 扩展词来源 | 系统扩展词被写成主查词或人工词 |
| 价格带机会 | 只写均价，没有价格段销量/销售额/集中度 |
| 新品机会 | 没有小类新品或低评论样本判断 |
| 淡旺季 | 用关键词旺季替代类目淡旺季 |
| 混池 | 没有标注 car/shower/liquid/cloth/brand 等混池标签 |
| 证据边界 | 视觉、样品、利润、合规未闭环却给强 Go |

## 非目标

- 不把运营变成必填词表提供者。
- 不为单一品类写专用规则。
- 不用 Sorftime 扩词替代竞品反查。
- 不把类目自动映射当最终类目。
- 不在利润/FBA/合规未回填前输出强 Go。
