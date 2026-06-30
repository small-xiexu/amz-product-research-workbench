# Stage 4 Contract — candidate_pool.json

**产出方**: Main Agent
**消费方**: `build_mcp_candidate_pool.py`, Stage 5, Stage 8
**输出路径**: `candidate_pool.json`

## 必填顶层字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `schema_version` | string | `"p2-candidate-pool-v1"` |
| `packet_id` | string | `"candidate_pool"` |
| `run_id` | string | run 目录名 |
| `generated_at` | string | ISO 时间戳 |
| `metadata` | dict | `{marketplace, site, task_name}` 至少这三项 |
| `source_brief` | dict | `{data_sources[], scope_note}` 来源说明 |
| `candidates` | list[dict] | 候选方向列表，≥ 1 |
| `evidence_refs` | list[string] | 至少 1 条，指向 quick packet/snapshot/gate |
| `pool_status` | string | ∈ {ready_for_route_matrix, needs_user_review, excluded} |

## candidates[] 每条必填

| 字段 | 类型 | 说明 |
|------|------|------|
| `candidate_id` | string | 可中文，描写产品形态（如 "基础款-材质升级"） |
| `route_id` | string | **kebab-case 英文**（如 `basic-material-upgrade`） |
| `candidate_name` | string | 中文名 |
| `top_products` | list[dict] | ≥ 4 ASIN，每个含 `asin`, `price`, `brand`, `monthly_sales`, `rating` |
| `reference_asins` | list[string] | ASIN 列表 |
| `demand_evidence` | dict | 需求证据 |
| `competition_structure` | dict | 竞争结构证据 |
| `status` | string | ∈ {active, watch, excluded} |
| `source_brief` | string | 一句话来源说明 |

## 禁止事项

- `candidate_id` / `route_id` 禁止用抽象序号（C01, R01, 路线A）
- 禁止内部术语占位符（`sellersprite|sorftime|mcp|quick_gate|workflow_state`）
- ASIN 必须放在 `top_products[]` 或 `reference_asins[]` 中，脚本遍历这两个容器
