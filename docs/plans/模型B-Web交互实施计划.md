# 模型 B · Web 交互式选品工作台实施计划

更新日期：2026-06-13

承接架构优化三轮重构。目标：把"运营 ↔ AI 多轮交互产出选品报告"的核心体验搬到本地网页，AI 真正住进产品（接 LLM API），后端复用现有 `packages/`。

## 锁定决策

1. **多 Provider**：Claude + GPT，网页可配置 Provider / 模型 / API key（key 只存后端）
2. **本地运行**：docker-compose（`server` + `webapp`），API key 走 `.env`
3. **Monorepo**：当前仓库加 `server/`（FastAPI）+ `webapp/`（Next.js + Tailwind + shadcn/ui）

## 核心机制

LLM 的 **tool use（函数调用）**驱动现有 `pipeline/` 函数：Claude/GPT 在对话循环里决定调哪个工具 / 让运营上传什么 / 何时暂停决策；后端执行工具并回喂结果。`interactive_workflow` 作为阶段状态机大脑。

## 关键约束（必须体现在设计里）

- **两种模式**（无方向探索 / 指定方向深挖）都必须经过卖家精灵手动导入；模式由 AI 根据运营对话自动识别并写入 `workflow_state`，不在网页上要求运营手动选择
- **工具分两类**：A 类 AI 可自动执行（inspect/build/validate/Sorftime）；B 类"请运营操作"动作卡（卖家精灵导出上传、评论上传、利润/合规填写、Go/Wait/No-Go 决策）
- **文件上传是一等公民**：由 AI 动作卡带上下文触发，上传后自动跑 `inspect_manual_exports` 盘点
- **评论插件第三档整合**：AI 判断需要 VOC 后创建评论采集任务；自有 Chrome 评论插件领取任务、慢速采集并回传评论 JSON；Excel/HTML 导入仅作为 fallback

## 目标结构

```
server/   FastAPI：LLM 适配层 + 工具注册 + 会话状态，复用 packages/
webapp/   Next.js + Tailwind + shadcn/ui：对话面板 + 工作台双栏
docker-compose.yml
```

## 批次台账

- [x] M1 后端 LLM 适配层 + tool-use 闭环（先接 2 个工具）
  - 状态：已完成
  - 范围：`server/llm`（base/anthropic/openai/mock + loop）、`server/tools/registry`、`server/sessions/store`、`server/app`（/api/chat、/api/health、/api/config、/api/sessions）、`server/config`、`server/requirements.txt`、`server/.env.example`、`server/README.md`
  - 已接工具：`inspect_manual_exports`、`build_candidate_pool`（A 类，操作会话产出物）
  - 验收：`compileall server` 通过；`server/tests` 5 项全通过——MockProvider 驱动「用户消息 → inspect → build_candidate_pool → 最终回复」完整闭环（用刮窗器真实样例生成候选池），含工具错误回喂、build 前置依赖校验、会话落盘重载；主仓库回归 27 项全过无影响；无需真实 API key
  - 待运行项：实际启动 FastAPI 需 `pip install -r server/requirements.txt`（M4 用 Docker 一键化）
- [x] M2 Next.js 双栏页面：对话 + 工作台（状态卡 + 文件上传）
  - 状态：已完成
  - 产物：`webapp/`（Next.js App Router + Tailwind），左栏 `ChatPanel`（对话 + 工具调用气泡）+ 右栏工作台 `StateCard`/`FileUploadCard`；设计系统采用 ui-ux-pro-max「Data-Dense Dashboard」蓝+琥珀色板、Fira Sans/Code
  - 后端补 `/api/upload`（多文件 → 会话上传目录）；`inspect_manual_exports` 工具支持回退到会话上传目录
  - 备注：先用请求/响应式 chat（非 SSE），流式作为后续增强
  - 验收：`npm run build` 类型检查 + 编译成功
- [x] M3 候选方向选择台 + 决策按钮 + 报告预览，打通完整交互式流程
  - 状态：已完成
  - 产物：`DirectionCards`（候选方向选择台，点选→发消息给 AI）、`DecisionBar`（Go/Wait/No-Go→发消息）、`ArtifactPreview`（盘点/候选池摘要）、`SettingsDialog`（Provider/模型切换）
  - 设计：工作台操作统一转成「发给 AI 的消息」，保持对话为核心
  - 验收：随 M2 一并 `npm run build` 通过
