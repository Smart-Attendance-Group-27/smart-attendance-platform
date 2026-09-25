import asyncio
from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from modules.notification.push.repository import PushDeliveryRepository


class FakeTransaction(AbstractAsyncContextManager):
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class FakeConnection:
    def __init__(self, rows: list[dict]) -> None:
        self.rows = rows
        self.fetch_calls: list[tuple] = []
        self.execute_calls: list[tuple] = []

    def transaction(self) -> FakeTransaction:
        return FakeTransaction()

    async def fetch(self, query: str, *args):
        self.fetch_calls.append((query, args))
        return self.rows

    async def execute(self, query: str, *args):
        self.execute_calls.append((query, args))
        return "UPDATE 1"


class FakeAcquire(AbstractAsyncContextManager):
    def __init__(self, connection: FakeConnection) -> None:
        self.connection = connection

    async def __aenter__(self) -> FakeConnection:
        return self.connection

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class FakePool:
    def __init__(self, connection: FakeConnection) -> None:
        self.connection = connection

    def acquire(self) -> FakeAcquire:
        return FakeAcquire(self.connection)


class SharedClaimQueue:
    def __init__(self, rows: list[dict]) -> None:
        self.rows = rows
        self.lock = asyncio.Lock()


class ConcurrentConnection(FakeConnection):
    def __init__(self, queue: SharedClaimQueue) -> None:
        super().__init__([])
        self.queue = queue

    async def fetch(self, query: str, *args):
        self.fetch_calls.append((query, args))
        async with self.queue.lock:
            batch_size = args[-1]
            claimed = self.queue.rows[:batch_size]
            del self.queue.rows[:batch_size]
            return claimed


class ConcurrentPool:
    def __init__(self, rows: list[dict]) -> None:
        self.queue = SharedClaimQueue(rows)

    def acquire(self) -> FakeAcquire:
        return FakeAcquire(ConcurrentConnection(self.queue))


def claimed_row() -> dict:
    return {
        "id": uuid4(),
        "notification_id": uuid4(),
        "notification_code": "ATTENDANCE_SESSION_OPENED",
        "device_token_id": uuid4(),
        "attempt_number": 0,
        "expo_push_token": "ExponentPushToken[secret-value]",
        "token_is_active": True,
        "title": "Attendance open",
        "body": "Check in now",
        "priority": "high",
        "related_entity_type": "ATTENDANCE_SESSION",
        "related_entity_id": uuid4(),
    }


@pytest.mark.asyncio
async def test_claim_ready_uses_skip_locked_and_marks_rows_in_flight() -> None:
    row = claimed_row()
    connection = FakeConnection([row])
    repository = PushDeliveryRepository(FakePool(connection))  # type: ignore[arg-type]

    claimed = await repository.claim_ready(
        batch_size=25,
        lease_timeout_seconds=60,
    )

    assert len(claimed) == 1
    assert claimed[0].id == row["id"]
    assert claimed[0].attempt_number == 1

    claim_query, claim_args = connection.fetch_calls[0]
    assert "FOR UPDATE OF da SKIP LOCKED" in claim_query
    assert "next_attempt_at" in claim_query
    assert claim_args[-1] == 25

    update_query, update_args = connection.execute_calls[0]
    assert "attempt_number = COALESCE(attempt_number, 0) + 1" in update_query
    assert "in_flight" in update_args
    assert update_args[0] == [row["id"]]


@pytest.mark.asyncio
async def test_empty_claim_does_not_issue_an_update() -> None:
    connection = FakeConnection([])
    repository = PushDeliveryRepository(FakePool(connection))  # type: ignore[arg-type]

    claimed = await repository.claim_ready(
        batch_size=10,
        lease_timeout_seconds=30,
    )

    assert claimed == []
    assert connection.execute_calls == []


@pytest.mark.asyncio
async def test_two_concurrent_claimers_receive_disjoint_attempts() -> None:
    rows = [claimed_row() for _ in range(8)]
    repository = PushDeliveryRepository(ConcurrentPool(rows))  # type: ignore[arg-type]

    first, second = await asyncio.gather(
        repository.claim_ready(batch_size=4, lease_timeout_seconds=60),
        repository.claim_ready(batch_size=4, lease_timeout_seconds=60),
    )

    first_ids = {attempt.id for attempt in first}
    second_ids = {attempt.id for attempt in second}
    assert len(first_ids) == 4
    assert len(second_ids) == 4
    assert first_ids.isdisjoint(second_ids)


@pytest.mark.asyncio
async def test_receipt_claim_uses_skip_locked_and_refreshes_poll_time() -> None:
    attempt_id = uuid4()
    connection = FakeConnection(
        [
            {
                "id": attempt_id,
                "device_token_id": uuid4(),
                "provider_message_id": "ticket-1",
                "attempt_number": 2,
                "attempted_at": datetime.now(UTC),
            }
        ]
    )
    repository = PushDeliveryRepository(FakePool(connection))  # type: ignore[arg-type]

    claimed = await repository.claim_sent_for_receipts(
        batch_size=1000,
        receipt_delay_seconds=15,
    )

    assert claimed[0].provider_message_id == "ticket-1"
    assert "FOR UPDATE SKIP LOCKED" in connection.fetch_calls[0][0]
    assert connection.execute_calls[0][1][0] == [attempt_id]


@pytest.mark.asyncio
async def test_retry_schedule_is_persisted_as_an_interval() -> None:
    connection = FakeConnection([])
    repository = PushDeliveryRepository(FakePool(connection))  # type: ignore[arg-type]
    attempt_id = uuid4()

    await repository.schedule_retry(
        attempt_id,
        failure_reason="temporary failure",
        delay_seconds=20,
    )

    query, args = connection.execute_calls[0]
    assert "next_attempt_at = now()" in query
    assert args[0] == attempt_id
    assert args[1] == "queued"
    assert args[3].total_seconds() == 20
