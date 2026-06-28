# AGENTS.md

Codex 项目入口。共同运行时规则见 `skills/amazon-product-research/references/runtime_rules.md`，必须先遵守该文件。

## Codex 启动顺序

1. 读取 `skills/amazon-product-research/references/runtime_rules.md`。
2. 需要启动选品流程时，读取 `.agents/skills/amazon-product-research/SKILL.md`，再回到 `skills/amazon-product-research/SKILL.md`。
3. 需要调度子 Agent 时，优先使用 `.codex/agents/*.toml` 注册文件；完整职责以 `skills/amazon-product-research/agents/*.md` 为准。
4. Agent 写 JSON 前必须对照 `skills/amazon-product-research/references/CONTRACT_MAP.md`。

不要自动提交代码。不要回滚用户或其他工具已有改动。
