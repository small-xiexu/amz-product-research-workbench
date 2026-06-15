"""Sorftime MCP 连接测试。

测试只做最小 MCP 握手与 tools/list，不记录、不返回完整 Key。
"""

from __future__ import annotations

import json
import ssl
from dataclasses import dataclass
from typing import Any
from urllib import error, request
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


CLIENT_NAME = "amz-product-research-workbench"
PROTOCOL_VERSION = "2025-03-26"


@dataclass
class RpcHttpResponse:
    body: str
    session_id: str | None = None


def build_sorftime_mcp_url(base_url: str, api_key: str) -> str:
    cleaned = str(base_url or "").strip()
    if not cleaned:
        raise ValueError("Sorftime MCP URL 未配置。")

    parts = urlsplit(cleaned)
    if not parts.scheme or not parts.netloc:
        raise ValueError("Sorftime MCP URL 需要包含 http:// 或 https://。")

    query = parse_qsl(parts.query, keep_blank_values=True)
    has_key_in_url = any(key.lower() == "key" and value for key, value in query)
    cleaned_key = str(api_key or "").strip()
    if not has_key_in_url and not cleaned_key:
        raise ValueError("Sorftime MCP Key 未配置，请先填写 Key 后再测试。")
    if cleaned_key and not has_key_in_url:
        query.append(("key", cleaned_key))

    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def test_sorftime_mcp(base_url: str, api_key: str, timeout: float = 15.0) -> dict[str, Any]:
    url = build_sorftime_mcp_url(base_url, api_key)

    init = _post_json_rpc(
        url,
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": CLIENT_NAME, "version": "0.1.0"},
            },
        },
        timeout=timeout,
    )
    _require_rpc_success(init.body, "初始化")

    try:
        _post_json_rpc(
            url,
            {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
            timeout=timeout,
            session_id=init.session_id,
        )
    except RuntimeError:
        # 部分 Streamable HTTP 实现不会给 notification 返回正文，不影响后续 tools/list。
        pass

    tools_resp = _post_json_rpc(
        url,
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        timeout=timeout,
        session_id=init.session_id,
    )
    tools_rpc = _require_rpc_success(tools_resp.body, "读取工具列表")
    tools = ((tools_rpc.get("result") or {}).get("tools") or [])
    tool_names = [
        tool.get("name")
        for tool in tools
        if isinstance(tool, dict) and isinstance(tool.get("name"), str)
    ]

    return {
        "ok": True,
        "source": "sorftime",
        "message": f"Sorftime MCP 连接成功，识别到 {len(tool_names)} 个工具。",
        "tool_count": len(tool_names),
        "tools": tool_names[:20],
    }


def _post_json_rpc(url: str, payload: dict[str, Any], timeout: float, session_id: str | None = None) -> RpcHttpResponse:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    if session_id:
        headers["Mcp-Session-Id"] = session_id

    req = request.Request(url, data=data, headers=headers, method="POST")
    try:
        with request.urlopen(req, timeout=timeout, context=_ssl_context()) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return RpcHttpResponse(body=body, session_id=resp.headers.get("mcp-session-id"))
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        message = _safe_error_from_body(body) or exc.reason or "HTTP 请求失败"
        raise RuntimeError(f"Sorftime MCP 调用失败：HTTP {exc.code}，{message}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"Sorftime MCP 连接失败：{exc.reason}") from exc
    except TimeoutError as exc:
        raise RuntimeError("Sorftime MCP 连接超时，请检查 URL 或网络。") from exc


def _ssl_context() -> ssl.SSLContext:
    try:
        import certifi
    except ImportError:  # pragma: no cover
        return ssl.create_default_context()
    return ssl.create_default_context(cafile=certifi.where())


def _require_rpc_success(body: str, action: str) -> dict[str, Any]:
    payload = _parse_rpc_payload(body)
    if not isinstance(payload, dict):
        raise RuntimeError(f"Sorftime MCP {action}失败：返回格式不是 JSON-RPC。")
    if payload.get("error"):
        error_payload = payload.get("error") or {}
        message = error_payload.get("message") if isinstance(error_payload, dict) else str(error_payload)
        raise RuntimeError(f"Sorftime MCP {action}失败：{message or '未知错误'}")
    return payload


def _parse_rpc_payload(body: str) -> Any:
    stripped = body.strip()
    if not stripped:
        return {}
    if stripped.startswith("event:") or "\ndata:" in stripped or stripped.startswith("data:"):
        for line in stripped.splitlines():
            line = line.strip()
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if not data or data == "[DONE]":
                continue
            try:
                return json.loads(data)
            except json.JSONDecodeError:
                continue
        return {}
    return json.loads(stripped)


def _safe_error_from_body(body: str) -> str:
    try:
        payload = _parse_rpc_payload(body)
    except (TypeError, json.JSONDecodeError):
        payload = None
    if isinstance(payload, dict):
        detail = payload.get("detail") or payload.get("message")
        if isinstance(detail, str):
            return detail[:160]
        error_payload = payload.get("error")
        if isinstance(error_payload, dict) and isinstance(error_payload.get("message"), str):
            return error_payload["message"][:160]
    return body.strip()[:160]
