# Sorftime MCP 工具调用策略

更新日期：2026-06-11

## 定位

Sorftime MCP 在选品系统中的角色是**深度验证层**，不是数据主源。卖家精灵手动导入做广域候选池铺底，Sorftime 在候选池产出后做趋势/竞品/关键词的深度交叉验证。

## 三源分工一览

| 数据源 | 职责 | 调用时机 |
|---|---|---|
| 卖家精灵手动导入 | 大盘扫描、Top100 完整明细、ABA、退货率 | 候选池生成前 |
| Sorftime MCP | 类目趋势、关键词趋势、竞品流量词、相似品延展 | 候选池产出后、候选确认前 |
| 自有评论插件 | 大批量 VOC、痛点/卖点/差评证据链 | 候选进入「继续看/试做」后 |

## 工具清单与调用时机

### 无方向探索模式

| 工具 | 调用时机 | 目的 | 积分消耗 |
|---|---|---|---|
| `search_categories_broadly` | 运营给出大概品类或完全无方向时 | 找可能值得看的细分类目入口 | 1 |
| `category_trend` | 筛出 3-5 个候选方向后 | 验证每个方向的月销量趋势、集中度变化、新品占比趋势 | 1/次 |
| `category_report` | 候选方向初步确认后 | 补充类目 Top100 基础数据（作为卖家精灵的交叉验证） | 1 |

### 指定方向深挖模式

| 工具 | 调用时机 | 目的 | 积分消耗 |
|---|---|---|---|
| `keyword_detail` | 确定 2-3 个主关键词后 | 获取周/月搜索量、CPC、旺季、首页竞品统计 | 1/词 |
| `keyword_trend` | `keyword_detail` 之后 | 看 24 个月搜索量走势，判断是否增长/季节性/衰退 | 1/词 |
| `keyword_extends` | 主关键词确定后 | 找延伸词，发现混池词和长尾机会词 | 1 |
| `keyword_search_results` | 候选边界校准后 | 看搜索首页竞品结构，与卖家精灵 Top100 交叉比对 | 1 |

### 候选方向确认后（继续看/试做）

| 工具 | 调用时机 | 目的 | 积分消耗 |
|---|---|---|---|
| `product_traffic_terms` | 确定重点竞品 ASIN 后 | 看竞品靠哪些词拿流量，找词位空隙 | 1/ASIN |
| `competitor_product_keywords` | 同上 | 提取竞品关键词词包，找可借鉴的流量词 | 1/ASIN |
| `similar_product` | 候选主线确认后 | 向周边延展，发现相似机会品 | 1 |
| `potential_product` | 同上 | 找潜力新品，补充候选池 | 1 |
| `similar_product_feature` | 方向确认、准备深挖报告时 | 分析同类热销品共有特征，指导卖点提炼和差异化定位 | **5（高消耗，谨慎调用）** |
| `product_detail` | 需要验证特定 ASIN 数据时 | 补充竞品详情字段 | 1/ASIN |
| `product_trend` | 重点竞品确定后 | 看竞品 24 个月销量趋势 | 1/ASIN |

## 调用原则

1. **顺序调用，不并发滥用**：每个工具只在上一步结论支撑的情况下才调用，不要一次性全部跑。
2. **`similar_product_feature` 限制调用**：消耗 5 积分，只在候选方向已确认、准备正式深挖时调用一次。
3. **关键词工具按词数控制**：主关键词 2-3 个，备选词 1 个，不对大词包逐一跑趋势。
4. **竞品工具按 ASIN 控制**：优先对 Top3-5 标杆竞品调用流量词，不对整个 Top100 逐一跑。
5. **评论不依赖 Sorftime**：`product_reviews` 只有近 1 年最多 100 条，VOC 证据链仍由自有插件承担。

## 数据写入 candidate_pool

Sorftime 验证结论写入 candidate_pool 的 `sorftime_verification` 字段组：

```json
{
  "sorftime_verification": {
    "category_trend": {
      "trend_direction": "增长/衰退/均衡/季节性",
      "monthly_sales_24m": [...],
      "top3_concentration_trend": "集中/分散/恶化",
      "new_product_share_trend": "上升/下降/均衡",
      "verified_at": "2026-06-11"
    },
    "keyword_verification": [
      {
        "keyword": "window squeegee",
        "weekly_search_volume": 45000,
        "monthly_search_volume": 180000,
        "cpc": 1.2,
        "seasonality": "均衡/旺季Q4",
        "competitor_count": 12000,
        "trend_direction": "增长"
      }
    ],
    "traffic_terms": {
      "asin": "B0XXXXX",
      "top_traffic_words": ["window squeegee", "extendable window squeegee"],
      "gap_opportunities": ["2 in 1 window cleaning tool"]
    }
  }
}
```

## 成本参考

| 工具类型 | 典型单次消耗 | V1 每轮调研预估消耗 |
|---|---|---|
| 类目工具 | 1 积分 | 3-5 积分（1-2 个类目趋势 + 1 次类目搜索） |
| 关键词工具 | 1 积分/词 | 6-10 积分（3 个关键词 × 详情+趋势） |
| 产品工具（常规） | 1 积分/ASIN | 5-10 积分（Top5 竞品流量词） |
| `similar_product_feature` | 5 积分 | 5 积分（只调用一次） |
| **合计（一次完整验证）** | — | **约 20-30 积分** |
