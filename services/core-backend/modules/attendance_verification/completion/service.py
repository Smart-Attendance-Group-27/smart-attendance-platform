from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

import asyncpg

from modules.attendance_verification.completion.exception import (
    ActiveStudentProfileNotFoundError,
    AttendanceSessionNotFoundError,
    VerificationNotStartedError,
)
from modules.attendance_verification.completion.repository import (
    COMPLETED_STATUS,
    FAILED_STATUS,
    IN_PROGRESS_STATUS,
    LATE_STATUS,
    PRESENT_STATUS,
    CompletionRepository,
)

ACTIVE_PROFILE_STATUS = "active"

GEOFENCE_PASSED_STATUS = "passed"
FACE_PASSED_STATUS = "passed"
QR_ACCEPTED_STATUS = "accepted"


class CompletionStatus(StrEnum):
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
                existing_status = await self._repository.find_attendance_status(
                    connection, session_id, student.id
                )
                return CompletionResult(
                    status=CompletionStatus.COMPLETED,
                    verification_attempt_id=attempt.id,
                    attendance_status=existing_status,
                    missing_requirements=[],
                    checked_in_at=attempt.started_at,
                )

            # attempt.status == 'in_progress' from here on.
            missing: list[str] = []

            if session.requires_geofence:
                geofence_status = await self._repository.latest_geofence_status(
                    connection, attempt.id
                )
                if geofence_status != GEOFENCE_PASSED_STATUS:
                    missing.append("geofence")

            if session.requires_face_verification:
                face_status = await self._repository.latest_face_status(connection, attempt.id)
                if face_status != FACE_PASSED_STATUS:
                    missing.append("face_verification")

            if session.requires_qr:
                qr_status = await self._repository.latest_qr_status(connection, attempt.id)
                if qr_status != QR_ACCEPTED_STATUS:
                    missing.append("qr")

            if missing:
                return CompletionResult(
                    status=CompletionStatus.INCOMPLETE,
                    verification_attempt_id=attempt.id,
                    attendance_status=None,
                    missing_requirements=missing,
                    checked_in_at=None,
                )

            completed_at = datetime.now(UTC)
            attendance_status = self._resolve_attendance_status(
                started_at=attempt.started_at,
                late_after_at=session.late_after_at,
                completed_at=completed_at,
            )

            await self._repository.insert_attendance_record(
                connection,
                record_id=uuid4(),
                session_id=session_id,
                student_id=student.id,
                attendance_status=attendance_status,
            )
            await self._repository.complete_verification_attempt(
                connection, attempt.id, completed_at
            )

            return CompletionResult(
                status=CompletionStatus.COMPLETED,
                verification_attempt_id=attempt.id,
                attendance_status=attendance_status,
                missing_requirements=[],
                checked_in_at=attempt.started_at,
            )

    @staticmethod
    def _resolve_attendance_status(
        *,
        started_at: datetime | None,
        late_after_at: datetime | None,
        completed_at: datetime,
    ) -> str:
        # Mirrors the same present/late rule already used for the manual-review
        # approve decision (modules/attendance_verification/manual_review) —
        # late if the student didn't even *start* verifying until after the
        # late threshold.
        reference_time = started_at or completed_at
        if late_after_at is not None and reference_time > late_after_at:
            return LATE_STATUS
        return PRESENT_STATUS


__all__ = [
    "CompletionResult",
    "CompletionService",
    "CompletionStatus",
    "IN_PROGRESS_STATUS",
]
