from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import UUID

import pytest

from modules.attendance_sessions.qr_session.exception import (
    AttendanceSessionNotActiveError,
    AttendanceSessionNotFoundError,
    DynamicQrConfigurationError,
    DynamicQrSessionUnavailableError,
    QrSessionNotFoundError,
)
from modules.attendance_sessions.qr_session.crypto import generate_dynamic_qr_value
from modules.attendance_sessions.qr_session.repository import (
    AttendanceSessionRecord,
    QrVerificationRecord,
)
from modules.attendance_sessions.qr_session.metadata import QrBatchMetadata
from modules.attendance_sessions.qr_session.service import QrSessionService


class FakeTransaction:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, exc_type: object, exc: object, traceback: object) -> bool:
        return False


class FakeConnection:
    def transaction(self) -> FakeTransaction:
        return FakeTransaction()


class FakeAcquire:
    def __init__(self, connection: FakeConnection) -> None:
        self._connection = connection

    async def __aenter__(self) -> FakeConnection:
        return self._connection

    async def __aexit__(self, exc_type: object, exc: object, traceback: object) -> bool:
        return False


class FakePool:
    def __init__(self) -> None:
        self.connection = FakeConnection()

    def acquire(self) -> FakeAcquire:
        return FakeAcquire(self.connection)


class FakeRepository:
    def __init__(self, session: AttendanceSessionRecord | None) -> None:
        self.session = session
        self.closed_session_id: UUID | None = None
        self.inserted_batch: tuple[UUID, UUID, str, int | None, datetime, datetime] | None = None
        self.inserted_token: tuple[UUID, UUID, str, datetime, datetime] | None = None
        self.deactivated_batch_ids: list[UUID] = []
        self.metadata: QrBatchMetadata | None = None
        self.verification_record: QrVerificationRecord | None = None
        self.fetched_qr_session_id: UUID | None = None

    async def lock_attendance_session(
        self,
        connection: FakeConnection,
        session_id: UUID,
    ) -> AttendanceSessionRecord | None:
        return self.session

    async def close_existing_active_qr_sessions(
        self,
        connection: FakeConnection,
        session_id: UUID,
        deactivated_at: datetime,
    ) -> list[UUID]:
        self.closed_session_id = session_id
        return self.deactivated_batch_ids

    async def insert_qr_batch(
        self,
        connection: FakeConnection,
        qr_session_id: UUID,
        attendance_session_id: UUID,
        mode: str,
        refresh_interval_seconds: int | None,
        activated_at: datetime,
        expires_at: datetime,
    ) -> None:
        self.inserted_batch = (
            qr_session_id,
            attendance_session_id,
            mode,
            refresh_interval_seconds,
            activated_at,
            expires_at,
        )

    async def insert_qr_token(
        self,
        connection: FakeConnection,
        qr_token_id: UUID,
        qr_session_id: UUID,
        token_hash: str,
        valid_from: datetime,
        expires_at: datetime,
    ) -> None:
        self.inserted_token = (qr_token_id, qr_session_id, token_hash, valid_from, expires_at)

    async def fetch_qr_batch_metadata(
        self,
        connection: FakeConnection,
        qr_session_id: UUID,
    ) -> QrBatchMetadata | None:
        self.fetched_qr_session_id = qr_session_id
        return self.metadata

    async def fetch_qr_verification_record(
        self,
        connection: FakeConnection,
        qr_session_id: UUID,
    ) -> QrVerificationRecord | None:
        self.fetched_qr_session_id = qr_session_id
        return self.verification_record


class FakeVerificationRepository:
    def __init__(self, record: QrVerificationRecord | None) -> None:
        self.record = record
        self.requested_qr_session_id: UUID | None = None

    async def fetch_qr_verification_record(
        self,
        connection: FakeConnection,
        qr_session_id: UUID,
    ) -> QrVerificationRecord | None:
        self.requested_qr_session_id = qr_session_id
        return self.record


class FakeQrBatchCache:
    def __init__(
        self,
        cached_metadata: QrBatchMetadata | None = None,
        fail_reads: bool = False,
    ) -> None:
        self.cached_metadata = cached_metadata
        self.fail_reads = fail_reads
        self.get_calls: list[UUID] = []
        self.set_calls: list[tuple[UUID, QrBatchMetadata, int]] = []
        self.delete_calls: list[UUID] = []

    async def get_qr_batch_cache(
        self,
        qr_session_id: UUID,
    ) -> QrBatchMetadata | None:
        self.get_calls.append(qr_session_id)
        if self.fail_reads:
            return None
        return self.cached_metadata

    async def set_qr_batch_cache(
        self,
        qr_session_id: UUID,
        metadata: QrBatchMetadata,
        ttl_seconds: int,
    ) -> None:
        self.set_calls.append((qr_session_id, metadata, ttl_seconds))

    async def delete_qr_batch_cache(self, qr_session_id: UUID) -> None:
        self.delete_calls.append(qr_session_id)


