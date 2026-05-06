import logging
import os
from contextlib import contextmanager
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote, urlparse, urlunparse

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine

from app.core.security import hash_password
from app.core.settings import get_settings

logger = logging.getLogger(__name__)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _normalized_database_url() -> str:
    settings = get_settings()
    database_url = settings.database_url

    if database_url.startswith("sqlite:///"):
        return database_url

    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql+psycopg://", 1)
    elif database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)

    return _resolve_local_postgres_service_host(database_url)


def _is_container_runtime() -> bool:
    running_in_docker = os.getenv("RUNNING_IN_DOCKER", "").strip().lower() in {"1", "true", "yes"}
    return running_in_docker or Path("/.dockerenv").exists()


def _resolve_local_postgres_service_host(database_url: str) -> str:
    if not database_url.startswith("postgresql+psycopg://") or _is_container_runtime():
        return database_url

    parsed = urlparse(database_url)
    if parsed.hostname != "postgres":
        return database_url

    # `postgres` resolves only on container networks. For host-run local backend, use localhost.
    user = quote(parsed.username, safe="") if parsed.username else ""
    password = quote(parsed.password, safe="") if parsed.password else ""
    userinfo = user
    if password:
        userinfo = f"{userinfo}:{password}"
    if userinfo:
        userinfo = f"{userinfo}@"
    port = parsed.port or 5432
    replaced = parsed._replace(netloc=f"{userinfo}localhost:{port}")
    logger.warning(
        "DATABASE_URL host 'postgres' detected outside container runtime. "
        "Using localhost for local development."
    )
    return urlunparse(replaced)


@lru_cache
def get_engine() -> Engine:
    database_url = _normalized_database_url()
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {"connect_timeout": 10}
    return create_engine(database_url, future=True, pool_pre_ping=True, connect_args=connect_args)


def is_sqlite() -> bool:
    return _normalized_database_url().startswith("sqlite")


def is_postgres() -> bool:
    return _normalized_database_url().startswith("postgresql+psycopg")


@contextmanager
def get_db_connection():
    with get_engine().begin() as connection:
        yield connection


def execute(connection: Connection, query: str, params: dict | None = None):
    return connection.execute(text(query), params or {})


def fetchone(connection: Connection, query: str, params: dict | None = None):
    return execute(connection, query, params).mappings().fetchone()


def fetchall(connection: Connection, query: str, params: dict | None = None):
    return execute(connection, query, params).mappings().fetchall()


