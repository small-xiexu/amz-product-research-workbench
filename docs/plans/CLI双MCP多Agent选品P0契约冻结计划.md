# CLI 双 MCP 多 Agent 选品 P0 契约冻结计划

状态：P0 契约冻结已完成；已通过 P0 专项测试、全量 unittest、通用红线扫描和 `git diff --check`

本计划是 `docs/CLI双MCP多Agent选品技术方案.md` 的 P0 实施台账。P0 只冻结契约和校验规则，不进入 P1 双 Agent 市场快验实现。

## 验收清单

- [x] P0-1 固化 MCP smoke call 输出样例
  - 状态：已完成；卖家精灵 `product_node` 与 Sorftime `keyword_detail` 最小真实调用已跑通，通用样例只保留字段形状
  - 验收：卖家精灵 MCP、Sorftime MCP 均有最小真实调用样例，包含工具名、参数、成功结果、空结果、失败/超时/限流格式。
  - 验收依据：`tests/fixtures/p0_contracts/mcp_smoke_call_examples.json`；真实调用不写入通用代码和文档。

- [x] P0-2 编写 MCP snapshot schema
  - 状态：已完成；已补 `mcp_snapshot.schema.json` 与 quick/deep 固定落盘路径约束
  - 验收：定义 quick / deep snapshot schema，覆盖 `mcp_snapshots/sellersprite_quick_snapshot.json`、`sorftime_quick_snapshot.json`、`sellersprite_deep_snapshot.json`、`sorftime_deep_snapshot.json`。
  - 验收依据：`packages/research_core/schemas/mcp_snapshot.schema.json`。

- [x] P0-3 编写 Evidence Packet schema
  - 状态：已完成；已补通用 Evidence Packet、冲突复核与评价汇总契约
  - 验收：quick、deep、conflict、evaluation、integrated judgment 均有 schema；数值型 facts / derived_metrics 明确 `metric_basis`；`evidence_refs` 统一 `path#json_pointer` 格式。
  - 验收依据：`evidence_packet.schema.json`、`quick_packet.schema.json`、`conflict_resolution_packet.schema.json`、`evaluation_summary.schema.json`、`integrated_operator_judgment.schema.json`。

- [x] P0-4 编写 Quick Gate schema 和门控测试
  - 状态：已完成；已补 Quick Packet / Quick Gate schema 与 stop/watch 优先级测试
  - 验收：Quick Packet 包含 `support_level`、`blocking_gaps`、`mixed_pool_level`、`demand_signal_level`、`price_band_health`、`category_boundary_clarity`；门控规则明确 stop 优先于 watch。
  - 验收依据：`packages/research_core/contracts/p0_contracts.py`；`tests/test_p0_contracts.py`。

- [x] P0-5 编写 progress.json 示例和恢复测试
  - 状态：已完成；已补顶层结构示例与 resume_policy 测试
  - 验收：最小示例包含 `current_stage`、`stages.stage_2.status`、`output_artifacts`、`validation_checks`、`next_action`、`completed_artifacts`；恢复测试验证已完成 artifact 不重复调用 MCP。
  - 验收依据：`packages/research_core/schemas/progress.schema.json`；`tests/fixtures/p0_contracts/progress.min.json`；`tests/test_p0_contracts.py`。

- [x] P0-6 修改正式报告契约
  - 状态：已完成；已移除 HTML 固定“数据来源与口径”板块要求并保留后台溯源
  - 验收：`docs/正式报告契约.md` 移除 HTML 固定“数据来源与口径”板块要求，保留“判断口径 / 样本边界”；Excel 和 `report_data.json` 继续保留 source_path 和证据链。
  - 验收依据：`docs/正式报告契约.md`；`tests/test_p0_contracts.py`。

- [x] P0-7 修改 Delivery QA required sections
  - 状态：已完成；已调整 required markers 与新增阻塞项检查
  - 验收：`delivery_qa.py` 不再要求 HTML 固定“数据来源与口径”板块；新增 blocking conflict、data_quality blocked、low confidence、progress 未完成、schema_version 不一致阻塞规则。
  - 验收依据：`packages/research_core/pipeline/delivery_qa.py`；`packages/research_core/pipeline/constants.py`；`tests/test_p0_contracts.py`。