@pytest.mark.asyncio
async def test_create_static_qr_session_hashes_raw_value_and_caps_expiration() -> None:
    current_time = datetime(2026, 8, 6, 10, 0, tzinfo=UTC)
    attendance_session_id = UUID("40000000-0000-0000-0000-000000000001")
    qr_session_id = UUID("50000000-0000-0000-0000-000000000001")
    qr_token_id = UUID("60000000-0000-0000-0000-000000000001")
    repository = FakeRepository(
        AttendanceSessionRecord(
            id=attendance_session_id,
            status="active",
            scheduled_end_at=current_time + timedelta(minutes=20),
            closed_at=None,
            cancelled_at=None,
        )
    )
    uuid_values = iter([qr_session_id, qr_token_id])
    service = QrSessionService(
        repository=repository,
        clock=lambda: current_time,
        uuid_factory=lambda: next(uuid_values),
        qr_value_generator=lambda: "raw-test-token",
    )

    result = await service.create_static_qr_session(
        FakePool(),
        attendance_session_id,
        valid_for_seconds=3600,
    )

    expected_hash = sha256("raw-test-token".encode("utf-8")).hexdigest()

    assert result.qr_session_id == qr_session_id
    assert result.attendance_session_id == attendance_session_id
    assert result.mode == "static"
    assert result.qr_value == "raw-test-token"
    assert result.refresh_interval_seconds is None
    assert result.valid_from == current_time
    assert result.expires_at == current_time + timedelta(minutes=20)
    assert repository.closed_session_id == attendance_session_id
    assert repository.inserted_batch == (
        qr_session_id,
        attendance_session_id,
        "static",
        None,
        current_time,
        current_time + timedelta(minutes=20),
    )
    assert repository.inserted_token == (
        qr_token_id,
        qr_session_id,
        expected_hash,
        current_time,
        current_time + timedelta(minutes=20),
    )


@pytest.mark.asyncio
async def test_create_static_qr_session_rejects_missing_attendance_session() -> None:
    service = QrSessionService(
        repository=FakeRepository(None),
        clock=lambda: datetime(2026, 8, 6, 10, 0, tzinfo=UTC),
    )

    with pytest.raises(AttendanceSessionNotFoundError):
        await service.create_static_qr_session(
            FakePool(),
            UUID("40000000-0000-0000-0000-000000000001"),
            valid_for_seconds=300,
        )


@pytest.mark.asyncio
async def test_create_static_qr_session_rejects_ended_session() -> None:
    current_time = datetime(2026, 8, 6, 10, 0, tzinfo=UTC)
    attendance_session_id = UUID("40000000-0000-0000-0000-000000000001")
    service = QrSessionService(
        repository=FakeRepository(
            AttendanceSessionRecord(
                id=attendance_session_id,
                status="active",
                scheduled_end_at=current_time,
                closed_at=None,
                cancelled_at=None,
            )
        ),
        clock=lambda: current_time,
    )

    with pytest.raises(AttendanceSessionNotActiveError, match="already ended"):
        await service.create_static_qr_session(FakePool(), attendance_session_id, 300)


@pytest.mark.asyncio
async def test_create_dynamic_qr_session_creates_batch_without_token_history() -> None:
    current_time = datetime(2026, 8, 6, 10, 0, tzinfo=UTC)
    attendance_session_id = UUID("40000000-0000-0000-0000-000000000001")
    qr_session_id = UUID("50000000-0000-0000-0000-000000000001")
    repository = FakeRepository(
        AttendanceSessionRecord(
            id=attendance_session_id,
            status="active",
            scheduled_end_at=current_time + timedelta(minutes=30),
            closed_at=None,
            cancelled_at=None,
        )
    )
    service = QrSessionService(
        repository=repository,
        clock=lambda: current_time,
        uuid_factory=lambda: qr_session_id,
    )

    result = await service.create_dynamic_qr_session(
        FakePool(),
        attendance_session_id,
        valid_for_seconds=900,
        refresh_interval_seconds=15,
    )

    assert result.qr_session_id == qr_session_id
    assert result.attendance_session_id == attendance_session_id
    assert result.mode == "dynamic"
    assert result.qr_value is None
    assert result.refresh_interval_seconds == 15
    assert result.valid_from == current_time
    assert result.expires_at == current_time + timedelta(minutes=15)
    assert repository.closed_session_id == attendance_session_id
    assert repository.inserted_batch == (
        qr_session_id,
        attendance_session_id,
        "dynamic",
        15,
        current_time,
        current_time + timedelta(minutes=15),
    )
    assert repository.inserted_token is None


@pytest.mark.asyncio
async def test_get_qr_batch_metadata_returns_cached_metadata_on_cache_hit() -> None:
    current_time = datetime(2026, 8, 6, 10, 0, tzinfo=UTC)
    metadata = build_qr_batch_metadata(
        expires_at=current_time + timedelta(minutes=15),
    )
    repository = FakeRepository(None)
    cache = FakeQrBatchCache(cached_metadata=metadata)
    service = QrSessionService(
        repository=repository,
        qr_batch_cache=cache,
        clock=lambda: current_time,
    )

    result = await service.get_qr_batch_metadata(FakePool(), metadata.id)

    assert result == metadata
    assert cache.get_calls == [metadata.id]
    assert repository.fetched_qr_session_id is None


@pytest.mark.asyncio
async def test_get_qr_batch_metadata_cache_miss_falls_back_to_database() -> None:
    current_time = datetime(2026, 8, 6, 10, 0, tzinfo=UTC)
    metadata = build_qr_batch_metadata(
        expires_at=current_time + timedelta(minutes=15),
    )
    repository = FakeRepository(None)
    repository.metadata = metadata
    cache = FakeQrBatchCache()
    service = QrSessionService(
        repository=repository,
        qr_batch_cache=cache,
        clock=lambda: current_time,
    )

    result = await service.get_qr_batch_metadata(FakePool(), metadata.id)

    assert result == metadata
    assert repository.fetched_qr_session_id == metadata.id


@pytest.mark.asyncio
async def test_get_qr_batch_metadata_cache_miss_populates_redis_with_ttl() -> None:
    current_time = datetime(2026, 8, 6, 10, 0, tzinfo=UTC)
    metadata = build_qr_batch_metadata(
        expires_at=current_time + timedelta(seconds=90),
    )
    repository = FakeRepository(None)
    repository.metadata = metadata
    cache = FakeQrBatchCache()
    service = QrSessionService(
        repository=repository,
        qr_batch_cache=cache,
        clock=lambda: current_time,
    )

    result = await service.get_qr_batch_metadata(FakePool(), metadata.id)

    assert result == metadata
    assert cache.set_calls == [(metadata.id, metadata, 90)]


