import pytest
from fastapi.testclient import TestClient

from core.config import get_settings
from main import create_app

DOC_PATHS = ("/docs", "/redoc", "/openapi.json")


@pytest.fixture(autouse=True)
def reset_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_docs_are_served_outside_production(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENVIRONMENT", "development")

    with TestClient(create_app(enable_database=False)) as client:
        assert [client.get(path).status_code for path in DOC_PATHS] == [200, 200, 200]


def test_docs_are_not_served_in_production(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENVIRONMENT", "Production")

    with TestClient(create_app(enable_database=False)) as client:
        assert [client.get(path).status_code for path in DOC_PATHS] == [404, 404, 404]
        assert client.get("/health").status_code == 200
