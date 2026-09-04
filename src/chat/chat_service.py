"""
Chat history service — persists Ask-page conversations across sessions.

Each session holds an ordered list of messages (the user's questions and the
system's answers, with their sources / verification / evaluation payloads). The
Ask page lists saved sessions so a user can reload an earlier conversation.

Storage: data/chat_sessions.json (gitignored — may contain client-specific
questions and answers).
"""
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

CHAT_PATH = Path("data/chat_sessions.json")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class ChatSession(BaseModel):
    """One saved Ask-page conversation."""
    session_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    title: str = "New chat"
    # Messages are stored as flexible dicts so the answer payload (sources,
    # verification, evaluation) round-trips without a rigid schema.
    messages: list[dict[str, Any]] = Field(default_factory=list)
    created_at: str = Field(default_factory=_now)
    updated_at: str = Field(default_factory=_now)


class ChatSessionSummary(BaseModel):
    """Lightweight session entry for the history list (no message bodies)."""
    session_id: str
    title: str
    message_count: int
    created_at: str
    updated_at: str


def _load() -> list[ChatSession]:
    if not CHAT_PATH.exists():
        return []
    try:
        data = json.loads(CHAT_PATH.read_text(encoding="utf-8"))
        return [ChatSession.model_validate(s) for s in data]
    except Exception:
        return []


def _save(sessions: list[ChatSession]) -> None:
    CHAT_PATH.parent.mkdir(parents=True, exist_ok=True)
    CHAT_PATH.write_text(
        json.dumps([s.model_dump() for s in sessions], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _derive_title(messages: list[dict[str, Any]]) -> str:
    """Use the first user message as the title, truncated."""
    for m in messages:
        if m.get("role") == "user" and m.get("content"):
            text = m["content"].strip().replace("\n", " ")
            return text[:60] + ("…" if len(text) > 60 else "")
    return "New chat"


def list_sessions() -> list[ChatSessionSummary]:
    """List saved sessions, most recently updated first."""
    sessions = sorted(_load(), key=lambda s: s.updated_at, reverse=True)
    return [
        ChatSessionSummary(
            session_id=s.session_id,
            title=s.title,
            message_count=len(s.messages),
            created_at=s.created_at,
            updated_at=s.updated_at,
        )
        for s in sessions
    ]


def get_session(session_id: str) -> ChatSession | None:
    """Return a full session by id, or None if not found."""
    for s in _load():
        if s.session_id == session_id:
            return s
    return None


def save_session(
    messages: list[dict[str, Any]],
    session_id: str | None = None,
    title: str | None = None,
) -> ChatSession:
    """
    Create or update a session.

    If session_id matches an existing session it is updated in place;
    otherwise a new session is created. Title defaults to the first question.
    """
    sessions = _load()
    resolved_title = title or _derive_title(messages)

    if session_id:
        for s in sessions:
            if s.session_id == session_id:
                s.messages = messages
                s.title = resolved_title
                s.updated_at = _now()
                _save(sessions)
                return s

    session = ChatSession(title=resolved_title, messages=messages)
    if session_id:
        session.session_id = session_id
    sessions.append(session)
    _save(sessions)
    return session


def delete_session(session_id: str) -> bool:
    """Delete a session. Returns True if one was removed."""
    sessions = _load()
    remaining = [s for s in sessions if s.session_id != session_id]
    if len(remaining) == len(sessions):
        return False
    _save(remaining)
    return True
