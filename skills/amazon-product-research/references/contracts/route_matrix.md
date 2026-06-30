# Stage 5 Contract — route_matrix_confirm.json

**产出方**: Main Agent
**消费方**: `build_route_matrix_confirm.py`, Stage 6-12
**输出路径**: `route_matrix_confirm.json`

## 必填顶层字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `schema_version` | string | `"p3-route-matrix-confirm-v1"` |
| `packet_id` | string | `"route_matrix_confirm"` |
| `source_candidate_pool` | dict | `{path, candidate_count}` 引用 candidate_pool.json |
| `route_options` | list[dict] | 全量路线（含排除的） |
| `selected_routes` | list[dict] | 确认深挖的路线，≥ 1 |
| `rejected_routes` | list[dict] | 暂不深挖的路线 |
| `decision` | string | ∈ {confirm, revise_candidate_pool, stop} |
| `decision_reason` | string | 决策理由 |
| `required_next_actions` | list[string] | 下一步动作 |
| `evidence_refs` | list[string] | 至少 1 条 |
| `voc_readiness` | dict | `{ready, notes}` |
| `data_completeness_ref` | string | 指向 data_completeness_check.json |
| `route_matrix` | list | **必须是数组，不能是字符串** |

## selected_routes[] / rejected_routes[] 每条必填

| 字段 | 类型 | 说明 |
|------|------|------|
| `route_id` | string | **kebab-case 英文**，全链路统一 key |
| `route_name` | string | 中文路线名 |
| `tier` | string | ∈ {full, light} |
| `reference_asins` | list[string] | ≥ 2（full tier），≥ 1（light tier） |
| `category_candidates` | list[string] | 候选类目 Node ID |

## 禁止事项

- `route_id` 禁止中文、抽象代码（C01, R01）、`p2-NN-xxx` 简写
- `route_matrix` 必须是 array 类型，不能是空字符串
- JSON 中禁止中文引号（`""`），只用英文引号 `""`
