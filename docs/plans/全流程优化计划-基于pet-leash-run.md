# 全流程优化计划 — 基于宠物牵引绳 Run 复盘

**日期**：2026-06-26 | **来源**：pet-leash-us 全 13 Stage 实战 | **状态**：待认领

---

## 目标

基于第一个端到端跑通的品类（宠物牵引绳）实战经验，消除结构性摩擦，让后续 run 从 Stage 1 到 Stage 13 更少人工救火、更多自动化。

---

## 当前状态

| 维度 | 状态 |
|------|------|
| 全流程可跑通 | 是——pet-leash-us 已走完 13 Stage，交付物通过 QA |
| 脚本自动化率 | ~40%——Stage 9-12 脚本全链路断裂，依赖 Agent 手工构建 |
| 契约一致性 | 差——judgment / report_data / QA 三套字段名体系，Stage 13 才发现 |
| MCP 溯源性 | 不可用——快照空壳，只能溯源到 evidence packet 层 |
| 问题记录 | 9 个 issue 已写入 `docs/issue_log/2026-06-26_pet-leash-run-issues.md` |

---

## 优化项

### P0 — 每个 run 必做，不做就无法自动跑通

#### OPT-01：脚本加类型守卫，消除数据鸿沟

**现象**：Agent 产出的 evidence packet 中 `facts` 列表混入裸 string，脚本调 `.get()` 全部崩溃。影响 `build_evaluation_summary.py`、`build_integrated_judgment.py`、`build_report_seed.py`、`build_report_xlsx.py` 四个脚本。

**根因**：`_utils.py` 的 `as_list()` / `first_text()` 等函数未做类型守卫，Agent prompt 未约束 `facts` 必须是 `list[dict]`。

**做法**：
1. `packages/research_core/pipeline/_utils.py`：已加 `safe_get(item, key, default)` 类型守卫函数
2. 全局 grep `as_list(` 返回值后直接调 `.get()` 的位置，替换为 `safe_get()` 或加 `isinstance(item, dict)` 守卫
3. SKILL.md Stage 6 Agent prompt 加格式约束："facts 必须为 `list[dict]`，每个 dict 至少含 `id` 和 `value` 字段"

**涉及文件**：
- `packages/research_core/pipeline/_utils.py`
- `packages/research_core/pipeline/build_analysis_packet.py`
- `packages/research_core/pipeline/build_evaluation_summary.py`
- `packages/research_core/pipeline/build_report_seed.py`
- `packages/research_core/pipeline/build_report_xlsx.py`
- `packages/research_core/pipeline/build_integrated_judgment.py`
- `.claude/skills/amazon-product-research/SKILL.md`

**验收**：用 pet-leash-us 的 evidence packet 跑 `build_evaluation_summary.py`，不再报 `'str' object has no attribute 'get'`。

---

#### OPT-02：build_evaluation_summary.py 改为纯汇总模式

**现象**：脚本设计为"自己从 evidence 生成 6 份评价"，但 SKILL.md 定义的是"Agent 产出评价 → 脚本做 governance 汇总"。脚本跑通会覆盖 Agent 评价，跑不通整条链路断裂。

**做法**：
1. `run_evaluations()` 不再调用 `_build_market_demand()` / `_build_competition()` / `_build_price_profit()` / `_build_voc_opportunity()` / `_build_risk()` / `_build_data_quality()` 这 6 个生成函数
2. 改为读取 `evaluations/market_demand_evaluation.json` 等 6 个 Agent 产出的文件
3. 校验 schema（每个文件必须含 `overall_score`、`dimension_scores`、`route_breakdown`）
4. 调 `_build_summary()` 做 governance 合成（路线交叉对比、blocked 规则、冲突标记）
5. 如果 Agent 评价文件不存在 → 报错"请先运行 6 个 Evaluation Agent"，不 fallback

**涉及文件**：`packages/research_core/pipeline/build_evaluation_summary.py`

**验收**：脚本执行后生成的 `evaluation_summary.json` 中的路线评分与 6 个 Agent 评价文件一致。

---

### P1 — 显著降低每个 run 的人工成本

#### OPT-03：统一三套字段名体系

**现象**：judgment 用 `if_you_choose_this_you_give_up`，契约要 `lose`；report_data 用 `keyword_strategy`，契约要 `keywords`。Stage 13 QA 才发现，手工映射 20+ 字段。

