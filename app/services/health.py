import logging
from importlib.util import find_spec

from app.core.db import fetchone, get_db_connection
from app.core.settings import get_settings
from app.services.runtime_metrics import runtime_metrics
from app.services.storage import storage_health

logger = logging.getLogger(__name__)


def get_health_status() -> dict:
    settings = get_settings()
    print("Health check executed")
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
    }


def get_readiness_status() -> dict:
    settings = get_settings()
    db_ok = True
    try:
        with get_db_connection() as connection:
            fetchone(connection, "SELECT 1 AS ok")
    except Exception:
        db_ok = False

    jwt_secret_ok = settings.environment != "production" or (
        settings.jwt_secret_key != "change-this-secret-before-production"
    )

    rag_dependencies_available = bool(find_spec("chromadb")) and bool(find_spec("sentence_transformers"))

    storage_state = storage_health()
    checks = {
        "database_connected": db_ok,
        "storage_available": storage_state["available"],
        "openrouter_key_configured": bool(settings.openrouter_api_key),
        "jwt_secret_configured": jwt_secret_ok,
        "rag_dependencies_available": rag_dependencies_available,
        "rag_enabled": settings.rag_enabled,
    }
    required_checks = {
        "database_connected": checks["database_connected"],
        "storage_available": checks["storage_available"],
        "jwt_secret_configured": checks["jwt_secret_configured"],
    }
    require_llm = settings.health_require_llm or settings.environment == "production"
    require_rag_dependencies = settings.environment in {"staging", "production"} and settings.rag_enabled

    if require_llm:
        required_checks["openrouter_key_configured"] = checks["openrouter_key_configured"]
    if require_rag_dependencies:
        required_checks["rag_dependencies_available"] = checks["rag_dependencies_available"]
    ready = all(required_checks.values())

    logger.info(
        "Readiness evaluated: ready=%s environment=%s required_checks=%s checks=%s",
        ready,
        settings.environment,
        required_checks,
        checks,
    )
    return {
        "status": "ready" if ready else "degraded",
        "checks": checks,
        "required_checks": required_checks,
        "policy": {
            "environment": settings.environment,
            "require_llm": require_llm,
            "require_rag_dependencies": require_rag_dependencies,
        },
    }


def get_system_status() -> dict:
    settings = get_settings()
    with get_db_connection() as connection:
        dataset_count = fetchone(connection, "SELECT COUNT(*) AS count FROM datasets")["count"]
        user_count = fetchone(connection, "SELECT COUNT(*) AS count FROM users")["count"]
        audit_count = fetchone(connection, "SELECT COUNT(*) AS count FROM audit_logs")["count"]

    storage_state = storage_health()

    return {
        "service": {
            "name": settings.app_name,
            "version": settings.app_version,
            "environment": settings.environment,
            "docs_enabled": settings.docs_enabled,
        },
        "capabilities": {
            "live_llm_configured": bool(settings.openrouter_api_key),
            "rag_enabled": settings.rag_enabled,
            "rag_dependencies_available": bool(find_spec("chromadb")) and bool(find_spec("sentence_transformers")),
        },
        "storage": {
            "database_url": settings.database_url,
            "provider": storage_state["provider"],
            "vector_db_dir": settings.vector_db_dir,
            "dataset_count": dataset_count,
            "user_count": user_count,
            "audit_log_count": audit_count,
        },
        "runtime": runtime_metrics.snapshot(),
    }
