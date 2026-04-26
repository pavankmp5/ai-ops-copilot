import threading
import time
from collections import deque

from fastapi import HTTPException, Request, status

from app.core.settings import get_settings

_lock = threading.Lock()
_requests: dict[str, deque[float]] = {}


def _get_identifier(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def enforce_rate_limit(request: Request) -> tuple[int, int]:
    settings = get_settings()
    identifier = _get_identifier(request)
    now = time.time()
    window_start = now - settings.rate_limit_window_seconds

    with _lock:
        request_times = _requests.setdefault(identifier, deque())
        while request_times and request_times[0] < window_start:
            request_times.popleft()

        if len(request_times) >= settings.rate_limit_requests:
            retry_after = max(1, int(settings.rate_limit_window_seconds - (now - request_times[0])))
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Retry after {retry_after} seconds.",
            )

        request_times.append(now)
        remaining = max(0, settings.rate_limit_requests - len(request_times))

    return remaining, settings.rate_limit_window_seconds
