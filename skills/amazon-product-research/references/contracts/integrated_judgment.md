# Stage 10a-b Contract — integrated_operator_judgment.json

**产出方**: Route Strategy Agent + Growth & Risk Agent（10a 并行） → Lead Operator Agent（10b 合成）
**消费方**: `validate_judgment.py`, Stage 11-12
**输出路径**: `analysis/integrated_operator_judgment.json`

## 必填顶层字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `schema_version` | string | `"p7-integrated-judgment-v1"` |
| `packet_id` | string | `"integrated_operator_judgment"` |
| `run_id` | string | run 目录名 |

## Stage 10a 深度分析字段（9 个，Route Strategy 5 + Growth & Risk 4）

### Route Strategy Agent 负责（5 个）

| 字段 | 类型 | 说明 |
|------|------|------|
| `route_recommendation` | dict | `{primary_recommendation, routes[{route_id, route_name, verdict, reasoning}]}` |
| `route_tradeoff` | list[dict] | `[{route_id, route_name, gain, lose, best_for, worst_for}]` |
| `competitor_benchmark` | list[dict] | `[{asin, route_id, brand, price, monthly_sales, rating, review_count}]`，必须回查市场结构证据 |
| `competitor_weakness_map` | list[dict] | `[{asin, fatal_weakness, my_counter, counter_difficulty: low/medium/high}]`，必须回查 VOC 证据差评原文 |
| `price_band_analysis` | list[dict] | `[{band, price_range, opportunity_level, asin_samples[], recommendation}]` |

### Growth & Risk Agent 负责（4 个）

| 字段 | 类型 | 说明 |
|------|------|------|
| `voc_to_spec` | list[dict] | `[{priority: P0/P1/P2, dimension, issue_description, spec_requirement, sample_tests}]` |
| `keyword_strategy` | dict | `{primary_attack[], testable[], negative[], strategy_note}` |
| `risk_mitigation` | list[dict] | `[{risk_id, category, severity, mitigation, verification_method}]` |
| `validation_roadmap` | list[dict] | `[{phase, timeline, actions[], pass_criteria, fail_next_step}]` |

## Stage 10b 决策摘要字段（Lead Operator Agent 负责）

| 字段 | 类型 | 说明 |
|------|------|------|
| `final_verdict` | string | ∈ {go, watch, no_go, blocked} |
| `verdict_reason` | string | 综合判断理由（2-4 段） |
| `confidence` | string | ∈ {high, medium, low} |
| `biggest_opportunity` | dict | `{dimension, score, reason}` |
| `biggest_risk` | dict | `{dimension, score, description}` |
| `required_next_actions` | list[string] | 下一步验证动作 |

## 硬约束

- 10a 任何字段仍含 `__ai_judgment__` 占位 → verdict 强制 `blocked`
- Lead Operator 不重做深度分析，只做交叉验证 + 决策拍板 + 合并写入
- final_verdict 必须与 evaluation_summary 的治理规则自洽
- 引用具体数字时（"63条腰挂松动"等）必须与 VOC evidence 保持一致
