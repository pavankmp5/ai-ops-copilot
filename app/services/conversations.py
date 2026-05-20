import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status

from app.core.auth import User
from app.core.db import execute, fetchall, fetchone, get_db_connection


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _default_title(question: str) -> str:
    cleaned = " ".join(question.strip().split())
    return (cleaned[:57] + "...") if len(cleaned) > 60 else cleaned


def create_chat_session(current_user: User, title: str | None = None) -> dict:
    now = _utc_now()
    session_id = str(uuid.uuid4())
    final_title = (title or "New Session").strip() or "New Session"
    with get_db_connection() as connection:
        execute(
            connection,
            """
            INSERT INTO chat_sessions (session_id, tenant_id, username, title, created_at, updated_at, archived_at)
            VALUES (:session_id, :tenant_id, :username, :title, :created_at, :updated_at, NULL)
            """,
            {
                "session_id": session_id,
                "tenant_id": current_user.tenant_id,
                "username": current_user.username,
                "title": final_title,
                "created_at": now,
                "updated_at": now,
            },
        )
    return {"session_id": session_id, "title": final_title, "created_at": now, "updated_at": now}


def list_chat_sessions(current_user: User, limit: int = 50) -> dict:
    capped_limit = max(1, min(limit, 200))
    with get_db_connection() as connection:
        rows = fetchall(
            connection,
            """
            SELECT session_id, title, created_at, updated_at
            FROM chat_sessions
            WHERE tenant_id = :tenant_id AND username = :username AND archived_at IS NULL
            ORDER BY updated_at DESC
            LIMIT :limit
            """,
            {"tenant_id": current_user.tenant_id, "username": current_user.username, "limit": capped_limit},
        )
    return {"count": len(rows), "sessions": [dict(row) for row in rows]}


def ensure_session_access(session_id: str, current_user: User) -> dict:
    with get_db_connection() as connection:
        session = fetchone(
            connection,
            """
            SELECT session_id, tenant_id, username, title, created_at, updated_at
            FROM chat_sessions
            WHERE session_id = :session_id AND archived_at IS NULL
            """,
            {"session_id": session_id},
        )
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found.")
    if session["tenant_id"] != current_user.tenant_id or session["username"] != current_user.username:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Session access denied.")
    return dict(session)


def get_or_create_session(current_user: User, session_id: str | None, question: str) -> dict:
    if session_id:
        return ensure_session_access(session_id.strip(), current_user)
    return create_chat_session(current_user, title=_default_title(question))


def persist_chat_interaction(
    current_user: User,
    *,
    session_id: str,
    question: str,
    answer: str,
    mode: str,
    dataset_id: str | None,
    answer_source: str,
    rag_used: bool,
    rag_context: str,
    latency_total_ms: float,
    latency_rag_ms: float,
    latency_llm_ms: float,
) -> dict:
    now = _utc_now()
    message_id = str(uuid.uuid4())
    retrieval_event_id = str(uuid.uuid4())
    context_excerpt = rag_context[:2000] if rag_context else None

    with get_db_connection() as connection:
        execute(
            connection,
            """
            INSERT INTO chat_messages (
                message_id, session_id, tenant_id, username, dataset_id, mode, question, answer, answer_source,
                rag_used, llm_model, latency_total_ms, latency_rag_ms, latency_llm_ms, created_at
            )
            VALUES (
                :message_id, :session_id, :tenant_id, :username, :dataset_id, :mode, :question, :answer, :answer_source,
                :rag_used, :llm_model, :latency_total_ms, :latency_rag_ms, :latency_llm_ms, :created_at
            )
            """,
            {
                "message_id": message_id,
                "session_id": session_id,
                "tenant_id": current_user.tenant_id,
                "username": current_user.username,
                "dataset_id": dataset_id,
                "mode": mode,
                "question": question,
                "answer": answer,
                "answer_source": answer_source,
                "rag_used": 1 if rag_used else 0,
                "llm_model": None,
                "latency_total_ms": latency_total_ms,
                "latency_rag_ms": latency_rag_ms,
                "latency_llm_ms": latency_llm_ms,
                "created_at": now,
            },
        )
        execute(
            connection,
            """
            INSERT INTO retrieval_events (
                event_id, session_id, message_id, tenant_id, dataset_id, rag_used, context_excerpt, created_at
            )
            VALUES (
                :event_id, :session_id, :message_id, :tenant_id, :dataset_id, :rag_used, :context_excerpt, :created_at
            )
            """,
            {
                "event_id": retrieval_event_id,
                "session_id": session_id,
                "message_id": message_id,
                "tenant_id": current_user.tenant_id,
                "dataset_id": dataset_id,
                "rag_used": 1 if rag_used else 0,
                "context_excerpt": context_excerpt,
                "created_at": now,
            },
        )
        execute(
            connection,
            """
            UPDATE chat_sessions
            SET updated_at = :updated_at
            WHERE session_id = :session_id
            """,
            {"updated_at": now, "session_id": session_id},
        )
    return {"message_id": message_id, "retrieval_event_id": retrieval_event_id}


def get_chat_session_detail(session_id: str, current_user: User) -> dict:
    session = ensure_session_access(session_id, current_user)
    with get_db_connection() as connection:
        messages = fetchall(
            connection,
            """
            SELECT
                message_id, session_id, dataset_id, mode, question, answer, answer_source, rag_used,
                latency_total_ms, latency_rag_ms, latency_llm_ms, created_at
            FROM chat_messages
            WHERE session_id = :session_id
            ORDER BY created_at ASC
            """,
            {"session_id": session_id},
        )
        retrieval = fetchall(
            connection,
            """
            SELECT event_id, message_id, dataset_id, rag_used, context_excerpt, created_at
            FROM retrieval_events
            WHERE session_id = :session_id
            ORDER BY created_at ASC
            """,
            {"session_id": session_id},
        )
    return {
        "session": session,
        "messages": [dict(row) for row in messages],
        "retrieval_events": [dict(row) for row in retrieval],
    }