@pytest.mark.asyncio
async def test_get_qr_batch_metadata_redis_failure_falls_back_to_database() -> None:
    current_time = datetime(2026, 8, 6, 10, 0, tzinfo=UTC)
    metadata = build_qr_batch_metadata(
        expires_at=current_time + timedelta(minutes=15),
    )
    repository = FakeRepository(None)
    repository.metadata = metadata
    cache = FakeQrBatchCache(fail_reads=True)
    service = QrSessionService(
        repository=repository,
        qr_batch_cache=cache,
        clock=lambda: current_time,
    )

    result = await service.get_qr_batch_metadata(FakePool(), metadata.id)

    assert result == metadata
    assert repository.fetched_qr_session_id == metadata.id


@pytest.mark.asyncio
async def test_create_dynamic_qr_session_invalidates_replaced_batch_cache() -> None:
    current_time = datetime(2026, 8, 6, 10, 0, tzinfo=UTC)
    attendance_session_id = UUID("40000000-0000-0000-0000-000000000001")
    old_qr_session_id = UUID("50000000-0000-0000-0000-000000000009")
    new_qr_session_id = UUID("50000000-0000-0000-0000-000000000010")
    repository = FakeRepository(
        AttendanceSessionRecord(
            id=attendance_session_id,
            status="active",
            scheduled_end_at=current_time + timedelta(minutes=30),
            closed_at=None,
            cancelled_at=None,
        )
    )
    repository.deactivated_batch_ids = [old_qr_session_id]
    cache = FakeQrBatchCache()
    service = QrSessionService(
        repository=repository,
        qr_batch_cache=cache,
        clock=lambda: current_time,
        uuid_factory=lambda: new_qr_session_id,
    )

    await service.create_dynamic_qr_session(
        FakePool(),
        attendance_session_id,
        valid_for_seconds=900,
        refresh_interval_seconds=15,
    )

    assert cache.delete_calls == [old_qr_session_id]


@pytest.mark.asyncio
async def test_create_dynamic_qr_session_caches_active_dynamic_metadata() -> None:
    current_time = datetime(2026, 8, 6, 10, 0, tzinfo=UTC)
    attendance_session_id = UUID("40000000-0000-0000-0000-000000000001")
    qr_session_id = UUID("50000000-0000-0000-0000-000000000001")
    repository = FakeRepository(
        AttendanceSessionRecord(
            id=attendance_session_id,
            status="active",
            scheduled_end_at=current_time + timedelta(minutes=30),
            closed_at=None,
            cancelled_at=None,
        )
    )
    cache = FakeQrBatchCache()
    service = QrSessionService(
        repository=repository,
        qr_batch_cache=cache,
        clock=lambda: current_time,
        uuid_factory=lambda: qr_session_id,
    )

    await service.create_dynamic_qr_session(
        FakePool(),
        attendance_session_id,
        valid_for_seconds=900,
        refresh_interval_seconds=15,
    )

    assert len(cache.set_calls) == 1
    cached_qr_session_id, metadata, ttl_seconds = cache.set_calls[0]
    assert cached_qr_session_id == qr_session_id
    assert metadata.id == qr_session_id
    assert metadata.attendance_session_id == attendance_session_id
    assert metadata.mode == "dynamic"
    assert metadata.status == "active"
    assert metadata.refresh_interval_seconds == 15
    assert metadata.expires_at == current_time + timedelta(minutes=15)
    assert ttl_seconds == 900


@pytest.mark.asyncio
async def test_get_current_dynamic_qr_session_generates_current_hmac_value() -> None:
    current_time = datetime(2026, 8, 6, 10, 4, 20, tzinfo=UTC)
    qr_session_id = UUID("50000000-0000-0000-0000-000000000001")
    metadata = build_qr_batch_metadata(qr_session_id=qr_session_id)
    service = QrSessionService(
        repository=FakeRepository(None),
        qr_batch_cache=FakeQrBatchCache(cached_metadata=metadata),
        clock=lambda: current_time,
        dynamic_qr_hmac_secret="test-secret",
    )

    result = await service.get_current_dynamic_qr_session(FakePool(), qr_session_id)

    assert result.qr_session_id == qr_session_id
    assert result.sequence == 17
    assert result.qr_value == generate_dynamic_qr_value(
        qr_session_id,
        17,
        "test-secret",
    )
    assert result.valid_from == datetime(2026, 8, 6, 10, 4, 15, tzinfo=UTC)
    assert result.expires_at == datetime(2026, 8, 6, 10, 4, 30, tzinfo=UTC)


@pytest.mark.asyncio
async def test_get_current_dynamic_qr_session_caps_window_at_batch_expiration() -> None:
    current_time = datetime(2026, 8, 6, 10, 14, 55, tzinfo=UTC)
    qr_session_id = UUID("50000000-0000-0000-0000-000000000001")
    metadata = build_qr_batch_metadata(
        qr_session_id=qr_session_id,
        expires_at=datetime(2026, 8, 6, 10, 15, 0, tzinfo=UTC),
    )
    service = QrSessionService(
        repository=FakeRepository(None),
        qr_batch_cache=FakeQrBatchCache(cached_metadata=metadata),
        clock=lambda: current_time,
        dynamic_qr_hmac_secret="test-secret",
    )

    result = await service.get_current_dynamic_qr_session(FakePool(), qr_session_id)

    assert result.sequence == 59
    assert result.valid_from == datetime(2026, 8, 6, 10, 14, 45, tzinfo=UTC)
    assert result.expires_at == datetime(2026, 8, 6, 10, 15, 0, tzinfo=UTC)


