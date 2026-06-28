# CLI 双 MCP 多 Agent 选品 P7-Report 报告交付收口实施计划

状态：Report Generation Agent 已实现；两阶段脚本 + Agent 三段式全链路闭环，全部验证通过。

本计划是 P7-Report 唯一进度台账。P7-Report 不重做 P7 判断层，只把 `integrated_operator_judgment.json`、证据包和 `report_data.seed.json` 交给 Report Generation Agent，再由脚本基于 Agent 产物完成 XLSX 和 QA。

## 正确职责边界

- `build_analysis_report.py`：生成 `analysis/report_data.seed.json` 和 `analysis/analysis_packet.json`；当 `report_data.json` 或 HTML 缺失时停止并提示 Report Generation Agent；当二者存在时生成 XLSX、QA、`qa_notes.md` 和 `audit_run_status.json`。
- Report Generation Agent：读取 `report_data.seed.json`、`integrated_operator_judgment.json` 和证据包，增强 `analysis/report_data.json`，并以资深运营专家视角手写 `analysis/<中文品名>_分析报告.html`。
- Delivery QA：只检查交付完整性、source_path 溯源、HTML 内部术语泄漏、P0 阻断项、必需板块和值一致性，不替代报告生成 Agent 写判断。

## 范围边界

- P7 判断层已完成，本次不重做 `integrated_operator_judgment.json`。
- 不允许脚本自动生成正式 HTML。
- 不允许脚本把 `report_data.seed.json` 自动升级成正式 `report_data.json`。
- 不新增任何证据包外数字。
- 不改 Web / server 主链路。

## 验收清单

- [x] P7R-0 计划台账纠偏
  - 状态：已完成
  - 已将本台账从“脚本自动闭环生成 HTML”纠回“Report Generation Agent 生成 report_data + HTML，脚本做 seed / XLSX / QA”。

- [x] P7R-1 移除脚本 HTML 正式生成器
  - 状态：已完成
  - 已删除 `packages/research_core/pipeline/build_report_html.py`，避免正式主链路误用脚本模板生成 HTML。

- [x] P7R-2 恢复 `build_analysis_report.py` 编排边界
  - 状态：已完成
  - 已恢复为：seed 生成、analysis_packet 写入、检查 Report Generation Agent 产物、XLSX 生成、QA、qa_notes、audit。
  - `report_data.json` 缺失时：只写 seed 和 analysis_packet，停止在 Report Generation Agent handoff。
  - HTML 缺失时：不生成 XLSX / QA，提示 Report Generation Agent 写正式 HTML。

- [x] P7R-3 恢复 P0 契约测试
  - 状态：已完成
  - `tests/test_p0_contracts.py` 已重新断言：没有 Agent 产物时，脚本不得生成 `report_data.json`、HTML、XLSX 或 QA。

- [x] P7R-4 恢复 P7-report 交付测试
  - 状态：已完成
  - `tests/test_report_delivery.py` 已改为 Agent handoff 模式：先验证脚本只生成 seed；再模拟 Report Generation Agent 产出 `report_data.json` + HTML；最后验证脚本生成 XLSX / QA。

## 验证结果

- `python3 -m unittest tests.test_p0_contracts tests.test_p7_contracts tests.test_p7_regression tests.test_report_delivery -v` → 81 OK。
- `python3 -m compileall -q packages scripts tests` → 通过。
- `python3 -m unittest discover -v` → 366 OK，skipped=3。
- `python3 scripts/check_generic_redlines.py --token-file tests/fixtures/generic_redline_tokens.json --no-auto-run-dir` → `generic_redline: OK`。
- `git diff --check` → 无输出。

## 下一步

- [x] Report Generation Agent 实现（2026-06-25 完成）
- [ ] 真实 run 验收：用真实品类数据跑完整三段式链路（seed → agent → XLSX/QA）

---

## Report Generation Agent 实现（2026-06-25）

### 新增文件

| 文件 | 说明 |
|---|---|
| `packages/research_core/pipeline/report_agent.py` | 本地开发/回归用 serial fallback，不是正式交付入口 |
| `scripts/run_report_agent.py` | 本地开发辅助 CLI |

### Agent 核心功能

- `enhance_seed_to_report_data(seed, judgment, analysis)` — seed → 正式 report_data.json 增强
  - Hero 判词从 judgment 推导
  - 类目全景洞察数据驱动填充
  - 竞品判词、痛点描述、价格带机会、关键词策略自动生成
  - Go/No-Go 条件从 judgment operator_constraints 填充
  - 下一步从 judgment required_next_actions 填充
  - 所有 source_path 保留，不捏造数字
- `generate_operator_html(report_data)` — 从 report_data.json 生成运营 HTML
  - 6 大板块完整
  - report_template.css 作为 inline `<style>`
  - 无内部术语泄露
  - 资深运营专家叙事风格
- `validate_agent_output(report_data_path, html_path)` — Agent 产物校验
  - 检查 11 板块完整
  - 检查空 source_path（阻断）
  - 检查 HTML 6 板块齐全
  - 检查 inline style

### 完整三段式链路

```
1. build_analysis_report.py → report_data.seed.json + analysis_packet.json
   （缺少 report_data.json → 输出 "REPORT DATA MISSING" 并停止）

2. Report Generation Agent → report_data.json + <品名>_分析报告.html（`run_report_agent.py` 仅可作本地开发辅助）
   （Agent 读取 seed/judgment/证据包，增强并生成 HTML）

3. build_analysis_report.py → XLSX + QA + qa_notes + audit
   （检测到 report_data.json + HTML 存在，生成剩余产物）
```

### 新增测试（21 项）

- `ReportAgentEnhancementTests`（8）：增强保留板块、provenance 标记、source_path 无空字符串、judgment 判词填充、下一步填充、竞品判词、痛点描述、价格带判词
- `ReportAgentHTMLTests`（5）：6 板块、无禁止术语、inline style、go-nogo class、DOCTYPE
- `ReportAgentValidationTests`（4）：有效输出通过、缺失 report_data、空 source_path、缺失 HTML
- `ReportAgentCLITests`（4）：CLI smoke、无 seed 失败、不存在目录失败、完整三段式流程

### 验证结果

```bash
python3 -m unittest discover -v                                                  → 387 OK (skipped=3)
python3 scripts/check_generic_redlines.py --token-file ... --no-auto-run-dir     → generic_redline: OK
git diff --check                                                                 → 无输出
python3 -m compileall -q packages scripts tests                                  → 通过
```
