from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import UUID

import pytest

from modules.attendance_sessions.qr_session.exception import (
    AttendanceSessionNotActiveError,
    AttendanceSessionNotFoundError,
)
from modules.attendance_sessions.qr_session.repository import (
    AttendanceSessionRecord,
    QrVerificationRecord,
)
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
        self.inserted_batch: tuple[UUID, UUID, datetime] | None = None
        self.inserted_token: tuple[UUID, UUID, str, datetime, datetime] | None = None

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
    ) -> None:
        self.closed_session_id = session_id

    async def insert_qr_batch(
        self,
        connection: FakeConnection,
        qr_session_id: UUID,
        attendance_session_id: UUID,
        activated_at: datetime,
    ) -> None:
        self.inserted_batch = (qr_session_id, attendance_session_id, activated_at)

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
    assert result.qr_value == "raw-test-token"
    assert result.valid_from == current_time
    assert result.expires_at == current_time + timedelta(minutes=20)
    assert repository.closed_session_id == attendance_session_id
    assert repository.inserted_batch == (qr_session_id, attendance_session_id, current_time)
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


def build_qr_verification_record(
    *,
    qr_session_id: UUID,
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
