"""MVP-1 闭环测试：用 MockProvider 驱动 tool-use 循环 + 真实 pipeline 工具，无需 API key。

验证：用户消息 → LLM 调 inspect_manual_exports → 调 build_candidate_pool → 给出最终回复，
且会话 artifacts 里生成了 manifest 与 candidate_pool。
"""

from __future__ import annotations

import unittest
from pathlib import Path

from server.config import ProviderConfig, build_provider, load_provider_config, merge_provider_config, public_config, save_provider_config
from server.data_sources.sorftime import build_sorftime_mcp_url
from server.llm.openai_provider import OpenAIProvider, normalize_openai_base_url
from server.llm.base import AssistantTurn, TextDelta, ToolCall, TurnComplete
from server.llm.loop import run_agent_turn, run_agent_turn_streaming
from server.llm.mock_provider import MockProvider
from server.sessions.store import Session, SessionStore
from server.tools.registry import ALL_TOOLS, make_dispatch

ROOT = Path(__file__).resolve().parents[2]
WINDOW_SAMPLE = ROOT / "卖家精灵导出_刮窗器_20260608"


class ToolRegistryTests(unittest.TestCase):
    def test_tools_exposed(self) -> None:
        names = {t.name for t in ALL_TOOLS}
        self.assertEqual(names, {"set_research_mode", "inspect_manual_exports", "build_candidate_pool"})
        for tool in ALL_TOOLS:
            self.assertIn("type", tool.input_schema)

    def test_set_research_mode_writes_session_state(self) -> None:
        session = Session(session_id="s2", mode="mode_pending", site="CA")
        dispatch = make_dispatch(session)
        result = dispatch(
            "set_research_mode",
            {
                "mode": "targeted_deep_dive",
                "intent": "窗户刮水器二合一工具",
                "site": "US",
                "reason": "用户已经给出明确产品方向",
            },
        )

        self.assertTrue(result["ok"])
        self.assertEqual(session.mode, "targeted_deep_dive")
        self.assertEqual(session.intent, "窗户刮水器二合一工具")
        self.assertEqual(session.site, "US")
        self.assertIsNotNone(session.workflow_state)
        self.assertEqual(session.workflow_state["mode"], "targeted_deep_dive")
        self.assertEqual(session.workflow_state["site"], "US")

    def test_build_candidate_pool_requires_manifest(self) -> None:
        session = Session(session_id="s1")
        dispatch = make_dispatch(session)
        with self.assertRaises(RuntimeError):
            dispatch("build_candidate_pool", {})


