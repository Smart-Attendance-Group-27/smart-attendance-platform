from datetime import time
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from conftest import (
    LINKED_LECTURER_SUBJECT,
    LINKED_STUDENT_SUBJECT,
    FakePool,
    build_authentication_service_for_tests,
    build_settings,
    default_connection,
)
from main import create_app
from modules.academic.lecturer_courses.repository import (
    LecturerCourseRecord,
    LecturerTimetableEntryRecord,
)
from modules.academic.lecturer_courses.route import get_lecturer_course_service
from modules.academic.lecturer_profile.exception import LecturerProfileNotFoundError
from modules.identity.auth.dependencies import get_authentication_service

COURSES_URL = "/api/v1/lecturers/me/courses"
TIMETABLE_URL = "/api/v1/lecturers/me/timetable"
COURSE_OFFERING_ID = UUID("30000000-0000-0000-0000-000000000001")


def authorize(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def lecturer_token(make_access_token) -> str:
    return make_access_token(subject=LINKED_LECTURER_SUBJECT, roles=("lecturer",))


def build_course() -> LecturerCourseRecord:
    return LecturerCourseRecord(
        course_offering_id=COURSE_OFFERING_ID,
        course_code="CS3203",
        course_name="Software Engineering Project",
        department_name="Computer Science",
        course_type="lecture",
        status="active",
        enrolled_count=40,
        attendance_rate_percent=None,
    )


def build_timetable_entry() -> LecturerTimetableEntryRecord:
    return LecturerTimetableEntryRecord(
        id=UUID("31000000-0000-0000-0000-000000000001"),
        course_code="CS3203",
        course_name="Software Engineering Project",
        day_of_week=1,
        start_time=time(9, 0),
        end_time=time(11, 0),
        classroom_code="LH-02",
        building_name="Engineering Faculty",
    )


class StubLecturerCourseService:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error

    async def list_courses_for_user(self, pool, user_id):
        if self.error is not None:
            raise self.error
        return [build_course()]

    async def list_timetable_for_user(self, pool, user_id):
        if self.error is not None:
            raise self.error
        return [build_timetable_entry()]


def build_client(jwks_document, service: StubLecturerCourseService) -> TestClient:
    app = create_app(enable_database=False)
    app.state.settings = build_settings()
    app.state.db_pool = FakePool(default_connection())
    app.dependency_overrides[get_authentication_service] = (
        lambda: build_authentication_service_for_tests(jwks_document)
    )
    app.dependency_overrides[get_lecturer_course_service] = lambda: service
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def client(jwks_document):
    with build_client(jwks_document, StubLecturerCourseService()) as test_client:
        yield test_client


def test_lists_my_courses(client: TestClient, make_access_token) -> None:
    response = client.get(COURSES_URL, headers=authorize(lecturer_token(make_access_token)))

    assert response.status_code == 200
    body = response.json()
    assert body[0]["courseOfferingId"] == str(COURSE_OFFERING_ID)
    assert body[0]["attendanceRatePercent"] is None


def test_lists_my_timetable(client: TestClient, make_access_token) -> None:
    response = client.get(TIMETABLE_URL, headers=authorize(lecturer_token(make_access_token)))

    assert response.status_code == 200
    body = response.json()
    assert body[0]["dayOfWeek"] == 1
    assert body[0]["startTime"] == "09:00:00"


def test_courses_rejects_non_lecturer_role(client: TestClient, make_access_token) -> None:
    response = client.get(
        COURSES_URL,
        headers=authorize(make_access_token(subject=LINKED_STUDENT_SUBJECT, roles=("student",))),
    )

    assert response.status_code == 403


def test_courses_missing_profile_returns_404(jwks_document, make_access_token) -> None:
    service = StubLecturerCourseService(error=LecturerProfileNotFoundError())
    with build_client(jwks_document, service) as client:
        response = client.get(COURSES_URL, headers=authorize(lecturer_token(make_access_token)))

    assert response.status_code == 404


def test_requires_bearer_token(client: TestClient) -> None:
    response = client.get(COURSES_URL)

    assert response.status_code == 401
