from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID

import asyncpg

from modules.academic.student_profile.exception import StudentProfileNotFoundError
from modules.academic.student_profile.repository import StudentProfileRepository
from modules.attendance_verification.attendance_state import VerificationAttemptStatus

ACTIVE_PROFILE_STATUS = "active"
GEOFENCE_PASSED_STATUS = "passed"
FACE_PASSED_STATUS = "passed"


class SessionState(StrEnum):
    SCHEDULED = "scheduled"
    ACTIVE = "active"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class SessionNotFoundError(Exception):
    """Raised when the session does not exist, or the student is not on its roster."""


@dataclass(frozen=True)
class VerificationState:
    attempt_status: str | None
    failure_reason: str | None
    geofence_status: str | None
    face_status: str | None
    liveness_passed: bool | None


@dataclass(frozen=True)
class InitialCheckInState:
    status: str
    checked_in_at: datetime


@dataclass(frozen=True)
class FinalAttendanceState:
    status: str
    source: str
    decided_at: datetime


@dataclass(frozen=True)
class StudentAttendanceState:
    session_id: UUID
    course_code: str | None
    course_name: str | None
    session_title: str | None
    session_type: str | None
    session_state: SessionState
    scheduled_start_at: datetime
    scheduled_end_at: datetime
    check_in_opens_at: datetime | None
    check_in_closes_at: datetime | None
    late_after_at: datetime | None
    requires_face_verification: bool
    qr_enabled: bool
    can_start_check_in: bool
    verification: VerificationState
    initial_check_in: InitialCheckInState | None
    final_attendance: FinalAttendanceState | None


@dataclass(frozen=True)
class StudentSessionRow:
    id: UUID
    course_code: str | None
    course_name: str | None
    session_title: str | None
    session_type: str | None
    status: str | None
    closed_at: datetime | None
    cancelled_at: datetime | None
    scheduled_start_at: datetime
    scheduled_end_at: datetime
    check_in_opens_at: datetime | None
    check_in_closes_at: datetime | None
    late_after_at: datetime | None
    requires_face_verification: bool
    requires_qr: bool


@dataclass(frozen=True)
class StudentAttemptRow:
    id: UUID
    status: str | None
    failure_reason: str | None
    checked_in_at: datetime | None
    initial_check_in_status: str | None


@dataclass(frozen=True)
class StudentFinalAttendanceRow:
    attendance_status: str
    record_source: str
    updated_at: datetime


def derive_session_state(
    *,
    status: str | None,
    closed_at: datetime | None,
    cancelled_at: datetime | None,
) -> SessionState:
    # status stays 'active' after close today, so closed_at/cancelled_at decide.
    if cancelled_at is not None:
        return SessionState.CANCELLED
    if closed_at is not None:
        return SessionState.CLOSED
    if status == SessionState.ACTIVE.value:
        return SessionState.ACTIVE
    return SessionState.SCHEDULED


def can_start_check_in(
    *,
    session_state: SessionState,
    check_in_opens_at: datetime | None,
    check_in_closes_at: datetime | None,
    now: datetime,
    attempt_status: str | None,
    has_final_attendance: bool,
) -> bool:
    if session_state is not SessionState.ACTIVE:
        return False
    if has_final_attendance:
        return False
    if attempt_status in {
        VerificationAttemptStatus.CHECKED_IN.value,
        VerificationAttemptStatus.FAILED.value,
    }:
        return False
    if check_in_opens_at is None or check_in_closes_at is None:
        return False
    return check_in_opens_at <= now < check_in_closes_at


