from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import UUID

import pytest

from modules.attendance_sessions.qr_session.exception import (
    AttendanceSessionNotActiveError,
    AttendanceSessionNotFoundError,
)
from modules.attendance_sessions.qr_session.repository import AttendanceSessionRecord
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
