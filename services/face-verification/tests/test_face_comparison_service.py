import asyncio
from uuid import uuid4

import pytest

from repositories.face_profile_repository import StoredFaceEmbedding
from services.face_comparison_service import (
    FaceComparisonService,
    FaceComparisonStatus,
)
from services.face_engine import FaceAnalysisResult, FaceAnalysisStatus


class FakeFaceEngine:
    def __init__(self, result: FaceAnalysisResult) -> None:
        self._result = result
        self.received_images: list[bytes] = []

    async def analyze(self, image: bytes) -> FaceAnalysisResult:
        self.received_images.append(image)
        return self._result


def create_reference(
    *,
    embedding: tuple[float, ...] = (1.0, 0.0),
    model_name: str = "buffalo_l",
    model_version: str = "1",
    dimension: int | None = None,
) -> StoredFaceEmbedding:
    return StoredFaceEmbedding(
        profile_id=uuid4(),
        student_id=uuid4(),
        embedding=embedding,
        model_name=model_name,
        model_version=model_version,
        dimension=dimension if dimension is not None else len(embedding),
    )


def successful_analysis(
    embedding: tuple[float, ...],
    *,
    model_name: str = "buffalo_l",
) -> FaceAnalysisResult:
    return FaceAnalysisResult.success(
        embedding=embedding,
        detection_confidence=0.98,
        model_name=model_name,
    )


def test_matching_embedding_passes_threshold() -> None:
    engine = FakeFaceEngine(successful_analysis((1.0, 0.0)))
    service = FaceComparisonService(face_engine=engine, model_version="1")

    result = asyncio.run(
        service.compare(
            reference=create_reference(),
            captured_image=b"captured-image",
            similarity_threshold=0.80,
        )
    )

    assert result.status is FaceComparisonStatus.MATCHED
    assert result.similarity_score == pytest.approx(1.0)
    assert engine.received_images == [b"captured-image"]


def test_non_matching_embedding_fails_threshold() -> None:
    service = FaceComparisonService(
        face_engine=FakeFaceEngine(successful_analysis((0.0, 1.0))),
        model_version="1",
    )

    result = asyncio.run(
        service.compare(
            reference=create_reference(),
            captured_image=b"captured-image",
            similarity_threshold=0.80,
        )
    )

    assert result.status is FaceComparisonStatus.NOT_MATCHED
    assert result.similarity_score == pytest.approx(0.0)


@pytest.mark.parametrize(
    ("analysis_status", "comparison_status"),
    [
        (FaceAnalysisStatus.NO_FACE, FaceComparisonStatus.NO_FACE),
        (
            FaceAnalysisStatus.MULTIPLE_FACES,
            FaceComparisonStatus.MULTIPLE_FACES,
        ),
        (FaceAnalysisStatus.LOW_QUALITY, FaceComparisonStatus.LOW_QUALITY),
        (
            FaceAnalysisStatus.PROCESSING_FAILED,
            FaceComparisonStatus.PROCESSING_FAILED,
        ),
    ],
)
def test_preserves_face_analysis_failure(
    analysis_status: FaceAnalysisStatus,
    comparison_status: FaceComparisonStatus,
) -> None:
    analysis = FaceAnalysisResult.failure(
        status=analysis_status,
        face_count=(2 if analysis_status is FaceAnalysisStatus.MULTIPLE_FACES else 0),
        reason="Analysis failed",
        model_name="buffalo_l",
    )
    service = FaceComparisonService(
        face_engine=FakeFaceEngine(analysis),
        model_version="1",
    )

    result = asyncio.run(
        service.compare(
            reference=create_reference(),
            captured_image=b"captured-image",
            similarity_threshold=0.80,
        )
    )

    assert result.status is comparison_status
    assert result.similarity_score is None


@pytest.mark.parametrize(
    ("reference", "analysis", "model_version"),
    [
        (
            create_reference(model_name="different-model"),
            successful_analysis((1.0, 0.0)),
            "1",
        ),
        (
            create_reference(model_version="2"),
            successful_analysis((1.0, 0.0)),
            "1",
        ),
        (
            create_reference(dimension=3),
            successful_analysis((1.0, 0.0)),
            "1",
        ),
    ],
)
def test_rejects_incompatible_embeddings(
    reference: StoredFaceEmbedding,
    analysis: FaceAnalysisResult,
    model_version: str,
) -> None:
    service = FaceComparisonService(
        face_engine=FakeFaceEngine(analysis),
        model_version=model_version,
    )

    result = asyncio.run(
        service.compare(
            reference=reference,
            captured_image=b"captured-image",
            similarity_threshold=0.80,
        )
    )

    assert result.status is FaceComparisonStatus.MODEL_MISMATCH
    assert result.similarity_score is None

