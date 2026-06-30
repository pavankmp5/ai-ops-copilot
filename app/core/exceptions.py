import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        request_id = getattr(request.state, "request_id", "unknown")
        logger.warning(
            "HTTP error request_id=%s path=%s status_code=%s detail=%s",
            request_id,
            request.url.path,
            exc.status_code,
            exc.detail,
        )
        response = JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "type": "http_error",
                    "detail": exc.detail,
                    "request_id": request_id,
                    "path": request.url.path,
                }
            },
        )
        response.headers["X-Request-ID"] = str(request_id)
        return response

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        request_id = getattr(request.state, "request_id", "unknown")
        logger.exception(
            "Unhandled error request_id=%s path=%s",
            request_id,
            request.url.path,
        )
        response = JSONResponse(
            status_code=500,
            content={
                "error": {
                    "type": "internal_server_error",
                    "detail": "An unexpected server error occurred.",
                    "request_id": request_id,
                    "path": request.url.path,
                }
            },
        )
        response.headers["X-Request-ID"] = str(request_id)
        return response
