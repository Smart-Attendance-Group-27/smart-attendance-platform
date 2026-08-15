from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from secrets import compare_digest, token_urlsafe
from uuid import UUID, uuid4

import asyncpg

from modules.attendance_sessions.qr_session.exception import (
    AttendanceSessionNotActiveError,
    AttendanceSessionNotFoundError,
)
from modules.attendance_sessions.qr_session.cache import QrBatchMetadataCache
from modules.attendance_sessions.qr_session.metadata import QrBatchMetadata
from modules.attendance_sessions.qr_session.repository import (
    ACTIVE_STATUS,
    DYNAMIC_QR_MODE,
    AttendanceSessionRecord,
    QrSessionRepository,
    QrVerificationRecord,
    STATIC_QR_MODE,
)


QR_TOKEN_SEQUENCE_NUMBER = 1
QR_TOKEN_RANDOM_BYTES = 32


@dataclass(frozen=True)
class CreatedQrSession:
    qr_session_id: UUID
    attendance_session_id: UUID
    mode: str
    qr_value: str | None
    refresh_interval_seconds: int | None
    status: str
    valid_from: datetime
    expires_at: datetime


@dataclass(frozen=True)
class VerifiedQrSession:
    qr_session_id: UUID
    status: str
    verified_at: datetime