**做法**：
1. 在 `build_report_seed.py` 和 `build_integrated_judgment.py` 的骨架生成阶段，输出时直接使用契约字段名（参考 `judgment_contract.py` 和 `constants.py` 中的 `REQUIRED_REPORT_DATA_SECTIONS`）
2. 在 Stage 11 脚本末尾加字段名校验：对比产出的 key 集合与 `REQUIRED_REPORT_DATA_SECTIONS`，缺失则报 warning
3. 所有 Agent prompt 中引用字段名时统一使用契约名

**涉及文件**：
- `packages/research_core/pipeline/build_report_seed.py`
- `packages/research_core/pipeline/build_integrated_judgment.py`
- `packages/research_core/pipeline/judgment_contract.py`
- `.claude/skills/amazon-product-research/SKILL.md`（Agent prompt 中的字段名引用）

**验收**：新 run 的 `report_data.json` 首次生成即通过 `_report_data_has_required_sections` 检查。

---

#### OPT-04：Stage 6 产出后立即契约校验

**现象**：evidence packet 的数据结构问题（裸 string 混入 facts、必填字段缺失）到 Stage 9-12 脚本崩溃时才发现。如果在 Stage 6 Agent 产出后立即校验，可以在更早阶段修。

**做法**：
1. 写一个轻量校验脚本 `scripts/validate_evidence_packet.py`：
   - 检查 `facts` 元素是否全是 `dict`
   - 检查每个 fact 是否含 `id`、`value`、`source`
   - 检查 `route_breakdown` 是否覆盖所有保留路线
2. 在 SKILL.md Stage 6 末尾的脚本清单中加入该校验步骤
3. 校验失败 → 打回 Stage 6 Agent 修复，不进入 Stage 7

**涉及文件**：
- 新建 `scripts/validate_evidence_packet.py`
- `.claude/skills/amazon-product-research/SKILL.md`

**验收**：故意构造一个含裸 string 的 evidence packet，脚本报错并指明具体位置。

---

#### OPT-05：VOC Evidence Agent 真正执行

**现象**：`voc_evidence_packet.json` 是脚本跑的空骨架（`pain_points_by_dimension: []`、`covered_routes: 0`）。真正的 VOC→规格推导在 Stage 10a Growth & Risk Agent 里补做。Stage 8 形同虚设。

**做法**：二选一
- **方案 A（推荐）**：让 VOC Evidence Agent 真正 spawn，读取 `review_voc_package.json` 完成痛点提取、维度分类、规格推导，写入 `voc_evidence_packet.json`
- **方案 B**：承认 VOC 分析实际发生在 Stage 10a，删除 Stage 8 VOC Evidence Agent，将评论分析职责显式合并到 Stage 10a Growth & Risk Agent 的 prompt 中

**涉及文件**：
- `.claude/skills/amazon-product-research/SKILL.md`
- `.claude/skills/amazon-product-research/references/multi_agent_dispatch.md`

**验收**：`voc_evidence_packet.json` 的 `pain_points_by_dimension` 不为空数组，`covered_routes > 0`。

---

#### OPT-06：Agent system prompt 注入工程约束

**现象**：Stage 10a Agent 用 `bash -c "python3 << 'PYEOF'"` 内联 100KB Python，中文引号导致 bash 转义失败，死循环重试。SKILL.md 已加硬规则，但 Agent 不一定遵守。

**做法**：
1. 在 `multi_agent_dispatch.md` 的 Stage 10a Agent prompt 中注入"文件写入必须使用 Write 工具"的 system 级约束
2. 在所有 Stage 的 Agent prompt 中增加通用工程约束："写入 JSON 用 Write 工具，运行 Python 先把脚本 Write 到 /tmp/ 再用 Bash 执行"

**涉及文件**：`.claude/skills/amazon-product-research/references/multi_agent_dispatch.md`

**验收**：Agent 日志中不再出现 heredoc 内联 Python。

---

### P2 — 改善体验和效率

#### OPT-07：增加"轻量路线"快速判定

**现象**：C10（金属链月销 1.8K）、C14（零 ASIN）在 Stage 5 就已明确数据不足，但仍走了完整的 6 维评价 + 2 深度分析，消耗大量 token。

