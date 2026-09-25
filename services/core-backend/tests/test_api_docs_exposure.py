import pytest
from fastapi.testclient import TestClient

from main import create_app

DOC_PATHS = ("/docs", "/redoc", "/openapi.json")


def test_docs_are_served_outside_production(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENVIRONMENT", "development")

    with TestClient(create_app(enable_database=False)) as client:
        assert [client.get(path).status_code for path in DOC_PATHS] == [200, 200, 200]


def test_docs_are_not_served_in_production(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENVIRONMENT", "Production")

    with TestClient(create_app(enable_database=False)) as client:
        assert [client.get(path).status_code for path in DOC_PATHS] == [404, 404, 404]
        assert client.get("/health").status_code == 200


def test_app_can_be_built_without_database_settings(monkeypatch) -> None:
    for name in ("DB_URI", "DB_HOST", "DB_USER", "DB_PASSWORD"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("APP_ENVIRONMENT", "development")

    assert create_app(enable_database=False) is not None
