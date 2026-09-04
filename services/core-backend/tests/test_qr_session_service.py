from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import UUID

import pytest

from modules.attendance_sessions.qr_session.exception import (
    ActiveStudentProfileNotFoundError,
    AttendanceSessionNotActiveError,
    AttendanceSessionNotFoundError,
    DynamicQrConfigurationError,
    DynamicQrSessionUnavailableError,
    LecturerSessionAccessError,
    QrNotRequiredError,
    QrSessionNotFoundError,
    StudentNotEligibleError,
    VerificationNotStartedError,
)
from modules.attendance_sessions.qr_session.crypto import generate_dynamic_qr_value
from modules.attendance_sessions.qr_session.repository import (
    AttendanceSessionRecord,
    QrVerificationRecord,
)
from modules.attendance_sessions.qr_session.metadata import QrBatchMetadata
from modules.attendance_sessions.qr_session.service import QrSessionService
from modules.attendance_verification.attempt_status import (
    CHECKED_IN_STATUS,
    COMPLETED_STATUS,
    IN_PROGRESS_STATUS,
)
from modules.attendance_verification.geofence.repository import (
    StudentProfileRecord,
    VerificationAttemptRecord,
)

LECTURER_ID = UUID("20000000-0000-0000-0000-000000000002")
STUDENT_USER_ID = UUID("20000000-0000-0000-0000-000000000011")
STUDENT_PROFILE_ID = UUID("23000000-0000-0000-0000-000000000001")


class FakeTransaction:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, exc_type: object, exc: object, traceback: object) -> bool:
        return False


