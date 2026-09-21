from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

import asyncpg

from modules.attendance_verification.attendance_state import AttendanceRecordSource


@dataclass(frozen=True)
class SessionForManualAttendance:
    id: UUID
    activated_at: datetime | None
    cancelled_at: datetime | None


@dataclass(frozen=True)
class ExistingAttendanceRecord:
    attendance_status: str | None
    record_source: str | None


class ManualAttendanceRepository:
    async def find_session_for_lecturer(
        self,
        connection: asyncpg.Connection,
        session_id: UUID,
        lecturer_id: UUID,
    ) -> SessionForManualAttendance | None:
        # FOR SHARE: a concurrent close or cancel takes FOR UPDATE on the
        # session, so it waits for this write instead of racing it.
        row = await connection.fetchrow(
            """
            SELECT session.id, session.activated_at, session.cancelled_at
            FROM attendance_session.sessions AS session
            JOIN academic.course_offerings AS offering
                ON offering.id = session.course_offering_id
            JOIN academic.course_lecturers AS assignment
                ON assignment.course_offering_id = offering.id
            WHERE session.id = $1 AND assignment.lecturer_id = $2
            FOR SHARE OF session
            """,
            session_id,
            lecturer_id,
        )
        if row is None:
            return None
        return SessionForManualAttendance(
            id=row["id"],
            activated_at=row["activated_at"],
            cancelled_at=row["cancelled_at"],
        )

    async def find_roster_student_user_id(
        self,
        connection: asyncpg.Connection,
        session_id: UUID,
        student_id: UUID,
    ) -> UUID | None:
        """The student's account id if they are on the roster, else ``None``."""

        return await connection.fetchval(
            """
            SELECT student.user_id
            FROM attendance_session.session_students AS roster
            JOIN academic.student_profiles AS student
                ON student.id = roster.student_id
            WHERE roster.session_id = $1 AND roster.student_id = $2
            """,
            session_id,
            student_id,
        )

    async def find_existing_record(
        self,
        connection: asyncpg.Connection,
        session_id: UUID,
        student_id: UUID,
    ) -> ExistingAttendanceRecord | None:
        row = await connection.fetchrow(
            """
            SELECT attendance_status, record_source
            FROM attendance_verification.attendance_records
            WHERE session_id = $1 AND student_id = $2
            FOR UPDATE
            """,
            session_id,
            student_id,
        )
        if row is None:
            return None
        return ExistingAttendanceRecord(
            attendance_status=row["attendance_status"],
            record_source=row["record_source"],
        )

    async def upsert_manual_record(
        self,
        connection: asyncpg.Connection,
        *,
        record_id: UUID,
        session_id: UUID,
        student_id: UUID,
        recorded_by: UUID,
        attendance_status: str,
        manual_reason: str,
    ) -> datetime:
        """Writes the manual record over whatever is there and returns its time.

        Unlike finalization, this overwrites an automatic row on purpose: a
        lecturer's decision always wins.
        """

        return await connection.fetchval(
            """
            INSERT INTO attendance_verification.attendance_records (
                id, session_id, student_id, recorded_by,
                attendance_status, record_source, manual_reason,
                created_at, updated_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, now(), now())
            ON CONFLICT (session_id, student_id) DO UPDATE
            SET recorded_by = EXCLUDED.recorded_by,
                attendance_status = EXCLUDED.attendance_status,
                record_source = EXCLUDED.record_source,
                manual_reason = EXCLUDED.manual_reason,
                updated_at = now()
            RETURNING updated_at
            """,
            record_id,
            session_id,
            student_id,
            recorded_by,
            attendance_status,
            AttendanceRecordSource.MANUAL.value,
            manual_reason,
        )
