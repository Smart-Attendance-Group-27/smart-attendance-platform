import asyncio
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from models.face_profile import FaceProfile
from repositories.face_profile_repository import FaceProfileRepository
from services.face_engine import FaceAnalysisResult, FaceAnalysisStatus
from services.reference_enrollment_service import (
    ReferenceEnrollmentPersistenceError,
    ReferenceEnrollmentService,
    ReferenceEnrollmentStatus,
)


class FakeFaceEngine:
    """Return one configured result and record which image was analyzed."""

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


def create_profile(
    *,
    student_id: UUID,
    generation_status: str = "pending",
) -> MagicMock:
    profile = MagicMock(spec=FaceProfile)
    profile.id = uuid4()
    profile.student_id = student_id
    profile.embedding_generation_status = generation_status
    return profile


def successful_analysis() -> FaceAnalysisResult:
    return FaceAnalysisResult.success(
        embedding=(0.6, 0.8),
        detection_confidence=0.98,
        model_name="test-model",
    )


def create_dependencies() -> tuple[AsyncMock, AsyncMock]:
    session = AsyncMock(spec=AsyncSession)
    repository = AsyncMock(spec=FaceProfileRepository)
    return session, repository


def test_enrolls_new_student_reference_without_returning_embedding() -> None:
    student_id = uuid4()
    profile = create_profile(student_id=student_id)
    session, repository = create_dependencies()
    repository.get_by_student_id.return_value = None
    repository.create_pending_profile.return_value = profile
    repository.save_generated_embedding.return_value = profile
    engine = FakeFaceEngine(successful_analysis())
    service = ReferenceEnrollmentService(
        session=session,
        face_engine=engine,
        repository=repository,
    )

    result = asyncio.run(
        service.enroll(
            student_id=student_id,
            official_photo=b"official-photo",
        )
    )

    assert result.status is ReferenceEnrollmentStatus.SUCCESS
    assert result.student_id == student_id
    assert result.profile_id == profile.id
    assert result.detection_confidence == 0.98
    assert result.model_name == "test-model"
    assert not hasattr(result, "embedding")
    assert engine.received_images == [b"official-photo"]
    repository.create_pending_profile.assert_awaited_once_with(student_id)
    repository.save_generated_embedding.assert_awaited_once_with(
        profile.id,
        (0.6, 0.8),
        model_name="test-model",
        model_version="1",
    )
    session.commit.assert_awaited_once_with()
    session.rollback.assert_not_awaited()


def test_rejects_normal_reenrollment_of_generated_profile() -> None:
    student_id = uuid4()
    profile = create_profile(
        student_id=student_id,
        generation_status="generated",
    )
    session, repository = create_dependencies()
    repository.get_by_student_id.return_value = profile
    engine = FakeFaceEngine(successful_analysis())
    service = ReferenceEnrollmentService(
        session=session,
        face_engine=engine,
        repository=repository,
    )

    result = asyncio.run(
        service.enroll(
            student_id=student_id,
            official_photo=b"official-photo",
        )
    )

    assert result.status is ReferenceEnrollmentStatus.ALREADY_ENROLLED
    assert engine.received_images == []
    repository.save_generated_embedding.assert_not_awaited()
    session.commit.assert_not_awaited()
    session.rollback.assert_not_awaited()


def test_rejects_enrollment_of_revoked_profile() -> None:
    student_id = uuid4()
    profile = create_profile(
        student_id=student_id,
        generation_status="revoked",
    )
    session, repository = create_dependencies()
    repository.get_by_student_id.return_value = profile
    engine = FakeFaceEngine(successful_analysis())
    service = ReferenceEnrollmentService(
        session=session,
        face_engine=engine,
        repository=repository,
    )

    result = asyncio.run(
        service.enroll(
            student_id=student_id,
            official_photo=b"official-photo",
        )
    )

    assert result.status is ReferenceEnrollmentStatus.PROFILE_REVOKED
    assert engine.received_images == []
    repository.save_generated_embedding.assert_not_awaited()
    session.commit.assert_not_awaited()


def test_records_failed_generation_when_photo_has_no_face() -> None:
    student_id = uuid4()
    profile = create_profile(student_id=student_id)
    session, repository = create_dependencies()
    repository.get_by_student_id.return_value = profile
    repository.mark_generation_failed.return_value = profile
    engine = FakeFaceEngine(
        FaceAnalysisResult.failure(
            status=FaceAnalysisStatus.NO_FACE,
            face_count=0,
            reason="No face was detected",
            model_name="test-model",
        )
    )
    service = ReferenceEnrollmentService(
        session=session,
        face_engine=engine,
        repository=repository,
    )

    result = asyncio.run(
        service.enroll(
            student_id=student_id,
            official_photo=b"official-photo",
        )
    )

    assert result.status is ReferenceEnrollmentStatus.NO_FACE
    assert result.failure_reason == "No face was detected"
    repository.mark_generation_failed.assert_awaited_once_with(profile.id)
    repository.save_generated_embedding.assert_not_awaited()
    session.commit.assert_awaited_once_with()
    session.rollback.assert_not_awaited()


def test_rolls_back_when_profile_disappears_while_saving() -> None:
    student_id = uuid4()
    profile = create_profile(student_id=student_id)
    session, repository = create_dependencies()
    repository.get_by_student_id.return_value = profile
    repository.save_generated_embedding.return_value = None
    service = ReferenceEnrollmentService(
        session=session,
        face_engine=FakeFaceEngine(successful_analysis()),
        repository=repository,
    )

    with pytest.raises(
        ReferenceEnrollmentPersistenceError,
        match="Face profile disappeared while saving the embedding",
    ):
        asyncio.run(
            service.enroll(
                student_id=student_id,
                official_photo=b"official-photo",
            )
        )

    session.commit.assert_not_awaited()
    session.rollback.assert_awaited_once_with()


def test_rolls_back_unexpected_face_engine_error() -> None:
    student_id = uuid4()
    profile = create_profile(student_id=student_id)
    session, repository = create_dependencies()
    repository.get_by_student_id.return_value = profile
    engine = FakeFaceEngine(
        successful_analysis(),
        error=RuntimeError("unexpected engine failure"),
    )
    service = ReferenceEnrollmentService(
        session=session,
        face_engine=engine,
        repository=repository,
    )

    with pytest.raises(RuntimeError, match="unexpected engine failure"):
        asyncio.run(
            service.enroll(
                student_id=student_id,
                official_photo=b"official-photo",
            )
        )

    session.commit.assert_not_awaited()
    session.rollback.assert_awaited_once_with()