**做法**：
1. Stage 5 `data_completeness_check.json` 中增加 `tier` 分类：
   - `full`：参考 ASIN ≥ 2、搜索量 ≥ 5K → 完整 6 维评价
   - `light`：参考 ASIN < 2 或搜索量 < 5K → 仅做 2 维快速定性（市场需求 + 数据质量），其余 4 维标注"数据不足"
2. Stage 9 的 `build_evaluation_summary.py` 读取 `tier` 分类，对 light 路线生成简化评价

**涉及文件**：
- `packages/research_core/pipeline/build_route_matrix_confirm.py`
- `packages/research_core/pipeline/build_evaluation_summary.py`
- `.claude/skills/amazon-product-research/SKILL.md`

**验收**：新 run 中 light 路线的评价文件仅含 2 个维度，明确标注 `tier: light`。

---

#### OPT-08：Agent 结束时自写简化快照

**现象**：子 Agent 的 tool_calls 格式与 `build_deep_snapshot.py` 期望不兼容，导致 MCP 快照持续空壳。Stage 13 QA 无法溯源到原始 MCP 返回。

**做法**：
1. Stage 6 Agent prompt 中增加：完成 evidence packet 写入后，同步生成简化快照文件，格式：
   ```json
   {
     "tool_summaries": [
       {"tool": "competitor_lookup", "params": {"keyword": "dog leash"}, "key_findings": ["37,417 units/month", "Top ASIN: B099WM7ZT7"]}
     ]
   }
   ```
2. Stage 13 QA 改为同时接受"完整快照"和"简化快照"两种格式
3. 不要求 Agent 保存完整 tool_result（那会膨胀上下文），只保存关键数字

**涉及文件**：
- `.claude/skills/amazon-product-research/SKILL.md`（Stage 6 Agent prompt）
- `packages/research_core/pipeline/delivery_qa.py`（QA 快照格式兼容）

**验收**：新 run 的 `mcp_snapshots/` 下快照文件不再为空壳，Stage 13 QA 可至少溯源 3 层。

---

#### OPT-09：放宽 HTML QA 的 CSS 刚性检查

**现象**：CSS 必须逐字节匹配模板、class 必须在白名单——手写 HTML 不可能一次通过 QA。本次 HTML 被 Agent 重渲一遍才过，额外消耗 ~75K token。

**做法**：二选一
- **方案 A**：Stage 12 提供标准 HTML 骨架文件（`report_template.html`），Agent 只填内容不写 CSS
- **方案 B**：QA 检查降级——CSS 检查改为"关键 class 存在"（hero/page/section/card/gonogo），不检查是否逐字节匹配模板；class 检查改为"发现非白名单 class 发 warning 不阻断"

**涉及文件**：
- `packages/research_core/pipeline/delivery_qa.py`
- `.claude/skills/amazon-product-research/references/report_template.css`
- 新建 `skills/amazon-product-research/references/report_template.html`（方案 A）

**验收**：Agent 手写的 HTML 首次即可通过 QA 渲染检查。

---

## 执行顺序建议

```
第一轮（解锁自动化）：
  OPT-01（类型守卫） → OPT-02（评价汇总改纯汇总） → OPT-04（契约校验前置）

第二轮（减少人工）：
  OPT-03（字段名统一） → OPT-05（VOC Agent 真正执行） → OPT-06（注入工程约束）

第三轮（改善体验）：
  OPT-07（轻量路线） → OPT-08（简化快照） → OPT-09（放宽 CSS 检查）
```

---

## 验收标准

用新品类（非宠物牵引绳）从头跑到 Stage 13：

- [ ] 6 个脚本生成环节（Stage 4/5/7/8/11/12）至少 5 个直接跑通，无需 Agent 手工替代
- [ ] `report_data.json` 首次生成即通过 `_report_data_has_required_sections`
- [ ] `voc_evidence_packet.json` 的 `pain_points_by_dimension` 非空
- [ ] Stage 13 QA 两层均首轮 PASS（渲染问题允许一轮 Agent 修复）
- [ ] 全程主 Agent 无需手工构建 JSON 骨架
- [ ] 9 个已记录 issue 全部可以在对应优化项中找到修复方案

---

## 关联

- Issue Log: `docs/issue_log/2026-06-26_pet-leash-run-issues.md`（9 个问题）
- QA Report: `runs/20260626_宠物牵引绳/analysis/qa_notes.md`
- Skill: `.claude/skills/amazon-product-research/SKILL.md`
- Dispatch: `.claude/skills/amazon-product-research/references/multi_agent_dispatch.md`
