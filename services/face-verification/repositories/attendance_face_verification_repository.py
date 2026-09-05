from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from models.face_validation_attempt import FaceValidationAttempt


@dataclass(frozen=True, slots=True)
class AttendanceVerificationContext:
    verification_attempt_id: UUID
    verification_status: str
    session_status: str
    requires_face_verification: bool
    requires_geofence: bool
    latest_geofence_status: str | None
    check_in_opens_at: datetime | None
    check_in_closes_at: datetime | None
    closed_at: datetime | None
    cancelled_at: datetime | None


class AttendanceFaceVerificationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def lock_verification_context(
        self,
        *,
        session_id: UUID,
        student_id: UUID,
    ) -> AttendanceVerificationContext | None:
        result = await self._session.execute(
            text(
                """
                SELECT
                    attempt.id AS verification_attempt_id,
                    attempt.status AS verification_status,
                    attendance_session.status AS session_status,
                    attendance_session.requires_face_verification,
                    attendance_session.requires_geofence,
                    (
                        SELECT geofence.validation_status
                        FROM attendance_verification.geofence_validation_attempts
                            AS geofence
                        WHERE geofence.verification_attempt_id = attempt.id
                        ORDER BY geofence.attempt_number DESC
                        LIMIT 1
                    ) AS latest_geofence_status,
                    attendance_session.check_in_opens_at,
                    attendance_session.check_in_closes_at,
                    attendance_session.closed_at,
                    attendance_session.cancelled_at
                FROM attendance_verification.verification_attempts AS attempt
                JOIN attendance_session.sessions AS attendance_session
                  ON attendance_session.id = attempt.session_id
                WHERE attempt.session_id = :session_id
                  AND attempt.student_id = :student_id
                FOR UPDATE OF attempt
                """
            ),
            {"session_id": session_id, "student_id": student_id},
        )
        row = result.mappings().one_or_none()
        if row is None:
            return None

        return AttendanceVerificationContext(
            verification_attempt_id=row["verification_attempt_id"],
            verification_status=row["verification_status"],
            session_status=row["session_status"],
            requires_face_verification=bool(row["requires_face_verification"]),
            requires_geofence=bool(row["requires_geofence"]),
            latest_geofence_status=row["latest_geofence_status"],
            check_in_opens_at=row["check_in_opens_at"],
            check_in_closes_at=row["check_in_closes_at"],
            closed_at=row["closed_at"],
            cancelled_at=row["cancelled_at"],
        )

    async def lock_latest_face_attempt(
        self,
        verification_attempt_id: UUID,
    ) -> FaceValidationAttempt | None:
        result = await self._session.execute(
            select(FaceValidationAttempt)
            .where(
                FaceValidationAttempt.verification_attempt_id
                == verification_attempt_id
            )
            .order_by(FaceValidationAttempt.attempt_number.desc())
            .limit(1)
            .with_for_update()
        )
        return result.scalar_one_or_none()

    async def save_latest_face_attempt(
        self,
        *,
        existing: FaceValidationAttempt | None,
        verification_attempt_id: UUID,
        face_profile_id: UUID,
        attempt_number: int,
        liveness_passed: bool | None,
        quality_passed: bool | None,
        similarity_score: float | None,
        verification_config_id: UUID,
        validation_status: str,
        failure_reason: str | None,
        captured_at: datetime,
        validated_at: datetime,
    ) -> FaceValidationAttempt:
        record = existing or FaceValidationAttempt(
            verification_attempt_id=verification_attempt_id,
            face_profile_id=face_profile_id,
            attempt_number=attempt_number,
            verification_config_id=verification_config_id,
        )

        record.face_profile_id = face_profile_id
        record.attempt_number = attempt_number
        record.liveness_passed = liveness_passed
        record.quality_passed = quality_passed
        record.similarity_score = (
            Decimal(str(similarity_score))
            if similarity_score is not None
            else None
        )
        record.verification_config_id = verification_config_id
        record.validation_status = validation_status
        record.failure_reason = failure_reason
        record.captured_at = captured_at
        record.validated_at = validated_at

        if existing is None:
            self._session.add(record)

        await self._session.flush()
        return record

    async def mark_verification_attempt_failed(
        self,
        verification_attempt_id: UUID,
        *,
        failure_reason: str,
        completed_at: datetime,
    ) -> None:
        await self._session.execute(
            text(
                """
                UPDATE attendance_verification.verification_attempts
                SET status = 'failed',
                    failure_reason = :failure_reason,
                    completed_at = :completed_at
                WHERE id = :verification_attempt_id
                  AND status = 'in_progress'
                """
            ),
            {
                "verification_attempt_id": verification_attempt_id,
                "failure_reason": failure_reason,
                "completed_at": completed_at,
            },
        )


__all__ = [
    "AttendanceFaceVerificationRepository",
    "AttendanceVerificationContext",
]
