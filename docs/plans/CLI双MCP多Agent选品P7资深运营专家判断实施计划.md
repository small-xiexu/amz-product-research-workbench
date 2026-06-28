# CLI 双 MCP 多 Agent 选品 P7 资深运营专家判断 实施计划

状态：历史计划已完成；当前主线已修正为“脚本只生成 judgment skeleton，最终判断由 Lead Operator Agent 完成”。

本计划记录早期 P7 实施。现状以 `skills/amazon-product-research/SKILL.md` 和 `agents/lead-operator-agent.md` 为准：`build_integrated_judgment.py` 只准备结构与证据 lineage，不替代资深运营专家判断。

## 范围边界

- P7 输入来自 P6 的 7 个产物（6 evaluation + 1 evaluation_summary）
- P7 产出 1 个核心文件：`integrated_operator_judgment.json`
- 不直接输出 HTML、XLSX（这些由 AI Report Generation Agent 基于 report_data.seed 增强后，再由脚本回写）
- 不改 web/server 主链路
- 不写死任何具体品类、ASIN、关键词、品牌、卖家、价格
- 脚本不得做最终判断；`final_verdict`、最大机会、最大风险和下一步策略由 Lead Operator Agent 写入
- 脚本骨架的 `execution_provenance.execution_mode` 标记为 `script_generated_skeleton`

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
  - 当前主线修正：已移除脚本 `_determine_verdict` 等拍板逻辑；P7 脚本只生成骨架
  - 推荐路线：从 route_matrix_confirm.json 的 selected_routes 提取主线
  - 最大机会/风险：从最高/最低分维度提取
  - 置信度：综合 low_confidence_dimensions 和 high 维度数量

- [x] P7-3 CLI 入口
  - 状态：已完成
  - 新增 CLI：`scripts/build_integrated_judgment.py`
  - 用法：`python3 scripts/build_integrated_judgment.py <run_dir>`
  - 前置检查：evaluations/ 和 evaluation_summary.json 必须存在
  - 输出后不宣称最终判断完成；`validate_judgment.py --check-verdict` 会拦截未由 Lead Operator Agent 填完的 skeleton

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
  - 当前主线修正：回归测试验证脚本 skeleton 不会应用 P6 verdict range，不会提取最大机会/风险
  - Progress flow: Stage 9 保持 running，`completed_artifacts` 不把 skeleton 当最终 judgment
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
