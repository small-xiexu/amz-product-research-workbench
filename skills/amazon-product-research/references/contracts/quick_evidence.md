# Stage 2 Contract — Quick Evidence Packet + Snapshot

**产出方**: SellerSprite Quick Agent / Sorftime Quick Agent
**消费方**: `fill_quick_packet_contract.py`, `build_quick_market_gate.py`, Stage 3-4
**输出路径**: `quick_check/{source}_quick_evidence_packet.json`, `mcp_snapshots/{source}_quick_snapshot.json`

## Evidence Packet 必填顶层字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `schema_version` | string | `"p1-quick-evidence-v1"` |
| `packet_id` | string | `"sellersprite_quick_evidence"` 或 `"sorftime_quick_evidence"` |
| `primary_source` | string | `"sellersprite"` 或 `"sorftime"` |
| `support_level` | string | ∈ {strong, moderate, weak, negative} |
| `mixed_pool_level` | string | 混池程度 |
| `demand_signal_level` | string | 需求信号强度 |
| `price_band_health` | string | 价格带健康度 |
| `category_boundary_clarity` | string | 类目边界清晰度 |
| `confidence` | string | ∈ {high, medium, low} |
| `evidence_items` | list[dict] | 至少 1 条证据项 |
| `candidate_seeds` | list[dict] | 候选子方向，每条含 `reference_asins[]` |
| `execution_provenance` | dict | `{executed_by_agent: true, agent_role, execution_mode: "agent"}` |
| `evidence_refs` | list[string] | 至少 1 条 |

## evidence_items[] 每条

| 字段 | 类型 | 说明 |
|------|------|------|
| `item_type` | string | 证据类型 |
| `facts` | dict | 必须为 dict 类型，含 `reference_asins[]`（≥6 个/方向，≥3 品牌，≥2 价格段） |
| `route_refs` | list[string] | 本 item 覆盖的子方向 |

## candidate_seeds[] 每条

| 字段 | 类型 | 说明 |
|------|------|------|
| `seed_id` | string | 子方向标识 |
| `seed_name` | string | 子方向中文名 |
| `reference_asins` | list[string] | ≥ 6 个 ASIN，≥ 3 品牌，≥ 2 价格段 |
| `category_candidates` | list[string] | 候选类目 Node ID |
| `demand_signal` | string | 需求信号描述 |

## Quick Snapshot 必填

| 字段 | 类型 | 说明 |
|------|------|------|
| `tool_calls` | list[dict] | 每条含 `call_id`, `tool_name`, `params`, `status` ∈ {success, empty, error}, `started_at`, `finished_at` |
| `tool_results` | list[dict] | 每条含 `result_id`, `call_id`, `tool_name`, `status`, `raw_result` |

## 禁止事项

- 不写最终放行判断（那是 Quick Gate 的事）
- 快照不能用简化 `tool_summaries` 代替完整 `tool_calls` + `tool_results`
- `candidate_seeds[].reference_asins[]` 每方向必须 ≥ 6 个，≥ 3 品牌，≥ 2 价格段
- JSON 中禁止中文引号