def _column_exists(connection: Connection, table_name: str, column_name: str) -> bool:
    if is_sqlite():
        rows = connection.exec_driver_sql(f"PRAGMA table_info({table_name})").fetchall()
        return any(row[1] == column_name for row in rows)

    row = fetchone(
        connection,
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = :table_name AND column_name = :column_name
        """,
        {"table_name": table_name, "column_name": column_name},
    )
    return row is not None


def init_db() -> None:
    with get_db_connection() as connection:
        if is_sqlite():
            connection.exec_driver_sql(
                """
                CREATE TABLE IF NOT EXISTS tenants (
                    tenant_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.exec_driver_sql(
                """
                CREATE TABLE IF NOT EXISTS users (
                    username TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL DEFAULT 'tenant_default',
                    role TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    password_salt TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.exec_driver_sql(
                """
                CREATE TABLE IF NOT EXISTS datasets (
                    dataset_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL DEFAULT 'tenant_default',
                    owner_username TEXT NOT NULL,
                    file_hash TEXT NOT NULL UNIQUE,
                    file_name TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.exec_driver_sql(
                """
                CREATE TABLE IF NOT EXISTS dataset_access (
                    username TEXT NOT NULL,
                    dataset_id TEXT NOT NULL,
                    shared_by_username TEXT,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (username, dataset_id)
                )
                """
            )
            connection.exec_driver_sql(
                """
                CREATE TABLE IF NOT EXISTS audit_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    actor_username TEXT,
                    tenant_id TEXT,
                    resource_type TEXT,
                    resource_id TEXT,
                    detail TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.exec_driver_sql(
                """
                CREATE TABLE IF NOT EXISTS refresh_tokens (
                    token TEXT PRIMARY KEY,
                    username TEXT NOT NULL,
                    tenant_id TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    revoked_at TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
        else:
            connection.exec_driver_sql(
                """
                CREATE TABLE IF NOT EXISTS tenants (
                    tenant_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.exec_driver_sql(
                """
                CREATE TABLE IF NOT EXISTS users (
                    username TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL DEFAULT 'tenant_default',
                    role TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    password_salt TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.exec_driver_sql(
                """
                CREATE TABLE IF NOT EXISTS datasets (
                    dataset_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL DEFAULT 'tenant_default',
                    owner_username TEXT NOT NULL,
                    file_hash TEXT NOT NULL UNIQUE,
                    file_name TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.exec_driver_sql(
                """
                CREATE TABLE IF NOT EXISTS dataset_access (
                    username TEXT NOT NULL,
                    dataset_id TEXT NOT NULL,
                    shared_by_username TEXT,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (username, dataset_id)
                )
                """
            )
            connection.exec_driver_sql(
                """
                CREATE TABLE IF NOT EXISTS audit_logs (
                    id BIGSERIAL PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    actor_username TEXT,
                    tenant_id TEXT,
                    resource_type TEXT,
                    resource_id TEXT,
                    detail TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.exec_driver_sql(
                """
                CREATE TABLE IF NOT EXISTS refresh_tokens (
                    token TEXT PRIMARY KEY,
                    username TEXT NOT NULL,
                    tenant_id TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    revoked_at TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )

        _migrate_schema(connection)
        _create_indexes(connection)
        _seed_default_tenants(connection)
        _seed_default_users(connection)

    logger.info("Database initialized successfully backend=%s", "sqlite" if is_sqlite() else "postgres")


def _migrate_schema(connection: Connection) -> None:
    if not _column_exists(connection, "users", "tenant_id"):
        connection.exec_driver_sql("ALTER TABLE users ADD COLUMN tenant_id TEXT NOT NULL DEFAULT 'tenant_default'")

    if not _column_exists(connection, "datasets", "tenant_id"):
        connection.exec_driver_sql("ALTER TABLE datasets ADD COLUMN tenant_id TEXT NOT NULL DEFAULT 'tenant_default'")

    if not _column_exists(connection, "dataset_access", "shared_by_username"):
        connection.exec_driver_sql("ALTER TABLE dataset_access ADD COLUMN shared_by_username TEXT")


def _create_indexes(connection: Connection) -> None:
    index_statements = [
        "CREATE INDEX IF NOT EXISTS idx_users_tenant_id ON users(tenant_id)",
        "CREATE INDEX IF NOT EXISTS idx_datasets_tenant_owner ON datasets(tenant_id, owner_username)",
        "CREATE INDEX IF NOT EXISTS idx_datasets_file_hash ON datasets(file_hash)",
        "CREATE INDEX IF NOT EXISTS idx_dataset_access_username ON dataset_access(username)",
        "CREATE INDEX IF NOT EXISTS idx_refresh_tokens_username ON refresh_tokens(username)",
        "CREATE INDEX IF NOT EXISTS idx_audit_logs_tenant_created ON audit_logs(tenant_id, created_at)",
    ]
    for statement in index_statements:
        connection.exec_driver_sql(statement)


def _seed_default_tenants(connection: Connection) -> None:
    tenants = [
        ("tenant_default", "Default Tenant"),
        ("tenant_external", "External Tenant"),
    ]
    for tenant_id, name in tenants:
        existing_tenant = fetchone(
            connection,
            "SELECT tenant_id FROM tenants WHERE tenant_id = :tenant_id",
            {"tenant_id": tenant_id},
        )
        if existing_tenant:
            continue

        execute(
            connection,
            """
            INSERT INTO tenants (tenant_id, name, created_at)
            VALUES (:tenant_id, :name, :created_at)
            """,
            {"tenant_id": tenant_id, "name": name, "created_at": _utc_now()},
        )
        logger.info("Seeded tenant '%s'", tenant_id)


def _seed_default_users(connection: Connection) -> None:
    default_users = [
        ("admin", "admin123", "admin", "tenant_default"),
        ("alice", "alice123", "user", "tenant_default"),
        ("bob", "bob123", "user", "tenant_default"),
        ("charlie", "charlie123", "user", "tenant_external"),
    ]

    for username, password, role, tenant_id in default_users:
        existing_user = fetchone(
            connection,
            "SELECT username FROM users WHERE username = :username",
            {"username": username},
        )
        if existing_user:
            execute(
                connection,
                """
                UPDATE users
                SET tenant_id = COALESCE(tenant_id, :tenant_id)
                WHERE username = :username
                """,
                {"tenant_id": tenant_id, "username": username},
            )
            continue

        password_hash, password_salt = hash_password(password)
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
        logger.info("Seeded default user '%s'", username)
