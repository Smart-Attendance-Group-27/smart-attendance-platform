from datetime import UTC, datetime

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
from modules.academic.admin_institution_reports.repository import (
    AtRiskCourseRecord,
    FacultyAttendanceRecord,
    InstitutionSummaryRecord,
    WeeklyTrendRecord,
)
from modules.academic.admin_institution_reports.route import (
    get_admin_institution_report_service,
)
from modules.academic.admin_institution_reports.service import InstitutionReports
from modules.identity.auth.dependencies import get_authentication_service

REPORTS_URL = "/api/v1/administrators/me/institution-reports"


def authorize(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def admin_token(make_access_token) -> str:
    return make_access_token(subject=LINKED_ADMINISTRATOR_SUBJECT, roles=("administrator",))


class StubInstitutionReportService:
    async def get_reports(self, pool):
        return InstitutionReports(
            summary=InstitutionSummaryRecord(
                overall_attendance_percent=87.4,
                total_sessions_completed=12,
                total_students=100,
                total_lecturers=6,
                students_at_risk_count=3,
            ),
            attendance_trend=[
                WeeklyTrendRecord(week_start=datetime(2026, 8, 3, tzinfo=UTC), attendance_rate_percent=84),
                WeeklyTrendRecord(week_start=datetime(2026, 8, 10, tzinfo=UTC), attendance_rate_percent=90),
            ],
            attendance_by_faculty=[
                FacultyAttendanceRecord(faculty_name="Faculty of Engineering", attendance_rate_percent=88.5),
            ],
            at_risk_courses=[
                AtRiskCourseRecord(course_code="CS6101", course_name="Cybersecurity Fundamentals", attendance_rate_percent=65.0),
            ],
        )


def build_client(jwks_document, service) -> TestClient:
    app = create_app(enable_database=False)
    app.state.settings = build_settings()
    app.state.db_pool = FakePool(default_connection())
    app.dependency_overrides[get_authentication_service] = (
        lambda: build_authentication_service_for_tests(jwks_document)
    )
    app.dependency_overrides[get_admin_institution_report_service] = lambda: service
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def client(jwks_document):
    with build_client(jwks_document, StubInstitutionReportService()) as test_client:
        yield test_client


def test_returns_institution_reports(client: TestClient, make_access_token) -> None:
    response = client.get(REPORTS_URL, headers=authorize(admin_token(make_access_token)))

    assert response.status_code == 200
    body = response.json()
    assert body["summary"]["totalStudents"] == 100
    assert body["summary"]["studentsAtRiskCount"] == 3
    assert body["attendanceTrend"] == [
        {"label": "Aug 3", "attendanceRate": 84.0},
        {"label": "Aug 10", "attendanceRate": 90.0},
    ]
    assert body["attendanceByFaculty"][0]["facultyName"] == "Faculty of Engineering"
    assert body["atRiskCourses"][0]["courseCode"] == "CS6101"


def test_rejects_non_administrator_role(client: TestClient, make_access_token) -> None:
    response = client.get(
        REPORTS_URL,
        headers=authorize(make_access_token(subject=LINKED_STUDENT_SUBJECT, roles=("student",))),
    )

    assert response.status_code == 403


def test_requires_bearer_token(client: TestClient) -> None:
    response = client.get(REPORTS_URL)

    assert response.status_code == 401
