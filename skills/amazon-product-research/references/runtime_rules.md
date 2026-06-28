# Shared Agent Runtime Rules

Claude Code 和 Codex 都必须遵守本文件。`AGENTS.md`、`CLAUDE.md` 只是平台入口；本文件才是共同运行时规则事实源。

## 语言与角色

- 始终使用简体中文回复。
- 默认站在资深亚马逊运营和工程协作视角。
- 项目当前只判断“市场能不能做”，不延伸到供应链、1688、利润核算或投放落地。

## 事实源顺序

| 类型 | 路径 | 规则 |
|---|---|---|
| 主流程 | `skills/amazon-product-research/SKILL.md` | 唯一主流程事实源 |
| Agent 规则 | `skills/amazon-product-research/agents/*.md` | 完整职责、禁止项、输入输出事实源 |
| 调度清单 | `skills/amazon-product-research/agent_manifest.json` | 只存运行时路由元数据，不承载完整业务定义 |
| 契约 | `skills/amazon-product-research/references/CONTRACT_MAP.md` | Agent 写 JSON 前必须对齐 |
| 调度规则 | `skills/amazon-product-research/references/multi_agent_dispatch.md` | spawn、并行、降级与 QA 修复规则 |
| 生成适配 | `.claude/agents/`、`.codex/agents/`、`.agents/skills/` | 开箱自动发现用，均为生成物 |

Claude/Codex 适配文件只服务运行时发现。业务规则变更必须改 canonical Skill 或 Agent 源文档，再运行 `python3 scripts/generate_agent_adapters.py`。

## 多 Agent 边界

- 主 Agent 负责推进流程、调度子 Agent、运行校验、更新进度。
- Evidence Agent 只产证据、缺口和置信度，不输出最终 Go/No-Go。
- Evaluation Agent 只评分、列风险和给 route_breakdown，不输出最终判断。
- Lead Operator Agent 是唯一有权输出最终放行判断的 Agent。
- Report Generation Agent 只转录已完成判断并写报告，不新增证据包外数字。
- Delivery QA Agent 只检查，不改判断、不改数据、不写正式报告。

## 脚本边界

- 脚本负责契约校验、确定性生成、seed、XLSX、QA、断点审计。
- 脚本不得替代 Agent 产出候选池、路线矩阵、最终判断或正式 HTML 报告。
- `run_report_agent.py` 只作为本地开发辅助，不是正式交付入口。
- Agent 适配文件由 `scripts/generate_agent_adapters.py` 生成，不手改。

## 通用硬编码红线

- 通用脚本、报告模板、Agent、Skill、Schema、QA 和文档不得写死任何特定品类的 ASIN、关键词、产品形态、供应商、品牌、卖家或价格。
- 本轮真实事实只能进入 `runs/<run_id>/`、测试样例、fixture 或明确标注的历史附录。
- 示例只能服务测试或附录，不能进入通用判断逻辑。
- 如确需保留特殊示例，必须在相邻行添加 `generic-redline: allow` 并说明原因。

## 计划与进度

- 当任务引用实施计划、plan、checklist 或 `docs/**/plans/*.md` 时，计划文件是唯一进度台账。
- 每完成一个可独立验收的事项，必须立即回写计划。
- 未验证的事项禁止勾选完成。
- 新会话恢复时，先读计划文件，再看代码现状。

## 开发完成必跑

修改以下范围后必须运行通用红线扫描：

- `packages/**`
- `scripts/**`
- `skills/**`
- `docs/**` 中的核心契约、规范和非历史计划文档
- `tests/**` 中影响通用逻辑或 fixture 的内容

推荐完整校验：

```bash
scripts/dev_verify.sh
```

至少必须通过：

```bash
python3 scripts/check_generic_redlines.py --token-file tests/fixtures/generic_redline_tokens.json --no-auto-run-dir
```

## Git 约束

- 不要自动提交，除非用户明确要求提交代码。
- 不要回滚用户或其他工具已有改动。
