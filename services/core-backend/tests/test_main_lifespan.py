import asyncio

import pytest
from fastapi import FastAPI

import main
from core.config import Settings
from modules.notification.readiness import NotificationSchemaReadiness


@pytest.mark.asyncio
async def test_lifespan_initializes_and_closes_database_and_redis(monkeypatch) -> None:
    settings = Settings(
        db_host="localhost",
        db_user="postgres",
        db_password="password",
        redis_url="redis://localhost:6379/0",
        push_worker_enabled=False,
        reminder_scheduler_enabled=False,
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


@pytest.mark.asyncio
async def test_lifespan_starts_and_stops_push_worker_before_database(
    monkeypatch,
) -> None:
    settings = Settings(
        db_host="localhost",
        db_user="postgres",
        db_password="password",
        redis_url=None,
        push_worker_enabled=True,
        reminder_scheduler_enabled=False,
        push_worker_shutdown_timeout_seconds=1,
        _env_file=None,
    )
    database_pool = object()
    events: list[str] = []

    class FakeWorker:
        def __init__(self, **kwargs) -> None:
            assert kwargs["repository"] is not None
            assert kwargs["provider"] is not None

        async def run(self, stop_event) -> None:
            events.append("started")
            await stop_event.wait()
            events.append("stopped")

    async def create_database_pool(_settings: Settings) -> object:
        return database_pool

    async def create_redis_client(_settings: Settings):
        return None

    async def close_database_pool(resource: object) -> None:
        assert resource is database_pool
        events.append("database_closed")

    async def close_redis_client(resource) -> None:
        return None

    async def check_readiness(resource) -> NotificationSchemaReadiness:
        assert resource is database_pool
        return NotificationSchemaReadiness(True, True)

    monkeypatch.setattr(main, "get_settings", lambda: settings)
    monkeypatch.setattr(main, "create_database_pool", create_database_pool)
    monkeypatch.setattr(main, "create_redis_client", create_redis_client)
    monkeypatch.setattr(main, "close_database_pool", close_database_pool)
    monkeypatch.setattr(main, "close_redis_client", close_redis_client)
    monkeypatch.setattr(main, "check_notification_schema_readiness", check_readiness)
    monkeypatch.setattr(main, "PushDeliveryWorker", FakeWorker)

    app = FastAPI()
    async with main.lifespan(app):
        await asyncio.sleep(0)
        assert events == ["started"]

    assert events == ["started", "stopped", "database_closed"]


@pytest.mark.asyncio
async def test_lifespan_starts_and_stops_reminder_scheduler(monkeypatch) -> None:
    settings = Settings(
        db_host="localhost",
        db_user="postgres",
        db_password="password",
        redis_url=None,
        push_worker_enabled=False,
        reminder_scheduler_enabled=True,
        push_worker_shutdown_timeout_seconds=1,
        _env_file=None,
    )
    database_pool = object()
    events: list[str] = []

    class FakeScheduler:
        def __init__(self, **kwargs) -> None:
            assert kwargs["pool"] is database_pool
            assert kwargs["lead_minutes"] == 15

        async def run(self, stop_event) -> None:
            events.append("started")
            await stop_event.wait()
            events.append("stopped")

    async def create_database_pool(_settings: Settings) -> object:
        return database_pool

    async def create_redis_client(_settings: Settings):
        return None

    async def close_database_pool(resource: object) -> None:
        events.append("database_closed")

    async def close_redis_client(resource) -> None:
        return None

    async def check_readiness(resource) -> NotificationSchemaReadiness:
        assert resource is database_pool
        return NotificationSchemaReadiness(True, True)

    monkeypatch.setattr(main, "get_settings", lambda: settings)
    monkeypatch.setattr(main, "create_database_pool", create_database_pool)
    monkeypatch.setattr(main, "create_redis_client", create_redis_client)
    monkeypatch.setattr(main, "close_database_pool", close_database_pool)
    monkeypatch.setattr(main, "close_redis_client", close_redis_client)
    monkeypatch.setattr(main, "check_notification_schema_readiness", check_readiness)
    monkeypatch.setattr(main, "UpcomingClassReminderScheduler", FakeScheduler)

    app = FastAPI()
    async with main.lifespan(app):
        await asyncio.sleep(0)
        assert events == ["started"]

    assert events == ["started", "stopped", "database_closed"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("push_enabled", "reminder_enabled", "readiness"),
    [
        (True, False, NotificationSchemaReadiness(False, True)),
        (False, True, NotificationSchemaReadiness(True, False)),
    ],
)
async def test_lifespan_does_not_start_background_task_when_schema_is_missing(
    monkeypatch,
    caplog,
    push_enabled: bool,
    reminder_enabled: bool,
    readiness: NotificationSchemaReadiness,
) -> None:
    settings = Settings(
        db_host="localhost",
        db_user="postgres",
        db_password="password",
        redis_url=None,
        push_worker_enabled=push_enabled,
        reminder_scheduler_enabled=reminder_enabled,
        _env_file=None,
    )
    database_pool = object()

    async def create_database_pool(_settings: Settings) -> object:
        return database_pool

    async def create_redis_client(_settings: Settings):
        return None

    async def close_resource(resource) -> None:
        return None

    async def check_readiness(resource) -> NotificationSchemaReadiness:
        assert resource is database_pool
        return readiness

    class UnexpectedTask:
        def __init__(self, **kwargs) -> None:
            pytest.fail("Background task was constructed despite a failed preflight")

    monkeypatch.setattr(main, "get_settings", lambda: settings)
    monkeypatch.setattr(main, "create_database_pool", create_database_pool)
    monkeypatch.setattr(main, "create_redis_client", create_redis_client)
    monkeypatch.setattr(main, "close_database_pool", close_resource)
    monkeypatch.setattr(main, "close_redis_client", close_resource)
    monkeypatch.setattr(main, "check_notification_schema_readiness", check_readiness)
    monkeypatch.setattr(main, "PushDeliveryWorker", UnexpectedTask)
    monkeypatch.setattr(main, "UpcomingClassReminderScheduler", UnexpectedTask)

    app = FastAPI()
    with caplog.at_level("ERROR"):
        async with main.lifespan(app):
            await asyncio.sleep(0)

    assert "not started" in caplog.text
