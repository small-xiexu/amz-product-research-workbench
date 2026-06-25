# CLI 双 MCP 多 Agent 选品 P6 多评价 Agent 实施计划

状态：P6 全部完成。

本计划是 P6 唯一进度台账。P6 基于 P4 双 MCP 深挖证据包 + P5 VOC 证据包，拆成 6 个可验证的分项评价文件，并汇总成 1 个约束型 evaluation_summary，供 P7 资深运营专家判断使用。

## 范围边界

- P6 输入来自 P4 和 P5 的 8 个上游产物
- P6 产出 7 个文件：6 个分项评价 + 1 个 evaluation_summary
- 不直接输出最终 Go/No-Go
- 不生成 integrated_operator_judgment、HTML、XLSX
- 不改 web/server 主链路
- 不写死任何具体品类、ASIN、关键词、品牌、卖家、价格
- 所有 evaluation 为 serial_fallback，execution_provenance 诚实标记

## 验收清单

- [x] P6-0 Schema 设计与契约定义
  - 状态：已完成
  - 新增 6 个 evaluation schema：market_demand / competition / price_profit / voc_opportunity / risk / data_quality
  - 新增 1 个 contract 模块：`packages/research_core/contracts/p6_contracts.py`
  - 定义 stage id：`stage_8_evaluation`，schema version：`p6-evaluation-v1`
  - 导出 `validate_evaluation_packet`、`validate_evaluation_summary`、`validate_all_evaluations`
  - Schema 路径：`packages/research_core/schemas/{dim}_evaluation.schema.json`

- [x] P6-1 Pipeline 核心实现
  - 状态：已完成
  - 新增 pipeline：`packages/research_core/pipeline/build_evaluation_summary.py`
  - 包含 6 个维度评价函数 + 1 个 summary 聚合函数
  - 每个评价基于上游证据包做确定性数据提取和规则评分
  - 所有 evidence_refs 指向具体 evidence packet 路径
  - 评分逻辑：score = round(hit_signals / total_signals * 100)，rating 从 score 阈值映射（≥70 strong，≥50 watch，≥30 weak，<30 blocked），blocker 条件覆盖
  - evaluation_summary 复用 P0 `summarize_evaluation_constraints` 治理逻辑
  - 跨维度张力检测：VOC 强但市场弱、市场强但竞争/价格 blocked、数据质量 blocked

- [x] P6-2 CLI 入口
  - 状态：已完成
  - 新增 CLI：`scripts/build_evaluation_summary.py`
  - 用法：`python3 scripts/build_evaluation_summary.py <run_dir>`

- [x] P6-3 合约测试
  - 状态：已完成
  - 新增测试：`tests/test_p6_contracts.py`（34 项）
  - Schema 验证：6 维度各 1 测试 + 错误版本/packet_id/score/rating/confidence + 缺失字段/evidence_refs/provenance = 14 tests
  - Summary 验证：有效/缺失维度/缺失字段/错误 packet_id/空 constraints/无效 verdict = 6 tests
  - validate_all_evaluations：全通过/缺失维度/无效 packet = 3 tests
  - Blocked 规则：data_quality blocked / 核心维度 blocked / 辅助维度不 block go = 3 tests
  - Low confidence 规则：tracking / 不 block = 2 tests
  - Rating 覆盖：4 ratings × 6 dims + 3 confidence levels × 6 dims = 2 tests
  - Score 边界：0/100/-1/101 = 4 tests
  - 总计：34 tests

- [x] P6-4 回归测试
  - 状态：已完成
  - 新增测试：`tests/test_p6_regression.py`（23 项）
  - E2E 链路：7 outputs delivered / all pass contract / summary pass contract / 6 dims in summary / valid scores+ratings / evidence_refs / execution_provenance = 7 tests
  - Summary 治理：blocked tracked / low_conf tracked / verdict_range valid / tensions_present = 4 tests
  - Progress 流：stage_8 done / completed_artifacts / next_action → P7 = 3 tests
  - 错误/缺失输入：missing market/search/voc/conflict = 4 tests
  - 范围边界：no report/web artifacts / only writes evaluations = 2 tests
  - CLI smoke：help / nonexistent / success = 3 tests
  - 总计：23 tests

## 验证结果

P6 全量：57 个测试通过
全量 `unittest discover`：296 个测试通过（skipped=3）

```bash
python3 -m unittest tests.test_p6_contracts tests.test_p6_regression -v  → 57 OK
python3 -m unittest discover -v                                         → 296 OK (skipped=3)
python3 scripts/check_generic_redlines.py --token-file tests/fixtures/generic_redline_tokens.json --no-auto-run-dir → generic_redline: OK
git diff --check                                                        → 无输出
```

## 文件清单

### 新增 Schema（6 个）
- `packages/research_core/schemas/market_demand_evaluation.schema.json`
- `packages/research_core/schemas/competition_evaluation.schema.json`
- `packages/research_core/schemas/price_profit_evaluation.schema.json`
- `packages/research_core/schemas/voc_opportunity_evaluation.schema.json`
- `packages/research_core/schemas/risk_evaluation.schema.json`
- `packages/research_core/schemas/data_quality_evaluation.schema.json`

### 新增契约（1 个）
- `packages/research_core/contracts/p6_contracts.py`

### 新增 Pipeline（1 个）
- `packages/research_core/pipeline/build_evaluation_summary.py`

### 新增 CLI（1 个）
- `scripts/build_evaluation_summary.py`

### 新增测试（2 个）
- `tests/test_p6_contracts.py`（34 tests）
- `tests/test_p6_regression.py`（23 tests）

### 修改文件（1 个）
- `packages/research_core/contracts/__init__.py` — 导出 P6 符号

## 评分规则总览

| 维度 | 信号数 | 关键数据源 | blocker 条件 |
|---|---|---|---|
| market_demand | 5 | search_demand keyword_demand, trend_signal; market_structure market_size | derived_metrics 含 negative/blocking |
| competition | 5 | market_structure concentration, new_product_signal | 混池 blocking; blocking conflict 未解决 |
| price_profit | 4 | market_structure price_band, market_size avg_price | 无（无成本输入，confidence 上限 medium） |
| voc_opportunity | 4 | voc_evidence review_scope, pain_points; review_voc_package stats | 无 |
| risk | 5 | conflict blocking_conflicts; market return_rate; search trend seasonality | 无 |
| data_quality | 5 | route_matrix routes; conflict blocking_conflicts/basis_mismatches; completeness blocker | blocking_conflict 未解决; P4 completeness blocker |

## 治理规则

1. data_quality blocked → recommended_final_verdict_range = ["blocked"]
2. 任一核心维度（market_demand/competition/price_profit/data_quality）blocked → ["watch", "no_go"]
3. 辅助维度（voc_opportunity/risk）blocked 不影响 go 选项
4. low confidence 维度被 tracking 但不 block
5. cross_dimension_tensions 探测：VOC 强+市场弱、市场强+竞争/价格 blocked、数据质量 blocked
