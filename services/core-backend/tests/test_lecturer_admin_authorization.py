"""Authorization boundary tests for CurrentLecturer / CurrentAdministrator.

Neither dependency has a production route yet (Stage 4/5 add the first real
lecturer/admin endpoints), so a minimal probe app exercises the exact same
get_current_user -> require_realm_role pipeline end-to-end via TestClient,
mirroring test_me_route.py's pattern for the existing CurrentUser/CurrentStudent
dependencies. Once real routes exist, prefer testing through those directly and
this file can shrink to just the cases a real route doesn't otherwise cover.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from conftest import (
    INACTIVE_STUDENT_SUBJECT,
    LINKED_ADMINISTRATOR_SUBJECT,
    LINKED_LECTURER_SUBJECT,
    LINKED_STUDENT_SUBJECT,
    UNLINKED_SUBJECT,
    FakePool,
    build_authentication_service_for_tests,
    build_settings,
    default_connection,
    generate_rsa_key,
)
from modules.identity.auth.dependencies import (
    CurrentAdministrator,
    CurrentLecturer,
    CurrentStudent,
    get_authentication_service,
)


def _build_probe_app() -> FastAPI:
    app = FastAPI()

    @app.get("/probe/student-only")
    async def student_only(current_user: CurrentStudent):
        return {"role": "student", "userId": str(current_user.user_id)}

    @app.get("/probe/lecturer-only")
    async def lecturer_only(current_user: CurrentLecturer):
        return {"role": "lecturer", "userId": str(current_user.user_id)}

    @app.get("/probe/administrator-only")
    async def administrator_only(current_user: CurrentAdministrator):
        return {"role": "administrator", "userId": str(current_user.user_id)}

    return app


@pytest.fixture
def client(jwks_document):
    app = _build_probe_app()
    app.state.settings = build_settings()
    app.state.db_pool = FakePool(default_connection())
    app.dependency_overrides[get_authentication_service] = (
        lambda: build_authentication_service_for_tests(jwks_document)
    )

    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def authorize(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# --- No / invalid / expired token -> 401 (identical for every role-gated route,
# since this happens in get_current_user before require_realm_role ever runs) ---


def test_lecturer_route_rejects_a_request_without_a_token(client) -> None:
    response = client.get("/probe/lecturer-only")
    assert response.status_code == 401


def test_administrator_route_rejects_a_request_without_a_token(client) -> None:
    response = client.get("/probe/administrator-only")
    assert response.status_code == 401


def test_lecturer_route_rejects_a_token_with_an_invalid_signature(
    client,
    make_access_token,
) -> None:
    forged_token = make_access_token(
        subject=LINKED_LECTURER_SUBJECT,
        roles=("lecturer",),
        private_key=generate_rsa_key(),
    )
    response = client.get("/probe/lecturer-only", headers=authorize(forged_token))
    assert response.status_code == 401


def test_administrator_route_rejects_an_expired_token(client, make_access_token) -> None:
    token = make_access_token(
        subject=LINKED_ADMINISTRATOR_SUBJECT,
        roles=("administrator",),
        expires_in_seconds=-30,
    )
    response = client.get("/probe/administrator-only", headers=authorize(token))
    assert response.status_code == 401


def test_lecturer_route_returns_404_for_an_unlinked_keycloak_user(
    client,
    make_access_token,
) -> None:
    token = make_access_token(subject=UNLINKED_SUBJECT, roles=("lecturer",))
    response = client.get("/probe/lecturer-only", headers=authorize(token))
    assert response.status_code == 404


def test_lecturer_route_returns_403_for_an_inactive_application_user(
    client,
    make_access_token,
) -> None:
    # INACTIVE_STUDENT_SUBJECT is disabled at the application-account level
    # (identity.users.account_status), independent of which realm role the
    # token claims — account status is checked before the role is.
    token = make_access_token(subject=INACTIVE_STUDENT_SUBJECT, roles=("lecturer",))
    response = client.get("/probe/lecturer-only", headers=authorize(token))
    assert response.status_code == 403


# --- Wrong role for the route -> 403 ---


def test_student_cannot_call_a_lecturer_only_route(client, make_access_token) -> None:
    token = make_access_token(subject=LINKED_STUDENT_SUBJECT, roles=("student",))
    response = client.get("/probe/lecturer-only", headers=authorize(token))
    assert response.status_code == 403


def test_student_cannot_call_an_administrator_only_route(client, make_access_token) -> None:
    token = make_access_token(subject=LINKED_STUDENT_SUBJECT, roles=("student",))
    response = client.get("/probe/administrator-only", headers=authorize(token))
    assert response.status_code == 403


def test_lecturer_cannot_call_an_administrator_only_route(client, make_access_token) -> None:
    token = make_access_token(subject=LINKED_LECTURER_SUBJECT, roles=("lecturer",))
    response = client.get("/probe/administrator-only", headers=authorize(token))
    assert response.status_code == 403


def test_administrator_cannot_call_a_lecturer_only_route(client, make_access_token) -> None:
    # The approved authorization policy does not grant administrators implicit
    # access to lecturer-only routes — each role is checked independently, roles
    # never imply one another.
    token = make_access_token(subject=LINKED_ADMINISTRATOR_SUBJECT, roles=("administrator",))
    response = client.get("/probe/lecturer-only", headers=authorize(token))
    assert response.status_code == 403


def test_lecturer_cannot_call_a_student_only_route(client, make_access_token) -> None:
    token = make_access_token(subject=LINKED_LECTURER_SUBJECT, roles=("lecturer",))
    response = client.get("/probe/student-only", headers=authorize(token))
    assert response.status_code == 403


# --- Correct role for the route -> 200, and identity/role are read from the
# validated token, never trusted from anything caller-supplied ---


def test_lecturer_can_call_a_lecturer_only_route(client, make_access_token) -> None:
    token = make_access_token(subject=LINKED_LECTURER_SUBJECT, roles=("lecturer",))
    response = client.get("/probe/lecturer-only", headers=authorize(token))
    assert response.status_code == 200
    assert response.json()["role"] == "lecturer"


def test_administrator_can_call_an_administrator_only_route(
    client,
    make_access_token,
) -> None:
    token = make_access_token(subject=LINKED_ADMINISTRATOR_SUBJECT, roles=("administrator",))
    response = client.get("/probe/administrator-only", headers=authorize(token))
    assert response.status_code == 200
    assert response.json()["role"] == "administrator"


def test_student_can_call_a_student_only_route(client, make_access_token) -> None:
    token = make_access_token(subject=LINKED_STUDENT_SUBJECT, roles=("student",))
    response = client.get("/probe/student-only", headers=authorize(token))
    assert response.status_code == 200
    assert response.json()["role"] == "student"


def test_a_user_with_multiple_roles_can_call_either_matching_route(
    client,
    make_access_token,
) -> None:
    token = make_access_token(subject=LINKED_LECTURER_SUBJECT, roles=("lecturer", "administrator"))

    lecturer_response = client.get("/probe/lecturer-only", headers=authorize(token))
    administrator_response = client.get("/probe/administrator-only", headers=authorize(token))

    assert lecturer_response.status_code == 200
    assert administrator_response.status_code == 200
