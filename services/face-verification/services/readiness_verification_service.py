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

from .embedding_similarity import cosine_similarity
from .face_engine import FaceAnalysisResult, FaceAnalysisStatus, FaceEngine


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
        face_engine: FaceEngine,
        face_profile_repository: FaceProfileRepository | None = None,
        verification_config_repository: VerificationConfigRepository | None = None,
        model_version: str = "1",
        clock: Clock = _utc_now,
    ) -> None:
        
        normalized_model_version = model_version.strip()

        if not normalized_model_version:
            raise ValueError("Model version cannot be blank")

        self._session = session
        self._face_engine = face_engine
        self._face_profile_repository = (face_profile_repository or FaceProfileRepository(session))
        self._verification_config_repository = (verification_config_repository or VerificationConfigRepository(session))
        self._model_version = normalized_model_version
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

            if not 0 <= threshold <= 1:
                raise ValueError("Active similarity threshold must be between 0 and 1")

            analysis = await self._face_engine.analyze(captured_image)

            if analysis.status is not FaceAnalysisStatus.SUCCESS:
                await self._record_readiness(
                    reference=reference,
                    verification_config_id=config.id,
                    status="failed",
                )
                await self._session.commit()

                return self._result_from_failed_analysis(
                    student_id=student_id,
                    reference=reference,
                    verification_config_id=config.id,
                    threshold=threshold,
                    analysis=analysis,
                )

            if analysis.embedding is None or analysis.model_name is None:
                raise ValueError("Successful face analysis is missing required data")

            if self._has_model_mismatch(reference, analysis):
                await self._record_readiness(
                    reference=reference,
                    verification_config_id=config.id,
                    status="failed",
                )
                await self._session.commit()

                return ReadinessVerificationResult(
                    status=ReadinessVerificationStatus.MODEL_MISMATCH,
                    student_id=student_id,
                    profile_id=reference.profile_id,
                    verification_config_id=config.id,
                    similarity_threshold=threshold,
                    detection_confidence=analysis.detection_confidence,
                    model_name=analysis.model_name,
                    failure_reason=("Captured and reference embeddings are incompatible"),
                )

            score = cosine_similarity(reference.embedding,analysis.embedding,)

            passed = score >= threshold

            await self._record_readiness(
                reference=reference,
                verification_config_id=config.id,
                status="passed" if passed else "failed",
            )

            await self._session.commit()

            return ReadinessVerificationResult(
                status=(ReadinessVerificationStatus.PASSED if passed else ReadinessVerificationStatus.FAILED),
                student_id=student_id,
                profile_id=reference.profile_id,
                verification_config_id=config.id,
                similarity_score=score,
                similarity_threshold=threshold,
                detection_confidence=analysis.detection_confidence,
                model_name=analysis.model_name,
                failure_reason=(None if passed else "Face similarity was below the required threshold"),
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

    def _has_model_mismatch(self, reference: StoredFaceEmbedding,analysis: FaceAnalysisResult,) -> bool:
        if analysis.embedding is None or analysis.model_name is None:
            return True

        return (
            reference.model_name != analysis.model_name
            or reference.model_version != self._model_version
            or reference.dimension != len(reference.embedding)
            or reference.dimension != len(analysis.embedding)
        )

    @staticmethod
    def _result_from_failed_analysis(
        *,
        student_id: UUID,
        reference: StoredFaceEmbedding,
        verification_config_id: UUID,
        threshold: float,
        analysis: FaceAnalysisResult,
    ) -> ReadinessVerificationResult:
        
        status_mapping = {
            FaceAnalysisStatus.NO_FACE: ReadinessVerificationStatus.NO_FACE,
            FaceAnalysisStatus.MULTIPLE_FACES: (ReadinessVerificationStatus.MULTIPLE_FACES),
            FaceAnalysisStatus.LOW_QUALITY: (ReadinessVerificationStatus.LOW_QUALITY),
            FaceAnalysisStatus.PROCESSING_FAILED: (ReadinessVerificationStatus.PROCESSING_FAILED),
        }

        try:
            result_status = status_mapping[analysis.status]

        except KeyError as error:
            raise ValueError("Successful analysis cannot be mapped as a failure") from error

        return ReadinessVerificationResult(
            status=result_status,
            student_id=student_id,
            profile_id=reference.profile_id,
            verification_config_id=verification_config_id,
            similarity_threshold=threshold,
            detection_confidence=analysis.detection_confidence,
            model_name=analysis.model_name,
            failure_reason=analysis.failure_reason,
        )


__all__ = [
    "ReadinessVerificationPersistenceError",
    "ReadinessVerificationResult",
    "ReadinessVerificationService",
    "ReadinessVerificationStatus",
]
