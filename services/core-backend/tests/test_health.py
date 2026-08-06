from fastapi.testclient import TestClient

from main import create_app


def test_health_endpoint() -> None:
    app = create_app(enable_database=False)

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
