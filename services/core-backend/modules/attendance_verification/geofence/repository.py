from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

import asyncpg

from modules.attendance_verification.geofence.types import GeofenceValidationResult

IN_PROGRESS_STATUS = "in_progress"
FAILED_STATUS = "failed"


@dataclass(frozen=True)
class StudentProfileRecord:
    id: UUID
    profile_status: str | None


@dataclass(frozen=True)
class AttendanceSessionRecord:
    id: UUID
    status: str | None
    check_in_opens_at: datetime | None
    check_in_closes_at: datetime | None
    requires_geofence: bool | None
    requires_face_verification: bool | None
    closed_at: datetime | None
    cancelled_at: datetime | None


@dataclass(frozen=True)
class SessionGeofenceRecord:
    centre_latitude: Decimal | None
    centre_longitude: Decimal | None
    radius_m: Decimal | None
    accuracy_buffer_m: Decimal | None
    maximum_allowed_accuracy_m: Decimal | None


@dataclass(frozen=True)
class VerificationAttemptRecord:
    id: UUID
    status: str | None
    failure_reason: str | None


class GeofenceRepository:
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

        return StudentProfileRecord(
            id=row["id"],
            profile_status=row["profile_status"],
        )

    async def lock_attendance_session(
        self,
        connection: asyncpg.Connection,
        session_id: UUID,
    ) -> AttendanceSessionRecord | None:
        row = await connection.fetchrow(
            """
            SELECT
                id,
                status,
                check_in_opens_at,
                check_in_closes_at,
                requires_geofence,
                requires_face_verification,
                closed_at,
                cancelled_at
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
            check_in_opens_at=row["check_in_opens_at"],
            check_in_closes_at=row["check_in_closes_at"],
            requires_geofence=row["requires_geofence"],
            requires_face_verification=row["requires_face_verification"],
            closed_at=row["closed_at"],
            cancelled_at=row["cancelled_at"],
        )

    async def lock_student_eligibility(
        self,
        connection: asyncpg.Connection,
        session_id: UUID,
        student_id: UUID,
    ) -> bool:
        row = await connection.fetchrow(
            """
            SELECT id
            FROM attendance_session.session_students
            WHERE session_id = $1
              AND student_id = $2
            FOR SHARE
            """,
            session_id,
            student_id,
        )
        return row is not None

    async def lock_session_geofence(
        self,
        connection: asyncpg.Connection,
        session_id: UUID,
    ) -> SessionGeofenceRecord | None:
        row = await connection.fetchrow(
            """
            SELECT
                centre_latitude,
                centre_longitude,
                radius_m,
                accuracy_buffer_m,
                maximum_allowed_accuracy_m
            FROM attendance_session.session_geofences
            WHERE session_id = $1
            FOR SHARE
            """,
            session_id,
        )

        if row is None:
            return None

        return SessionGeofenceRecord(
            centre_latitude=row["centre_latitude"],
            centre_longitude=row["centre_longitude"],
            radius_m=row["radius_m"],
            accuracy_buffer_m=row["accuracy_buffer_m"],
            maximum_allowed_accuracy_m=row["maximum_allowed_accuracy_m"],
        )

    async def lock_or_create_verification_attempt(
        self,
        connection: asyncpg.Connection,
        verification_attempt_id: UUID,
        session_id: UUID,
        student_id: UUID,
        started_at: datetime,
    ) -> VerificationAttemptRecord:
        row = await connection.fetchrow(
            """
            INSERT INTO attendance_verification.verification_attempts (
                id,
                session_id,
                student_id,
                status,
                failure_reason,
                started_at,
                completed_at
            )
            VALUES ($1, $2, $3, $4, NULL, $5, NULL)
            ON CONFLICT (session_id, student_id) DO UPDATE
            SET session_id = EXCLUDED.session_id
            RETURNING id, status, failure_reason
            """,
            verification_attempt_id,
            session_id,
            student_id,
            IN_PROGRESS_STATUS,
            started_at,
        )

        return VerificationAttemptRecord(
            id=row["id"],
            status=row["status"],
            failure_reason=row["failure_reason"],
        )

    async def next_geofence_attempt_number(
        self,
        connection: asyncpg.Connection,
        verification_attempt_id: UUID,
    ) -> int:
        value = await connection.fetchval(
            """
            SELECT COALESCE(MAX(attempt_number), 0) + 1
            FROM attendance_verification.geofence_validation_attempts
            WHERE verification_attempt_id = $1
            """,
            verification_attempt_id,
        )
        return int(value)

    async def insert_geofence_attempt(
        self,
        connection: asyncpg.Connection,
        geofence_attempt_id: UUID,
        verification_attempt_id: UUID,
        attempt_number: int,
        accuracy_m: float | None,
        result: GeofenceValidationResult,
        captured_at: datetime,
        validated_at: datetime,
    ) -> None:
        await connection.execute(
            """
            INSERT INTO attendance_verification.geofence_validation_attempts (
                id,
                verification_attempt_id,
                attempt_number,
                accuracy_m,
                distance_from_centre_m,
                validation_status,
                failure_reason,
                captured_at,
                validated_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            """,
            geofence_attempt_id,
            verification_attempt_id,
            attempt_number,
            Decimal(str(accuracy_m)) if accuracy_m is not None else None,
            Decimal(str(result.distance_m)),
            result.decision.value.lower(),
            result.reason.value if result.reason is not None else None,
            captured_at,
            validated_at,
        )

    async def mark_verification_attempt_failed(
        self,
        connection: asyncpg.Connection,
        verification_attempt_id: UUID,
        failure_reason: str,
        completed_at: datetime,
    ) -> None:
        await connection.execute(
            """
            UPDATE attendance_verification.verification_attempts
            SET status = $2,
                failure_reason = $3,
                completed_at = $4
            WHERE id = $1
            """,
            verification_attempt_id,
            FAILED_STATUS,
            failure_reason,
            completed_at,
        )
