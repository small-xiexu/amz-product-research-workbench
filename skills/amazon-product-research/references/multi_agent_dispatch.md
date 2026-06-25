# 多 Agent 调度规则

本项目采用受控多 Agent：数据源专家 Agent 只产 Evidence Packet，资深运营专家 Agent 只产最终综合判断，Report Generation Agent 负责 `report_data.json` 与 HTML 报告，Delivery QA 检查交付边界。

## 调度表

| 阶段 | 是否 spawn | 触发条件 | Agent | 产物 |
|---|---|---|---|---|
| Stage 0-5 | 默认不 spawn | 常规交互推进 | 主 Agent 串行按专家口径执行 | `candidate_pool.json`、`route_matrix_confirm.json` |
| Stage 6 VOC | 可 spawn | 评论导出已导入，或路线多、样本多 | VOC Evidence Agent | `review_voc/voc_evidence_packet.json` |
| Stage 7 证据补齐 | 默认自动 spawn（如工具可用） | Search Demand、Market Structure 缺口明确 | Search Demand Agent、Market Structure Agent | `search_demand_evidence_packet.json`、`market_structure_evidence_packet.json` |
| Stage 7 冲突复核 | 不 spawn（脚本执行） | 双 evidence packet 齐全 | 脚本 `build_conflict_resolution_packet.py` | `conflict_review/conflict_resolution_packet.json` |
| Stage 7 多评价 | 可 spawn（6 个评价 Agent 可并行） | 全部 evidence packet + conflict packet 齐全 | 6 个 Evaluation Agent | `evaluations/*.json` + `evaluation_summary.json` |
| Stage 7 资深运营判断 | 可 spawn（推荐独立 spawn） | 6 份 evaluation + evaluation_summary 齐全 | Lead Operator Agent | `analysis/integrated_operator_judgment.json` |
| Stage 7 报告生成 | 不 spawn | seed、judgment、证据包齐全 | Report Generation Agent + 脚本跑 XLSX/QA | `analysis/report_data.json`、`<中文品名>_分析报告.html`、`<中文品名>_数据回表.xlsx` |
| Stage 7 交付 QA | **强制 spawn**（不可降级） | `report_data.json` + HTML 均已生成 | Delivery QA Agent | `analysis/qa_notes.md` |

## Stage 7 推荐顺序

1. Search Demand Agent：用 Sorftime 深扫类目、核心词、长尾词、P0/P1 ASIN 流量词、自然位和热销特征。
2. Market Structure Agent：用卖家精灵 Top100、ABA、关键词反查和市场分析整理市场结构证据。
3. 冲突复核脚本：`python3 -m packages.research_core.pipeline.build_conflict_resolution_packet <run_dir>` 生成 `conflict_review/conflict_resolution_packet.json`。
4. 6 个评价 Agent（可并行）：各自读对应证据包，输出 `evaluations/*.json` + `evaluation_summary.json`。
5. Lead Operator Agent：读 6 份 evaluation + evaluation_summary + 证据包 + conflict packet，输出 `analysis/integrated_operator_judgment.json`。
6. 脚本：运行 `build_analysis_report.py` 生成 `analysis/report_data.seed.json`。
7. Report Generation Agent：基于 seed、judgment 和证据包增强 `report_data.json`，再手写 `<中文品名>_分析报告.html`。
8. 脚本：再次运行 `build_analysis_report.py` 生成 XLSX + QA（脚本不生成 HTML、不重写 report_data）。
9. 脚本 QA：运行 `python3 scripts/run_delivery_qa.py <run_dir>` 检查文件完整性、source_path 溯源、禁止术语、冲突泄漏、P0 阻断。
10. Delivery QA Agent（**强制 spawn**）：交叉验证数据真实性（6 条阻断规则）和运营判断质量（8 条检查），写入 `analysis/qa_notes.md`。
11. QA 修复循环：若 QA 发现阻断项 → 主 Agent 调度 Report Generation Agent 修复 → 重新脚本 QA + Agent QA，最多 3 轮。3 轮后仍 BLOCKED → 需人工介入。

## 降级规则

如果运行环境没有真实子 Agent 工具、子 Agent 执行失败，或用户明确要求串行，允许主 Agent 按同一 Agent 口径串行执行，并必须在 `execution_provenance`、`run_status_audit` 和 QA 结果中标明 `serial_fallback`。

降级不代表不能交付，但报告必须说明：

- 哪些证据是真实工具/脚本产出。
- 哪些证据是主 Agent 串行整理。
- 哪些数据缺口会影响市场机会判断。

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

- Search Demand / Market Structure / VOC Evidence Agent 不输出最终路线优先级。
- Senior Operator Agent 不生成 HTML，不写 `report_data.json`。
- Report Generation Agent 不重算 P7 判断，不新增证据包外数字。
- 专家 Agent 不新增原始数字；所有关键数字必须来自 Evidence Packet。
- Delivery QA Agent **不改判断、不改数据、不写 report_data.json/HTML/XLSX**，只写 `qa_notes.md`。
- Delivery QA Agent **不可降级为 serial_fallback**，必须独立 spawn。

## 输出边界

用户版报告只展示业务语言，不展示 Agent、MCP、tool、spawn、packet 等内部术语。内部 Evidence Packet 可以保留执行来源和工具参数，供 QA 与后续恢复使用。
