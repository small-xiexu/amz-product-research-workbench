# 宠物牵引绳 Run 中发现的问题与修复方案

**日期**：2026-06-26 | **发现人**：主 Agent + 运营 | **Run**：pet-leash-us

---

## 问题 1：Agent 产出路径与脚本期望不一致

**现象**：Agent 深挖产出写入 `deep_dive/`，但 Stage 7-8 脚本（`build_review_asin_batch.py`、`build_conflict_review.py`）硬编码期望 `market_structure/market_structure_evidence_packet.json` 和 `search_demand/search_demand_evidence_packet.json`。

**影响**：每个 run 都要手动建符号链接，否则脚本链断裂。

**根因**：SKILL.md Stage 6 的 Agent prompt 中指定的输出路径与脚本硬编码路径未统一。

**修复**：
- 文件：`/Users/sxie/.claude/skills/amazon-product-research/SKILL.md`
- 位置：Stage 6 Agent prompt 中的输出路径
- 改动：`deep_dive/market_structure_evidence_packet.json` → `market_structure/market_structure_evidence_packet.json`
- 改动：`deep_dive/search_demand_evidence_packet.json` → `search_demand/search_demand_evidence_packet.json`
- 同步检查 `multi_agent_dispatch.md` 中 Stage 6 产物路径是否一致

---

## 问题 2：Market Structure Agent 单 Agent 超时

**现象**：Stage 6 Market Structure Agent 覆盖 11 条路线，单 Agent 调用 ~58 次 MCP，上下文膨胀到 ~1.2MB，运行 20 分钟后因无进度被 watchdog 杀掉。

**影响**：Agent 收集了大量数据但未能完成最终写入，需恢复后重写。

**根因**：单 Agent 承担了全部 11 条路线的深挖任务。

**修复方案**（二选一）：

### 方案 A：按路线分片，多个 Agent 串行接力
- 将 11 条路线拆成 3 组（4+4+3）
- 3 个 Agent 串行执行：Agent A 完成 → Agent B 继续 → Agent C 继续
- 每个 Agent 写入独立的 route_breakdown 片段
- 主 Agent 最后合并成一个完整 evidence packet
- **优点**：单个 Agent 不会超时，且避免了并行导致的 MCP 超频（40次/分钟限制）
- **缺点**：总耗时会增加（3 个串行），但比单 Agent 超时重跑更可控

### 方案 B：限定单 Agent 最大路线数
- 在 SKILL.md 中规定：深挖路线 > 8 条时，自动触发分片
- 路线 ≤ 8 条时仍可单 Agent

**推荐**：方案 A（分片串行），兼顾 MCP 限流和 Agent 稳定性。

**修改文件**：
- `/Users/sxie/.claude/skills/amazon-product-research/SKILL.md` Stage 6 部分
- `/Users/sxie/.claude/skills/amazon-product-research/references/multi_agent_dispatch.md` Stage 6 调度规则

---

## 问题 3：占位符扫描过于暴力

**现象**：`_check_placeholders()` 对所有非白名单 key 下的 string 值做正则 `sellersprite|sorftime|mcp|quick_gate|workflow_state` 扫描。`candidate_pool.json` 的 `appearance_reason`、`reason`、`route_summary` 等业务描述字段被命中，Agent 需要 3 轮清理才能通过校验。

**影响**：纯机械工作，浪费 token 和时间。

**根因**：白名单 `_TECHNICAL_KEY_PATTERNS` 缺少业务描述类 key。

**修复**：
- 文件：`/Users/sxie/Documents/亚马逊/amz-product-research-workbench/packages/research_core/pipeline/build_mcp_candidate_pool.py`
- 在 `_TECHNICAL_KEY_PATTERNS` 中追加：
  ```python
  "appearance_reason",
  "reason",
  "route_summary",
  "note",
  "notes",
  "description",
  "detail",
  "summary",
  "statement",
  "insights_for_handoff",
  "decision_reason",
  "selection_reason",
  "verdict_reason",
  "biggest_opportunity",
  "biggest_risk",
  "recommendation",
  ```
