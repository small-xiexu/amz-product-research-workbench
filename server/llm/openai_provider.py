"""OpenAI (GPT) Provider：把标准化消息翻译成 Chat Completions 的 function calling 格式。"""

from __future__ import annotations

import json
from typing import Any, Iterator
from urllib.parse import urlsplit, urlunsplit

from server.llm.base import AssistantTurn, LLMProvider, StreamEvent, TextDelta, ToolCall, ToolSpec, TurnComplete


class OpenAIProvider(LLMProvider):
    name = "openai"

    def __init__(self, api_key: str, model: str = "gpt-4o", base_url: str | None = None) -> None:
        if not api_key:
            raise ValueError("OpenAIProvider 需要 api_key")
        try:
            import openai  # 懒加载
            import httpx
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("未安装 openai/httpx SDK，请 `pip install openai httpx`") from exc
        self.base_url = normalize_openai_base_url(base_url)
        self._client = openai.OpenAI(
            api_key=api_key,
            base_url=self.base_url,
            http_client=httpx.Client(trust_env=False),
        )
        self.model = model

    def complete(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[ToolSpec],
    ) -> AssistantTurn:
        resp = self._client.chat.completions.create(
            model=self.model,
            messages=self._messages_to_openai(system, messages),
            tools=[self._tool_to_openai(t) for t in tools],
        )
        if not resp.choices:
            raise RuntimeError("OpenAI 兼容接口返回了空 choices，请检查网关或模型名称")
        choice = resp.choices[0].message
        tool_calls: list[ToolCall] = []
        for call in getattr(choice, "tool_calls", None) or []:
            try:
                args = json.loads(call.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            tool_calls.append(ToolCall(id=call.id, name=call.function.name, arguments=args))
        return AssistantTurn(text=choice.content or "", tool_calls=tool_calls, raw=resp)

    def stream(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[ToolSpec],
    ) -> Iterator[StreamEvent]:
        stream = self._client.chat.completions.create(
            model=self.model,
            messages=self._messages_to_openai(system, messages),
            tools=[self._tool_to_openai(t) for t in tools],
            stream=True,
        )
        text_parts: list[str] = []
        # 按 index 累积工具调用片段
        partial: dict[int, dict[str, Any]] = {}
        for chunk in stream:
            choices = getattr(chunk, "choices", None) or []
            if not choices:
                continue
            delta = choices[0].delta
            if getattr(delta, "content", None):
                text_parts.append(delta.content)
                yield TextDelta(delta.content)
            for tc in getattr(delta, "tool_calls", None) or []:
                slot = partial.setdefault(tc.index, {"id": None, "name": "", "arguments": ""})
                if tc.id:
                    slot["id"] = tc.id
                if tc.function and tc.function.name:
                    slot["name"] = tc.function.name
                if tc.function and tc.function.arguments:
                    slot["arguments"] += tc.function.arguments

        tool_calls: list[ToolCall] = []
        for _, slot in sorted(partial.items()):
            try:
                args = json.loads(slot["arguments"] or "{}")
            except json.JSONDecodeError:
                args = {}
            tool_calls.append(ToolCall(id=slot["id"] or "", name=slot["name"], arguments=args))
        yield TurnComplete(AssistantTurn(text="".join(text_parts), tool_calls=tool_calls))

    @staticmethod
    def _tool_to_openai(tool: ToolSpec) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.input_schema,
            },
        }

    @staticmethod
    def _messages_to_openai(system: str, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = [{"role": "system", "content": system}]
        for msg in messages:
            role = msg["role"]
            if role == "user":
                out.append({"role": "user", "content": msg.get("content", "")})
            elif role == "assistant":
                entry: dict[str, Any] = {"role": "assistant", "content": msg.get("content", "") or None}
                if msg.get("tool_calls"):
                    entry["tool_calls"] = [
                        {
                            "id": call["id"],
                            "type": "function",
                            "function": {
                                "name": call["name"],
                                "arguments": json.dumps(call["arguments"], ensure_ascii=False),
                            },
                        }
                        for call in msg["tool_calls"]
                    ]
                out.append(entry)
            elif role == "tool":
                out.append(
                    {
                        "role": "tool",
                        "tool_call_id": msg["tool_call_id"],
                        "content": msg.get("content", ""),
                    }
                )
        return out


def normalize_openai_base_url(base_url: str | None) -> str | None:
    """兼容 OpenAI SDK：用户只填网关根地址时自动补 /v1。"""

    cleaned = str(base_url or "").strip()
    if not cleaned:
        return None
    parts = urlsplit(cleaned)
    if not parts.scheme or not parts.netloc:
        trimmed = cleaned.rstrip("/")
        return trimmed if trimmed.endswith("/v1") else f"{trimmed}/v1"

    path = parts.path.rstrip("/")
    if not path.endswith("/v1"):
        path = f"{path}/v1" if path else "/v1"
    return urlunsplit((parts.scheme, parts.netloc, path, "", ""))
