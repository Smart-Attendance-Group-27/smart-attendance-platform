import pytest
from fastapi import FastAPI

import main
from core.config import Settings


@pytest.mark.asyncio
async def test_lifespan_initializes_and_closes_database_and_redis(monkeypatch) -> None:
    settings = Settings(
        db_host="localhost",
        db_user="postgres",
        db_password="password",
        redis_url="redis://localhost:6379/0",
        _env_file=None,
    )
    database_pool = object()
    redis_client = object()
    closed_resources: list[object] = []

    async def create_database_pool(_settings: Settings) -> object:
        return database_pool

    async def create_redis_client(_settings: Settings) -> object:
        return redis_client

    async def close_database_pool(resource: object) -> None:
        closed_resources.append(resource)

    async def close_redis_client(resource: object) -> None:
        closed_resources.append(resource)

    monkeypatch.setattr(main, "get_settings", lambda: settings)
    monkeypatch.setattr(main, "create_database_pool", create_database_pool)
    monkeypatch.setattr(main, "create_redis_client", create_redis_client)
    monkeypatch.setattr(main, "close_database_pool", close_database_pool)
    monkeypatch.setattr(main, "close_redis_client", close_redis_client)

    app = FastAPI()
    async with main.lifespan(app):
        assert app.state.db_pool is database_pool
        assert app.state.redis_client is redis_client

    assert closed_resources == [redis_client, database_pool]
