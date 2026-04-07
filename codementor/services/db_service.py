"""
Database CRUD operations using Reflex's built-in SQLModel session.
Abstracts all DB calls away from the State layer.
"""

import reflex as rx
from datetime import datetime


# ─── Snippet CRUD ─────────────────────────────────────────────────────────────

def save_snippet(data: dict) -> dict | None:
    """Insert or return a new snippet. Returns the saved record as dict."""
    from codementor.models.snippet import Snippet

    try:
        with rx.session() as session:
            snippet = Snippet(
                title=data.get("title", "untitled.py"),
                code=data.get("code", ""),
                language=data.get("language", "python"),
                style_score=data.get("style_score", 0),
                error_count=data.get("error_count", 0),
                style_issue_count=data.get("style_issue_count", 0),
                created_at=datetime.utcnow().isoformat(),
            )
            session.add(snippet)
            session.commit()
            session.refresh(snippet)
            return snippet.dict()
    except Exception as e:
        print(f"DB save_snippet error: {e}")
        return None


def get_snippets(limit: int = 50) -> list[dict]:
    """Return recent snippets ordered by creation time desc."""
    from codementor.models.snippet import Snippet
    from sqlmodel import select

    try:
        with rx.session() as session:
            results = session.exec(
                select(Snippet).order_by(Snippet.id.desc()).limit(limit)
            ).all()
            return [s.dict() for s in results]
    except Exception as e:
        print(f"DB get_snippets error: {e}")
        return []


def get_snippet_by_id(snippet_id: int) -> dict | None:
    """Fetch a single snippet by ID."""
    from codementor.models.snippet import Snippet

    try:
        with rx.session() as session:
            snippet = session.get(Snippet, snippet_id)
            return snippet.dict() if snippet else None
    except Exception as e:
        print(f"DB get_snippet_by_id error: {e}")
        return None


def delete_snippet(snippet_id: int) -> bool:
    """Delete a snippet and cascade to related records."""
    from codementor.models.snippet import Snippet

    try:
        with rx.session() as session:
            snippet = session.get(Snippet, snippet_id)
            if snippet:
                session.delete(snippet)
                session.commit()
                return True
        return False
    except Exception as e:
        print(f"DB delete_snippet error: {e}")
        return False


# ─── Chat Log CRUD ────────────────────────────────────────────────────────────

def save_chat_message(snippet_id: int, role: str, content: str) -> bool:
    """Append a chat message to the log."""
    from codementor.models.chat_log import ChatLog

    try:
        with rx.session() as session:
            log = ChatLog(
                snippet_id=snippet_id,
                role=role,
                content=content,
                timestamp=datetime.utcnow().isoformat(),
            )
            session.add(log)
            session.commit()
            return True
    except Exception as e:
        print(f"DB save_chat_message error: {e}")
        return False


def get_chat_history(snippet_id: int) -> list[dict]:
    """Get all chat messages for a snippet."""
    from codementor.models.chat_log import ChatLog
    from sqlmodel import select

    try:
        with rx.session() as session:
            results = session.exec(
                select(ChatLog)
                .where(ChatLog.snippet_id == snippet_id)
                .order_by(ChatLog.id)
            ).all()
            return [c.dict() for c in results]
    except Exception as e:
        print(f"DB get_chat_history error: {e}")
        return []