class FakeConnection:
    def __init__(self) -> None:
        self.executed_queries: list[str] = []
        self.executed_args: list[tuple] = []

    def transaction(self) -> FakeTransaction:
        return FakeTransaction()

    async def execute(self, query: str, *args) -> None:
        """Absorbs the write_audit_log() call made inside the same transaction."""
        self.executed_queries.append(query)
        self.executed_args.append(args)


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
        self.inserted_batch: tuple[UUID, UUID, str, int | None, datetime, datetime, UUID] | None = None
        self.inserted_token: tuple[UUID, UUID, str, datetime, datetime] | None = None
        self.deactivated_batch_ids: list[UUID] = []
        self.metadata: QrBatchMetadata | None = None
        self.verification_record: QrVerificationRecord | None = None
        self.fetched_qr_session_id: UUID | None = None
        self.owns_session = True
        self.owns_qr_session = True
        self.qr_token_id_for_batch: UUID | None = None
        self.next_attempt_number = 1
        self.inserted_qr_validation_attempts: list[tuple] = []

    async def lock_attendance_session(
        self,
        connection: FakeConnection,
        session_id: UUID,
    ) -> AttendanceSessionRecord | None:
        return self.session

    async def session_owned_by_lecturer(
        self,
        connection: FakeConnection,
        session_id: UUID,
        lecturer_id: UUID,
    ) -> bool:
        return self.owns_session

    async def qr_batch_owned_by_lecturer(
        self,
        connection: FakeConnection,
        qr_session_id: UUID,
        lecturer_id: UUID,
    ) -> bool:
        return self.owns_qr_session

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
        issued_by: UUID,
    ) -> None:
        self.inserted_batch = (
            qr_session_id,
            attendance_session_id,
            mode,
            refresh_interval_seconds,
            activated_at,
            expires_at,
            issued_by,
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

    async def find_qr_token_id_for_batch(
        self,
        connection: FakeConnection,
        qr_batch_id: UUID,
    ) -> UUID | None:
        return self.qr_token_id_for_batch

    async def next_qr_attempt_number(
        self,
        connection: FakeConnection,
        verification_attempt_id: UUID,
    ) -> int:
        return self.next_attempt_number

    async def insert_qr_validation_attempt(
        self,
        connection: FakeConnection,
        qr_validation_attempt_id: UUID,
        verification_attempt_id: UUID,
        qr_token_id: UUID | None,
        qr_batch_id: UUID,
        attempt_number: int,
        validation_status: str,
        failure_reason: str | None,
        validated_at: datetime,
    ) -> None:
        self.inserted_qr_validation_attempts.append(
            (
                qr_validation_attempt_id,
                verification_attempt_id,
                qr_token_id,
                qr_batch_id,
                attempt_number,
                validation_status,
                failure_reason,
                validated_at,
            )
        )


class FakeVerificationRepository:
    def __init__(self, record: QrVerificationRecord | None) -> None:
        self.record = record
        self.requested_qr_session_id: UUID | None = None
        self.qr_token_id_for_batch: UUID | None = None
        self.next_attempt_number = 1
        self.inserted_qr_validation_attempts: list[tuple] = []

    async def fetch_qr_verification_record(
        self,
        connection: FakeConnection,
        qr_session_id: UUID,
    ) -> QrVerificationRecord | None:
        self.requested_qr_session_id = qr_session_id
        return self.record

    async def find_qr_token_id_for_batch(
        self,
        connection: FakeConnection,
        qr_batch_id: UUID,
    ) -> UUID | None:
        return self.qr_token_id_for_batch

    async def next_qr_attempt_number(
        self,
        connection: FakeConnection,
        verification_attempt_id: UUID,
    ) -> int:
        return self.next_attempt_number

    async def insert_qr_validation_attempt(
        self,
        connection: FakeConnection,
        qr_validation_attempt_id: UUID,
        verification_attempt_id: UUID,
        qr_token_id: UUID | None,
        qr_batch_id: UUID,
        attempt_number: int,
        validation_status: str,
        failure_reason: str | None,
        validated_at: datetime,
    ) -> None:
        self.inserted_qr_validation_attempts.append(
            (
                qr_validation_attempt_id,
                verification_attempt_id,
                qr_token_id,
                qr_batch_id,
                attempt_number,
                validation_status,
                failure_reason,
                validated_at,
            )
        )


_UNSET = object()
_DEFAULT_ATTEMPT = VerificationAttemptRecord(
    id=UUID("70000000-0000-0000-0000-000000000001"),
    status=IN_PROGRESS_STATUS,
    failure_reason=None,
)


class FakeStudentVerificationRepository:
    """Stands in for GeofenceRepository's student-side lookups QR reuses."""

    def __init__(
        self,
        *,
        student: StudentProfileRecord | None = None,
        eligible: bool = True,
        attempt: object = _UNSET,
    ) -> None:
        self.student = (
            student
            if student is not None
            else StudentProfileRecord(id=STUDENT_PROFILE_ID, profile_status="active")
        )
        self.eligible = eligible
        self.attempt = _DEFAULT_ATTEMPT if attempt is _UNSET else attempt
        self.requested_user_id: UUID | None = None

    async def lock_student_profile_for_user(
        self,
        connection: FakeConnection,
        user_id: UUID,
    ) -> StudentProfileRecord | None:
        self.requested_user_id = user_id
        return self.student

    async def lock_student_eligibility(
        self,
        connection: FakeConnection,
        session_id: UUID,
        student_id: UUID,
    ) -> bool:
        return self.eligible

    async def find_verification_attempt(
        self,
        connection: FakeConnection,
        session_id: UUID,
        student_id: UUID,
        *,
        lock_for_update: bool = False,
    ) -> VerificationAttemptRecord | None:
        return self.attempt


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
async def test_create_static_qr_session_writes_an_audit_log_entry() -> None:
    current_time = datetime(2026, 8, 6, 10, 0, tzinfo=UTC)
    attendance_session_id = UUID("40000000-0000-0000-0000-000000000001")
    repository = FakeRepository(
        AttendanceSessionRecord(
            id=attendance_session_id,
            status="active",
            scheduled_end_at=current_time + timedelta(minutes=20),
            closed_at=None,
            cancelled_at=None,
        )
    )
    pool = FakePool()
    service = QrSessionService(repository=repository, clock=lambda: current_time)

    await service.create_static_qr_session(pool, attendance_session_id, 300, LECTURER_ID)

    audit_query = pool.connection.executed_queries[0]
    audit_args = pool.connection.executed_args[0]
    assert "audit.audit_logs" in audit_query
    assert audit_args[0] == LECTURER_ID
    assert audit_args[1] == "lecturer"
    assert audit_args[2] == "qr_session.create"
    assert audit_args[3] == "qr_session"


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
        lecturer_id=LECTURER_ID,
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
        LECTURER_ID,
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
            lecturer_id=LECTURER_ID,
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
        await service.create_static_qr_session(FakePool(), attendance_session_id, 300, LECTURER_ID)


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
        lecturer_id=LECTURER_ID,
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
        LECTURER_ID,
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
        expires_at=current_time + timedelta(seconds=45),
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
    assert cache.set_calls == [(metadata.id, metadata, 45)]


@pytest.mark.asyncio
async def test_get_qr_batch_metadata_caps_ttl_so_a_closed_session_cannot_stay_cached_long() -> None:
    current_time = datetime(2026, 8, 6, 10, 0, tzinfo=UTC)
    metadata = build_qr_batch_metadata(
        expires_at=current_time + timedelta(hours=24),
    )
    repository = FakeRepository(None)
    repository.metadata = metadata
    cache = FakeQrBatchCache()
    service = QrSessionService(
        repository=repository,
        qr_batch_cache=cache,
        clock=lambda: current_time,
    )

    await service.get_qr_batch_metadata(FakePool(), metadata.id)

    assert cache.set_calls == [(metadata.id, metadata, 60)]


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
        lecturer_id=LECTURER_ID,
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
        lecturer_id=LECTURER_ID,
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
    # Capped well below the batch's own 900s validity — see
    # MAX_QR_BATCH_CACHE_TTL_SECONDS in service.py.
    assert ttl_seconds == 60


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
    service = QrSessionService(repository=repository, clock=lambda: current_time, verification_repository=FakeStudentVerificationRepository())

    result = await service.verify_qr_session(
        FakePool(),
        qr_session_id,
        "raw-test-token",
        STUDENT_USER_ID,
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
        verification_repository=FakeStudentVerificationRepository(),
    )

    result = await service.verify_qr_session(FakePool(), qr_session_id, "wrong-token", STUDENT_USER_ID)

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
        verification_repository=FakeStudentVerificationRepository(),
    )

    result = await service.verify_qr_session(FakePool(), qr_session_id, "raw-test-token", STUDENT_USER_ID)

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
        verification_repository=FakeStudentVerificationRepository(),
    )

    result = await service.verify_qr_session(FakePool(), qr_session_id, "raw-test-token", STUDENT_USER_ID)

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
        verification_repository=FakeStudentVerificationRepository(),
    )

    result = await service.verify_qr_session(FakePool(), qr_session_id, "raw-test-token", STUDENT_USER_ID)

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
        verification_repository=FakeStudentVerificationRepository(),
    )

    result = await service.verify_qr_session(FakePool(), qr_session_id, "raw-test-token", STUDENT_USER_ID)

    assert result.status == "closed"


