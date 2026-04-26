from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from app.services.health import get_health_status, get_readiness_status, get_system_status

router = APIRouter(tags=["health"])


@router.get("/healthz")
def health_check():
    return get_health_status()


@router.get("/health")
def health_check_alias():
    return get_health_status()


@router.get("/readyz")
def readiness_check():
    readiness = get_readiness_status()
    status_code = status.HTTP_200_OK if readiness["status"] == "ready" else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(status_code=status_code, content=readiness)


@router.get("/system/status")
def system_status():
    return get_system_status()
