"""会话状态存储：每个会话持有交互状态、对话历史和产出物（manifest / candidate_pool 等）。

MVP 用进程内字典 + 可选 JSON 落盘。后续可替换为 SQLite，无需改上层。
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Session:
    """单个选品会话的全部可序列化状态。"""

    session_id: str
    mode: str = "targeted_deep_dive"
    intent: str = ""
    site: str = "US"
    messages: list[dict[str, Any]] = field(default_factory=list)
    workflow_state: dict[str, Any] | None = None
    artifacts: dict[str, Any] = field(default_factory=dict)  # manifest / candidate_pool / research_package ...

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "mode": self.mode,
            "intent": self.intent,
            "site": self.site,
            "messages": self.messages,
            "workflow_state": self.workflow_state,
            "artifacts": self.artifacts,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Session":
        return cls(
            session_id=data["session_id"],
            mode=data.get("mode", "targeted_deep_dive"),
            intent=data.get("intent", ""),
            site=data.get("site", "US"),
            messages=data.get("messages", []),
            workflow_state=data.get("workflow_state"),
            artifacts=data.get("artifacts", {}),
        )


class SessionStore:
    """线程安全的会话存储，按 session_id 索引。"""

    def __init__(self, persist_dir: Path | str | None = None) -> None:
        self._lock = threading.Lock()
        self._sessions: dict[str, Session] = {}
        self._persist_dir = Path(persist_dir) if persist_dir else None
        if self._persist_dir:
            self._persist_dir.mkdir(parents=True, exist_ok=True)
            self._load_all()

    def create(self, session: Session) -> Session:
        with self._lock:
            self._sessions[session.session_id] = session
        self._persist(session)
        return session

    def get(self, session_id: str) -> Session | None:
        with self._lock:
            return self._sessions.get(session_id)

    def save(self, session: Session) -> None:
        with self._lock:
            self._sessions[session.session_id] = session
        self._persist(session)

    def list_ids(self) -> list[str]:
        with self._lock:
            return list(self._sessions.keys())

    def _persist(self, session: Session) -> None:
        if not self._persist_dir:
            return
        path = self._persist_dir / f"{session.session_id}.json"
        path.write_text(json.dumps(session.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    def _load_all(self) -> None:
        assert self._persist_dir is not None
        for path in self._persist_dir.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                session = Session.from_dict(data)
                self._sessions[session.session_id] = session
            except (json.JSONDecodeError, KeyError):
                continue
