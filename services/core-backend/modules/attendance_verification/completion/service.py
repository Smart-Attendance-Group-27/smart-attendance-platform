from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID

import asyncpg

from modules.attendance_verification.completion.exception import (
    ActiveStudentProfileNotFoundError,
    AttendanceSessionNotFoundError,
    AttendanceSessionNotOpenError,
    VerificationNotStartedError,
)
from modules.attendance_verification.completion.repository import (
    CHECKED_IN_STATUS,
    COMPLETED_STATUS,
    FAILED_STATUS,
    IN_PROGRESS_STATUS,
    CompletionRepository,
)

ACTIVE_PROFILE_STATUS = "active"
ACTIVE_SESSION_STATUS = "active"

GEOFENCE_PASSED_STATUS = "passed"
FACE_PASSED_STATUS = "passed"
QR_ACCEPTED_STATUS = "accepted"


class CompletionStatus(StrEnum):
    """Outcome of the start-of-lecture check-in operation.

    CHECKED_IN is provisional: it means the student proved presence at the
    start of the lecture. It is NOT a final attendance status. The final
    present/late/absent decision is made once, when the session is finalized.

    COMPLETED is returned only for an attempt the session finalizer has
    already closed, so a late duplicate call reports the real outcome
    instead of silently re-checking in.
    """

    CHECKED_IN = "checked_in"
    COMPLETED = "completed"
    INCOMPLETE = "incomplete"
    FAILED = "failed"


@dataclass(frozen=True)
class CompletionResult:
    status: CompletionStatus
    verification_attempt_id: UUID
    attendance_status: str | None
    missing_requirements: list[str]
    checked_in_at: datetime | None


class CompletionService:
    """Decides whether a student has completed the start-of-lecture check-in.

    Writes only the provisional CHECKED_IN state on
    attendance_verification.verification_attempts. It deliberately does NOT
    write attendance_verification.attendance_records: that table holds the
    final academic result and belongs to session finalization alone.
    """

    def __init__(self, repository: CompletionRepository | None = None) -> None:
        self._repository = repository or CompletionRepository()

    async def complete_for_user(
        self,
        pool: asyncpg.Pool,
        user_id: UUID,
        session_id: UUID,
    ) -> CompletionResult:
        async with pool.acquire() as connection, connection.transaction():
            student = await self._repository.lock_student_profile_for_user(connection, user_id)
            if student is None or student.profile_status != ACTIVE_PROFILE_STATUS:
                raise ActiveStudentProfileNotFoundError(
                    "No active student profile exists for this account.",
                )

            session = await self._repository.lock_attendance_session(connection, session_id)
            if session is None:
                raise AttendanceSessionNotFoundError("The attendance session was not found.")

            self._validate_session_is_open(session)

            attempt = await self._repository.lock_verification_attempt(
                connection, session_id, student.id
            )
            if attempt is None:
                raise VerificationNotStartedError(
                    "No verification attempt exists yet — complete the geofence "
                    "check first.",
                )

            if attempt.status == FAILED_STATUS:
                return CompletionResult(
                    status=CompletionStatus.FAILED,
                    verification_attempt_id=attempt.id,
                    attendance_status=None,
                    missing_requirements=[],
                    checked_in_at=None,
                )

            if attempt.status == COMPLETED_STATUS:
                # The session was already finalized. Report the final result
                # rather than reopening a decision that has been made.
                existing_status = await self._repository.find_attendance_status(
                    connection, session_id, student.id
                )
                return CompletionResult(
                    status=CompletionStatus.COMPLETED,
                    verification_attempt_id=attempt.id,
                    attendance_status=existing_status,
                    missing_requirements=[],
                    checked_in_at=attempt.checked_in_at,
                )

            if attempt.status == CHECKED_IN_STATUS:
                # Idempotent: repeating the call must not move checked_in_at,
                # because the QR applicability rule is anchored to it.
                return CompletionResult(
                    status=CompletionStatus.CHECKED_IN,
                    verification_attempt_id=attempt.id,
                    attendance_status=None,
                    missing_requirements=[],
                    checked_in_at=attempt.checked_in_at,
                )

            # attempt.status == 'in_progress' from here on.
            missing = await self._find_missing_requirements(connection, session, attempt.id)

            if missing:
                return CompletionResult(
                    status=CompletionStatus.INCOMPLETE,
                    verification_attempt_id=attempt.id,
                    attendance_status=None,
                    missing_requirements=missing,
                    checked_in_at=None,
                )

            checked_in_at = datetime.now(UTC)
            await self._repository.mark_verification_attempt_checked_in(
                connection, attempt.id, checked_in_at
            )

            return CompletionResult(
                status=CompletionStatus.CHECKED_IN,
                verification_attempt_id=attempt.id,
                attendance_status=None,
                missing_requirements=[],
                checked_in_at=checked_in_at,
            )

    async def _find_missing_requirements(
        self,
        connection: asyncpg.Connection,
        session,
        verification_attempt_id: UUID,
    ) -> list[str]:
        missing: list[str] = []

        if session.requires_geofence:
            geofence_status = await self._repository.latest_geofence_status(
                connection, verification_attempt_id
            )
            if geofence_status != GEOFENCE_PASSED_STATUS:
                missing.append("geofence")

        if session.requires_face_verification:
            face_status = await self._repository.latest_face_status(
                connection, verification_attempt_id
            )
            if face_status != FACE_PASSED_STATUS:
                missing.append("face_verification")

        if session.requires_qr:
            qr_status = await self._repository.latest_qr_status(
                connection, verification_attempt_id
            )
            if qr_status != QR_ACCEPTED_STATUS:
                missing.append("qr")

        return missing

    @staticmethod
    def _validate_session_is_open(session) -> None:
        """Rejects check-in against a session the lecturer already ended.

        The geofence step enforces the check-in window before it creates the
        attempt, so the window is not re-checked here — a student who started
        in time should not lose their check-in because the window elapsed
        while the face step was running. Closure is different: it is an
        explicit lecturer action that ends the lecture.
        """
        if session.cancelled_at is not None:
            raise AttendanceSessionNotOpenError("The attendance session was cancelled.")

        if session.closed_at is not None:
            raise AttendanceSessionNotOpenError("The attendance session is already closed.")

        if session.status != ACTIVE_SESSION_STATUS:
            raise AttendanceSessionNotOpenError("The attendance session is not active.")


__all__ = [
    "CompletionResult",
    "CompletionService",
    "CompletionStatus",
    "IN_PROGRESS_STATUS",
]
