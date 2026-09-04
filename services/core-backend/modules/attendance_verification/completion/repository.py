from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

import asyncpg

from modules.attendance_verification.attempt_status import (
    CHECKED_IN_STATUS,
    COMPLETED_STATUS,
    FAILED_STATUS,
    IN_PROGRESS_STATUS,
)

# Re-exported so existing importers of this module keep working.
__all__ = [
    "CHECKED_IN_STATUS",
    "COMPLETED_STATUS",
    "FAILED_STATUS",
    "IN_PROGRESS_STATUS",
    "CompletionRepository",
]

PRESENT_STATUS = "present"
LATE_STATUS = "late"
RECORD_SOURCE_AUTOMATIC = "automatic"


@dataclass(frozen=True)
class StudentProfileRecord:
    id: UUID
    profile_status: str | None


@dataclass(frozen=True)
class AttendanceSessionRecord:
    id: UUID
    status: str | None
    closed_at: datetime | None
    cancelled_at: datetime | None
    late_after_at: datetime | None
    requires_geofence: bool | None
    requires_face_verification: bool | None
    requires_qr: bool | None


@dataclass(frozen=True)
class VerificationAttemptRecord:
    id: UUID
    status: str | None
    started_at: datetime | None
    # When initial check-in completed. NULL until the student passes it.
    # Distinct from started_at, which is when the geofence step began: QR
    # applicability is measured from when check-in *finished*.
    checked_in_at: datetime | None = None


class CompletionRepository:
    async def lock_student_profile_for_user(
        self,
        connection: asyncpg.Connection,
        user_id: UUID,
    ) -> StudentProfileRecord | None:
        row = await connection.fetchrow(
            """
            SELECT id, profile_status
            FROM academic.student_profiles
            WHERE user_id = $1
            FOR SHARE
            """,
            user_id,
        )
        if row is None:
            return None
        return StudentProfileRecord(id=row["id"], profile_status=row["profile_status"])

    async def lock_attendance_session(
        self,
        connection: asyncpg.Connection,
        session_id: UUID,
    ) -> AttendanceSessionRecord | None:
        row = await connection.fetchrow(
            """
            SELECT
                id, status, closed_at, cancelled_at, late_after_at,
                requires_geofence, requires_face_verification, requires_qr
            FROM attendance_session.sessions
            WHERE id = $1
            FOR SHARE
            """,
            session_id,
        )
        if row is None:
            return None
        return AttendanceSessionRecord(
            id=row["id"],
            status=row["status"],
            closed_at=row["closed_at"],
            cancelled_at=row["cancelled_at"],
            late_after_at=row["late_after_at"],
            requires_geofence=row["requires_geofence"],
            requires_face_verification=row["requires_face_verification"],
            requires_qr=row["requires_qr"],
        )

    async def lock_verification_attempt(
        self,
        connection: asyncpg.Connection,
        session_id: UUID,
        student_id: UUID,
    ) -> VerificationAttemptRecord | None:
        row = await connection.fetchrow(
            """
            SELECT id, status, started_at, checked_in_at
            FROM attendance_verification.verification_attempts
            WHERE session_id = $1 AND student_id = $2
            FOR UPDATE
            """,
            session_id,
            student_id,
        )
        if row is None:
            return None
        return VerificationAttemptRecord(
            id=row["id"],
            status=row["status"],
            started_at=row["started_at"],
            checked_in_at=row["checked_in_at"],
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
    ) -> str | None:
        return await connection.fetchval(
            """
            SELECT validation_status
            FROM face_verification.face_validation_attempts
            WHERE verification_attempt_id = $1
            ORDER BY attempt_number DESC
            LIMIT 1
            """,
            verification_attempt_id,
        )

    async def latest_qr_status(
        self,
        connection: asyncpg.Connection,
        verification_attempt_id: UUID,
    ) -> str | None:
        return await connection.fetchval(
            """
            SELECT validation_status
            FROM attendance_verification.qr_validation_attempts
            WHERE verification_attempt_id = $1
            ORDER BY attempt_number DESC
            LIMIT 1
            """,
            verification_attempt_id,
        )

    async def find_attendance_status(
        self,
        connection: asyncpg.Connection,
        session_id: UUID,
        student_id: UUID,
    ) -> str | None:
        return await connection.fetchval(
            """
            SELECT attendance_status
            FROM attendance_verification.attendance_records
            WHERE session_id = $1 AND student_id = $2
            """,
            session_id,
            student_id,
        )

    async def insert_attendance_record(
        self,
        connection: asyncpg.Connection,
        *,
        record_id: UUID,
        session_id: UUID,
        student_id: UUID,
        attendance_status: str,
    ) -> None:
        await connection.execute(
            """
            INSERT INTO attendance_verification.attendance_records (
                id, session_id, student_id, recorded_by,
                attendance_status, record_source, manual_reason, created_at, updated_at
            )
            VALUES ($1, $2, $3, NULL, $4, $5, NULL, now(), now())
            ON CONFLICT (session_id, student_id) DO UPDATE
            SET attendance_status = EXCLUDED.attendance_status,
                record_source = EXCLUDED.record_source,
                updated_at = now()
            """,
            record_id,
            session_id,
            student_id,
            attendance_status,
            RECORD_SOURCE_AUTOMATIC,
        )

    async def mark_verification_attempt_checked_in(
        self,
        connection: asyncpg.Connection,
        verification_attempt_id: UUID,
        checked_in_at: datetime,
    ) -> None:
        """Records the provisional CHECKED_IN state for one attempt.

        completed_at is deliberately left NULL: the attempt is not finished,
        it is only past the start-of-lecture checks. Session finalization is
        what sets completed_at and writes the final attendance record.
        """
        await connection.execute(
            """
            UPDATE attendance_verification.verification_attempts
            SET status = $2, checked_in_at = $3
            WHERE id = $1
            """,
            verification_attempt_id,
            CHECKED_IN_STATUS,
            checked_in_at,
        )

    async def complete_verification_attempt(
        self,
        connection: asyncpg.Connection,
        verification_attempt_id: UUID,
        completed_at: datetime,
    ) -> None:
        await connection.execute(
            """
            UPDATE attendance_verification.verification_attempts
            SET status = $2, completed_at = $3
            WHERE id = $1
            """,
            verification_attempt_id,
            COMPLETED_STATUS,
            completed_at,
        )
