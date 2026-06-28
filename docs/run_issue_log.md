# 全流程跑测问题日志

状态：**21 项已修复，0 项待修复**（2026-06-25 宠物牵引绳跑测） <!-- generic-redline: allow historical run postmortem retains original case name -->

记录规则：
- 每条问题写清楚：**阶段、现象、期望、是否阻塞**
- 阻塞问题标 `[BLOCK]`，非阻塞标 `[NOTE]`
- 跑完后来本会话修复

---

## 问题列表

### [BLOCK] · 已修复 — Stage 2 — Quick Agent 产出的 evidence packet 缺少契约必填字段

- **现象**：Agent 生成的 packet JSON 内容质量高，但缺少 `validate_quick_packet()` 要求的 17 个必填字段，导致后续脚本报错。
- **修复**：创建 `scripts/fill_quick_packet_contract.py`，从 Agent 自由格式 JSON 补全全部 17 个契约字段；Agent prompt 中也加入了完整字段清单。测试覆盖：导入性、17字段补齐、原始内容保留。

### [NOTE] · 已修复 — Stage 2 — Agent 写入目录与脚本期望不一致

- **现象**：Agent prompt 写入 `quick_packets/`，脚本期望 `quick_check/`。
- **修复**：统一为 `quick_check/`。`market-structure-agent.md` 和 `search-demand-agent.md` 的输出路径已修正。

### [BLOCK] · 已修复 — Stage 4 — 缺少 workflow_state.json 初始化脚本

- **现象**：`build_mcp_candidate_pool.py` 依赖 `workflow_state.json`，但没有脚本自动生成。
- **修复**：创建 `scripts/init_workflow_state.py`，自动生成含全部 10 个必填字段的 workflow_state。测试覆盖：导入性验证。

### [BLOCK] · 已修复 — Stage 4 — quick_market_gate.json 无人产出

- **现象**：没有明确的"谁来产出 gate 文件"的职责分配，候选池脚本找不到 gate 文件。
- **修复**：创建 `scripts/build_quick_market_gate.py`，读取两个 quick packet 后调用 `build_quick_market_gate()` 生成门控。

### [NOTE] · 已修复 — Stage 2 — MCP Snapshot 缺失

- **现象**：Agent 未保存 MCP 原始返回，evidence_refs 指向不存在的文件。
- **修复**：在 `market-structure-agent.md` 和 `search-demand-agent.md` 的 prompt 中增加了保存 MCP snapshot 到 `mcp_snapshots/` 的指令。

### [NOTE] · 已降级 — Stage 2 — Sorftime MCP 部分 API 不可用

- **现象**：`category_search_from_product_name` 和 `category_name_search` 调用失败。
- **处理**：已知 MCP 服务端限制，在 Agent prompt 中注明用 `keyword_search_results` 替代。非代码侧可修复项。

### [NOTE] · 已修复 — Stage 2-3 — 双源搜索趋势数据冲突未自动标记

- **现象**：卖家精灵 vs Sorftime 趋势数据冲突未被自动检出。
- **修复**：在 `quick_market_check.py` 中新增 `_flag_cross_source_discrepancies()` 函数，检测 4 类跨源分歧（support_level、mixed_pool、category_boundary、trend signals），输出 `cross_validation` 字段。测试覆盖：字段存在性、support_level 分歧检出。

### [NOTE] · 已修复 — Stage 1-4 — 整体流程碎片化

- **现象**：Stage 1-4 之间依赖大量手工步骤。
- **修复**：创建 `scripts/run_pipeline.py`，一键编排 Stage 1-4，支持 `--from-stage` 断点续跑。SKILL.md 和 README 已加入对应命令引用。测试覆盖：导入性验证。

---

## 修复记录

### [BLOCK] · 已修复 — Stage 5 — 路线确认缺乏人工介入通道

- **现象**：Gate 判 WATCH → 候选池 `needs_user_review` → `build_route_matrix_confirm.py` 自动 reject 全部路线。
- **修复**：添加 `--force-confirm` 标志。当设置时，跳过 `needs_user_review` 检查，将 support_level 为 strong/moderate 的路线标记为 selected。blocker 和 先放弃 仍然正确 reject。测试覆盖：`RouteMatrixForceConfirmTests`。

### [BLOCK] · 已修复 — Stage 6/7/8 — 深挖阶段目录命名不一致

- **现象**：Agent 写入 `evidence/`，但脚本期望 `market_structure/`、`search_demand/`。
- **修复**：Agent prompt（market-structure-agent.md、search-demand-agent.md）在上一轮已修正，Stage 6 写 `market_structure/` 和 `search_demand/`。另创建 `build_deep_evidence_packet.py` 接管 Agent 自由格式 → P4 契约包的转换。

### [BLOCK] · 已修复 — Stage 7 — 深挖 snapshot 契约格式缺失

