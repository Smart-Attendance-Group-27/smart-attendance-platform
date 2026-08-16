import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from models.face_profile import FaceProfile
from models.verification_config import VerificationConfig
from repositories.face_profile_repository import (
    FaceProfileRepository,
    StoredFaceEmbedding,
)
from repositories.verification_config_repository import (
    VerificationConfigRepository,
)
from services.face_engine import FaceAnalysisResult, FaceAnalysisStatus
from services.readiness_verification_service import (
    ReadinessVerificationPersistenceError,
    ReadinessVerificationService,
    ReadinessVerificationStatus,
)


class FakeFaceEngine:
    def __init__(
        self,
        result: FaceAnalysisResult,
        *,
        error: Exception | None = None,
    ) -> None:
        self._result = result
        self._error = error
        self.received_images: list[bytes] = []

    async def analyze(self, image: bytes) -> FaceAnalysisResult:
        self.received_images.append(image)

        if self._error is not None:
            raise self._error

        return self._result


def create_dependencies() -> tuple[AsyncMock, AsyncMock, AsyncMock]:
    session = AsyncMock(spec=AsyncSession)
    face_profile_repository = AsyncMock(spec=FaceProfileRepository)
    config_repository = AsyncMock(spec=VerificationConfigRepository)
    return session, face_profile_repository, config_repository


def create_reference(
    *,
    student_id: UUID,
    embedding: tuple[float, ...] = (1.0, 0.0),
    model_name: str = "buffalo_l",
    model_version: str = "1",
    dimension: int | None = None,
) -> StoredFaceEmbedding:
    return StoredFaceEmbedding(
        profile_id=uuid4(),
        student_id=student_id,
        embedding=embedding,
        model_name=model_name,
        model_version=model_version,
        dimension=dimension if dimension is not None else len(embedding),
    )


def create_config(threshold: str = "0.80") -> MagicMock:
    config = MagicMock(spec=VerificationConfig)
    config.id = uuid4()
    config.similarity_threshold = Decimal(threshold)
    return config


def successful_analysis(
    *,
    embedding: tuple[float, ...] = (1.0, 0.0),
    model_name: str = "buffalo_l",
) -> FaceAnalysisResult:
    return FaceAnalysisResult.success(
        embedding=embedding,
        detection_confidence=0.98,
        model_name=model_name,
    )


def create_service(
    *,
    session: AsyncMock,
    face_profile_repository: AsyncMock,
    config_repository: AsyncMock,
    engine: FakeFaceEngine,
    checked_at: datetime | None = None,
    model_version: str = "1",
) -> ReadinessVerificationService:
    fixed_time = checked_at or datetime(2026, 8, 16, tzinfo=timezone.utc)
    return ReadinessVerificationService(
        session=session,
        face_engine=engine,
        face_profile_repository=face_profile_repository,
        verification_config_repository=config_repository,
        model_version=model_version,
        clock=lambda: fixed_time,
    )


def test_matching_face_passes_without_returning_embeddings() -> None:
    student_id = uuid4()
    checked_at = datetime(2026, 8, 16, 12, 30, tzinfo=timezone.utc)
    reference = create_reference(student_id=student_id)
    config = create_config("0.80")
    session, profile_repository, config_repository = create_dependencies()
    profile_repository.get_stored_embedding_for_comparison.return_value = reference
    profile_repository.update_readiness_result.return_value = MagicMock(
        spec=FaceProfile
    )
    config_repository.get_active.return_value = config
    engine = FakeFaceEngine(successful_analysis())
    service = create_service(
        session=session,
        face_profile_repository=profile_repository,
        config_repository=config_repository,
        engine=engine,
        checked_at=checked_at,
    )

    result = asyncio.run(
        service.verify(
            student_id=student_id,
            captured_image=b"captured-face",
        )
    )

    assert result.status is ReadinessVerificationStatus.PASSED
    assert result.student_id == student_id
    assert result.profile_id == reference.profile_id
    assert result.verification_config_id == config.id
    assert result.similarity_score == pytest.approx(1.0)
    assert result.similarity_threshold == pytest.approx(0.80)
    assert result.detection_confidence == pytest.approx(0.98)
    assert not hasattr(result, "embedding")
    assert engine.received_images == [b"captured-face"]
    profile_repository.update_readiness_result.assert_awaited_once_with(
        reference.profile_id,
        status="passed",
        verification_config_id=config.id,
        checked_at=checked_at,
    )
    session.commit.assert_awaited_once_with()
    session.rollback.assert_not_awaited()


