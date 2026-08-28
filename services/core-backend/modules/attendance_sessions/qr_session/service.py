import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from secrets import compare_digest, token_urlsafe
from typing import cast
from uuid import UUID, uuid4

import asyncpg

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
from modules.attendance_sessions.qr_session.cache import QrBatchMetadataCache
from modules.attendance_sessions.qr_session.crypto import (
    calculate_dynamic_qr_sequence,
    generate_dynamic_qr_value,
    get_dynamic_qr_window,
)
from modules.attendance_sessions.qr_session.metadata import QrBatchMetadata
from modules.attendance_sessions.qr_session.repository import (
    ACTIVE_STATUS,
    DYNAMIC_QR_MODE,
    AttendanceSessionRecord,
    QrSessionRepository,
    QrVerificationRecord,
    STATIC_QR_MODE,
)
from modules.attendance_verification.geofence.repository import (
    IN_PROGRESS_STATUS,
    GeofenceRepository,
)
from modules.audit.repository import write_audit_log


QR_TOKEN_SEQUENCE_NUMBER = 1
QR_TOKEN_RANDOM_BYTES = 32
SSE_RECONNECT_RETRY_MS = 3000
ACTOR_TYPE_LECTURER = "lecturer"
AUDIT_ENTITY_TYPE = "qr_session"
# Dynamic QR batch metadata (including the attendance session's own
# status/closed_at) is cached with a TTL that would otherwise run all the way
# to the batch's own expiry — up to MAX_QR_VALIDITY_SECONDS (24h). Closing a
# session doesn't invalidate that cache entry, so without a cap, a student
# could keep getting "accepted" QR verifications against a session the
# lecturer already closed, for as long as the stale entry survives. Capping
# the cache TTL bounds that window without adding cross-module invalidation.
MAX_QR_BATCH_CACHE_TTL_SECONDS = 60


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


@dataclass(frozen=True)
class CurrentDynamicQrSession:
    qr_session_id: UUID
    qr_value: str
    sequence: int
    valid_from: datetime
    expires_at: datetime


