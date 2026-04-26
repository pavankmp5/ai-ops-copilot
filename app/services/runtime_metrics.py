import threading
import time


class RuntimeMetrics:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._started_at = time.time()
        self._total_requests = 0
        self._status_counts: dict[str, int] = {}
        self._route_counts: dict[str, int] = {}
        self._last_request_at: float | None = None
        self._last_response_time_ms = 0.0

    def record_request(self, path: str, status_code: int, duration_ms: float) -> None:
        status_key = str(status_code)
        with self._lock:
            self._total_requests += 1
            self._status_counts[status_key] = self._status_counts.get(status_key, 0) + 1
            self._route_counts[path] = self._route_counts.get(path, 0) + 1
            self._last_request_at = time.time()
            self._last_response_time_ms = duration_ms

    def snapshot(self) -> dict:
        with self._lock:
            top_routes = sorted(self._route_counts.items(), key=lambda item: item[1], reverse=True)[:5]
            return {
                "uptime_seconds": round(time.time() - self._started_at, 2),
                "total_requests": self._total_requests,
                "status_counts": dict(self._status_counts),
                "top_routes": [{"path": path, "count": count} for path, count in top_routes],
                "last_response_time_ms": self._last_response_time_ms,
                "last_request_at_epoch": self._last_request_at,
            }


runtime_metrics = RuntimeMetrics()
