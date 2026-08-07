from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from secrets import token_urlsafe
from uuid import UUID, uuid4

import asyncpg

from modules.attendance_sessions.qr_session.exception import (
    AttendanceSessionNotActiveError,
    AttendanceSessionNotFoundError,
)
from modules.attendance_sessions.qr_session.repository import (
    ACTIVE_STATUS,
    AttendanceSessionRecord,
    QrSessionRepository,
)


QR_TOKEN_SEQUENCE_NUMBER = 1
QR_TOKEN_RANDOM_BYTES = 32


@dataclass(frozen=True)
class CreatedQrSession:
    qr_session_id: UUID
    attendance_session_id: UUID
    qr_value: str
    status: str
    valid_from: datetime
    expires_at: datetime


class QrSessionService:
    def __init__(
        self,
        repository: QrSessionRepository | None = None,
        clock: Callable[[], datetime] | None = None,
        uuid_factory: Callable[[], UUID] | None = None,
        qr_value_generator: Callable[[], str] | None = None,
    ) -> None:
        self._repository = repository or QrSessionRepository()
        self._clock = clock or self._utc_now
        self._uuid_factory = uuid_factory or uuid4
        self._qr_value_generator = qr_value_generator or self._generate_qr_value

    async def create_static_qr_session(
        self,
        pool: asyncpg.Pool,
        attendance_session_id: UUID,
        valid_for_seconds: int,
    ) -> CreatedQrSession:
        current_time = self._ensure_utc(self._clock())
        requested_expires_at = current_time + timedelta(seconds=valid_for_seconds)

        async with pool.acquire() as connection:
            async with connection.transaction():
                attendance_session = await self._repository.lock_attendance_session(
                    connection,
                    attendance_session_id,
                )
                self._validate_attendance_session(attendance_session, current_time)

                assert attendance_session is not None
                scheduled_end_at = self._ensure_utc(attendance_session.scheduled_end_at)
                actual_expires_at = min(requested_expires_at, scheduled_end_at)

                qr_session_id = self._uuid_factory()
                qr_token_id = self._uuid_factory()
                qr_value = self._qr_value_generator()
                token_hash = self._hash_qr_value(qr_value)

                await self._repository.close_existing_active_qr_sessions(
                    connection,
                    attendance_session_id,
                    current_time,
                )
                await self._repository.insert_qr_batch(
                    connection,
                    qr_session_id,
                    attendance_session_id,
                    current_time,
                )
                await self._repository.insert_qr_token(
                    connection,
                    qr_token_id,
                    qr_session_id,
                    token_hash,
                    current_time,
                    actual_expires_at,
                )

        return CreatedQrSession(
            qr_session_id=qr_session_id,
            attendance_session_id=attendance_session_id,
            qr_value=qr_value,
            status=ACTIVE_STATUS,
            valid_from=current_time,
            expires_at=actual_expires_at,
        )

    @staticmethod
    def _utc_now() -> datetime:
        return datetime.now(UTC)

    @staticmethod
    def _generate_qr_value() -> str:
        return token_urlsafe(QR_TOKEN_RANDOM_BYTES)

    @staticmethod
    def _hash_qr_value(qr_value: str) -> str:
        return sha256(qr_value.encode("utf-8")).hexdigest()

    @staticmethod
    def _ensure_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    @staticmethod
    def _validate_attendance_session(
        attendance_session: AttendanceSessionRecord | None,
        current_time: datetime,
    ) -> None:
        if attendance_session is None:
            raise AttendanceSessionNotFoundError()

        scheduled_end_at = QrSessionService._ensure_utc(attendance_session.scheduled_end_at)

        if attendance_session.status != ACTIVE_STATUS:
            raise AttendanceSessionNotActiveError("Attendance session is not active.")

        if attendance_session.closed_at is not None:
            raise AttendanceSessionNotActiveError("Attendance session is already closed.")

        if attendance_session.cancelled_at is not None:
            raise AttendanceSessionNotActiveError("Attendance session is cancelled.")

        if scheduled_end_at <= current_time:
            raise AttendanceSessionNotActiveError("Attendance session has already ended.")
