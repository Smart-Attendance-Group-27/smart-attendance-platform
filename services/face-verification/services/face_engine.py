from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, runtime_checkable


# Acceptable outcomes returned after analyzing a captured image.
class FaceAnalysisStatus(StrEnum):
    SUCCESS = "success"
    NO_FACE = "no_face"
    MULTIPLE_FACES = "multiple_faces"
    LOW_QUALITY = "low_quality"
    PROCESSING_FAILED = "processing_failed"


# Immutable data returned by any face-engine implementation.
@dataclass(frozen=True, slots=True)
class FaceAnalysisResult:
    status: FaceAnalysisStatus
    face_count: int
    embedding: tuple[float, ...] | None = None
    detection_confidence: float | None = None
    model_name: str | None = None
    failure_reason: str | None = None

    def __post_init__(self) -> None:
        # Reject result combinations that would be unsafe or contradictory.
        if self.face_count < 0:
            raise ValueError("Face count cannot be negative")

        if (self.detection_confidence is not None and not 0 <= self.detection_confidence <= 1):
            raise ValueError("Detection confidence must be between 0 and 1")

        if self.status is FaceAnalysisStatus.SUCCESS:
            if self.face_count != 1:
                raise ValueError("Successful analysis must contain exactly one face")
            if not self.embedding:
                raise ValueError("Successful analysis must contain an embedding")
            if self.detection_confidence is None:
                raise ValueError("Successful analysis must contain detection confidence")
            if not self.model_name:
                raise ValueError("Successful analysis must contain the model name")
            
        elif self.embedding is not None:
            raise ValueError("Failed analysis must not contain an embedding")

    # constructor for a valid successful result.
    @classmethod
    def success(cls,*,embedding: tuple[float, ...],detection_confidence: float,model_name: str,) -> "FaceAnalysisResult":
        return cls(
            status=FaceAnalysisStatus.SUCCESS,
            face_count=1,
            embedding=embedding,
            detection_confidence=detection_confidence,
            model_name=model_name,
        )

    # constructor for no-face, quality, or processing failures.
    @classmethod
    def failure(cls,*,status: FaceAnalysisStatus,face_count: int,reason: str,detection_confidence: float | None = None,model_name: str | None = None,) -> "FaceAnalysisResult":
        if status is FaceAnalysisStatus.SUCCESS:
            raise ValueError("Use success() for successful analysis")

        return cls(
            status=status,
            face_count=face_count,
            detection_confidence=detection_confidence,
            model_name=model_name,
            failure_reason=reason,
        )


# Contract that both fake and real InsightFace engines must follow.
@runtime_checkable
class FaceEngine(Protocol):
    async def analyze(self, image: bytes) -> FaceAnalysisResult:
        """Analyze encoded image bytes and return one normalized embedding."""

        ...