@pytest.mark.asyncio
async def test_get_current_dynamic_qr_session_rejects_missing_secret() -> None:
    current_time = datetime(2026, 8, 6, 10, 0, tzinfo=UTC)
    metadata = build_qr_batch_metadata()
    service = QrSessionService(
        repository=FakeRepository(None),
        qr_batch_cache=FakeQrBatchCache(cached_metadata=metadata),
        clock=lambda: current_time,
    )

    with pytest.raises(DynamicQrConfigurationError):
        await service.get_current_dynamic_qr_session(FakePool(), metadata.id)


@pytest.mark.asyncio
async def test_get_current_dynamic_qr_session_rejects_static_qr_session() -> None:
    current_time = datetime(2026, 8, 6, 10, 0, tzinfo=UTC)
    metadata = build_qr_batch_metadata(mode="static", refresh_interval_seconds=None)
    service = QrSessionService(
        repository=FakeRepository(None),
        qr_batch_cache=FakeQrBatchCache(cached_metadata=metadata),
        clock=lambda: current_time,
        dynamic_qr_hmac_secret="test-secret",
    )

    with pytest.raises(DynamicQrSessionUnavailableError, match="not a dynamic"):
        await service.get_current_dynamic_qr_session(FakePool(), metadata.id)


@pytest.mark.asyncio
async def test_get_current_dynamic_qr_session_rejects_closed_batch() -> None:
    current_time = datetime(2026, 8, 6, 10, 0, tzinfo=UTC)
    metadata = build_qr_batch_metadata(
        status="inactive",
        deactivated_at=current_time - timedelta(seconds=1),
    )
    service = QrSessionService(
        repository=FakeRepository(None),
        qr_batch_cache=FakeQrBatchCache(cached_metadata=metadata),
        clock=lambda: current_time,
        dynamic_qr_hmac_secret="test-secret",
    )

    with pytest.raises(DynamicQrSessionUnavailableError, match="closed"):
        await service.get_current_dynamic_qr_session(FakePool(), metadata.id)


@pytest.mark.asyncio
async def test_get_current_dynamic_qr_session_rejects_closed_attendance_session() -> None:
    current_time = datetime(2026, 8, 6, 10, 0, tzinfo=UTC)
    metadata = build_qr_batch_metadata(
        attendance_session_closed_at=current_time - timedelta(seconds=1),
    )
    service = QrSessionService(
        repository=FakeRepository(None),
        qr_batch_cache=FakeQrBatchCache(cached_metadata=metadata),
        clock=lambda: current_time,
        dynamic_qr_hmac_secret="test-secret",
    )

    with pytest.raises(DynamicQrSessionUnavailableError, match="already closed"):
        await service.get_current_dynamic_qr_session(FakePool(), metadata.id)


@pytest.mark.asyncio
async def test_get_current_dynamic_qr_session_rejects_expired_batch() -> None:
    current_time = datetime(2026, 8, 6, 10, 15, tzinfo=UTC)
    metadata = build_qr_batch_metadata(expires_at=current_time)
    service = QrSessionService(
        repository=FakeRepository(None),
        qr_batch_cache=FakeQrBatchCache(cached_metadata=metadata),
        clock=lambda: current_time,
        dynamic_qr_hmac_secret="test-secret",
    )

    with pytest.raises(DynamicQrSessionUnavailableError, match="expired"):
        await service.get_current_dynamic_qr_session(FakePool(), metadata.id)


@pytest.mark.asyncio
async def test_get_current_dynamic_qr_session_rejects_missing_refresh_interval() -> None:
    current_time = datetime(2026, 8, 6, 10, 0, tzinfo=UTC)
    metadata = build_qr_batch_metadata(refresh_interval_seconds=None)
    service = QrSessionService(
        repository=FakeRepository(None),
        qr_batch_cache=FakeQrBatchCache(cached_metadata=metadata),
        clock=lambda: current_time,
        dynamic_qr_hmac_secret="test-secret",
    )

    with pytest.raises(DynamicQrSessionUnavailableError, match="missing"):
        await service.get_current_dynamic_qr_session(FakePool(), metadata.id)


@pytest.mark.asyncio
async def test_get_current_dynamic_qr_session_rejects_missing_qr_session() -> None:
    current_time = datetime(2026, 8, 6, 10, 0, tzinfo=UTC)
    repository = FakeRepository(None)
    service = QrSessionService(
        repository=repository,
        qr_batch_cache=FakeQrBatchCache(),
        clock=lambda: current_time,
        dynamic_qr_hmac_secret="test-secret",
    )

    with pytest.raises(QrSessionNotFoundError):
        await service.get_current_dynamic_qr_session(
            FakePool(),
            UUID("50000000-0000-0000-0000-000000000001"),
        )


@pytest.mark.asyncio
async def test_get_current_dynamic_qr_session_does_not_store_token_records() -> None:
    current_time = datetime(2026, 8, 6, 10, 0, tzinfo=UTC)
    repository = FakeRepository(None)
    metadata = build_qr_batch_metadata()
    service = QrSessionService(
        repository=repository,
        qr_batch_cache=FakeQrBatchCache(cached_metadata=metadata),
        clock=lambda: current_time,
        dynamic_qr_hmac_secret="test-secret",
    )

    await service.get_current_dynamic_qr_session(FakePool(), metadata.id)

    assert repository.inserted_token is None


@pytest.mark.asyncio
async def test_get_current_dynamic_qr_session_does_not_log_or_cache_generated_values(
    caplog: pytest.LogCaptureFixture,
) -> None:
    current_time = datetime(2026, 8, 6, 10, 4, 20, tzinfo=UTC)
    metadata = build_qr_batch_metadata()
    cache = FakeQrBatchCache(cached_metadata=metadata)
    service = QrSessionService(
        repository=FakeRepository(None),
        qr_batch_cache=cache,
        clock=lambda: current_time,
        dynamic_qr_hmac_secret="test-secret",
    )

    result = await service.get_current_dynamic_qr_session(FakePool(), metadata.id)

    assert result.qr_value not in caplog.text
    assert "test-secret" not in caplog.text
    assert cache.set_calls == []


