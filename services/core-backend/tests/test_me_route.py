import pytest
from fastapi.testclient import TestClient

from conftest import (
    INACTIVE_STUDENT_SUBJECT,
    LINKED_LECTURER_SUBJECT,
    STUDENT_USER_ID,
    UNLINKED_SUBJECT,
    FakePool,
    build_authentication_service_for_tests,
    build_settings,
    default_connection,
    generate_rsa_key,
)
from main import create_app
from modules.identity.auth.dependencies import get_authentication_service


@pytest.fixture
def client(jwks_document):
    app = create_app(enable_database=False)
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


def test_returns_the_signed_in_application_user(client, make_access_token) -> None:
    response = client.get("/api/v1/me", headers=authorize(make_access_token()))

    assert response.status_code == 200
    assert response.json() == {
        "id": str(STUDENT_USER_ID),
        "email": "230701a@student.uniattend.test",
        "roles": ["student"],
    }


def test_never_exposes_sensitive_user_fields(client, make_access_token) -> None:
    response = client.get("/api/v1/me", headers=authorize(make_access_token()))

    payload = response.json()
    for forbidden_field in (
        "password_hash",
        "passwordHash",
        "keycloak_user_id",
        "keycloakUserId",
        "account_status",
        "failed_login_attempts",
        "locked_until",
    ):
        assert forbidden_field not in payload


def test_rejects_a_request_without_a_token(client) -> None:
    response = client.get("/api/v1/me")

    assert response.status_code == 401
    assert response.json()["detail"] == "A bearer access token is required."


def test_rejects_a_malformed_authorization_header(client) -> None:
    response = client.get("/api/v1/me", headers={"Authorization": "Basic abc123"})

    assert response.status_code == 401


def test_rejects_a_bearer_header_with_no_token(client) -> None:
    response = client.get("/api/v1/me", headers={"Authorization": "Bearer"})

    assert response.status_code == 401


def test_rejects_a_token_that_is_not_a_jwt(client) -> None:
    response = client.get("/api/v1/me", headers=authorize("not-a-jwt"))

    assert response.status_code == 401


def test_rejects_a_token_with_an_invalid_signature(client, make_access_token) -> None:
    forged_token = make_access_token(private_key=generate_rsa_key())

    response = client.get("/api/v1/me", headers=authorize(forged_token))

    assert response.status_code == 401
    assert "signature" in response.json()["detail"]


def test_rejects_an_expired_token(client, make_access_token) -> None:
    response = client.get(
        "/api/v1/me",
        headers=authorize(make_access_token(expires_in_seconds=-30)),
    )

    assert response.status_code == 401
    assert "expired" in response.json()["detail"]


def test_rejects_a_token_from_the_wrong_issuer(client, make_access_token) -> None:
    response = client.get(
        "/api/v1/me",
        headers=authorize(make_access_token(issuer="http://other.test/realms/x")),
    )

    assert response.status_code == 401
    assert "issuer" in response.json()["detail"]


def test_rejects_a_token_with_the_wrong_audience(client, make_access_token) -> None:
    response = client.get(
        "/api/v1/me",
        headers=authorize(make_access_token(audience="another-api")),
    )

    assert response.status_code == 401
    assert "audience" in response.json()["detail"]


def test_returns_404_for_an_unlinked_keycloak_user(client, make_access_token) -> None:
    response = client.get(
        "/api/v1/me",
        headers=authorize(make_access_token(subject=UNLINKED_SUBJECT)),
    )

    assert response.status_code == 404


def test_returns_403_for_an_inactive_application_user(
    client,
    make_access_token,
) -> None:
    response = client.get(
        "/api/v1/me",
        headers=authorize(make_access_token(subject=INACTIVE_STUDENT_SUBJECT)),
    )

    assert response.status_code == 403


def test_allows_a_lecturer_to_read_their_own_identity(
    client,
    make_access_token,
) -> None:
    response = client.get(
        "/api/v1/me",
        headers=authorize(
            make_access_token(subject=LINKED_LECTURER_SUBJECT, roles=("lecturer",)),
        ),
    )

    assert response.status_code == 200
    assert response.json()["roles"] == ["lecturer"]


def test_returns_503_when_keycloak_settings_are_missing(make_access_token) -> None:
    app = create_app(enable_database=False)
    app.state.settings = build_settings(
        keycloak_expected_issuer=None,
        keycloak_jwks_url=None,
    )
    app.state.db_pool = FakePool(default_connection())

    with TestClient(app, raise_server_exceptions=False) as test_client:
        response = test_client.get(
            "/api/v1/me",
            headers=authorize(make_access_token()),
        )

    assert response.status_code == 503
    detail = response.json()["detail"]
    assert "KEYCLOAK_EXPECTED_ISSUER" in detail
    assert "KEYCLOAK_JWKS_URL" in detail
