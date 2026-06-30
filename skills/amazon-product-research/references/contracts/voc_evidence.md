# Stage 8 Contract — voc_evidence_packet.json

**产出方**: VOC Evidence Agent
**消费方**: `validate_voc_packet.py`, Stage 9-12
**输出路径**: `review_voc/voc_evidence_packet.json`

## 必填顶层字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `schema_version` | string | `"p5-voc-evidence-v1"` |
| `packet_id` | string | `"voc_evidence_packet"` |
| `run_id` | string | run 目录名 |
| `pain_points` | list[dict] | 痛点列表，≥ 1，每个 ≥ 3 条评论引用 |
| `route_refs` | list[string] | 覆盖所有 selected_routes |
| `execution_provenance` | dict | 见下方 |
| `evidence_refs` | list[string] | 至少 1 条 |
| `confidence` | string | ∈ {high, medium, low} |

## execution_provenance 必填

```json
{
  "executed_by_agent": true,
  "agent_role": "VOC Evidence Agent",
  "execution_mode": "agent",
  "subagent_id": "<本 Agent 的 run_id>",
  "source_packet": "review_voc/review_voc_package.json"
}
```

禁止标记为 `execution_mode=serial_fallback` 或 `executed_by_agent=false`。

## pain_points[] 每条必填

| 字段 | 类型 | 说明 |
|------|------|------|
| `pain_point_id` | string | 唯一标识 |
| `dimension` | string | 痛点维度（中文） |
| `priority` | string | ∈ {P0, P1, P2}（JSON 中用枚举值，HTML 中翻译） |
| `description` | string | 痛点描述 |
| `evidence_refs` | list[dict] | ≥ 3 条，每条含 `review_id` + `quote` |
| `route_refs` | list[string] | 涉及的路线 |
| `spec_requirement` | string | 产品规格要求 |
| `listing_risk_note` | string | Listing 风险提示 |

## evidence_refs[] 每条必填

| 字段 | 类型 | 说明 |
|------|------|------|
| `review_id` | string | 评论 ID，如 `R3D9KL05O74U62` |
| `quote` | string | 原文片段 |

## 禁止事项

- 不得以"量太少"为由跳过任何 selected_routes 的评论分析
- `evidence_refs` 不能为空，必须有 review_id 和 quote
- 禁止标记 `executed_by_agent=false`
