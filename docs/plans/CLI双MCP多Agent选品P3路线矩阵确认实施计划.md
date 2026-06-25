# CLI 双 MCP 多 Agent 选品 P3 路线矩阵确认实施计划

状态：P3 已完成；已实现路线矩阵确认与数据完整性检查，不进入双 MCP 深挖和正式 VOC。

本计划是 P3 唯一进度台账。P3 只消费 `candidate_pool.json`，输出 `route_matrix_confirm.json`、`data_completeness_check.json` 和 `progress.json` 的 stage_5 状态。

## 范围边界

- 只处理 `runs/<run_id>/candidate_pool.json`、`runs/<run_id>/route_matrix_confirm.json`、`runs/<run_id>/data_completeness_check.json` 和 `runs/<run_id>/progress.json`。
- 不生成正式 deep MCP evidence packet。
- 不生成完整 VOC 正式产物。
- 不生成多评价产物。
- 不生成正式报告。
- 不改 Web / server 主链路。
- 不写死任何具体品类、ASIN、关键词、价格、品牌、卖家或供应商。

## 验收清单

- [x] P3-1 固化 P3 输入输出契约
  - 状态：已完成；P3 读取 `candidate_pool.json`，输出 `route_matrix_confirm.json`、`data_completeness_check.json` 和 `progress.json` 的 stage_5 状态。
  - 验收：P3 只基于 candidate_pool 生成路线矩阵确认，不进入 P4/P5/P6/P7。
  - 补充验收：缺少 `candidate_pool.json` 时直接标记 P3 failed，不再兼容 legacy route matrix fallback。
  - 验收依据：`docs/CLI双MCP多Agent选品技术方案.md`、`packages/research_core/pipeline/build_route_matrix_confirmation.py`、`scripts/build_route_matrix_confirm.py`、`tests/test_p3_route_matrix_confirm.py`。

- [x] P3-2 实现数据完整性检查
  - 状态：已完成；已生成 `data_completeness_check.json`，并区分 blocker / warning / acceptable。
  - 验收：生成 `data_completeness_check.json`，并能把 blocker / warning / acceptable 写清楚。
  - 验收依据：`packages/research_core/pipeline/build_route_matrix_confirmation.py`、`tests/test_p3_route_matrix_confirm.py`。

- [x] P3-3 实现路线矩阵确认
  - 状态：已完成；已输出 `selected_routes` / `rejected_routes` / `decision` / `voc_readiness` / `required_next_actions`。
  - 验收：decision 能在 confirm / revise_candidate_pool / stop 之间稳定切换。
  - 验收依据：`packages/research_core/pipeline/build_route_matrix_confirmation.py`、`tests/test_p3_route_matrix_confirm.py`。

- [x] P3-4 更新 progress.json
  - 状态：已完成；stage_4_candidate_pool 与 stage_5_route_matrix 已按回退规则回写。
  - 验收：decision=revise_candidate_pool 时不进入深挖，stage_4 / stage_5 状态正确。
  - 验收依据：`packages/research_core/pipeline/build_route_matrix_confirmation.py`、`tests/test_p3_route_matrix_confirm.py`。

- [x] P3-5 补充 P3 测试
  - 状态：已完成；覆盖 confirm / revise_candidate_pool / stop / blocker / voc_readiness。
  - 验收：新增测试覆盖 P3 最小链路及失败分支。
  - 验收依据：`tests/test_p3_route_matrix_confirm.py`、`python3 -m unittest tests.test_p3_route_matrix_confirm -v`。

- [x] P3-6 完成 P3 验证
  - 状态：已完成；P0/P1/P2 回归、P3 专项、全量 unittest、红线扫描和 diff 检查均通过。
  - 验收命令：`python3 -m unittest tests.test_p0_contracts -v`、`python3 -m unittest tests.test_p1_quick_market_check -v`、`python3 -m unittest tests.test_p2_mcp_candidate_pool -v`、`python3 -m unittest tests.test_p3_route_matrix_confirm -v`、`python3 -m unittest discover -v`、`python3 scripts/check_generic_redlines.py --token-file tests/fixtures/generic_redline_tokens.json --no-auto-run-dir`、`git diff --check`。
  - 结果：全部通过；`python3 -m unittest discover -v` 共 99 项通过（skipped=3），`generic_redline: OK`，`git diff --check` 无输出。
