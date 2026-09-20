"""Unit tests for NotificationService (notification_service.py)."""

import asyncio
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from modules.notification.device_tokens.repository import DeviceTokenRecord
from modules.notification.push.exception import (
    InactiveNotificationTypeError,
    NotificationTypeNotFoundError,
    PushDeliveryError,
)
from modules.notification.push.notification_service import NotificationService
from modules.notification.push.provider import PushMessage, PushReceipt

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

USER_ID = UUID("20000000-0000-0000-0000-000000000011")
TOKEN_ID_A = UUID("d0000000-0000-0000-0000-000000000001")
TOKEN_ID_B = UUID("d0000000-0000-0000-0000-000000000002")
TOKEN_A = "ExponentPushToken[aaaaaaaaaaaaaaaaaaaaa]"
TOKEN_B = "ExponentPushToken[bbbbbbbbbbbbbbbbbbbbb]"
NOTIFICATION_TYPE = "ATTENDANCE_SESSION_OPENED"

# ---------------------------------------------------------------------------
# Fake infrastructure
# ---------------------------------------------------------------------------


def _make_token_record(
    token_id: UUID = TOKEN_ID_A,
    expo_token: str = TOKEN_A,
    is_active: bool = True,
) -> DeviceTokenRecord:
    return DeviceTokenRecord(
        id=token_id,
        user_id=USER_ID,
        expo_push_token=expo_token,
        platform="android",
        is_active=is_active,
        registered_at=datetime(2026, 1, 1, tzinfo=UTC),
        last_used_at=None,
        revoked_at=None,
    )


class FakeConnection:
    """In-memory asyncpg connection for NotificationService tests."""

    _SENTINEL = object()  # distinguish "not provided" from explicit None

    def __init__(
        self,
        *,
        type_row: dict | None = _SENTINEL,  # type: ignore[assignment]
        pref_row: dict | None = None,
        active_tokens: list[DeviceTokenRecord] | None = None,
    ) -> None:
        # Use sentinel to distinguish "caller passed None" from "not provided".
        if type_row is FakeConnection._SENTINEL:
            self._type_row: dict | None = {
                "code": NOTIFICATION_TYPE,
                "default_push_enabled": True,
                "default_in_app_enabled": True,
                "is_active": True,
            }
        else:
            self._type_row = type_row
        self._pref_row = pref_row          # None → fall back to type default
        self._active_tokens = active_tokens or []
        self.executed: list[str] = []
        self.updates: list[dict] = []
        self._notification_id: UUID | None = None
        self._attempt_ids: list[UUID] = []
        self._deactivated: list[UUID] = []


    async def fetchrow(self, query: str, *args: Any) -> dict | None:
        self.executed.append(query)
        if "notification_types" in query:
            return self._type_row  # type: ignore[return-value]
        if "notification_preferences" in query:
            return self._pref_row  # type: ignore[return-value]
        return None

    async def fetch(self, query: str, *args: Any) -> list:
        self.executed.append(query)
        if "device_tokens" in query:
            return [
                {
                    "id": t.id,
                    "user_id": t.user_id,
                    "expo_push_token": t.expo_push_token,
                    "platform": t.platform,
                    "is_active": t.is_active,
                    "registered_at": t.registered_at,
                    "last_used_at": t.last_used_at,
                    "revoked_at": t.revoked_at,
                }
                for t in self._active_tokens
            ]
        return []

    async def execute(self, query: str, *args: Any) -> str:
        self.executed.append(query)
        if "notification.notifications" in query and "INSERT" in query:
            self._notification_id = args[0]
        if "delivery_attempts" in query and "INSERT" in query:
            self._attempt_ids.append(args[0])
        if "delivery_attempts" in query and "UPDATE" in query:
            self.updates.append({"attempt_id": args[0], "status": args[1]})
        if "is_active  = false" in query:
            self._deactivated.append(args[0])
        return "OK"


class FakePool:
    def __init__(self, connection: FakeConnection) -> None:
        self._conn = connection

    @asynccontextmanager
    async def acquire(self):
        yield self._conn


class OkPushProvider:
    """Always returns successful receipts."""

    async def send_many(self, messages: list[PushMessage]) -> list[PushReceipt]:
        return [
            PushReceipt(
                token=m.to,
                status="ok",
                provider_id=f"expo-{i}",
                failure_reason=None,
                is_invalid_token=False,
            )
            for i, m in enumerate(messages)
        ]


class FailPushProvider:
    """Always returns error receipts."""

    def __init__(self, *, is_invalid: bool = False) -> None:
        self._is_invalid = is_invalid

    async def send_many(self, messages: list[PushMessage]) -> list[PushReceipt]:
        return [
            PushReceipt(
                token=m.to,
                status="error",
                provider_id=None,
                failure_reason="DeviceNotRegistered" if self._is_invalid else "SomeError",
                is_invalid_token=self._is_invalid,
            )
            for m in messages
        ]


class RaisingPushProvider:
    """Raises PushDeliveryError on every call."""

    async def send_many(self, messages: list[PushMessage]) -> list[PushReceipt]:
        raise PushDeliveryError("Expo is down")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _run_with_background_tasks(coro):
    """Run coro then let any spawned background tasks complete."""
    result = await coro
    # Give event loop one cycle to start background tasks.
    await asyncio.sleep(0)
    # Drain remaining tasks.
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
    return result


# ---------------------------------------------------------------------------
# Notification type validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_raises_when_type_not_found():
    conn = FakeConnection(type_row=None)
    pool = FakePool(conn)
    service = NotificationService(push_provider=OkPushProvider())

    with pytest.raises(NotificationTypeNotFoundError):
        await service.send_notification(
            pool,
            recipient_user_id=USER_ID,
            notification_type="UNKNOWN_TYPE",
            title="T",
            body="B",
        )


