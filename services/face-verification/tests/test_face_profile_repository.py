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

class FakeEmbeddingCrypto:
    def encrypt(self, embedding: list[float]) -> bytes:
        return b"encrypted-embedding"

    def decrypt(self, token: bytes) -> tuple[float, ...]:
        return (0.1, 0.2, 0.3)


def create_repository(session: AsyncMock) -> FaceProfileRepository:
    return FaceProfileRepository(session, embedding_crypto=FakeEmbeddingCrypto())


def test_gets_face_profile_by_id() -> None:
    session = create_session()
    profile_id = uuid4()
    profile = MagicMock(spec=FaceProfile)
    session.get.return_value = profile
    repository = create_repository(session)

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
    repository = create_repository(session)

    result = asyncio.run(repository.get_by_student_id(uuid4()))

    assert result is profile
    session.execute.assert_awaited_once()
    session.commit.assert_not_awaited()


def test_creates_pending_face_profile() -> None:
    session = create_session()
    student_id = uuid4()
    repository = create_repository(session)

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
    repository = create_repository(session)

    result = asyncio.run(
        repository.save_generated_embedding(
            uuid4(),
            [0.1, 0.2, 0.3],
            model_name="test-model",
            model_version="1",
            generated_at=datetime.now(timezone.utc),
        )
    )

    assert result is profile
    session.execute.assert_awaited_once()
    session.commit.assert_not_awaited()


def test_rejects_empty_embedding_without_querying_database() -> None:
    session = create_session()
    repository = create_repository(session)

    with pytest.raises(
        ValueError,
        match="Embedding must contain at least one value",
    ):
        asyncio.run(repository.save_generated_embedding(uuid4(), [], model_name="test-model"))

    session.execute.assert_not_awaited()


def test_marks_embedding_generation_as_failed() -> None:
    session = create_session()
    query_result = MagicMock()
    profile = MagicMock(spec=FaceProfile)
    query_result.scalar_one_or_none.return_value = profile
    session.execute.return_value = query_result
    repository = create_repository(session)

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
    repository = create_repository(session)
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


def test_returns_none_when_no_profile_for_decrypted_comparison_embedding() -> None:
    session = create_session()
    query_result = MagicMock()
    query_result.scalar_one_or_none.return_value = None
    session.execute.return_value = query_result
    repository = create_repository(session)

    result = asyncio.run(repository.get_decrypted_embedding_for_comparison(uuid4()))

    assert result is None


def test_returns_none_when_profile_is_not_generated_for_comparison_embedding() -> None:
    session = create_session()
    query_result = MagicMock()
    profile = MagicMock(spec=FaceProfile)
    profile.embedding_generation_status = "pending"
    query_result.scalar_one_or_none.return_value = profile
    session.execute.return_value = query_result
    repository = create_repository(session)

    result = asyncio.run(repository.get_decrypted_embedding_for_comparison(uuid4()))

    assert result is None


def test_returns_decrypted_embedding_for_generated_profile() -> None:
    session = create_session()
    query_result = MagicMock()
    profile = MagicMock(spec=FaceProfile)
    profile.embedding_generation_status = "generated"
    profile.embedding_encrypted = b"encrypted-embedding"
    profile.embedding_dimension = 3
    query_result.scalar_one_or_none.return_value = profile
    session.execute.return_value = query_result
    repository = create_repository(session)

    result = asyncio.run(repository.get_decrypted_embedding_for_comparison(uuid4()))

    assert result == (0.1, 0.2, 0.3)


def test_rejects_generated_profile_with_dimension_mismatch() -> None:
    session = create_session()
    query_result = MagicMock()
    profile = MagicMock(spec=FaceProfile)
    profile.embedding_generation_status = "generated"
    profile.embedding_encrypted = b"encrypted-embedding"
    profile.embedding_dimension = 4
    query_result.scalar_one_or_none.return_value = profile
    session.execute.return_value = query_result
    repository = create_repository(session)

    with pytest.raises(
        ValueError,
        match="Decrypted embedding dimension does not match stored metadata",
    ):
        asyncio.run(repository.get_decrypted_embedding_for_comparison(uuid4()))