- [x] M4 docker-compose 一键本地起服务
  - 状态：已完成
  - 产物：`server/Dockerfile`、`webapp/Dockerfile`（多阶段构建）、根 `docker-compose.yml`（server:8000 + webapp:3000，env_file 读 server/.env，会话目录挂载）
  - 验收：前端构建本地验证通过；`docker compose up --build` 即可本地起前后端

## 收尾总结（M1–M4 全部完成）

模型 B 最小可用版打通：**运营在网页对话 → AI（Claude/GPT）tool-use 调用现有 pipeline → 工作台实时显示状态/候选/决策**。

- 后端 FastAPI 直接复用 `packages/`，零业务重写；LLM 适配层支持 Claude/GPT 网页切换。
- 前端 Next.js 双栏：对话 + 工作台；文件上传一等公民；候选方向选择台 + 决策按钮均回流为对话消息。
- 一键 `docker compose up --build` 本地起服务。
- 核心闭环有单测（MockProvider，无需 key）；前端 `npm run build` 通过。

## 后续可增强（非本期）

- 后端 Skill Loader：读取 `skills/*.md`，由 Prompt Builder 按阶段注入 Master Skill / market-scan / candidate-deep-dive / review-voc-analysis
- Sorftime MCP 后端代理：把 MCP tools/list 转成模型可调用工具，并记录积分、参数和证据链
- 自有评论插件任务队列：网页创建任务、插件领取、进度回传、评论 JSON 入库、VOC Skill 自动分析
- 接更多本地工具：research_package、利润/合规模板、validate、正式报告生成
- workflow_state 与 LLM 循环更强同步（next_action_card 渲染成结构化卡）
- 报告四件套在网页内预览/下载

## 追加决策：Agent 化路线（2026-06-15）

后续以 `skills/amazon-product-research/SKILL.md` 和 `skills/amazon-product-research/references/multi_agent_dispatch.md` 为准：

- 删除前端模式选择卡，运营直接和 AI 对话。
- 后端加载项目内 Skills，而不是依赖 Codex/Claude 客户端 Skill 运行时。
- AI 自动判断模式、阶段、MCP 调用时机和运营暂停点。
- Sorftime MCP 由后端代理调用。
- 自有评论插件走第三档整合：AI 创建评论任务，插件采集并回传。

## 追加：chat SSE 流式（已完成）

- 状态：已完成
- 后端：`LLMProvider.stream()`（默认回退 + Anthropic `messages.stream` / OpenAI `stream=True` 真流式 + Mock 逐字）；`run_agent_turn_streaming` 生成器逐事件 yield（text / tool_start / tool_result / done / session / error）；`/api/chat/stream` 用 `StreamingResponse` 推 SSE
- 前端：`api.chatStream` 用 fetch + ReadableStream 解析 SSE；`page.tsx` 逐 delta 更新助手气泡、工具事件并入、流式光标
- 验收：后端 `server/tests` 6 项全过（新增流式事件测试）；前端 `npm run build` 通过

## Agent 化路线（进行中）

- [x] P0 删除前端模式选择，改为 AI 自动识别模式
  - 状态：已完成
  - 验收：工作台首屏不再展示模式选择；`mode_pending` 仅作为内部过渡态；新增 `set_research_mode` 工具，首轮对话可自动写回模式与 workflow_state；后端系统提示与会话摘要已改为“AI 自动识别模式”
  - 补充验收：对话气泡支持轻量 Markdown 展示（加粗、标题、有序列表、无序列表）；已用浏览器打开历史会话 `c72709796331` 验证不再裸露 `**`；`npm run lint && npm run build`、`server/tests` 15 项通过
- [ ] P1 Skill Loader + Prompt Builder
  - 待开始：后端读取 `skills/*.md`，按阶段注入 Master Skill / market-scan / candidate-deep-dive / review-voc-analysis
- [ ] P2 Sorftime MCP 工具化
  - 待开始：后端代理 MCP 并把工具注册进 Agent Loop
- [ ] P3 评论任务队列
  - 待开始：Web 创建任务，插件领取并回传状态
- [ ] P4 插件回传评论 + VOC 分析
  - 待开始：评论 JSON 入库并自动触发 VOC Skill
- [ ] P5 报告闭环
  - 待开始：最终报告包含交互决策、MCP 证据和评论 VOC 证据
