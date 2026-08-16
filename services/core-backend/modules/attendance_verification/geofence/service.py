from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg

from modules.attendance_verification.geofence.exception import (
    ActiveStudentProfileNotFoundError,
    AttendanceSessionNotActiveError,
    AttendanceSessionNotFoundError,
    CheckInClosedError,
    CheckInNotOpenError,
    GeofenceAttemptLimitReachedError,
    GeofenceNotConfiguredError,
    GeofenceNotRequiredError,
    StudentNotEligibleError,
    VerificationAttemptClosedError,
)
from modules.attendance_verification.geofence.policy import GeofenceValidationPolicy
from modules.attendance_verification.geofence.repository import (
    IN_PROGRESS_STATUS,
    AttendanceSessionRecord,
    GeofenceRepository,
    SessionGeofenceRecord,
    StudentProfileRecord,
)
from modules.attendance_verification.geofence.types import (
    GeofenceBoundary,
    GeofenceDecision,
    GeofenceNextStep,
    GeofenceReading,
    GeofenceReason,
    GeofenceValidationResult,
)

ACTIVE_STATUS = "active"


@dataclass(frozen=True)
class RecordedGeofenceAttempt:
    verification_attempt_id: UUID
    attempt_number: int
    result: GeofenceValidationResult


class GeofenceValidationService:
    def __init__(
        self,
        policy: GeofenceValidationPolicy,
        max_attempts: int,
        repository: GeofenceRepository | None = None,
        clock: Callable[[], datetime] | None = None,
        uuid_factory: Callable[[], UUID] | None = None,
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least one")

        self._policy = policy
        self._max_attempts = max_attempts
        self._repository = repository or GeofenceRepository()
        self._clock = clock or self._utc_now
        self._uuid_factory = uuid_factory or uuid4

    async def validate_attempt(
        self,
        pool: asyncpg.Pool,
        user_id: UUID,
        session_id: UUID,
        reading: GeofenceReading,
    ) -> RecordedGeofenceAttempt:
        validated_at = self._as_utc("clock", self._clock())

        async with pool.acquire() as connection:
            async with connection.transaction():
                student = await self._repository.lock_student_profile_for_user(
                    connection,
                    user_id,
                )
                self._validate_student_profile(student)
                assert student is not None

                session = await self._repository.lock_attendance_session(
                    connection,
                    session_id,
                )
                self._validate_session(session, validated_at)
                assert session is not None

                is_eligible = await self._repository.lock_student_eligibility(
                    connection,
                    session_id,
                    student.id,
                )
                if not is_eligible:
                    raise StudentNotEligibleError(
                        "The student is not eligible for this attendance session.",
                    )

                geofence = await self._repository.lock_session_geofence(
                    connection,
                    session_id,
                )
                boundary = self._build_boundary(geofence)

                verification_attempt = (
                    await self._repository.lock_or_create_verification_attempt(
                        connection,
                        self._uuid_factory(),
                        session_id,
                        student.id,
                        validated_at,
                    )
                )
                if verification_attempt.status != IN_PROGRESS_STATUS:
                    if (
                        verification_attempt.failure_reason
                        == GeofenceReason.ATTEMPT_LIMIT_REACHED.value
                    ):
                        raise GeofenceAttemptLimitReachedError(self._max_attempts)
                    raise VerificationAttemptClosedError(
                        "The verification attempt is already complete.",
                    )

                attempt_number = (
                    await self._repository.next_geofence_attempt_number(
                        connection,
                        verification_attempt.id,
                    )
                )
                if attempt_number > self._max_attempts:
                    raise GeofenceAttemptLimitReachedError(self._max_attempts)

                result = self._policy.evaluate(
                    reading,
                    boundary,
                    validated_at=validated_at,
                )
                result = self._finalize_last_retry(result, attempt_number)

                await self._repository.insert_geofence_attempt(
                    connection,
                    self._uuid_factory(),
                    verification_attempt.id,
                    attempt_number,
                    reading.accuracy_m,
                    result,
                    self._as_utc("captured_at", reading.captured_at),
                    validated_at,
                )

                if result.decision is GeofenceDecision.FAILED:
                    assert result.reason is not None
                    await self._repository.mark_verification_attempt_failed(
                        connection,
                        verification_attempt.id,
                        result.reason.value,
                        validated_at,
                    )

        return RecordedGeofenceAttempt(
            verification_attempt_id=verification_attempt.id,
            attempt_number=attempt_number,
            result=result,
        )

    def _finalize_last_retry(
        self,
        result: GeofenceValidationResult,
        attempt_number: int,
    ) -> GeofenceValidationResult:
        if (
            attempt_number != self._max_attempts
            or result.decision is not GeofenceDecision.RETRY_REQUIRED
        ):
            return result

        return GeofenceValidationResult(
            decision=GeofenceDecision.FAILED,
            distance_m=result.distance_m,
            allowed_radius_m=result.allowed_radius_m,
            next_step=GeofenceNextStep.NONE,
            reason=GeofenceReason.ATTEMPT_LIMIT_REACHED,
        )

    @staticmethod
    def _validate_student_profile(student: StudentProfileRecord | None) -> None:
        if student is None or student.profile_status != ACTIVE_STATUS:
            raise ActiveStudentProfileNotFoundError(
                "No active student profile exists for this account.",
            )

    @staticmethod
    def _validate_session(
        session: AttendanceSessionRecord | None,
        validated_at: datetime,
    ) -> None:
        if session is None:
            raise AttendanceSessionNotFoundError(
                "The attendance session was not found.",
            )

        if (
            session.status != ACTIVE_STATUS
            or session.closed_at is not None
            or session.cancelled_at is not None
        ):
            raise AttendanceSessionNotActiveError(
                "The attendance session is not active.",
            )

        if session.check_in_opens_at is None or session.check_in_closes_at is None:
            raise AttendanceSessionNotActiveError(
                "The attendance session has no check-in window.",
            )

        check_in_opens_at = GeofenceValidationService._as_utc(
            "check_in_opens_at",
            session.check_in_opens_at,
        )
        check_in_closes_at = GeofenceValidationService._as_utc(
            "check_in_closes_at",
            session.check_in_closes_at,
        )

        if validated_at < check_in_opens_at:
            raise CheckInNotOpenError("Check-in has not opened yet.")

        if validated_at >= check_in_closes_at:
            raise CheckInClosedError("Check-in is closed.")

        if session.requires_geofence is not True:
            raise GeofenceNotRequiredError(
                "Geofence validation is not required for this session.",
            )

    @staticmethod
    def _build_boundary(
        geofence: SessionGeofenceRecord | None,
    ) -> GeofenceBoundary:
        if geofence is None or any(
            value is None
            for value in (
                geofence.centre_latitude,
                geofence.centre_longitude,
                geofence.radius_m,
                geofence.accuracy_buffer_m,
                geofence.maximum_allowed_accuracy_m,
            )
        ):
            raise GeofenceNotConfiguredError(
                "The attendance session has no complete geofence snapshot.",
            )

        assert geofence.centre_latitude is not None
        assert geofence.centre_longitude is not None
        assert geofence.radius_m is not None
        assert geofence.accuracy_buffer_m is not None
        assert geofence.maximum_allowed_accuracy_m is not None

        return GeofenceBoundary(
            centre_latitude=float(geofence.centre_latitude),
            centre_longitude=float(geofence.centre_longitude),
            radius_m=float(geofence.radius_m),
            accuracy_buffer_m=float(geofence.accuracy_buffer_m),
            maximum_allowed_accuracy_m=float(
                geofence.maximum_allowed_accuracy_m,
            ),
        )

    @staticmethod
    def _utc_now() -> datetime:
        return datetime.now(UTC)

    @staticmethod
    def _as_utc(field_name: str, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(f"{field_name} must include a timezone")
        return value.astimezone(UTC)
