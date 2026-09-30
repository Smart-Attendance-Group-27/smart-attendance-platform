from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

import asyncpg

from modules.attendance_verification.attendance_state import VerificationAttemptStatus
from modules.attendance_verification.check_in.domain import RequiredStep, StepRequirement
from modules.attendance_verification.session_overrides.domain import (
    GeofenceWaiverReason,
    OverrideScope,
    SessionVerificationOverride,
)

GEOFENCE_PASSED_STATUS = "passed"
PENDING_REVIEW_STATUS = "pending"


@dataclass(frozen=True)
class OverrideSessionRecord:
    id: UUID
    activated_at: datetime | None
    closed_at: datetime | None
    cancelled_at: datetime | None
    requires_geofence: bool
    requires_face_verification: bool


@dataclass(frozen=True)
class ReopenedAttempt:
    verification_attempt_id: UUID
    student_id: UUID
    previous_failure_reason: str | None


class SessionOverrideRepository:
    async def find_session_for_lecturer(
        self,
        connection: asyncpg.Connection,
        session_id: UUID,
        lecturer_id: UUID,
        *,
        lock_for_update: bool = False,
    ) -> OverrideSessionRecord | None:
        # FOR UPDATE serialises a waiver with closing the session, which takes
        # the same row lock.
        lock_clause = "FOR UPDATE" if lock_for_update else ""
        row = await connection.fetchrow(
            f"""
            SELECT
                session.id, session.activated_at, session.closed_at,
                session.cancelled_at, session.requires_geofence,
                session.requires_face_verification
            FROM attendance_session.sessions AS session
            WHERE session.id = $1
              AND EXISTS (
                  SELECT 1
                  FROM academic.course_lecturers AS assignment
                  WHERE assignment.course_offering_id = session.course_offering_id
                    AND assignment.lecturer_id = $2
              )
            {lock_clause}
            """,
            session_id,
            lecturer_id,
        )
        if row is None:
            return None
        return OverrideSessionRecord(
            id=row["id"],
            activated_at=row["activated_at"],
            closed_at=row["closed_at"],
            cancelled_at=row["cancelled_at"],
            requires_geofence=bool(row["requires_geofence"]),
            requires_face_verification=bool(row["requires_face_verification"]),
        )

    async def find_override(
        self,
        connection: asyncpg.Connection,
        session_id: UUID,
        factor: RequiredStep,
    ) -> SessionVerificationOverride | None:
        row = await connection.fetchrow(
            """
            SELECT
                override.id, override.session_id, override.verification_factor,
                override.scope, override.previous_policy, override.new_policy,
                override.reason_code, override.reason_text, override.performed_by,
                override.performed_at, override.affected_student_count,
                COALESCE(
                    NULLIF(TRIM(CONCAT_WS(
                        ' ', lecturer.first_name, NULLIF(lecturer.middle_name, ''),
                        lecturer.last_name
                    )), ''),
                    app_user.email
                ) AS performed_by_name
            FROM attendance_session.session_verification_overrides AS override
            LEFT JOIN academic.lecturer_profiles AS lecturer
                ON lecturer.user_id = override.performed_by
            LEFT JOIN identity.users AS app_user
                ON app_user.id = override.performed_by
            WHERE override.session_id = $1 AND override.verification_factor = $2
            """,
            session_id,
            factor.value,
        )
        if row is None:
            return None
        return SessionVerificationOverride(
            id=row["id"],
            session_id=row["session_id"],
            verification_factor=RequiredStep(row["verification_factor"]),
            scope=OverrideScope(row["scope"]),
            previous_policy=StepRequirement(row["previous_policy"]),
            new_policy=StepRequirement(row["new_policy"]),
            reason_code=GeofenceWaiverReason(row["reason_code"]),
            reason_text=row["reason_text"],
            performed_by=row["performed_by"],
            performed_by_name=row["performed_by_name"],
            performed_at=row["performed_at"],
            affected_student_count=row["affected_student_count"],
        )

    async def count_students_without_geofence_pass(
        self,
        connection: asyncpg.Connection,
        session_id: UUID,
    ) -> int:
        """Roster students with no passing geofence reading, including those
        who have not started at all. This is ``affected_student_count``."""

        value = await connection.fetchval(
            """
            SELECT COUNT(*)
            FROM attendance_session.session_students AS roster
            WHERE roster.session_id = $1
              AND NOT EXISTS (
                  SELECT 1
                  FROM attendance_verification.verification_attempts AS attempt
                  JOIN attendance_verification.geofence_validation_attempts AS reading
                      ON reading.verification_attempt_id = attempt.id
                  WHERE attempt.session_id = roster.session_id
                    AND attempt.student_id = roster.student_id
                    AND reading.validation_status = $2
              )
            """,
            session_id,
            GEOFENCE_PASSED_STATUS,
        )
        return int(value or 0)

    async def insert_override(
        self,
        connection: asyncpg.Connection,
        *,
        session_id: UUID,
        factor: RequiredStep,
        reason_code: GeofenceWaiverReason,
        reason_text: str | None,
        performed_by: UUID,
        performed_at: datetime,
        affected_student_count: int,
    ) -> UUID | None:
        """Returns the new id, or ``None`` when the factor was already waived."""

        return await connection.fetchval(
            """
            INSERT INTO attendance_session.session_verification_overrides (
                session_id, verification_factor, scope, previous_policy, new_policy,
                reason_code, reason_text, performed_by, performed_at,
                affected_student_count
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            ON CONFLICT (session_id, verification_factor) DO NOTHING
            RETURNING id
            """,
            session_id,
            factor.value,
            OverrideScope.SESSION.value,
            StepRequirement.REQUIRED.value,
            StepRequirement.WAIVED.value,
            reason_code.value,
            reason_text,
            performed_by,
            performed_at,
            affected_student_count,
        )

    async def reopen_attempts_failed_by_geofence(
        self,
        connection: asyncpg.Connection,
        session_id: UUID,
        reopenable_reasons: frozenset[str],
    ) -> list[ReopenedAttempt]:
        """Puts attempts that failed only on location back in progress.

        This changes the process state of the attempt, never the evidence: the
        failed geofence readings stay exactly as recorded. Attempts a lecturer
        already decided (a manual attendance record or a finished review) are
        left alone.
        """

        rows = await connection.fetch(
            """
            WITH target AS (
                SELECT attempt.id, attempt.student_id, attempt.failure_reason
                FROM attendance_verification.verification_attempts AS attempt
                WHERE attempt.session_id = $1
                  AND attempt.status = $2
                  AND attempt.failure_reason = ANY($3::text[])
                  AND NOT EXISTS (
                      SELECT 1 FROM attendance_verification.attendance_records AS record
                      WHERE record.session_id = attempt.session_id
                        AND record.student_id = attempt.student_id
                  )
                  AND NOT EXISTS (
                      SELECT 1 FROM attendance_verification.manual_reviews AS review
                      WHERE review.verification_attempt_id = attempt.id
                        AND review.review_status IS NOT NULL
                        AND review.review_status <> $5
                  )
                FOR UPDATE OF attempt
            )
            UPDATE attendance_verification.verification_attempts AS attempt
            SET status = $4, failure_reason = NULL, completed_at = NULL
            FROM target
            WHERE attempt.id = target.id
            RETURNING attempt.id, target.student_id, target.failure_reason
            """,
            session_id,
            VerificationAttemptStatus.FAILED.value,
            sorted(reopenable_reasons),
            VerificationAttemptStatus.IN_PROGRESS.value,
            PENDING_REVIEW_STATUS,
        )
        return [
            ReopenedAttempt(
                verification_attempt_id=row["id"],
                student_id=row["student_id"],
                previous_failure_reason=row["failure_reason"],
            )
            for row in rows
        ]

    async def geofence_counts(
        self,
        connection: asyncpg.Connection,
        session_id: UUID,
    ) -> tuple[int, int]:
        """``(students who submitted a location, students who passed)``."""

        row = await connection.fetchrow(
            """
            SELECT
                COUNT(*) AS attempted,
                COUNT(*) FILTER (WHERE per_student.passed) AS passed
            FROM (
                SELECT BOOL_OR(reading.validation_status = $2) AS passed
                FROM attendance_verification.verification_attempts AS attempt
                JOIN attendance_verification.geofence_validation_attempts AS reading
                    ON reading.verification_attempt_id = attempt.id
                WHERE attempt.session_id = $1
                GROUP BY attempt.id
            ) AS per_student
            """,
            session_id,
            GEOFENCE_PASSED_STATUS,
        )
        return int(row["attempted"] or 0), int(row["passed"] or 0)


__all__ = [
    "OverrideSessionRecord",
    "ReopenedAttempt",
    "SessionOverrideRepository",
]
