"""工具注册表：把 `packages/research_core/pipeline` 的纯数据函数包装成 LLM 可调用工具。

设计要点：
- 工具操作的是「当前会话」的产出物（manifest / candidate_pool 等），LLM 只需传简单参数。
- 工具返回「摘要」给 LLM（控制 token），完整产出物存进会话 artifacts。
- A 类工具 = AI 可自动执行（本文件）；B 类「请运营操作」动作卡由 workflow 层产出，不在此注册。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from server.llm.base import ToolSpec
from server.sessions.store import Session

# 复用现有数据逻辑
from packages.research_core.pipeline.inspect_manual_exports import build_manifest

from packages.research_core.workflows import create_initial_state

ToolHandler = Callable[[Session, dict[str, Any]], dict[str, Any]]


# ----------------------------- 工具定义 -----------------------------

INSPECT_MANUAL_EXPORTS = ToolSpec(
    name="inspect_manual_exports",
    description=(
        "盘点运营上传/指定的卖家精灵导出文件夹，识别搜索结果、市场分析、关键词反查、ABA 等数据源，"
        "并检查缺失项。运营完成卖家精灵导出并上传后调用。若不传 folder，则使用本会话最近上传的文件夹。"
        "结果存入会话，供后续构建候选池使用。"
    ),
    input_schema={
        "type": "object",
        "properties": {
            "folder": {"type": "string", "description": "卖家精灵导出文件夹的本地路径（可选，默认用会话已上传目录）"},
            "task_name": {"type": "string", "description": "任务名（可选）"},
            "site": {"type": "string", "description": "站点，仅支持 US、CA、MX（可选，默认 US）"},
        },
        "required": [],
    },
)

SET_RESEARCH_MODE = ToolSpec(
    name="set_research_mode",
    description=(
        "根据运营的自然语言意图，自动确定本轮选品模式并写回会话。"
        "仅在你已判断本轮更接近无方向探索或指定方向深挖时调用。"
    ),
    input_schema={
        "type": "object",
        "properties": {
            "mode": {
                "type": "string",
                "enum": ["broad_discovery", "targeted_deep_dive"],
                "description": "本轮内部模式",
            },
            "intent": {"type": "string", "description": "对运营当前选品意图的简短归纳"},
            "site": {"type": "string", "description": "站点，仅支持 US、CA、MX（可选）"},
            "reason": {"type": "string", "description": "为何判断成该模式（可选）"},
        },
        "required": ["mode", "intent"],
    },
)


# ----------------------------- 工具实现 -----------------------------

def _handle_inspect_manual_exports(session: Session, args: dict[str, Any]) -> dict[str, Any]:
    folder_arg = args.get("folder") or session.artifacts.get("upload_folder")
    if not folder_arg:
        raise RuntimeError("尚未上传卖家精灵导出文件，请先让运营上传。")
    folder = Path(folder_arg).expanduser()
    if not folder.is_dir():
        raise FileNotFoundError(f"文件夹不存在：{folder}")
    manifest = build_manifest(folder, args.get("task_name"), args.get("site") or session.site or "US")
    session.artifacts["manifest"] = manifest

    metadata = manifest.get("metadata", {})
    return {
        "ok": True,
        "site": metadata.get("site"),
        "task_name": metadata.get("task_name"),
        "available_sources": manifest.get("available_sources", []),
        "missing_sources": manifest.get("missing_sources", []),
        "file_count": len(manifest.get("files", [])),
        "hint": "数据已盘点并存入会话。可调用 build_candidate_pool 构建候选池。",
    }


def _handle_set_research_mode(session: Session, args: dict[str, Any]) -> dict[str, Any]:
    mode = str(args.get("mode") or "").strip()
    if mode not in {"broad_discovery", "targeted_deep_dive"}:
        raise ValueError("mode 必须是 broad_discovery 或 targeted_deep_dive")

    intent = str(args.get("intent") or session.intent or "").strip()
    if not intent:
        raise ValueError("intent 不能为空")

    site = str(args.get("site") or session.site or "US").strip().upper() or "US"
    if site not in {"US", "CA", "MX"}:
        site = session.site or "US"

    session.mode = mode
    session.intent = intent
    session.site = site
    session.workflow_state = create_initial_state(
        workflow_id=session.session_id,
        mode=mode,  # type: ignore[arg-type]
        initial_intent=intent,
        site=site,
    ).to_dict()

    return {
        "ok": True,
        "mode": mode,
        "intent": intent,
        "site": site,
        "stage": session.workflow_state.get("stage") if session.workflow_state else None,
        "question": session.workflow_state.get("operator_question") if session.workflow_state else None,
        "hint": "模式已写回会话，接下来可继续问运营问题或调用数据盘点工具。",
    }



_HANDLERS: dict[str, ToolHandler] = {
    SET_RESEARCH_MODE.name: _handle_set_research_mode,
    INSPECT_MANUAL_EXPORTS.name: _handle_inspect_manual_exports,
}

ALL_TOOLS: list[ToolSpec] = [SET_RESEARCH_MODE, INSPECT_MANUAL_EXPORTS]


def make_dispatch(session: Session) -> Callable[[str, dict[str, Any]], dict[str, Any]]:
    """绑定到具体会话的工具分发器，交给 run_agent_turn 使用。"""

    def dispatch(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        handler = _HANDLERS.get(name)
        if handler is None:
            raise KeyError(f"未知工具：{name}")
        return handler(session, arguments)

    return dispatch
