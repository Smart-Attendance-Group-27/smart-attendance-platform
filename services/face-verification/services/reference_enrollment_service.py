from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from models.face_profile import FaceProfile
from repositories.face_profile_repository import FaceProfileRepository

from .face_engine import (
    FaceAnalysisResult,
    FaceAnalysisStatus,
    FaceEngine,
)


class ReferenceEnrollmentStatus(StrEnum):

    SUCCESS = "success"
    ALREADY_ENROLLED = "already_enrolled"
    PROFILE_REVOKED = "profile_revoked"
    NO_FACE = "no_face"
    MULTIPLE_FACES = "multiple_faces"
    LOW_QUALITY = "low_quality"
    PROCESSING_FAILED = "processing_failed"


@dataclass(frozen=True, slots=True)
class ReferenceEnrollmentResult:

    status: ReferenceEnrollmentStatus
    student_id: UUID
    profile_id: UUID
    detection_confidence: float | None = None
    model_name: str | None = None
    failure_reason: str | None = None


class ReferenceEnrollmentPersistenceError(RuntimeError):
    """Raised when an expected face-profile update did not occur."""


class ReferenceEnrollmentService:
    """Generate and store a reference embedding from an official photograph."""
    _DEFAULT_MODEL_VERSION = "1"

    def __init__(self, *,session: AsyncSession,face_engine: FaceEngine,repository: FaceProfileRepository | None = None,) -> None:
        self._session = session
        self._face_engine = face_engine
        self._repository = repository or FaceProfileRepository(session)

    async def enroll(self,*,student_id: UUID,official_photo: bytes, ) -> ReferenceEnrollmentResult:
        try:
            profile = await self._repository.get_by_student_id(student_id)

            # Replacing a valid reference must be a separate, explicitly authorized operation. Normal enrollment never overwrites it.
            if profile is not None and (profile.embedding_generation_status == "generated"):
                return self._result_without_analysis(
                    status=ReferenceEnrollmentStatus.ALREADY_ENROLLED,
                    profile=profile,
                    reason="The student already has a generated face profile",
                )

            # A revoked profile must be restored through an administrator's revocation
            if profile is not None and (profile.embedding_generation_status == "revoked"):
                return self._result_without_analysis(
                    status=ReferenceEnrollmentStatus.PROFILE_REVOKED,
                    profile=profile,
                    reason="The student's face profile is revoked",
                )

            if profile is None:
                # The supplied UUID must already identify a real student.
                profile = await self._repository.create_pending_profile(student_id)

            analysis = await self._face_engine.analyze(official_photo)

            if analysis.status is not FaceAnalysisStatus.SUCCESS:
                await self._save_failed_generation(profile.id)
                await self._session.commit()

                return self._result_from_analysis(
                    status=self._map_failure_status(analysis.status),
                    student_id=student_id,
                    profile_id=profile.id,
                    analysis=analysis,
                )

            # FaceAnalysisResult guarantees that a successful result contains an embedding
            if analysis.embedding is None:
                raise ReferenceEnrollmentPersistenceError("Successful analysis did not contain an embedding")
            if analysis.model_name is None:
                raise ReferenceEnrollmentPersistenceError("Successful analysis did not contain a model name")

            saved_profile = (
                await self._repository.save_generated_embedding(
                    profile.id,
                    analysis.embedding,
                    model_name=analysis.model_name,
                    model_version=self._DEFAULT_MODEL_VERSION,
                )
            )

            if saved_profile is None:
                raise ReferenceEnrollmentPersistenceError("Face profile disappeared while saving the embedding")

            await self._session.commit()

            return self._result_from_analysis(
                status=ReferenceEnrollmentStatus.SUCCESS,
                student_id=student_id,
                profile_id=profile.id,
                analysis=analysis,
            )
        except Exception:
            await self._session.rollback()
            raise

    async def _save_failed_generation(self, profile_id: UUID) -> None:
        failed_profile = await self._repository.mark_generation_failed(profile_id)

        if failed_profile is None:
            raise ReferenceEnrollmentPersistenceError("Face profile disappeared while recording failure")

    @staticmethod
    def _map_failure_status(status: FaceAnalysisStatus,) -> ReferenceEnrollmentStatus:
        mapping = {
            FaceAnalysisStatus.NO_FACE: ReferenceEnrollmentStatus.NO_FACE,
            FaceAnalysisStatus.MULTIPLE_FACES: ReferenceEnrollmentStatus.MULTIPLE_FACES,
            FaceAnalysisStatus.LOW_QUALITY: ReferenceEnrollmentStatus.LOW_QUALITY,
            FaceAnalysisStatus.PROCESSING_FAILED: ReferenceEnrollmentStatus.PROCESSING_FAILED,
        }

        try:
            return mapping[status]
        except KeyError as error:
            # just a safety check
            raise ValueError("Successful analysis cannot be mapped as a failure") from error

    @staticmethod
    def _result_from_analysis(*,status: ReferenceEnrollmentStatus,student_id: UUID,profile_id: UUID,analysis: FaceAnalysisResult,) -> ReferenceEnrollmentResult:
        return ReferenceEnrollmentResult(
            status=status,
            student_id=student_id,
            profile_id=profile_id,
            detection_confidence=analysis.detection_confidence,
            model_name=analysis.model_name,
            failure_reason=analysis.failure_reason,
        )

    @staticmethod
    def _result_without_analysis(*,status: ReferenceEnrollmentStatus,profile: FaceProfile,reason: str,) -> ReferenceEnrollmentResult:
        return ReferenceEnrollmentResult(
            status=status,
            student_id=profile.student_id,
            profile_id=profile.id,
            failure_reason=reason,
        )


__all__ = [
    "ReferenceEnrollmentPersistenceError",
    "ReferenceEnrollmentResult",
    "ReferenceEnrollmentService",
    "ReferenceEnrollmentStatus",
]
