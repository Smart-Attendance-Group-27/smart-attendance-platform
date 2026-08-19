import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from models.verification_config import VerificationConfig
from repositories.face_profile_repository import (
    FaceProfileRepository,
    StoredFaceEmbedding,
)
from repositories.verification_attempt_repository import (
    VerificationAttemptRecord,
    VerificationAttemptRepository,
)
from repositories.verification_config_repository import (
    VerificationConfigRepository,
)
from services.attendance_face_verification_service import (
    AttendanceFaceVerificationService,
    AttendanceFaceVerificationStatus,
)
from services.face_comparison_service import FaceComparisonService
from services.face_engine import FaceAnalysisResult, FaceAnalysisStatus


class FakeFaceEngine:
    def __init__(self, result: FaceAnalysisResult) -> None:
        self._result = result
        self.received_images: list[bytes] = []

    async def analyze(self, image: bytes) -> FaceAnalysisResult:
        self.received_images.append(image)
        return self._result


def create_dependencies() -> tuple[AsyncMock, AsyncMock, AsyncMock, AsyncMock]:
    session = AsyncMock(spec=AsyncSession)
    face_profile_repository = AsyncMock(spec=FaceProfileRepository)
    config_repository = AsyncMock(spec=VerificationConfigRepository)
    attempt_repository = AsyncMock(spec=VerificationAttemptRepository)
    attempt_repository.next_attempt_number.return_value = 1
    return session, face_profile_repository, config_repository, attempt_repository


def create_reference(
    *,
    student_id: UUID,
    embedding: tuple[float, ...] = (1.0, 0.0),
    model_name: str = "buffalo_l",
    model_version: str = "1",
) -> StoredFaceEmbedding:
    return StoredFaceEmbedding(
        profile_id=uuid4(),
        student_id=student_id,
        embedding=embedding,
        model_name=model_name,
        model_version=model_version,
        dimension=len(embedding),
    )


def create_config(threshold: str = "0.80") -> MagicMock:
    config = MagicMock(spec=VerificationConfig)
    config.id = uuid4()
    config.similarity_threshold = Decimal(threshold)
    return config


def successful_analysis(embedding: tuple[float, ...] = (1.0, 0.0)) -> FaceAnalysisResult:
    return FaceAnalysisResult.success(
        embedding=embedding,
        detection_confidence=0.98,
        model_name="buffalo_l",
    )


def create_service(
    *,
    session: AsyncMock,
    face_profile_repository: AsyncMock,
    config_repository: AsyncMock,
    attempt_repository: AsyncMock,
    engine: FakeFaceEngine,
    validated_at: datetime | None = None,
) -> AttendanceFaceVerificationService:
    fixed_time = validated_at or datetime(2026, 8, 19, tzinfo=timezone.utc)
    return AttendanceFaceVerificationService(
        session=session,
        face_comparison_service=FaceComparisonService(face_engine=engine, model_version="1"),
        face_profile_repository=face_profile_repository,
        verification_config_repository=config_repository,
        verification_attempt_repository=attempt_repository,
        clock=lambda: fixed_time,
    )


def test_passes_when_face_matches_an_in_progress_attempt() -> None:
    student_id = uuid4()
    session_id = uuid4()
    attempt_id = uuid4()
    reference = create_reference(student_id=student_id)
    config = create_config("0.80")
    session, profile_repository, config_repository, attempt_repository = create_dependencies()
    attempt_repository.find_in_progress.return_value = VerificationAttemptRecord(
        id=attempt_id, status="in_progress"
    )
    profile_repository.get_stored_embedding_for_comparison.return_value = reference
    config_repository.get_active.return_value = config
    service = create_service(
        session=session,
        face_profile_repository=profile_repository,
        config_repository=config_repository,
        attempt_repository=attempt_repository,
        engine=FakeFaceEngine(successful_analysis()),
    )

    result = asyncio.run(
        service.verify(session_id=session_id, student_id=student_id, captured_image=b"face")
    )

    assert result.status is AttendanceFaceVerificationStatus.PASSED
    assert result.verification_attempt_id == attempt_id
    assert result.attempt_number == 1
    attempt_repository.find_in_progress.assert_awaited_once_with(
        session_id=session_id, student_id=student_id
    )
    insert_kwargs = attempt_repository.insert_face_attempt.await_args.kwargs
    assert insert_kwargs["verification_attempt_id"] == attempt_id
    assert insert_kwargs["validation_status"] == "passed"
    assert insert_kwargs["liveness_passed"] is True
    assert insert_kwargs["quality_passed"] is True
    assert insert_kwargs["similarity_score"] == pytest.approx(Decimal("1"))
    session.commit.assert_awaited_once_with()
    session.rollback.assert_not_awaited()


