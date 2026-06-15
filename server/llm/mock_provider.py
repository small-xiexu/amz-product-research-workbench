"""MockProvider：按预设脚本输出，用于无 API key 的本地闭环测试。"""

from __future__ import annotations

from typing import Any, Iterator

from server.llm.base import AssistantTurn, LLMProvider, StreamEvent, TextDelta, ToolSpec, TurnComplete


class MockProvider(LLMProvider):
    """按 `script`（AssistantTurn 列表）依次返回；每调用一次 complete() 取下一个。

    用于验证 tool-use 循环、工具分发和会话状态，不依赖真实 LLM。
    """

    name = "mock"

    def __init__(self, script: list[AssistantTurn], model: str = "mock-1") -> None:
        self._script = list(script)
        self._index = 0
        self.model = model
        self.calls: list[dict[str, Any]] = []

    def complete(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[ToolSpec],
    ) -> AssistantTurn:
        self.calls.append({"system": system, "messages": list(messages), "tools": [t.name for t in tools]})
        if self._index >= len(self._script):
            return AssistantTurn(text="（脚本结束）")
        turn = self._script[self._index]
        self._index += 1
        return turn

    def stream(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[ToolSpec],
    ) -> Iterator[StreamEvent]:
        turn = self.complete(system, messages, tools)
        # 模拟逐字流式：按字符分段
        for ch in turn.text:
            yield TextDelta(ch)
        yield TurnComplete(turn)
