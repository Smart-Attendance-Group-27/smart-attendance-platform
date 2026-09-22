"""Unit tests for DeviceTokenService."""

from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4
from datetime import datetime, UTC

import pytest

from modules.notification.device_tokens.exception import (
    InvalidExpoPushTokenError,
    UnsupportedPlatformError,
)
from modules.notification.device_tokens.repository import DeviceTokenRecord
from modules.notification.device_tokens.service import DeviceTokenService

USER_ID = UUID("20000000-0000-0000-0000-000000000011")
TOKEN_ID = UUID("d0000000-0000-0000-0000-000000000001")

VALID_TOKEN = "ExponentPushToken[xxxxxxxxxxxxxxxxxxxxxx]"
VALID_TOKEN_NEW_FORMAT = "ExpoPushToken[yyyyyyyyyyyyyyyyyyyyyy]"


def _make_record(
    token: str = VALID_TOKEN,
    platform: str = "android",
    is_active: bool = True,
) -> DeviceTokenRecord:
    return DeviceTokenRecord(
        id=TOKEN_ID,
        user_id=USER_ID,
        expo_push_token=token,
        platform=platform,
        is_active=is_active,
        registered_at=datetime(2026, 1, 1, tzinfo=UTC),
        last_used_at=None,
        revoked_at=None,
    )


# ---------------------------------------------------------------------------
# Token format validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_register_rejects_empty_token():
    service = DeviceTokenService()
    pool = AsyncMock()
    with pytest.raises(InvalidExpoPushTokenError):
        await service.register(pool, user_id=USER_ID, expo_push_token="", platform="android")


@pytest.mark.asyncio
async def test_register_rejects_malformed_token():
    service = DeviceTokenService()
    pool = AsyncMock()
    with pytest.raises(InvalidExpoPushTokenError):
        await service.register(
            pool, user_id=USER_ID, expo_push_token="not-a-token", platform="android"
        )


@pytest.mark.asyncio
async def test_register_accepts_exponent_prefix():
    repo = AsyncMock()
    repo.upsert.return_value = _make_record()
    service = DeviceTokenService(repository=repo)

    conn = AsyncMock()
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=conn)
    ctx.__aexit__ = AsyncMock(return_value=None)
    pool = MagicMock()
    pool.acquire.return_value = ctx

    result = await service.register(
        pool, user_id=USER_ID, expo_push_token=VALID_TOKEN, platform="android"
    )
    assert result.expo_push_token == VALID_TOKEN


@pytest.mark.asyncio
async def test_register_accepts_expo_prefix():
    repo = AsyncMock()
    repo.upsert.return_value = _make_record(token=VALID_TOKEN_NEW_FORMAT)
    service = DeviceTokenService(repository=repo)

    conn = AsyncMock()
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=conn)
    ctx.__aexit__ = AsyncMock(return_value=None)
    pool = MagicMock()
    pool.acquire.return_value = ctx

    result = await service.register(
        pool,
        user_id=USER_ID,
        expo_push_token=VALID_TOKEN_NEW_FORMAT,
        platform="android",
    )
    assert result.expo_push_token == VALID_TOKEN_NEW_FORMAT


# ---------------------------------------------------------------------------
# Platform validation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("platform", ["windows", "ios", "web", "macos", ""])
@pytest.mark.asyncio
async def test_register_rejects_non_android_platform(platform: str):
    service = DeviceTokenService()
    pool = AsyncMock()
    with pytest.raises(UnsupportedPlatformError):
        await service.register(
            pool, user_id=USER_ID, expo_push_token=VALID_TOKEN, platform=platform
        )


@pytest.mark.asyncio
async def test_register_accepts_android_platform():
    repo = AsyncMock()
    repo.upsert.return_value = _make_record(platform="android")
    service = DeviceTokenService(repository=repo)

    conn = AsyncMock()
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=conn)
    ctx.__aexit__ = AsyncMock(return_value=None)
    pool = MagicMock()
    pool.acquire.return_value = ctx

    result = await service.register(
        pool, user_id=USER_ID, expo_push_token=VALID_TOKEN, platform="android"
    )
    assert result.platform == "android"


# ---------------------------------------------------------------------------
# Platform normalisation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_register_lowercases_platform():
    repo = AsyncMock()
    repo.upsert.return_value = _make_record(platform="android")
    service = DeviceTokenService(repository=repo)

    conn = AsyncMock()
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=conn)
    ctx.__aexit__ = AsyncMock(return_value=None)
    pool = MagicMock()
    pool.acquire.return_value = ctx

    await service.register(
        pool, user_id=USER_ID, expo_push_token=VALID_TOKEN, platform="Android"
    )
    # The repo should have been called with lowercase
    repo.upsert.assert_called_once()
    call_kwargs = repo.upsert.call_args.kwargs
    assert call_kwargs["platform"] == "android"


# ---------------------------------------------------------------------------
# Token revocation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_revoke_accepts_valid_token():
    repo = AsyncMock()
    repo.revoke.return_value = True
    service = DeviceTokenService(repository=repo)

    conn = AsyncMock()
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=conn)
    ctx.__aexit__ = AsyncMock(return_value=None)
    pool = MagicMock()
    pool.acquire.return_value = ctx

    revoked = await service.revoke(pool, user_id=USER_ID, expo_push_token=VALID_TOKEN)
    assert revoked is True
    repo.revoke.assert_called_once_with(conn, user_id=USER_ID, expo_push_token=VALID_TOKEN)


@pytest.mark.asyncio
async def test_revoke_rejects_malformed_token():
    service = DeviceTokenService()
    pool = AsyncMock()
    with pytest.raises(InvalidExpoPushTokenError):
        await service.revoke(pool, user_id=USER_ID, expo_push_token="bad-token")


@pytest.mark.asyncio
async def test_upsert_transfers_token_ownership_without_touching_other_tokens():
    from modules.notification.device_tokens.repository import DeviceTokenRepository

    new_user_id = uuid4()
    connection = AsyncMock()
    connection.fetchrow.return_value = {
        "id": TOKEN_ID,
        "user_id": new_user_id,
        "expo_push_token": VALID_TOKEN,
        "platform": "android",
        "is_active": True,
        "registered_at": datetime(2026, 1, 1, tzinfo=UTC),
        "last_used_at": datetime(2026, 1, 2, tzinfo=UTC),
        "revoked_at": None,
    }

    record = await DeviceTokenRepository().upsert(
        connection,
        user_id=new_user_id,
        expo_push_token=VALID_TOKEN,
        platform="android",
    )

    assert record.user_id == new_user_id
    query = connection.fetchrow.call_args.args[0]
    assert "user_id      = EXCLUDED.user_id" in query
    assert "UPDATE notification.device_tokens" not in query
