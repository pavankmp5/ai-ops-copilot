import os
import sys
import time
from pathlib import Path

from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.main import app


def require_status(response, expected: int, name: str) -> None:
    if response.status_code != expected:
        body = response.text
        raise RuntimeError(f"{name} failed: expected {expected}, got {response.status_code}. body={body}")


def is_strict_readiness_mode() -> bool:
    mode = os.getenv("SMOKE_READINESS_MODE", "auto").strip().lower()
    if mode not in {"auto", "strict", "relaxed"}:
        raise RuntimeError("SMOKE_READINESS_MODE must be one of: auto, strict, relaxed.")

    if mode == "strict":
        return True
    if mode == "relaxed":
        return False

    environment = os.getenv("ENVIRONMENT", "development").strip().lower()
    return environment in {"staging", "production"}


def is_core_ready(payload: dict) -> bool:
    checks = payload.get("checks", {})
    return bool(
        checks.get("database_connected")
        and checks.get("storage_available")
        and checks.get("jwt_secret_configured")
    )


def wait_for_ready(client: TestClient, timeout_seconds: int = 20, poll_seconds: float = 1.0) -> dict:
    strict_mode = is_strict_readiness_mode()
    deadline = time.time() + timeout_seconds
    latest_status = None
    latest_payload = None

    while time.time() < deadline:
        response = client.get("/readyz")
        latest_status = response.status_code
        latest_payload = response.json()

        if latest_status == 200:
            return {"status_code": latest_status, "payload": latest_payload}

        if latest_status == 503 and not strict_mode and is_core_ready(latest_payload):
            return {"status_code": latest_status, "payload": latest_payload}

        time.sleep(poll_seconds)

    raise RuntimeError(
        "GET /readyz did not become healthy in time. "
        f"strict_mode={strict_mode} status={latest_status} payload={latest_payload}"
    )


def main() -> None:
    with TestClient(app) as client:
        home = client.get("/")
        require_status(home, 200, "GET /")
        print("GET /", home.status_code, home.json())

        health = client.get("/health")
        require_status(health, 200, "GET /health")
        print("GET /health", health.status_code, health.json())

        ready = wait_for_ready(client)
        print("GET /readyz", ready["status_code"], ready["payload"])

        login = client.post("/auth/token", data={"username": "admin", "password": "admin123"})
        require_status(login, 200, "POST /auth/token")
        print("POST /auth/token", login.status_code)

        token = login.json()["tokens"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        me = client.get("/auth/me", headers=headers)
        require_status(me, 200, "GET /auth/me")
        print("GET /auth/me", me.status_code, me.json())

        datasets = client.get("/datasets", headers=headers)
        require_status(datasets, 200, "GET /datasets")
        print("GET /datasets", datasets.status_code, datasets.json())


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Smoke test failed: {exc}")
        raise SystemExit(1)
