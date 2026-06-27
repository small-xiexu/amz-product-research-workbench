# Pipeline Contract Map — Agent ↔ 脚本接口规范

**目的**: Agent 产出格式与脚本消费格式的对照审计。每个 Agent 开发时必须对照此表确保字段路径、命名约定、枚举值与下游脚本一致。

**更新规则**: 新增 Agent 或修改契约字段时，同步更新此表。修复 Pipeline 断裂 bug 后，在对应条目加 `<!-- fix: #N -->` 注释。

---

## 1. Stage 1-2: Quick Market Check (P1)

| 产出文件 | 产出方 | 消费方 | 关键契约字段 |
|----------|--------|--------|------------|
| `mcp_snapshots/sellersprite_quick_snapshot.json` | SellerSprite Quick Agent | `quick_market_check.py` | `tool_calls[].call_id`, `tool_calls[].tool_name`, `tool_calls[].status` ∈ {success,empty,error}, `tool_calls[].started_at`, `tool_calls[].finished_at` |
| `mcp_snapshots/sorftime_quick_snapshot.json` | Sorftime Quick Agent | `quick_market_check.py` | 同上 |
| `quick_check/sellersprite_quick_evidence_packet.json` | `quick_market_check.py`（从 snapshot 构建） | Gate, Candidate Pool | `support_level` ∈ {strong,moderate,weak,negative}, `mixed_pool_level`, `demand_signal_level`, `price_band_health`, `category_boundary_clarity`, `confidence` ∈ {high,medium,low} |
| `quick_check/sorftime_quick_evidence_packet.json` | `quick_market_check.py` | Gate, Candidate Pool | 同上 |
| `quick_check/quick_market_gate.json` | `quick_market_check.py` → `decide_quick_gate()` | 全链路 | `gate_result` ∈ {continue,watch,stop} |

**Agent 输出约束**:
- `candidate_seeds[].reference_asins[]` 写在 `facts` dict 中，供 Stage 4 候选池汇总
- 快照必须用完整 `tool_calls` + `tool_results` 结构，不能用简化 `tool_summaries`

---

## 2. Stage 4: Candidate Pool (P2)

| 产出文件 | 产出方 | 消费方 | 关键契约字段 |
|----------|--------|--------|------------|
| `candidate_pool.json` | Main Agent | `build_mcp_candidate_pool.py`, Stage 5, 8 | `candidates[].candidate_id`, `candidates[].top_products[]`, `candidates[].reference_asins[]`, `candidates[].candidate_seeds[].reference_asins[]`, `candidates[].route_id`（kebab-case）, `pool_status` |

**Agent 输出约束**:
- ASIN 必须放在 `candidates[].top_products[]` 或 `candidates[].reference_asins[]` 或 `candidates[].candidate_seeds[].reference_asins[]` 中 —— 脚本会遍历这三个容器 <!-- fix: #5 -->
- `candidate_id` 格式随意，但**必须同时写入 `route_id` 字段**（kebab-case 英文），否则 Stage 8 ASIN 提取无法匹配 <!-- fix: #3 -->
- 禁止内部术语占位符（脚本会正则扫描 `sellersprite|sorftime|mcp|quick_gate|workflow_state`）
- `pool_status` ∈ {ready_for_route_matrix, needs_user_review, excluded}

**脚本消费方式**:
- `_extract_pool_asins()` → 遍历 `candidates[].asin`（顶层）, `top_products[]`, `reference_asins[]`, `candidate_seeds[].reference_asins[]`
- 路线匹配: 优先用 `candidate.route_id`，其次用 token 重叠匹配 `candidate_id` ↔ `route_id`

---

## 3. Stage 5: Route Matrix Confirmation (P3)

