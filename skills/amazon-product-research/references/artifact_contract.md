# Codex 版产物契约

每轮选品必须有一个独立 run 目录。

## 目录结构

```text
runs/<yyyymmdd>_<中文品类方向>/
├── progress.json                      # 断点恢复（AI 自动维护）
├── inputs/
│   ├── seller_sprite/                 # 卖家精灵原始导出（只读，不修改）
│   └── reviews/                       # 评论原始导出（只读，不修改）
├── mcp/
│   └── sorftime_verification.json     # Sorftime 采集快照
├── candidate_pool.json                # 候选品池
├── route_matrix_confirm.json          # 路线确认配置
├── market_structure/
│   └── market_structure_evidence_packet.json
├── search_demand/
│   └── search_demand_evidence_packet.json
├── review_voc/
│   ├── review_voc_package.json
│   ├── voc_evidence_packet.json
│   └── voc_evidence.xlsx
└── analysis/
    ├── <中文品名>_分析报告.html       ← 最终交付：AI 手写决策报告
    ├── <中文品名>_数据回表.xlsx       ← 最终交付：脚本生成数据回表
    ├── report_data.json                ← 唯一数据中枢
    └── delivery_qa_result.json         ← QA 校验结果
```

**关键约束：**
- `run_id` = `yyyymmdd_中文品类方向`，如 `YYYYMMDD_示例品类`
- `<中文品名>` 与目录名去掉日期前缀一致（`_extract_product_name()` 直接从目录名推导）
- `inputs/` 下是运营手动导出的原始文件，只读不修改
- 所有 AI 笔记、中间 `.md` 文件不放入 run 目录

## 命名规则

| 字段 | 用途 | 例子 |
|---|---|---|
| `run_id` | 本轮运行 ID | `YYYYMMDD_中文品类方向`，如 `YYYYMMDD_示例品类` |
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

- `<中文品名>_分析报告.html`、`<中文品名>_数据回表.xlsx` 存在（最终交付物）
- `report_data.json`、`delivery_qa_result.json` 存在（脚本生成）
- `<中文品名>_分析报告.html` 由 AI 以资深运营专家视角手写，8 个板块完整，用词克制，决策导向
- HTML 包含资深亚马逊运营专家综合分析，不只是多源摘要拼接
- HTML/Excel 是用户可读报告，不能展示 Agent、MCP、tool、internal execution、spawn、packet 等内部执行术语
- Excel 能回表到 Sorftime、卖家精灵、VOC 和证据审计，但 Sheet/标题使用用户可理解名称

最终正式报告最低要求（legacy，当前主链路以 `analysis/` 为最终交付）：

- final_report 五件套存在
- `data.xlsx` 可读取
- 报告结构完整
- Top100 有效明细充足
- 评论 VOC 有证据链，或明确待补
- 市场机会评分卡 8 维完整

## Stage 7 市场机会产物口径

`analysis/` 是多数据源市场机会报告的用户 review 主入口：

- `<中文品名>_分析报告.html`：**最终交付**。AI 以资深亚马逊运营专家视角手写的决策建议书，8 个板块，给人看。
- `<中文品名>_数据回表.xlsx`：**最终交付**。脚本自动生成的数据回表，10 个 Sheet，给数字溯源。
- `report_data.json`：**唯一数据中枢**。HTML 和 XLSX 均从此文件生成，所有数据声明通过 `source_path` 可追溯到证据包。
- `delivery_qa_result.json`：**中间产物**。QA Agent 对证据边界、硬缺口和报告完整性的检查。

职责边界：

- 数据源专家 Agent 只产 evidence、缺口、置信度和待补动作，不输出最终报告。
- AI 主 Agent 以资深亚马逊运营专家身份，读全部证据包后直接手写 `<中文品名>_分析报告.html`。
- 脚本只负责生成 `report_data.json`（seed/重写）、`<中文品名>_数据回表.xlsx` 和 QA 校验，不生成 HTML。
- HTML 由 AI 单独手写，与脚本产物互不覆盖。

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
