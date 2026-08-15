import pytest
from fastapi.testclient import TestClient

from conftest import (
    LINKED_LECTURER_SUBJECT,
    LINKED_STUDENT_SUBJECT,
    STUDENT_PROFILE_ID,
    STUDENT_USER_ID,
    FakeConnection,
    FakePool,
    build_authentication_service_for_tests,
    build_profile_row,
    build_settings,
    build_user_row,
    default_connection,
)
from main import create_app
from modules.identity.auth.dependencies import get_authentication_service

PROFILE_URL = "/api/v1/students/me/profile"


def build_client(jwks_document, connection: FakeConnection | None = None) -> TestClient:
    app = create_app(enable_database=False)
    app.state.settings = build_settings()
    app.state.db_pool = FakePool(connection or default_connection())
    app.dependency_overrides[get_authentication_service] = (
        lambda: build_authentication_service_for_tests(jwks_document)
    )
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def client(jwks_document):
    with build_client(jwks_document) as test_client:
        yield test_client


def authorize(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_returns_the_profile_of_the_signed_in_student(
    client,
    make_access_token,
) -> None:
    response = client.get(PROFILE_URL, headers=authorize(make_access_token()))

    assert response.status_code == 200
    assert response.json() == {
        "id": str(STUDENT_PROFILE_ID),
        "registrationNumber": "230701A",
        "fullName": "Amal Perera",
        "universityEmail": "230701a@student.uniattend.test",
    }


def test_never_exposes_internal_profile_fields(client, make_access_token) -> None:
    response = client.get(PROFILE_URL, headers=authorize(make_access_token()))

    payload = response.json()
    for forbidden_field in (
        "user_id",
        "userId",
        "profile_status",
        "profileStatus",
        "department_id",
        "password_hash",
        "keycloak_user_id",
    ):
        assert forbidden_field not in payload


def test_requires_a_bearer_token(client) -> None:
    response = client.get(PROFILE_URL)

    assert response.status_code == 401


def test_rejects_an_invalid_token(client) -> None:
    response = client.get(PROFILE_URL, headers=authorize("not-a-jwt"))

    assert response.status_code == 401


def test_rejects_a_lecturer(client, make_access_token) -> None:
    response = client.get(
        PROFILE_URL,
        headers=authorize(
            make_access_token(subject=LINKED_LECTURER_SUBJECT, roles=("lecturer",)),
        ),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "The 'student' role is required."


def test_rejects_a_token_carrying_no_roles(client, make_access_token) -> None:
    response = client.get(PROFILE_URL, headers=authorize(make_access_token(roles=())))

    assert response.status_code == 403


def test_returns_404_when_the_student_has_no_profile(
    jwks_document,
    make_access_token,
) -> None:
    connection = FakeConnection(
        users_by_keycloak_id={LINKED_STUDENT_SUBJECT: build_user_row()},
        profiles_by_user_id={},
    )

    with build_client(jwks_document, connection) as client:
        response = client.get(PROFILE_URL, headers=authorize(make_access_token()))

    assert response.status_code == 404


def test_returns_404_when_the_profile_is_not_active(
    jwks_document,
    make_access_token,
) -> None:
    connection = FakeConnection(
        users_by_keycloak_id={LINKED_STUDENT_SUBJECT: build_user_row()},
        profiles_by_user_id={
            STUDENT_USER_ID: build_profile_row(profile_status="withdrawn"),
        },
    )

    with build_client(jwks_document, connection) as client:
        response = client.get(PROFILE_URL, headers=authorize(make_access_token()))

    assert response.status_code == 404


def test_ignores_a_student_id_supplied_by_the_caller(
    client,
    make_access_token,
) -> None:
    # The endpoint takes no identifier from the request, so a query parameter
    # naming another student changes nothing.
    response = client.get(
        f"{PROFILE_URL}?userId=20000000-0000-0000-0000-000000000012",
        headers=authorize(make_access_token()),
    )

    assert response.status_code == 200
    assert response.json()["id"] == str(STUDENT_PROFILE_ID)
