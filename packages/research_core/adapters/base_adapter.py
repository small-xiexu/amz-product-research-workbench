"""Base adapter interface and global adapter registry."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from packages.research_core.schema import (
        NormalizedProduct,
        NormalizedKeyword,
        NormalizedCategory,
    )


class BaseDataAdapter:
    """所有数据源 Adapter 的基类。实现三个方法即可接入系统。"""

    source_type: ClassVar[str] = ""

    def fetch_products(self) -> list[NormalizedProduct]:
        return []

    def fetch_keywords(self) -> list[NormalizedKeyword]:
        return []

    def fetch_category(self) -> NormalizedCategory | None:
        return None

    @classmethod
    def from_mcp_snapshot(cls, snapshot: dict[str, Any]) -> BaseDataAdapter:
        """从 MCP 快照构建适配器（子类按需覆写）。"""
        raise NotImplementedError(
            f"{cls.__name__} 不支持 MCP 快照输入，请使用适配器专属构造方式"
        )


# 注册表：source_type → Adapter 类
# 新增数据源只需在此加一行
ADAPTER_REGISTRY: dict[str, type[BaseDataAdapter]] = {}