| 产出文件 | 产出方 | 消费方 | 关键契约字段 |
|----------|--------|--------|------------|
| `route_matrix_confirm.json` | Main Agent | `build_route_matrix_confirmation.py`, Stage 6-12 | `decision` ∈ {confirm,revise,stop}, `selected_routes[].route_id`（kebab-case，全链路统一 key）, `rejected_routes[].route_id` |
| `data_completeness_check.json` | `build_route_matrix_confirmation.py` | Stage 7 前置校验 | `overall_level` ∈ {acceptable,warning,blocker} |

**Agent 输出约束**:
- **`route_id` 必须用 kebab-case 英文**（如 `retractable-tape-leash`），禁止中文 `route_name`、抽象代码（C01, R01）、`p2-NN-xxx` 简写 <!-- fix: #3 -->
- `selected_routes[].route_id` 是全链路路线匹配的唯一 key —— Stage 6/7/8/9/10 全部依赖它
- 每个 selected_route 至少有 1 个参考 ASIN，否则触发 `merge_or_exclude` 判定

---

## 4. Stage 6: Dual MCP Deep Dive (P4)

| 产出文件 | 产出方 | 消费方 | 关键契约字段 |
|----------|--------|--------|------------|
| `mcp_snapshots/sellersprite_deep_snapshot.json` | Market Structure Agent | `build_sellersprite_deep_dive.py`, `build_conflict_review.py` | `tool_calls[].call_id/status/started_at/finished_at`, `tool_results[].call_id/status/raw_result` <!-- fix: #1 --> |
| `mcp_snapshots/sorftime_deep_snapshot.json` | Search Demand Agent | `build_sorftime_deep_dive.py`, `build_conflict_review.py` | 同上 |
| `market_structure/market_structure_evidence_packet.json` | `build_sellersprite_deep_dive.py` | `build_conflict_review.py`, Stage 8+ | `evidence_items[].facts.normalized_value.field_values` / `numeric_values`, `metric_basis{}`（14 字段），`selected_routes[]` |
| `search_demand/search_demand_evidence_packet.json` | `build_sorftime_deep_dive.py` | `build_conflict_review.py`, Stage 8+ | 同上 |

**Agent 输出约束**:
- 快照格式必须是 `tool_calls[]` + `tool_results[]` 完整结构，不能是简化的 `tool_summaries[]` <!-- fix: #1 -->
- `tool_calls[].status` ∈ {success, empty, error}
- `tool_results[].status` 同上，每个 result 必须有 `raw_result` 或 `normalized_preview`
- `evidence_items[].facts` 是 dict（P4 契约只要求 dict，不强求 `{value, source_path}` 结构）<!-- fix: #2 -->

**evidence_items 类型映射** (Market Structure):
| item_type | 来源 MCP 工具 | 对应 conflict pair |
|-----------|-------------|-------------------|
| `market_capacity` | market_research | market_capacity |
| `price_band` | market_price_distribution | price_band |
| `seller_concentration` | market_seller_concentration | seller_concentration |
| `competitor_structure` | product_research | competitor_sample |
| `asin_operating_data` | asin_detail | asin_operating_data |
| `review_threshold` | market_ratings_count | review_threshold |
| `category_boundary` | market_research | category_boundary |

---

## 5. Stage 7: Conflict Review (P4-Conflict)

| 产出文件 | 产出方 | 消费方 | 关键契约字段 |
|----------|--------|--------|------------|
| `conflict_review/deep_data_completeness_check.json` | `build_conflict_review.py` | Stage 8 `build_review_asin_batch.py` | `completeness_level` ∈ {acceptable,warning,blocker}, `route_checks[].route_id/status/gap_level` |
| `conflict_review/conflict_resolution_packet.json` | `build_conflict_review.py` | Stage 8 | `conflict_level` ∈ {none,warning,blocker}, `comparable_conflicts[].severity` ∈ {minor,material,blocking} |

**时序约束**:
- `progress.stages.stage_6_deep_dive.status == "done"` 时，如果冲突产物尚未生成，跳过 P4 进度校验（不报错）<!-- fix: #4 -->
- 正常流程：Stage 6 深挖 → Stage 7 冲突复核 → 标 done

