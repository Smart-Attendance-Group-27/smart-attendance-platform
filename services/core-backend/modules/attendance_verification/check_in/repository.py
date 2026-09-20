"""Every database read and write the initial check-in needs.

All methods take a ``connection`` rather than a pool. Check-in is decided
inside somebody else's transaction — the geofence pass, the face pass, or the
session close that reconciles stragglers — and splitting that across two
connections would let a session close between reading the evidence and writing
the check-in.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

import asyncpg

from modules.attendance_verification.attendance_state import (
    InitialCheckInStatus,
    VerificationAttemptStatus,
)

GEOFENCE_PASSED_STATUS = "passed"
FACE_PASSED_STATUS = "passed"


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
    checked_in_at: datetime | None
    initial_check_in_status: str | None


@dataclass(frozen=True)
class AttemptEvidenceRecord:
    """One session attempt with the times its initial steps passed."""

    attempt_id: UUID
    student_id: UUID
    status: str | None
    started_at: datetime | None
    geofence_passed_at: datetime | None
    face_passed_at: datetime | None


class CheckInRepository:
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
            SELECT id, status, started_at, checked_in_at, initial_check_in_status
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
            initial_check_in_status=row["initial_check_in_status"],
        )

    async def geofence_passed_at(
        self,
        connection: asyncpg.Connection,
        verification_attempt_id: UUID,
        *,
        not_after: datetime | None = None,
    ) -> datetime | None:
        """When the geofence step first passed, or ``None`` if it never has.

        The *earliest* pass is the answer, not the latest: the student satisfied
        the requirement then, and re-verifying afterwards must not push their
        check-in time later and make them retrospectively late.
        """

        return await connection.fetchval(
            """
            SELECT MIN(validated_at)
            FROM attendance_verification.geofence_validation_attempts
            WHERE verification_attempt_id = $1
              AND validation_status = $2
              AND validated_at IS NOT NULL
              AND ($3::timestamptz IS NULL OR validated_at <= $3)
            """,
            verification_attempt_id,
            GEOFENCE_PASSED_STATUS,
            not_after,
        )

    async def face_passed_at(
        self,
        connection: asyncpg.Connection,
        verification_attempt_id: UUID,
        *,
        not_after: datetime | None = None,
    ) -> datetime | None:
        """When the face step first passed *with liveness*, else ``None``.

        A face match without a liveness result is a photo held up to the camera
        as far as this is concerned, so it does not check anybody in. The face
        service already refuses to store ``validation_status = 'passed'`` unless
        liveness passed; repeating the condition here means a future writer that
        bypasses that constraint still cannot check a student in.
        """

        return await connection.fetchval(
            """
            SELECT MIN(validated_at)
            FROM face_verification.face_validation_attempts
            WHERE verification_attempt_id = $1
              AND validation_status = $2
              AND liveness_passed IS TRUE
              AND validated_at IS NOT NULL
              AND ($3::timestamptz IS NULL OR validated_at <= $3)
            """,
            verification_attempt_id,
            FACE_PASSED_STATUS,
            not_after,
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

    async def persist_check_in(
        self,
        connection: asyncpg.Connection,
        verification_attempt_id: UUID,
        *,
        checked_in_at: datetime,
        initial_check_in_status: InitialCheckInStatus,
    ) -> None:
        """Record the check-in on the attempt. Writes no attendance record.

        ``completed_at`` is kept in step with ``checked_in_at`` because the
        lecturer's manual-review list still reads and orders by it. The new
        columns are the ones that carry meaning; ``completed_at`` stays
        populated so that screen keeps working unchanged.

        The ``status`` guard makes this safe to call twice: a concurrent geofence
        and face pass racing to check the same student in will both compute the
        same answer, and only the first write lands.
        """

        await connection.execute(
            """
            UPDATE attendance_verification.verification_attempts
            SET status = $2,
                checked_in_at = $3,
                initial_check_in_status = $4,
                completed_at = $3
            WHERE id = $1
              AND (status IS NULL OR status = $5)
            """,
            verification_attempt_id,
            VerificationAttemptStatus.CHECKED_IN.value,
            checked_in_at,
            initial_check_in_status.value,
            VerificationAttemptStatus.IN_PROGRESS.value,
        )

    async def list_attempts_with_evidence(
        self,
        connection: asyncpg.Connection,
        session_id: UUID,
        *,
        not_after: datetime | None = None,
        statuses: tuple[str, ...] = (VerificationAttemptStatus.IN_PROGRESS.value,),
    ) -> list[AttemptEvidenceRecord]:
        """Every attempt of a session, with when each initial step passed.

        Reconciliation at session close uses this with ``not_after = closed_at``
        so that evidence which landed *before* the close still counts, even
        though nothing had got around to writing the check-in yet. Evidence
        recorded after the close is excluded by the same bound.
        """

        rows = await connection.fetch(
            """
            SELECT
                attempt.id AS attempt_id,
                attempt.student_id,
                attempt.status,
                attempt.started_at,
                (
                    SELECT MIN(geofence.validated_at)
                    FROM attendance_verification.geofence_validation_attempts AS geofence
                    WHERE geofence.verification_attempt_id = attempt.id
                      AND geofence.validation_status = $3
                      AND geofence.validated_at IS NOT NULL
                      AND ($4::timestamptz IS NULL OR geofence.validated_at <= $4)
                ) AS geofence_passed_at,
                (
                    SELECT MIN(face.validated_at)
                    FROM face_verification.face_validation_attempts AS face
                    WHERE face.verification_attempt_id = attempt.id
                      AND face.validation_status = $5
                      AND face.liveness_passed IS TRUE
                      AND face.validated_at IS NOT NULL
                      AND ($4::timestamptz IS NULL OR face.validated_at <= $4)
                ) AS face_passed_at
            FROM attendance_verification.verification_attempts AS attempt
            WHERE attempt.session_id = $1
              AND (attempt.status = ANY($2::text[]) OR attempt.status IS NULL)
            ORDER BY attempt.started_at
            FOR UPDATE OF attempt
            """,
            session_id,
            list(statuses),
            GEOFENCE_PASSED_STATUS,
            not_after,
            FACE_PASSED_STATUS,
        )
        return [
            AttemptEvidenceRecord(
                attempt_id=row["attempt_id"],
                student_id=row["student_id"],
                status=row["status"],
                started_at=row["started_at"],
                geofence_passed_at=row["geofence_passed_at"],
                face_passed_at=row["face_passed_at"],
            )
            for row in rows
        ]


__all__ = [
    "AttemptEvidenceRecord",
    "AttendanceSessionRecord",
    "CheckInRepository",
    "StudentProfileRecord",
    "VerificationAttemptRecord",
]
