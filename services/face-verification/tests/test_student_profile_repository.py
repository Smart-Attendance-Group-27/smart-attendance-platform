import asyncio
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from repositories.student_profile_repository import (
    StudentProfileRepository,
)


def test_gets_student_by_exact_registration_number() -> None:
    session = AsyncMock(spec=AsyncSession)
    student_id = uuid4()
    query_result = MagicMock()
    query_result.mappings.return_value.one_or_none.return_value = {
        "id": student_id,
        "registration_number": "230734J",
        "profile_status": "active",
    }
    session.execute.return_value = query_result
    repository = StudentProfileRepository(session)

    result = asyncio.run(
        repository.get_by_registration_number("230734J")
    )

    assert result is not None
    assert result.id == student_id
    assert result.registration_number == "230734J"
    assert result.profile_status == "active"
    session.execute.assert_awaited_once()
    parameters = session.execute.await_args.args[1]
    assert parameters == {"registration_number": "230734J"}
    session.commit.assert_not_awaited()


def test_returns_none_when_registration_number_is_unknown() -> None:
    session = AsyncMock(spec=AsyncSession)
    query_result = MagicMock()
    query_result.mappings.return_value.one_or_none.return_value = None
    session.execute.return_value = query_result
    repository = StudentProfileRepository(session)

    result = asyncio.run(
        repository.get_by_registration_number("UNKNOWN")
    )

    assert result is None
    session.commit.assert_not_awaited()