---

## 6. Stage 8: VOC Review Analysis (P5)

| 产出文件 | 产出方 | 消费方 | 关键契约字段 |
|----------|--------|--------|------------|
| `review_voc/review_asin_batch.json` | `build_review_asin_batch.py` | 运营导出, `build_review_voc_package.py` | `asin_items[].asin`, `asin_items[].asin_role` ∈ {primary_reference, high_sales_benchmark, target_price_band_sample, new_release_sample, premium_benchmark, painpoint_reference, excluded_reference}, `asin_items[].route_ref`（kebab-case route_id） |
| `review_voc/voc_evidence_packet.json` | VOC Evidence Agent | Stage 9-12 | `pain_points_by_dimension[].evidence_refs[].review_id/quote`, `execution_provenance.executed_by_agent = true` |
| `review_voc/voc_gate.json` | `build_voc_gate.py` | Stage 9 | `decision`, `thresholds.current_total_reviews >= 30` |

**Agent 输出约束**:
- `pain_points_by_dimension[].evidence_refs[]` 每个条目必须含 `review_id` 和 `quote`
- `route_refs[]` 必须覆盖所有已确认路线（不得以"量太少"为由跳过）

---

## 7. Stage 9: Six-Dimensional Evaluation (P6)

| 产出文件 | 产出方 | 消费方 | 关键契约字段 |
|----------|--------|--------|------------|
| `evaluations/market_demand_evaluation.json` | Market Demand Agent | `build_evaluation_summary.py` | `score` (0-100), `rating` ∈ {strong,watch,weak,blocked}, `confidence`, `key_reasons[]` ≥1 |
| `evaluations/competition_evaluation.json` | Competition Agent | 同上 | 同上 |
| `evaluations/price_profit_evaluation.json` | Price/Profit Agent | 同上 | 同上 |
| `evaluations/voc_opportunity_evaluation.json` | VOC Opportunity Agent | 同上 | 同上 |
| `evaluations/risk_evaluation.json` | Risk Agent | 同上 | 同上 |
| `evaluations/data_quality_evaluation.json` | Data Quality Agent | 同上 | 同上 |
| `evaluations/evaluation_summary.json` | `build_evaluation_summary.py` | Stage 10 | `blocked_dimensions[]`, `low_confidence_dimensions[]`, `operator_judgment_constraints[]` |

**Agent 输出约束**:
- `execution_provenance` 必须含 `executed_by_agent`, `agent_role`, `execution_mode`
- `evidence_refs[]` ≥1 条
- 核心维度（market_demand, competition, price_profit, data_quality）的 `rating=blocked` → Stage 10 不能出 Go verdict

---

## 8. Stage 10a-b: Integrated Judgment (P7)

| 产出文件 | 产出方 | 消费方 | 关键契约字段 |
|----------|--------|--------|------------|
| `integrated_operator_judgment.json` (skeleton) | `build_integrated_judgment.py` | Route Strategy Agent, Growth & Risk Agent | 10 个 `__ai_judgment__` 占位字段 |
| `integrated_operator_judgment.json` (filled) | Route Strategy Agent + Growth & Risk Agent（并行） → Lead Operator Agent 合成 | Stage 11-12 | `route_recommendation.routes[]/primary_recommendation`, `route_tradeoff[]`, `competitor_benchmark[]`, `competitor_weakness_map[]`, `price_band_analysis[]`, `voc_to_spec[]`, `keyword_strategy.primary_attack[]/testable[]/negative[]`, `risk_mitigation[]`, `validation_roadmap[]`, `final_verdict` ∈ {go,watch,no_go,blocked}, `confidence` |

**硬约束**: 任何字段仍含 `__ai_judgment__` → verdict 强制为 `blocked`，Stage 10a 必须重试

---

