import pytest
from fastapi.testclient import TestClient

from main import create_app


class HealthyConnection:
    async def fetchval(self, query: str) -> int:
        return 1


class UnreachableConnection:
    async def fetchval(self, query: str) -> int:
        raise ConnectionError(
            "connection to server at aws-0-ap-northeast-2.pooler.supabase.com "
            "failed: password authentication failed",
        )


class FakeHealthPool:
    def __init__(self, connection) -> None:
        self._connection = connection
        self.closed = False

    def acquire(self):
        return _AcquireContext(self._connection)

    async def close(self) -> None:
        self.closed = True


class _AcquireContext:
    def __init__(self, connection) -> None:
        self._connection = connection

    async def __aenter__(self):
        return self._connection

    async def __aexit__(self, *_: object) -> None:
        return None


def build_client(pool) -> TestClient:
    app = create_app(enable_database=False)
    app.state.db_pool = pool
    return TestClient(app, raise_server_exceptions=False)


def test_health_endpoint() -> None:
    app = create_app(enable_database=False)

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_database_health_reports_a_reachable_database() -> None:
    with build_client(FakeHealthPool(HealthyConnection())) as client:
        response = client.get("/health/db")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "connected"}


def test_database_health_fails_without_leaking_credentials() -> None:
    with build_client(FakeHealthPool(UnreachableConnection())) as client:
        response = client.get("/health/db")

    assert response.status_code == 500
    body = response.text.lower()
    assert "password" not in body
    assert "pooler.supabase.com" not in body


@pytest.mark.parametrize("path", ["/health", "/health/db"])
def test_health_endpoints_need_no_token(path: str) -> None:
    with build_client(FakeHealthPool(HealthyConnection())) as client:
        response = client.get(path)

    assert response.status_code == 200
