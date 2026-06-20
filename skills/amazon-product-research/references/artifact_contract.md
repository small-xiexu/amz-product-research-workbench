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
├── analysis/
│   ├── analysis_report.html
│   ├── analysis_report.xlsx
│   ├── analysis_evidence_packet.json
│   └── delivery_qa_result.json
├── research_package.json
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
| `run_id` | 本轮运行 ID | `YYYYMMDD_<topic>` |
| `product_direction` | 报告主标题 | `<目标方向>` |
| `keyword` | 查询词 | `<目标关键词>` |
| `task_name` | 本轮任务名 | `<站点><目标方向>深挖` |
| `data_sources` | 数据源 | `Sorftime MCP` / `卖家精灵` / `评论插件` |

报告标题只能使用 `product_direction` 或清洗后的候选方向，不得包含：

- `MCP`
- `验证`
- `回归`
- `测试`
- `UI`
- `预览`

这些词只能进入 `data_sources`、`workflow_summary` 或证据说明。

## 必须校验

Stage 7 市场机会报告和最终报告都必须校验。最终正式报告以 `validate_research_outputs.py` 通过为准；Stage 7 以 `analysis/delivery_qa_result.json` 通过或明确待补为准。

Stage 7 最低要求：

- `analysis_report.html`、`analysis_report.xlsx`、`analysis_evidence_packet.json` 存在
- `analysis_evidence_packet.json` 包含 Lead Operator 的 professional analysis memo
- HTML 包含资深亚马逊运营专家综合分析，不只是多源摘要拼接
- HTML/Excel 是用户可读报告，不能展示 Agent、MCP、tool、internal execution、spawn、packet 等内部执行术语
- Excel 能回表到 Sorftime、卖家精灵、VOC、市场机会评分和证据审计，但 Sheet/标题使用用户可理解名称

最终正式报告最低要求：

- final_report 五件套存在
- `data.xlsx` 可读取
- 报告结构完整
- Top100 有效明细充足
- 评论 VOC 有证据链，或明确待补
- 市场机会评分卡 8 维完整

## Stage 7 市场机会产物口径

`analysis/` 是多数据源市场机会报告的用户 review 主入口：

- `analysis_report.html`：通俗可读的市场机会报告。
- `analysis_report.xlsx`：可筛选的路线、关键词、竞品、VOC、评分卡和证据审计。
- `analysis_evidence_packet.json`：Lead Operator 主 Agent 的结构化综合判断和 professional analysis memo。
- `delivery_qa_result.json`：QA Agent 对证据边界、硬缺口和报告完整性的检查。

职责边界：

- 数据源专家 Agent 只产 evidence、缺口、置信度和待补动作，不输出最终报告。
- Lead Operator 以资深亚马逊运营专家身份产 professional analysis memo，并解释需求、市场、VOC、风险缺口和结论原因。
- Report Writer 只把 memo + 全部 evidence 写成用户版 HTML/Excel，不新增数字、不改事实、不改商业判断。

通用模板只能写章节、字段和数据映射，不能写死当前品类、ASIN、关键词或类目。

缺证据表达：

- 系统没有采集、解析或交叉验证到：写“系统侧待补”。
- 需要运营打开 ASIN、关键词结果页、详情页或评论上下文判断：写“人工 review 待补”。
- 只有用户确实未提供必要输入或确认时，才写“用户输入缺失”。

## MCP 产物口径

`mcp/sorftime_verification.json` 和 `search_demand_evidence` 必须保留：

- 类目候选、nodeId、类目角色和来源
- 参考 ASIN、路线和相似理由
- 运营式关键词池
- 关键词月搜、CPC、竞争量和混池标签
- 类目淡旺季和关键词热度的边界说明
- 热销特征、冲突证据和 `data_gaps`
