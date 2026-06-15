"""Tool-use 智能循环：让 LLM 在「思考 → 调工具 → 看结果 → 再思考」中推进，直到给出最终回复。"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Iterator

from server.llm.base import AssistantTurn, LLMProvider, TextDelta, ToolSpec, TurnComplete

# 工具分发器签名：dispatch(tool_name, arguments) -> 结果（任意可 JSON 序列化对象）
Dispatch = Callable[[str, dict[str, Any]], Any]


@dataclass
class ToolRun:
    """一次工具执行记录，供前端展示和审计。"""

    call_id: str
    name: str
    arguments: dict[str, Any]
    result: Any
    ok: bool = True
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "call_id": self.call_id,
            "name": self.name,
            "arguments": self.arguments,
            "result": self.result,
            "ok": self.ok,
            "error": self.error,
        }


@dataclass
class AgentResult:
    """一次完整 agent 回合的结果。"""

    final_text: str
    messages: list[dict[str, Any]]
    tool_runs: list[ToolRun] = field(default_factory=list)
    steps: int = 0
    stopped_reason: str = "completed"

    def to_dict(self) -> dict[str, Any]:
        return {
            "final_text": self.final_text,
            "tool_runs": [run.to_dict() for run in self.tool_runs],
            "steps": self.steps,
            "stopped_reason": self.stopped_reason,
        }


def run_agent_turn(
    provider: LLMProvider,
    system: str,
    messages: list[dict[str, Any]],
    tools: list[ToolSpec],
    dispatch: Dispatch,
    max_steps: int = 8,
) -> AgentResult:
    """驱动一轮 agent 交互。

    `messages` 为标准化历史（已包含最新用户消息），过程中会原地追加助手与工具消息。
    每次 LLM 返回工具调用就执行并回喂；返回纯文本即结束。
    """

    tool_runs: list[ToolRun] = []
    steps = 0
    stopped_reason = "completed"

    while steps < max_steps:
        steps += 1
        turn: AssistantTurn = provider.complete(system, messages, tools)

        messages.append(
            {
                "role": "assistant",
                "content": turn.text,
                "tool_calls": [call.to_dict() for call in turn.tool_calls],
            }
        )

        if not turn.wants_tools:
            return AgentResult(
                final_text=turn.text,
                messages=messages,
                tool_runs=tool_runs,
                steps=steps,
                stopped_reason="completed",
            )

        for call in turn.tool_calls:
            try:
                result = dispatch(call.name, call.arguments)
                run = ToolRun(call.id, call.name, call.arguments, result, ok=True)
            except Exception as exc:  # noqa: BLE001 - 工具错误回喂给 LLM 自行恢复
                result = {"error": str(exc)}
                run = ToolRun(call.id, call.name, call.arguments, result, ok=False, error=str(exc))
            tool_runs.append(run)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.id,
                    "name": call.name,
                    "content": json.dumps(result, ensure_ascii=False, default=str),
                }
            )

    stopped_reason = "max_steps_reached"
    return AgentResult(
        final_text="（已达到最大工具调用步数，请运营确认或继续。）",
        messages=messages,
        tool_runs=tool_runs,
        steps=steps,
        stopped_reason=stopped_reason,
    )


def run_agent_turn_streaming(
    provider: LLMProvider,
    system: str,
    messages: list[dict[str, Any]],
    tools: list[ToolSpec],
    dispatch: Dispatch,
    max_steps: int = 8,
) -> Iterator[dict[str, Any]]:
    """流式版 agent 循环，逐事件 yield，供 SSE 推送。

    事件类型：
    - {"type": "text", "delta": str}                  助手增量文本
    - {"type": "tool_start", "name", "call_id", "arguments"}
    - {"type": "tool_result", "name", "call_id", "ok", "result", "error"}
    - {"type": "done", "stopped_reason", "steps", "final_text"}
    """

    steps = 0
    final_text_parts: list[str] = []

    while steps < max_steps:
        steps += 1
        turn: AssistantTurn | None = None
        step_text = ""

        for event in provider.stream(system, messages, tools):
            if isinstance(event, TextDelta):
                step_text += event.text
                yield {"type": "text", "delta": event.text}
            elif isinstance(event, TurnComplete):
                turn = event.turn

        if turn is None:  # 兜底：流未给出完整轮次
            turn = AssistantTurn(text=step_text)

        messages.append(
            {
                "role": "assistant",
                "content": turn.text,
                "tool_calls": [call.to_dict() for call in turn.tool_calls],
            }
        )

        if not turn.wants_tools:
            final_text_parts.append(turn.text)
            yield {
                "type": "done",
                "stopped_reason": "completed",
                "steps": steps,
                "final_text": turn.text,
            }
            return

        for call in turn.tool_calls:
            yield {"type": "tool_start", "name": call.name, "call_id": call.id, "arguments": call.arguments}
            try:
                result = dispatch(call.name, call.arguments)
                ok, error = True, None
            except Exception as exc:  # noqa: BLE001
                result, ok, error = {"error": str(exc)}, False, str(exc)
            yield {
                "type": "tool_result",
                "name": call.name,
                "call_id": call.id,
                "ok": ok,
                "result": result,
                "error": error,
            }
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.id,
                    "name": call.name,
                    "content": json.dumps(result, ensure_ascii=False, default=str),
                }
            )

    yield {
        "type": "done",
        "stopped_reason": "max_steps_reached",
        "steps": steps,
        "final_text": "（已达到最大工具调用步数，请运营确认或继续。）",
    }