@pytest.mark.asyncio
async def test_verify_qr_session_raises_not_found_for_missing_qr_session() -> None:
    current_time = datetime(2026, 8, 6, 10, 0, tzinfo=UTC)
    qr_session_id = UUID("50000000-0000-0000-0000-000000000001")
    service = QrSessionService(
        repository=FakeVerificationRepository(None),
        clock=lambda: current_time,
        verification_repository=FakeStudentVerificationRepository(),
    )

    with pytest.raises(QrSessionNotFoundError):
        await service.verify_qr_session(FakePool(), qr_session_id, "raw-test-token", STUDENT_USER_ID)


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
        verification_repository=FakeStudentVerificationRepository(),
    )

    result = await service.verify_qr_session(FakePool(), qr_session_id, "raw-test-token", STUDENT_USER_ID)

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
    service = QrSessionService(repository=repository, clock=lambda: current_time, verification_repository=FakeStudentVerificationRepository())

    result = await service.verify_qr_session(FakePool(), qr_session_id, raw_qr_value, STUDENT_USER_ID)

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
        verification_repository=FakeStudentVerificationRepository(),
        dynamic_qr_hmac_secret="test-secret",
    )
    qr_value = generate_dynamic_qr_value(qr_session_id, 17, "test-secret")

    result = await service.verify_qr_session(FakePool(), qr_session_id, qr_value, STUDENT_USER_ID)

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
        verification_repository=FakeStudentVerificationRepository(),
        dynamic_qr_hmac_secret="test-secret",
    )

    result = await service.verify_qr_session(FakePool(), qr_session_id, "wrong-value", STUDENT_USER_ID)

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
        verification_repository=FakeStudentVerificationRepository(),
        dynamic_qr_hmac_secret="test-secret",
    )

    result = await service.verify_qr_session(FakePool(), qr_session_id, "any-value", STUDENT_USER_ID)

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
        verification_repository=FakeStudentVerificationRepository(),
        dynamic_qr_hmac_secret="test-secret",
    )

    result = await service.verify_qr_session(FakePool(), qr_session_id, "any-value", STUDENT_USER_ID)

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
        verification_repository=FakeStudentVerificationRepository(),
        dynamic_qr_hmac_secret="test-secret",
    )
    qr_value = generate_dynamic_qr_value(qr_session_id, 17, "test-secret")

    result = await service.verify_qr_session(FakePool(), qr_session_id, qr_value, STUDENT_USER_ID)

    assert result.status == "accepted"
    assert repository.inserted_token is None
    assert all(qr_value != str(call) for call in cache.set_calls)


