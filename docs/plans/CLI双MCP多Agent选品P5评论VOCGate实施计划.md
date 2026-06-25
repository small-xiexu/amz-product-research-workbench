# CLI 双 MCP 多 Agent 选品 P5 评论 VOC Gate 实施计划

状态：P5 全部完成。P5-0 契约设计 → P5-1 ASIN 批次 → P5-2 VOC 包 → P5-3 证据包+Gate → P5-4 回归收口 → P5 refinement 语义与职责边界清理。

本计划是 P5 唯一进度台账。P5 基于 P4 `stage_6_deep_dive` 已完成产物，在 `stage_7_voc_gate` 阶段完成评论 VOC 证据包和 Gate 决策。不进入报告、评价 Agent 最终判断或 Stage 7 正式交付。

## 范围边界

- P5 输入来自 P4 的 6 个产物：`route_matrix_confirm.json`、`candidate_pool.json`、`market_structure/market_structure_evidence_packet.json`、`search_demand/search_demand_evidence_packet.json`、`conflict_review/deep_data_completeness_check.json`、`conflict_review/conflict_resolution_packet.json`，以及评论插件导出的 Excel/HTML/JSON。
- P5 产出：`review_voc/review_asin_batch.json`、`review_voc/review_voc_package.json`、`review_voc/voc_evidence_packet.json`、`review_voc/voc_gate.json`。
- 不进入正式报告、HTML、XLSX、评价 Agent 最终判断、资深运营专家最终排序。
- 不进入供应商、成本、利润、合规、产品方案。
- 不改 Web / server 主链路。
- 不写死任何具体品类、ASIN、关键词、品牌、卖家、供应商或价格。
- VOC 脚本只做数据导入、规范化、契约校验和证据包组织；不在脚本里写关键词规则做痛点分析。痛点归因由 VOC Evidence Agent 或主 Agent 基于 normalized_reviews 和 evidence_refs 生成。

## 与旧流程的关系

- 旧 Skill `SKILL.md` 中 Stage 6 描述的是旧流程的"评论 VOC 分析"，当前仍以旧 stage 命名和旧 CLI 命令为主。
- 新 CLI 双 MCP 多 Agent 流程中，P4 `stage_6_deep_dive` 完成后 `next_action.stage_id = "stage_7_voc_gate"`。
- P5 所有实现以 `stage_7_voc_gate` 为准，不兼容旧 Stage 6 命名。
- 旧 Skill 的 Stage 6 描述待 P5 全部完成后同步，不在 P5-0 阶段修改 Skill。
- `docs/评论VOC导出指令完整性规范.md` 中对运营的 ASIN 输出格式继续适用，P5-1 的 ASIN 批次计划将复用该规范。

## 验收清单

- [x] P5-0 VOC Gate 契约设计与实施计划冻结
  - 状态：已完成；已梳理现有 VOC 导入脚本能力、VOC Evidence Agent 角色和旧流程描述；已定义 P5 输入输出、阶段边界、Gate 决策规则、阻断条件、样本阈值和 progress 规则。
  - 新增文档：`docs/plans/CLI双MCP多Agent选品P5评论VOCGate实施计划.md`（本文件）、`docs/references/p5_voc_gate_contract.md`（P5 契约说明）。
  - 验证命令：`python3 scripts/check_generic_redlines.py --token-file tests/fixtures/generic_redline_tokens.json --no-auto-run-dir`、`git diff --check`。
  - 结果：全部通过；红线扫描输出 `generic_redline: OK`，`git diff --check` 无输出。

