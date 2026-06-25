# CLI 双 MCP 多 Agent 选品 P7 资深运营专家判断 实施计划

状态：P7 全部完成。

本计划是 P7 唯一进度台账。P7 基于 P6 的 6 维评价 + evaluation_summary，生成 deterministic integrated_operator_judgment，作为资深运营专家判断的脚本化替代。

## 范围边界

- P7 输入来自 P6 的 7 个产物（6 evaluation + 1 evaluation_summary）
- P7 产出 1 个核心文件：`integrated_operator_judgment.json`
- 不直接输出 HTML、XLSX（这些由 AI Report Generation Agent 基于 report_data.seed 增强后，再由脚本回写）
- 不改 web/server 主链路
- 不写死任何具体品类、ASIN、关键词、品牌、卖家、价格
- 判断逻辑完全 deterministic，不依赖 Agent/MCP 调用
- execution_provenance 诚实标记为 serial_fallback

## 验收清单

- [x] P7-0 Schema 设计
  - 状态：已完成
  - 更新 schema：`packages/research_core/schemas/integrated_operator_judgment.schema.json`
  - 添加 required 字段：execution_provenance, run_id, generated_at
  - evidence_refs 改为 string array（与 P6 一致）

- [x] P7-1 契约定义
  - 状态：已完成
  - 新增 contract：`packages/research_core/contracts/p7_contracts.py`
  - 定义 stage id：`stage_9_report`，schema version：`p7-judgment-v1`
  - 导出 `validate_integrated_judgment`
  - 常量：`P7_ALLOWED_VERDICTS`, `P7_ALLOWED_CONFIDENCE`

- [x] P7-2 Pipeline 核心实现
  - 状态：已完成
  - 新增 pipeline：`packages/research_core/pipeline/build_integrated_judgment.py`
  - `build_integrated_judgment(run_dir)` — 纯函数，返回 judgment dict
  - `run_integrated_judgment(run_dir)` — 写入文件 + 更新 progress
  - `update_progress(run_dir, judgment)` — progress.json 更新
  - 判断逻辑：`_determine_verdict` 从 evaluation_summary 的 recommended_final_verdict_range 出发，结合各维度 strong/watch 数量做确定性推导
  - 推荐路线：从 route_matrix_confirm.json 的 selected_routes 提取主线
  - 最大机会/风险：从最高/最低分维度提取
  - 置信度：综合 low_confidence_dimensions 和 high 维度数量

- [x] P7-3 CLI 入口
  - 状态：已完成
  - 新增 CLI：`scripts/build_integrated_judgment.py`
  - 用法：`python3 scripts/build_integrated_judgment.py <run_dir>`
  - 前置检查：evaluations/ 和 evaluation_summary.json 必须存在
  - 输出后自动 validate

- [x] P7-4 合约测试
  - 状态：已完成
  - 新增测试：`tests/test_p7_contracts.py`（28 项）
  - Valid judgment: 5 tests（go/watch/no_go/blocked/all confidence）
  - String route: 1 test
  - Error cases: 14 tests（wrong schema/packet/stage/verdict/confidence, missing fields, empty arrays, provenance）
  - Verdict boundary: 4 tests
  - Verdict reason: 4 tests

- [x] P7-5 回归测试
  - 状态：已完成
  - 新增测试：`tests/test_p7_regression.py`（26 项）
  - E2E: 14 tests（output exists, contract pass, valid verdict/confidence/reason/route/next_actions/constraints/evidence_refs, provenance, verdict in range, opportunity, risk）
  - Progress flow: 3 tests（stage_9 done, completed_artifacts, next_action ai_step）
  - Error/missing: 2 tests（missing evaluations dir, missing route_matrix）
  - Scope boundaries: 3 tests（no HTML, no XLSX, deterministic）
  - CLI smoke: 4 tests（help, nonexistent, success, no evaluations dir）
  - Full chain: 1 test（P6→P7 full integration）

## 验证结果

P7 全量：54 个测试通过（28 合约 + 26 回归）
全量 `unittest discover`：350 个测试通过（skipped=3）

```bash
python3 -m unittest tests.test_p7_contracts tests.test_p7_regression -v  → 54 OK
python3 -m unittest discover -v                                         → 350 OK (skipped=3)
python3 scripts/check_generic_redlines.py --token-file tests/fixtures/generic_redline_tokens.json --no-auto-run-dir → generic_redline: OK
git diff --check                                                        → 无输出
```

## 文件清单

### 新增 Pipeline（1 个）
- `packages/research_core/pipeline/build_integrated_judgment.py`

### 新增契约（1 个）
- `packages/research_core/contracts/p7_contracts.py`

### 新增 CLI（1 个）
- `scripts/build_integrated_judgment.py`

### 新增测试（2 个）
- `tests/test_p7_contracts.py`（28 tests）
- `tests/test_p7_regression.py`（26 tests）

### 修改文件（2 个）
- `packages/research_core/contracts/__init__.py` — 导出 P7 符号
- `packages/research_core/schemas/integrated_operator_judgment.schema.json` — 完善 schema

## 判断规则总览

| 规则 | 条件 | 结果 |
|---|---|---|
| blocked 传导 | evaluation_summary 推荐范围含 "blocked" | final_verdict = "blocked" |
| go 传导 | 范围含 "go"，核心维度无 blocked，≥4 strong | final_verdict = "go" |
| watch 传导 | 范围含 "go" 但 strong < 4 | final_verdict = "watch" |
| watch 传导 | 范围仅 ["watch", "no_go"]，≥3 strong+watch | final_verdict = "watch" |
| no_go 传导 | 范围仅 ["watch", "no_go"]，strong+watch < 3 | final_verdict = "no_go" |
| 置信度 downgrade | ≥3 low confidence | confidence = "low" |
| 置信度 downgrade | 核心维度 blocked 或 low confidence | confidence = "medium" |
| 推荐路线 | route_matrix selected_routes 中 role=mainline | recommended_route |
| 最大机会 | 最高分 dimension | biggest_opportunity |
| 最大风险 | blocked > 最低分 dimension | biggest_risk |
