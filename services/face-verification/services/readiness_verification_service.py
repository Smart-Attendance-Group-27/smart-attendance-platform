from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from repositories.face_profile_repository import (
    FaceProfileRepository,
    StoredFaceEmbedding,
)
from repositories.verification_config_repository import (
    VerificationConfigRepository,
)

from .face_comparison_service import (
    FaceComparisonService,
    FaceComparisonStatus,
)


class ReadinessVerificationStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    PROFILE_NOT_ENROLLED = "profile_not_enrolled"
    NO_ACTIVE_CONFIG = "no_active_config"
    NO_FACE = "no_face"
    MULTIPLE_FACES = "multiple_faces"
    LOW_QUALITY = "low_quality"
    PROCESSING_FAILED = "processing_failed"
    MODEL_MISMATCH = "model_mismatch"


@dataclass(frozen=True, slots=True)
class ReadinessVerificationResult:

    status: ReadinessVerificationStatus
    student_id: UUID
    profile_id: UUID | None = None
    verification_config_id: UUID | None = None
    similarity_score: float | None = None
    similarity_threshold: float | None = None
    detection_confidence: float | None = None
    model_name: str | None = None
    failure_reason: str | None = None


class ReadinessVerificationPersistenceError(RuntimeError):
    """Raised when a readiness result could not be stored."""


Clock = Callable[[], datetime]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ReadinessVerificationService:
    """Verify a captured face without creating an attendance record."""

    def __init__(
        self,
        *,
        session: AsyncSession,
        face_comparison_service: FaceComparisonService,
        face_profile_repository: FaceProfileRepository | None = None,
        verification_config_repository: VerificationConfigRepository | None = None,
        clock: Clock = _utc_now,
    ) -> None:
        self._session = session
        self._face_comparison_service = face_comparison_service
        self._face_profile_repository = (face_profile_repository or FaceProfileRepository(session))
        self._verification_config_repository = (verification_config_repository or VerificationConfigRepository(session))
        self._clock = clock

    async def verify(self,*,student_id: UUID,captured_image: bytes,) -> ReadinessVerificationResult:
        try:
            reference = (await self._face_profile_repository.get_stored_embedding_for_comparison(student_id))

            if reference is None:
                return ReadinessVerificationResult(
                    status=ReadinessVerificationStatus.PROFILE_NOT_ENROLLED,
                    student_id=student_id,
                    failure_reason=("The student does not have a generated face profile"),
                )

            config = await self._verification_config_repository.get_active()

            if config is None:
                return ReadinessVerificationResult(
                    status=ReadinessVerificationStatus.NO_ACTIVE_CONFIG,
                    student_id=student_id,
                    profile_id=reference.profile_id,
                    model_name=reference.model_name,
                    failure_reason=("No active face-verification configuration is available"),
                )

            threshold = float(config.similarity_threshold)
            comparison = await self._face_comparison_service.compare(
                reference=reference,
                captured_image=captured_image,
                similarity_threshold=threshold,
            )
            passed = comparison.status is FaceComparisonStatus.MATCHED

            await self._record_readiness(
                reference=reference,
                verification_config_id=config.id,
                status="passed" if passed else "failed",
            )

            await self._session.commit()

            return ReadinessVerificationResult(
                status=self._readiness_status_for_comparison(
                    comparison.status
                ),
                student_id=student_id,
                profile_id=reference.profile_id,
                verification_config_id=config.id,
                similarity_score=comparison.similarity_score,
                similarity_threshold=comparison.similarity_threshold,
                detection_confidence=comparison.detection_confidence,
                model_name=comparison.model_name,
                failure_reason=comparison.failure_reason,
            )
        
        except Exception:
            await self._session.rollback()
            raise

    async def _record_readiness(self,*,reference: StoredFaceEmbedding,verification_config_id: UUID,status: str,) -> None:
        updated_profile = (
            await self._face_profile_repository.update_readiness_result(
                reference.profile_id,
                status=status,
                verification_config_id=verification_config_id,
                checked_at=self._clock(),
            )
        )

        if updated_profile is None:
            raise ReadinessVerificationPersistenceError("Face profile disappeared while recording readiness")

    @staticmethod
    def _readiness_status_for_comparison(
        comparison_status: FaceComparisonStatus,
    ) -> ReadinessVerificationStatus:
        if comparison_status is FaceComparisonStatus.MATCHED:
            return ReadinessVerificationStatus.PASSED

        if comparison_status is FaceComparisonStatus.NOT_MATCHED:
            return ReadinessVerificationStatus.FAILED

        return ReadinessVerificationStatus(comparison_status.value)


__all__ = [
    "ReadinessVerificationPersistenceError",
    "ReadinessVerificationResult",
    "ReadinessVerificationService",
    "ReadinessVerificationStatus",
]
