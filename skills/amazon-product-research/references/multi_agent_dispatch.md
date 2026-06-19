# 多 Agent 受控调度规范

本规范定义什么时候把 `agents/*.md` 角色升级为真实子 Agent。目标是并行专业判断，而不是让每一步都自动开 Agent。

## 调度原则

- 默认由主 Agent 串行推进 Stage 0-5，避免方向未定时产生多余分支。
- 只有运行环境存在可用子 Agent 工具时，才允许真实 spawn；否则按对应 agent 文件的角色口径由主 Agent 串行执行。
- 子 Agent 只产 Evidence Packet，不直接输出 Go/Wait/No-Go。
- Lead Operator Agent 只在 Evidence Packet 完成后整合判断。
- 每个子 Agent 的任务必须给出明确输入文件、输出文件和禁止越权事项。
- 子 Agent 不应修改原始导出文件；写入范围限制在自己的 Evidence Packet 或对应分析目录。

## 阶段触发

| 阶段 | 默认方式 | 真实 spawn 条件 | 子 Agent | 输出 |
|---|---|---|---|---|
| Stage 0-1 意图/快探 | 主 Agent 串行 | 不 spawn | 无 | 候选假设卡、Sorftime 快探 |
| Stage 2-3 导出/导入 | 脚本 + 主 Agent | 不 spawn | Data Pipeline 口径即可 | `import_manifest.json`、`candidate_pool.json` |
| Stage 4-5 路线矩阵 | 主 Agent 串行 | 不 spawn，除非路线多且用户要求并行 | 可选 Explorer | `route_matrix_confirm.*` |
| Stage 6 评论 VOC | 优先 spawn | `review_voc_package.json` 存在且有效评论 >= 30 | VOC Evidence Agent | `review_voc/voc_evidence_packet.json` |
| Stage 7 综合预审 | 必须 spawn 数据源 Agent | 路线矩阵确认，VOC 已完成或缺口明确，且已有 Sorftime/卖家精灵/1688 任一后续数据 | Search Demand Agent、Market Structure Agent、VOC Evidence Agent、Supply Chain Agent、Report Writer、Delivery QA Agent | `analysis/analysis_report.html`、`analysis/analysis_report.xlsx`、`analysis/analysis_evidence_packet.json` |
| Stage 8 利润/合规 | 优先 spawn | 利润或合规模板已回填，或需要生成待补清单 | Profit Compliance Agent | `profit_compliance/profit_compliance_evidence_packet.json` |
| 最终报告前 QA | 优先 spawn | `analysis/*`、`final_report/*` 或 `research_package.json` 已生成 | Delivery QA Agent | `analysis/delivery_qa_result.json` 或 `final_report/delivery_qa_result.json` |
| 最终决策 | 主 Agent | 不 spawn；由主 Agent 执行 Lead Operator 口径 | Lead Operator Agent | `integrated_operator_judgment`、对话结论 |

## 推荐并行组合

当 Stage 6 已完成且路线仍为“继续看”时，Stage 7 必须围绕综合预审报告组织并行：

1. Search Demand Agent：用 Sorftime 深扫类目、核心词、长尾词、P0/P1 ASIN 流量词、自然位、热销特征和 1688 粗采购信号。
2. Market Structure Agent：用卖家精灵验证 Top100、ABA、关键词反查、价格带、评论门槛和新品信号。
3. VOC Evidence Agent：把评论痛点翻译成产品规格、样品测试项和供应链验证项。
4. Supply Chain Agent：用 1688 插件和 Sorftime 1688 信号验证可供应形态、候选款、采购价、MOQ、混池和可承接规格。
5. Lead Operator Agent：只在上述证据完成后，以资深亚马逊运营专家身份生成 `analysis_evidence_packet.json`。
6. Report Writer：把主 Agent 结论渲染成 `analysis_report.html` 和 `analysis_report.xlsx`。
7. Delivery QA Agent：检查报告完整性、证据边界、硬缺口和是否过度推荐。

不要让多个子 Agent 写同一个文件。若需要统一汇总，由主 Agent 在子 Agent 完成后读取各自 Evidence Packet 生成综合判断。

Stage 7 真实多 Agent 的最小合格形态是四个数据源 Agent 都有独立 Evidence Packet。尤其是 Sorftime 深扫必须由 Search Demand Agent 子 Agent 执行，主 Agent 不能因为自己可以调用 MCP 就静默代跑。主 Agent 只负责派发、等待/整合和最终 Lead Operator 判断。

如果运行环境支持子 Agent，但 Search Demand Agent 没有真实执行记录，Delivery QA 必须标记为待补；这类报告最多作为临时草稿，不作为正式 Stage 7 交付。

Profit Compliance Agent 不属于 Stage 7 必跑项；它只在 Stage 8 利润/FBA/合规字段回填后启动。Stage 7 只负责列出利润待回填字段和进入 Stage 8 的条件。

## 子 Agent Prompt 必含内容

每次 spawn 子 Agent 时，主 Agent 必须在任务说明中包含：

- 当前 run 目录绝对路径。
- 需要读取的 agent 定义文件路径。
- 输入文件路径。
- 允许写入的输出文件路径。
- 禁止修改原始导出、禁止给最终 Go/No-Go。
- Evidence Packet 必须符合 `references/evidence_packet_contract.md`。
- 若证据不足，输出 `data_gaps`，不要编造结论。
- Stage 7 数据源 Agent 必须写入 `execution_provenance`，标明是否 `real_subagent_spawn`、子 Agent ID、补跑/降级说明。

## 降级执行

如果运行环境没有子 Agent 工具、用户要求不使用多 Agent，或任务太小不值得 spawn：

- 主 Agent 可以读取对应 agent 文件，按角色口径串行产出 Evidence Packet。
- 必须在最终说明中写清楚“本轮未启动独立子 Agent，仅按该角色口径执行”。
