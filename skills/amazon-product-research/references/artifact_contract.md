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
├── supply_chain/
├── analysis/
│   ├── analysis_report.html
│   ├── analysis_report.xlsx
│   ├── analysis_evidence_packet.json
│   └── delivery_qa_result.json
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

Stage 7 综合预审和最终报告都必须校验。最终正式报告以 `validate_research_outputs.py` 通过为准；Stage 7 以 `analysis/delivery_qa_result.json` 通过或明确待补为准。

Stage 7 最低要求：

- `analysis_report.html`、`analysis_report.xlsx`、`analysis_evidence_packet.json` 存在
- `analysis_evidence_packet.json` 包含 Lead Operator 的 professional analysis memo
- HTML 包含资深亚马逊运营专家综合分析，不只是多源摘要拼接
- HTML/Excel 是用户可读报告，不能展示 Agent、MCP、tool、internal execution、spawn、packet 等内部执行术语
- Excel 能回表到 Sorftime、卖家精灵、VOC、1688 和利润待补字段，但 Sheet/标题使用用户可理解名称
- 利润/合规未回填时只能 Wait/待补

最终正式报告最低要求：

- final_report 五件套存在
- `data.xlsx` 可读取
- 12 章报告结构完整
- Top100 有效明细充足
- 评论 VOC 有证据链，或明确待补
- 利润/合规未回填时只能 Wait/待补

## Stage 7 综合预审产物口径

`analysis/` 是 1688 导入后、利润/FBA/合规回填前的用户 review 主入口：

- `analysis_report.html`：通俗可读的产品机会综合预审报告。
- `analysis_report.xlsx`：可筛选的路线、关键词、竞品、VOC、1688 候选和利润待补字段。
- `analysis_evidence_packet.json`：Lead Operator 主 Agent 的结构化综合判断和 professional analysis memo。
- `delivery_qa_result.json`：QA Agent 对证据边界、硬缺口和报告完整性的检查。

职责边界：

- 数据源专家 Agent 只产 evidence、缺口、置信度和待补动作，不输出最终报告和最终 Go/Wait/No-Go。
- Lead Operator 以资深亚马逊运营专家身份产 professional analysis memo，并解释需求、市场、VOC、供应链、利润/合规缺口和结论原因。
- Report Writer 只把 memo + 全部 evidence 写成用户版 HTML/Excel，不新增数字、不改事实、不改商业判断。

通用模板只能写章节、字段和数据映射，不能写死当前品类、ASIN、供应商、关键词或类目。

缺证据表达：

- 系统没有采集、解析或交叉验证到：写“系统侧待补”。
- 需要运营打开 ASIN、关键词结果页、1688 链接、图片、详情页或评论上下文判断：写“人工 review 待补”。
- 只有用户确实未提供必要输入或确认时，才写“用户输入缺失”。

## MCP 产物口径

`mcp/sorftime_verification.json` 的 1688 采购价信号必须保留：

- `source_tool`: `ali1688_similar_product`
- `source_site`: `1688中国站`
- `source_url`: `https://www.1688.com/` 或 `*.1688.com`
- `quote_currency`: `RMB` 或 `CNY`
- 无效样本数量和原因：非 1688 域名、Alibaba 国际站 USD 报价、币种不明