class AgentLoopTests(unittest.TestCase):
    @unittest.skipUnless(WINDOW_SAMPLE.is_dir(), "需要刮窗器真实导出样例文件夹")
    def test_full_tool_use_loop_with_mock_provider(self) -> None:
        session = Session(session_id="s-mock", mode="targeted_deep_dive", intent="窗户刮水器二合一工具", site="US")

        # 脚本：先调盘点工具 → 再调候选池工具 → 给最终结论
        script = [
            AssistantTurn(
                text="先盘点你上传的卖家精灵导出。",
                tool_calls=[ToolCall(id="t1", name="inspect_manual_exports", arguments={"folder": str(WINDOW_SAMPLE), "site": "US"})],
            ),
            AssistantTurn(
                text="数据齐全，构建候选池。",
                tool_calls=[ToolCall(id="t2", name="build_candidate_pool", arguments={})],
            ),
            AssistantTurn(text="候选池已生成，请在工作台选择要深挖的主线方向。"),
        ]
        provider = MockProvider(script)

        session.messages.append({"role": "user", "content": "我想做窗户刮水器二合一工具"})
        result = run_agent_turn(
            provider=provider,
            system="测试系统提示",
            messages=session.messages,
            tools=ALL_TOOLS,
            dispatch=make_dispatch(session),
        )

        self.assertEqual(result.stopped_reason, "completed")
        self.assertIn("候选池已生成", result.final_text)

        tool_names = [run.name for run in result.tool_runs]
        self.assertEqual(tool_names, ["inspect_manual_exports", "build_candidate_pool"])
        self.assertTrue(all(run.ok for run in result.tool_runs))

        # 会话产出物
        self.assertIn("manifest", session.artifacts)
        self.assertIn("candidate_pool", session.artifacts)
        self.assertGreaterEqual(len(session.artifacts["candidate_pool"].get("candidates", [])), 1)

    @unittest.skipUnless(WINDOW_SAMPLE.is_dir(), "需要刮窗器真实导出样例文件夹")
    def test_streaming_loop_emits_text_and_tool_events(self) -> None:
        session = Session(session_id="s-stream", mode="targeted_deep_dive", intent="刮窗器", site="US")
        script = [
            AssistantTurn(
                text="先盘点。",
                tool_calls=[ToolCall(id="t1", name="inspect_manual_exports", arguments={"folder": str(WINDOW_SAMPLE)})],
            ),
            AssistantTurn(
                text="构建候选池。",
                tool_calls=[ToolCall(id="t2", name="build_candidate_pool", arguments={})],
            ),
            AssistantTurn(text="完成，请选择主线。"),
        ]
        provider = MockProvider(script)
        session.messages.append({"role": "user", "content": "开始"})

        events = list(
            run_agent_turn_streaming(provider, "sys", session.messages, ALL_TOOLS, make_dispatch(session))
        )
        types = [e["type"] for e in events]
        self.assertIn("text", types)
        self.assertIn("tool_start", types)
        self.assertIn("tool_result", types)
        self.assertEqual(types[-1], "done")
        self.assertEqual(events[-1]["stopped_reason"], "completed")

        text = "".join(e["delta"] for e in events if e["type"] == "text")
        self.assertIn("完成，请选择主线。", text)
        self.assertIn("candidate_pool", session.artifacts)

    def test_tool_error_is_fed_back_not_raised(self) -> None:
        session = Session(session_id="s-err")
        script = [
            AssistantTurn(
                text="尝试盘点不存在的文件夹。",
                tool_calls=[ToolCall(id="t1", name="inspect_manual_exports", arguments={"folder": "/tmp/__nope__"})],
            ),
            AssistantTurn(text="抱歉，文件夹不存在，请确认路径。"),
        ]
        provider = MockProvider(script)
        session.messages.append({"role": "user", "content": "盘点一下"})
        result = run_agent_turn(provider, "sys", session.messages, ALL_TOOLS, make_dispatch(session))

        self.assertEqual(result.stopped_reason, "completed")
        self.assertEqual(len(result.tool_runs), 1)
        self.assertFalse(result.tool_runs[0].ok)
        self.assertIn("不存在", result.tool_runs[0].error or "")


