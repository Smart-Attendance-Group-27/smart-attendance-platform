import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from models.face_profile import FaceProfile
from repositories.face_profile_repository import FaceProfileRepository


def create_session() -> AsyncMock:
    return AsyncMock(spec=AsyncSession)


def test_gets_face_profile_by_id() -> None:
    session = create_session()
    profile_id = uuid4()
    profile = MagicMock(spec=FaceProfile)
    session.get.return_value = profile
    repository = FaceProfileRepository(session)

    result = asyncio.run(repository.get_by_id(profile_id))

    assert result is profile
    session.get.assert_awaited_once_with(FaceProfile, profile_id)
    session.commit.assert_not_awaited()


def test_gets_face_profile_by_student_id() -> None:
    session = create_session()
    query_result = MagicMock()
    profile = MagicMock(spec=FaceProfile)
    query_result.scalar_one_or_none.return_value = profile
    session.execute.return_value = query_result
    repository = FaceProfileRepository(session)

    result = asyncio.run(repository.get_by_student_id(uuid4()))

    assert result is profile
    session.execute.assert_awaited_once()
    session.commit.assert_not_awaited()


def test_creates_pending_face_profile() -> None:
    session = create_session()
    student_id = uuid4()
    repository = FaceProfileRepository(session)

    profile = asyncio.run(repository.create_pending_profile(student_id))

    assert profile.student_id == student_id
    assert profile.embedding_generation_status == "pending"
    assert profile.readiness_status == "not_checked"
    session.add.assert_called_once_with(profile)
    session.flush.assert_awaited_once_with()
    session.commit.assert_not_awaited()


def test_saves_generated_embedding() -> None:
    session = create_session()
    query_result = MagicMock()
    profile = MagicMock(spec=FaceProfile)
    query_result.scalar_one_or_none.return_value = profile
    session.execute.return_value = query_result
    repository = FaceProfileRepository(session)

    result = asyncio.run(
        repository.save_generated_embedding(
            uuid4(),
            [0.1, 0.2, 0.3],
            generated_at=datetime.now(timezone.utc),
        )
    )

    assert result is profile
    session.execute.assert_awaited_once()
    session.commit.assert_not_awaited()


def test_rejects_empty_embedding_without_querying_database() -> None:
    session = create_session()
    repository = FaceProfileRepository(session)

    with pytest.raises(
        ValueError,
        match="Embedding must contain at least one value",
    ):
        asyncio.run(repository.save_generated_embedding(uuid4(), []))

    session.execute.assert_not_awaited()


def test_marks_embedding_generation_as_failed() -> None:
    session = create_session()
    query_result = MagicMock()
    profile = MagicMock(spec=FaceProfile)
    query_result.scalar_one_or_none.return_value = profile
    session.execute.return_value = query_result
    repository = FaceProfileRepository(session)

    result = asyncio.run(repository.mark_generation_failed(uuid4()))

    assert result is profile
    session.execute.assert_awaited_once()
    session.commit.assert_not_awaited()


def test_updates_readiness_result() -> None:
    session = create_session()
    query_result = MagicMock()
    profile = MagicMock(spec=FaceProfile)
    query_result.scalar_one_or_none.return_value = profile
    session.execute.return_value = query_result
    repository = FaceProfileRepository(session)
    checked_at = datetime.now(timezone.utc)

    result = asyncio.run(
        repository.update_readiness_result(
            uuid4(),
            status="passed",
            verification_config_id=uuid4(),
            checked_at=checked_at,
        )
    )

    assert result is profile
    session.execute.assert_awaited_once()
    session.commit.assert_not_awaited()
