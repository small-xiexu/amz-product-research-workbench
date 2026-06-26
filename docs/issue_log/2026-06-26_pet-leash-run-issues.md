# 宠物牵引绳 Run 中发现的问题与修复方案

**日期**：2026-06-26 | **发现人**：主 Agent + 运营 | **Run**：pet-leash-us

---

## 问题 1：Agent 产出路径与脚本期望不一致

**现象**：Agent 深挖产出写入 `deep_dive/`，但 Stage 7-8 脚本（`build_review_asin_batch.py`、`build_conflict_review.py`）硬编码期望 `market_structure/market_structure_evidence_packet.json` 和 `search_demand/search_demand_evidence_packet.json`。

**影响**：每个 run 都要手动建符号链接，否则脚本链断裂。

**根因**：SKILL.md Stage 6 的 Agent prompt 中指定的输出路径与脚本硬编码路径未统一。

**修复**：
- 文件：`/Users/sxie/.claude/skills/amazon-product-research/SKILL.md`
- 位置：Stage 6 Agent prompt 中的输出路径
- 改动：`deep_dive/market_structure_evidence_packet.json` → `market_structure/market_structure_evidence_packet.json`
- 改动：`deep_dive/search_demand_evidence_packet.json` → `search_demand/search_demand_evidence_packet.json`
- 同步检查 `multi_agent_dispatch.md` 中 Stage 6 产物路径是否一致

---

## 问题 2：Market Structure Agent 单 Agent 超时

**现象**：Stage 6 Market Structure Agent 覆盖 11 条路线，单 Agent 调用 ~58 次 MCP，上下文膨胀到 ~1.2MB，运行 20 分钟后因无进度被 watchdog 杀掉。

**影响**：Agent 收集了大量数据但未能完成最终写入，需恢复后重写。

**根因**：单 Agent 承担了全部 11 条路线的深挖任务。

**修复方案**（二选一）：

### 方案 A：按路线分片，多个 Agent 串行接力
- 将 11 条路线拆成 3 组（4+4+3）
- 3 个 Agent 串行执行：Agent A 完成 → Agent B 继续 → Agent C 继续
- 每个 Agent 写入独立的 route_breakdown 片段
- 主 Agent 最后合并成一个完整 evidence packet
- **优点**：单个 Agent 不会超时，且避免了并行导致的 MCP 超频（40次/分钟限制）
- **缺点**：总耗时会增加（3 个串行），但比单 Agent 超时重跑更可控

### 方案 B：限定单 Agent 最大路线数
- 在 SKILL.md 中规定：深挖路线 > 8 条时，自动触发分片
- 路线 ≤ 8 条时仍可单 Agent

**推荐**：方案 A（分片串行），兼顾 MCP 限流和 Agent 稳定性。

**修改文件**：
- `/Users/sxie/.claude/skills/amazon-product-research/SKILL.md` Stage 6 部分
- `/Users/sxie/.claude/skills/amazon-product-research/references/multi_agent_dispatch.md` Stage 6 调度规则

---

## 问题 3：占位符扫描过于暴力

**现象**：`_check_placeholders()` 对所有非白名单 key 下的 string 值做正则 `sellersprite|sorftime|mcp|quick_gate|workflow_state` 扫描。`candidate_pool.json` 的 `appearance_reason`、`reason`、`route_summary` 等业务描述字段被命中，Agent 需要 3 轮清理才能通过校验。

**影响**：纯机械工作，浪费 token 和时间。

**根因**：白名单 `_TECHNICAL_KEY_PATTERNS` 缺少业务描述类 key。

**修复**：
- 文件：`/Users/sxie/Documents/亚马逊/amz-product-research-workbench/packages/research_core/pipeline/build_mcp_candidate_pool.py`
- 在 `_TECHNICAL_KEY_PATTERNS` 中追加：
  ```python
  "appearance_reason",
  "reason",
  "route_summary",
  "note",
  "notes",
  "description",
  "detail",
  "summary",
  "statement",
  "insights_for_handoff",
  "decision_reason",
  "selection_reason",
  "verdict_reason",
  "biggest_opportunity",
  "biggest_risk",
  "recommendation",
  ```
