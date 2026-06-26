# server · 选品工作台后端

FastAPI 后端：把 `packages/research_core/pipeline` 的数据函数包装成 LLM 工具，
通过统一的 Provider 适配层（Claude / GPT）驱动运营 ↔ AI 多轮交互。

## 分层

```
server/
├── app.py                 FastAPI 路由：/api/health /api/config /api/sessions /api/chat
├── config.py              Provider 工厂 + 系统提示 + AI 配置持久化（Key 不下发前端）
├── llm/
│   ├── base.py            Provider 无关类型：ToolSpec / ToolCall / AssistantTurn / LLMProvider
│   ├── loop.py            tool-use agentic 循环
│   ├── anthropic_provider.py   Claude（SDK 懒加载）
│   ├── openai_provider.py      GPT（SDK 懒加载）
│   └── mock_provider.py        无 key 测试用
├── tools/registry.py      把 pipeline 函数注册成 LLM 工具（操作会话产出物）
└── sessions/store.py      会话状态：对话历史 + workflow_state + artifacts
```

核心逻辑（llm/tools/sessions）不依赖 FastAPI，可独立单测。

## 本地运行

```bash
cd server
cp .env.example .env        # 可填 ANTHROPIC_API_KEY / OPENAI_API_KEY，也可在网页 AI 配置页填写
pip install -r requirements.txt

# 从仓库根启动（让后端能 import packages/）
cd ..
uvicorn server.app:app --reload --port 8000
```

## 测试（无需 API key）

```bash
# 从仓库根
python3 -m unittest discover -s server/tests -v
```

MockProvider 会驱动「用户消息 → inspect_manual_exports → 最终回复」完整闭环。

## 配置入口

- 网页入口：前端右上角 `AI 配置`，或直接访问 `/settings/ai`。
- `AI 配置` 支持配置 Claude/OpenAI 兼容接口、模型、Base URL、Anthropic/OpenAI Key。
- `数据源配置` 支持配置 Sorftime MCP URL/Key，后续接入其他第三方数据中心也放在这里。
- 完整 Key 只保存到后端本地 `APP_CONFIG_PATH`（默认 `.runtime/ai-config.json`），接口只返回 `已配置/来源/脱敏尾号`。
- `.env` 仍然可作为兜底配置；网页保存的 Key 优先于环境变量。

## API 速览

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | /api/health | 健康检查 + 当前 Provider/模型 |
| GET/POST | /api/config | 查看/保存 AI 配置（key 不下发） |
| POST | /api/config/test | 测试当前/待保存 AI 配置是否能初始化 Provider |
| POST | /api/sessions | 创建会话（mode: broad_discovery / targeted_deep_dive） |
| GET | /api/sessions/{id} | 查看会话状态与产出物 |
| POST | /api/chat | 发送一条运营消息，触发一轮 tool-use 交互 |

## 当前工具（A 类 · AI 可自动执行）

- `inspect_manual_exports`：盘点卖家精灵导出文件夹

后续按计划接入 research_package、利润/合规模板、validate 及 Sorftime 验证工具。
