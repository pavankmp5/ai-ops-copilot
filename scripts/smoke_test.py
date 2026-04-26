import sys
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


def main() -> None:
    client = TestClient(app)

    home = client.get("/")
    require_status(home, 200, "GET /")
    print("GET /", home.status_code, home.json())

    health = client.get("/health")
    require_status(health, 200, "GET /health")
    print("GET /health", health.status_code, health.json())

    ready = client.get("/readyz")
    require_status(ready, 200, "GET /readyz")
    print("GET /readyz", ready.status_code, ready.json())

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
