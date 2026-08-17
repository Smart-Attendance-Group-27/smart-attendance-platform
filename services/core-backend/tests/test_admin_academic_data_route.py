from datetime import time
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
from modules.academic.admin_academic_data.repository import (
    AdminCourseOfferingRecord,
    AdminCourseRecord,
    AdminEnrolmentRecord,
    AdminTimetableEntryRecord,
)
from modules.academic.admin_academic_data.route import get_admin_academic_data_service
from modules.academic.admin_academic_data.service import SOURCE_CONNECTION_STATUS, AcademicData
from modules.identity.auth.dependencies import get_authentication_service

ACADEMIC_DATA_URL = "/api/v1/administrators/me/academic-data"


def authorize(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def admin_token(make_access_token) -> str:
    return make_access_token(subject=LINKED_ADMINISTRATOR_SUBJECT, roles=("administrator",))


def build_academic_data() -> AcademicData:
    return AcademicData(
        source_connection_status=SOURCE_CONNECTION_STATUS,
        courses=[
            AdminCourseRecord(
                id=UUID("36000000-0000-0000-0000-000000000001"),
                course_code="CS3203",
                course_name="Software Engineering Project",
                department_name="Computer Science",
                credits=3,
                status="active",
            )
        ],
        offerings=[
            AdminCourseOfferingRecord(
                id=UUID("37000000-0000-0000-0000-000000000001"),
                course_code="CS3203",
                course_name="Software Engineering Project",
                semester_label="Semester 1 (2026)",
                batch_year=2023,
                course_type="core",
                attendance_threshold_percent=80,
                enrolled_count=6,
                status="active",
            )
        ],
        timetable=[
            AdminTimetableEntryRecord(
                id=UUID("3a000000-0000-0000-0000-000000000001"),
                course_code="CS3203",
                course_name="Software Engineering Project",
                day_of_week=1,
                start_time=time(9, 0),
                end_time=time(11, 0),
                classroom_code="LH-02",
                lecturer_name="N. Perera",
            )
        ],
        enrolments=[
            AdminEnrolmentRecord(
                id=UUID("39000000-0000-0000-0000-000000000001"),
                student_name="Amal Perera",
                registration_number="230701A",
                course_code="CS3203",
                semester_label="Semester 1 (2026)",
                enrolment_status="enrolled",
            )
        ],
    )


class StubAdminAcademicDataService:
    async def get_academic_data(self, pool):
        return build_academic_data()


def build_client(jwks_document, service) -> TestClient:
    app = create_app(enable_database=False)
    app.state.settings = build_settings()
    app.state.db_pool = FakePool(default_connection())
    app.dependency_overrides[get_authentication_service] = (
        lambda: build_authentication_service_for_tests(jwks_document)
    )
    app.dependency_overrides[get_admin_academic_data_service] = lambda: service
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def client(jwks_document):
    with build_client(jwks_document, StubAdminAcademicDataService()) as test_client:
        yield test_client


def test_returns_academic_data_with_honest_sync_status(client: TestClient, make_access_token) -> None:
    response = client.get(ACADEMIC_DATA_URL, headers=authorize(admin_token(make_access_token)))

    assert response.status_code == 200
    body = response.json()
    assert body["sourceConnectionStatus"] == "not_configured"
    assert body["courses"][0]["courseCode"] == "CS3203"
    assert body["timetable"][0]["lecturerName"] == "N. Perera"


def test_rejects_non_administrator_role(client: TestClient, make_access_token) -> None:
    response = client.get(
        ACADEMIC_DATA_URL,
        headers=authorize(make_access_token(subject=LINKED_STUDENT_SUBJECT, roles=("student",))),
    )

    assert response.status_code == 403


def test_requires_bearer_token(client: TestClient) -> None:
    response = client.get(ACADEMIC_DATA_URL)

    assert response.status_code == 401
