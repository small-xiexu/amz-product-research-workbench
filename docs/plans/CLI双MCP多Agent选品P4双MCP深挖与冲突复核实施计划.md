# CLI 双 MCP 多 Agent 选品 P4 双 MCP 深挖与冲突复核实施计划

状态：P4-0 / P4-0a / P4-0b / P4-1 已完成；P4-1 仅固化双 MCP 深挖契约与 schema，不进入 P4 正式深挖实现。

本计划是 P4 唯一进度台账。P4 必须基于 P0/P1/P2/P3 已完成契约与产物继续推进，先完成工具能力边界、字段映射、metric_basis 和 conflict_resolution_packet 比较范围确认，再等待确认进入实现。

## 范围边界

- P4 输入来自 `runs/<run_id>/route_matrix_confirm.json`、`runs/<run_id>/data_completeness_check.json`、`runs/<run_id>/candidate_pool.json` 和上游 quick evidence packets。
- P4 正式实现时才生成 `mcp_snapshots/sellersprite_deep_snapshot.json`、`mcp_snapshots/sorftime_deep_snapshot.json`、`market_structure/market_structure_evidence_packet.json`、`search_demand/search_demand_evidence_packet.json` 和 `conflict_review/conflict_resolution_packet.json`。
- P4-0 只做最小样本真实 MCP 能力烟测与契约映射，烟测样本只写入 `runs/<run_id>/mcp_probe/`，不作为选品结论。
- 不进入 VOC、评价 Agent、资深运营专家判断或正式报告。
- 不改 Web / server 主链路。
- 不写死任何具体品类、ASIN、关键词、价格、品牌、卖家或供应商。

## 验收清单

- [x] P4-0 SellerSprite / Sorftime MCP 真实能力烟测与字段映射
  - 状态：已完成；已完成最小真实 smoke，已创建临时 run 并记录双 MCP 原始返回、字段摘要和失败原因。
  - 目标：产出 `runs/<run_id>/mcp_probe/sellersprite_probe_raw.json`、`runs/<run_id>/mcp_probe/sorftime_probe_raw.json`、`runs/<run_id>/mcp_probe/mcp_probe_summary.json`、`docs/references/p4_mcp_capability_mapping.md`。
  - 验收依据：`runs/20260624_p4_mcp_probe/mcp_probe/sellersprite_probe_raw.json`、`runs/20260624_p4_mcp_probe/mcp_probe/sorftime_probe_raw.json`、`runs/20260624_p4_mcp_probe/mcp_probe/mcp_probe_summary.json`、`docs/references/p4_mcp_capability_mapping.md`。
  - 验证命令：`python3 -m json.tool runs/20260624_p4_mcp_probe/mcp_probe/sellersprite_probe_raw.json`、`python3 -m json.tool runs/20260624_p4_mcp_probe/mcp_probe/sorftime_probe_raw.json`、`python3 -m json.tool runs/20260624_p4_mcp_probe/mcp_probe/mcp_probe_summary.json`、`python3 scripts/check_generic_redlines.py --token-file tests/fixtures/generic_redline_tokens.json --no-auto-run-dir`、`git diff --check`。
  - 结果：全部通过；红线扫描输出 `generic_redline: OK`，`git diff --check` 无输出。

