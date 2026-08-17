from __future__ import annotations

import asyncio
import math
from collections.abc import Callable, Sequence
from typing import Any, Protocol

from core.config import Settings
from services.face_engine import (FaceAnalysisResult,FaceAnalysisStatus,FaceEngine,)


__all__ = [
    "InsightFaceAnalyzer",
    "InsightFaceEngine",
    "create_configured_insightface_engine",
    "create_insightface_engine",
]


def create_configured_insightface_engine(
    settings: Settings,
) -> InsightFaceEngine:
    """Create the shared model using the service's single configuration."""

    return create_insightface_engine(
        model_name=settings.face_model_name,
        providers=(settings.face_execution_provider,),
        context_id=settings.face_context_id,
        detection_size=(
            settings.face_detection_size,
            settings.face_detection_size,
        ),
        minimum_detection_confidence=(
            settings.face_minimum_detection_confidence
        ),
        max_concurrent_inferences=settings.face_max_concurrent_inferences,
    )

def create_insightface_engine(
    *,
    model_name: str,
    providers: Sequence[str],
    context_id: int,
    detection_size: tuple[int, int],
    minimum_detection_confidence: float,
    max_concurrent_inferences: int,
) -> InsightFaceEngine:

    try:
        import cv2
        import numpy as np
        from insightface.app import FaceAnalysis
        
    except ImportError as error:
        raise RuntimeError(
            "InsightFace dependencies are not installed. "
            "Install the face-verification requirements first."
        ) from error

    # FaceAnalysis performs detection, landmark-based alignment, and embedding generation.
    analyzer = FaceAnalysis(name=model_name,providers=list(providers),)
    analyzer.prepare(ctx_id=context_id,det_size=detection_size,)

    def decode_image(image: bytes) -> Any | None:
        encoded_image = np.frombuffer(image, dtype=np.uint8)

        if encoded_image.size == 0:
            return None

        return cv2.imdecode(encoded_image, cv2.IMREAD_COLOR)

    return InsightFaceEngine(
        analyzer=analyzer,
        image_decoder=decode_image,
        model_name=model_name,
        minimum_detection_confidence=minimum_detection_confidence,
        max_concurrent_inferences=max_concurrent_inferences,
    )

# InsightFace's FaceAnalysis object follows this small interface.
class InsightFaceAnalyzer(Protocol):
    def get(self, image: Any) -> Sequence[Any]:
        """Detect faces and attach recognition embeddings to them."""

        ...

ImageDecoder = Callable[[bytes], Any | None]


class InsightFaceEngine(FaceEngine):
    """Adapt InsightFace output to the application's FaceEngine contract."""

    def __init__(self,*,analyzer: InsightFaceAnalyzer,image_decoder: ImageDecoder,model_name: str,
        minimum_detection_confidence: float,max_concurrent_inferences: int,) -> None:
        if not model_name.strip():
            raise ValueError("Model name cannot be blank")

        if not 0 <= minimum_detection_confidence <= 1:
            raise ValueError("Minimum detection confidence must be between 0 and 1")

        if max_concurrent_inferences < 1:
            raise ValueError("Maximum concurrent inferences must be at least 1")

        self._analyzer = analyzer
        self._image_decoder = image_decoder
        self._model_name = model_name
        self._minimum_detection_confidence = (minimum_detection_confidence)
        self._inference_semaphore = asyncio.Semaphore(max_concurrent_inferences)

    async def analyze(self, image: bytes) -> FaceAnalysisResult:
        """Decode one image and return one normalized face embedding."""

        if not image:
            return self._failure(
                status=FaceAnalysisStatus.PROCESSING_FAILED,
                face_count=0,
                reason="Image is empty",
            )

        try:
            # Image decoding is synchronous, so it also runs outside FastAPI's event-loop thread.
            decoded_image = await asyncio.to_thread(self._image_decoder,image,)
        except Exception:
            return self._failure(status=FaceAnalysisStatus.PROCESSING_FAILED,face_count=0,reason="Image could not be decoded",)

        if decoded_image is None:
            return self._failure(status=FaceAnalysisStatus.PROCESSING_FAILED,face_count=0,reason="Image could not be decoded",)

        try:
            # semaphore limits how many calls use this model simultaneously.
            async with self._inference_semaphore:
                faces = await asyncio.to_thread(self._analyzer.get,decoded_image,)

        except Exception:
            # Do not return internal model details to an API caller.
            return self._failure(status=FaceAnalysisStatus.PROCESSING_FAILED,face_count=0,reason="Face analysis failed",)

        face_count = len(faces)

        if face_count == 0:
            return self._failure(status=FaceAnalysisStatus.NO_FACE,face_count=0,reason="No face was detected",)

        if face_count > 1:
            return self._failure(status=FaceAnalysisStatus.MULTIPLE_FACES,face_count=face_count,reason="More than one face was detected",)

        face = faces[0]
        detection_confidence = self._read_detection_confidence(face)

        if detection_confidence is None:
            return self._failure(status=FaceAnalysisStatus.PROCESSING_FAILED,face_count=1,reason="Face detection confidence is invalid",)

        # Detection confidence is only an initial quality check.
        if detection_confidence < self._minimum_detection_confidence:
            return self._failure(status=FaceAnalysisStatus.LOW_QUALITY,face_count=1,reason="Face detection confidence is too low",detection_confidence=detection_confidence,)

        embedding = self._read_normalized_embedding(face)

        if embedding is None:
            return self._failure(status=FaceAnalysisStatus.PROCESSING_FAILED,face_count=1,reason="Face embedding is invalid",detection_confidence=detection_confidence,)

        return FaceAnalysisResult.success(embedding=embedding,detection_confidence=detection_confidence,model_name=self._model_name,)

    def _failure(self,*,status: FaceAnalysisStatus,face_count: int,reason: str,detection_confidence: float | None = None,) -> FaceAnalysisResult:
        """Create a failure result that still identifies the selected model."""

        return FaceAnalysisResult.failure(
            status=status,
            face_count=face_count,
            reason=reason,
            detection_confidence=detection_confidence,
            model_name=self._model_name,
        )

    @staticmethod
    def _read_detection_confidence(face: Any) -> float | None:
        """Read and validate InsightFace's det_score value."""

        try:
            confidence = float(face.det_score)
        except (AttributeError, TypeError, ValueError):
            return None

        if not math.isfinite(confidence) or not 0 <= confidence <= 1:
            return None

        return confidence

    @staticmethod
    def _read_normalized_embedding(face: Any,) -> tuple[float, ...] | None:
        """Read the embedding and normalize it to unit length defensively."""

        try:
            raw_embedding = face.normed_embedding

            if raw_embedding is None:
                return None

            embedding = tuple(float(value) for value in raw_embedding)

        except (AttributeError, TypeError, ValueError):
            return None

        if not embedding or not all(math.isfinite(value) for value in embedding):
            return None

        magnitude = math.sqrt(sum(value * value for value in embedding))

        if not math.isfinite(magnitude) or magnitude <= 0:
            return None

        return tuple(value / magnitude for value in embedding)
