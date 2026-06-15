"""FastAPI 应用：会话管理 + 多轮 chat（tool-use 编排）。

仅在运行服务时才需要 fastapi/uvicorn；核心逻辑（llm/tools/sessions）不依赖本文件，可独立测试。
"""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from server.config import (
    SYSTEM_PROMPT,
    ProviderConfig,
    build_provider,
    load_provider_config,
    merge_provider_config,
    public_config,
    resolve_sorftime_api_key,
    save_provider_config,
)
from server.data_sources.sorftime import test_sorftime_mcp
from server.llm.loop import run_agent_turn, run_agent_turn_streaming
from server.sessions.store import Session, SessionStore
from server.tools.registry import ALL_TOOLS, make_dispatch
from packages.research_core.workflows import create_initial_state

ROOT = Path(__file__).resolve().parents[1]
SESSIONS_DIR = Path(os.environ.get("SESSIONS_DIR", ROOT / ".sessions"))
CONFIG_PATH = Path(os.environ.get("APP_CONFIG_PATH", ROOT / ".runtime" / "ai-config.json"))

app = FastAPI(title="AMZ Selection Workbench API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

store = SessionStore(persist_dir=SESSIONS_DIR)
ALLOWED_SITES = {"US", "CA", "MX"}


# ----------------------------- 请求/响应模型 -----------------------------

class CreateSessionRequest(BaseModel):
    mode: str = "mode_pending"  # mode_pending | broad_discovery | targeted_deep_dive
    intent: str = ""
    site: str = "US"


class UpdateSessionRequest(BaseModel):
    mode: str | None = None
    intent: str | None = None
    site: str | None = None


class ChatRequest(BaseModel):
    session_id: str
    message: str


class ConfigUpdate(BaseModel):
    provider: str
    model: str
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    anthropic_base_url: str | None = None
    openai_base_url: str | None = None
    sorftime_mcp_url: str | None = None
    sorftime_api_key: str | None = None
    clear_anthropic_key: bool = False
    clear_openai_key: bool = False
    clear_sorftime_key: bool = False


_runtime_config: ProviderConfig = load_provider_config(CONFIG_PATH)


# ----------------------------- 路由 -----------------------------

@app.get("/api/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "provider": _runtime_config.provider, "model": _runtime_config.model}


@app.get("/api/config")
def get_config() -> dict[str, Any]:
    return public_config(_runtime_config)


@app.post("/api/config")
def update_config(payload: ConfigUpdate) -> dict[str, Any]:
    global _runtime_config
    _runtime_config = merge_provider_config(_runtime_config, payload.model_dump())
    save_provider_config(CONFIG_PATH, _runtime_config)
    return get_config()


@app.post("/api/config/test")
def test_config(payload: ConfigUpdate | None = None) -> dict[str, Any]:
    candidate = _runtime_config
    if payload is not None:
        candidate = merge_provider_config(_runtime_config, payload.model_dump())
    try:
        provider = build_provider(candidate)
        turn = provider.complete(
            system="你是一个连接测试助手。只回复 OK。",
            messages=[{"role": "user", "content": "请回复 OK，用来测试模型连接。"}],
            tools=[],
        )
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"模型调用失败：{exc}") from exc
    return {
        "ok": True,
        "provider": provider.name,
        "model": provider.model,
        "message": f"模型连接成功，返回：{(turn.text or '').strip()[:80] or 'OK'}",
    }


@app.post("/api/config/data-sources/test")
def test_data_sources(payload: ConfigUpdate | None = None) -> dict[str, Any]:
    candidate = _runtime_config
    if payload is not None:
        candidate = merge_provider_config(_runtime_config, payload.model_dump())
    try:
        return test_sorftime_mcp(candidate.sorftime_mcp_url, resolve_sorftime_api_key(candidate))
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Sorftime MCP 测试失败：{exc}") from exc


@app.post("/api/sessions")
def create_session(payload: CreateSessionRequest) -> dict[str, Any]:
    if payload.mode not in ("mode_pending", "broad_discovery", "targeted_deep_dive"):
        raise HTTPException(status_code=400, detail="mode 必须是 mode_pending、broad_discovery 或 targeted_deep_dive")
    site = _normalize_site(payload.site)
    session_id = uuid.uuid4().hex[:12]
    state = None
    if payload.mode != "mode_pending":
        state = create_initial_state(
            workflow_id=session_id,
            mode=payload.mode,  # type: ignore[arg-type]
            initial_intent=payload.intent,
            site=site,
        ).to_dict()
    session = Session(
        session_id=session_id,
        mode=payload.mode,
        intent=payload.intent,
        site=site,
        workflow_state=state,
    )
    store.create(session)
    return session.to_dict()


@app.get("/api/sessions/{session_id}")
def get_session(session_id: str) -> dict[str, Any]:
    session = store.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    return session.to_dict()


@app.patch("/api/sessions/{session_id}")
def update_session(session_id: str, payload: UpdateSessionRequest) -> dict[str, Any]:
    session = store.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    next_mode = payload.mode or session.mode
    if next_mode not in ("mode_pending", "broad_discovery", "targeted_deep_dive"):
        raise HTTPException(status_code=400, detail="mode 必须是 mode_pending、broad_discovery 或 targeted_deep_dive")

    next_intent = session.intent if payload.intent is None else payload.intent.strip()
    next_site = _normalize_site(session.site, reject_invalid=False) if payload.site is None else _normalize_site(payload.site)

    should_rebuild_state = (
        next_mode != "mode_pending"
        and (
            session.workflow_state is None
            or next_mode != session.mode
            or next_intent != session.intent
            or next_site != session.site
        )
    )
    session.mode = next_mode
    session.intent = next_intent
    session.site = next_site
    if next_mode == "mode_pending":
        session.workflow_state = None
    elif should_rebuild_state:
        session.workflow_state = create_initial_state(
            workflow_id=session.session_id,
            mode=next_mode,  # type: ignore[arg-type]
            initial_intent=next_intent,
            site=next_site,
        ).to_dict()

    store.save(session)
    return session.to_dict()


def _normalize_site(site: str | None, *, reject_invalid: bool = True) -> str:
    value = (site or "US").strip().upper() or "US"
    if value in ALLOWED_SITES:
        return value
    if reject_invalid:
        raise HTTPException(status_code=400, detail="站点仅支持 US、CA、MX")
    return "US"


@app.post("/api/upload")
async def upload_files(session_id: str = Form(...), files: list[UploadFile] = File(...)) -> dict[str, Any]:
    session = store.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    upload_dir = SESSIONS_DIR / session_id / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    saved: list[str] = []
    for upload in files:
        name = Path(upload.filename or "file").name
        dest = upload_dir / name
        dest.write_bytes(await upload.read())
        saved.append(name)

    session.artifacts["upload_folder"] = str(upload_dir)
    existing = set(session.artifacts.get("uploaded_files", []))
    session.artifacts["uploaded_files"] = sorted(existing | set(saved))
    store.save(session)
    return {
        "session_id": session_id,
        "upload_folder": str(upload_dir),
        "saved": saved,
        "total": len(session.artifacts["uploaded_files"]),
    }


@app.post("/api/chat")
def chat(payload: ChatRequest) -> dict[str, Any]:
    session = store.get(payload.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    try:
        provider = build_provider(_runtime_config)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    session.messages.append({"role": "user", "content": payload.message})
    result = run_agent_turn(
        provider=provider,
        system=SYSTEM_PROMPT,
        messages=session.messages,
        tools=ALL_TOOLS,
        dispatch=make_dispatch(session),
    )
    store.save(session)

    return {
        "session_id": session.session_id,
        "reply": result.final_text,
        "tool_runs": [run.to_dict() for run in result.tool_runs],
        "steps": result.steps,
        "stopped_reason": result.stopped_reason,
        "artifacts_keys": list(session.artifacts.keys()),
    }


@app.post("/api/chat/stream")
def chat_stream(payload: ChatRequest) -> StreamingResponse:
    session = store.get(payload.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    try:
        provider = build_provider(_runtime_config)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    session.messages.append({"role": "user", "content": payload.message})

    def event_stream():
        try:
            for event in run_agent_turn_streaming(
                provider=provider,
                system=SYSTEM_PROMPT,
                messages=session.messages,
                tools=ALL_TOOLS,
                dispatch=make_dispatch(session),
            ):
                yield _sse(event)
            store.save(session)
            yield _sse({"type": "session", "artifacts_keys": list(session.artifacts.keys())})
        except Exception as exc:  # noqa: BLE001
            store.save(session)
            yield _sse({"type": "error", "message": str(exc)})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _sse(data: dict[str, Any]) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"
