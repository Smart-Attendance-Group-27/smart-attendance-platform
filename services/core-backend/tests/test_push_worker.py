import asyncio
import logging
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from modules.notification.push.exception import ExpoNetworkError
from modules.notification.push.provider import PushDeliveryReceipt, PushReceipt
from modules.notification.push.repository import ClaimedDelivery, SentDelivery
from modules.notification.push.worker import (
    PushDeliveryWorker,
    PushWorkerConfig,
    retry_delay_seconds,
)


TOKEN = "ExponentPushToken[never-log-this-value]"


def claimed(*, attempt_number: int = 1, active: bool = True) -> ClaimedDelivery:
    return ClaimedDelivery(
        id=uuid4(),
        notification_id=uuid4(),
        notification_code="ATTENDANCE_SESSION_OPENED",
        device_token_id=uuid4(),
        expo_push_token=TOKEN,
        attempt_number=attempt_number,
        title="Attendance open",
        body="Check in now",
        priority="high",
        related_entity_type="ATTENDANCE_SESSION",
        related_entity_id=uuid4(),
        token_is_active=active,
    )


def sent(*, attempt_number: int = 1) -> SentDelivery:
    return SentDelivery(
        id=uuid4(),
        device_token_id=uuid4(),
        provider_message_id="ticket-1",
        attempt_number=attempt_number,
    )


def build_worker(repository, provider, **overrides) -> PushDeliveryWorker:
    values = {
        "batch_size": 100,
        "receipt_batch_size": 1000,
        "poll_interval_seconds": 0.01,
        "receipt_delay_seconds": 0,
        "lease_timeout_seconds": 60,
        "max_attempts": 3,
        "retry_base_seconds": 5,
        "retry_max_seconds": 60,
    }
    values.update(overrides)
    return PushDeliveryWorker(
        repository=repository,
        provider=provider,
        config=PushWorkerConfig(**values),
    )


def repository_mock():
    repository = AsyncMock()
    repository.claim_ready.return_value = []
    repository.claim_sent_for_receipts.return_value = []
    return repository


@pytest.mark.asyncio
async def test_worker_sends_claimed_messages_and_persists_tickets() -> None:
    attempt = claimed()
    repository = repository_mock()
    repository.claim_ready.return_value = [attempt]
    provider = AsyncMock()
    provider.send_many.return_value = [
        PushReceipt(TOKEN, "ok", "ticket-1", None, False)
    ]
    provider.fetch_receipts.return_value = {}

    stats = await build_worker(repository, provider).run_once()

    assert stats.claimed == 1
    assert stats.tickets_persisted == 1
    message = provider.send_many.call_args.args[0][0]
    assert message.to == TOKEN
    assert message.data["notificationId"] == str(attempt.notification_id)
    assert message.data["notificationCode"] == "ATTENDANCE_SESSION_OPENED"
    repository.mark_sent.assert_awaited_once_with(attempt.id, "ticket-1")


@pytest.mark.asyncio
async def test_worker_retries_provider_failure_with_exponential_backoff() -> None:
    attempt = claimed(attempt_number=2)
    repository = repository_mock()
    repository.claim_ready.return_value = [attempt]
    provider = AsyncMock()
    provider.send_many.side_effect = ExpoNetworkError("temporary")

    stats = await build_worker(repository, provider).run_once()

    assert stats.retried == 1
    repository.schedule_retry.assert_awaited_once_with(
        attempt.id,
        failure_reason="temporary",
        delay_seconds=10,
    )


@pytest.mark.asyncio
async def test_worker_marks_failure_terminal_at_attempt_cap() -> None:
    attempt = claimed(attempt_number=3)
    repository = repository_mock()
    repository.claim_ready.return_value = [attempt]
    provider = AsyncMock()
    provider.send_many.side_effect = ExpoNetworkError("still unavailable")

    stats = await build_worker(repository, provider).run_once()

    assert stats.failed == 1
    repository.mark_failed.assert_awaited_once_with(
        attempt.id,
        failure_reason="still unavailable",
    )
    repository.schedule_retry.assert_not_awaited()


