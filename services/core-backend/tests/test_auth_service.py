import pytest

from conftest import (
    INACTIVE_STUDENT_SUBJECT,
    LINKED_LECTURER_SUBJECT,
    LINKED_STUDENT_SUBJECT,
    STUDENT_USER_ID,
    UNLINKED_SUBJECT,
    FakeConnection,
    FakePool,
    build_authentication_service_for_tests,
    build_user_row,
    default_connection,
)
from modules.identity.auth.exception import (
    InactiveUserError,
    UserNotLinkedError,
)
from modules.identity.auth.repository import AuthUserRepository


async def test_maps_a_linked_active_student_to_the_internal_user_id(
    jwks_document,
    make_access_token,
) -> None:
    service = build_authentication_service_for_tests(jwks_document)
    pool = FakePool(default_connection())

    authenticated_user = await service.authenticate(pool, make_access_token())

    assert authenticated_user.user_id == STUDENT_USER_ID
    assert authenticated_user.keycloak_user_id == LINKED_STUDENT_SUBJECT
    assert authenticated_user.email == "230701a@student.uniattend.test"
    assert authenticated_user.roles == ("student",)
    assert authenticated_user.has_role("student")


async def test_rejects_a_subject_with_no_application_user(
    jwks_document,
    make_access_token,
) -> None:
    service = build_authentication_service_for_tests(jwks_document)
    pool = FakePool(default_connection())

    with pytest.raises(UserNotLinkedError):
        await service.authenticate(
            pool,
            make_access_token(subject=UNLINKED_SUBJECT),
        )


async def test_rejects_an_inactive_application_user(
    jwks_document,
    make_access_token,
) -> None:
    service = build_authentication_service_for_tests(jwks_document)
    pool = FakePool(default_connection())

    with pytest.raises(InactiveUserError):
        await service.authenticate(
            pool,
            make_access_token(subject=INACTIVE_STUDENT_SUBJECT),
        )


async def test_keeps_the_lecturer_roles_from_the_token(
    jwks_document,
    make_access_token,
) -> None:
    service = build_authentication_service_for_tests(jwks_document)
    pool = FakePool(default_connection())

    authenticated_user = await service.authenticate(
        pool,
        make_access_token(subject=LINKED_LECTURER_SUBJECT, roles=("lecturer",)),
    )

    assert authenticated_user.roles == ("lecturer",)
    assert not authenticated_user.has_role("student")


async def test_prefers_the_stored_email_over_the_token_email(
    jwks_document,
    make_access_token,
) -> None:
    service = build_authentication_service_for_tests(jwks_document)
    pool = FakePool(default_connection())

    authenticated_user = await service.authenticate(
        pool,
        make_access_token(email="stale-token-email@example.test"),
    )

    assert authenticated_user.email == "230701a@student.uniattend.test"


async def test_repository_maps_a_row_to_an_application_user_record() -> None:
    connection = FakeConnection(
        users_by_keycloak_id={LINKED_STUDENT_SUBJECT: build_user_row()},
    )

    record = await AuthUserRepository().find_by_keycloak_user_id(
        connection,
        LINKED_STUDENT_SUBJECT,
    )

    assert record is not None
    assert record.id == STUDENT_USER_ID
    assert record.account_status == "active"
    assert record.keycloak_user_id == LINKED_STUDENT_SUBJECT
    assert "identity.users" in connection.executed_queries[0]
    assert "keycloak_user_id = $1" in connection.executed_queries[0]


async def test_repository_returns_none_for_an_unknown_keycloak_user() -> None:
    connection = FakeConnection(users_by_keycloak_id={})

    record = await AuthUserRepository().find_by_keycloak_user_id(
        connection,
        UNLINKED_SUBJECT,
    )

    assert record is None