def test_similarity_below_threshold_fails() -> None:
    student_id = uuid4()
    reference = create_reference(student_id=student_id)
    config = create_config("0.80")
    session, profile_repository, config_repository = create_dependencies()
    profile_repository.get_stored_embedding_for_comparison.return_value = reference
    profile_repository.update_readiness_result.return_value = MagicMock(
        spec=FaceProfile
    )
    config_repository.get_active.return_value = config
    service = create_service(
        session=session,
        face_profile_repository=profile_repository,
        config_repository=config_repository,
        engine=FakeFaceEngine(
            successful_analysis(embedding=(0.0, 1.0))
        ),
    )

    result = asyncio.run(
        service.verify(student_id=student_id, captured_image=b"captured-face")
    )

    assert result.status is ReadinessVerificationStatus.FAILED
    assert result.similarity_score == pytest.approx(0.0)
    assert result.failure_reason == (
        "Face similarity was below the required threshold"
    )
    assert profile_repository.update_readiness_result.await_args.kwargs[
        "status"
    ] == "failed"
    session.commit.assert_awaited_once_with()


def test_returns_profile_not_enrolled_without_running_analysis() -> None:
    student_id = uuid4()
    session, profile_repository, config_repository = create_dependencies()
    profile_repository.get_stored_embedding_for_comparison.return_value = None
    engine = FakeFaceEngine(successful_analysis())
    service = create_service(
        session=session,
        face_profile_repository=profile_repository,
        config_repository=config_repository,
        engine=engine,
    )

    result = asyncio.run(
        service.verify(student_id=student_id, captured_image=b"captured-face")
    )

    assert result.status is ReadinessVerificationStatus.PROFILE_NOT_ENROLLED
    assert result.profile_id is None
    assert engine.received_images == []
    config_repository.get_active.assert_not_awaited()
    profile_repository.update_readiness_result.assert_not_awaited()
    session.commit.assert_not_awaited()


def test_returns_no_active_config_without_running_analysis() -> None:
    student_id = uuid4()
    reference = create_reference(student_id=student_id)
    session, profile_repository, config_repository = create_dependencies()
    profile_repository.get_stored_embedding_for_comparison.return_value = reference
    config_repository.get_active.return_value = None
    engine = FakeFaceEngine(successful_analysis())
    service = create_service(
        session=session,
        face_profile_repository=profile_repository,
        config_repository=config_repository,
        engine=engine,
    )

    result = asyncio.run(
        service.verify(student_id=student_id, captured_image=b"captured-face")
    )

    assert result.status is ReadinessVerificationStatus.NO_ACTIVE_CONFIG
    assert result.profile_id == reference.profile_id
    assert engine.received_images == []
    profile_repository.update_readiness_result.assert_not_awaited()
    session.commit.assert_not_awaited()


@pytest.mark.parametrize(
    ("analysis_status", "face_count", "expected_status"),
    [
        (
            FaceAnalysisStatus.NO_FACE,
            0,
            ReadinessVerificationStatus.NO_FACE,
        ),
        (
            FaceAnalysisStatus.MULTIPLE_FACES,
            2,
            ReadinessVerificationStatus.MULTIPLE_FACES,
        ),
        (
            FaceAnalysisStatus.LOW_QUALITY,
            1,
            ReadinessVerificationStatus.LOW_QUALITY,
        ),
        (
            FaceAnalysisStatus.PROCESSING_FAILED,
            0,
            ReadinessVerificationStatus.PROCESSING_FAILED,
        ),
    ],
)
def test_maps_analysis_failures_and_records_failed_readiness(
    analysis_status: FaceAnalysisStatus,
    face_count: int,
    expected_status: ReadinessVerificationStatus,
) -> None:
    student_id = uuid4()
    reference = create_reference(student_id=student_id)
    config = create_config()
    session, profile_repository, config_repository = create_dependencies()
    profile_repository.get_stored_embedding_for_comparison.return_value = reference
    profile_repository.update_readiness_result.return_value = MagicMock(
        spec=FaceProfile
    )
    config_repository.get_active.return_value = config
    analysis = FaceAnalysisResult.failure(
        status=analysis_status,
        face_count=face_count,
        reason="Capture could not be verified",
        model_name="buffalo_l",
    )
    service = create_service(
        session=session,
        face_profile_repository=profile_repository,
        config_repository=config_repository,
        engine=FakeFaceEngine(analysis),
    )

    result = asyncio.run(
        service.verify(student_id=student_id, captured_image=b"captured-face")
    )

    assert result.status is expected_status
    assert result.similarity_score is None
    assert result.failure_reason == "Capture could not be verified"
    assert profile_repository.update_readiness_result.await_args.kwargs[
        "status"
    ] == "failed"
    session.commit.assert_awaited_once_with()