@pytest.mark.asyncio
async def test_stream_dynamic_qr_sessions_sends_current_qr_immediately() -> None:
    current_time = datetime(2026, 8, 6, 10, 0, 8, tzinfo=UTC)
    metadata = build_qr_batch_metadata()
    service = QrSessionService(
        repository=FakeRepository(None),
        qr_batch_cache=FakeQrBatchCache(cached_metadata=metadata),
        clock=lambda: current_time,
        dynamic_qr_hmac_secret="test-secret",
    )

    stream = service.stream_current_dynamic_qr_sessions(FakePool(), metadata.id)
    try:
        result = await anext(stream)
    finally:
        await stream.aclose()

    assert result.sequence == 0
    assert result.qr_value == generate_dynamic_qr_value(metadata.id, 0, "test-secret")
    assert result.valid_from == datetime(2026, 8, 6, 10, 0, tzinfo=UTC)
    assert result.expires_at == datetime(2026, 8, 6, 10, 0, 15, tzinfo=UTC)


@pytest.mark.asyncio
async def test_stream_dynamic_qr_sessions_uses_same_value_as_current_endpoint_logic() -> None:
    current_time = datetime(2026, 8, 6, 10, 4, 20, tzinfo=UTC)
    metadata = build_qr_batch_metadata()
    service = QrSessionService(
        repository=FakeRepository(None),
        qr_batch_cache=FakeQrBatchCache(cached_metadata=metadata),
        clock=lambda: current_time,
        dynamic_qr_hmac_secret="test-secret",
    )

    current_result = await service.get_current_dynamic_qr_session(
        FakePool(),
        metadata.id,
    )
    stream = service.stream_current_dynamic_qr_sessions(
        FakePool(),
        metadata.id,
        initial_qr_session=current_result,
    )
    try:
        streamed_result = await anext(stream)
    finally:
        await stream.aclose()

    assert streamed_result == current_result


@pytest.mark.asyncio
async def test_stream_dynamic_qr_sessions_rotates_to_different_next_value() -> None:
    clock_time = datetime(2026, 8, 6, 10, 0, 8, tzinfo=UTC)
    metadata = build_qr_batch_metadata()
    service = QrSessionService(
        repository=FakeRepository(None),
        qr_batch_cache=FakeQrBatchCache(cached_metadata=metadata),
        clock=lambda: clock_time,
        dynamic_qr_hmac_secret="test-secret",
    )

    async def advance_clock(seconds: float) -> None:
        nonlocal clock_time
        clock_time += timedelta(seconds=seconds)

    stream = service.stream_current_dynamic_qr_sessions(
        FakePool(),
        metadata.id,
        sleep=advance_clock,
    )
    try:
        first_result = await anext(stream)
        second_result = await anext(stream)
    finally:
        await stream.aclose()

    assert first_result.sequence == 0
    assert second_result.sequence == 1
    assert second_result.qr_value != first_result.qr_value


@pytest.mark.asyncio
async def test_stream_dynamic_qr_sessions_waits_until_activated_boundary() -> None:
    clock_time = datetime(2026, 8, 6, 10, 0, 8, 500000, tzinfo=UTC)
    metadata = build_qr_batch_metadata()
    sleep_calls: list[float] = []
    service = QrSessionService(
        repository=FakeRepository(None),
        qr_batch_cache=FakeQrBatchCache(cached_metadata=metadata),
        clock=lambda: clock_time,
        dynamic_qr_hmac_secret="test-secret",
    )

    async def advance_clock(seconds: float) -> None:
        nonlocal clock_time
        sleep_calls.append(seconds)
        clock_time += timedelta(seconds=seconds)

    stream = service.stream_current_dynamic_qr_sessions(
        FakePool(),
        metadata.id,
        sleep=advance_clock,
    )
    try:
        first_result = await anext(stream)
        second_result = await anext(stream)
    finally:
        await stream.aclose()

    assert first_result.sequence == 0
    assert second_result.sequence == 1
    assert sleep_calls == [6.5]


@pytest.mark.asyncio
async def test_stream_dynamic_qr_sessions_stops_when_batch_closes() -> None:
    clock_time = datetime(2026, 8, 6, 10, 0, 8, tzinfo=UTC)
    metadata = build_qr_batch_metadata()
    cache = FakeQrBatchCache(cached_metadata=metadata)
    service = QrSessionService(
        repository=FakeRepository(None),
        qr_batch_cache=cache,
        clock=lambda: clock_time,
        dynamic_qr_hmac_secret="test-secret",
    )

    async def close_batch_after_wait(seconds: float) -> None:
        nonlocal clock_time
        clock_time += timedelta(seconds=seconds)
        cache.cached_metadata = build_qr_batch_metadata(
            status="inactive",
            deactivated_at=clock_time,
        )

    stream = service.stream_current_dynamic_qr_sessions(
        FakePool(),
        metadata.id,
        sleep=close_batch_after_wait,
    )
    try:
        first_result = await anext(stream)
        with pytest.raises(StopAsyncIteration):
            await anext(stream)
    finally:
        await stream.aclose()

    assert first_result.sequence == 0


