# 多 Agent 调度规则

本项目采用受控多 Agent：数据源专家 Agent 只产 Evidence Packet，评价 Agent 只打分，资深运营专家 Agent 只产最终综合判断，Report Generation Agent 负责 `report_data.json` 与 HTML 报告，Delivery QA Agent 检查交付边界。

## 阶段依赖链

```
Stage 1 (意图收集) → Stage 2-3 (快验+门控) → Stage 4 (候选池) → Stage 5 (路线确认)
    → Stage 6 (双MCP深挖) → Stage 7 (冲突复核) → Stage 8 (VOC)
    → Stage 9 (六维评价) → Stage 10 (资深判断) → Stage 11 (seed)
    → Stage 12 (报告生成) → Stage 13 (QA)
```

- 每个阶段 done 后才能进入下一阶段。
- Stage 9 依赖 Stage 6、7、8 全部 done。
- Stage 10 依赖 Stage 9 done。
- Stage 12 依赖 Stage 10、11 done。
- Stage 13 依赖 Stage 12 done。

## 调度表

| 阶段 | spawn | 触发条件 | Agent | 产物 |
|---|---|---|---|---|
| Stage 1 意图收集 | 不 spawn | 主 Agent 主动推进 | 主 Agent | `workflow_state.json`、`progress.json` |
| Stage 2-3 快验+门控 | **强制并行 spawn** | Stage 1 done | 卖家精灵 Quick Agent、Sorftime Quick Agent | `sellersprite_quick_evidence_packet.json`、`sorftime_quick_evidence_packet.json`、`quick_market_gate.json` |
| Stage 4 候选池 | 不 spawn | Stage 3 gate=continue/watch | 主 Agent 产出 candidate_pool.json → 脚本 `build_mcp_candidate_pool.py` 合约校验 | `candidate_pool.json` |
| Stage 5 路线确认 | 不 spawn | Stage 4 done + 运营确认 | 主 Agent 产出 route_matrix_confirm.json → 脚本 `build_route_matrix_confirm.py` 合约校验 + `data_completeness_check.json` | `route_matrix_confirm.json`、`data_completeness_check.json` |
| Stage 6 双 MCP 深挖 | **强制并行 spawn** | Stage 5 done | Market Structure Agent、Search Demand Agent | `market_structure_evidence_packet.json`、`search_demand_evidence_packet.json` |
| Stage 7 冲突复核 | 不 spawn（脚本执行） | Stage 6 done | 脚本 `build_conflict_review.py` | `conflict_resolution_packet.json` |
| Stage 8 VOC | **强制 spawn** | Stage 7 done + 运营导出评论 | VOC Evidence Agent + 脚本 `build_review_voc_package.py`、`build_voc_gate.py` | `voc_gate.json`、`review_voc_package.json`、`voc_evidence_packet.json` |
| Stage 9 六维评价 | **推荐并行 spawn** | Stage 6、7、8 全部 done | 6 个 Evaluation Agent | `evaluations/*.json`、`evaluation_summary.json` |
| Stage 10a 深度分析 | **强制并行 spawn** | Stage 9 done | Route Strategy Agent、Growth & Risk Agent | `integrated_operator_judgment.json` 的 9 个深度分析字段（路线推荐/路线取舍/竞品对标/竞品弱点/价格带解读 — Route Strategy；VOC→规格/关键词策略/风险缓解/验证路线图 — Growth & Risk） |
| Stage 10b 决策合成 | **推荐独立 spawn** | Stage 10a done | Lead Operator Agent（跨维度权衡 + 最终决策） | `integrated_operator_judgment.json`（决策摘要 + 合并 10a 的 9 个深度分析字段） |
| Stage 11 seed | 不 spawn（脚本执行） | Stage 10 done | 脚本 `build_report_seed.py` | `report_data.seed.json` |
| Stage 12 报告生成 | **推荐独立 spawn** | Stage 10b + Stage 11 done | Report Generation Agent 写 `report_data.json` + HTML；脚本只生成 XLSX/QA | `report_data.json`、`<中文品名>_分析报告.html`、`<中文品名>_决策工具包.xlsx` |
| Stage 13 QA | **强制 spawn**（不可降级） | Stage 12 done | Delivery QA Agent + 脚本 `run_delivery_qa.py` | `delivery_qa_result.json`、`qa_notes.md` |

## Stage 2-3 快验并行规则