@pytest.mark.asyncio
async def test_create_static_qr_session_rejects_lecturer_who_does_not_own_session() -> None:
    current_time = datetime(2026, 8, 6, 10, 0, tzinfo=UTC)
    attendance_session_id = UUID("40000000-0000-0000-0000-000000000001")
    repository = FakeRepository(
        AttendanceSessionRecord(
            id=attendance_session_id,
            status="active",
            scheduled_end_at=current_time + timedelta(minutes=20),
            closed_at=None,
            cancelled_at=None,
        )
    )
    repository.owns_session = False
    service = QrSessionService(repository=repository, clock=lambda: current_time)

    with pytest.raises(LecturerSessionAccessError):
        await service.create_static_qr_session(FakePool(), attendance_session_id, 300, LECTURER_ID)


@pytest.mark.asyncio
async def test_create_static_qr_session_rejects_session_without_qr_enabled() -> None:
    current_time = datetime(2026, 8, 6, 10, 0, tzinfo=UTC)
    attendance_session_id = UUID("40000000-0000-0000-0000-000000000001")
    repository = FakeRepository(
        AttendanceSessionRecord(
            id=attendance_session_id,
            status="active",
            scheduled_end_at=current_time + timedelta(minutes=20),
            closed_at=None,
            cancelled_at=None,
            requires_qr=False,
        )
    )
    service = QrSessionService(repository=repository, clock=lambda: current_time)

    with pytest.raises(QrNotRequiredError):
        await service.create_static_qr_session(FakePool(), attendance_session_id, 300, LECTURER_ID)


@pytest.mark.asyncio
async def test_assert_lecturer_owns_qr_session_rejects_non_owner() -> None:
    repository = FakeRepository(None)
    repository.owns_qr_session = False
    service = QrSessionService(repository=repository)

    with pytest.raises(LecturerSessionAccessError):
        await service.assert_lecturer_owns_qr_session(
            FakePool(),
            UUID("50000000-0000-0000-0000-000000000001"),
            LECTURER_ID,
        )


@pytest.mark.asyncio
async def test_assert_lecturer_owns_qr_session_allows_owner() -> None:
    repository = FakeRepository(None)
    service = QrSessionService(repository=repository)

    await service.assert_lecturer_owns_qr_session(
        FakePool(),
        UUID("50000000-0000-0000-0000-000000000001"),
        LECTURER_ID,
    )


@pytest.mark.asyncio
async def test_verify_qr_session_rejects_inactive_student_profile() -> None:
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
    service = QrSessionService(
        repository=repository,
        clock=lambda: current_time,
        verification_repository=FakeStudentVerificationRepository(
            student=StudentProfileRecord(id=STUDENT_PROFILE_ID, profile_status="archived"),
        ),
    )

    with pytest.raises(ActiveStudentProfileNotFoundError):
        await service.verify_qr_session(FakePool(), qr_session_id, "raw-test-token", STUDENT_USER_ID)


@pytest.mark.asyncio
async def test_verify_qr_session_rejects_ineligible_student() -> None:
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
    service = QrSessionService(
        repository=repository,
        clock=lambda: current_time,
        verification_repository=FakeStudentVerificationRepository(eligible=False),
    )

    with pytest.raises(StudentNotEligibleError):
        await service.verify_qr_session(FakePool(), qr_session_id, "raw-test-token", STUDENT_USER_ID)


@pytest.mark.asyncio
async def test_verify_qr_session_rejects_when_verification_not_started() -> None:
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
    service = QrSessionService(
        repository=repository,
        clock=lambda: current_time,
        verification_repository=FakeStudentVerificationRepository(attempt=None),
    )

    with pytest.raises(VerificationNotStartedError):
        await service.verify_qr_session(FakePool(), qr_session_id, "raw-test-token", STUDENT_USER_ID)


@pytest.mark.asyncio
async def test_verify_qr_session_returns_closed_when_attempt_already_terminal() -> None:
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
    service = QrSessionService(
        repository=repository,
        clock=lambda: current_time,
        verification_repository=FakeStudentVerificationRepository(
            attempt=VerificationAttemptRecord(
                id=UUID("70000000-0000-0000-0000-000000000001"),
                status="failed",
                failure_reason="OUTSIDE_GEOFENCE",
            ),
        ),
    )

    result = await service.verify_qr_session(FakePool(), qr_session_id, "raw-test-token", STUDENT_USER_ID)

    assert result.status == "closed"


