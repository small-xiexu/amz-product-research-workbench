# Seller Sprite Product Research

亚马逊选品全流程的 Skill 骨架。

## 当前状态

只做流程、规则、数据结构和报告骨架，不包含实际 MCP 调用实现。

## 目录

| 路径 | 作用 |
|---|---|
| `SKILL.md` | Skill 主入口，定义流程、规则、输入输出 |
| `references/` | 工具映射、数据包结构、决策规则、输出结构 |
| `agents/` | 后续拆分的数据管道和洞察职责 |

## 目标

- 用卖家精灵 MCP 跑通 V1 选品初筛闭环。
- 生成 `research_package`、Excel 数据底表、报告、摘要、HTML 看板。
- 预留评论插件、网页工作台和后续应用演进空间。
