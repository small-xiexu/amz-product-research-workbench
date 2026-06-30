# Stage 13 Contract — 交付 QA 双层门禁

**产出方**: Script QA (`run_delivery_qa.py`) + Delivery QA Agent
**消费方**: 最终交付判定
**输出路径**: `analysis/qa_notes.md`

## Script QA 检查项（`run_delivery_qa.py`）

| 检查项 | 说明 | 阻断级别 |
|--------|------|----------|
| HTML 存在性 | `analysis/*.html` 文件存在 | ERROR |
| XLSX 存在性 | `analysis/*.xlsx` 文件存在 | ERROR |
| report_data.json 完整 | 竞品/路线/关键词/痛点节非空 | ERROR |
| 内部术语泄漏 | HTML 不含 Agent/MCP/tool/packet/pipeline/source_path/snapshot/schema_version/execution_provenance/卖家精灵/Sorftime/data source conflict | ERROR |
| 占位符残留 | `__ai_judgment__` 不得出现在最终产物中 | ERROR |
| 快照完整性 | 深挖快照 `tool_calls` + `tool_results` 完整 | WARN |
| 数字交叉一致性 | report_data vs HTML vs XLSX 关键数字一致 | WARN |

## Delivery QA Agent 检查项

| 检查项 | 说明 |
|--------|------|
| 快照溯源 | 每个关键数字可追溯到 MCP tool_call |
| 路线完整性 | 所有 Stage 5 确认路线在报告中有体现 |
| 竞品覆盖 | 每条路线 ≥ 2 个代表 ASIN |
| 痛点溯源 | 每个 pain_point 的 evidence_refs 含 review_id + quote |
| 治理规则合规 | final_verdict 与 evaluation_summary 自洽 |
| 数据来源标注 | data_unavailable 标注合理，无虚假数据 |

## QA 判定规则

| 结果 | 条件 |
|------|------|
| PASS | 所有 ERROR 通过，WARN ≤ 2 |
| PASS_WITH_WARN | 所有 ERROR 通过，WARN > 2 |
| FAIL | 任一 ERROR 未通过 |
| BLOCKED | 快照缺失 + 关键数字无法溯源 |

## Agent 行为约束

- Delivery QA Agent **不改判断、不改数据**，只检查
- 发现问题写入 `qa_notes.md`，标注严重级别和修复建议
- QA FAIL → 打回对应 Stage 修复，不直接修改
- `qa_notes.md` 是 QA 唯一输出，不生成额外 JSON

## 禁止事项

- 不得在 QA 过程中修改 report_data.json、HTML、XLSX
- 不得以"不影响交付"为由降级 ERROR 为 WARN
- 不得跳过快照溯源检查