@pytest.mark.asyncio
async def test_verify_qr_session_accepts_a_checked_in_student() -> None:
    """A mid-lecture QR window is aimed at students who already checked in.

    Treating checked_in as a closed attempt would reject every scan the
    feature exists to accept.
    """
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
    service = QrSessionService(
        repository=repository,
        clock=lambda: current_time,
        verification_repository=FakeStudentVerificationRepository(
            attempt=VerificationAttemptRecord(
                id=UUID("70000000-0000-0000-0000-000000000001"),
                status=CHECKED_IN_STATUS,
                failure_reason=None,
            ),
        ),
    )

    result = await service.verify_qr_session(
        FakePool(), qr_session_id, "raw-test-token", STUDENT_USER_ID
    )

    assert result.status == "accepted"


@pytest.mark.asyncio
async def test_verify_qr_session_returns_closed_for_a_finalized_attempt() -> None:
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
    service = QrSessionService(
        repository=repository,
        clock=lambda: current_time,
        verification_repository=FakeStudentVerificationRepository(
            attempt=VerificationAttemptRecord(
                id=UUID("70000000-0000-0000-0000-000000000001"),
                status=COMPLETED_STATUS,
                failure_reason=None,
            ),
        ),
    )

    result = await service.verify_qr_session(
        FakePool(), qr_session_id, "raw-test-token", STUDENT_USER_ID
    )

    assert result.status == "closed"


@pytest.mark.asyncio
async def test_verify_qr_session_records_the_window_for_dynamic_qr() -> None:
    """Dynamic QR persists no token row, so qr_batch_id is the only link
    back to the window a scan satisfied."""
    current_time = datetime(2026, 8, 6, 10, 4, 20, tzinfo=UTC)
    qr_session_id = UUID("50000000-0000-0000-0000-000000000001")
    attempt_id = UUID("70000000-0000-0000-0000-000000000001")
    repository = FakeRepository(None)
    repository.metadata = build_qr_batch_metadata(qr_session_id=qr_session_id)
    repository.verification_record = build_qr_verification_record(
        qr_session_id=qr_session_id,
        qr_mode="dynamic",
    )
    service = QrSessionService(
        repository=repository,
        clock=lambda: current_time,
        uuid_factory=lambda: UUID("80000000-0000-0000-0000-000000000001"),
        dynamic_qr_hmac_secret="test-secret",
        verification_repository=FakeStudentVerificationRepository(
            attempt=VerificationAttemptRecord(
                id=attempt_id, status=CHECKED_IN_STATUS, failure_reason=None
            ),
        ),
    )
    qr_value = generate_dynamic_qr_value(qr_session_id, 17, "test-secret")

    result = await service.verify_qr_session(
        FakePool(), qr_session_id, qr_value, STUDENT_USER_ID
    )

    assert result.status == "accepted"
    recorded = repository.inserted_qr_validation_attempts[0]
    assert recorded[2] is None, "dynamic QR has no token row"
    assert recorded[3] == qr_session_id, "the window must still be recorded"


@pytest.mark.asyncio
async def test_verify_qr_session_persists_a_qr_validation_attempt() -> None:
    current_time = datetime(2026, 8, 6, 10, 0, tzinfo=UTC)
    qr_session_id = UUID("50000000-0000-0000-0000-000000000001")
    qr_token_id = UUID("60000000-0000-0000-0000-000000000001")
    attempt_id = UUID("70000000-0000-0000-0000-000000000001")
    repository = FakeVerificationRepository(
        build_qr_verification_record(
            qr_session_id=qr_session_id,
            token_hash=sha256("raw-test-token".encode("utf-8")).hexdigest(),
            token_valid_from=current_time - timedelta(minutes=1),
            token_expires_at=current_time + timedelta(minutes=5),
        )
    )
    repository.qr_token_id_for_batch = qr_token_id
    repository.next_attempt_number = 3
    service = QrSessionService(
        repository=repository,
        clock=lambda: current_time,
        uuid_factory=lambda: UUID("80000000-0000-0000-0000-000000000001"),
        verification_repository=FakeStudentVerificationRepository(
            attempt=VerificationAttemptRecord(id=attempt_id, status=IN_PROGRESS_STATUS, failure_reason=None),
        ),
    )

    await service.verify_qr_session(FakePool(), qr_session_id, "raw-test-token", STUDENT_USER_ID)

    assert repository.inserted_qr_validation_attempts == [
        (
            UUID("80000000-0000-0000-0000-000000000001"),
            attempt_id,
            qr_token_id,
            # The window this scan was made against, so final attendance can
            # tell one lecturer QR window from another.
            qr_session_id,
            3,
            "accepted",
            None,
            current_time,
        )
    ]


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