def test_fails_when_similarity_is_below_threshold() -> None:
    student_id = uuid4()
    session_id = uuid4()
    attempt_id = uuid4()
    reference = create_reference(student_id=student_id)
    config = create_config("0.80")
    session, profile_repository, config_repository, attempt_repository = create_dependencies()
    attempt_repository.find_in_progress.return_value = VerificationAttemptRecord(
        id=attempt_id, status="in_progress"
    )
    profile_repository.get_stored_embedding_for_comparison.return_value = reference
    config_repository.get_active.return_value = config
    service = create_service(
        session=session,
        face_profile_repository=profile_repository,
        config_repository=config_repository,
        attempt_repository=attempt_repository,
        engine=FakeFaceEngine(successful_analysis(embedding=(0.0, 1.0))),
    )

    result = asyncio.run(
        service.verify(session_id=session_id, student_id=student_id, captured_image=b"face")
    )

    assert result.status is AttendanceFaceVerificationStatus.FAILED
    insert_kwargs = attempt_repository.insert_face_attempt.await_args.kwargs
    assert insert_kwargs["validation_status"] == "failed"
    assert insert_kwargs["liveness_passed"] is None
    assert insert_kwargs["quality_passed"] is None
    assert insert_kwargs["failure_reason"] is not None
    session.commit.assert_awaited_once_with()


def test_reports_not_found_when_no_verification_attempt_exists() -> None:
    student_id = uuid4()
    session_id = uuid4()
    session, profile_repository, config_repository, attempt_repository = create_dependencies()
    attempt_repository.find_in_progress.return_value = None
    service = create_service(
        session=session,
        face_profile_repository=profile_repository,
        config_repository=config_repository,
        attempt_repository=attempt_repository,
        engine=FakeFaceEngine(successful_analysis()),
    )

    result = asyncio.run(
        service.verify(session_id=session_id, student_id=student_id, captured_image=b"face")
    )

    assert result.status is AttendanceFaceVerificationStatus.VERIFICATION_ATTEMPT_NOT_FOUND
    profile_repository.get_stored_embedding_for_comparison.assert_not_awaited()
    attempt_repository.insert_face_attempt.assert_not_awaited()
    session.commit.assert_not_awaited()


@pytest.mark.parametrize("closed_status", ["failed", "completed"])
def test_reports_closed_when_verification_attempt_is_not_in_progress(
    closed_status: str,
) -> None:
    student_id = uuid4()
    session_id = uuid4()
    attempt_id = uuid4()
    session, profile_repository, config_repository, attempt_repository = create_dependencies()
    attempt_repository.find_in_progress.return_value = VerificationAttemptRecord(
        id=attempt_id, status=closed_status
    )
    service = create_service(
        session=session,
        face_profile_repository=profile_repository,
        config_repository=config_repository,
        attempt_repository=attempt_repository,
        engine=FakeFaceEngine(successful_analysis()),
    )

    result = asyncio.run(
        service.verify(session_id=session_id, student_id=student_id, captured_image=b"face")
    )

    assert result.status is AttendanceFaceVerificationStatus.VERIFICATION_ATTEMPT_CLOSED
    profile_repository.get_stored_embedding_for_comparison.assert_not_awaited()
    session.commit.assert_not_awaited()


def test_reports_profile_not_enrolled_without_running_analysis() -> None:
    student_id = uuid4()
    session_id = uuid4()
    attempt_id = uuid4()
    session, profile_repository, config_repository, attempt_repository = create_dependencies()
    attempt_repository.find_in_progress.return_value = VerificationAttemptRecord(
        id=attempt_id, status="in_progress"
    )
    profile_repository.get_stored_embedding_for_comparison.return_value = None
    engine = FakeFaceEngine(successful_analysis())
    service = create_service(
        session=session,
        face_profile_repository=profile_repository,
        config_repository=config_repository,
        attempt_repository=attempt_repository,
        engine=engine,
    )

    result = asyncio.run(
        service.verify(session_id=session_id, student_id=student_id, captured_image=b"face")
    )

    assert result.status is AttendanceFaceVerificationStatus.PROFILE_NOT_ENROLLED
    assert engine.received_images == []
    config_repository.get_active.assert_not_awaited()
    session.commit.assert_not_awaited()


