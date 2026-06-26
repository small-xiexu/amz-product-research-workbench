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
| Stage 4 候选池 | 不 spawn | Stage 3 gate=continue | 主 Agent 产出 candidate_pool.json → 脚本 `build_mcp_candidate_pool.py` 合约校验 | `candidate_pool.json` |
| Stage 5 路线确认 | 不 spawn | Stage 4 done + 运营确认 | 主 Agent 产出 route_matrix_confirm.json → 脚本 `build_route_matrix_confirm.py` 合约校验 + `data_completeness_check.json` | `route_matrix_confirm.json`、`data_completeness_check.json` |
| Stage 6 双 MCP 深挖 | **强制并行 spawn** | Stage 5 done | Market Structure Agent、Search Demand Agent | `market_structure_evidence_packet.json`、`search_demand_evidence_packet.json` |
| Stage 7 冲突复核 | 不 spawn（脚本执行） | Stage 6 done | 脚本 `build_conflict_review.py` | `conflict_resolution_packet.json` |
| Stage 8 VOC | 推荐 spawn | Stage 7 done + 运营导出评论 | VOC Evidence Agent + 脚本 `build_review_voc_package.py` | `voc_gate.json`、`review_voc_package.json`、`voc_evidence_packet.json` |
| Stage 9 六维评价 | **推荐并行 spawn** | Stage 6、7、8 全部 done | 6 个 Evaluation Agent | `evaluations/*.json`、`evaluation_summary.json` |
| Stage 10a 深度分析 | **强制并行 spawn** | Stage 9 done | Route Strategy Agent、Growth & Risk Agent | `integrated_operator_judgment.json` 的 10 个深度分析字段（路线推荐/路线取舍/竞品对标/竞品弱点/价格带解读 — Route Strategy；VOC→规格/关键词策略/风险缓解/冷启动/验证路线图 — Growth & Risk） |
| Stage 10b 决策合成 | **推荐独立 spawn** | Stage 10a done | Lead Operator Agent（跨维度权衡 + 最终决策） | `integrated_operator_judgment.json`（决策摘要 + 合并 10a 的 10 个深度分析字段） |
| Stage 11 seed | 不 spawn（脚本执行） | Stage 10 done | 脚本 `build_analysis_report.py` | `report_data.seed.json` |
| Stage 12 报告生成 | 不 spawn | Stage 10 + 11 done | Report Generation Agent + 脚本 | `report_data.json`、`<中文品名>_分析报告.html`、`<中文品名>_决策工具包.xlsx` |
| Stage 13 QA | **强制 spawn**（不可降级） | Stage 12 done | Delivery QA Agent + 脚本 `run_delivery_qa.py` | `delivery_qa_result.json`、`qa_notes.md` |

## Stage 2-3 快验并行规则

卖家精灵 Quick Agent 和 Sorftime Quick Agent 必须同时启动，互不依赖。两方都完成后 Quick Gate 合并判定。

| Quick Agent | 数据源 | 职责 | 禁止 |
|---|---|---|---|
| 卖家精灵 Quick Agent | 卖家精灵 MCP | 大盘容量、候选类目、价格带、集中度、Review 门槛 | 不写最终 Go/No-Go、不替 Sorftime 判断搜索需求 |
| Sorftime Quick Agent | Sorftime MCP | 关键词搜索量、搜索意图、混池、候选类目、类目趋势 | 不写最终 Go/No-Go、不用关键词搜索量替代市场销量 |

## Stage 6 深挖并行规则

Market Structure Agent 和 Search Demand Agent 必须同时启动，互不依赖。深挖比快验更完整，覆盖全量 Top100、完整关键词分层、类目趋势。

## Stage 9 六维评价并行规则

6 个 Evaluation Agent 可全部并行启动，各自读取对应证据包：

| Agent | 读取 | 输出 |
|---|---|---|
| Market Demand Evaluation Agent | 市场结构 + 搜索需求证据 | `market_demand_evaluation.json` |
| Competition Evaluation Agent | 市场结构证据 | `competition_evaluation.json` |
| Price Profit Evaluation Agent | 市场结构证据 | `price_profit_evaluation.json` |
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