class StudentAttendanceStateRepository:
    async def find_session_for_student(
        self,
        connection: asyncpg.Connection,
        session_id: UUID,
        student_id: UUID,
    ) -> StudentSessionRow | None:
        row = await connection.fetchrow(
            """
            SELECT
                session.id,
                course.course_code,
                course.course_name,
                session.session_title,
                session.session_type,
                session.status,
                session.closed_at,
                session.cancelled_at,
                session.scheduled_start_at,
                session.scheduled_end_at,
                session.check_in_opens_at,
                session.check_in_closes_at,
                session.late_after_at,
                session.requires_face_verification,
                session.requires_qr
            FROM attendance_session.session_students AS eligible_student
            JOIN attendance_session.sessions AS session
                ON session.id = eligible_student.session_id
            JOIN academic.course_offerings AS offering
                ON offering.id = session.course_offering_id
            JOIN academic.courses AS course
                ON course.id = offering.course_id
            WHERE session.id = $1 AND eligible_student.student_id = $2
            """,
            session_id,
            student_id,
        )
        if row is None:
            return None
        return StudentSessionRow(
            id=row["id"],
            course_code=row["course_code"],
            course_name=row["course_name"],
            session_title=row["session_title"],
            session_type=row["session_type"],
            status=row["status"],
            closed_at=row["closed_at"],
            cancelled_at=row["cancelled_at"],
            scheduled_start_at=row["scheduled_start_at"],
            scheduled_end_at=row["scheduled_end_at"],
            check_in_opens_at=row["check_in_opens_at"],
            check_in_closes_at=row["check_in_closes_at"],
            late_after_at=row["late_after_at"],
            requires_face_verification=bool(row["requires_face_verification"]),
            requires_qr=bool(row["requires_qr"]),
        )

    async def find_verification_attempt(
        self,
        connection: asyncpg.Connection,
        session_id: UUID,
        student_id: UUID,
    ) -> StudentAttemptRow | None:
        row = await connection.fetchrow(
            """
            SELECT id, status, failure_reason, checked_in_at, initial_check_in_status
            FROM attendance_verification.verification_attempts
            WHERE session_id = $1 AND student_id = $2
            """,
            session_id,
            student_id,
        )
        if row is None:
            return None
        return StudentAttemptRow(
            id=row["id"],
            status=row["status"],
            failure_reason=row["failure_reason"],
            checked_in_at=row["checked_in_at"],
            initial_check_in_status=row["initial_check_in_status"],
        )

    async def latest_geofence_status(
        self,
        connection: asyncpg.Connection,
        verification_attempt_id: UUID,
    ) -> str | None:
        return await connection.fetchval(
            """
            SELECT validation_status
            FROM attendance_verification.geofence_validation_attempts
            WHERE verification_attempt_id = $1
            ORDER BY attempt_number DESC
            LIMIT 1
            """,
            verification_attempt_id,
        )

    async def latest_face_status(
        self,
        connection: asyncpg.Connection,
        verification_attempt_id: UUID,
    ) -> tuple[str | None, bool | None]:
        row = await connection.fetchrow(
            """
            SELECT validation_status, liveness_passed
            FROM face_verification.face_validation_attempts
            WHERE verification_attempt_id = $1
            ORDER BY attempt_number DESC
            LIMIT 1
            """,
            verification_attempt_id,
        )
        if row is None:
            return None, None
        return row["validation_status"], row["liveness_passed"]

    async def find_attendance_record(
        self,
        connection: asyncpg.Connection,
        session_id: UUID,
        student_id: UUID,
    ) -> StudentFinalAttendanceRow | None:
        row = await connection.fetchrow(
            """
            SELECT attendance_status, record_source, updated_at
            FROM attendance_verification.attendance_records
            WHERE session_id = $1 AND student_id = $2
            """,
            session_id,
            student_id,
        )
        if row is None:
            return None
        return StudentFinalAttendanceRow(
            attendance_status=row["attendance_status"],
            record_source=row["record_source"],
            updated_at=row["updated_at"],
        )