- [x] P5-1 生成 VOC ASIN 批次计划
  - 状态：已完成；已实现全链路 ASIN 批次生成，从 6 个 P4 产物提取 ASIN、按 7 种竞品角色分配、生成 operator_instruction 和 route_coverage。
  - 新增 pipeline：`packages/research_core/pipeline/build_review_asin_batch.py`
  - 新增 CLI：`scripts/build_review_asin_batch.py`
  - 新增契约：`packages/research_core/contracts/p5_contracts.py`（`validate_review_asin_batch` 等 4 个 validator）
  - 更新契约导出：`packages/research_core/contracts/__init__.py`
  - 新增测试：`tests/test_p5_asin_batch.py`（18 项：HappyPath 4、Error 2、Contract 8、Progress 4）
  - 验收依据：`runs/<run_id>/review_voc/review_asin_batch.json` 通过 contract validator。
  - 验证命令：`python3 -m unittest tests.test_p5_asin_batch -v`、`python3 -m unittest discover -v`、`python3 scripts/check_generic_redlines.py --token-file tests/fixtures/generic_redline_tokens.json --no-auto-run-dir`、`git diff --check`。
  - 结果：全部通过；18 个 P5-1 测试通过；全量 `unittest discover` 通过 171 个测试、跳过 3 个既有条件测试；红线扫描输出 `generic_redline: OK`，`git diff --check` 无输出。
  - 目标：基于 P4 产物生成 `review_voc/review_asin_batch.json`，告诉运营或评论插件应抓哪些 ASIN 的评论。
  - 输入：`route_matrix_confirm.json`、`candidate_pool.json`、P4 `market_structure_evidence_packet.json`、P4 `search_demand_evidence_packet.json`、`deep_data_completeness_check.json`、`conflict_resolution_packet.json`。
  - 输出：`runs/<run_id>/review_voc/review_asin_batch.json`。
  - ASIN 选择逻辑按"路线覆盖"和"竞品角色"组织：高销量标杆、目标价格带样本、低评论新品样本、差异化/痛点参考样本、排除或混池对照样本。
  - 用户侧只输出可复制 ASIN 清单、站点、目标目录和导入命令；不要求运营填写复杂筛选条件。
  - 验收依据：`runs/<run_id>/review_voc/review_asin_batch.json` 通过 contract validator。
  - 验证命令：`python3 -m unittest tests.test_p5_asin_batch -v`、`python3 -m unittest discover -v`、`python3 scripts/check_generic_redlines.py --token-file tests/fixtures/generic_redline_tokens.json --no-auto-run-dir`、`git diff --check`。

- [x] P5-2 接入评论插件导出并生成规范化 VOC 包
  - 状态：已完成；Pipeline 模块和 CLI 入口已实现，复用现有解析逻辑生成 P5 专用 review_voc_package.json。
  - 新增 pipeline：`packages/research_core/pipeline/build_review_voc_package.py`
  - 新增 CLI：`scripts/build_review_voc_package.py`
  - 新增测试：`tests/test_p5_voc_package.py`（22 项：HappyPath 6、Error 5、Scope 3、Contract 6、CLI Smoke 2）
  - 结果：全部通过；193 个全量测试通过、3 个既有条件测试跳过；红线扫描 `generic_redline: OK`；`git diff --check` 无输出。

- [x] P5-3 生成 VOC Evidence Packet 与 VOC Gate
  - 状态：已完成；Pipeline 模块和 CLI 入口已实现，支持数据驱动的证据包生成和规则驱动的 Gate 决策。
  - 新增 pipeline：`packages/research_core/pipeline/build_voc_gate.py`（证据包 + Gate 生成）
  - 新增 CLI：`scripts/build_voc_gate.py`
  - 新增测试：`tests/test_p5_voc_gate.py`（30 项：HappyPath 5、Decision 7、Contract 11、Scope 3、MissingInput 4）
  - Gate 决策覆盖：continue/watch/stop/need_more_reviews 四个路径，含 P4 conflict blocker 阻断、P4 completeness blocker 阻断、warning 继承、样本不足阻断
  - Evidence 证据包包含：review_scope、asin_coverage（by_route/by_asin_role）、pain_points_by_dimension（数据驱动的 n-gram 分组，每条含 evidence_refs 溯源）、unmet_needs、differentiation_opportunities、mixed_pool_signals、review_quality_gaps
  - 痛点分析采用数据驱动方式（评论中文 n-gram 频率分组），不写死关键词规则
  - Progress 更新：stage_7_voc_gate.status = "done"，next_action 根据 decision 指向 stage_7_report 或 stay/stop
  - 结果：全部通过；223 个全量测试通过、3 个既有条件测试跳过；红线扫描 `generic_redline: OK`；`git diff --check` 无输出。

