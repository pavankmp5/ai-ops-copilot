import logging
from datetime import UTC, datetime

from fastapi import HTTPException, status

from app.core.auth import User, get_user_by_username
from app.core.db import execute, fetchall, fetchone, get_db_connection, is_postgres
from app.services.audit import record_audit_event

logger = logging.getLogger(__name__)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def ensure_dataset_access(dataset_id: str, current_user: User) -> None:
    with get_db_connection() as connection:
        dataset_row = fetchone(
            connection,
            """
            SELECT tenant_id, owner_username
            FROM datasets
            WHERE dataset_id = :dataset_id
            """,
            {"dataset_id": dataset_id},
        )

        access_row = fetchone(
            connection,
            """
            SELECT 1
            FROM dataset_access
            WHERE username = :username AND dataset_id = :dataset_id
            """,
            {"username": current_user.username, "dataset_id": dataset_id},
        )

    if not dataset_row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset '{dataset_id}' not found.",
        )

    if dataset_row["tenant_id"] != current_user.tenant_id:
        logger.warning(
            "Cross-tenant access denied user='%s' tenant='%s' dataset='%s' dataset_tenant='%s'",
            current_user.username,
            current_user.tenant_id,
            dataset_id,
            dataset_row["tenant_id"],
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"User '{current_user.username}' cannot access dataset '{dataset_id}' from another tenant.",
        )

    if current_user.role == "admin":
        return

    if dataset_row["owner_username"] == current_user.username or access_row:
        return

    logger.warning(
        "User '%s' denied access to dataset '%s'",
        current_user.username,
        dataset_id,
    )
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=f"User '{current_user.username}' is not allowed to access dataset '{dataset_id}'.",
    )


def assign_dataset_owner(dataset_id: str, username: str, tenant_id: str, file_hash: str, file_name: str) -> None:
    user = get_user_by_username(username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User '{username}' not found.",
        )

    with get_db_connection() as connection:
        execute(
            connection,
            """
            INSERT INTO datasets (dataset_id, tenant_id, owner_username, file_hash, file_name, created_at)
            VALUES (:dataset_id, :tenant_id, :username, :file_hash, :file_name, :created_at)
            """,
            {
                "dataset_id": dataset_id,
                "tenant_id": tenant_id,
                "username": username,
                "file_hash": file_hash,
                "file_name": file_name,
                "created_at": _utc_now(),
            },
        )

    record_audit_event(
        event_type="dataset.create",
        actor_username=username,
        tenant_id=tenant_id,
        resource_type="dataset",
        resource_id=dataset_id,
        detail=f"Dataset '{file_name}' created.",
    )
    logger.info("Assigned dataset '%s' to owner '%s' tenant='%s'", dataset_id, username, tenant_id)


def get_dataset_owner(dataset_id: str) -> str | None:
    with get_db_connection() as connection:
        row = fetchone(
            connection,
            """
            SELECT owner_username
            FROM datasets
            WHERE dataset_id = :dataset_id
            """,
            {"dataset_id": dataset_id},
        )
    return row["owner_username"] if row else None


def get_dataset_metadata(dataset_id: str) -> dict | None:
    with get_db_connection() as connection:
        row = fetchone(
            connection,
            """
            SELECT dataset_id, tenant_id, owner_username, file_name, created_at
            FROM datasets
            WHERE dataset_id = :dataset_id
            """,
            {"dataset_id": dataset_id},
        )
    return dict(row) if row else None


def get_dataset_id_by_hash(file_hash: str, tenant_id: str) -> str | None:
    with get_db_connection() as connection:
        row = fetchone(
            connection,
            """
            SELECT dataset_id
            FROM datasets
            WHERE file_hash = :file_hash AND tenant_id = :tenant_id
            """,
            {"file_hash": file_hash, "tenant_id": tenant_id},
        )
    return row["dataset_id"] if row else None


def register_dataset_hash(dataset_id: str, file_hash: str) -> None:
    logger.info("Dataset '%s' hash registration confirmed hash='%s'", dataset_id, file_hash[:12])


def grant_dataset_access(username: str, dataset_id: str, granted_by_username: str | None = None) -> None:
    user = get_user_by_username(username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User '{username}' not found.",
        )

    if user.role == "admin":
        return

    with get_db_connection() as connection:
        if is_postgres():
            execute(
                connection,
                """
                INSERT INTO dataset_access (username, dataset_id, shared_by_username, created_at)
                VALUES (:username, :dataset_id, :shared_by_username, :created_at)
                ON CONFLICT (username, dataset_id) DO NOTHING
                """,
                {
                    "username": username,
                    "dataset_id": dataset_id,
                    "shared_by_username": granted_by_username,
                    "created_at": _utc_now(),
                },
            )
        else:
            connection.exec_driver_sql(
                """
                INSERT OR IGNORE INTO dataset_access (username, dataset_id, shared_by_username, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (username, dataset_id, granted_by_username, _utc_now()),
            )

    logger.info("Granted dataset '%s' to user '%s'", dataset_id, username)


def share_dataset(dataset_id: str, target_username: str, current_user: User) -> dict:
    target_user = get_user_by_username(target_username)
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User '{target_username}' not found.",
        )

    with get_db_connection() as connection:
        dataset_row = fetchone(
            connection,
            """
            SELECT tenant_id, owner_username
            FROM datasets
            WHERE dataset_id = :dataset_id
            """,
            {"dataset_id": dataset_id},
        )

    if not dataset_row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset '{dataset_id}' not found.",
        )

    if dataset_row["tenant_id"] != current_user.tenant_id or target_user.tenant_id != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Datasets can only be shared within the same tenant.",
        )

    if current_user.role != "admin" and dataset_row["owner_username"] != current_user.username:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the dataset owner or an admin can share this dataset.",
        )

    grant_dataset_access(target_username, dataset_id, granted_by_username=current_user.username)
    record_audit_event(
        event_type="dataset.share",
        actor_username=current_user.username,
        tenant_id=current_user.tenant_id,
        resource_type="dataset",
        resource_id=dataset_id,
        detail=f"Shared with user '{target_username}'.",
    )
    return {
        "message": "Dataset shared successfully.",
        "dataset_id": dataset_id,
        "shared_with": target_username,
        "tenant_id": current_user.tenant_id,
    }


def list_dataset_records(current_user: User | None = None) -> list[dict]:
    if current_user is None:
        query = """
            SELECT dataset_id, tenant_id, file_name, owner_username, created_at
            FROM datasets
            ORDER BY created_at DESC
        """
        params: dict = {}
    elif current_user.role == "admin":
        query = """
            SELECT dataset_id, tenant_id, file_name, owner_username, created_at
            FROM datasets
            WHERE tenant_id = :tenant_id
            ORDER BY created_at DESC
        """
        params = {"tenant_id": current_user.tenant_id}
    else:
        query = """
            SELECT DISTINCT d.dataset_id, d.tenant_id, d.file_name, d.owner_username, d.created_at
            FROM datasets d
            LEFT JOIN dataset_access da ON da.dataset_id = d.dataset_id
            WHERE d.tenant_id = :tenant_id
              AND (d.owner_username = :username OR da.username = :username)
            ORDER BY d.created_at DESC
        """
        params = {"tenant_id": current_user.tenant_id, "username": current_user.username}

    with get_db_connection() as connection:
        rows = fetchall(connection, query, params)

    return [
        {
            "id": row["dataset_id"],
            "tenant_id": row["tenant_id"],
            "file": row["file_name"],
            "owner_username": row["owner_username"],
            "created_at": row["created_at"],
        }
        for row in rows
    ]