- 同步修改：
  - `/Users/sxie/Documents/亚马逊/amz-product-research-workbench/packages/research_core/pipeline/build_route_matrix_confirmation.py` 中的同名白名单
  - `/Users/sxie/Documents/亚马逊/amz-product-research-workbench/packages/research_core/pipeline/build_report_seed.py` 中的同名白名单（如有）

---

## 问题 4：深挖快照在子 Agent 模式下不可用

**现象**：`build_deep_snapshot.py` 期望从 Agent MCP dump JSON 文件提取 tool_calls/tool_results。子 Agent 的 tool_calls 在 JSONL 格式的 task output 文件中，格式不匹配，无法生成合约快照。导致整条脚本链（`build_sellersprite_deep_dive.py` → `build_deep_evidence_packet.py` → `build_conflict_review.py`）全部断裂。

**影响**：
- Stage 6 深挖脚本无法运行（快照不完整报 `missing required fields`）
- Stage 7 冲突复核脚本无法运行（依赖 `deep_data_completeness_check.json`）
- Stage 13 QA 数据溯源链中断（无法从报告数字追溯到 MCP 原始返回）

**注意**：不影响数据正确性——Agent 证据包中的数字是真实 MCP 返回的。影响的是 Stage 13 的可追溯性。

**修复方案**（二选一）：

### 方案 A：Agent 结束时自动生成快照
- Agent prompt 中要求：在写入 evidence packet 的同时，将 tool_calls 摘要写入快照文件
- 快照格式与 `build_deep_snapshot.py` 期望的合约一致
- **优点**：不改变现有脚本链
- **缺点**：Agent 需要额外工作量

### 方案 B：Stage 7 脚本直接读证据包
- `build_conflict_review.py` 改为接受 evidence packet 作为主输入，快照作为 optional
- 快照缺失时降级为 `snapshot_unavailable`，不阻塞流程
- **优点**：减少中间层依赖
- **缺点**：Stage 13 QA 仍缺溯源链

**推荐**：A+B 组合——Stage 6 让 Agent 顺便写快照（保 Stage 13 溯源），Stage 7 改为优先读证据包（不阻塞流程）。

**修改文件**：
- `/Users/sxie/.claude/skills/amazon-product-research/SKILL.md` Stage 6 Agent prompt（方案 A）
- `/Users/sxie/Documents/亚马逊/amz-product-research-workbench/packages/research_core/pipeline/build_conflict_review.py`（方案 B）

---

## 问题 5：`build_review_asin_batch.py` KeyError

**现象**：脚本执行到最后一行 `print(f"batch: {outputs['asin_batch']}")` 时 KeyError，产物未写盘。

**影响**：ASIN 批处理文件 `review_asin_batch.json` 和导出说明 `inputs/reviews/README.txt` 未生成。

**根因**：`main()` 函数返回的 dict key 与调用方期望的 key 名不一致。

**修复**：
- 文件：`/Users/sxie/Documents/亚马逊/amz-product-research-workbench/packages/research_core/pipeline/build_review_asin_batch.py`
- 行 747：
  ```python
  # 修改前
  print(f"batch: {outputs['asin_batch']}")
  # 修改后
  print(f"batch: {outputs.get('asin_batch', outputs.get('batch_path', 'unknown'))}")
  ```
- 同步检查 `generate_asin_batch()` 函数（行 71-110）返回的 dict key 名是否与 main() 一致

---

## 问题 6：Stage 9-12 脚本层与 Agent 产出数据结构鸿沟（系统性）

**现象**：`build_evaluation_summary.py`、`build_integrated_judgment.py`、`build_report_seed.py`、`build_report_xlsx.py` 四个脚本全部因同一类错误崩溃：`AttributeError: 'str' object has no attribute 'get'`。

**影响**：Stages 9-12 的脚本链路全部断裂，无法自动生成 evaluation_summary、judgment skeleton、report_data.seed、XLSX。全部靠主 Agent 手工构建替代。

