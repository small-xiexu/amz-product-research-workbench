# CLI 双 MCP 多 Agent 选品 P8 QA 强化实施计划

状态：未启动

本计划是 P8 唯一进度台账。P8 在 P7 报告交付完成的基础上，建立**双层强制 QA 门禁**，不可跳过、不可降级。

## 范围边界

- 只改 `packages/research_core/pipeline/delivery_qa.py`、`constants.py`、`skills/amazon-product-research/agents/delivery-qa-agent.md`、`skills/amazon-product-research/references/multi_agent_dispatch.md`。
- 新增 `scripts/run_delivery_qa.py`、`tests/test_p8_qa_hardening.py`。
- 不改 Web/server 主链路。
- 不改其他 pipeline 模块、Skill 主文件、报告生成 Agent 定义。
- 不写死任何具体品类、ASIN、关键词、价格、品牌、卖家或供应商。

## QA 架构

```
build_analysis_report.py 生成 XLSX 后
          │
          ├─ 1. 脚本 QA（自动执行，不可跳过）
          │     → analysis/delivery_qa_result.json
          │     fail → 阻断，不进入 Agent QA
          │
          └─ 2. Delivery QA Agent（强制独立 spawn，不可跳过）
                → analysis/qa_notes.md
                pass → 交付
                fail → 打回 Report Generation Agent 修复
                       ↓
                重新 QA（最多 3 轮）
                3 轮不过 → blocked，人工介入
```

## 验收清单

### 脚本 QA 强化

- [ ] P8-1 补全禁止术语模式
  - 状态：未启动
  - 在 `constants.py` 的 `FORBIDDEN_HTML_PATTERNS` 中新增：
    - 数据源品牌名：`卖家精灵`（作为数据源描述）、`Sorftime`（作为数据源描述）
    - 冲突过程语言：`数据源冲突`、`数据不一致`、`两个数据源`
    - 数据源对比：`卖家精灵显示`、`Sorftime 显示`
    - 内部产物概念：`snapshot`、`schema_version`、`execution_provenance`
  - `<style>` 标签内不扫描。
  - 验收：含禁止术语的 HTML → 检出；正常运营报告 → 通过。

- [ ] P8-2 新增冲突泄漏专项扫描
  - 状态：未启动
  - 在 `delivery_qa.py` 中新增 `_scan_conflict_leak(html_path, conflict_packet_path)`。
  - 从 `conflict_resolution_packet.json` 提取所有冲突涉及的 ASIN、类目、关键词。
  - 扫描 HTML 是否出现冲突相关语言。
  - 报告中允许的运营表达不触发告警："需求稳定性需验证"、"类目边界需复核"、"样本量有限"。
  - 集成到 `run_delivery_qa()` 的 checks 中。
  - 验收：含"两个数据源冲突"→ 检出；含"需求稳定性需验证"→ 通过。

- [ ] P8-3 增强 source_path 追溯至 MCP snapshot
  - 状态：未启动
  - 在 `_try_resolve_path` 中增加 MCP snapshot 级别的追溯。
  - 如果 source_path 指向 evidence packet 中的字段，且该字段的 `evidence_refs` 指向 MCP snapshot，验证：
    1. snapshot 文件是否真实存在于 `mcp_snapshots/` 目录
    2. JSON pointer 语法是否合法（RFC 6901）
  - 兜底：source_path 中引用路径以 `runs/` 或 `mcp_snapshots/` 开头时，验证文件真实存在。
  - 验收：有效文件路径 → resolved；不存在的文件 → unresolved；非法 JSON pointer → unresolved。

- [ ] P8-4 新增脚本 QA CLI 入口
  - 状态：未启动
  - 新增 `scripts/run_delivery_qa.py`。
  - 用法：`python3 scripts/run_delivery_qa.py <run_dir>`
  - 自动找到 `analysis/report_data.json`、HTML、XLSX，调用 `run_delivery_qa()`。
  - 打印 pass/fail 及失败明细。
  - 退出码：pass → 0，fail → 1。
  - 验收：有效 run 目录 → 退出码 0 或 1；不存在目录 → 退出码 1 并打印错误。

### Delivery QA Agent 强化

- [ ] P8-5 重写 delivery-qa-agent.md
  - 状态：未启动
  - 调度规则改为强制独立 spawn，不可跳过，不可主 Agent 自检替代。
  - 每次 QA 重跑必须是新的独立 spawn。
  - 如果环境不支持 spawn：标记为 `blocked`，不得以降级方式交付。
  - 验收：Agent 定义文件与 `docs/CLI双MCP多Agent选品技术方案.md` QA 段完全一致。

