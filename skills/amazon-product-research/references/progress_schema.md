# progress.json 断点恢复契约

每个 run 目录下必须有 `progress.json`，AI 在每个阶段完成后自动写入：

- Stage 1 意图收集完成
- Stage 3 快验门控通过
- Stage 4 候选池生成
- Stage 5 路线确认（**尤其等运营决策时**）
- Stage 6 双 MCP 深挖完成
- Stage 8 VOC 分析完成
- Stage 13 QA 完成
- 任何需要**等待运营回复**的时刻

## 结构

```json
{
  "run_id": "YYYYMMDD_示例品类",
  "current_stage": "stage_5_route_matrix",
  "status": "waiting_operator",
  "stages_completed": ["stage_1_inputs", "stage_2_market_quick_check", "stage_3_quick_gate", "stage_4_candidate_pool"],
  "last_updated": "2026-06-25T22:00:00",
  "context_brief": "已确认{品类方向}为优先方向，排除{具体排除方向}",
  "pending_questions": [
    "目标价格带是$X-Y还是$Y-Z？"
  ],
  "next_step": "等待运营确认路线后进入Stage 6双MCP深挖"
}
```

## 字段

| 字段 | 必填 | 说明 |
|---|---|---|
| `run_id` | 是 | 与目录名一致 |
| `current_stage` | 是 | 当前所处阶段标识 |
| `status` | 是 | `in_progress` / `waiting_operator` / `qa_review` / `completed` |
| `stages_completed` | 是 | 已完成的阶段列表 |
| `last_updated` | 是 | ISO 时间戳 |
| `context_brief` | 否 | 当前进度一句话总结 |
| `pending_questions` | 否 | 等待运营回答的问题 |
| `next_step` | 否 | 下一步动作描述 |

## 恢复流程

运营重新连接后说"继续 <run_id>"，AI 必须：

1. 读 `progress.json` 了解当前阶段和卡点
2. 读已完成的产物文件（candidate_pool / route_matrix / evidence packets / report_data）重建数据认知
3. 如有 `pending_questions`，优先把问题重新呈现给运营
4. 如无待确认问题，从 `next_step` 继续推进