- [x] P4-0a 双 MCP 文档对齐 + 最小字段烟测复核
  - 状态：已完成；已读取 P4 技术方案、SellerSprite MCP 工具参考、Sorftime MCP 工具调用策略和 P3 计划，已同步 `docs/references/p4_mcp_capability_mapping.md` 与 `mcp_probe_summary.json`。
  - 目标：按最新 P4-0 要求补齐 SellerSprite / Sorftime 工具能力分组、推荐主责、双源交叉验证字段、单源字段、metric_basis、冲突可比较 / 不可比较清单和正式实现建议。
  - 验收依据：`docs/references/p4_mcp_capability_mapping.md`、`runs/20260624_p4_mcp_probe/mcp_probe/sellersprite_probe_raw.json`、`runs/20260624_p4_mcp_probe/mcp_probe/sorftime_probe_raw.json`、`runs/20260624_p4_mcp_probe/mcp_probe/mcp_probe_summary.json`。
  - 验证命令：`python3 -m json.tool runs/20260624_p4_mcp_probe/mcp_probe/sellersprite_probe_raw.json`、`python3 -m json.tool runs/20260624_p4_mcp_probe/mcp_probe/sorftime_probe_raw.json`、`python3 -m json.tool runs/20260624_p4_mcp_probe/mcp_probe/mcp_probe_summary.json`、`python3 scripts/check_generic_redlines.py --token-file tests/fixtures/generic_redline_tokens.json --no-auto-run-dir`、`git diff --check`。
  - 结果：全部通过；红线扫描输出 `generic_redline: OK`，`git diff --check` 无输出。

- [x] P4-0b 重新执行双 MCP 最小字段烟测
  - 状态：已完成；已重新用独立 run 复测 SellerSprite / Sorftime 代表工具字段，并已合并网络切换后 SellerSprite 关键工具补充复测结果。
  - 目标：产出 `runs/20260624_p4_0b_mcp_probe/mcp_probe/sellersprite_probe_raw.json`、`runs/20260624_p4_0b_mcp_probe/mcp_probe/sorftime_probe_raw.json`、`runs/20260624_p4_0b_mcp_probe/mcp_probe/mcp_probe_summary.json`，并按结果更新 `docs/references/p4_mcp_capability_mapping.md`。
  - 验收依据：`runs/20260624_p4_0b_mcp_probe/mcp_probe/sellersprite_probe_raw.json`、`runs/20260624_p4_0b_mcp_probe/mcp_probe/sorftime_probe_raw.json`、`runs/20260624_p4_0b_mcp_probe/mcp_probe/mcp_probe_summary.json`、`docs/references/p4_mcp_capability_mapping.md`。
  - 验证命令：`python3 -m json.tool runs/20260624_p4_0b_mcp_probe/mcp_probe/sellersprite_probe_raw.json`、`python3 -m json.tool runs/20260624_p4_0b_mcp_probe/mcp_probe/sorftime_probe_raw.json`、`python3 -m json.tool runs/20260624_p4_0b_mcp_probe/mcp_probe/mcp_probe_summary.json`、`python3 scripts/check_generic_redlines.py --token-file tests/fixtures/generic_redline_tokens.json --no-auto-run-dir`、`git diff --check`。
  - 结果：全部通过；红线扫描输出 `generic_redline: OK`，`git diff --check` 无输出。

- [x] P4-0b 补充：SellerSprite 网络切换后关键工具复测回写
  - 状态：已完成；已重新调用 SellerSprite 关键工具，并回写同一个 P4-0b run artifact、能力映射文档和验收命令。
  - 范围：只同步 P4-0b 烟测结论，不新增 P4-0c，不进入正式 P4 深挖实现。
  - 验收依据：`runs/20260624_p4_0b_mcp_probe/mcp_probe/sellersprite_probe_raw.json`、`runs/20260624_p4_0b_mcp_probe/mcp_probe/mcp_probe_summary.json`、`docs/references/p4_mcp_capability_mapping.md`。
  - 验证命令：`python3 -m json.tool runs/20260624_p4_0b_mcp_probe/mcp_probe/sellersprite_probe_raw.json`、`python3 -m json.tool runs/20260624_p4_0b_mcp_probe/mcp_probe/sorftime_probe_raw.json`、`python3 -m json.tool runs/20260624_p4_0b_mcp_probe/mcp_probe/mcp_probe_summary.json`、`python3 scripts/check_generic_redlines.py --token-file tests/fixtures/generic_redline_tokens.json --no-auto-run-dir`、`python3 scripts/check_generic_redlines.py --run-dir runs/20260624_p4_0b_mcp_probe`、`git diff --check`。
  - 结果：全部通过；红线扫描输出 `generic_redline: OK`，`git diff --check` 无输出。

