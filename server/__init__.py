"""选品工作台后端（FastAPI）。

复用 `packages/` 现有数据逻辑，把 pipeline 函数包装成 LLM 工具，
通过统一的 Provider 适配层（Claude / GPT）驱动多轮交互。
"""
