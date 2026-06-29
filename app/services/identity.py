import logging
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from pydantic import BaseModel, Field

from app.core.db import execute, fetchall, fetchone, get_db_connection
from app.core.security import (
    create_access_token,
    decode_access_token,
    generate_refresh_token,
    hash_password,
    verify_password,
)
from app.core.settings import get_settings
from app.services.audit import record_audit_event

logger = logging.getLogger(__name__)


class TokenBundle(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RegistrationRequest(BaseModel):
    username: str
    password: str
    tenant_id: str | None = None
    role: str = "viewer"


class CreateUserRequest(BaseModel):
    username: str
    password: str
    tenant_id: str
    role: str = "viewer"


class AuthenticatedUser(BaseModel):
    username: str
    tenant_id: str
    role: str
    allowed_dataset_ids: list[str] = Field(default_factory=list)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _fetch_allowed_dataset_ids(username: str) -> list[str]:
    with get_db_connection() as connection:
        rows = fetchall(
            connection,
            """
            SELECT dataset_id
            FROM dataset_access
            WHERE username = :username
            ORDER BY created_at ASC
            """,
            {"username": username},
        )
    return [row["dataset_id"] for row in rows]


def get_authenticated_user(username: str) -> AuthenticatedUser | None:
    with get_db_connection() as connection:
        row = fetchone(
            connection,
            """
            SELECT username, tenant_id, role, status
            FROM users
            WHERE username = :username
            """,
            {"username": username},
        )

    if not row:
        return None

    if row["status"] != "active":
        logger.warning("User '%s' is not active.", row["username"])
        return None

    allowed_dataset_ids = ["*"] if row["role"] == "admin" else _fetch_allowed_dataset_ids(row["username"])
    return AuthenticatedUser(
        username=row["username"],
        tenant_id=row["tenant_id"],
        role=row["role"],
        allowed_dataset_ids=allowed_dataset_ids,
    )


def _persist_refresh_token(username: str, tenant_id: str) -> str:
    refresh_token = generate_refresh_token()
    expires_at = (datetime.now(UTC) + timedelta(minutes=get_settings().refresh_token_expire_minutes)).isoformat()
    with get_db_connection() as connection:
        execute(
            connection,
            """
            INSERT INTO refresh_tokens (token, username, tenant_id, expires_at, revoked_at, created_at)
            VALUES (:token, :username, :tenant_id, :expires_at, NULL, :created_at)
            """,
            {
                "token": refresh_token,
                "username": username,
                "tenant_id": tenant_id,
                "expires_at": expires_at,
                "created_at": _utc_now(),
            },
        )
    return refresh_token


def _build_token_bundle(user: AuthenticatedUser) -> TokenBundle:
    access_token = create_access_token(subject=user.username, role=user.role)
    refresh_token = _persist_refresh_token(user.username, user.tenant_id)
    return TokenBundle(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=get_settings().jwt_expire_minutes * 60,
    )


def authenticate_user(username: str, password: str) -> tuple[AuthenticatedUser, TokenBundle]:
    cleaned_username = username.strip()
    with get_db_connection() as connection:
        row = fetchone(
            connection,
            """
            SELECT username, password_hash, password_salt
            FROM users
            WHERE username = :username
            """,
            {"username": cleaned_username},
        )

    if not row:
        logger.warning("Authentication failed for unknown user '%s'", cleaned_username)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials.")

    if not verify_password(password, row["password_hash"], row["password_salt"]):
        logger.warning("Authentication failed for user '%s' due to password mismatch", cleaned_username)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials.")

    user = get_authenticated_user(cleaned_username)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found.")

    with get_db_connection() as connection:
        execute(
            connection,
            """
            UPDATE users
            SET last_login_at = :last_login_at
            WHERE username = :username
            """,
            {"last_login_at": _utc_now(), "username": user.username},
        )

    record_audit_event(
        event_type="auth.login",
        actor_username=user.username,
        tenant_id=user.tenant_id,
        resource_type="user",
        resource_id=user.username,
        detail="User authenticated successfully.",
    )
    logger.info("Authenticated user '%s' with role '%s'", user.username, user.role)
    return user, _build_token_bundle(user)


def refresh_access_token(refresh_token: str) -> tuple[AuthenticatedUser, TokenBundle]:
    with get_db_connection() as connection:
        row = fetchone(
            connection,
            """
            SELECT token, username, tenant_id, expires_at, revoked_at
            FROM refresh_tokens
            WHERE token = :token
            """,
            {"token": refresh_token},
        )

    if not row or row["revoked_at"]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token.")

    if datetime.fromisoformat(row["expires_at"]) < datetime.now(UTC):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token expired.")

    user = get_authenticated_user(row["username"])
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found.")

    revoke_refresh_token(refresh_token)
    record_audit_event(
        event_type="auth.refresh",
        actor_username=user.username,
        tenant_id=user.tenant_id,
        resource_type="user",
        resource_id=user.username,
        detail="Refresh token exchanged for new access token.",
    )
    return user, _build_token_bundle(user)


def revoke_refresh_token(refresh_token: str, actor_username: str | None = None) -> None:
    tenant_id = None
    with get_db_connection() as connection:
        row = fetchone(
            connection,
            """
            SELECT username, tenant_id
            FROM refresh_tokens
            WHERE token = :token
            """,
            {"token": refresh_token},
        )
        execute(
            connection,
            """
            UPDATE refresh_tokens
            SET revoked_at = :revoked_at
            WHERE token = :token AND revoked_at IS NULL
            """,
            {"revoked_at": _utc_now(), "token": refresh_token},
        )

    if row:
        tenant_id = row["tenant_id"]
        record_audit_event(
            event_type="auth.logout",
            actor_username=actor_username or row["username"],
            tenant_id=tenant_id,
            resource_type="user",
            resource_id=row["username"],
            detail="Refresh token revoked.",
        )


def register_user(request: RegistrationRequest) -> AuthenticatedUser:
    username = request.username.strip()
    password = request.password.strip()
    tenant_id = (request.tenant_id or "tenant_default").strip()
    role = request.role.strip()
    allowed_roles = {"admin", "analyst", "viewer"}

    if len(username) < 3 or len(password) < 6:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username/password too short.")
    if role not in allowed_roles:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid role.")

    password_hash, password_salt = hash_password(password)
    with get_db_connection() as connection:
        tenant = fetchone(connection, "SELECT tenant_id FROM tenants WHERE tenant_id = :tenant_id", {"tenant_id": tenant_id})
        if not tenant:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Tenant '{tenant_id}' not found.")

        existing = fetchone(connection, "SELECT username FROM users WHERE username = :username", {"username": username})
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already exists.")

        execute(
            connection,
            """
            INSERT INTO users (username, tenant_id, role, password_hash, password_salt, created_at)
            VALUES (:username, :tenant_id, :role, :password_hash, :password_salt, :created_at)
            """,
            {
                "username": username,
                "tenant_id": tenant_id,
                "role": role,
                "password_hash": password_hash,
                "password_salt": password_salt,
                "created_at": _utc_now(),
            },
        )

    user = get_authenticated_user(username)
    if not user:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create user.")

    record_audit_event(
        event_type="auth.register",
        actor_username=user.username,
        tenant_id=user.tenant_id,
        resource_type="user",
        resource_id=user.username,
        detail="User self-registered.",
    )
    return user


def create_user_by_admin(request: CreateUserRequest, actor: AuthenticatedUser) -> AuthenticatedUser:
    if actor.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins can create users.")

    if actor.tenant_id != request.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin can only create users inside their own tenant.",
        )

    created_user = register_user(
        RegistrationRequest(
            username=request.username,
            password=request.password,
            tenant_id=request.tenant_id,
            role=request.role,
        )
    )
    record_audit_event(
        event_type="auth.admin_create_user",
        actor_username=actor.username,
        tenant_id=actor.tenant_id,
        resource_type="user",
        resource_id=created_user.username,
        detail="User created by admin.",
    )
    return created_user


def resolve_user_from_access_token(token: str) -> AuthenticatedUser:
    payload = decode_access_token(token, expected_type="access")
    username = payload.get("sub", "").strip()
    user = get_authenticated_user(username)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found.")
    return user
