# webapp · 选品工作台前端

Next.js (App Router) + Tailwind，双栏布局：**左侧 AI 对话 + 右侧结构化工作台**。
设计系统来自 ui-ux-pro-max「Data-Dense Dashboard」（蓝 #1E40AF + 琥珀 #D97706，Fira Sans/Code）。

## 布局

```
┌─────────────────────────┬──────────────────────────┐
│ ChatPanel               │ Workbench（右栏）         │
│ · 多轮对话 + 工具调用展示 │ · StateCard 流程进度       │
│ · Enter 换行            │ · FileUploadCard 上传      │
│ · ⌘/Ctrl+Enter 发送     │                          │
│                         │ · DirectionCards 方向选择台 │
│                         │ · ArtifactPreview 数据产出  │
│                         │ · DecisionBar Go/Wait/No-Go │
└─────────────────────────┴──────────────────────────┘
```

工作台的「深挖 / 决策」按钮本质是把结构化操作转成一条发给 AI 的消息，保持「对话为核心」。
右上角提供两个配置入口：`AI 配置` 只维护模型接口、模型名称和大模型 Key；`数据源配置` 维护 Sorftime MCP 等第三方数据中心连接信息。完整 Key 只提交给后端保存，前端只展示脱敏状态。

## 本地开发

```bash
cd webapp
cp .env.local.example .env.local     # BACKEND_URL 指向 FastAPI
npm install --legacy-peer-deps
npm run dev                          # http://localhost:3000
```

需要后端先起：见 `server/README.md`。`/api/*` 通过 Next.js rewrites 代理到 `BACKEND_URL`。

## 一键 Docker（前后端一起）

```bash
# 仓库根，先配置 server/.env 的 API key
docker compose up --build
# 前端 http://localhost:3000，后端 http://localhost:8000
```

## 组件

| 文件 | 职责 |
|---|---|
| `app/page.tsx` | 状态编排：会话、消息、配置 |
| `components/ChatPanel.tsx` | 对话面板 + 工具调用气泡 |
| `components/StateCard.tsx` | 会话信息 + 流程进度条 |
| `components/FileUploadCard.tsx` | 卖家精灵/评论导出上传 |
| `components/DirectionCards.tsx` | 候选方向选择台 + 决策栏 |
| `components/ArtifactPreview.tsx` | 盘点/候选池摘要 |
| `app/settings/ai/page.tsx` | AI 配置页面 |
| `components/AiConfigPanel.tsx` | Provider/模型/Key 配置 |
| `app/settings/data-sources/page.tsx` | 数据源配置页面 |
| `components/DataSourcesPanel.tsx` | Sorftime MCP 等数据源连接配置 |
