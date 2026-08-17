from datetime import UTC, datetime
from decimal import Decimal
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
from modules.academic.admin_classrooms.exception import (
    BuildingNotFoundError,
    ClassroomNotFoundError,
)
from modules.academic.admin_classrooms.repository import BuildingRecord, ClassroomRecord
from modules.academic.admin_classrooms.route import get_admin_classroom_service
from modules.identity.auth.dependencies import get_authentication_service

CLASSROOMS_URL = "/api/v1/administrators/me/classrooms"
BUILDINGS_URL = "/api/v1/administrators/me/buildings"
BUILDING_ID = UUID("32000000-0000-0000-0000-000000000001")
CLASSROOM_ID = UUID("33000000-0000-0000-0000-000000000001")
CURRENT_TIME = datetime(2026, 8, 13, 5, 30, tzinfo=UTC)


def authorize(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def admin_token(make_access_token) -> str:
    return make_access_token(subject=LINKED_ADMINISTRATOR_SUBJECT, roles=("administrator",))


def build_classroom() -> ClassroomRecord:
    return ClassroomRecord(
        id=CLASSROOM_ID,
        building_id=BUILDING_ID,
        building_name="Engineering Faculty Building",
        classroom_code="LH-02",
        floor_number=1,
        capacity=120,
        latitude=Decimal("6.7961"),
        longitude=Decimal("79.9007"),
        default_geofence_radius_m=Decimal("40"),
        status="active",
        assigned_courses_count=1,
        created_at=CURRENT_TIME,
        updated_at=CURRENT_TIME,
    )


VALID_WRITE_BODY = {
    "buildingId": str(BUILDING_ID),
    "classroomCode": "LH-05",
    "floorNumber": 3,
    "capacity": 60,
    "latitude": 6.8,
    "longitude": 79.9,
    "defaultGeofenceRadiusM": 30,
    "status": "active",
}


class StubAdminClassroomService:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[str] = []

    async def list_buildings(self, pool):
        self.calls.append("list_buildings")
        return [BuildingRecord(id=BUILDING_ID, building_name="Engineering Faculty Building", status="active")]

    async def list_classrooms(self, pool):
        self.calls.append("list_classrooms")
        if self.error is not None:
            raise self.error
        return [build_classroom()]

    async def get_classroom(self, pool, classroom_id):
        self.calls.append("get_classroom")
        if self.error is not None:
            raise self.error
        return build_classroom()

    async def create_classroom(self, pool, actor_user_id, **kwargs):
        self.calls.append("create_classroom")
        if self.error is not None:
            raise self.error
        return build_classroom()

    async def update_classroom(self, pool, actor_user_id, classroom_id, **kwargs):
        self.calls.append("update_classroom")
        if self.error is not None:
            raise self.error
        return build_classroom()


def build_client(jwks_document, service: StubAdminClassroomService) -> TestClient:
    app = create_app(enable_database=False)
    app.state.settings = build_settings()
    app.state.db_pool = FakePool(default_connection())
    app.dependency_overrides[get_authentication_service] = (
        lambda: build_authentication_service_for_tests(jwks_document)
    )
    app.dependency_overrides[get_admin_classroom_service] = lambda: service
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def service() -> StubAdminClassroomService:
    return StubAdminClassroomService()


@pytest.fixture
def client(jwks_document, service: StubAdminClassroomService):
    with build_client(jwks_document, service) as test_client:
        yield test_client


def test_lists_buildings(client: TestClient, make_access_token) -> None:
    response = client.get(BUILDINGS_URL, headers=authorize(admin_token(make_access_token)))

    assert response.status_code == 200
    assert response.json()[0]["buildingName"] == "Engineering Faculty Building"


def test_lists_classrooms(client: TestClient, make_access_token) -> None:
    response = client.get(CLASSROOMS_URL, headers=authorize(admin_token(make_access_token)))

    assert response.status_code == 200
    body = response.json()
    assert body[0]["id"] == str(CLASSROOM_ID)
    assert body[0]["defaultGeofenceRadiusM"] == 40.0


def test_rejects_non_administrator_role(client: TestClient, make_access_token) -> None:
    response = client.get(
        CLASSROOMS_URL,
        headers=authorize(make_access_token(subject=LINKED_STUDENT_SUBJECT, roles=("student",))),
    )

    assert response.status_code == 403


def test_get_classroom(client: TestClient, make_access_token) -> None:
    response = client.get(
        f"{CLASSROOMS_URL}/{CLASSROOM_ID}",
        headers=authorize(admin_token(make_access_token)),
    )

    assert response.status_code == 200


def test_get_missing_classroom_returns_404(jwks_document, make_access_token) -> None:
    service = StubAdminClassroomService(error=ClassroomNotFoundError())
    with build_client(jwks_document, service) as client:
        response = client.get(
            f"{CLASSROOMS_URL}/{CLASSROOM_ID}",
            headers=authorize(admin_token(make_access_token)),
        )

    assert response.status_code == 404


def test_creates_classroom(client: TestClient, service: StubAdminClassroomService, make_access_token) -> None:
    response = client.post(
        CLASSROOMS_URL,
        headers=authorize(admin_token(make_access_token)),
        json=VALID_WRITE_BODY,
    )

    assert response.status_code == 201
    assert "create_classroom" in service.calls


def test_create_classroom_rejects_invalid_latitude(client: TestClient, make_access_token) -> None:
    body = {**VALID_WRITE_BODY, "latitude": 999}
    response = client.post(
        CLASSROOMS_URL,
        headers=authorize(admin_token(make_access_token)),
        json=body,
    )

    assert response.status_code == 422


def test_create_classroom_missing_building_returns_404(jwks_document, make_access_token) -> None:
    service = StubAdminClassroomService(error=BuildingNotFoundError())
    with build_client(jwks_document, service) as client:
        response = client.post(
            CLASSROOMS_URL,
            headers=authorize(admin_token(make_access_token)),
            json=VALID_WRITE_BODY,
        )

    assert response.status_code == 404


def test_updates_classroom(client: TestClient, service: StubAdminClassroomService, make_access_token) -> None:
    response = client.put(
        f"{CLASSROOMS_URL}/{CLASSROOM_ID}",
        headers=authorize(admin_token(make_access_token)),
        json=VALID_WRITE_BODY,
    )

    assert response.status_code == 200
    assert "update_classroom" in service.calls


def test_requires_bearer_token(client: TestClient) -> None:
    response = client.get(CLASSROOMS_URL)

    assert response.status_code == 401