@pytest.mark.parametrize(
    ("reference", "analysis", "model_version"),
    [
        (
            create_reference(
                student_id=UUID(int=1),
                model_name="different-model",
            ),
            successful_analysis(),
            "1",
        ),
        (
            create_reference(
                student_id=UUID(int=1),
                model_version="2",
            ),
            successful_analysis(),
            "1",
        ),
        (
            create_reference(
                student_id=UUID(int=1),
                dimension=3,
            ),
            successful_analysis(),
            "1",
        ),
    ],
)
def test_model_or_dimension_mismatch_fails_safely(
    reference: StoredFaceEmbedding,
    analysis: FaceAnalysisResult,
    model_version: str,
) -> None:
    student_id = reference.student_id
    config = create_config()
    session, profile_repository, config_repository = create_dependencies()
    profile_repository.get_stored_embedding_for_comparison.return_value = reference
    profile_repository.update_readiness_result.return_value = MagicMock(
        spec=FaceProfile
    )
    config_repository.get_active.return_value = config
    service = create_service(
        session=session,
        face_profile_repository=profile_repository,
        config_repository=config_repository,
        engine=FakeFaceEngine(analysis),
        model_version=model_version,
    )

    result = asyncio.run(
        service.verify(student_id=student_id, captured_image=b"captured-face")
    )

    assert result.status is ReadinessVerificationStatus.MODEL_MISMATCH
    assert result.similarity_score is None
    assert profile_repository.update_readiness_result.await_args.kwargs[
        "status"
    ] == "failed"
    session.commit.assert_awaited_once_with()


def test_rolls_back_when_readiness_update_does_not_find_profile() -> None:
    student_id = uuid4()
    reference = create_reference(student_id=student_id)
    config = create_config()
    session, profile_repository, config_repository = create_dependencies()
    profile_repository.get_stored_embedding_for_comparison.return_value = reference
    profile_repository.update_readiness_result.return_value = None
    config_repository.get_active.return_value = config
    service = create_service(
        session=session,
        face_profile_repository=profile_repository,
        config_repository=config_repository,
        engine=FakeFaceEngine(successful_analysis()),
    )

    with pytest.raises(
        ReadinessVerificationPersistenceError,
        match="Face profile disappeared while recording readiness",
    ):
        asyncio.run(
            service.verify(
                student_id=student_id,
                captured_image=b"captured-face",
            )
        )

    session.commit.assert_not_awaited()
    session.rollback.assert_awaited_once_with()


def test_rolls_back_unexpected_face_engine_error() -> None:
    student_id = uuid4()
    reference = create_reference(student_id=student_id)
    config = create_config()
    session, profile_repository, config_repository = create_dependencies()
    profile_repository.get_stored_embedding_for_comparison.return_value = reference
    config_repository.get_active.return_value = config
    service = create_service(
        session=session,
        face_profile_repository=profile_repository,
        config_repository=config_repository,
        engine=FakeFaceEngine(
            successful_analysis(),
            error=RuntimeError("unexpected engine failure"),
        ),
    )

    with pytest.raises(RuntimeError, match="unexpected engine failure"):
        asyncio.run(
            service.verify(
                student_id=student_id,
                captured_image=b"captured-face",
            )
        )

    profile_repository.update_readiness_result.assert_not_awaited()
    session.commit.assert_not_awaited()
    session.rollback.assert_awaited_once_with()