class QrSessionService:
    def __init__(
        self,
        repository: QrSessionRepository | None = None,
        qr_batch_cache: QrBatchMetadataCache | None = None,
        clock: Callable[[], datetime] | None = None,
        uuid_factory: Callable[[], UUID] | None = None,
        qr_value_generator: Callable[[], str] | None = None,
    ) -> None:
        self._repository = repository or QrSessionRepository()
        self._qr_batch_cache = qr_batch_cache
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

                deactivated_qr_session_ids = (
                    await self._repository.close_existing_active_qr_sessions(
                        connection,
                        attendance_session_id,
                        current_time,
                    )
                )
                await self._repository.insert_qr_batch(
                    connection,
                    qr_session_id,
                    attendance_session_id,
                    STATIC_QR_MODE,
                    None,
                    current_time,
                    actual_expires_at,
                )
                await self._repository.insert_qr_token(
                    connection,
                    qr_token_id,
                    qr_session_id,
                    token_hash,
                    current_time,
                    actual_expires_at,
                )

        await self._delete_cached_qr_batches(deactivated_qr_session_ids)

        return CreatedQrSession(
            qr_session_id=qr_session_id,
            attendance_session_id=attendance_session_id,
            mode=STATIC_QR_MODE,
            qr_value=qr_value,
            refresh_interval_seconds=None,
            status=ACTIVE_STATUS,
            valid_from=current_time,
            expires_at=actual_expires_at,
        )

    async def create_dynamic_qr_session(
        self,
        pool: asyncpg.Pool,
        attendance_session_id: UUID,
        valid_for_seconds: int,
        refresh_interval_seconds: int,
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

                deactivated_qr_session_ids = (
                    await self._repository.close_existing_active_qr_sessions(
                        connection,
                        attendance_session_id,
                        current_time,
                    )
                )
                await self._repository.insert_qr_batch(
                    connection,
                    qr_session_id,
                    attendance_session_id,
                    DYNAMIC_QR_MODE,
                    refresh_interval_seconds,
                    current_time,
                    actual_expires_at,
                )

        await self._delete_cached_qr_batches(deactivated_qr_session_ids)
        await self._set_cached_qr_batch_metadata(
            QrBatchMetadata(
                id=qr_session_id,
                attendance_session_id=attendance_session_id,
                mode=DYNAMIC_QR_MODE,
                status=ACTIVE_STATUS,
                activated_at=current_time,
                deactivated_at=None,
                refresh_interval_seconds=refresh_interval_seconds,
                expires_at=actual_expires_at,
            ),
            current_time,
        )

        return CreatedQrSession(
            qr_session_id=qr_session_id,
            attendance_session_id=attendance_session_id,
            mode=DYNAMIC_QR_MODE,
            qr_value=None,
            refresh_interval_seconds=refresh_interval_seconds,
            status=ACTIVE_STATUS,
            valid_from=current_time,
            expires_at=actual_expires_at,
        )

    async def get_qr_batch_metadata(
        self,
        pool: asyncpg.Pool,
        qr_session_id: UUID,
    ) -> QrBatchMetadata | None:
        current_time = self._ensure_utc(self._clock())

        if self._qr_batch_cache is not None:
            cached_metadata = await self._qr_batch_cache.get_qr_batch_cache(
                qr_session_id,
            )
            if cached_metadata is not None:
                return cached_metadata

        async with pool.acquire() as connection:
            metadata = await self._repository.fetch_qr_batch_metadata(
                connection,
                qr_session_id,
            )

        if metadata is not None:
            await self._set_cached_qr_batch_metadata(metadata, current_time)

        return metadata

    async def verify_qr_session(
        self,
        pool: asyncpg.Pool,
        qr_session_id: UUID,
        qr_value: str,
    ) -> VerifiedQrSession:
        current_time = self._ensure_utc(self._clock())
        submitted_token_hash = self._hash_qr_value(qr_value)

        async with pool.acquire() as connection:
            verification_record = await self._repository.fetch_qr_verification_record(
                connection,
                qr_session_id,
            )

        verification_status = self._classify_qr_verification(
            verification_record,
            submitted_token_hash,
            current_time,
        )

        return VerifiedQrSession(
            qr_session_id=qr_session_id,
            status=verification_status,
            verified_at=current_time,
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

    @staticmethod
    def _classify_qr_verification(
        verification_record: QrVerificationRecord | None,
        submitted_token_hash: str,
        current_time: datetime,
    ) -> str:
        if verification_record is None:
            return "invalid"

        if QrSessionService._verification_record_is_closed(
            verification_record,
            current_time,
        ):
            return "closed"

        if verification_record.token_hash is None:
            return "invalid"

        if verification_record.token_revoked_at is not None:
            return "closed"

        if (
            verification_record.token_valid_from is None
            or verification_record.token_expires_at is None
        ):
            return "invalid"

        token_valid_from = QrSessionService._ensure_utc(
            verification_record.token_valid_from,
        )
        token_expires_at = QrSessionService._ensure_utc(
            verification_record.token_expires_at,
        )

        if current_time < token_valid_from or current_time >= token_expires_at:
            return "expired"

        if not compare_digest(verification_record.token_hash, submitted_token_hash):
            return "invalid"

        return "accepted"

    @staticmethod
    def _verification_record_is_closed(
        verification_record: QrVerificationRecord,
        current_time: datetime,
    ) -> bool:
        if verification_record.attendance_session_id is None:
            return True

        if verification_record.attendance_session_status != ACTIVE_STATUS:
            return True

        if verification_record.attendance_session_closed_at is not None:
            return True

        if verification_record.attendance_session_cancelled_at is not None:
            return True

        if verification_record.attendance_session_scheduled_end_at is None:
            return True

        scheduled_end_at = QrSessionService._ensure_utc(
            verification_record.attendance_session_scheduled_end_at,
        )

        if scheduled_end_at <= current_time:
            return True

        if verification_record.batch_status != ACTIVE_STATUS:
            return True

        return verification_record.batch_deactivated_at is not None

    async def _delete_cached_qr_batches(
        self,
        qr_session_ids: list[UUID],
    ) -> None:
        if self._qr_batch_cache is None:
            return

        for qr_session_id in qr_session_ids:
            await self._qr_batch_cache.delete_qr_batch_cache(qr_session_id)

    async def _set_cached_qr_batch_metadata(
        self,
        metadata: QrBatchMetadata,
        current_time: datetime,
    ) -> None:
        if self._qr_batch_cache is None:
            return

        ttl_seconds = self._calculate_qr_batch_cache_ttl_seconds(
            metadata,
            current_time,
        )

        if ttl_seconds <= 0:
            return

        await self._qr_batch_cache.set_qr_batch_cache(
            metadata.id,
            metadata,
            ttl_seconds,
        )

    @staticmethod
    def _calculate_qr_batch_cache_ttl_seconds(
        metadata: QrBatchMetadata,
        current_time: datetime,
    ) -> int:
        expires_at = QrSessionService._ensure_utc(metadata.expires_at)
        return int((expires_at - current_time).total_seconds())
