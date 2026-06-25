# CLI 双 MCP 多 Agent 选品 P1 市场快验实施计划

状态：P1 已完成；已实现双 Agent 市场快验最小可运行链路，不进入 P2 候选池主流程。

本计划是 P1 唯一进度台账。P1 读取 P0 冻结契约，输出双 quick snapshot、双 quick evidence packet、`quick_market_gate.json` 和 `progress.json` 阶段状态。

## 范围边界

- 只处理 `runs/<run_id>/mcp_snapshots/`、`runs/<run_id>/quick_check/`、`runs/<run_id>/progress.json`。
- 不生成 `candidate_pool.json`。
- 不生成正式报告。
- 不修改 Web / server 主链路。
- 不写死任何具体品类、ASIN、关键词、价格、品牌、卖家或供应商。

## 验收清单

- [x] P1-1 固化 P1 输入输出契约
  - 状态：已完成；P1 仅读取 `workflow_state.json` 和 quick snapshot，输出双 snapshot、双 quick packet、quick gate、progress，不生成 P2 产物
  - 验收：P1 输入/输出与 P0 schema 一致，且不包含 P2 产物。
  - 验收依据：`packages/research_core/pipeline/quick_market_check.py`、`scripts/run_quick_market_check.py`。

- [x] P1-2 实现 quick snapshot 读取 / 生成入口
  - 状态：已完成；支持 run 目录已有 snapshot 和 `--snapshot-source-dir` fixture / sample snapshot 复制模式
  - 验收：支持已有真实 MCP snapshot 文件模式和 fixture / sample snapshot 模式，输出符合 `mcp_snapshot.schema.json`。
  - 验收依据：`packages/research_core/pipeline/quick_market_check.py`、`tests/fixtures/p1_quick_check/*.json`、`tests/test_p1_quick_market_check.py`。

- [x] P1-3 实现 SellerSprite Quick Packet 构建
  - 状态：已完成；可从 `sellersprite_quick_snapshot.json` 生成 SellerSprite quick evidence packet
  - 验收：`sellersprite_quick_snapshot.json` 可转换为 `quick_check/sellersprite_quick_evidence_packet.json`，满足 `quick_packet.schema.json`。
  - 验收依据：`build_quick_packet()`；`test_sellersprite_quick_snapshot_builds_quick_packet`。

- [x] P1-4 实现 Sorftime Quick Packet 构建
  - 状态：已完成；可从 `sorftime_quick_snapshot.json` 生成 Sorftime quick evidence packet
  - 验收：`sorftime_quick_snapshot.json` 可转换为 `quick_check/sorftime_quick_evidence_packet.json`，满足 `quick_packet.schema.json`。
  - 验收依据：`build_quick_packet()`；`test_sorftime_quick_snapshot_builds_quick_packet`。

- [x] P1-5 实现 Quick Gate
  - 状态：已完成；Quick Gate 复用 P0 冻结规则并写入 `quick_market_gate.json`
  - 验收：复用 `packages/research_core/contracts/p0_contracts.py::decide_quick_gate`，生成 `quick_check/quick_market_gate.json`。
  - 验收依据：`build_quick_market_gate()`；`test_quick_gate_watch_when_material_mixed_pool`、`test_quick_gate_stop_when_blocking_gaps_exist`。

- [x] P1-6 更新 progress.json
  - 状态：已完成；成功链路写入 done，schema 失败链路写入 failed 且不进入 done
  - 验收：P1 每个关键节点写入状态、产物、校验结果、next_action；失败时不进入 done。
  - 验收依据：`build_success_progress()`、`_write_failure_progress()`；`test_schema_failure_writes_failed_progress_and_does_not_mark_done`。

- [x] P1-7 补充 P1 测试
  - 状态：已完成；新增 P1 专项测试覆盖最小链路和失败分支
  - 验收：覆盖 snapshot -> quick packet、quick gate continue/watch/stop、blocking 优先级、progress done/failed、schema 失败不 done。
  - 验收依据：`tests/test_p1_quick_market_check.py`；`python3 -m unittest tests.test_p1_quick_market_check -v` 通过。

- [x] P1-8 完成 P1 验证
  - 状态：已完成；P0 专项、全量 unittest、通用红线扫描和 diff 检查均通过
  - 验收命令：`python3 -m unittest tests.test_p0_contracts -v`、`python3 -m unittest discover -v`、`python3 scripts/check_generic_redlines.py --token-file tests/fixtures/generic_redline_tokens.json --no-auto-run-dir`、`git diff --check`。
  - 验收依据：P0 专项 11 tests OK；全量 unittest 89 tests OK, skipped=3；generic_redline: OK；`git diff --check` 无输出。