- **现象**：Agent 保存自由格式 MCP 返回，不满足 15 字段 deep snapshot 契约。
- **修复**：创建 `scripts/build_deep_snapshot.py`，从 Agent 的 tool_calls/result 自由格式自动填充全部 15 个必填字段。测试覆盖：`DeepSnapshotTests`。

### [BLOCK] · 已修复 — Stage 8 — Evidence Packet 结构不匹配

- **现象**：`_extract_evidence_asins()` 只识别 `evidence_items` 数组，Agent 产出的 free-form facts 导致提取 0 个 ASIN。
- **修复**：新增 `_scan_facts_for_asins()` 回退逻辑，递归扫描 `facts` 下所有嵌套 dict 中的 ASIN 字段。测试覆盖：`ExtractEvidenceAsinsFallbackTests`。

### [NOTE] · 已修复 — Stage 8 — VOC Gate 脚本前置依赖设计反转

- **现象**：`build_voc_gate.py` 要求 `review_voc_package.json` 先存在，但实际流程应该先 gate → 用户导出 → package。
- **修复**：`review_voc_package.json` 改为可选依赖。Gate 仅基于 `asin_batch.json` 生成骨架 evidence packet + gate 判定。无 package 时默认 decision=`need_more_reviews`。

### [NOTE] · 已修复 — Stage 6 — fill_quick_packet_contract.py 不修复嵌套字段

- **现象**：`metric_basis` 子字段使用 `setdefault` 不覆盖空值；`category_boundary_clarity: "partial"` 等非标准枚举值未映射。
- **修复**：`metric_basis` 子字段改为直接赋值（覆盖空字符串）；新增 non-standard → 标准枚举值映射表（partial→moderate, unclear→weak, fuzzy→unknown）；枚举集合与 `quick_market_check.py` 对齐。测试覆盖：`FillContractNestedFixTests`。

### [NOTE] · 已修复 — Stage 8 — Agent prompt 目录与脚本期望不一致（深挖轮）

- **现象**：同 Issue #2（目录不一致），深挖轮同样问题。
- **修复**：Agent prompt 已在上一轮修正；另由 `build_deep_evidence_packet.py` 接管产出路径。

---

### 2026-06-25 — 前 8 项已修复

| # | 问题 | 修复 |
|---|---|---|
| 1 | Quick Agent 缺契约字段 | `scripts/fill_quick_packet_contract.py` + Agent prompt 补全字段清单 |
| 2 | 目录名不一致 | Agent prompt 统一为 `quick_check/` |
| 3 | 缺 workflow_state.json | `scripts/init_workflow_state.py` |
| 4 | 缺 quick_market_gate.json | `scripts/build_quick_market_gate.py` |
| 5 | MCP Snapshot 缺失 | Agent prompt 增加保存快照指令 |
| 6 | Sorftime API 不可用 | 降级为已知限制，prompt 中给出替代方案 |
| 7 | 双源冲突未标记 | `quick_market_check.py` 新增交叉校验逻辑 |
| 8 | 流程碎片化 | `scripts/run_pipeline.py` 端到端编排 |

### 新增测试覆盖

- `NewScriptImportTests`：4 个新脚本的导入性 + `fill_contract` 17字段补齐 + 原始内容保留
- `QuickGateCrossValidationTests`：`cross_validation` 字段存在性 + `support_level` 分歧检出
- `DeepSnapshotTests`：`build_deep_snapshot` 导入性 + 全部 15 字段补齐
- `DeepEvidencePacketTests`：`build_deep_evidence_packet` 导入性 + market_structure/search_demand packet 字段 + facts 回退
- `FillContractNestedFixTests`：`metric_basis` 子字段覆盖 + boundary 枚举映射
- `RouteMatrixForceConfirmTests`：force_confirm 选择逻辑 + blocker/先放弃 正确拒绝
- `ExtractEvidenceAsinsFallbackTests`：free-form facts ASIN 提取 + evidence_items 优先
- 全量 465 测试通过，0 回归

### Stage 5-8 修复总结

| # | 问题 | 修复 |
|---|---|---|
| 9 | 路线确认无人工入口 | `build_route_matrix_confirm.py --force-confirm` |
| 10 | 深挖目录名不一致 | Agent prompt 已修正 + `build_deep_evidence_packet.py` |
| 11 | snapshot 契约缺失 | `scripts/build_deep_snapshot.py` |
| 12 | evidence_items 结构不匹配 | `_scan_facts_for_asins()` 回退 |
| 13 | VOC gate 前置依赖反转 | `review_voc_package.json` 改为可选 |
| 14 | fill 脚本不修嵌套 | `metric_basis` 直接赋值 + 枚举映射表 |
| 15 | Agent prompt 与脚本目录不同 | Agent prompt 已修正 + `build_deep_evidence_packet.py` |