- 同步修改：
  - `/Users/sxie/Documents/亚马逊/amz-product-research-workbench/packages/research_core/pipeline/build_route_matrix_confirmation.py` 中的同名白名单
  - `/Users/sxie/Documents/亚马逊/amz-product-research-workbench/packages/research_core/pipeline/build_report_seed.py` 中的同名白名单（如有）

---

## 问题 4：深挖快照在子 Agent 模式下不可用

**现象**：`build_deep_snapshot.py` 期望从 Agent MCP dump JSON 文件提取 tool_calls/tool_results。子 Agent 的 tool_calls 在 JSONL 格式的 task output 文件中，格式不匹配，无法生成合约快照。导致整条脚本链（`build_sellersprite_deep_dive.py` → `build_deep_evidence_packet.py` → `build_conflict_review.py`）全部断裂。

**影响**：
- Stage 6 深挖脚本无法运行（快照不完整报 `missing required fields`）
- Stage 7 冲突复核脚本无法运行（依赖 `deep_data_completeness_check.json`）
- Stage 13 QA 数据溯源链中断（无法从报告数字追溯到 MCP 原始返回）

**注意**：不影响数据正确性——Agent 证据包中的数字是真实 MCP 返回的。影响的是 Stage 13 的可追溯性。

**修复方案**（二选一）：

### 方案 A：Agent 结束时自动生成快照
- Agent prompt 中要求：在写入 evidence packet 的同时，将 tool_calls 摘要写入快照文件
- 快照格式与 `build_deep_snapshot.py` 期望的合约一致
- **优点**：不改变现有脚本链
- **缺点**：Agent 需要额外工作量

### 方案 B：Stage 7 脚本直接读证据包
- `build_conflict_review.py` 改为接受 evidence packet 作为主输入，快照作为 optional
- 快照缺失时降级为 `snapshot_unavailable`，不阻塞流程
- **优点**：减少中间层依赖
- **缺点**：Stage 13 QA 仍缺溯源链

**推荐**：A+B 组合——Stage 6 让 Agent 顺便写快照（保 Stage 13 溯源），Stage 7 改为优先读证据包（不阻塞流程）。

**修改文件**：
- `/Users/sxie/.claude/skills/amazon-product-research/SKILL.md` Stage 6 Agent prompt（方案 A）
- `/Users/sxie/Documents/亚马逊/amz-product-research-workbench/packages/research_core/pipeline/build_conflict_review.py`（方案 B）

---

## 问题 5：`build_review_asin_batch.py` KeyError

**现象**：脚本执行到最后一行 `print(f"batch: {outputs['asin_batch']}")` 时 KeyError，产物未写盘。

**影响**：ASIN 批处理文件 `review_asin_batch.json` 和导出说明 `inputs/reviews/README.txt` 未生成。

**根因**：`main()` 函数返回的 dict key 与调用方期望的 key 名不一致。

**修复**：
- 文件：`/Users/sxie/Documents/亚马逊/amz-product-research-workbench/packages/research_core/pipeline/build_review_asin_batch.py`
- 行 747：
  ```python
  # 修改前
  print(f"batch: {outputs['asin_batch']}")
  # 修改后
  print(f"batch: {outputs.get('asin_batch', outputs.get('batch_path', 'unknown'))}")
  ```
- 同步检查 `generate_asin_batch()` 函数（行 71-110）返回的 dict key 名是否与 main() 一致

---

## 修复优先级

| 优先级 | 问题 | 理由 |
|---|---|---|
| P0 | #5 KeyError | 一行修复，阻塞所有 run 的 Stage 8 |
| P1 | #1 路径不统一 | 每个 run 都受影响，修复成本低 |
| P1 | #3 占位符过激 | 每个 run Stage 4 浪费 3+ 轮清理 |
| P2 | #4 快照不可用 | 影响 Stage 13 QA 溯源，不阻塞交付 |
| P2 | #2 Agent 超时 | 仅路线数 > 8 时触发，可降级重试 |

---

## 对当前 pet-leash-us run 的影响

当前 run 已通过手动 workaround 推进到 Stage 8（等待运营导出评论）。后续 Stage 9-13 的关键依赖是证据包内容（已有）而非快照（缺失）。

Stage 13 QA 时会因快照缺失报 `source_path 不可解析`，需在报告中标注数据溯源降级。