卖家精灵 Quick Agent 和 Sorftime Quick Agent 必须同时启动，互不依赖。两方都完成后 Quick Gate 合并判定。

| Quick Agent | 数据源 | 职责 | 禁止 |
|---|---|---|---|
| 卖家精灵 Quick Agent | 卖家精灵 MCP | 大盘容量、候选类目、价格带、集中度、Review 门槛。**强制：发现 ALL 子方向 + 每方向挖 6-8 参考 ASIN（≥3 品牌、≥2 价格段）** | 不写最终 Go/No-Go、不替 Sorftime 判断搜索需求 |
| Sorftime Quick Agent | Sorftime MCP | 关键词搜索量、搜索意图、混池、候选类目、类目趋势。**强制：每方向独立采词 + 每方向挖 6-8 参考 ASIN（≥3 品牌、≥2 价格段）** | 不写最终 Go/No-Go、不用关键词搜索量替代市场销量 |

## Stage 6 深挖并行规则

Market Structure Agent 和 Search Demand Agent 必须同时启动，互不依赖。深挖比快验更完整，覆盖全量 Top100、完整关键词分层、类目趋势。

**路线分片规则**：保留路线 > 8 条时，单 Agent 无法在上下文中完成全部深挖，必须分片：
- 将路线按每组 4-5 条拆成 2-3 组
- 同一 Agent 角色串行执行各组分片：Agent A 完成第一组 → Agent B 继续第二组 → ...
- 每个分片 Agent 写入独立的 `route_breakdown_{group}.json` 片段（如 `route_breakdown_01.json`、`route_breakdown_02.json`）
- 全部分片完成后，由脚本 `build_deep_evidence_packet.py` 合并成完整 evidence packet
- 路线 ≤ 8 条时仍可单 Agent 执行

**快照规则**：Agent 写入 evidence packet 的同时，**必须使用 Write 工具**将本 Agent 所有 MCP tool_calls + tool_results 完整写入快照：
- Market Structure → `mcp_snapshots/sellersprite_deep_snapshot.json`
- Search Demand → `mcp_snapshots/sorftime_deep_snapshot.json`
- Agent 必须在每次 MCP 调用后立即记录 call 元信息和 result 摘要，全部完成后用 Write 工具一次性写入
- 快照缺失 → Stage 13 QA 硬阻断，不得用 `snapshot_unavailable` 降级绕过

## Stage 9 六维评价并行规则

6 个 Evaluation Agent 可全部并行启动，各自读取对应证据包：

| Agent | 读取 | 输出 |
|---|---|---|
| Market Demand Evaluation Agent | 市场结构 + 搜索需求证据 | `market_demand_evaluation.json` |
| Competition Evaluation Agent | 市场结构证据 | `competition_evaluation.json` |
| Price Band Opportunity Evaluation Agent | 市场结构证据 | `price_profit_evaluation.json` |
| VOC Opportunity Evaluation Agent | VOC 证据 | `voc_opportunity_evaluation.json` |
| Risk Evaluation Agent | 全部证据 + 冲突复核 | `risk_evaluation.json` |
| Data Quality Evaluation Agent | 全部证据 + MCP snapshot + 冲突复核 | `data_quality_evaluation.json` |

全部完成后由脚本 `build_evaluation_summary.py` 生成 `evaluation_summary.json`。

## Spawn 去重规则

spawn 任何 Agent 前，主 Agent 必须先检查 `<teammate-message>` 中是否已有同角色 Agent 的活跃通知（含 `idle_notification`）。若已有同角色 Agent 在运行，必须用 `SendMessage` 继续已有 Agent，不得重复 spawn。

同一阶段同一角色 Agent 只允许一个实例。

## 降级规则

运行环境不支持真实子 Agent、子 Agent 执行失败，或用户明确要求串行时，允许主 Agent 按同一 Agent 口径串行执行，并必须在 `execution_provenance` 和 QA 结果中标明 `serial_fallback`。

降级不代表不能交付，但报告必须说明：
- 哪些证据是真实工具/脚本产出。
- 哪些证据是主 Agent 串行整理。
- 哪些数据缺口会影响市场机会判断。

不可降级的阶段：
- **Stage 2-3 快验**：可降级，两 Quick Agent 变为主 Agent 串行执行
- **Stage 6 深挖**：可降级，两 Agent 变为主 Agent 串行执行
- **Stage 9 六维评价**：可降级，6 Agent 变为主 Agent 逐个串行执行
- **Stage 10 资深判断**：可降级，变为资深运营专家角色提示词在主 Agent 内执行
- **Stage 13 QA**：**不可降级**，必须独立 spawn。环境不支持 spawn 时标记 `blocked`，不得以主 Agent 自检替代

