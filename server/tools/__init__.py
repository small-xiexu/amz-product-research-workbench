"""LLM 工具注册表。"""

from server.tools.registry import ALL_TOOLS, make_dispatch

__all__ = ["ALL_TOOLS", "make_dispatch"]
