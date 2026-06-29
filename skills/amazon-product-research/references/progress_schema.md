# progress.json 断点恢复契约

每个 run 目录下必须有 `progress.json`。它是断点恢复的运行台账，脚本或主 Agent 在阶段开始、完成、阻塞、等待运营输入时更新。

## 顶层结构

```json
{
  "schema_version": "p0-contract-v1",
  "current_stage": "stage_5_route_matrix",
  "updated_at": "2026-06-29T10:00:00+08:00",
  "global_blockers": [],
  "next_action": {
    "type": "needs_user",
    "stage_id": "stage_5_route_matrix",
    "description": "等待运营确认路线矩阵后进入 Stage 6 双 MCP 深挖"
  },
  "completed_artifacts": [
    "candidate_pool.json",
    "route_matrix_confirm.json"
  ],
  "stages": {
    "stage_5_route_matrix": {
      "status": "needs_user",
      "attempts": 1,
      "input_artifacts": ["candidate_pool.json"],
      "output_artifacts": ["route_matrix_confirm.json"],
      "validation_checks": [],
      "last_error": "",
      "next_required_user_action": "确认保留路线",
      "resume_policy": {
        "reuse_existing_artifacts": true,
        "allow_repeat_mcp_call": false,
        "force_refresh": false
      }
    }
  }
}
```

## 字段

| 字段 | 必填 | 说明 |
|---|---|---|
| `schema_version` | 是 | 契约版本 |
| `current_stage` | 是 | 当前阶段 ID |
| `updated_at` | 是 | ISO 时间戳 |
| `global_blockers` | 是 | 全局阻断原因列表，无阻断为空数组 |
| `next_action` | 是 | 下一步动作，至少含 `type` 和 `description` |
| `completed_artifacts` | 是 | 已完成产物路径列表 |
| `stages` | 是 | 各阶段状态对象 |

## 阶段状态

`stages.<stage_id>.status` 统一使用：

| 状态 | 含义 |
|---|---|
| `pending` | 尚未开始 |
| `running` | 正在执行 |
| `done` | 已完成且产物已通过对应校验 |
| `blocked` | 阻断，需要人工或外部状态变化 |
| `failed` | 执行失败，可按错误信息修复后重试 |
| `needs_user` | 等待运营确认或补充输入 |

每个阶段对象至少包含：

| 字段 | 说明 |
|---|---|
| `attempts` | 当前阶段尝试次数 |
| `input_artifacts` | 本阶段输入产物 |
| `output_artifacts` | 本阶段输出产物 |
| `validation_checks` | 已运行校验及结果 |
| `last_error` | 最近错误，无错误为空字符串 |
| `next_required_user_action` | 等待运营时必须写清楚要什么 |
| `resume_policy` | 恢复策略，说明是否复用产物、是否允许重复 MCP 调用 |

## 恢复流程

运营重新连接后说“继续 `<run_id>`”，AI 必须：

1. 读取 `progress.json` 的 `current_stage`、`stages`、`next_action`、`global_blockers`。
2. 若当前阶段为 `needs_user`，先复述 `next_required_user_action`。
3. 若当前阶段为 `blocked` 或 `failed`，先说明阻断/失败原因和可恢复动作。
4. 若可继续，按 `resume_policy` 复用已完成产物；禁止无理由重复 MCP 调用。
5. 读取已完成产物重建上下文，再进入下一阶段。
