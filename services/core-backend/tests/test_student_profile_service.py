import pytest

from conftest import (
    STUDENT_PROFILE_ID,
    STUDENT_USER_ID,
    FakeConnection,
    FakePool,
    build_profile_row,
)
from modules.academic.student_profile.exception import StudentProfileNotFoundError
from modules.academic.student_profile.repository import StudentProfileRepository
from modules.academic.student_profile.service import StudentProfileService


def build_pool(**profile_overrides) -> FakePool:
    return FakePool(
        FakeConnection(
            profiles_by_user_id={
                STUDENT_USER_ID: build_profile_row(**profile_overrides),
            },
        ),
    )


async def test_returns_the_profile_for_the_given_user() -> None:
    profile = await StudentProfileService().get_profile_for_user(
        build_pool(),
        STUDENT_USER_ID,
    )

    assert profile.id == STUDENT_PROFILE_ID
    assert profile.registration_number == "230701A"
    assert profile.full_name == "Amal Perera"
    assert profile.university_email == "230701a@student.uniattend.test"


async def test_includes_the_middle_name_in_the_full_name() -> None:
    profile = await StudentProfileService().get_profile_for_user(
        build_pool(middle_name="Kumara"),
        STUDENT_USER_ID,
    )

    assert profile.full_name == "Amal Kumara Perera"


async def test_skips_blank_name_parts() -> None:
    profile = await StudentProfileService().get_profile_for_user(
        build_pool(first_name="Amal", middle_name="   ", last_name=None),
        STUDENT_USER_ID,
    )

    assert profile.full_name == "Amal"


async def test_raises_when_no_profile_row_exists() -> None:
    pool = FakePool(FakeConnection(profiles_by_user_id={}))

    with pytest.raises(StudentProfileNotFoundError):
        await StudentProfileService().get_profile_for_user(pool, STUDENT_USER_ID)


async def test_treats_an_inactive_profile_as_missing() -> None:
    pool = build_pool(profile_status="archived")

    with pytest.raises(StudentProfileNotFoundError):
        await StudentProfileService().get_profile_for_user(pool, STUDENT_USER_ID)


async def test_repository_maps_a_row_to_a_profile_record() -> None:
    connection = FakeConnection(
        profiles_by_user_id={STUDENT_USER_ID: build_profile_row()},
    )

    record = await StudentProfileRepository().find_by_user_id(
        connection,
        STUDENT_USER_ID,
    )

    assert record is not None
    assert record.id == STUDENT_PROFILE_ID
    assert record.user_id == STUDENT_USER_ID
    assert record.registration_number == "230701A"
    assert record.profile_status == "active"
    assert record.university_email == "230701a@student.uniattend.test"

    executed_query = connection.executed_queries[0]
    assert "academic.student_profiles" in executed_query
    assert "JOIN identity.users" in executed_query
    assert "profile.user_id = $1" in executed_query


async def test_repository_returns_none_when_the_user_has_no_profile() -> None:
    connection = FakeConnection(profiles_by_user_id={})

    record = await StudentProfileRepository().find_by_user_id(
        connection,
        STUDENT_USER_ID,
    )

    assert record is None
