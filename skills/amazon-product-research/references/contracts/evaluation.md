# Stage 9 Contract — 六维评价

**产出方**: 6 个 Evaluation Agent（并行）
**消费方**: `validate_evaluation.py`, `build_evaluation_summary.py`, Stage 10
**输出路径**: `evaluations/{dimension}_evaluation.json`

## 所有 6 份评价的通用必填字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `schema_version` | string | `"p6-evaluation-v1"` |
| `packet_id` | string | `"{dimension}_evaluation"` |
| `dimension` | string | 维度名 |
| `score` | int | 0-100 |
| `rating` | string | ∈ {strong, watch, weak, blocked} |
| `confidence` | string | ∈ {high, medium, low} |
| `key_reasons` | list[string] | ≥ 1 条理由 |
| `risks` | list[dict] | 风险列表 |
| `required_followups` | list[string] | 后续验证 |
| `evidence_refs` | list[string] | ≥ 1 条证据引用 |
| `route_breakdown` | list[dict] | 每条路线的独立评分 |
| `execution_provenance` | dict | `{executed_by_agent: true, agent_role, execution_mode: "agent"}` |

## route_breakdown[] 每条必填

| 字段 | 类型 | 说明 |
|------|------|------|
| `route_id` | string | **必须带 route_id**（kebab-case），禁止靠索引位置隐式匹配 |
| `score` | int | 该路线在此维度的评分 0-100 |
| `rating` | string | ∈ {strong, watch, weak, blocked} |
| `reason` | string | 评分理由 |

## 六维清单

| 维度 key | Agent | 核心问题 |
|-----------|-------|----------|
| `market_demand` | Market Demand Evaluation Agent | 需求是否真实、稳定、足够大 |
| `competition` | Competition Evaluation Agent | 是否头部垄断、评论门槛是否过高 |
| `price_profit` | Price Band Opportunity Evaluation Agent | 价格带是否健康，有无切入窗口 |
| `voc_opportunity` | VOC Opportunity Evaluation Agent | 痛点能否转成产品差异化 |
| `risk` | Risk Evaluation Agent | 合规、季节性、退货、体积、同质化 |
| `data_quality` | Data Quality Evaluation Agent | 样本、混池、跨源冲突 |

## Tier 规则

| tier | 条件 | 评价维度 |
|------|------|----------|
| `full` | 参考 ASIN ≥ 2 且搜索量 ≥ 5K | 完整 6 维 |
| `light` | 不满足 full 条件 | 仅 market_demand + data_quality，其余 4 维由脚本生成 placeholder |

## 禁止事项

- `route_breakdown` 为 list 时，每条必须带 `route_id`，禁止靠位置匹配
- score 不能在 > 90 时 rating=weak，也不能 < 20 时 rating=strong
- `evidence_refs` 不能为空