@pytest.mark.asyncio
async def test_receipt_marks_delivery_complete() -> None:
    attempt = sent()
    repository = repository_mock()
    repository.claim_sent_for_receipts.return_value = [attempt]
    provider = AsyncMock()
    provider.fetch_receipts.return_value = {
        "ticket-1": PushDeliveryReceipt("ticket-1", "ok", None, False)
    }

    stats = await build_worker(repository, provider).run_once()

    assert stats.delivered == 1
    repository.mark_delivered.assert_awaited_once_with(attempt.id)


@pytest.mark.asyncio
async def test_device_not_registered_receipt_deactivates_token() -> None:
    attempt = sent()
    repository = repository_mock()
    repository.claim_sent_for_receipts.return_value = [attempt]
    provider = AsyncMock()
    provider.fetch_receipts.return_value = {
        "ticket-1": PushDeliveryReceipt(
            "ticket-1",
            "error",
            "DeviceNotRegistered: gone",
            True,
        )
    }

    stats = await build_worker(repository, provider).run_once()

    assert stats.tokens_deactivated == 1
    repository.mark_failed.assert_awaited_once_with(
        attempt.id,
        failure_reason="DeviceNotRegistered: gone",
    )
    repository.deactivate_token.assert_awaited_once_with(attempt.device_token_id)


@pytest.mark.asyncio
async def test_transient_receipt_failure_requeues_with_backoff() -> None:
    attempt = sent(attempt_number=2)
    repository = repository_mock()
    repository.claim_sent_for_receipts.return_value = [attempt]
    provider = AsyncMock()
    provider.fetch_receipts.return_value = {
        "ticket-1": PushDeliveryReceipt(
            "ticket-1",
            "error",
            "MessageRateExceeded: retry later",
            False,
        )
    }

    stats = await build_worker(repository, provider).run_once()

    assert stats.retried == 1
    repository.schedule_retry.assert_awaited_once_with(
        attempt.id,
        failure_reason="MessageRateExceeded: retry later",
        delay_seconds=10,
    )


@pytest.mark.asyncio
async def test_invalid_token_ticket_fails_and_deactivates_without_receipt_poll() -> None:
    attempt = claimed()
    repository = repository_mock()
    repository.claim_ready.return_value = [attempt]
    provider = AsyncMock()
    provider.send_many.return_value = [
        PushReceipt(
            TOKEN,
            "error",
            None,
            "DeviceNotRegistered: gone",
            True,
        )
    ]

    stats = await build_worker(repository, provider).run_once()

    assert stats.failed == 1
    assert stats.tokens_deactivated == 1
    repository.deactivate_token.assert_awaited_once_with(attempt.device_token_id)


@pytest.mark.asyncio
async def test_inactive_token_is_failed_without_being_sent() -> None:
    attempt = claimed(active=False)
    repository = repository_mock()
    repository.claim_ready.return_value = [attempt]
    provider = AsyncMock()

    stats = await build_worker(repository, provider).run_once()

    assert stats.failed == 1
    provider.send_many.assert_not_awaited()


@pytest.mark.asyncio
async def test_worker_stops_cleanly() -> None:
    repository = repository_mock()
    provider = AsyncMock()
    worker = build_worker(repository, provider)
    stop_event = asyncio.Event()

    task = asyncio.create_task(worker.run(stop_event))
    await asyncio.sleep(0)
    stop_event.set()
    await asyncio.wait_for(task, timeout=1)

    assert task.done()


@pytest.mark.asyncio
async def test_worker_logs_never_include_push_token(caplog) -> None:
    attempt = claimed()
    repository = repository_mock()
    repository.claim_ready.return_value = [attempt]
    provider = AsyncMock()
    provider.send_many.side_effect = RuntimeError(f"bad payload for {TOKEN}")
    worker = build_worker(repository, provider)
    stop_event = asyncio.Event()

    async def stop_after_cycle():
        await asyncio.sleep(0.02)
        stop_event.set()

    with caplog.at_level(logging.ERROR):
        await asyncio.gather(worker.run(stop_event), stop_after_cycle())

    assert TOKEN not in caplog.text


@pytest.mark.parametrize(
    ("attempt_number", "expected"),
    [(1, 5), (2, 10), (3, 20), (10, 60)],
)
def test_retry_delay_is_exponential_and_capped(attempt_number, expected) -> None:
    assert retry_delay_seconds(
        attempt_number,
        base_seconds=5,
        max_seconds=60,
    ) == expected
