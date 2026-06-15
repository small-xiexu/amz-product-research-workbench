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
from packages.research_core.pipeline.build_candidate_pool_from_import_manifest import build_candidate_pool

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

BUILD_CANDIDATE_POOL = ToolSpec(
    name="build_candidate_pool",
    description=(
        "基于当前会话已盘点的卖家精灵导入数据，构建候选品池（含候选方向、需求证据、竞争结构、"
        "建议评论 VOC ASIN 批次等）。必须先调用 inspect_manual_exports。"
    ),
    input_schema={"type": "object", "properties": {}, "required": []},
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


def _handle_build_candidate_pool(session: Session, args: dict[str, Any]) -> dict[str, Any]:
    manifest = session.artifacts.get("manifest")
    if not manifest:
        raise RuntimeError("尚无 manifest，请先调用 inspect_manual_exports。")
    pool = build_candidate_pool(manifest)
    session.artifacts["candidate_pool"] = pool

    metadata = pool.get("metadata", {})
    candidates = pool.get("candidates", [])
    primary = candidates[0] if candidates else {}
    return {
        "ok": True,
        "pool_id": metadata.get("pool_id"),
        "site": metadata.get("site"),
        "candidate_count": len(candidates),
        "primary_candidate_name": primary.get("candidate_name") or primary.get("name"),
        "direction_card_count": len(pool.get("direction_cards", []) or []),
        "next_review_voc_asin_count": len(pool.get("next_review_voc_asins", []) or []),
        "hint": "候选池已生成并存入会话，可在工作台查看候选方向并选择主线。",
    }


_HANDLERS: dict[str, ToolHandler] = {
    INSPECT_MANUAL_EXPORTS.name: _handle_inspect_manual_exports,
    BUILD_CANDIDATE_POOL.name: _handle_build_candidate_pool,
}

ALL_TOOLS: list[ToolSpec] = [INSPECT_MANUAL_EXPORTS, BUILD_CANDIDATE_POOL]


def make_dispatch(session: Session) -> Callable[[str, dict[str, Any]], dict[str, Any]]:
    """绑定到具体会话的工具分发器，交给 run_agent_turn 使用。"""

    def dispatch(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        handler = _HANDLERS.get(name)
        if handler is None:
            raise KeyError(f"未知工具：{name}")
        return handler(session, arguments)

    return dispatch
