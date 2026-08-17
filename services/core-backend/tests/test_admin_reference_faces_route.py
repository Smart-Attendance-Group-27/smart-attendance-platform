from datetime import UTC, datetime
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from conftest import (
    LINKED_ADMINISTRATOR_SUBJECT,
    LINKED_STUDENT_SUBJECT,
    FakePool,
    build_authentication_service_for_tests,
    build_settings,
    default_connection,
)
from main import create_app
from modules.academic.admin_reference_faces.repository import ReferenceFaceRecord
from modules.academic.admin_reference_faces.route import get_admin_reference_face_service
from modules.identity.auth.dependencies import get_authentication_service

REFERENCE_FACES_URL = "/api/v1/administrators/me/reference-faces"
STUDENT_ID = UUID("23000000-0000-0000-0000-000000000001")
CURRENT_TIME = datetime(2026, 8, 13, 5, 30, tzinfo=UTC)


def authorize(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def admin_token(make_access_token) -> str:
    return make_access_token(subject=LINKED_ADMINISTRATOR_SUBJECT, roles=("administrator",))


class StubAdminReferenceFaceService:
    async def list_reference_faces(self, pool):
        return [
            ReferenceFaceRecord(
                student_id=STUDENT_ID,
                registration_number="230701A",
                full_name="Amal Perera",
                embedding_generation_status="generated",
                generated_at=CURRENT_TIME,
                latest_attempt_status="passed",
                latest_attempt_validated_at=CURRENT_TIME,
            ),
            ReferenceFaceRecord(
                student_id=UUID("23000000-0000-0000-0000-000000000002"),
                registration_number="230702B",
                full_name="Nimal Silva",
                embedding_generation_status=None,
                generated_at=None,
                latest_attempt_status=None,
                latest_attempt_validated_at=None,
            ),
        ]


def build_client(jwks_document, service) -> TestClient:
    app = create_app(enable_database=False)
    app.state.settings = build_settings()
    app.state.db_pool = FakePool(default_connection())
    app.dependency_overrides[get_authentication_service] = (
        lambda: build_authentication_service_for_tests(jwks_document)
    )
    app.dependency_overrides[get_admin_reference_face_service] = lambda: service
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def client(jwks_document):
    with build_client(jwks_document, StubAdminReferenceFaceService()) as test_client:
        yield test_client


def test_returns_readiness_status_without_embeddings(client: TestClient, make_access_token) -> None:
    response = client.get(REFERENCE_FACES_URL, headers=authorize(admin_token(make_access_token)))

    assert response.status_code == 200
    body = response.json()
    assert body[0]["readinessStatus"] == "passed"
    assert body[1]["readinessStatus"] == "not_checked"
    assert body[1]["embeddingGenerationStatus"] == "pending"
    for row in body:
        assert set(row.keys()) == {
            "studentId",
            "studentName",
            "registrationNumber",
            "embeddingGenerationStatus",
            "readinessStatus",
            "generatedAt",
            "readinessCheckedAt",
        }


def test_rejects_non_administrator_role(client: TestClient, make_access_token) -> None:
    response = client.get(
        REFERENCE_FACES_URL,
        headers=authorize(make_access_token(subject=LINKED_STUDENT_SUBJECT, roles=("student",))),
    )

    assert response.status_code == 403


def test_requires_bearer_token(client: TestClient) -> None:
    response = client.get(REFERENCE_FACES_URL)

    assert response.status_code == 401