- [ ] P8-6 定义数据真实性交叉核对规则
  - 状态：未启动
  - Agent 必须实际打开文件、读取数值、逐条交叉比对三级追溯链：
    HTML 数字 → report_data.json value + source_path → evidence packet → MCP snapshot
  - 定义 6 条 blocker 级别规则：
    1. HTML 数字在 report_data.json 中无对应
    2. source_path 为空或无效
    3. evidence packet 字段在 MCP snapshot 中无对应
    4. 数值在三级链路中不一致
    5. 报告中出现 evidence packet 中不存在的数字（凭空捏造）
    6. 派生计算错误
  - 验收：含捏造数字的 fixture 报告 → Agent 应检出所有 blocker。

- [ ] P8-7 定义运营判断质量检查规则
  - 状态：未启动
  - 8 条检查规则（4 blocker + 4 error）：
    - blocker：只堆数据不下判断、low confidence 强结论、评价 blocked 却给 Go、VOC 痛点无法溯源
    - error：过度乐观、关键词未分层、参考 ASIN 不相似、内部术语/数据源/冲突泄漏
  - 验收：含上述问题的 fixture 报告 → Agent 应检出。

- [ ] P8-8 定义修复循环机制
  - 状态：未启动
  - 最多 3 轮 QA 修复循环。
  - 每轮 QA 输出独立的 `qa_notes.md`（最新轮）和 `qa_notes.roundN.md`（历史轮）。
  - `qa_notes.md` 格式为可执行修复清单，精确到行级别。
  - Report Generation Agent 修复时只能修改报告内容和 `report_data.json`，不得修改 evidence packet 或 MCP snapshot。
  - 3 轮不过 → `stage_10_qa` 标记为 `blocked`，`next_required_user_action` 写清阻塞原因。
  - `progress.json` 中 `stage_10_qa` 状态：`pending → running → needs_fix → running → done` 或 `pending → running → blocked`。
  - 验收：fixture 模拟 3 轮 QA 循环，第 3 轮仍 fail → progress 中 `stage_10_qa.status = "blocked"`。

### 调度规则更新

- [ ] P8-9 更新 multi_agent_dispatch.md
  - 状态：未启动
  - Delivery QA Agent 从"可 spawn"改为"强制 spawn"。
  - 新增 QA → 报告 Agent 修复循环编排说明。
  - 新增"QA 不可降级"规则：环境不支持 spawn 时标记 blocked，不交付。
  - 验收：调度表与 P8 架构一致。

### 测试与回归

- [ ] P8-10 补充 P8 测试
  - 状态：未启动
  - 新增 `tests/test_p8_qa_hardening.py`。
  - 脚本层测试（≥12 项）：
    - 禁止术语扫描：含"卖家精灵"→ 检出；含"需求稳定性需验证"→ 通过
    - 冲突泄漏：含"两个数据源冲突"→ 检出；正常报告 → 通过
    - source_path 追溯：有效路径 → resolved；不存在文件 → unresolved；非法 JSON pointer → unresolved
    - P0 阻塞项：blocking conflict 未解决 → fail；data_quality=blocked → fail
    - CLI smoke：有效目录 → 退出码 0 或 1；不存在目录 → 退出码 1
  - Agent 层契约测试（≥8 项，用 fixture 模拟）：
    - 报告数字在 evidence 中存在 → 通过
    - 报告数字在 evidence 中不存在 → blocker
    - HTML 写 5000，evidence 是 3200 → blocker
    - 报告给 Go 但 data_quality blocked → blocker
    - 只堆数据无明确结论 → blocker
    - 修复循环：3 轮 fail → blocked
    - 修复循环：第 2 轮 pass → done
  - 验证命令：
    - `python3 -m unittest tests.test_p8_qa_hardening -v`
    - `python3 -m unittest discover -v`
    - `python3 scripts/check_generic_redlines.py --token-file tests/fixtures/generic_redline_tokens.json --no-auto-run-dir`
    - `git diff --check`

- [ ] P8-11 完成 P8 验证
  - 状态：未启动
  - P0-P7 全量回归通过。
  - P8 专项测试通过。
  - 通用红线扫描通过。
  - `git diff --check` 无输出。

## 出口条件

- [ ] 所有 P8 项完成并有验收依据。
- [ ] 脚本 QA 可独立运行（`scripts/run_delivery_qa.py`）。
- [ ] Delivery QA Agent 定义文件与技术方案 QA 段完全一致。
- [ ] 修复循环机制在 progress.json 状态机中可追踪。
- [ ] P8 专项测试通过（≥20 项）。
- [ ] 全量 unittest 通过（现有 387 项 + P8 新增）。
- [ ] 通用红线扫描通过。
- [ ] `git diff --check` 通过。

## 参考

- 技术方案 QA 段：`docs/CLI双MCP多Agent选品技术方案.md` L720-870
- 脚本 QA 实现：`packages/research_core/pipeline/delivery_qa.py`
- QA 规则常量：`packages/research_core/pipeline/constants.py`
- Agent 定义：`skills/amazon-product-research/agents/delivery-qa-agent.md`
- 调度规则：`skills/amazon-product-research/references/multi_agent_dispatch.md`
- 正式报告契约：`docs/正式报告契约.md`