- [x] P4-1 固化 P4 deep snapshot 输入输出契约
  - 状态：已完成；已补 P4 正式 deep snapshot、P4 evidence packet、deep completeness、conflict resolution、preconditions、metric_basis 可比较性与 stage_6 progress 契约。
  - 契约与 validator：`packages/research_core/contracts/p4_contracts.py`、`packages/research_core/contracts/__init__.py`。
  - Schema：`packages/research_core/schemas/p4_deep_snapshot.schema.json`、`packages/research_core/schemas/p4_evidence_packet.schema.json`、`packages/research_core/schemas/deep_data_completeness_check.schema.json`、`packages/research_core/schemas/conflict_resolution_packet.schema.json`。
  - 测试：`tests/test_p4_contracts.py`。
  - 验证命令：`python3 -m unittest tests.test_p4_contracts -v`、`python3 -m unittest tests.test_p0_contracts tests.test_p1_quick_market_check tests.test_p2_mcp_candidate_pool tests.test_p3_route_matrix_confirm -v`、`python3 -m unittest discover -v`、`python3 scripts/check_generic_redlines.py --token-file tests/fixtures/generic_redline_tokens.json --no-auto-run-dir`、`git diff --check`。
  - 结果：全部通过；`unittest discover` 通过 112 个测试、跳过 3 个既有条件测试；红线扫描输出 `generic_redline: OK`，`git diff --check` 无输出。

- [x] P4-2 实现 SellerSprite Market Structure 深挖链路
  - 状态：已完成；已实现 SellerSprite deep snapshot 复用 / probe 归一化、market_structure evidence packet 生成、stage_6_deep_dive 进度更新与 P4-2 测试。
  - 新增 pipeline：`packages/research_core/pipeline/build_sellersprite_deep_dive.py`
  - 新增 CLI：`scripts/build_sellersprite_deep_dive.py`
  - 新增测试：`tests/test_p4_sellersprite_deep_dive.py`
  - 验收依据：`runs/<run_id>/mcp_snapshots/sellersprite_deep_snapshot.json`、`runs/<run_id>/market_structure/market_structure_evidence_packet.json`、`runs/<run_id>/progress.json`
  - 验证命令：`python3 -m unittest tests.test_p4_sellersprite_deep_dive -v`、`python3 -m unittest tests.test_p4_contracts -v`、`python3 -m unittest tests.test_p0_contracts tests.test_p1_quick_market_check tests.test_p2_mcp_candidate_pool tests.test_p3_route_matrix_confirm -v`、`python3 -m unittest discover -v`、`python3 scripts/check_generic_redlines.py --token-file tests/fixtures/generic_redline_tokens.json --no-auto-run-dir`、`git diff --check`
  - 结果：全部通过；全量 `unittest discover` 通过 121 个测试、跳过 3 个既有条件测试；红线扫描输出 `generic_redline: OK`，`git diff --check` 无输出。

- [x] P4-3 实现 Sorftime Search Demand 深挖链路
  - 状态：已完成；已实现 Sorftime deep snapshot 复用 / probe 归一化、search_demand evidence packet 生成、stage_6_deep_dive 进度更新与 P4-3 测试。
  - 新增 pipeline：`packages/research_core/pipeline/build_sorftime_deep_dive.py`
  - 新增 CLI：`scripts/build_sorftime_deep_dive.py`
  - 新增测试：`tests/test_p4_sorftime_deep_dive.py`
  - 验收依据：`runs/<run_id>/mcp_snapshots/sorftime_deep_snapshot.json`、`runs/<run_id>/search_demand/search_demand_evidence_packet.json`、`runs/<run_id>/progress.json`
  - 验证命令：`python3 -m unittest tests.test_p4_sorftime_deep_dive -v`、`python3 -m unittest tests.test_p4_contracts -v`、`python3 -m unittest tests.test_p0_contracts tests.test_p1_quick_market_check tests.test_p2_mcp_candidate_pool tests.test_p3_route_matrix_confirm -v`、`python3 -m unittest discover -v`、`python3 scripts/check_generic_redlines.py --token-file tests/fixtures/generic_redline_tokens.json --no-auto-run-dir`、`git diff --check`
  - 结果：全部通过；全量 `unittest discover` 通过 130 个测试、跳过 3 个既有条件测试；红线扫描输出 `generic_redline: OK`，`git diff --check` 无输出。

