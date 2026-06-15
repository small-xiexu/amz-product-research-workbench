"""Anthropic (Claude) Provider：把标准化消息翻译成 Messages API 的 tool-use 格式。"""

from __future__ import annotations

from typing import Any, Iterator

from server.llm.base import AssistantTurn, LLMProvider, StreamEvent, TextDelta, ToolCall, ToolSpec, TurnComplete


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-20250514",
        max_tokens: int = 4096,
        base_url: str | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("AnthropicProvider 需要 api_key")
        try:
            import anthropic  # 懒加载，避免无 SDK 时 import 失败
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("未安装 anthropic SDK，请 `pip install anthropic`") from exc
        self._client = (
            anthropic.Anthropic(api_key=api_key, base_url=base_url)
            if base_url
            else anthropic.Anthropic(api_key=api_key)
        )
        self.model = model
        self.max_tokens = max_tokens

    def complete(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[ToolSpec],
    ) -> AssistantTurn:
        resp = self._client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system,
            tools=[self._tool_to_anthropic(t) for t in tools],
            messages=self._messages_to_anthropic(messages),
        )
        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        for block in resp.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(ToolCall(id=block.id, name=block.name, arguments=dict(block.input or {})))
        return AssistantTurn(text="".join(text_parts), tool_calls=tool_calls, raw=resp)

    def stream(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[ToolSpec],
    ) -> Iterator[StreamEvent]:
        with self._client.messages.stream(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system,
            tools=[self._tool_to_anthropic(t) for t in tools],
            messages=self._messages_to_anthropic(messages),
        ) as stream:
            for text in stream.text_stream:
                if text:
                    yield TextDelta(text)
            final = stream.get_final_message()
        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        for block in final.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(ToolCall(id=block.id, name=block.name, arguments=dict(block.input or {})))
        yield TurnComplete(AssistantTurn(text="".join(text_parts), tool_calls=tool_calls, raw=final))

    @staticmethod
    def _tool_to_anthropic(tool: ToolSpec) -> dict[str, Any]:
        return {
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.input_schema,
        }

    @staticmethod
    def _messages_to_anthropic(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for msg in messages:
            role = msg["role"]
            if role == "user":
                out.append({"role": "user", "content": [{"type": "text", "text": msg.get("content", "")}]})
            elif role == "assistant":
                content: list[dict[str, Any]] = []
                if msg.get("content"):
                    content.append({"type": "text", "text": msg["content"]})
                for call in msg.get("tool_calls", []):
                    content.append(
                        {
                            "type": "tool_use",
                            "id": call["id"],
                            "name": call["name"],
                            "input": call["arguments"],
                        }
                    )
                out.append({"role": "assistant", "content": content or [{"type": "text", "text": ""}]})
            elif role == "tool":
                out.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": msg["tool_call_id"],
                                "content": msg.get("content", ""),
                            }
                        ],
                    }
                )
        return out
