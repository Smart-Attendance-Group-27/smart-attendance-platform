from dataclasses import dataclass
from enum import StrEnum

from repositories.face_profile_repository import StoredFaceEmbedding

from .embedding_similarity import cosine_similarity
from .face_engine import FaceAnalysisStatus, FaceEngine


class FaceComparisonStatus(StrEnum):
    MATCHED = "matched"
    NOT_MATCHED = "not_matched"
    NO_FACE = "no_face"
    MULTIPLE_FACES = "multiple_faces"
    LOW_QUALITY = "low_quality"
    PROCESSING_FAILED = "processing_failed"
    MODEL_MISMATCH = "model_mismatch"


@dataclass(frozen=True, slots=True)
class FaceComparisonResult:
    status: FaceComparisonStatus
    similarity_score: float | None = None
    similarity_threshold: float | None = None
    detection_confidence: float | None = None
    model_name: str | None = None
    failure_reason: str | None = None


class FaceComparisonService:
    """Run the shared capture-to-reference face comparison pipeline."""

    def __init__(
        self,
        *,
        face_engine: FaceEngine,
        model_version: str,
    ) -> None:
        normalized_model_version = model_version.strip()
        if not normalized_model_version:
            raise ValueError("Model version cannot be blank")

        self._face_engine = face_engine
        self._model_version = normalized_model_version

    async def compare(
        self,
        *,
        reference: StoredFaceEmbedding,
        captured_image: bytes,
        similarity_threshold: float,
    ) -> FaceComparisonResult:
        if not 0 <= similarity_threshold <= 1:
            raise ValueError(
                "Similarity threshold must be between 0 and 1"
            )

        analysis = await self._face_engine.analyze(captured_image)

        if analysis.status is not FaceAnalysisStatus.SUCCESS:
            try:
                comparison_status = FaceComparisonStatus(
                    analysis.status.value
                )
            except ValueError as error:
                raise ValueError(
                    "Successful analysis cannot be mapped as a failure"
                ) from error

            return FaceComparisonResult(
                status=comparison_status,
                similarity_threshold=similarity_threshold,
                detection_confidence=analysis.detection_confidence,
                model_name=analysis.model_name,
                failure_reason=analysis.failure_reason,
            )

        if analysis.embedding is None or analysis.model_name is None:
            raise ValueError("Successful face analysis is missing required data")

        if (
            reference.model_name != analysis.model_name
            or reference.model_version != self._model_version
            or reference.dimension != len(reference.embedding)
            or reference.dimension != len(analysis.embedding)
        ):
            return FaceComparisonResult(
                status=FaceComparisonStatus.MODEL_MISMATCH,
                similarity_threshold=similarity_threshold,
                detection_confidence=analysis.detection_confidence,
                model_name=analysis.model_name,
                failure_reason=(
                    "Captured and reference embeddings are incompatible"
                ),
            )

        score = cosine_similarity(reference.embedding, analysis.embedding)
        matched = score >= similarity_threshold

        return FaceComparisonResult(
            status=(
                FaceComparisonStatus.MATCHED
                if matched
                else FaceComparisonStatus.NOT_MATCHED
            ),
            similarity_score=score,
            similarity_threshold=similarity_threshold,
            detection_confidence=analysis.detection_confidence,
            model_name=analysis.model_name,
            failure_reason=(
                None
                if matched
                else "Face similarity was below the required threshold"
            ),
        )


__all__ = [
    "FaceComparisonResult",
    "FaceComparisonService",
    "FaceComparisonStatus",
]