class StudentAttendanceStateService:
    def __init__(
        self,
        repository: StudentAttendanceStateRepository | None = None,
        student_profile_repository: StudentProfileRepository | None = None,
        clock=None,
    ) -> None:
        self._repository = repository or StudentAttendanceStateRepository()
        self._student_profile_repository = (
            student_profile_repository or StudentProfileRepository()
        )
        self._clock = clock or self._utc_now

    async def get_for_user(
        self,
        pool: asyncpg.Pool,
        user_id: UUID,
        session_id: UUID,
    ) -> StudentAttendanceState:
        now = self._as_utc(self._clock())

        async with pool.acquire() as connection:
            profile = await self._student_profile_repository.find_by_user_id(
                connection,
                user_id,
            )
            if profile is None or profile.profile_status != ACTIVE_PROFILE_STATUS:
                raise StudentProfileNotFoundError()

            session_row = await self._repository.find_session_for_student(
                connection,
                session_id,
                profile.id,
            )
            if session_row is None:
                raise SessionNotFoundError()

            attempt = await self._repository.find_verification_attempt(
                connection,
                session_id,
                profile.id,
            )

            geofence_status: str | None = None
            face_status: str | None = None
            liveness_passed: bool | None = None
            if attempt is not None:
                geofence_status = await self._repository.latest_geofence_status(
                    connection,
                    attempt.id,
                )
                face_status, liveness_passed = await self._repository.latest_face_status(
                    connection,
                    attempt.id,
                )

            attendance_record = await self._repository.find_attendance_record(
                connection,
                session_id,
                profile.id,
            )

        session_state = derive_session_state(
            status=session_row.status,
            closed_at=session_row.closed_at,
            cancelled_at=session_row.cancelled_at,
        )

        initial_check_in = None
        if (
            attempt is not None
            and attempt.checked_in_at is not None
            and attempt.initial_check_in_status is not None
        ):
            initial_check_in = InitialCheckInState(
                status=attempt.initial_check_in_status,
                checked_in_at=attempt.checked_in_at,
            )

        final_attendance = None
        if attendance_record is not None:
            final_attendance = FinalAttendanceState(
                status=attendance_record.attendance_status,
                source=attendance_record.record_source,
                decided_at=attendance_record.updated_at,
            )

        return StudentAttendanceState(
            session_id=session_row.id,
            course_code=session_row.course_code,
            course_name=session_row.course_name,
            session_title=session_row.session_title,
            session_type=session_row.session_type,
            session_state=session_state,
            scheduled_start_at=session_row.scheduled_start_at,
            scheduled_end_at=session_row.scheduled_end_at,
            check_in_opens_at=session_row.check_in_opens_at,
            check_in_closes_at=session_row.check_in_closes_at,
            late_after_at=session_row.late_after_at,
            requires_face_verification=session_row.requires_face_verification,
            qr_enabled=session_row.requires_qr,
            can_start_check_in=can_start_check_in(
                session_state=session_state,
                check_in_opens_at=session_row.check_in_opens_at,
                check_in_closes_at=session_row.check_in_closes_at,
                now=now,
                attempt_status=attempt.status if attempt is not None else None,
                has_final_attendance=attendance_record is not None,
            ),
            verification=VerificationState(
                attempt_status=attempt.status if attempt is not None else None,
                failure_reason=attempt.failure_reason if attempt is not None else None,
                geofence_status=geofence_status,
                face_status=face_status,
                liveness_passed=liveness_passed,
            ),
            initial_check_in=initial_check_in,
            final_attendance=final_attendance,
        )

    @staticmethod
    def _utc_now() -> datetime:
        return datetime.now(UTC)

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("clock must include a timezone")
        return value.astimezone(UTC)


__all__ = [
    "FinalAttendanceState",
    "InitialCheckInState",
    "SessionNotFoundError",
    "SessionState",
    "StudentAttemptRow",
    "StudentAttendanceState",
    "StudentAttendanceStateRepository",
    "StudentAttendanceStateService",
    "StudentFinalAttendanceRow",
    "StudentSessionRow",
    "VerificationState",
    "can_start_check_in",
    "derive_session_state",
]