class QrSessionService:
    # This class is the QR module's business layer. Routes call it, repositories
    # provide data access, and this service decides which domain result
    # ("accepted", "invalid", "expired", "closed") should be returned.
    def __init__(
        self,
        repository: QrSessionRepository | None = None,
        qr_batch_cache: QrBatchMetadataCache | None = None,
        clock: Callable[[], datetime] | None = None,
        uuid_factory: Callable[[], UUID] | None = None,
        qr_value_generator: Callable[[], str] | None = None,
        dynamic_qr_hmac_secret: object | None = None,
        verification_repository: GeofenceRepository | None = None,
    ) -> None:
        self._repository = repository or QrSessionRepository()
        self._qr_batch_cache = qr_batch_cache
        self._clock = clock or self._utc_now
        self._uuid_factory = uuid_factory or uuid4
        self._qr_value_generator = qr_value_generator or self._generate_qr_value
        self._dynamic_qr_hmac_secret = self._normalize_secret(dynamic_qr_hmac_secret)
        # Verification attempts are geofence's table conceptually — reused
        # here rather than duplicated, since QR augments the same attempt
        # geofence starts instead of owning a separate one.
        self._verification_repository = verification_repository or GeofenceRepository()

    async def create_static_qr_session(
        self,
        pool: asyncpg.Pool,
        attendance_session_id: UUID,
        valid_for_seconds: int,
        lecturer_id: UUID,
    ) -> CreatedQrSession:
        current_time = self._ensure_utc(self._clock())
        actual_expires_at = current_time + timedelta(seconds=valid_for_seconds)

        # Creation is transactional because we must close older active QR
        # batches and create the new batch/token as one consistent operation.
        async with pool.acquire() as connection:
            connection = cast(asyncpg.Connection, connection)
            async with connection.transaction():
                attendance_session = await self._repository.fetch_attendance_session(
                    connection,
                    attendance_session_id,
                )

                assert attendance_session is not None
                qr_session_id = self._uuid_factory()
                qr_token_id = self._uuid_factory() 
                qr_value = self._qr_value_generator()
                # Static QR stores only the hash. The raw value is returned
                # once to the lecturer UI for QR rendering and is not persisted.
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
                    lecturer_id,
                )
                await self._repository.insert_qr_token(
                    connection,
                    qr_token_id,
                    qr_session_id,
                    token_hash,
                    current_time,
                    actual_expires_at,
                )

                await write_audit_log(
                    connection,
                    actor_user_id=lecturer_id,
                    actor_type=ACTOR_TYPE_LECTURER,
                    action="qr_session.create",
                    entity_type=AUDIT_ENTITY_TYPE,
                    entity_id=qr_session_id,
                    new_values={
                        "attendanceSessionId": str(attendance_session_id),
                        "mode": STATIC_QR_MODE,
                        "expiresAt": actual_expires_at.isoformat(),
                    },
                )

        await self._delete_cached_qr_batches(deactivated_qr_session_ids)

        # Static QR returns qr_value because the web page must render it as the
        # QR code. Dynamic creation returns None and relies on the SSE stream
        # or internal service generation.
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
        lecturer_id: UUID,
    ) -> CreatedQrSession:
        current_time = self._ensure_utc(self._clock())
        actual_expires_at = current_time + timedelta(seconds=valid_for_seconds)

        # Dynamic QR creates only the batch metadata. Individual QR values are
        # derived later using HMAC, so no rotating token rows are stored.
        async with pool.acquire() as connection:
            connection = cast(asyncpg.Connection, connection)
            async with connection.transaction():

                # get the attendance session details
                attendance_session = await self._repository.fetch_attendance_session(
                    connection,
                    attendance_session_id,
                )

                assert attendance_session is not None
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
                    lecturer_id,
                )

                await write_audit_log(
                    connection,
                    actor_user_id=lecturer_id,
                    actor_type=ACTOR_TYPE_LECTURER,
                    action="qr_session.create",
                    entity_type=AUDIT_ENTITY_TYPE,
                    entity_id=qr_session_id,
                    new_values={
                        "attendanceSessionId": str(attendance_session_id),
                        "mode": DYNAMIC_QR_MODE,
                        "refreshIntervalSeconds": refresh_interval_seconds,
                        "expiresAt": actual_expires_at.isoformat(),
                    },
                )

        await self._delete_cached_qr_batches(deactivated_qr_session_ids)

        #Insert QR metadata into cache for dynamic QR session 
        await self._set_cached_qr_batch_metadata(
            QrBatchMetadata(
                id=qr_session_id,
                attendance_session_id=attendance_session_id,
                attendance_session_status=attendance_session.status,
                attendance_session_scheduled_end_at=attendance_session.scheduled_end_at,
                attendance_session_closed_at=attendance_session.closed_at,
                attendance_session_cancelled_at=attendance_session.cancelled_at,
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



    async def assert_lecturer_owns_qr_session(
        self,
        pool: asyncpg.Pool,
        qr_session_id: UUID,
        lecturer_id: UUID,
    ) -> None:
        async with pool.acquire() as connection:
            connection = cast(asyncpg.Connection, connection)
            owns_qr_session = await self._repository.qr_batch_owned_by_lecturer(
                connection,
                qr_session_id,
                lecturer_id,
            )
        if not owns_qr_session:
            raise LecturerSessionAccessError()

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
                # Redis is a read-through optimization only. Returning here is
                # safe because cache entries expire quickly and DB remains truth.
                return cached_metadata

        # Cache miss/failure path: load from PostgreSQL, then write back with a
        # bounded TTL.
        async with pool.acquire() as connection:
            connection = cast(asyncpg.Connection, connection)
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
        student_user_id: UUID,
    ) -> VerifiedQrSession:
        current_time = self._ensure_utc(self._clock())
        # Hash immediately so the raw QR value is not stored, logged, or passed
        # into static-token database writes.
        submitted_token_hash = self._hash_qr_value(qr_value)

        # First read the QR/session/student state needed to classify the scan.
        # The QR attempt write happens later after classification.
        async with pool.acquire() as connection:
            connection = cast(asyncpg.Connection, connection)
            verification_record = await self._repository.fetch_qr_verification_record(
                connection,
                qr_session_id,
            )

            if verification_record is None or verification_record.attendance_session_id is None:
                raise QrSessionNotFoundError()

            student = await self._verification_repository.lock_student_profile_for_user(
                connection,
                student_user_id,
            )
            if student is None or student.profile_status != ACTIVE_STATUS:
                raise ActiveStudentProfileNotFoundError(
                    "No active student profile exists for this account.",
                )

            is_eligible = await self._verification_repository.lock_student_eligibility(
                connection,
                verification_record.attendance_session_id,
                student.id,
            )
            if not is_eligible:
                raise StudentNotEligibleError(
                    "The student is not eligible for this attendance session.",
                )

            # Not locked: this connection is released before the write step
            # below (see get_qr_batch_metadata's own separate acquire, which
            # classification may call into) rather than held across it, so a
            # lock taken here wouldn't cover the eventual write anyway. The
            # qr_validation_attempts unique index on (verification_attempt_id,
            # attempt_number) is what actually prevents a duplicate number
            # under a race, matching geofence's equivalent tolerance.
            attempt = await self._verification_repository.find_verification_attempt(
                connection,
                verification_record.attendance_session_id,
                student.id,
            )
            if attempt is None:
                raise VerificationNotStartedError(
                    "Verification has not started for this session yet.",
                )

        if verification_record.qr_mode == DYNAMIC_QR_MODE:
            # Dynamic values are generated from the current time window and
            # server-side secret, not read from qr_tokens.
            verification_status = await self._classify_dynamic_qr_verification(
                pool,
                qr_session_id,
                qr_value,
                current_time,
            )
        else:
            # Static values are validated by comparing the submitted hash with
            # the stored token_hash.
            verification_status = self._classify_qr_verification(
                verification_record,
                submitted_token_hash,
                current_time,
            )

        if attempt.status != IN_PROGRESS_STATUS:
            verification_status = "closed"

        # Record that the student attempted QR validation. The raw QR value is
        # intentionally not written here; only the outcome is stored.
        async with pool.acquire() as connection:
            connection = cast(asyncpg.Connection, connection)
            async with connection.transaction():
                qr_token_id = await self._repository.find_qr_token_id_for_batch(
                    connection,
                    qr_session_id,
                )
                attempt_number = await self._repository.next_qr_attempt_number(
                    connection,
                    attempt.id,
                )
                await self._repository.insert_qr_validation_attempt(
                    connection,
                    self._uuid_factory(),
                    attempt.id,
                    qr_token_id,
                    attempt_number,
                    verification_status,
                    None if verification_status == "accepted" else verification_status,
                    current_time,
                )

        return VerifiedQrSession(
            qr_session_id=qr_session_id,
            status=verification_status,
            verified_at=current_time,
        )

    async def get_current_dynamic_qr_session(
        self,
        pool: asyncpg.Pool,
        qr_session_id: UUID,
    ) -> CurrentDynamicQrSession:
        current_time = self._ensure_utc(self._clock())
        secret = self._require_dynamic_qr_hmac_secret()
        metadata = await self.get_qr_batch_metadata(pool, qr_session_id)

        if metadata is None:
            raise QrSessionNotFoundError()

        self._validate_dynamic_qr_metadata(metadata, current_time)

        assert metadata.refresh_interval_seconds is not None
        # The sequence number identifies the active time window. Every device
        # observing the same server time window gets the same expected value.
        sequence = calculate_dynamic_qr_sequence(
            metadata.activated_at,
            metadata.refresh_interval_seconds,
            current_time,
        )
        valid_from, expires_at = get_dynamic_qr_window(
            metadata.activated_at,
            metadata.refresh_interval_seconds,
            sequence,
        )

        batch_expires_at = self._ensure_utc(metadata.expires_at)
        if expires_at > batch_expires_at:
            expires_at = batch_expires_at

        # HMAC makes dynamic QR deterministic for the backend but impossible to
        # predict without DYNAMIC_QR_HMAC_SECRET.
        qr_value = generate_dynamic_qr_value(qr_session_id, sequence, secret)

        return CurrentDynamicQrSession(
            qr_session_id=qr_session_id,
            qr_value=qr_value,
            sequence=sequence,
            valid_from=valid_from,
            expires_at=expires_at,
        )

    async def stream_current_dynamic_qr_sessions(
        self,
        pool: asyncpg.Pool,
        qr_session_id: UUID,
        *,
        initial_qr_session: CurrentDynamicQrSession | None = None,
        is_disconnected: Callable[[], Awaitable[bool]] | None = None,
        sleep: Callable[[float], Awaitable[object]] = asyncio.sleep,
    ) -> AsyncIterator[CurrentDynamicQrSession]:
        current_qr_session = initial_qr_session

        while True:
            if await self._client_is_disconnected(is_disconnected):
                break

            if current_qr_session is None:
                try:
                    current_qr_session = await self.get_current_dynamic_qr_session(
                        pool,
                        qr_session_id,
                    )
                except (QrSessionNotFoundError, DynamicQrSessionUnavailableError):
                    break

            yield current_qr_session

            if await self._client_is_disconnected(is_disconnected):
                break

            # Sleep until the current dynamic window expires, then regenerate
            # and yield the next QR value.
            wait_seconds = self._calculate_dynamic_qr_stream_wait_seconds(
                current_qr_session,
                self._clock(),
            )
            await sleep(wait_seconds)
            current_qr_session = None

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
    def _normalize_secret(secret: object | None) -> str | None:
        if secret is None:
            return None

        get_secret_value = getattr(secret, "get_secret_value", None)
        if callable(get_secret_value):
            secret = get_secret_value()

        if not isinstance(secret, str):
            secret = str(secret)

        stripped_secret = secret.strip()
        if not stripped_secret:
            return None

        return stripped_secret

    def _require_dynamic_qr_hmac_secret(self) -> str:
        if self._dynamic_qr_hmac_secret is None:
            raise DynamicQrConfigurationError(
                "Dynamic QR HMAC secret is not configured.",
            )

        return self._dynamic_qr_hmac_secret

    @staticmethod
    def _ensure_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    @staticmethod
    def _calculate_dynamic_qr_stream_wait_seconds(
        current_qr_session: CurrentDynamicQrSession,
        current_time: datetime,
    ) -> float:
        expires_at = QrSessionService._ensure_utc(current_qr_session.expires_at)
        current_time = QrSessionService._ensure_utc(current_time)
        return max(0.0, (expires_at - current_time).total_seconds())

    @staticmethod
    async def _client_is_disconnected(
        is_disconnected: Callable[[], Awaitable[bool]] | None,
    ) -> bool:
        if is_disconnected is None:
            return False

        return await is_disconnected()

    @staticmethod
    def _classify_qr_verification(
        verification_record: QrVerificationRecord | None,
        submitted_token_hash: str,
        current_time: datetime,
    ) -> str:
        # Static QR classification maps all database/session/token conditions
        # into the mobile-facing domain statuses.
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

        # compare_digest avoids timing-sensitive equality checks and is the
        # final static QR hash comparison.
        if not compare_digest(verification_record.token_hash, submitted_token_hash):
            return "invalid"

        return "accepted"

    async def _classify_dynamic_qr_verification(
        self,
        pool: asyncpg.Pool,
        qr_session_id: UUID,
        submitted_qr_value: str,
        current_time: datetime,
    ) -> str:
        try:
            # Reuse current dynamic QR generation so verification and SSE stream
            # agree on the active QR value for the same time window.
            current_qr_session = await self.get_current_dynamic_qr_session(
                pool,
                qr_session_id,
            )
        except QrSessionNotFoundError:
            return "invalid"
        except DynamicQrConfigurationError:
            raise
        except DynamicQrSessionUnavailableError as error:
            if "expired" in error.message or "ended" in error.message:
                return "expired"
            return "closed"

        if compare_digest(current_qr_session.qr_value, submitted_qr_value):
            return "accepted"

        return "invalid"

    @staticmethod
    def _verification_record_is_closed(
        verification_record: QrVerificationRecord,
        current_time: datetime,
    ) -> bool:
        # Anything that means "students should not be able to verify now" is
        # collapsed to the user-facing "closed" result.
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

    @staticmethod
    def _validate_dynamic_qr_metadata(
        metadata: QrBatchMetadata,
        current_time: datetime,
    ) -> None:
        QrSessionService._validate_dynamic_qr_attendance_session_metadata(
            metadata,
            current_time,
        )

        if metadata.mode != DYNAMIC_QR_MODE:
            raise DynamicQrSessionUnavailableError(
                "QR session is not a dynamic QR session.",
            )

        if metadata.status != ACTIVE_STATUS:
            raise DynamicQrSessionUnavailableError("QR session is closed.")

        if metadata.deactivated_at is not None:
            raise DynamicQrSessionUnavailableError("QR session is closed.")

        if metadata.refresh_interval_seconds is None:
            raise DynamicQrSessionUnavailableError(
                "Dynamic QR refresh interval is missing.",
            )

        if metadata.refresh_interval_seconds <= 0:
            raise DynamicQrSessionUnavailableError(
                "Dynamic QR refresh interval is invalid.",
            )

        activated_at = QrSessionService._ensure_utc(metadata.activated_at)
        expires_at = QrSessionService._ensure_utc(metadata.expires_at)

        if current_time < activated_at:
            raise DynamicQrSessionUnavailableError("QR session is not active yet.")

        if current_time >= expires_at:
            raise DynamicQrSessionUnavailableError("QR session is expired.")

    @staticmethod
    def _validate_dynamic_qr_attendance_session_metadata(
        metadata: QrBatchMetadata,
        current_time: datetime,
    ) -> None:
        if metadata.attendance_session_status != ACTIVE_STATUS:
            raise DynamicQrSessionUnavailableError("Attendance session is not active.")

        if metadata.attendance_session_closed_at is not None:
            raise DynamicQrSessionUnavailableError("Attendance session is already closed.")

        if metadata.attendance_session_cancelled_at is not None:
            raise DynamicQrSessionUnavailableError("Attendance session is cancelled.")

        if metadata.attendance_session_scheduled_end_at is None:
            raise DynamicQrSessionUnavailableError(
                "Attendance session scheduled end is missing.",
            )

        scheduled_end_at = QrSessionService._ensure_utc(
            metadata.attendance_session_scheduled_end_at,
        )

        if scheduled_end_at <= current_time:
            raise DynamicQrSessionUnavailableError("Attendance session has already ended.")

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
        natural_ttl = int((expires_at - current_time).total_seconds())
        # Keep Redis short-lived because session close/cancel can happen before
        # the QR batch's natural expiry.
        return min(natural_ttl, MAX_QR_BATCH_CACHE_TTL_SECONDS)