@pytest.mark.asyncio
async def test_stream_dynamic_qr_sessions_stops_cleanly_on_client_disconnect() -> None:
    metadata = build_qr_batch_metadata()
    disconnect_checks = iter([False, True])
    sleep_calls: list[float] = []
    service = QrSessionService(
        repository=FakeRepository(None),
        qr_batch_cache=FakeQrBatchCache(cached_metadata=metadata),
        clock=lambda: datetime(2026, 8, 6, 10, 0, 8, tzinfo=UTC),
        dynamic_qr_hmac_secret="test-secret",
    )

    async def is_disconnected() -> bool:
        return next(disconnect_checks)

    async def track_sleep(seconds: float) -> None:
        sleep_calls.append(seconds)

    stream = service.stream_current_dynamic_qr_sessions(
        FakePool(),
        metadata.id,
        is_disconnected=is_disconnected,
        sleep=track_sleep,
    )
    try:
        first_result = await anext(stream)
        with pytest.raises(StopAsyncIteration):
            await anext(stream)
    finally:
        await stream.aclose()

    assert first_result.sequence == 0
    assert sleep_calls == []


@pytest.mark.asyncio
async def test_stream_dynamic_qr_sessions_does_not_create_tokens_or_cache_qr_values() -> None:
    metadata = build_qr_batch_metadata()
    repository = FakeRepository(None)
    cache = FakeQrBatchCache(cached_metadata=metadata)
    service = QrSessionService(
        repository=repository,
        qr_batch_cache=cache,
        clock=lambda: datetime(2026, 8, 6, 10, 0, 8, tzinfo=UTC),
        dynamic_qr_hmac_secret="test-secret",
    )

    stream = service.stream_current_dynamic_qr_sessions(FakePool(), metadata.id)
    try:
        result = await anext(stream)
    finally:
        await stream.aclose()

    assert result.qr_value
    assert repository.inserted_token is None
    assert cache.set_calls == []


@pytest.mark.asyncio
async def test_verify_qr_session_accepts_correct_qr_value() -> None:
    current_time = datetime(2026, 8, 6, 10, 0, tzinfo=UTC)
    qr_session_id = UUID("50000000-0000-0000-0000-000000000001")
    repository = FakeVerificationRepository(
        build_qr_verification_record(
            qr_session_id=qr_session_id,
            token_hash=sha256("raw-test-token".encode("utf-8")).hexdigest(),
            token_valid_from=current_time - timedelta(minutes=1),
            token_expires_at=current_time + timedelta(minutes=5),
        )
    )
    service = QrSessionService(repository=repository, clock=lambda: current_time)

    result = await service.verify_qr_session(
        FakePool(),
        qr_session_id,
        "raw-test-token",
    )

    assert result.qr_session_id == qr_session_id
    assert result.status == "accepted"
    assert result.verified_at == current_time


@pytest.mark.asyncio
async def test_verify_qr_session_rejects_wrong_qr_value() -> None:
    current_time = datetime(2026, 8, 6, 10, 0, tzinfo=UTC)
    qr_session_id = UUID("50000000-0000-0000-0000-000000000001")
    service = QrSessionService(
        repository=FakeVerificationRepository(
            build_qr_verification_record(
                qr_session_id=qr_session_id,
                token_hash=sha256("correct-token".encode("utf-8")).hexdigest(),
                token_valid_from=current_time - timedelta(minutes=1),
                token_expires_at=current_time + timedelta(minutes=5),
            )
        ),
        clock=lambda: current_time,
    )

    result = await service.verify_qr_session(FakePool(), qr_session_id, "wrong-token")

    assert result.status == "invalid"


@pytest.mark.asyncio
async def test_verify_qr_session_returns_expired_for_expired_token() -> None:
    current_time = datetime(2026, 8, 6, 10, 0, tzinfo=UTC)
    qr_session_id = UUID("50000000-0000-0000-0000-000000000001")
    service = QrSessionService(
        repository=FakeVerificationRepository(
            build_qr_verification_record(
                qr_session_id=qr_session_id,
                token_hash=sha256("raw-test-token".encode("utf-8")).hexdigest(),
                token_valid_from=current_time - timedelta(minutes=10),
                token_expires_at=current_time,
            )
        ),
        clock=lambda: current_time,
    )

    result = await service.verify_qr_session(FakePool(), qr_session_id, "raw-test-token")

    assert result.status == "expired"


@pytest.mark.asyncio
async def test_verify_qr_session_returns_closed_for_revoked_token() -> None:
    current_time = datetime(2026, 8, 6, 10, 0, tzinfo=UTC)
    qr_session_id = UUID("50000000-0000-0000-0000-000000000001")
    service = QrSessionService(
        repository=FakeVerificationRepository(
            build_qr_verification_record(
                qr_session_id=qr_session_id,
                token_hash=sha256("raw-test-token".encode("utf-8")).hexdigest(),
                token_revoked_at=current_time - timedelta(seconds=1),
                token_valid_from=current_time - timedelta(minutes=1),
                token_expires_at=current_time + timedelta(minutes=5),
            )
        ),
        clock=lambda: current_time,
    )

    result = await service.verify_qr_session(FakePool(), qr_session_id, "raw-test-token")

    assert result.status == "closed"


@pytest.mark.asyncio
async def test_verify_qr_session_returns_closed_for_closed_qr_batch() -> None:
    current_time = datetime(2026, 8, 6, 10, 0, tzinfo=UTC)
    qr_session_id = UUID("50000000-0000-0000-0000-000000000001")
    service = QrSessionService(
        repository=FakeVerificationRepository(
            build_qr_verification_record(
                qr_session_id=qr_session_id,
                batch_status="inactive",
                batch_deactivated_at=current_time - timedelta(seconds=1),
                token_hash=sha256("raw-test-token".encode("utf-8")).hexdigest(),
                token_valid_from=current_time - timedelta(minutes=1),
                token_expires_at=current_time + timedelta(minutes=5),
            )
        ),
        clock=lambda: current_time,
    )

    result = await service.verify_qr_session(FakePool(), qr_session_id, "raw-test-token")

    assert result.status == "closed"


