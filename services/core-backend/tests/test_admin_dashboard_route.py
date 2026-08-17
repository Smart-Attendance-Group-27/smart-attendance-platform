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
from modules.academic.admin_dashboard.repository import AdminOverviewRecord
from modules.academic.admin_dashboard.route import get_admin_dashboard_service
from modules.identity.auth.dependencies import get_authentication_service

OVERVIEW_URL = "/api/v1/administrators/me/dashboard-overview"


def authorize(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def admin_token(make_access_token) -> str:
    return make_access_token(subject=LINKED_ADMINISTRATOR_SUBJECT, roles=("administrator",))


class StubAdminDashboardService:
    async def get_overview(self, pool):
        return AdminOverviewRecord(
            active_users_count=10,
            configured_classrooms_count=3,
            active_geofences_count=3,
        )


def build_client(jwks_document, service) -> TestClient:
    app = create_app(enable_database=False)
    app.state.settings = build_settings()
    app.state.db_pool = FakePool(default_connection())
    app.dependency_overrides[get_authentication_service] = (
        lambda: build_authentication_service_for_tests(jwks_document)
    )
    app.dependency_overrides[get_admin_dashboard_service] = lambda: service
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def client(jwks_document):
    with build_client(jwks_document, StubAdminDashboardService()) as test_client:
        yield test_client


def test_returns_overview_with_honest_policy_and_sync_placeholders(
    client: TestClient,
    make_access_token,
) -> None:
    response = client.get(OVERVIEW_URL, headers=authorize(admin_token(make_access_token)))

    assert response.status_code == 200
    body = response.json()
    assert body["activeUsersCount"] == 10
    assert body["configuredClassroomsCount"] == 3
    assert body["activeGeofencesCount"] == 3
    assert body["policyAlertsCount"] == 0
    assert body["academicSourceStatusLabel"] == "Not configured"


def test_rejects_non_administrator_role(client: TestClient, make_access_token) -> None:
    response = client.get(
        OVERVIEW_URL,
        headers=authorize(make_access_token(subject=LINKED_STUDENT_SUBJECT, roles=("student",))),
    )

    assert response.status_code == 403


def test_requires_bearer_token(client: TestClient) -> None:
    response = client.get(OVERVIEW_URL)

    assert response.status_code == 401