## Stage 13 推荐执行顺序

1. 脚本 QA：`python3 scripts/run_delivery_qa.py <run_dir>` — 检查文件完整性、source_path 溯源、禁止术语、冲突泄漏、P0 阻断。
2. Delivery QA Agent（**强制 spawn**）：交叉验证数据真实性（7 条阻断规则）和运营判断质量（8 条检查），写入 `analysis/qa_notes.md`。
3. QA 修复循环：若 QA 发现阻断项 → 主 Agent 调度 Report Generation Agent 修复 → 重新脚本 QA + Agent QA，最多 3 轮。3 轮后仍 BLOCKED → `progress.json` 标记 `blocked`，需人工介入。

## QA 修复循环

Delivery QA Agent 发现阻断项后，主 Agent 调度 Report Generation Agent 修复并重新 QA，而非跳过。流程：

```
脚本 QA (run_delivery_qa.py)
  → Agent QA（强制 spawn）
    → 阻断项？→ 主 Agent 读取 qa_notes.md，调度 Report Generation Agent 修复
    → Report Generation Agent 重写 report_data.json / HTML
    → 重新脚本 QA + Agent QA（最多 3 轮）
    → 3 轮仍 BLOCKED → 标记"需人工介入"，写入 qa_notes.md
```

修复循环规则：
- 主 Agent 不直接修改 report_data.json 或 HTML，只负责读取 qa_notes.md 并调度。
- 修复工作由 Report Generation Agent 执行（它是唯一写入 report_data.json 和 HTML 的角色）。
- 每轮 Agent QA 必须从零开始重新检查所有项（不缓存上一轮结果）。
- 修复后必须同时重跑脚本 QA 和 Agent QA。
- 不允许在阻断项未清除的情况下标记交付完成。

## 越权规则

- 卖家精灵 Quick Agent / Sorftime Quick Agent 不输出最终 Go/No-Go，不写正式报告。
- Search Demand / Market Structure / VOC Evidence Agent 不输出最终路线优先级。
- 6 个 Evaluation Agent 只打分和列风险，不输出最终 Go/No-Go。
- Lead Operator Agent 不生成 HTML，不写 `report_data.json`。
- Report Generation Agent 不重算判断，不新增证据包外数字。
- 专家 Agent 不新增原始数字；所有关键数字必须来自 Evidence Packet。
- Delivery QA Agent **不改判断、不改数据、不写 report_data.json/HTML/XLSX**，只写 `qa_notes.md`。
- Delivery QA Agent **不可降级为 serial_fallback**，必须独立 spawn。

## 输出边界

用户版报告只展示业务语言，不展示 Agent、MCP、tool、spawn、packet 等内部术语。内部 Evidence Packet 可以保留执行来源和工具参数，供 QA 与后续恢复使用。

## 工程约束（所有 Agent 强制遵守）

所有 spawn Agent 必须遵守以下工程约束，违反即视为 Agent 执行失败，需打回重做：

### 文件写入

- **写入任何文件必须使用 Write 工具**（或 Edit 工具做增量修改）。
- **禁止**使用 `bash -c "cat << 'EOF' > file.json"`、`bash -c "python3 << 'PYEOF'"` 或任何 heredoc 内联方式写入文件。
- **禁止**使用 `echo`、`printf` 拼接多行内容后管道写入文件。

原因：heredoc 内联在中文引号、特殊字符、缩进嵌套场景下极易产生 bash 转义错误，导致文件写入不完整或 Agent 死循环重试。

### Python 脚本执行

- 需要运行 Python 脚本时，必须**先用 Write 工具将脚本写入 `/tmp/` 目录**，再用 `Bash` 工具执行 `python3 /tmp/script_name.py`。
- **禁止**使用 `bash -c "python3 << 'PYEOF' ... PYEOF"` 或 `python3 -c "..."` 内联超过 5 行的 Python 代码。
- 临时脚本用完后可删除，不做长期维护要求。

### JSON 产出

- 所有 JSON 产出必须通过 Write 工具写入目标路径（run_dir 下的正式产物）或通过脚本写入（由 Write-to-/tmp/ 的脚本执行）。
- **禁止**在 Agent 输出文本中直接打印 JSON 并期望主 Agent 代为写入。
