import asyncio

import pytest

from services.face_engine import (
    FaceAnalysisResult,
    FaceAnalysisStatus,
    FaceEngine,
)


# Lightweight engine used to test the contract without loading InsightFace.
class FakeFaceEngine:
    async def analyze(self, image: bytes) -> FaceAnalysisResult:
        # Return a predictable failure when the caller provides no image data.
        if not image:
            return FaceAnalysisResult.failure(
                status=FaceAnalysisStatus.PROCESSING_FAILED,
                face_count=0,
                reason="Image is empty",
            )

        # Return a small deterministic embedding for every non-empty image.
        return FaceAnalysisResult.success(
            embedding=(0.1, 0.2, 0.3),
            detection_confidence=0.98,
            model_name="test-model",
        )


# A valid success result must contain all data required for comparison.
def test_success_result_contains_normalized_analysis_output() -> None:
    result = FaceAnalysisResult.success(
        embedding=(0.1, 0.2, 0.3),
        detection_confidence=0.98,
        model_name="test-model",
    )

    assert result.status is FaceAnalysisStatus.SUCCESS
    assert result.face_count == 1
    assert result.embedding == (0.1, 0.2, 0.3)
    assert result.detection_confidence == 0.98
    assert result.model_name == "test-model"
    assert result.failure_reason is None


# Failure results must explain the problem and must not expose an embedding.
def test_failure_result_does_not_contain_embedding() -> None:
    result = FaceAnalysisResult.failure(
        status=FaceAnalysisStatus.NO_FACE,
        face_count=0,
        reason="No face detected",
        model_name="test-model",
    )

    assert result.status is FaceAnalysisStatus.NO_FACE
    assert result.embedding is None
    assert result.failure_reason == "No face detected"


# Two detected faces cannot represent one successful verification result.
def test_rejects_success_without_exactly_one_face() -> None:
    with pytest.raises(ValueError,match="Successful analysis must contain exactly one face",):
        FaceAnalysisResult(
            status=FaceAnalysisStatus.SUCCESS,
            face_count=2,
            embedding=(0.1, 0.2),
            detection_confidence=0.98,
            model_name="test-model",
        )


# An embedding is trusted only when the overall analysis succeeded.
def test_rejects_embedding_on_failed_analysis() -> None:
    with pytest.raises(ValueError,match="Failed analysis must not contain an embedding",):
        FaceAnalysisResult(
            status=FaceAnalysisStatus.LOW_QUALITY,
            face_count=1,
            embedding=(0.1, 0.2),
            failure_reason="Image quality is too low",
        )


def test_fake_engine_satisfies_contract() -> None:
    engine = FakeFaceEngine()

    assert isinstance(engine, FaceEngine)

    result = asyncio.run(engine.analyze(b"encoded-image"))

    assert result.status is FaceAnalysisStatus.SUCCESS