**根因**：Agent 产出的证据包（`market_structure_evidence_packet.json`、`search_demand_evidence_packet.json`）中 `facts` 列表混入了纯字符串元素。脚本侧 `_utils.py` 的 `as_list()` / `first_text()` 等工具函数未做类型守卫，对列表元素直接调 `.get()`。

**修复**（二选一，推荐组合）：

### 方案 A：脚本侧防御性编程
- 文件：`packages/research_core/pipeline/_utils.py`
- 在 `as_list()` 返回值使用处加 `isinstance(item, dict)` 守卫
- 影响面：`build_evaluation_summary.py`、`build_analysis_packet.py`、`build_report_xlsx.py` 等所有调 `as_list()` 后直接 `.get()` 的位置
- **优点**：一次修复全局生效，不依赖 Agent 行为
- **缺点**：可能导致静默跳过数据（需加 warning 日志）

### 方案 B：Agent prompt 侧格式约束
- 文件：`/Users/sxie/.claude/skills/amazon-product-research/SKILL.md`
- 在 evidence packet 输出规范中强制：`facts` 必须为 `list[dict]`，不可含裸 string
- 同步检查 `multi_agent_dispatch.md` 中 Agent prompt
- **优点**：从源头避免脏数据
- **缺点**：依赖 Agent 遵守约束，不能 100% 保证

**推荐**：A+B 组合 —— 脚本做类型守卫 + Agent prompt 做格式约束。

**修改文件**：
- `/packages/research_core/pipeline/_utils.py` — 类型守卫（方案 A）
- `/packages/research_core/pipeline/build_analysis_packet.py` — 事实遍历处加固（方案 A）
- `/.claude/skills/amazon-product-research/SKILL.md` — facts 格式约束（方案 B）
- `/.claude/skills/amazon-product-research/references/multi_agent_dispatch.md` — Agent prompt 约束（方案 B）

---

## 问题 7：Stage 10a Agent 陷入 Bash Heredoc 死循环

**现象**：Route Strategy Agent 尝试用 `bash -c "python3 << 'PYEOF' ..."` 内联 Python 写入巨型 JSON（~100KB），因 Python 字符串内含单引号（如 `'rope'概念`）导致 bash heredoc 引号冲突。Agent 反复重试同一策略，日志仅 56 行却膨胀到 785KB，最终被主 Agent 手动终止。

**影响**：Stage 10a Route Strategy Agent 的任务由主 Agent 接管完成，浪费 ~5 分钟 + 大量 token。如果所有 run 都出现此问题，Stage 10a 将不可自动执行。

**根因**：Agent prompt 未约定"如何写入文件"的工程约束。Agent 自由选择了效率最低的写入路径——在 bash -c 中嵌入巨型 heredoc。

**修复**：
- 文件：`/Users/sxie/.claude/skills/amazon-product-research/SKILL.md`
- 位置：Stage 10a Agent prompt 末尾
- 增加硬规则：
  ```
  写入规范（硬约束）：
  - 必须用 Write 工具写入 Python 脚本文件到 /tmp/，再用 Bash 执行该脚本。
  - 禁止在 bash -c / heredoc 中内联超过 20 行的 Python 代码。
  - 禁止用 Bash + heredoc 方式直接写 JSON（应使用 Write 工具）。
  ```
- 同步修改 `multi_agent_dispatch.md` 中 Stage 10a Agent prompt

---

## 问题 8：build_evaluation_summary.py 设计与 SKILL.md 流程冲突

**现象**：SKILL.md 规定 Stage 9 由 6 个 Evaluation Agent 产出评价 → 脚本做汇总。但脚本实现是自行从证据包调用 `_build_market_demand()` 等函数生成评价并覆盖 Agent 产出。两套逻辑矛盾。

**影响**：
- 脚本跑通后会覆盖 Agent 更高质量的评价（Agent 评价含具体路线分析+数字引用，脚本只做布尔信号检查）
- 脚本跑不通时（如本次问题 #6）无降级路径
- evaluation_summary.json 的 governance 逻辑（blocked 路线、跨维度冲突）在脚本中实现，Agent 手工汇总需重复造轮子

