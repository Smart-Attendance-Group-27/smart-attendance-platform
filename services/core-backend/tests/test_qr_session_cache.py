from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from redis import RedisError

from modules.attendance_sessions.qr_session.cache import QrBatchMetadataCache
from modules.attendance_sessions.qr_session.metadata import QrBatchMetadata


class FakeRedis:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.values: dict[str, str] = {}
        self.set_calls: list[tuple[str, str, int | None]] = []
        self.delete_calls: list[str] = []

    async def get(self, key: str) -> str | None:
        if self.fail:
            raise RedisError("redis unavailable")
        return self.values.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        if self.fail:
            raise RedisError("redis unavailable")
        self.values[key] = value
        self.set_calls.append((key, value, ex))

    async def delete(self, key: str) -> None:
        if self.fail:
            raise RedisError("redis unavailable")
        self.values.pop(key, None)
        self.delete_calls.append(key)


@pytest.mark.asyncio
async def test_qr_batch_cache_stores_and_returns_metadata_with_ttl() -> None:
    redis = FakeRedis()
    cache = QrBatchMetadataCache(redis)
    metadata = build_metadata()

    await cache.set_qr_batch_cache(metadata.id, metadata, ttl_seconds=120)
    result = await cache.get_qr_batch_cache(metadata.id)

    assert result == metadata
    assert redis.set_calls[0][0] == f"qr:batch:{metadata.id}"
    assert redis.set_calls[0][2] == 120


@pytest.mark.asyncio
async def test_qr_batch_cache_delete_invalidates_metadata() -> None:
    redis = FakeRedis()
    cache = QrBatchMetadataCache(redis)
    metadata = build_metadata()

    await cache.set_qr_batch_cache(metadata.id, metadata, ttl_seconds=120)
    await cache.delete_qr_batch_cache(metadata.id)

    assert await cache.get_qr_batch_cache(metadata.id) is None
    assert redis.delete_calls == [f"qr:batch:{metadata.id}"]


@pytest.mark.asyncio
async def test_qr_batch_cache_redis_failures_are_safe() -> None:
    cache = QrBatchMetadataCache(FakeRedis(fail=True))
    metadata = build_metadata()

    assert await cache.get_qr_batch_cache(metadata.id) is None
    await cache.set_qr_batch_cache(metadata.id, metadata, ttl_seconds=120)
    await cache.delete_qr_batch_cache(metadata.id)


@pytest.mark.asyncio
async def test_qr_batch_cache_does_not_store_raw_qr_values_or_secrets() -> None:
    redis = FakeRedis()
    cache = QrBatchMetadataCache(redis)
    metadata = build_metadata()

    await cache.set_qr_batch_cache(metadata.id, metadata, ttl_seconds=120)

    cached_json = redis.set_calls[0][1]
    assert "raw-qr-value" not in cached_json
    assert "token_hash" not in cached_json
    assert "hmac" not in cached_json.lower()
    assert "secret" not in cached_json.lower()


def build_metadata() -> QrBatchMetadata:
    return QrBatchMetadata(
        id=UUID("50000000-0000-0000-0000-000000000001"),
        attendance_session_id=UUID("40000000-0000-0000-0000-000000000001"),
        mode="dynamic",
        status="active",
        activated_at=datetime(2026, 8, 6, 10, 0, tzinfo=UTC),
        deactivated_at=None,
        refresh_interval_seconds=15,
        expires_at=datetime(2026, 8, 6, 10, 0, tzinfo=UTC)
        + timedelta(minutes=15),
    )