@pytest.mark.parametrize(
    ("session_status", "closed_at", "cancelled_at", "scheduled_end_at"),
    [
        ("closed", None, None, datetime(2026, 8, 6, 11, 0, tzinfo=UTC)),
        (
            "active",
            datetime(2026, 8, 6, 9, 30, tzinfo=UTC),
            None,
            datetime(2026, 8, 6, 11, 0, tzinfo=UTC),
        ),
        (
            "active",
            None,
            datetime(2026, 8, 6, 9, 30, tzinfo=UTC),
            datetime(2026, 8, 6, 11, 0, tzinfo=UTC),
        ),
        ("active", None, None, datetime(2026, 8, 6, 10, 0, tzinfo=UTC)),
    ],
)
@pytest.mark.asyncio
async def test_verify_qr_session_returns_closed_for_closed_cancelled_or_ended_attendance_session(
    session_status: str,
    closed_at: datetime | None,
    cancelled_at: datetime | None,
    scheduled_end_at: datetime,
) -> None:
    current_time = datetime(2026, 8, 6, 10, 0, tzinfo=UTC)
    qr_session_id = UUID("50000000-0000-0000-0000-000000000001")
    service = QrSessionService(
        repository=FakeVerificationRepository(
            build_qr_verification_record(
                qr_session_id=qr_session_id,
                attendance_session_status=session_status,
                attendance_session_closed_at=closed_at,
                attendance_session_cancelled_at=cancelled_at,
                attendance_session_scheduled_end_at=scheduled_end_at,
                token_hash=sha256("raw-test-token".encode("utf-8")).hexdigest(),
                token_valid_from=current_time - timedelta(minutes=1),
                token_expires_at=current_time + timedelta(minutes=5),
            )
        ),
        clock=lambda: current_time,
    )

    result = await service.verify_qr_session(FakePool(), qr_session_id, "raw-test-token")

    assert result.status == "closed"


@pytest.mark.asyncio
async def test_verify_qr_session_returns_invalid_for_missing_qr_session() -> None:
    current_time = datetime(2026, 8, 6, 10, 0, tzinfo=UTC)
    qr_session_id = UUID("50000000-0000-0000-0000-000000000001")
    service = QrSessionService(
        repository=FakeVerificationRepository(None),
        clock=lambda: current_time,
    )

    result = await service.verify_qr_session(FakePool(), qr_session_id, "raw-test-token")

    assert result.status == "invalid"


@pytest.mark.asyncio
async def test_verify_qr_session_hashes_submitted_qr_value_before_comparison() -> None:
    current_time = datetime(2026, 8, 6, 10, 0, tzinfo=UTC)
    qr_session_id = UUID("50000000-0000-0000-0000-000000000001")
    submitted_hash = sha256("raw-test-token".encode("utf-8")).hexdigest()
    service = QrSessionService(
        repository=FakeVerificationRepository(
            build_qr_verification_record(
                qr_session_id=qr_session_id,
                token_hash=submitted_hash,
                token_valid_from=current_time - timedelta(minutes=1),
                token_expires_at=current_time + timedelta(minutes=5),
            )
        ),
        clock=lambda: current_time,
    )

    result = await service.verify_qr_session(FakePool(), qr_session_id, "raw-test-token")

    assert result.status == "accepted"


@pytest.mark.asyncio
async def test_verify_qr_session_does_not_pass_raw_qr_value_to_repository_or_logs(
    caplog: pytest.LogCaptureFixture,
) -> None:
    current_time = datetime(2026, 8, 6, 10, 0, tzinfo=UTC)
    qr_session_id = UUID("50000000-0000-0000-0000-000000000001")
    raw_qr_value = "raw-secret-qr-value"
    repository = FakeVerificationRepository(
        build_qr_verification_record(
            qr_session_id=qr_session_id,
            token_hash=sha256(raw_qr_value.encode("utf-8")).hexdigest(),
            token_valid_from=current_time - timedelta(minutes=1),
            token_expires_at=current_time + timedelta(minutes=5),
        )
    )
    service = QrSessionService(repository=repository, clock=lambda: current_time)

    result = await service.verify_qr_session(FakePool(), qr_session_id, raw_qr_value)

    assert result.status == "accepted"
    assert repository.requested_qr_session_id == qr_session_id
    assert raw_qr_value not in caplog.text


@pytest.mark.asyncio
async def test_verify_dynamic_qr_session_accepts_current_hmac_value() -> None:
    current_time = datetime(2026, 8, 6, 10, 4, 20, tzinfo=UTC)
    qr_session_id = UUID("50000000-0000-0000-0000-000000000001")
    repository = FakeRepository(None)
    repository.metadata = build_qr_batch_metadata(qr_session_id=qr_session_id)
    repository.verification_record = build_qr_verification_record(
        qr_session_id=qr_session_id,
        qr_mode="dynamic",
    )
    service = QrSessionService(
        repository=repository,
        clock=lambda: current_time,
        dynamic_qr_hmac_secret="test-secret",
    )
    qr_value = generate_dynamic_qr_value(qr_session_id, 17, "test-secret")

    result = await service.verify_qr_session(FakePool(), qr_session_id, qr_value)

    assert result.status == "accepted"
    assert result.verified_at == current_time


@pytest.mark.asyncio
async def test_verify_dynamic_qr_session_rejects_wrong_value() -> None:
    current_time = datetime(2026, 8, 6, 10, 4, 20, tzinfo=UTC)
    qr_session_id = UUID("50000000-0000-0000-0000-000000000001")
    repository = FakeRepository(None)
    repository.metadata = build_qr_batch_metadata(qr_session_id=qr_session_id)
    repository.verification_record = build_qr_verification_record(
        qr_session_id=qr_session_id,
        qr_mode="dynamic",
    )
    service = QrSessionService(
        repository=repository,
        clock=lambda: current_time,
        dynamic_qr_hmac_secret="test-secret",
    )

    result = await service.verify_qr_session(FakePool(), qr_session_id, "wrong-value")

    assert result.status == "invalid"