- [x] P4-4 实现数据归一化与冲突复核
  - 状态：已完成；已实现 deep_data_completeness_check 和 conflict_resolution_packet 生成、双源 metric_basis 归一化、冲突判定（blocker/warning/none）、stage_6_deep_dive 完成推进到 stage_7_voc_gate。
  - 新增 pipeline：`packages/research_core/pipeline/build_conflict_review.py`
  - 新增 CLI：`scripts/build_conflict_review.py`
  - 新增测试：`tests/test_p4_conflict_review.py`
  - 验收依据：`runs/<run_id>/conflict_review/deep_data_completeness_check.json`、`runs/<run_id>/conflict_review/conflict_resolution_packet.json`、`runs/<run_id>/progress.json`
  - 验证命令：`python3 -m unittest tests.test_p4_conflict_review -v`、`python3 -m unittest tests.test_p4_contracts -v`、`python3 -m unittest tests.test_p4_sellersprite_deep_dive tests.test_p4_sorftime_deep_dive -v`、`python3 -m unittest tests.test_p0_contracts tests.test_p1_quick_market_check tests.test_p2_mcp_candidate_pool tests.test_p3_route_matrix_confirm -v`、`python3 -m unittest discover -v`、`python3 scripts/check_generic_redlines.py --token-file tests/fixtures/generic_redline_tokens.json --no-auto-run-dir`、`git diff --check`
  - 结果：全部通过；全量 `unittest discover` 通过 140 个测试、跳过 3 个既有条件测试；红线扫描输出 `generic_redline: OK`，`git diff --check` 无输出。

- [x] P4-5 补充 P4 测试与回归验证
  - 状态：已完成；已补充 13 项回归测试（端到端串联 8 项 + CLI smoke 4 项 + 进度链验证、阻断验证、范围验证、契约验证、全局阻断器清理）。
  - 新增测试：`tests/test_p4_regression.py`（P4EndToEndTests 8 项 + P4CliSmokeTests 4 项 + 进度链+artifact 累积+全局阻断器清理验证）。
  - 端到端串联覆盖：P1→P2→P3→P4-2→P4-3→P4-4 全链路 artifact 生成 + progress 链 + contract validator 全覆盖。
  - CLI smoke 覆盖：`scripts/build_sellersprite_deep_dive.py`、`scripts/build_sorftime_deep_dive.py`、`scripts/build_conflict_review.py` 子进程调用，含全链串联 smoke。
  - 阻断覆盖：缺失 SS snapshot 阻断 P4-2、缺失 SF snapshot 阻断 P4-3、缺失 evidence packet 阻断 P4-4，均不标 stage_6 done。
  - 范围验证：全链路不产生 review_voc、evaluations、report_data.json、HTML、XLSX。
  - 验证命令：`python3 -m unittest tests.test_p4_regression -v`、`python3 -m unittest discover -v`、`python3 scripts/check_generic_redlines.py --token-file tests/fixtures/generic_redline_tokens.json --no-auto-run-dir`、`git diff --check`。
  - 结果：全部通过；全量 `unittest discover` 通过 153 个测试、跳过 3 个既有条件测试；红线扫描输出 `generic_redline: OK`，`git diff --check` 无输出。
