import asyncio
import math
import threading
import time
from types import SimpleNamespace
from typing import Any

import pytest

from adapters.insightface_engine import InsightFaceEngine
from services.face_engine import FaceAnalysisStatus, FaceEngine


class FakeAnalyzer:
    """Return configured faces without loading a real InsightFace model."""

    def __init__(self,faces: list[Any] | None = None,error: Exception | None = None,) -> None:
        self._faces = faces or []
        self._error = error
        self.received_image: Any | None = None

    def get(self, image: Any) -> list[Any]:
        self.received_image = image

        if self._error is not None:
            raise self._error

        return self._faces


class ConcurrentTrackingAnalyzer:
    """Record how many model calls are active at the same time."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._active_calls = 0
        self.maximum_active_calls = 0

    def get(self, image: Any) -> list[Any]:
        with self._lock:
            self._active_calls += 1
            self.maximum_active_calls = max(self.maximum_active_calls,self._active_calls,)

        # Keep this call active briefly so concurrent access would be visible.
        time.sleep(0.02)

        with self._lock:
            self._active_calls -= 1

        return [SimpleNamespace(det_score=0.98,normed_embedding=(1.0, 0.0),)]


def create_engine(analyzer: FakeAnalyzer,*,decoder=lambda _: "decoded-image",) -> InsightFaceEngine:
    return InsightFaceEngine(
        analyzer=analyzer,
        image_decoder=decoder,
        model_name="test-model",
        minimum_detection_confidence=0.60,
    )


def test_satisfies_face_engine_contract() -> None:
    engine = create_engine(FakeAnalyzer())

    assert isinstance(engine, FaceEngine)


def test_rejects_empty_image_before_running_model() -> None:
    analyzer = FakeAnalyzer()
    engine = create_engine(analyzer)

    result = asyncio.run(engine.analyze(b""))

    assert result.status is FaceAnalysisStatus.PROCESSING_FAILED
    assert result.failure_reason == "Image is empty"
    assert analyzer.received_image is None


def test_returns_processing_failure_for_invalid_encoded_image() -> None:
    analyzer = FakeAnalyzer()
    engine = create_engine(analyzer, decoder=lambda _: None)

    result = asyncio.run(engine.analyze(b"invalid-image"))

    assert result.status is FaceAnalysisStatus.PROCESSING_FAILED
    assert result.failure_reason == "Image could not be decoded"
    assert analyzer.received_image is None


def test_returns_no_face_when_analyzer_detects_nothing() -> None:
    engine = create_engine(FakeAnalyzer())

    result = asyncio.run(engine.analyze(b"encoded-image"))

    assert result.status is FaceAnalysisStatus.NO_FACE
    assert result.face_count == 0
    assert result.embedding is None


def test_returns_multiple_faces_when_more_than_one_is_detected() -> None:
    faces = [
        SimpleNamespace(det_score=0.95, normed_embedding=(1.0, 0.0)),
        SimpleNamespace(det_score=0.90, normed_embedding=(0.0, 1.0)),
    ]
    engine = create_engine(FakeAnalyzer(faces))

    result = asyncio.run(engine.analyze(b"encoded-image"))

    assert result.status is FaceAnalysisStatus.MULTIPLE_FACES
    assert result.face_count == 2
    assert result.embedding is None


def test_returns_low_quality_for_low_detection_confidence() -> None:
    face = SimpleNamespace(det_score=0.40,normed_embedding=(1.0, 0.0),)
    engine = create_engine(FakeAnalyzer([face]))

    result = asyncio.run(engine.analyze(b"encoded-image"))

    assert result.status is FaceAnalysisStatus.LOW_QUALITY
    assert result.face_count == 1
    assert result.detection_confidence == 0.40
    assert result.embedding is None


def test_returns_normalized_embedding_for_one_valid_face() -> None:
    face = SimpleNamespace(det_score=0.98,normed_embedding=(3.0, 4.0),)
    engine = create_engine(FakeAnalyzer([face]))

    result = asyncio.run(engine.analyze(b"encoded-image"))

    assert result.status is FaceAnalysisStatus.SUCCESS
    assert result.embedding == pytest.approx((0.6, 0.8))
    assert result.detection_confidence == 0.98
    assert result.model_name == "test-model"
    assert math.isclose(
        math.sqrt(sum(value * value for value in result.embedding or ())),
        1.0,
    )


def test_hides_internal_analyzer_error_from_result() -> None:
    analyzer = FakeAnalyzer(error=RuntimeError("internal model detail"))
    engine = create_engine(analyzer)

    result = asyncio.run(engine.analyze(b"encoded-image"))

    assert result.status is FaceAnalysisStatus.PROCESSING_FAILED
    assert result.failure_reason == "Face analysis failed"
    assert "internal model detail" not in result.failure_reason


def test_limits_shared_model_to_one_inference_at_a_time() -> None:
    analyzer = ConcurrentTrackingAnalyzer()
    engine = InsightFaceEngine(
        analyzer=analyzer,
        image_decoder=lambda _: "decoded-image",
        model_name="test-model",
        max_concurrent_inferences=1,
    )

    async def analyze_three_images() -> list[Any]:
        return await asyncio.gather(
            engine.analyze(b"image-one"),
            engine.analyze(b"image-two"),
            engine.analyze(b"image-three"),
        )

    results = asyncio.run(analyze_three_images())

    assert all(result.status is FaceAnalysisStatus.SUCCESS for result in results)
    assert analyzer.maximum_active_calls == 1
