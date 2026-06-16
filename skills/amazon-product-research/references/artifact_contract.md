# Codex 版产物契约

每轮选品必须有一个独立 run 目录。

## 目录结构

```text
runs/<run_id>/
├── inputs/
│   ├── seller_sprite/
│   └── reviews/
├── mcp/
├── workflow_state.json
├── import_manifest.json
├── candidate_pool.json
├── review_voc/
├── research_package.json
├── profit_review_template.xlsx
├── ip_compliance_review_template.xlsx
├── final_report/
│   ├── report.md
│   ├── report.html
│   ├── dashboard.html
│   ├── summary.md
│   └── data.xlsx
├── workflow_summary.json
└── workflow_summary.md
```

## 命名规则

| 字段 | 用途 | 例子 |
|---|---|---|
| `run_id` | 本轮运行 ID | `20260615_pet_leash` |
| `product_direction` | 报告主标题 | `宠物牵引绳` |
| `keyword` | 查询词 | `hands free dog leash` |
| `task_name` | 本轮任务名 | `美国站宠物牵引绳深挖` |
| `data_sources` | 数据源 | `Sorftime MCP` / `卖家精灵` / `评论插件` |

报告标题只能使用 `product_direction` 或清洗后的候选方向，不得包含：

- `MCP`
- `1688`
- `验证`
- `回归`
- `测试`
- `UI`
- `预览`

这些词只能进入 `data_sources`、`workflow_summary` 或证据说明。

## 必须校验

`validate_research_outputs.py` 通过前，不算交付完成。

最低要求：

- final_report 五件套存在
- `data.xlsx` 可读取
- 12 章报告结构完整
- Top100 有效明细充足
- 评论 VOC 有证据链，或明确待补
- 利润/合规未回填时只能 Wait/待补

## MCP 产物口径

`mcp/sorftime_verification.json` 的 1688 采购价信号必须保留：

- `source_tool`: `ali1688_similar_product`
- `source_site`: `1688中国站`
- `source_url`: `https://www.1688.com/` 或 `*.1688.com`
- `quote_currency`: `RMB` 或 `CNY`
- 无效样本数量和原因：非 1688 域名、Alibaba 国际站 USD 报价、币种不明