@pytest.mark.asyncio
async def test_raises_when_type_is_inactive():
    conn = FakeConnection(
        type_row={
            "code": NOTIFICATION_TYPE,
            "default_push_enabled": True,
            "default_in_app_enabled": True,
            "is_active": False,
        }
    )
    pool = FakePool(conn)
    service = NotificationService(push_provider=OkPushProvider())

    with pytest.raises(InactiveNotificationTypeError):
        await service.send_notification(
            pool,
            recipient_user_id=USER_ID,
            notification_type=NOTIFICATION_TYPE,
            title="T",
            body="B",
        )


# ---------------------------------------------------------------------------
# Notification creation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_notification_row_is_inserted():
    conn = FakeConnection(active_tokens=[_make_token_record()])
    pool = FakePool(conn)
    service = NotificationService(push_provider=OkPushProvider())

    notification_id = await _run_with_background_tasks(
        service.send_notification(
            pool,
            recipient_user_id=USER_ID,
            notification_type=NOTIFICATION_TYPE,
            title="Open",
            body="Session is open",
        )
    )

    assert isinstance(notification_id, UUID)
    assert any("notification.notifications" in q for q in conn.executed)


# ---------------------------------------------------------------------------
# Push preference — disabled
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_push_skipped_when_user_pref_disabled():
    """When user preference explicitly disables push, no delivery attempt is inserted."""
    conn = FakeConnection(
        pref_row={"push_enabled": False},
        active_tokens=[_make_token_record()],
    )
    pool = FakePool(conn)
    service = NotificationService(push_provider=OkPushProvider())

    await service.send_notification(
        pool,
        recipient_user_id=USER_ID,
        notification_type=NOTIFICATION_TYPE,
        title="T",
        body="B",
    )

    assert conn._attempt_ids == []


# ---------------------------------------------------------------------------
# Push preference — default fallback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_push_uses_type_default_when_no_preference():
    """When no user preference exists, falls back to default_push_enabled=True."""
    conn = FakeConnection(
        pref_row=None,
        active_tokens=[_make_token_record()],
    )
    pool = FakePool(conn)
    service = NotificationService(push_provider=OkPushProvider())

    await _run_with_background_tasks(
        service.send_notification(
            pool,
            recipient_user_id=USER_ID,
            notification_type=NOTIFICATION_TYPE,
            title="T",
            body="B",
        )
    )

    # A delivery attempt should have been created.
    assert len(conn._attempt_ids) == 1


# ---------------------------------------------------------------------------
# No active device tokens
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_push_when_no_active_tokens():
    conn = FakeConnection(active_tokens=[])
    pool = FakePool(conn)
    service = NotificationService(push_provider=OkPushProvider())

    await service.send_notification(
        pool,
        recipient_user_id=USER_ID,
        notification_type=NOTIFICATION_TYPE,
        title="T",
        body="B",
    )

    assert conn._attempt_ids == []


# ---------------------------------------------------------------------------
# Multi-device delivery
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delivery_attempt_per_device():
    tokens = [
        _make_token_record(TOKEN_ID_A, TOKEN_A),
        _make_token_record(TOKEN_ID_B, TOKEN_B),
    ]
    conn = FakeConnection(active_tokens=tokens)
    pool = FakePool(conn)
    service = NotificationService(push_provider=OkPushProvider())

    await _run_with_background_tasks(
        service.send_notification(
            pool,
            recipient_user_id=USER_ID,
            notification_type=NOTIFICATION_TYPE,
            title="T",
            body="B",
        )
    )

    assert len(conn._attempt_ids) == 2
    sent_statuses = [u["status"] for u in conn.updates]
    assert all(s == "sent" for s in sent_statuses)


# ---------------------------------------------------------------------------
# Failed delivery — marks attempt as failed
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_failed_delivery_marks_attempt_failed():
    conn = FakeConnection(active_tokens=[_make_token_record()])
    pool = FakePool(conn)
    service = NotificationService(push_provider=FailPushProvider())

    await _run_with_background_tasks(
        service.send_notification(
            pool,
            recipient_user_id=USER_ID,
            notification_type=NOTIFICATION_TYPE,
            title="T",
            body="B",
        )
    )

    assert len(conn.updates) == 1
    assert conn.updates[0]["status"] == "failed"


# ---------------------------------------------------------------------------
# Invalid token — deactivates the token
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_invalid_token_deactivates_device():
    conn = FakeConnection(active_tokens=[_make_token_record(token_id=TOKEN_ID_A)])
    pool = FakePool(conn)
    service = NotificationService(push_provider=FailPushProvider(is_invalid=True))

    await _run_with_background_tasks(
        service.send_notification(
            pool,
            recipient_user_id=USER_ID,
            notification_type=NOTIFICATION_TYPE,
            title="T",
            body="B",
        )
    )

    assert TOKEN_ID_A in conn._deactivated


# ---------------------------------------------------------------------------
# Provider-level failure — all attempts marked failed
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_provider_level_failure_marks_all_attempts_failed():
    tokens = [_make_token_record(TOKEN_ID_A, TOKEN_A), _make_token_record(TOKEN_ID_B, TOKEN_B)]
    conn = FakeConnection(active_tokens=tokens)
    pool = FakePool(conn)
    service = NotificationService(push_provider=RaisingPushProvider())

    await _run_with_background_tasks(
        service.send_notification(
            pool,
            recipient_user_id=USER_ID,
            notification_type=NOTIFICATION_TYPE,
            title="T",
            body="B",
        )
    )

    failed_statuses = [u["status"] for u in conn.updates]
    assert len(failed_statuses) == 2
    assert all(s == "failed" for s in failed_statuses)