## 9. Stage 11-12: Report Generation

| 产出文件 | 产出方 | 消费方 | 关键契约字段 |
|----------|--------|--------|------------|
| `analysis/report_data.seed.json` | `build_report_seed.py` | Report Generation Agent | 10 个 seed section（hero, category_panorama 等），判断类字段标记 `__ai_judgment__` |
| `analysis/report_data.json` | Report Generation Agent | `build_report_xlsx.py`, QA | AI 手写文案，**禁止**新增数字 |
| `analysis/<品名>_分析报告.html` | Report Generation Agent | QA | 禁止出现: Agent/MCP/tool/packet/pipeline/source_path/snapshot/schema_version/execution_provenance/卖家精灵/Sorftime/data source conflict |

---

## 10. 全局契约约定

### 命名铁律

| 约定 | 说明 |
|------|------|
| `route_id` | 全链路统一用 kebab-case 英文（`retractable-tape-leash`）。禁止中文、抽象代码、`p2-NN-xxx` 简写。Stage 5 定义，Stage 6-12 消费。 |
| `evidence_refs` / `source_refs` | 使用 `path#fragment` 格式（`market_structure/market_structure_evidence_packet.json#evidence_items[0]`）。QA 阶段依赖此格式做三级溯源。 |
| `execution_provenance` | Agent 产出: `executed_by_agent: true, execution_mode: agent`；脚本产出: `execution_mode: script_generated` |
| `confidence` | 全链路统一枚举: {high, medium, low} |
| `status` | tool_call/tool_result: {success, empty, error}；stage: {pending, running, done, blocked, failed, needs_user} |

### 枚举值全集

| 字段 | 允许值 |
|------|--------|
| `gate_result` | continue, watch, stop |
| `decision` (route_matrix) | confirm, revise_candidate_pool, stop |
| `completeness_level` | acceptable, warning, blocker |
| `conflict_level` | none, warning, blocker |
| `conflict_severity` | minor, material, blocking, basis_mismatch |
| `rating` (evaluation) | strong, watch, weak, blocked |
| `score` (evaluation) | 0-100 整数 |
| `final_verdict` | go, watch, no_go, blocked |
| `asin_role` | primary_reference, high_sales_benchmark, target_price_band_sample, new_release_sample, premium_benchmark, painpoint_reference, excluded_reference |

### 文件路径约定

所有路径相对于 `runs/<run_id>/`：

| 子目录 | 用途 |
|--------|------|
| `mcp_snapshots/` | MCP 原始/深挖快照 |
| `quick_check/` | Stage 2 快验产物 |
| `market_structure/` | 卖家精灵深挖 evidence packet |
| `search_demand/` | Sorftime 深挖 evidence packet |
| `conflict_review/` | Stage 7 冲突复核 |
| `review_voc/` | Stage 8 VOC 产物 |
| `evaluations/` | Stage 9 六维评估 |
| `analysis/` | Stage 11-12 报告 |

---

## 已知修复记录

| 修复 | 日期 | 问题 | 涉及文件 |
|------|------|------|----------|
| #1 | 2026-06-27 | Deep snapshot 用简化 tool_summaries 而非完整 tool_calls | Agent prompts, `build_sellersprite_deep_dive.py` |
| #2 | 2026-06-27 | validate_evidence_packet 额外结构约束 vs P4 契约 | `validate_evidence_packet.py`, `build_conflict_review.py` |
| #3 | 2026-06-27 | 路线命名三套体系互不打通 | `build_review_asin_batch.py`, `validate_evidence_packet.py` |
| #4 | 2026-06-27 | progress.json Stage 6 done 鸡生蛋 | `p4_contracts.py` |
| #5 | 2026-06-27 | _extract_pool_asins 不扫描 top_products | `build_review_asin_batch.py` |
| #6 | 2026-06-27 | watch 状态被误判为不可进入 P3 | `build_mcp_candidate_pool.py` |
