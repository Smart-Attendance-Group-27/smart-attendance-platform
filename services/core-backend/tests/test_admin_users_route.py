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
from modules.identity.admin_users.exception import (
    CannotModifyOwnAccountError,
    UserNotFoundError,
)
from modules.identity.admin_users.repository import (
    AdministratorAccountRecord,
    LecturerAccountRecord,
    StudentAccountRecord,
    UserAccountRecord,
)
from modules.identity.admin_users.route import get_admin_user_service
from modules.identity.admin_users.service import UserDirectory
from modules.identity.auth.dependencies import get_authentication_service

USERS_URL = "/api/v1/administrators/me/users"
TARGET_USER_ID = UUID("20000000-0000-0000-0000-000000000011")


def authorize(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def admin_token(make_access_token) -> str:
    return make_access_token(subject=LINKED_ADMINISTRATOR_SUBJECT, roles=("administrator",))


def build_directory() -> UserDirectory:
    return UserDirectory(
        students=[
            StudentAccountRecord(
                user_id=TARGET_USER_ID,
                registration_number="230701A",
                full_name="Amal Perera",
                email="230701a@student.uniattend.test",
                department_name="Computer Science",
                intake_year=2023,
                current_semester=5,
                account_status="active",
                profile_status="active",
            )
        ],
        lecturers=[
            LecturerAccountRecord(
                user_id=UUID("20000000-0000-0000-0000-000000000002"),
                employee_number="EMP-001",
                full_name="N. Perera",
                email="n.perera@staff.uniattend.test",
                department_name="Computer Science",
                designation="Senior Lecturer",
                account_status="active",
                profile_status="active",
            )
        ],
        administrators=[
            AdministratorAccountRecord(
                user_id=UUID("20000000-0000-0000-0000-000000000001"),
                full_name="System Administrator",
                email="admin@uniattend.test",
                department_name="Computer Science",
                administrative_scope="university",
                account_status="active",
                profile_status="active",
            )
        ],
    )


class StubAdminUserService:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.status_calls: list[tuple] = []

    async def get_directory(self, pool):
        return build_directory()

    async def update_account_status(self, pool, actor_user_id, target_user_id, account_status):
        self.status_calls.append((actor_user_id, target_user_id, account_status))
        if self.error is not None:
            raise self.error
        return UserAccountRecord(id=target_user_id, account_status=account_status, locked_until=None)


def build_client(jwks_document, service: StubAdminUserService) -> TestClient:
    app = create_app(enable_database=False)
    app.state.settings = build_settings()
    app.state.db_pool = FakePool(default_connection())
    app.dependency_overrides[get_authentication_service] = (
        lambda: build_authentication_service_for_tests(jwks_document)
    )
    app.dependency_overrides[get_admin_user_service] = lambda: service
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def service() -> StubAdminUserService:
    return StubAdminUserService()


@pytest.fixture
def client(jwks_document, service: StubAdminUserService):
    with build_client(jwks_document, service) as test_client:
        yield test_client


def test_returns_combined_user_directory(client: TestClient, make_access_token) -> None:
    response = client.get(USERS_URL, headers=authorize(admin_token(make_access_token)))

    assert response.status_code == 200
    body = response.json()
    assert len(body["students"]) == 1
    assert len(body["lecturers"]) == 1
    assert len(body["administrators"]) == 1
    assert body["students"][0]["registrationNumber"] == "230701A"


def test_rejects_non_administrator_role(client: TestClient, make_access_token) -> None:
    response = client.get(
        USERS_URL,
        headers=authorize(make_access_token(subject=LINKED_STUDENT_SUBJECT, roles=("student",))),
    )

    assert response.status_code == 403


def test_updates_account_status(client: TestClient, service: StubAdminUserService, make_access_token) -> None:
    response = client.patch(
        f"{USERS_URL}/{TARGET_USER_ID}/account-status",
        headers=authorize(admin_token(make_access_token)),
        json={"accountStatus": "suspended"},
    )

    assert response.status_code == 200
    assert response.json()["accountStatus"] == "suspended"
    assert service.status_calls[0][2] == "suspended"


def test_rejects_unknown_status_value(client: TestClient, make_access_token) -> None:
    response = client.patch(
        f"{USERS_URL}/{TARGET_USER_ID}/account-status",
        headers=authorize(admin_token(make_access_token)),
        json={"accountStatus": "banned"},
    )

    assert response.status_code == 422


def test_status_update_missing_user_returns_404(jwks_document, make_access_token) -> None:
    service = StubAdminUserService(error=UserNotFoundError())
    with build_client(jwks_document, service) as client:
        response = client.patch(
            f"{USERS_URL}/{TARGET_USER_ID}/account-status",
            headers=authorize(admin_token(make_access_token)),
            json={"accountStatus": "suspended"},
        )

    assert response.status_code == 404


def test_cannot_modify_own_account_returns_409(jwks_document, make_access_token) -> None:
    service = StubAdminUserService(error=CannotModifyOwnAccountError())
    with build_client(jwks_document, service) as client:
        response = client.patch(
            f"{USERS_URL}/{TARGET_USER_ID}/account-status",
            headers=authorize(admin_token(make_access_token)),
            json={"accountStatus": "suspended"},
        )

    assert response.status_code == 409


def test_requires_bearer_token(client: TestClient) -> None:
    response = client.get(USERS_URL)

    assert response.status_code == 401
