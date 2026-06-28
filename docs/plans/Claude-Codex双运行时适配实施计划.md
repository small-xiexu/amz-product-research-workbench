# Claude/Codex 双运行时适配实施计划

当前目标：让同一套亚马逊选品多 Agent 项目同时适配 Claude Code 与 Codex。业务事实源仍然只保留一份：`skills/amazon-product-research/`；`.claude/agents/`、`.codex/agents/`、`.agents/skills/` 都是运行时适配层。

## 事实源与适配层

| 层 | 路径 | 职责 |
|---|---|---|
| 项目总规则 | `AGENTS.md` / `CLAUDE.md` | 分别给 Codex / Claude Code 注入项目铁律 |
| 主流程事实源 | `skills/amazon-product-research/SKILL.md` | 13 阶段主流程、暂停点、校验门禁 |
| Agent 事实源 | `skills/amazon-product-research/agents/*.md` | 每个业务 Agent 的职责、输入输出、越权边界 |
| Agent 清单 | `skills/amazon-product-research/agent_manifest.json` | 平台无关元数据，驱动双端适配生成 |
| 共享运行时规则 | `skills/amazon-product-research/references/runtime_rules.md` | Claude/Codex 根入口共同引用的项目铁律 |
| Claude 适配 | `.claude/agents/*.md` | Claude Code 项目级 subagents |
| Codex 适配 | `.codex/agents/*.toml` | Codex 项目级 custom agents |
| Codex Skill 适配 | `.agents/skills/amazon-product-research/SKILL.md` | Codex repo-scoped skill 入口 |

## 开发清单

- [x] P0-1 创建本实施计划文档
  - 验收：已创建本文件，作为本轮双运行时适配的唯一进度台账。
- [x] P0-2 补齐 `AGENTS.md` 与 `CLAUDE.md`
  - 验收：已新增两端根规则入口，均指向同一套 Skill、Agent、契约与调度事实源。
- [x] P0-3 建立平台无关 `agent_manifest.json`
  - 验收：已新增 `skills/amazon-product-research/agent_manifest.json`，覆盖 16 个业务 Agent 角色和生成适配所需元数据。
- [x] P1-1 实现 `scripts/generate_agent_adapters.py`
  - 验收：生成器已可从 manifest + Agent 源文档生成 Claude/Codex 适配文件和 Codex Skill 入口，并支持 `--check` 防漂移。
- [x] P1-2 生成 `.claude/agents/*.md`
  - 验收：已生成 16 个 Claude Code 项目级 subagent 文件，均带 source hash 与 canonical instructions。
- [x] P1-3 生成 `.codex/agents/*.toml`
  - 验收：已生成 16 个 Codex custom agent TOML 文件，均带 source hash 与 `developer_instructions`。
- [x] P1-4 生成 `.agents/skills/amazon-product-research/SKILL.md`
  - 验收：已生成 Codex repo skill 入口，指向 canonical skill，不复制第二份业务事实源。
- [x] P1-5 新增同步校验测试
  - 验收：已新增 `tests/test_agent_adapter_sync.py`，覆盖 manifest、生成文件、source hash、Codex Skill 入口与根规则入口；单测通过。
- [x] P1-6 修正文档现存不一致
  - 验收：已统一 README 的 16 个 Agent 口径，并修正 Growth & Risk 为 4 字段；残留检索无命中。
- [x] P2-1 运行验证
  - 验收：`python3 -m unittest tests.test_agent_adapter_sync -v` 通过；`scripts/dev_verify.sh` 通过，446 个测试 OK、2 个 skip；`python3 scripts/generate_agent_adapters.py --check` 通过；通用红线扫描 OK。
- [x] P2-2 固化开箱自动发现策略
  - 验收：`.gitignore` 只忽略 `.claude/settings.local.json`、`.claude/reviews/`、`.claude/worktrees/`；`.claude/agents`、`.codex/agents`、`.agents/skills` 保持可提交；同步测试新增防误忽略检查并通过。
- [x] P2-3 抽出共享运行时规则，瘦身 `AGENTS.md` / `CLAUDE.md`
  - 验收：已新增 `skills/amazon-product-research/references/runtime_rules.md`；`AGENTS.md` / `CLAUDE.md` 只保留平台入口、启动顺序和跳转，不再重复维护多 Agent 边界、脚本边界和红线规则。
- [x] P2-4 降低 manifest 自然语言漂移风险
  - 验收：manifest 增加 `manifest_scope=runtime_routing_only` 和 `description_policy`；Agent 选择摘要字段改为 `routing_hint`；生成器强制嵌入 source 正文与 hash；测试校验 manifest 不再使用 `description` 作为业务摘要字段。

## 验收标准

1. Claude Code 能从 `.claude/agents/` 发现项目级 subagents。
2. Codex 能从 `.codex/agents/` 发现项目级 custom agents。
3. Codex 能从 `.agents/skills/amazon-product-research/SKILL.md` 触发 repo skill。
4. 双端适配文件均由生成脚本产出，包含源文件 hash，测试能发现漂移。
5. 根目录 `AGENTS.md` 与 `CLAUDE.md` 都明确脚本边界：Agent 做判断，脚本做校验、确定性生成和 QA。
6. 全仓红线扫描通过，不引入任何特定品类、ASIN、关键词、品牌、卖家或价格硬编码。
7. 开箱自动发现优先：`.claude/agents/`、`.codex/agents/`、`.agents/skills/` 不整体 gitignore；只忽略本地配置、review/worktree 状态和缓存。
8. `AGENTS.md` 和 `CLAUDE.md` 不重复维护大段规则，只引用共享运行时规则。
9. manifest 不承载完整业务定义；完整职责、禁止项和判断边界必须来自对应 Agent 源文档。
