# CLI 双 MCP 多 Agent 选品 P2 候选池实施计划

状态：P2 已完成；只实现 MCP 候选池最小可运行链路，不进入 P3 路线矩阵和双 MCP 深挖。

本计划是 P2 唯一进度台账。P2 只消费 P1 quick 产物，输出 `candidate_pool.json` 和 `progress.json` 的 stage_4 状态。

## 范围边界

- 只处理 `runs/<run_id>/candidate_pool.json` 与 `runs/<run_id>/progress.json`。
- 不生成 `route_matrix_confirm.json`。
- 不调用正式 deep MCP。
- 不生成 market_structure / search_demand deep evidence packet。
- 不生成 VOC、评价、报告。
- 不改 Web / server 主链路。
- 不依赖 `scripts/build_fused_candidate_pool.py` 的硬编码样例逻辑。
- 不写死任何具体品类、ASIN、关键词、价格、品牌、卖家或供应商。

## 验收清单

- [x] P2-1 固化 P2 输入输出契约
  - 状态：已完成；P2 只消费 workflow_state + 双 quick packet + quick gate，输出只保留 candidate_pool.json 与 progress.json 的 stage_4 状态。
  - 验收：P2 输入来自 workflow_state + 双 quick packet + quick gate；P2 输出只含 candidate_pool.json 与 progress.json 更新。
  - 验收依据：`docs/CLI双MCP多Agent选品技术方案.md`、`packages/research_core/pipeline/build_mcp_candidate_pool.py`、`scripts/build_mcp_candidate_pool.py`、`tests/test_p2_mcp_candidate_pool.py`。

- [x] P2-2 实现 MCP 候选池构建模块
  - 状态：已完成；新增通用入口，可从 quick gate / quick packet 构建候选池，不依赖 `scripts/build_fused_candidate_pool.py`。
  - 验收：新增通用入口，可从 quick gate / quick packet 构建候选池，不依赖 `scripts/build_fused_candidate_pool.py`。
  - 验收依据：`packages/research_core/pipeline/build_mcp_candidate_pool.py`、`tests/test_p2_mcp_candidate_pool.py`。

- [x] P2-3 新增 CLI 薄壳
  - 状态：已完成；`scripts/build_mcp_candidate_pool.py` 仅调用通用入口并支持 run 目录执行。
  - 验收：`scripts/build_mcp_candidate_pool.py` 调用通用入口并支持 run 目录执行。
  - 验收依据：`scripts/build_mcp_candidate_pool.py`、`python3 -m unittest tests.test_p2_mcp_candidate_pool -v`。

- [x] P2-4 更新 candidate_pool schema
  - 状态：已完成；现有 `candidate_pool.schema.json` 已可兼容 P2 候选池输出，未破坏旧测试，通用逻辑按现有 schema 运行。
  - 验收：schema 向后兼容扩展，能表达 P2 候选池字段且不破坏旧测试。
  - 验收依据：`packages/research_core/schemas/candidate_pool.schema.json`、`packages/research_core/contracts/validators.py`、`python3 -m unittest tests.test_regression -v`。

- [x] P2-5 更新 progress.json
  - 状态：已完成；stage_4_candidate_pool 按 quick gate 结果落成 done / needs_user / blocked / failed。
  - 验收：stage_4_candidate_pool 根据 quick gate 结果落成 done / needs_user / blocked / failed。
  - 验收依据：`packages/research_core/pipeline/build_mcp_candidate_pool.py`、`tests/test_p2_mcp_candidate_pool.py`。

- [x] P2-6 补充 P2 测试
  - 状态：已完成；覆盖 continue / watch / stop、schema 失败、candidate_pool 不进入 P3、evidence_refs 溯源、progress 状态。
  - 验收：覆盖 continue / watch / stop、schema 失败、candidate_pool 不进入 P3、evidence_refs 溯源、progress 状态。
  - 验收依据：`tests/test_p2_mcp_candidate_pool.py`、`python3 -m unittest tests.test_p2_mcp_candidate_pool -v`。

- [x] P2-7 完成 P2 验证
  - 状态：已完成；基础回归、红线扫描和 diff 检查全部通过。
  - 验收命令：`python3 -m unittest tests.test_p0_contracts -v`、`python3 -m unittest tests.test_p1_quick_market_check -v`、`python3 -m unittest tests.test_p2_mcp_candidate_pool -v`、`python3 -m unittest discover -v`、`python3 scripts/check_generic_redlines.py --token-file tests/fixtures/generic_redline_tokens.json --no-auto-run-dir`、`git diff --check`。
  - 结果：全部通过；`python3 -m unittest discover -v` 共 94 项通过（skipped=3），`generic_redline: OK`，`git diff --check` 无输出。