class SessionStoreTests(unittest.TestCase):
    def test_persist_and_reload(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            store = SessionStore(persist_dir=tmp)
            store.create(Session(session_id="abc", intent="测试", artifacts={"k": 1}))
            reloaded = SessionStore(persist_dir=tmp)
            got = reloaded.get("abc")
            self.assertIsNotNone(got)
            assert got is not None
            self.assertEqual(got.intent, "测试")
            self.assertEqual(got.artifacts["k"], 1)


class ProviderConfigTests(unittest.TestCase):
    def test_openai_base_url_appends_v1_when_missing(self) -> None:
        self.assertEqual(normalize_openai_base_url("http://localhost:8888"), "http://localhost:8888/v1")
        self.assertEqual(normalize_openai_base_url("http://localhost:8888/"), "http://localhost:8888/v1")
        self.assertEqual(normalize_openai_base_url("http://localhost:8888/v1"), "http://localhost:8888/v1")
        self.assertEqual(normalize_openai_base_url("https://gateway.example/api"), "https://gateway.example/api/v1")
        self.assertEqual(normalize_openai_base_url("https://gateway.example/api?token=x"), "https://gateway.example/api/v1")
        self.assertIsNone(normalize_openai_base_url(""))

    def test_openai_stream_skips_empty_choices_chunks(self) -> None:
        import types

        provider = object.__new__(OpenAIProvider)
        provider.model = "gpt-test"

        empty_chunk = types.SimpleNamespace(choices=[])
        text_chunk = types.SimpleNamespace(
            choices=[
                types.SimpleNamespace(
                    delta=types.SimpleNamespace(content="OK", tool_calls=[]),
                )
            ]
        )

        class FakeCompletions:
            def create(self, **kwargs):  # noqa: ANN003
                return iter([empty_chunk, text_chunk])

        provider._client = types.SimpleNamespace(  # type: ignore[attr-defined]
            chat=types.SimpleNamespace(completions=FakeCompletions())
        )

        events = list(provider.stream("sys", [{"role": "user", "content": "hi"}], []))
        self.assertIsInstance(events[0], TextDelta)
        self.assertEqual(events[0].text, "OK")
        self.assertIsInstance(events[-1], TurnComplete)
        self.assertEqual(events[-1].turn.text, "OK")

    def test_anthropic_base_url_round_trip(self) -> None:
        import tempfile

        current = ProviderConfig(
            provider="anthropic",
            model="claude-sonnet-4-20250514",
            anthropic_base_url="https://old-claude.example",
            openai_base_url="https://old-openai.example/v1",
            api_keys={"anthropic": "sk-test-anthropic"},
        )
        merged = merge_provider_config(
            current,
            {
                "provider": "anthropic",
                "model": "claude-sonnet-4-20250514",
                "anthropic_base_url": "https://claude-gateway.example",
                "openai_base_url": "https://openai-gateway.example/v1",
            },
        )

        self.assertEqual(merged.anthropic_base_url, "https://claude-gateway.example")
        self.assertEqual(merged.openai_base_url, "https://openai-gateway.example/v1")
        self.assertEqual(public_config(merged)["anthropic_base_url"], "https://claude-gateway.example")

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ai-config.json"
            save_provider_config(path, merged)
            reloaded = load_provider_config(path)
            self.assertEqual(reloaded.anthropic_base_url, "https://claude-gateway.example")
            self.assertEqual(reloaded.openai_base_url, "https://openai-gateway.example/v1")

    def test_build_provider_passes_anthropic_base_url(self) -> None:
        import sys
        import types

        captured: dict[str, object] = {}
        fake_module = types.ModuleType("server.llm.anthropic_provider")

        class FakeAnthropicProvider:
            name = "anthropic"

            def __init__(self, api_key: str, model: str, base_url: str | None = None) -> None:
                captured["api_key"] = api_key
                captured["model"] = model
                captured["base_url"] = base_url
                self.model = model

        fake_module.AnthropicProvider = FakeAnthropicProvider
        original_module = sys.modules.get("server.llm.anthropic_provider")
        sys.modules["server.llm.anthropic_provider"] = fake_module
        try:
            build_provider(
                ProviderConfig(
                    provider="anthropic",
                    model="claude-sonnet-4-20250514",
                    anthropic_base_url="https://claude-gateway.example",
                    api_keys={"anthropic": "sk-test"},
                )
            )
        finally:
            if original_module is None:
                sys.modules.pop("server.llm.anthropic_provider", None)
            else:
                sys.modules["server.llm.anthropic_provider"] = original_module

        self.assertEqual(captured["api_key"], "sk-test")
        self.assertEqual(captured["model"], "claude-sonnet-4-20250514")
        self.assertEqual(captured["base_url"], "https://claude-gateway.example")

    def test_sorftime_quick_url_key_is_stored_as_secret(self) -> None:
        current = ProviderConfig(
            provider="anthropic",
            model="claude-sonnet-4-20250514",
            sorftime_mcp_url="https://mcp.sorftime.com",
        )

        merged = merge_provider_config(
            current,
            {
                "provider": "anthropic",
                "model": "claude-sonnet-4-20250514",
                "sorftime_mcp_url": "https://mcp.sorftime.com?locale=zh&key=sk-url-secret",
            },
        )

        self.assertEqual(merged.sorftime_mcp_url, "https://mcp.sorftime.com?locale=zh")
        self.assertEqual(merged.sorftime_api_key, "sk-url-secret")
        self.assertEqual(public_config(merged)["sorftime_mcp_url"], "https://mcp.sorftime.com?locale=zh")


class SorftimeDataSourceTests(unittest.TestCase):
    def test_build_sorftime_mcp_url_appends_key(self) -> None:
        self.assertEqual(
            build_sorftime_mcp_url("https://mcp.sorftime.com", "sk-test"),
            "https://mcp.sorftime.com?key=sk-test",
        )
        self.assertEqual(
            build_sorftime_mcp_url("https://mcp.sorftime.com?locale=zh", "sk-test"),
            "https://mcp.sorftime.com?locale=zh&key=sk-test",
        )

    def test_build_sorftime_mcp_url_keeps_existing_key(self) -> None:
        self.assertEqual(
            build_sorftime_mcp_url("https://mcp.sorftime.com?key=already", "sk-test"),
            "https://mcp.sorftime.com?key=already",
        )

    def test_build_sorftime_mcp_url_requires_url_and_key(self) -> None:
        with self.assertRaises(ValueError):
            build_sorftime_mcp_url("", "sk-test")
        with self.assertRaises(ValueError):
            build_sorftime_mcp_url("https://mcp.sorftime.com", "")


if __name__ == "__main__":
    unittest.main()
