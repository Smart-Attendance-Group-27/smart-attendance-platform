import asyncio

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from core.config import Settings
from db.engine import (
    _build_database_url,
    create_database_engine,
    dispose_database_engine,
)


def create_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "db_host": "localhost",
        "db_port": 5432,
        "db_name": "postgres",
        "db_user": "face_service",
        "db_password": "test-password",
        "db_ssl_mode": "disable",
        "face_embedding_encryption_key": "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=",
        "db_pool_min_size": 1,
        "db_pool_max_size": 5,
        "db_command_timeout_seconds": 10,
        "_env_file": None,
    }
    values.update(overrides)

    return Settings(**values)


def test_builds_asyncpg_url_from_individual_settings() -> None:
    url = _build_database_url(create_settings())

    assert url.drivername == "postgresql+asyncpg"
    assert url.username == "face_service"
    assert url.password == "test-password"
    assert url.host == "localhost"
    assert url.port == 5432
    assert url.database == "postgres"


def test_converts_configured_uri_to_asyncpg_url() -> None:
    settings = create_settings(
        db_uri=(
            "postgresql://configured-user:configured-password@"
            "database.example.com:6543/postgres?sslmode=require"
        )
    )

    url = _build_database_url(settings)

    assert url.drivername == "postgresql+asyncpg"
    assert url.username == "configured-user"
    assert url.host == "database.example.com"
    assert url.port == 6543
    assert "sslmode" not in url.query


def test_creates_and_disposes_async_engine_without_connecting() -> None:
    engine = create_database_engine(create_settings())

    assert isinstance(engine, AsyncEngine)
    assert engine.pool.size() == 1

    asyncio.run(dispose_database_engine(engine))


def test_rejects_pool_maximum_smaller_than_minimum() -> None:
    settings = create_settings(
        db_pool_min_size=5,
        db_pool_max_size=1,
    )

    with pytest.raises(
        ValueError,
        match="DB_POOL_MAX_SIZE must be greater than or equal to",
    ):
        create_database_engine(settings)