@pytest.mark.asyncio
async def test_verify_dynamic_qr_session_returns_expired_for_expired_batch() -> None:
    current_time = datetime(2026, 8, 6, 10, 15, tzinfo=UTC)
    qr_session_id = UUID("50000000-0000-0000-0000-000000000001")
    repository = FakeRepository(None)
    repository.metadata = build_qr_batch_metadata(
        qr_session_id=qr_session_id,
        expires_at=current_time,
    )
    repository.verification_record = build_qr_verification_record(
        qr_session_id=qr_session_id,
        qr_mode="dynamic",
    )
    service = QrSessionService(
        repository=repository,
        clock=lambda: current_time,
        dynamic_qr_hmac_secret="test-secret",
    )

    result = await service.verify_qr_session(FakePool(), qr_session_id, "any-value")

    assert result.status == "expired"


@pytest.mark.asyncio
async def test_verify_dynamic_qr_session_returns_closed_for_closed_batch() -> None:
    current_time = datetime(2026, 8, 6, 10, 4, 20, tzinfo=UTC)
    qr_session_id = UUID("50000000-0000-0000-0000-000000000001")
    repository = FakeRepository(None)
    repository.metadata = build_qr_batch_metadata(
        qr_session_id=qr_session_id,
        status="inactive",
        deactivated_at=current_time - timedelta(seconds=1),
    )
    repository.verification_record = build_qr_verification_record(
        qr_session_id=qr_session_id,
        qr_mode="dynamic",
    )
    service = QrSessionService(
        repository=repository,
        clock=lambda: current_time,
        dynamic_qr_hmac_secret="test-secret",
    )

    result = await service.verify_qr_session(FakePool(), qr_session_id, "any-value")

    assert result.status == "closed"


@pytest.mark.asyncio
async def test_verify_dynamic_qr_session_does_not_create_tokens_or_cache_qr_values() -> None:
    current_time = datetime(2026, 8, 6, 10, 4, 20, tzinfo=UTC)
    qr_session_id = UUID("50000000-0000-0000-0000-000000000001")
    repository = FakeRepository(None)
    cache = FakeQrBatchCache()
    metadata = build_qr_batch_metadata(qr_session_id=qr_session_id)
    repository.metadata = metadata
    repository.verification_record = build_qr_verification_record(
        qr_session_id=qr_session_id,
        qr_mode="dynamic",
    )
    service = QrSessionService(
        repository=repository,
        qr_batch_cache=cache,
        clock=lambda: current_time,
        dynamic_qr_hmac_secret="test-secret",
    )
    qr_value = generate_dynamic_qr_value(qr_session_id, 17, "test-secret")

    result = await service.verify_qr_session(FakePool(), qr_session_id, qr_value)

    assert result.status == "accepted"
    assert repository.inserted_token is None
    assert all(qr_value != str(call) for call in cache.set_calls)


def build_qr_verification_record(
    *,
    qr_session_id: UUID,
    qr_mode: str = "static",
    batch_status: str = "active",
    batch_deactivated_at: datetime | None = None,
    attendance_session_id: UUID = UUID("40000000-0000-0000-0000-000000000001"),
    attendance_session_status: str = "active",
    attendance_session_scheduled_end_at: datetime = datetime(
        2026,
        8,
        6,
        11,
        0,
        tzinfo=UTC,
    ),
    attendance_session_closed_at: datetime | None = None,
    attendance_session_cancelled_at: datetime | None = None,
    token_hash: str | None = None,
    token_valid_from: datetime | None = None,
    token_expires_at: datetime | None = None,
    token_revoked_at: datetime | None = None,
) -> QrVerificationRecord:
    return QrVerificationRecord(
        qr_session_id=qr_session_id,
        qr_mode=qr_mode,
        refresh_interval_seconds=None,
        batch_status=batch_status,
        batch_deactivated_at=batch_deactivated_at,
        attendance_session_id=attendance_session_id,
        attendance_session_status=attendance_session_status,
        attendance_session_scheduled_end_at=attendance_session_scheduled_end_at,
        attendance_session_closed_at=attendance_session_closed_at,
        attendance_session_cancelled_at=attendance_session_cancelled_at,
        token_hash=token_hash,
        token_valid_from=token_valid_from,
        token_expires_at=token_expires_at,
        token_revoked_at=token_revoked_at,
    )


def build_qr_batch_metadata(
    *,
    qr_session_id: UUID = UUID("50000000-0000-0000-0000-000000000001"),
    attendance_session_id: UUID = UUID("40000000-0000-0000-0000-000000000001"),
    attendance_session_status: str | None = "active",
    attendance_session_scheduled_end_at: datetime | None = datetime(
        2026,
        8,
        6,
        11,
        0,
        tzinfo=UTC,
    ),
    attendance_session_closed_at: datetime | None = None,
    attendance_session_cancelled_at: datetime | None = None,
    mode: str = "dynamic",
    status: str = "active",
    activated_at: datetime = datetime(2026, 8, 6, 10, 0, tzinfo=UTC),
    deactivated_at: datetime | None = None,
    refresh_interval_seconds: int | None = 15,
    expires_at: datetime = datetime(2026, 8, 6, 10, 15, tzinfo=UTC),
) -> QrBatchMetadata:
    return QrBatchMetadata(
        id=qr_session_id,
        attendance_session_id=attendance_session_id,
        attendance_session_status=attendance_session_status,
        attendance_session_scheduled_end_at=attendance_session_scheduled_end_at,
        attendance_session_closed_at=attendance_session_closed_at,
        attendance_session_cancelled_at=attendance_session_cancelled_at,
        mode=mode,
        status=status,
        activated_at=activated_at,
        deactivated_at=deactivated_at,
        refresh_interval_seconds=refresh_interval_seconds,
        expires_at=expires_at,
    )