**根因**：脚本设计为 "self-contained evaluation generator"，但 SKILL.md 的定义是 "Agent first, script summary"。两者从未对齐。

**修复**：
- 文件：`packages/research_core/pipeline/build_evaluation_summary.py`
- 改为纯汇总模式：`run_evaluations()` 不再调 `_build_market_demand()` 等 6 个生成函数
- 新逻辑：读 `evaluations/market_demand_evaluation.json` 等 6 个已有文件 → 校验 schema → 调 `_build_summary()` 做 governance 合成
- 保留 `_build_summary()` 和 governance 逻辑（`_score_to_rating`、`_collect_blockers` 等），删 `_build_market_demand` / `_build_competition` / `_build_price_profit` / `_build_voc_opportunity` / `_build_risk` / `_build_data_quality` 6 个生成函数
- 如果 Agent 评价文件不存在 → 报错 "请先运行 6 个 Evaluation Agent"，不 fallback 到脚本自生成

---

## 问题 9：小但高频的工程摩擦

| 子问题 | 现象 | 修复 |
|---|---|---|
| 9a. HTML 输出路径不一致 | Agent 写 `run根目录/宠物牵引绳_分析报告.html`，`build_report_xlsx.py` 期望 `analysis/宠物牵引绳_分析报告.html` | SKILL.md Stage 12 Agent prompt 统一指定输出到 `analysis/` |
| 9b. VOC evidence packet 标记不完整 | `voc_evidence_packet.json` 中 `executed_by_agent=false`、`execution_mode=serial_fallback`，与 SKILL.md 定义的 VOC Evidence Agent 角色不符 | VOC Evidence Agent prompt 中强制写回正确的 `execution_provenance` |
| 9c. C14 零数据路线仍参与全流程 | C14 座椅安全带零 ASIN 但消耗了 4 个评价 Agent 的 token 做 blocked 判定 | Stage 5 `data_completeness_check.json` 中增加 `merge_or_exclude` 决策点：任一参考 ASIN=0 的路线触发"合并或排除"建议，不等运营确认先在 Agent prompt 中标注 |

---

## 修复优先级（更新）

| 优先级 | 问题 | 理由 |
|---|---|---|
| P0 | #6 脚本数据结构鸿沟 | 阻塞 Stages 9-12 全部脚本链路，每个 run 都需手工 workaround |
| P0 | #5 KeyError | 一行修复，阻塞所有 run 的 Stage 8 |
| P1 | #8 评价汇总设计冲突 | 每次 Stage 9 都要手工绕过，且 Agent 评价有被脚本覆盖的风险 |
| P1 | #1 路径不统一 | 每个 run 都受影响，修复成本低 |
| P1 | #3 占位符过激 | 每个 run Stage 4 浪费 3+ 轮清理 |
| P1 | #7 Agent heredoc 死循环 | Stage 10a 稳定性问题，影响所有 >8 路线的 run |
| P2 | #4 快照不可用 | 影响 Stage 13 QA 溯源，不阻塞交付 |
| P2 | #2 Agent 超时 | 仅路线数 > 8 时触发，可降级重试 |
| P2 | #9 工程摩擦 | 3 个小点各自独立，影响效率但不阻塞 |

---

## 对当前 pet-leash-us run 的影响（更新）

当前 run 已通过手工 workaround 推进到 Stage 12 完成，交付物已产出：
- `宠物牵引绳_分析报告.html`（42KB，10 板块，0 内部术语）
- `宠物牵引绳_决策工具包.xlsx`（5 Sheet）
- `analysis/integrated_operator_judgment.json`（100KB，10 深度字段 + 决策摘要）
- `analysis/report_data.json`（28KB 结构化数据）

Stage 13 QA 脚本链路因问题 #6 不可用，数据溯源（snapshot → evidence → report）无法自动化校验。如需 Stage 13 可在修复 #6 后重新执行。
