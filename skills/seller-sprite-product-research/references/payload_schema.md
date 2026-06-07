# 统一数据包结构

## 目标

把一次调研的所有数据、计算和判断放进一个结构里，方便渲染报告和复盘。

## 顶层结构

```json
{
  "metadata": {},
  "constraints": {},
  "operator_inputs": {},
  "product_flags": [],
  "raw_sources": {},
  "normalized_tables": {},
  "market_analysis": {},
  "keyword_analysis": {},
  "competitor_pool": {},
  "profit_reference": {},
  "return_risk": {},
  "ip_screening": {},
  "compliance_screening": {},
  "review_sources": {},
  "voc_analysis": {},
  "opportunity_hypotheses": [],
  "status_card": {},
  "report_summary": {},
  "dashboard_views": {},
  "workspace_views": {},
  "excel_sheets": {}
}
```

## 字段说明

| 字段 | 含义 |
|---|---|
| `metadata` | 品类、站点、时间、数据源 |
| `constraints` | 禁区、排除规则、目标边界 |
| `operator_inputs` | 售价、采购价、汇率、FBA、仓储、广告、退货等手填项 |
| `product_flags` | 带电、电池、无线、儿童、食品接触等属性 |
| `raw_sources` | 卖家精灵导出文件索引、API/MCP 原始返回索引 |
| `normalized_tables` | 清洗后的标准表 |
| `market_analysis` | 市场规模、价格带、集中度、新品占比、趋势 |
| `keyword_analysis` | 关键词层级、趋势、CPC 参考 |
| `competitor_pool` | Top10 标杆组、近半年放量新品组、结构补充组 |
| `profit_reference` | 利润参考输入、结果、毛利率 |
| `return_risk` | 退货率、来源、风险提示 |
| `ip_screening` | 外观/实用/发明、商标、版权初筛 |
| `compliance_screening` | 可能材料、触发属性、待复核项 |
| `review_sources` | 评论插件 Excel/HTML 信息 |
| `voc_analysis` | 评论痛点、亮点、改品机会 |
| `opportunity_hypotheses` | 候选机会假设、证据、反证 |
| `status_card` | 继续看/试做/观察/先放弃 |
| `report_summary` | 主报告摘要 |
| `dashboard_views` | HTML 看板数据 |
| `workspace_views` | 工作台卡片数据 |
| `excel_sheets` | Excel Sheet 列表和路径 |

## 规则

1. 每个结论都必须能回到来源或计算逻辑。
2. 强判断不允许缺来源。
3. 手填字段必须在结构中显式标记。
