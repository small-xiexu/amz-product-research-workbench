# Stage 6 Contract — evidence packet + deep snapshot

**产出方**: Market Structure Agent / Search Demand Agent
**消费方**: `validate_evidence_packet.py`, `build_conflict_review.py`, Stage 8+
**输出路径**: `market_structure/market_structure_evidence_packet.json` 或 `search_demand/search_demand_evidence_packet.json`

## Evidence Packet 必填顶层字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `schema_version` | string | `"p4-deep-contract-v1"` |
| `packet_id` | string | `"market_structure_evidence"` 或 `"search_demand_evidence"` |
| `run_id` | string | run 目录名 |
| `primary_source` | string | `"sellersprite"` 或 `"sorftime"` |
| `evidence_items` | list[dict] | 至少 1 条，每条含 `facts` |
| `route_refs` | list[string] | 覆盖所有 selected_routes 的 route_id |
| `selected_routes` | list[string] | 同上 |
| `data_gaps` | list[dict] | 数据缺口列表 |
| `confidence` | string | ∈ {high, medium, low} |

## evidence_items[] 每条

| 字段 | 类型 | 说明 |
|------|------|------|
| `item_type` | string | Market Structure: market_capacity / price_band / seller_concentration / competitor_structure / asin_operating_data / review_threshold / category_boundary |
| `facts` | dict | 必须为 dict 类型（不能是裸 string 或空 dict） |
| `route_refs` | list[string] | 本 item 覆盖的路线 |

## Deep Snapshot 必填（用 Write 工具显式写入）

| 字段 | 类型 | 说明 |
|------|------|------|
| `schema_version` | string | `"p4-deep-contract-v1"` |
| `snapshot_id` | string | `"<run_id>-sellersprite-deep"` 或 `"<run_id>-sorftime-deep"` |
| `tool_calls` | list[dict] | 每条含 `call_id`, `tool_name`, `params`, `status` ∈ {success,empty,error}, `started_at`, `finished_at` |
| `tool_results` | list[dict] | 每条含 `result_id`, `call_id`, `tool_name`, `status`, `raw_result` 或 `normalized_preview` |

**快照必须用 Write 工具写入 `mcp_snapshots/` 目录。** 子 Agent 模式下 MCP tool_calls 无法被主线程捕获，唯一可靠方式是 Agent 在每次 MCP 调用后立即记录，全部完成后用 Write 一次性写入。

## 禁止事项

- `evidence_items[].facts` 不能是空 dict 或裸 string
- 快照不能缺失（Stage 13 QA 硬阻断）
- 快照不能用简化 `tool_summaries` 代替完整 `tool_calls` + `tool_results`
- JSON 中禁止中文引号
