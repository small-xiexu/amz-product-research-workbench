"""Provider 无关的 LLM 类型与抽象接口。

统一的标准化消息格式（normalized messages），各 Provider 负责翻译成自家 API：

- {"role": "user", "content": str}
- {"role": "assistant", "content": str, "tool_calls": [ToolCall, ...]}
- {"role": "tool", "tool_call_id": str, "name": str, "content": str}
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Iterator, Union


@dataclass(frozen=True)
class ToolSpec:
    """一个可被 LLM 调用的工具定义。input_schema 为 JSON Schema。"""

    name: str
    description: str
    input_schema: dict[str, Any]


@dataclass
class ToolCall:
    """LLM 发起的一次工具调用。"""

    id: str
    name: str
    arguments: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "name": self.name, "arguments": self.arguments}


@dataclass
class AssistantTurn:
    """LLM 的一轮输出：可见文本 + 可选的工具调用。"""

    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    raw: Any = None

    @property
    def wants_tools(self) -> bool:
        return bool(self.tool_calls)


@dataclass
class TextDelta:
    """流式输出中的一段增量文本。"""

    text: str


@dataclass
class TurnComplete:
    """流式输出结束，携带完整的助手轮次（含工具调用）。"""

    turn: AssistantTurn


StreamEvent = Union[TextDelta, TurnComplete]


class LLMProvider(ABC):
    """统一的对话补全接口。"""

    name: str = "base"
    model: str = ""

    @abstractmethod
    def complete(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[ToolSpec],
    ) -> AssistantTurn:
        """根据系统提示、标准化消息历史和工具列表，返回一轮助手输出。"""
        raise NotImplementedError

    def stream(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[ToolSpec],
    ) -> Iterator[StreamEvent]:
        """流式输出，默认回退为「一次性」：调用 complete 后整段返回。

        支持真流式的 Provider 应重写本方法，逐段 yield TextDelta，最后 yield TurnComplete。
        """
        turn = self.complete(system, messages, tools)
        if turn.text:
            yield TextDelta(turn.text)
        yield TurnComplete(turn)