- [x] P0-8 固化 integrated_operator_judgment schema
  - 状态：已完成；已补最终判断 schema 必填字段
  - 验收：schema 覆盖 `final_verdict`、`verdict_reason`、`recommended_route`、`rejected_routes`、`biggest_opportunity`、`biggest_risk`、`required_next_actions`、`constraints_applied`、`evidence_refs`、`confidence`。
  - 验收依据：`packages/research_core/schemas/integrated_operator_judgment.schema.json`。

- [x] P0-9 明确 build_analysis_report.py 职责
  - 状态：已完成；已将 seed 输出从 `report_data.json` 拆到 `report_data.seed.json`
  - 验收：脚本只负责生成 `report_data.seed.json`、基于 `report_data.json` 生成 XLSX、运行 QA；不负责手写正式 HTML；如保留旧占位 HTML 必须标记 `draft`。
  - 验收依据：`packages/research_core/pipeline/build_analysis_report.py`；`tests/test_p0_contracts.py`。

- [x] P0-10 决定 scripts/build_fused_candidate_pool.py 去留
  - 状态：已完成；决策为废弃为历史原型，不吸收、不重命名为 MCP 主入口
  - 验收：明确吸收到 `scripts/build_mcp_candidate_pool.py`、重命名为 MCP 主入口，或废弃；未去除品类/样例硬编码前不得作为通用主链路。
  - 验收依据：`docs/CLI双MCP多Agent选品技术方案.md`；P2 新建通用 `scripts/build_mcp_candidate_pool.py`，不得依赖该脚本硬编码逻辑。

- [x] P0-11 同步 Skill / Agent / 报告设计参考旧口径
  - 状态：已完成；已同步 Stage 7 三段式、HTML required sections、Delivery QA 阻塞规则和 legacy renderer 说明
  - 验收：Skill、Delivery QA Agent、报告设计参考、report_renderer 旧常量与 P0 新契约一致，不进入 P1 实现。
  - 验收依据：`skills/amazon-product-research/SKILL.md`、`skills/amazon-product-research/agents/delivery-qa-agent.md`、`skills/amazon-product-research/references/report_design_spec.md`、`packages/report_renderer/constants.py`。
  - 验证命令：`python3 -m unittest tests.test_p0_contracts -v`、`python3 -m unittest discover -v`、`python3 scripts/check_generic_redlines.py --token-file tests/fixtures/generic_redline_tokens.json --no-auto-run-dir`、`git diff --check`。

- [x] P0-12 深扫 Agent / Reference 旧报告口径
  - 状态：已完成；已清理报告生成 Agent、产物契约和报告质量样例中的旧 Stage 7 固定板块描述
  - 验收：3 个深层参考文件与 P0 三段式报告契约一致，不进入 P1 实现。
  - 验收依据：`skills/amazon-product-research/agents/report-generation-agent.md`、`skills/amazon-product-research/references/artifact_contract.md`、`skills/amazon-product-research/references/report_quality_sample.md`。
  - 验证命令：`python3 -m unittest tests.test_p0_contracts -v`、`python3 -m unittest discover -v`、`python3 scripts/check_generic_redlines.py --token-file tests/fixtures/generic_redline_tokens.json --no-auto-run-dir`、`git diff --check`。

## P0 出口条件

- [x] 所有 P0 项完成并有验收依据。
- [x] 通用红线扫描通过。
  - 验收依据：`python3 scripts/check_generic_redlines.py --token-file tests/fixtures/generic_redline_tokens.json --no-auto-run-dir`
- [x] `git diff --check` 通过。
- [x] 方案、契约、QA、计划文件对 P1 的输入/输出没有冲突。
  - 验收依据：`python3 -m unittest discover -v`、`python3 -m unittest tests.test_p0_contracts -v`