def test_reports_no_active_config_without_running_analysis() -> None:
    student_id = uuid4()
    session_id = uuid4()
    attempt_id = uuid4()
    reference = create_reference(student_id=student_id)
    session, profile_repository, config_repository, attempt_repository = create_dependencies()
    attempt_repository.find_in_progress.return_value = VerificationAttemptRecord(
        id=attempt_id, status="in_progress"
    )
    profile_repository.get_stored_embedding_for_comparison.return_value = reference
    config_repository.get_active.return_value = None
    engine = FakeFaceEngine(successful_analysis())
    service = create_service(
        session=session,
        face_profile_repository=profile_repository,
        config_repository=config_repository,
        attempt_repository=attempt_repository,
        engine=engine,
    )

    result = asyncio.run(
        service.verify(session_id=session_id, student_id=student_id, captured_image=b"face")
    )

    assert result.status is AttendanceFaceVerificationStatus.NO_ACTIVE_CONFIG
    assert engine.received_images == []
    session.commit.assert_not_awaited()


@pytest.mark.parametrize(
    ("analysis_status", "face_count", "expected_status"),
    [
        (FaceAnalysisStatus.NO_FACE, 0, AttendanceFaceVerificationStatus.NO_FACE),
        (FaceAnalysisStatus.MULTIPLE_FACES, 2, AttendanceFaceVerificationStatus.MULTIPLE_FACES),
        (FaceAnalysisStatus.LOW_QUALITY, 1, AttendanceFaceVerificationStatus.LOW_QUALITY),
        (FaceAnalysisStatus.PROCESSING_FAILED, 0, AttendanceFaceVerificationStatus.PROCESSING_FAILED),
    ],
)
def test_maps_analysis_failures(
    analysis_status: FaceAnalysisStatus,
    face_count: int,
    expected_status: AttendanceFaceVerificationStatus,
) -> None:
    student_id = uuid4()
    session_id = uuid4()
    attempt_id = uuid4()
    reference = create_reference(student_id=student_id)
    config = create_config()
    session, profile_repository, config_repository, attempt_repository = create_dependencies()
    attempt_repository.find_in_progress.return_value = VerificationAttemptRecord(
        id=attempt_id, status="in_progress"
    )
    profile_repository.get_stored_embedding_for_comparison.return_value = reference
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
        attempt_repository=attempt_repository,
        engine=FakeFaceEngine(analysis),
    )

    result = asyncio.run(
        service.verify(session_id=session_id, student_id=student_id, captured_image=b"face")
    )

    assert result.status is expected_status
    session.commit.assert_awaited_once_with()


def test_rolls_back_unexpected_face_engine_error() -> None:
    student_id = uuid4()
    session_id = uuid4()
    attempt_id = uuid4()
    reference = create_reference(student_id=student_id)
    config = create_config()
    session, profile_repository, config_repository, attempt_repository = create_dependencies()
    attempt_repository.find_in_progress.return_value = VerificationAttemptRecord(
        id=attempt_id, status="in_progress"
    )
    profile_repository.get_stored_embedding_for_comparison.return_value = reference
    config_repository.get_active.return_value = config

    class FailingEngine:
        async def analyze(self, image: bytes) -> FaceAnalysisResult:
            raise RuntimeError("unexpected engine failure")

    service = create_service(
        session=session,
        face_profile_repository=profile_repository,
        config_repository=config_repository,
        attempt_repository=attempt_repository,
        engine=FailingEngine(),  # type: ignore[arg-type]
    )

    with pytest.raises(RuntimeError, match="unexpected engine failure"):
        asyncio.run(
            service.verify(session_id=session_id, student_id=student_id, captured_image=b"face")
        )

    attempt_repository.insert_face_attempt.assert_not_awaited()
    session.commit.assert_not_awaited()
    session.rollback.assert_awaited_once_with()
