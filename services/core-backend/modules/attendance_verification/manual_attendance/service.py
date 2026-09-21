from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

import asyncpg

from modules.academic.lecturer_profile.exception import LecturerProfileNotFoundError
from modules.academic.lecturer_profile.repository import LecturerProfileRepository
from modules.attendance_verification.attendance_state import (
    AttendanceRecordSource,
    FinalAttendanceStatus,
)
from modules.attendance_verification.manual_attendance.exception import (
    ManualReasonInvalidError,
    SessionCancelledError,
    SessionNotFoundError,
    SessionNotStartedError,
    StudentNotOnRosterError,
)
from modules.attendance_verification.manual_attendance.repository import (
    ManualAttendanceRepository,
)
from modules.audit.repository import write_audit_log
from modules.contracts.announce import announce
from modules.contracts.notifications import NoOpNotificationProducer, NotificationProducer

ACTIVE_PROFILE_STATUS = "active"
ACTOR_TYPE_LECTURER = "lecturer"
AUDIT_ACTION = "attendance.manual_set"
AUDIT_ENTITY_TYPE = "attendance_session"
MIN_REASON_LENGTH = 3
MAX_REASON_LENGTH = 500


@dataclass(frozen=True)
class ManualAttendanceResult:
    session_id: UUID
    student_id: UUID
    status: FinalAttendanceStatus
    reason: str
    recorded_by: UUID
    updated_at: datetime
    source: AttendanceRecordSource = AttendanceRecordSource.MANUAL


class ManualAttendanceService:
    """The one place a lecturer's attendance decision is written.

    The direct endpoint and manual review both go through here, so there is a
    single set of rules for who may set what, and a single audit trail.
    """

    def __init__(
        self,
        repository: ManualAttendanceRepository | None = None,
        lecturer_profile_repository: LecturerProfileRepository | None = None,
        notification_producer: NotificationProducer | None = None,
    ) -> None:
        self._repository = repository or ManualAttendanceRepository()
        self._lecturer_profile_repository = (
            lecturer_profile_repository or LecturerProfileRepository()
        )
        self._notification_producer = notification_producer or NoOpNotificationProducer()

    async def set_status(
        self,
        pool: asyncpg.Pool,
        *,
        lecturer_user_id: UUID,
        session_id: UUID,
        student_id: UUID,
        status: FinalAttendanceStatus,
        reason: str,
    ) -> ManualAttendanceResult:
        async with pool.acquire() as connection, connection.transaction():
            return await self.set_status_in_transaction(
                connection,
                lecturer_user_id=lecturer_user_id,
                session_id=session_id,
                student_id=student_id,
                status=status,
                reason=reason,
            )

    async def set_status_in_transaction(
        self,
        connection: asyncpg.Connection,
        *,
        lecturer_user_id: UUID,
        session_id: UUID,
        student_id: UUID,
        status: FinalAttendanceStatus,
        reason: str,
    ) -> ManualAttendanceResult:
        """Same as ``set_status`` but inside the caller's transaction."""

        reason = reason.strip()
        if not MIN_REASON_LENGTH <= len(reason) <= MAX_REASON_LENGTH:
            raise ManualReasonInvalidError()

        lecturer_id = await self._resolve_active_lecturer_id(connection, lecturer_user_id)

        session = await self._repository.find_session_for_lecturer(
            connection,
            session_id,
            lecturer_id,
        )
        if session is None:
            raise SessionNotFoundError()
        if session.cancelled_at is not None:
            raise SessionCancelledError()
        if session.activated_at is None:
            raise SessionNotStartedError()

        student_user_id = await self._repository.find_roster_student_user_id(
            connection,
            session_id,
            student_id,
        )
        if student_user_id is None:
            raise StudentNotOnRosterError()

        previous = await self._repository.find_existing_record(
            connection,
            session_id,
            student_id,
        )
        updated_at = await self._repository.upsert_manual_record(
            connection,
            record_id=uuid4(),
            session_id=session_id,
            student_id=student_id,
            recorded_by=lecturer_user_id,
            attendance_status=status.value,
            manual_reason=reason,
        )

        await write_audit_log(
            connection,
            actor_user_id=lecturer_user_id,
            actor_type=ACTOR_TYPE_LECTURER,
            action=AUDIT_ACTION,
            entity_type=AUDIT_ENTITY_TYPE,
            entity_id=session_id,
            old_values=(
                {
                    "status": previous.attendance_status,
                    "source": previous.record_source,
                }
                if previous is not None
                else None
            ),
            new_values={
                "status": status.value,
                "source": AttendanceRecordSource.MANUAL.value,
                "reason": reason,
            },
            metadata={"studentId": str(student_id)},
        )

        await announce(
            connection,
            lambda: self._notification_producer.attendance_changed(
                connection,
                session_id=session_id,
                student_user_id=student_user_id,
                status=status,
            ),
            label="attendance_changed",
        )

        return ManualAttendanceResult(
            session_id=session_id,
            student_id=student_id,
            status=status,
            reason=reason,
            recorded_by=lecturer_user_id,
            updated_at=updated_at,
        )

    async def _resolve_active_lecturer_id(
        self,
        connection: asyncpg.Connection,
        user_id: UUID,
    ) -> UUID:
        profile = await self._lecturer_profile_repository.find_by_user_id(connection, user_id)
        if profile is None or profile.profile_status != ACTIVE_PROFILE_STATUS:
            raise LecturerProfileNotFoundError("No active lecturer profile exists for this account.")
        return profile.id


__all__ = ["ManualAttendanceResult", "ManualAttendanceService"]
