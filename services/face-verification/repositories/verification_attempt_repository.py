from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.base import verification_attempts_table
from models.face_validation_attempt import FaceValidationAttempt

IN_PROGRESS_STATUS = "in_progress"


@dataclass(frozen=True, slots=True)
class VerificationAttemptRecord:
    id: UUID
    status: str | None


class VerificationAttemptRepository:
    """Read-only lookups into core-backend's attendance_verification schema,
    plus writes into face_verification.face_validation_attempts — the only
    table in that join this service is allowed to write."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_in_progress(
        self,
        *,
        session_id: UUID,
        student_id: UUID,
    ) -> VerificationAttemptRecord | None:
        statement = select(
            verification_attempts_table.c.id,
            verification_attempts_table.c.status,
        ).where(
            verification_attempts_table.c.session_id == session_id,
            verification_attempts_table.c.student_id == student_id,
        )
        result = await self._session.execute(statement)
        row = result.first()

        if row is None:
            return None

        return VerificationAttemptRecord(id=row.id, status=row.status)

    async def next_attempt_number(self, verification_attempt_id: UUID) -> int:
        statement = select(
            func.coalesce(func.max(FaceValidationAttempt.attempt_number), 0) + 1
        ).where(
            FaceValidationAttempt.verification_attempt_id == verification_attempt_id
        )
        result = await self._session.execute(statement)
        return int(result.scalar_one())

    async def insert_face_attempt(
        self,
        *,
        verification_attempt_id: UUID,
        face_profile_id: UUID,
        verification_config_id: UUID,
        attempt_number: int,
        liveness_passed: bool | None,
        quality_passed: bool | None,
        similarity_score: Decimal | None,
        validation_status: str,
        failure_reason: str | None,
        captured_at: datetime,
        validated_at: datetime,
    ) -> None:
        attempt = FaceValidationAttempt(
            verification_attempt_id=verification_attempt_id,
            face_profile_id=face_profile_id,
            verification_config_id=verification_config_id,
            attempt_number=attempt_number,
            liveness_passed=liveness_passed,
            quality_passed=quality_passed,
            similarity_score=similarity_score,
            validation_status=validation_status,
            failure_reason=failure_reason,
            captured_at=captured_at,
            validated_at=validated_at,
        )
        self._session.add(attempt)
        await self._session.flush()


__all__ = [
    "IN_PROGRESS_STATUS",
    "VerificationAttemptRecord",
    "VerificationAttemptRepository",
]
