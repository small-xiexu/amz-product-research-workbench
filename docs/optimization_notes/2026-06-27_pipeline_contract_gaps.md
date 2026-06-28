# Pipeline 契约对齐待优化清单

**日期**: 2026-06-27
**来源**: 宠物牵引绳全流程跑通过程中发现的 Agent–脚本契约断裂点 <!-- generic-redline: allow historical run postmortem retains original case name -->
**优先级**: P1（影响批量跑品类的自动化程度）

---

## 1. Deep Snapshot 契约格式断裂

**现象**：Agent 产出的快照是简化 `tool_summaries` 格式，P4 契约要求完整 `tool_calls` + `tool_results` 结构（各含 `call_id/status/started_at/finished_at` 等字段）。每次需要手工写转换脚本。

**涉及文件**：
- Agent prompt: `agents/market-structure-agent.md`、`agents/search-demand-agent.md`
- 契约定义: `packages/research_core/contracts/p4_contracts.py` → `validate_deep_snapshot`
- 转换逻辑: `packages/research_core/pipeline/build_sellersprite_deep_dive.py` → `normalize_sellersprite_probe_snapshot`

**建议修复**：
- Agent prompt 中直接嵌入 deep snapshot 的 JSON schema（必填字段清单）
- 或脚本侧新增 `--from-agent-format` 参数，自动做格式升级

---

## 2. validate_evidence_packet.py 与 P4 契约规则不一致

**现象**：`scripts/validate_evidence_packet.py` 要求 facts 每个 value 必须是 `{value, source_path}` 结构；但 P4 官方契约（`p4_contracts.py`）只要求 facts 是 dict。冲突复核代码直接访问 `normalized_value.field_values`，被包装后报 `NoneType`。

**涉及文件**：
- `scripts/validate_evidence_packet.py` → `_check_facts_structure`
- `packages/research_core/contracts/p4_contracts.py` → `_validate_evidence_item`
- `packages/research_core/pipeline/build_conflict_review.py` → `_find_normalized_value`

**建议修复**：
- 统一 facts 结构规范：要么全部用 `{value, source_path}`（改冲突复核代码适配），要么只要求 dict（改校验器放宽）
- 推荐后者：P4 契约是权威源，自定义校验器不应额外加结构约束

---

## 3. 路线命名三套体系互不打通

**现象**：
- `candidate_pool.json` 用 `p2-NN-<简写方向>`（如 `p2-03-<品类词>-<形态>`）
- `route_matrix_confirm.json` 用 `<完整产品形态>`（如 `<品类词>-<材质>-<功能>`）
- `validate_evidence_packet.py` 用中文 `route_name` 做路线覆盖对比

三种命名在同一路线上指向不同字符串，Stage 8 ASIN 提取脚本三套都对不上，需要词重叠模糊匹配才能跑通。根源是 Agent 在 Stage 4 生成了自己的简写 ID，但未从路线矩阵回填正式 `route_id`。

**涉及文件**：
- `packages/research_core/pipeline/build_review_asin_batch.py` → `_extract_pool_asins`、`_extract_selected_routes`
- `scripts/validate_evidence_packet.py` → `_check_route_coverage`

**建议修复**：
- Stage 4 生成 candidate 时直接写 `route_id` 字段（从路线矩阵回填）
- 全链路统一用 `route_id`（kebab-case 英文）做匹配 key
- `_check_route_coverage` 改为用 `route_id` 而非 `route_name`

---

## 4. progress.json 状态机鸡生蛋问题

**现象**：Stage 6 标 `done` 后，`validate_p4_preconditions` 立即检查 `conflict_review/deep_data_completeness_check.json` 是否存在（此时尚未生成）。必须先保持 Stage 6 非 `done`，跑完 Stage 7 冲突复核再标完成。

**涉及文件**：
- `packages/research_core/contracts/p4_contracts.py` → `validate_p4_preconditions`（L467-471）
- `packages/research_core/pipeline/build_conflict_review.py` → `run_conflict_review`

**建议修复**：
- 在 `validate_p4_preconditions` 中将 Stage 6 `done` 时的冲突产物检查改为 `required=False`（不存在时不报错）
- 或在 SKILL.md 中明确写出"Stage 6 完成后标记为 `deep_dive_complete` 而非 `done`，Stage 7 完成后再置 `done`"

---

## 5. _extract_pool_asins 不扫描 top_products

**现象**：候选池的 ASIN 全在 `candidates[].top_products[]` 嵌套结构中，但 `_extract_pool_asins` 只查 `entry.asin` 顶层字段，导致 Stage 8 第一步报"无可用 ASIN"。

**涉及文件**：
- `packages/research_core/pipeline/build_review_asin_batch.py` → `_extract_pool_asins`

**建议修复**：
- `_extract_pool_asins` 增加 `top_products` 遍历逻辑（已临时修复，需回看是否还有 `reference_asins`、`candidate_seeds` 等其他 ASIN 容器字段）

---

## 6. quick_gate/gate_result 的 "watch" 状态语义模糊

**现象**：快验 Gate 返回 `watch` 后，Stage 4 校验脚本报 `p3_entry_ready: false`（"Candidate pool can enter P3 only when quick gate continues"），但实际流程中 `watch` 就是继续推进的信号。这个 `false` 标记可能误导运营。

**涉及文件**：
- `scripts/build_mcp_candidate_pool.py` 或对应的 pipeline 校验逻辑
- `quick_check/quick_market_gate.json`

**建议修复**：
- `watch` 状态在进度校验中也应视为可进入 P3（`pass: true`），或拆为 `watch_continue` / `watch_block` 两种子状态

---

## 总结

根本原因：**Agent 产出格式和脚本期望的契约没有完全对齐**。Snapshot 结构、facts 字段形态、路线命名体系、ASIN 嵌套位置——每次断裂点都是同一类问题。

建议：将 Agent prompt 中要求的输出 JSON schema 与脚本侧 contract 做一次对照审计，生成一份 `CONTRACT_MAP.md` 作为后续 Agent 开发的参考规范。
