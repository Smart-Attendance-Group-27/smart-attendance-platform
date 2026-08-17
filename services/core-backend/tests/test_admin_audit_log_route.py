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
from modules.audit.admin_log.repository import AuditLogRecord
from modules.audit.admin_log.route import get_audit_log_service
from modules.identity.auth.dependencies import get_authentication_service

AUDIT_LOGS_URL = "/api/v1/administrators/me/audit-logs"
CURRENT_TIME = datetime(2026, 8, 13, 5, 30, tzinfo=UTC)


def authorize(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def admin_token(make_access_token) -> str:
    return make_access_token(subject=LINKED_ADMINISTRATOR_SUBJECT, roles=("administrator",))


class StubAuditLogService:
    def __init__(self) -> None:
        self.requested_limit: int | None = None

    async def list_audit_logs(self, pool, *, limit):
        self.requested_limit = limit
        return [
            AuditLogRecord(
                id=UUID("50000000-0000-0000-0000-000000000001"),
                occurred_at=CURRENT_TIME,
                actor_user_id=UUID("20000000-0000-0000-0000-000000000002"),
                actor_type="lecturer",
                actor_name="N. Perera",
                action="manual_review.decide",
                entity_type="verification_attempt",
                entity_id=UUID("50000000-0000-0000-0000-000000000002"),
                outcome="success",
                failure_reason=None,
            )
        ]


def build_client(jwks_document, service) -> TestClient:
    app = create_app(enable_database=False)
    app.state.settings = build_settings()
    app.state.db_pool = FakePool(default_connection())
    app.dependency_overrides[get_authentication_service] = (
        lambda: build_authentication_service_for_tests(jwks_document)
    )
    app.dependency_overrides[get_audit_log_service] = lambda: service
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def service() -> StubAuditLogService:
    return StubAuditLogService()


@pytest.fixture
def client(jwks_document, service: StubAuditLogService):
    with build_client(jwks_document, service) as test_client:
        yield test_client


def test_returns_audit_log_entries(client: TestClient, make_access_token) -> None:
    response = client.get(AUDIT_LOGS_URL, headers=authorize(admin_token(make_access_token)))

    assert response.status_code == 200
    body = response.json()
    assert body[0]["actorName"] == "N. Perera"
    assert body[0]["action"] == "manual_review.decide"


def test_forwards_limit_query_param(client: TestClient, service: StubAuditLogService, make_access_token) -> None:
    response = client.get(
        f"{AUDIT_LOGS_URL}?limit=50",
        headers=authorize(admin_token(make_access_token)),
    )

    assert response.status_code == 200
    assert service.requested_limit == 50


def test_rejects_out_of_range_limit(client: TestClient, make_access_token) -> None:
    response = client.get(
        f"{AUDIT_LOGS_URL}?limit=9999",
        headers=authorize(admin_token(make_access_token)),
    )

    assert response.status_code == 422


def test_rejects_non_administrator_role(client: TestClient, make_access_token) -> None:
    response = client.get(
        AUDIT_LOGS_URL,
        headers=authorize(make_access_token(subject=LINKED_STUDENT_SUBJECT, roles=("student",))),
    )

    assert response.status_code == 403


def test_requires_bearer_token(client: TestClient) -> None:
    response = client.get(AUDIT_LOGS_URL)

    assert response.status_code == 401
