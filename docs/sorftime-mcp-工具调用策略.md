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
| `search_categories_broadly` | 完全无方向时找细分类目入口 | 1 |
| `category_trend` × 2-3 方向 | 验证每个候选方向的月销趋势、集中度、新品占比 | 1/次 |
| `keyword_list` × 主方向 | 获取核心词搜索量量级，判断主词体量 | 1 |

典型消耗：3-6 积分。

### 模式二——前置验证工具（卖家精灵导出前先跑）

> 目标：5-7 积分内给出快验结论，如果方向有问题，在运营导出前就告知，避免无效操作。

| 工具 | 目的 | 积分 |
|---|---|---|
| `category_search_from_product_name` | 从产品名定位 Amazon 类目节点 | 1 |
| `category_trend` × 1 | 判断类目趋势（增长/衰退/均衡/季节性） | 1 |
| `keyword_detail` × 2-3 主词 | 搜索量 + CPC + 首页竞品数量 | 1/词 |

典型消耗：4-6 积分。

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
| `similar_product` | 候选主线确认后 | 向周边延展，发现相似机会品 | 1 |
| `potential_product` | 同上 | 找潜力新品，补充候选池 | 1 |
| `similar_product_feature` | 方向确认、准备深挖报告时 | 同类热销品共有特征，指导卖点提炼 | **5（谨慎调用）** |
| `product_detail` | 需要验证特定 ASIN 数据时 | 补充竞品详情字段 | 1/ASIN |
| `product_trend` | 重点竞品确定后 | 竞品 24 个月销量趋势 | 1/ASIN |

> ⚠️ 早期已调用过的 `category_trend` / `keyword_detail`，深挖阶段可直接复用，不重复调用。

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
    }
  }
}
```

---

## 成本参考

| 阶段 | 典型工具组合 | 消耗 |
|---|---|---|
| 模式一并行初探 | `category_trend` × 2-3 + `keyword_list` | 3-6 积分 |
| 模式二前置快验 | `category_search_from_product_name` + `category_trend` + `keyword_detail` × 2-3 | 4-6 积分 |
| 深度验证（共用） | 关键词工具 + 竞品流量词 + `similar_product_feature` | 15-25 积分 |
| **合计（一次完整调研）** | — | **约 20-35 积分** |
