from fastapi import APIRouter, Depends, Query

from app.core.auth import User, require_roles
from app.services.audit import list_audit_logs

router = APIRouter(tags=["audit"])


@router.get("/audit-logs")
def get_audit_logs(
    limit: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(require_roles("admin")),
):
    return list_audit_logs(current_user, limit=limit)
