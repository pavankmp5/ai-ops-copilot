import logging
import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from app.core.db import execute, fetchall, get_db_connection
from app.core.request_context import get_request_id

if TYPE_CHECKING:
    from app.core.auth import User

logger = logging.getLogger(__name__)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def record_audit_event(
    event_type: str,
    actor_username: str | None,
    tenant_id: str | None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    detail: str | None = None,
    request_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    metadata: dict | None = None,
) -> None:
    resolved_request_id = request_id or get_request_id()
    with get_db_connection() as connection:
        execute(
            connection,
            """
            INSERT INTO audit_logs (
                event_type,
                actor_username,
                tenant_id,
                resource_type,
                resource_id,
                detail,
                request_id,
                ip_address,
                user_agent,
                metadata_json,
                created_at
            )
            VALUES (
                :event_type,
                :actor_username,
                :tenant_id,
                :resource_type,
                :resource_id,
                :detail,
                :request_id,
                :ip_address,
                :user_agent,
                :metadata_json,
                :created_at
            )
            """,
            {
                "event_type": event_type,
                "actor_username": actor_username,
                "tenant_id": tenant_id,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "detail": detail,
                "request_id": resolved_request_id,
                "ip_address": ip_address,
                "user_agent": user_agent,
                "metadata_json": json.dumps(metadata, ensure_ascii=True) if metadata else None,
                "created_at": _utc_now(),
            },
        )

    logger.info(
        "Audit event recorded event_type=%s actor=%s tenant=%s resource_type=%s resource_id=%s request_id=%s",
        event_type,
        actor_username,
        tenant_id,
        resource_type,
        resource_id,
        resolved_request_id,
    )


def list_audit_logs(current_user: "User", limit: int = 50) -> dict:
    capped_limit = max(1, min(limit, 200))
    with get_db_connection() as connection:
        rows = fetchall(
            connection,
            """
            SELECT
                event_type,
                actor_username,
                tenant_id,
                resource_type,
                resource_id,
                detail,
                request_id,
                ip_address,
                user_agent,
                metadata_json,
                created_at
            FROM audit_logs
            WHERE tenant_id = :tenant_id
            ORDER BY created_at DESC
            LIMIT :limit
            """,
            {"tenant_id": current_user.tenant_id, "limit": capped_limit},
        )

    return {
        "count": len(rows),
        "logs": [dict(row) for row in rows],
    }
