from fastapi.testclient import TestClient

from app.main import FRONTEND_DIST


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_backend_serves_built_frontend_when_available(client: TestClient) -> None:
    if not FRONTEND_DIST.exists():
        return

    response = client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
