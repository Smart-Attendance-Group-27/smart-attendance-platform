import asyncio
from contextlib import AbstractAsyncContextManager
from unittest.mock import AsyncMock

import pytest

from modules.notification.producer.repository import NotificationProducerRepository
from modules.notification.reminders.scheduler import UpcomingClassReminderScheduler


@pytest.mark.asyncio
async def test_reminder_repository_uses_database_idempotency_guard() -> None:
    connection = AsyncMock()
    connection.fetchrow.return_value = {"created_count": 2}

    created = await NotificationProducerRepository().enqueue_upcoming_class_reminders(
        connection,
        lead_minutes=15,
    )

    assert created == 2
    query = connection.fetchrow.call_args.args[0]
    assert "ON CONFLICT DO NOTHING" in query
    assert "notification_preferences" in query
    assert "delivery_attempts" in query


class Transaction(AbstractAsyncContextManager):
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class Connection:
    def transaction(self):
        return Transaction()


class Acquire(AbstractAsyncContextManager):
    async def __aenter__(self):
        return Connection()

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class Pool:
    def acquire(self):
        return Acquire()


@pytest.mark.asyncio
async def test_scheduler_is_idempotent_across_repeated_runs() -> None:
    producer = AsyncMock()
    producer.upcoming_class_reminders.side_effect = [2, 0]
    scheduler = UpcomingClassReminderScheduler(
        pool=Pool(),  # type: ignore[arg-type]
        interval_seconds=1,
        lead_minutes=15,
        producer=producer,
    )

    assert await scheduler.run_once() == 2
    assert await scheduler.run_once() == 0
    assert producer.upcoming_class_reminders.await_count == 2


@pytest.mark.asyncio
async def test_scheduler_stops_cleanly() -> None:
    producer = AsyncMock()
    producer.upcoming_class_reminders.return_value = 0
    scheduler = UpcomingClassReminderScheduler(
        pool=Pool(),  # type: ignore[arg-type]
        interval_seconds=0.01,
        lead_minutes=15,
        producer=producer,
    )
    stop = asyncio.Event()
    task = asyncio.create_task(scheduler.run(stop))
    await asyncio.sleep(0)
    stop.set()
    await asyncio.wait_for(task, timeout=1)
    assert task.done()