- [x] P5-4 测试与回归验证
  - 状态：已完成；P5 全链路回归收口，跨阶段串联验证通过。
  - 新增测试：`tests/test_p5_regression.py`（16 项：E2E 链路 3、Progress 链 3、跨阶段阻断 4、数据流完整性 3、证据链完整性 2、范围边界 2）
  - 覆盖项全部验收通过：
    - 端到端链路：P5-1→P5-2→P5-3 串联，4 个产物全部落盘 + 全部通过 contract validator
    - CLI smoke：3 个 CLI 各自有测试（P5-1/P5-2/P5-3 共 5 个 CLI smoke）
    - progress 链：status pending→running→done，completed_artifacts 累加 4 个产出，next_action 按 decision 分流
    - 范围边界：P5-2 不生成 P5-3 产物，全链路不生成 HTML/XLSX/md/report
    - 阻断验证：缺 asin_batch 阻断 P5-2，缺 voc_package 阻断 P5-3，缺 P4 conflict 阻断 P5-3，P5-1 独立运行
    - 决策路径：continue/watch/stop/need_more_reviews 各至少一个用例（P5-3 测试覆盖）
    - 契约验证：4 个 P5 契约 validator 全覆盖（P5-1/P5-2/P5-3 测试 + E2E 测试）
    - 数据流：P5-2 引 P5-1 batch，P5-3 evidence 引 P5-2 package，P5-3 gate 引 P5-3 evidence
    - 证据链：每个 pain_point 有 review_id/asin/rating/source_path 可追溯
  - P5 全量：86 个测试通过；全量 `unittest discover` 239 个测试通过、3 个既有条件测试跳过
  - 验证命令全部通过：
    - `python3 -m unittest tests.test_p5_regression -v` → 16 OK
    - `python3 -m unittest tests.test_p5_asin_batch tests.test_p5_voc_package tests.test_p5_voc_gate -v` → 70 OK
    - `python3 -m unittest discover -v` → 239 OK (skipped=3)
    - `python3 scripts/check_generic_redlines.py --token-file tests/fixtures/generic_redline_tokens.json --no-auto-run-dir` → `generic_redline: OK`
    - `git diff --check` → 无输出

- [x] P5 refinement — 语义修正与职责边界清理
  - 状态：已完成；两个修复全部落地，86 个 P5 测试 + 全量 239 测试通过。
  - **Fix 1 - P5-1 零 ASIN 语义修正**：
    - `run_review_asin_batch()` 现在检测零 ASIN 时跳过文件写出，仅回写 `progress.json`（`status: blocked`，`next_action.type: needs_user`）
    - 有 ASIN 但覆盖不足时仍产出 `review_asin_batch.json` 并附 `data_gaps`
    - 新增 `_update_progress_blocked()` 函数
    - 测试 `test_no_asins_in_inputs_still_produces_batch_with_gaps` 已适配新行为：零 ASIN 时不再产出 batch 文件，验证 blocked 状态
  - **Fix 2 - P5-3 职责边界修正**：
    - 移除 `_build_pain_points()` 和 `_build_needs_and_opps()` 两个死函数（约 140 行）
    - `pain_points_by_dimension`、`unmet_needs`、`differentiation_opportunities` 设为空列表，明确标记为 Agent 边界
    - `execution_provenance.execution_mode` 改为 `"serial_fallback"`（原为 `"script_generated_skeleton"`）
    - `build_voc_gate` 模块 docstring 更新，明确脚本/Orchestrator/Agent 三方职责
  - 验证命令全部通过：
    - `python3 -m unittest tests.test_p5_asin_batch tests.test_p5_voc_package tests.test_p5_voc_gate tests.test_p5_regression -v` → 86 OK
    - `python3 -m unittest discover -v` → 239 OK (skipped=3)
    - `python3 scripts/check_generic_redlines.py --token-file tests/fixtures/generic_redline_tokens.json --no-auto-run-dir` → `generic_redline: OK`
    - `git diff --check` → 无输出

