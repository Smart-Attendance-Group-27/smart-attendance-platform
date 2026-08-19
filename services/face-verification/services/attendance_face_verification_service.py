from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from repositories.face_profile_repository import FaceProfileRepository
from repositories.verification_attempt_repository import (
    IN_PROGRESS_STATUS,
    VerificationAttemptRepository,
)
from repositories.verification_config_repository import (
    VerificationConfigRepository,
)

from .face_comparison_service import FaceComparisonService, FaceComparisonStatus


class AttendanceFaceVerificationStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    VERIFICATION_ATTEMPT_NOT_FOUND = "verification_attempt_not_found"
    VERIFICATION_ATTEMPT_CLOSED = "verification_attempt_closed"
    PROFILE_NOT_ENROLLED = "profile_not_enrolled"
    NO_ACTIVE_CONFIG = "no_active_config"
    NO_FACE = "no_face"
    MULTIPLE_FACES = "multiple_faces"
    LOW_QUALITY = "low_quality"
    PROCESSING_FAILED = "processing_failed"
    MODEL_MISMATCH = "model_mismatch"


@dataclass(frozen=True, slots=True)
class AttendanceFaceVerificationResult:
    status: AttendanceFaceVerificationStatus
    student_id: UUID
    verification_attempt_id: UUID | None = None
    attempt_number: int | None = None
    similarity_score: float | None = None
    similarity_threshold: float | None = None
    failure_reason: str | None = None


Clock = Callable[[], datetime]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AttendanceFaceVerificationService:
    """Verifies a captured face against a specific attendance session's
    verification attempt, and records the outcome on
    face_verification.face_validation_attempts. Distinct from
    ReadinessVerificationService, which checks profile enrolment quality in
    isolation and never touches an attempt or writes a validation attempt."""

    def __init__(
        self,
        *,
        session: AsyncSession,
        face_comparison_service: FaceComparisonService,
        face_profile_repository: FaceProfileRepository | None = None,
        verification_config_repository: VerificationConfigRepository | None = None,
        verification_attempt_repository: VerificationAttemptRepository | None = None,
        clock: Clock = _utc_now,
    ) -> None:
        self._session = session
        self._face_comparison_service = face_comparison_service
        self._face_profile_repository = face_profile_repository or FaceProfileRepository(session)
        self._verification_config_repository = (
            verification_config_repository or VerificationConfigRepository(session)
        )
        self._verification_attempt_repository = (
            verification_attempt_repository or VerificationAttemptRepository(session)
        )
        self._clock = clock

    async def verify(
        self,
        *,
        session_id: UUID,
        student_id: UUID,
        captured_image: bytes,
    ) -> AttendanceFaceVerificationResult:
        try:
            attempt = await self._verification_attempt_repository.find_in_progress(
                session_id=session_id,
                student_id=student_id,
            )
            if attempt is None:
                return AttendanceFaceVerificationResult(
                    status=AttendanceFaceVerificationStatus.VERIFICATION_ATTEMPT_NOT_FOUND,
                    student_id=student_id,
                    failure_reason=(
                        "No verification attempt exists for this student and "
                        "session — complete the geofence check first."
                    ),
                )
            if attempt.status != IN_PROGRESS_STATUS:
                return AttendanceFaceVerificationResult(
                    status=AttendanceFaceVerificationStatus.VERIFICATION_ATTEMPT_CLOSED,
                    student_id=student_id,
                    verification_attempt_id=attempt.id,
                    failure_reason="The verification attempt is already complete.",
                )

            reference = await self._face_profile_repository.get_stored_embedding_for_comparison(
                student_id
            )
            if reference is None:
                return AttendanceFaceVerificationResult(
                    status=AttendanceFaceVerificationStatus.PROFILE_NOT_ENROLLED,
                    student_id=student_id,
                    verification_attempt_id=attempt.id,
                    failure_reason="The student does not have a generated face profile",
                )

            config = await self._verification_config_repository.get_active()
            if config is None:
                return AttendanceFaceVerificationResult(
                    status=AttendanceFaceVerificationStatus.NO_ACTIVE_CONFIG,
                    student_id=student_id,
                    verification_attempt_id=attempt.id,
                    failure_reason="No active face-verification configuration is available",
                )

            threshold = float(config.similarity_threshold)
            comparison = await self._face_comparison_service.compare(
                reference=reference,
                captured_image=captured_image,
                similarity_threshold=threshold,
            )
            passed = comparison.status is FaceComparisonStatus.MATCHED
            validated_at = self._clock()
            attempt_number = await self._verification_attempt_repository.next_attempt_number(
                attempt.id
            )

            await self._verification_attempt_repository.insert_face_attempt(
                verification_attempt_id=attempt.id,
                face_profile_id=reference.profile_id,
                verification_config_id=config.id,
                attempt_number=attempt_number,
                liveness_passed=True if passed else None,
                quality_passed=True if passed else None,
                similarity_score=(
                    Decimal(str(comparison.similarity_score))
                    if comparison.similarity_score is not None
                    else None
                ),
                validation_status="passed" if passed else "failed",
                failure_reason=None if passed else (comparison.failure_reason or "Face verification failed"),
                captured_at=validated_at,
                validated_at=validated_at,
            )

            await self._session.commit()

            return AttendanceFaceVerificationResult(
                status=self._status_for_comparison(comparison.status),
                student_id=student_id,
                verification_attempt_id=attempt.id,
                attempt_number=attempt_number,
                similarity_score=comparison.similarity_score,
                similarity_threshold=comparison.similarity_threshold,
                failure_reason=comparison.failure_reason,
            )
        except Exception:
            await self._session.rollback()
            raise

    @staticmethod
    def _status_for_comparison(
        comparison_status: FaceComparisonStatus,
    ) -> AttendanceFaceVerificationStatus:
        if comparison_status is FaceComparisonStatus.MATCHED:
            return AttendanceFaceVerificationStatus.PASSED
        if comparison_status is FaceComparisonStatus.NOT_MATCHED:
            return AttendanceFaceVerificationStatus.FAILED
        return AttendanceFaceVerificationStatus(comparison_status.value)


__all__ = [
    "AttendanceFaceVerificationResult",
    "AttendanceFaceVerificationService",
    "AttendanceFaceVerificationStatus",
]
