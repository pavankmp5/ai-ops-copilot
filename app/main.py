import logging
import os
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.core.db import init_db
from app.core.exceptions import register_exception_handlers
from app.core.logging import setup_logging
from app.core.request_context import set_request_id
from app.core.settings import get_settings
from app.routes import audit, auth, data, health, query
from app.services.rate_limiter import enforce_rate_limit
from app.services.runtime_metrics import runtime_metrics

settings = get_settings()
setup_logging(settings)


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.storage_provider == "local":
        os.makedirs(settings.data_dir, exist_ok=True)
    os.makedirs(settings.vector_db_dir, exist_ok=True)
    init_db()
    logging.getLogger("app.startup").info(
        "Startup complete environment=%s storage_provider=%s vector_db_dir=%s database_backend=%s",
        settings.environment,
        settings.storage_provider,
        settings.vector_db_dir,
        "sqlite" if settings.database_url.startswith("sqlite") else "postgres",
    )
    try:
        yield
    finally:
        logging.getLogger("app.shutdown").info("Shutdown complete")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    docs_url="/docs" if settings.docs_enabled else None,
    redoc_url="/redoc" if settings.docs_enabled else None,
    openapi_url="/openapi.json" if settings.docs_enabled else None,
    lifespan=lifespan,
)
register_exception_handlers(app)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def home():
    return {
        "message": "AI Ops Copilot is running",
        "service": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "docs_url": "/docs" if settings.docs_enabled else None,
    }

@app.middleware("http")
async def log_requests(request: Request, call_next):
    if request.url.path in ["/health", "/healthz", "/readyz"]:
        return await call_next(request)

    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    set_request_id(request_id)
    remaining, window_seconds = enforce_rate_limit(request)
    start_time = time.perf_counter()
    response = None
    try:
        response = await call_next(request)
        return response
    finally:
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        status_code = response.status_code if response is not None else 500

        logging.getLogger("app.request").info(
            "request_id=%s method=%s path=%s status_code=%s duration_ms=%s",
            request_id,
            request.method,
            request.url.path,
            status_code,
            duration_ms,
        )
        runtime_metrics.record_request(request.url.path, status_code, duration_ms)

        if response is not None:
            response.headers["X-Request-ID"] = request_id
            response.headers["X-RateLimit-Remaining"] = str(remaining)
            response.headers["X-RateLimit-Window"] = str(window_seconds)
            response.headers["X-Response-Time-ms"] = str(duration_ms)

        set_request_id(None)


app.include_router(audit.router)
app.include_router(auth.router)
app.include_router(health.router)
app.include_router(data.router)
app.include_router(query.router)