---

### [BLOCK] · 已修复 — Stage 2-3 — `price_band_health` 枚举值三层不一致

- **现象**：Agent prompt（healthy/watch/weak/unknown）、`fill_quick_packet_contract.py`（healthy/watch/weak/unknown）、`quick_market_check.py`（strong/moderate/weak/blocking/unknown）三层枚举不一致，Agent 输出 `"healthy"` → fill_script 放行 → validate_quick_packet 拒绝。
- **修复**（方案 A）：`fill_quick_packet_contract.py` 新增 `_price_health_map`（healthy→strong, watch→moderate, good→strong, poor→weak）；`PRICE_BAND_HEALTH` 集合与 `quick_market_check.py` 对齐为 `{strong, moderate, weak, blocking, unknown}`。与 `category_boundary_clarity` 的 `_boundary_map` 同模式。测试覆盖：`price_band_health_healthy_mapped_to_strong`、`price_band_health_watch_mapped_to_moderate`。

---

### [NOTE] · 已修复 — Stage 13 — QA 缺少 HTML vs XLSX 核心指标交叉比对

- **现象**：HTML 和 XLSX 各自溯源到 report_data.json 但可能取了不同字段，运营看到的两个文件数字不一致。
- **修复**：`delivery-qa-agent.md` 新增第 7 条阻断规则 "HTML 与 XLSX 核心指标不一致"。覆盖 8 个核心指标（ASIN 月销/价格、节点总容量、价格带占比、品牌/商品集中度等），含检查方法和常见根因排查。阻断规则从 6 条增至 7 条。

---

### [NOTE] · 已修复 — Stage 8 — 未自动创建 `inputs/reviews/` 目录及导出说明

- **现象**：Stage 8 生成 ASIN 清单后，用户不知道导出文件放哪里，需手工问、手工建目录。
- **修复**：`build_review_asin_batch.py` 在生成 `review_asin_batch.json` 后自动创建 `inputs/reviews/` 目录，写入 `README.txt`，包含 ASIN 清单（含角色和路线标注）、站点、导出要求（≥30条/ASIN，低分≥10条）、文件格式、命名建议和下一步命令。

---

### [NOTE] · 已修复 — Stage 8 — 主 Agent 未检查已有 Agent 就重复 spawn VOC Agent

- **现象**：另一个会话已 spawn VOC Evidence Agent 在跑，主 Agent 不知情又 spawn 了一个，两个 Agent 做重复工作。
- **修复**：`multi_agent_dispatch.md` 新增"## Spawn 去重规则"：spawn 前必须检查 `<teammate-message>` 中是否有同角色 Agent 的活跃通知，如有则用 `SendMessage` 继续而非新建。
- **发生时间**：2026-06-25
- **严重程度**：NOTE（浪费 token 但不影响数据正确性）

---

### [BLOCK] · 已修复 — Stage 10 — 资深运营分析 Agent 职责太薄，缺少深度解读

- **现象**：当前 Stage 10 Lead Operator Agent 只产出 `final_verdict` + `biggest_opportunity` + `biggest_risk` + `required_next_actions`，是决策摘要而非运营分析。
- **修复**：Lead Operator Agent 重写为深度运营分析角色，新增 6 个深度分析字段（`route_recommendation`、`competitor_benchmark`、`price_band_analysis`、`voc_to_spec`、`keyword_strategy`、`risk_mitigation`），明确要求回查原始证据包、解释维度间张力、做路线级拆解。同步更新：`lead-operator-agent.md`（重写）、`p7_contracts.py`（schema_version→v2 + 6 新字段校验）、`build_integrated_judgment.py`（6 个骨架构建函数）、`multi_agent_dispatch.md`（Stage 10 产物描述）、`SKILL.md`（Stage 10 完整字段表）。
- **发生时间**：2026-06-25
- **严重程度**：BLOCK（报告 Agent 越权分析会导致判断质量不稳定，QA 无法校验运营逻辑）

### [NOTE] · 已修复 — Stage 12 — Report Generation Agent 提示词仍含"自己分析"残留

- **现象**：`report-generation-agent.md` 中 Agent 职责包含"补充运营判断文字"、"优化判断类字段"、"使其更贴合实际数据、更有运营洞察"，隐含了 Agent 需要自己做运营分析的假设。
- **修复**：Report Generation Agent 重新定位为"呈现者"：输入新增 `integrated_operator_judgment.json` 作为判断权威来源，判断字段映射表明确"从 judgment 转录"的规则，删除"优化判断""补充洞察""以运营专家视角解读"等残留描述。三处修改：Agent 职责描述、输入表（新增 judgment 行）、第一步流程（优化→转录）、可以做清单。
- **发生时间**：2026-06-25
- **严重程度**：NOTE（Stage 10 升级后自然解决，但需同步修改以消除歧义）
