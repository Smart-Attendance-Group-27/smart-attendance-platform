from datetime import UTC, datetime
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
from modules.academic.lecturer_profile.exception import LecturerProfileNotFoundError
from modules.academic.lecturer_reports.exception import CourseOfferingNotFoundError
from modules.academic.lecturer_reports.repository import (
    AtRiskStudentRecord,
    CourseSessionReportRecord,
    LecturerOverviewRecord,
    WeeklyTrendRecord,
)
from modules.academic.lecturer_reports.route import get_lecturer_report_service
from modules.identity.auth.dependencies import get_authentication_service

OVERVIEW_URL = "/api/v1/lecturers/me/dashboard-overview"
COURSE_OFFERING_ID = UUID("30000000-0000-0000-0000-000000000001")
REPORT_URL = f"/api/v1/lecturers/me/reports/courses/{COURSE_OFFERING_ID}"
TREND_URL = "/api/v1/lecturers/me/reports/attendance-trend"
AT_RISK_URL = "/api/v1/lecturers/me/reports/at-risk-students"
SESSION_ID = UUID("40000000-0000-0000-0000-000000000001")
STUDENT_ID = UUID("23000000-0000-0000-0000-000000000001")
CURRENT_TIME = datetime(2026, 8, 13, 5, 30, tzinfo=UTC)


def authorize(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def lecturer_token(make_access_token) -> str:
    return make_access_token(subject=LINKED_LECTURER_SUBJECT, roles=("lecturer",))


def build_overview() -> LecturerOverviewRecord:
    return LecturerOverviewRecord(
        active_course_count=3,
        upcoming_session_count=2,
        today_session_count=1,
        average_attendance_rate_percent=None,
        pending_review_count=0,
    )


def build_session_report() -> CourseSessionReportRecord:
    return CourseSessionReportRecord(
        session_id=SESSION_ID,
        scheduled_start_at=CURRENT_TIME,
        activated_at=None,
        closed_at=None,
        cancelled_at=None,
        enrolled_count=40,
        present_count=0,
        late_count=0,
        absent_count=0,
        pending_review_count=0,
    )


def build_trend_point() -> WeeklyTrendRecord:
    return WeeklyTrendRecord(week_start=CURRENT_TIME, attendance_rate_percent=88.5)


def build_at_risk_student() -> AtRiskStudentRecord:
    return AtRiskStudentRecord(
        student_id=STUDENT_ID,
        registration_number="230701A",
        full_name="Amal Perera",
        course_code="CS3203",
        attendance_rate_percent=58.6,
        late_count=3,
        last_attended_at=CURRENT_TIME,
    )


class StubLecturerReportService:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error

    async def get_overview_for_user(self, pool, user_id):
        if self.error is not None:
            raise self.error
        return build_overview()

    async def get_course_session_report_for_user(self, pool, user_id, course_offering_id):
        if self.error is not None:
            raise self.error
        return [build_session_report()]

    async def get_attendance_trend_for_user(self, pool, user_id):
        if self.error is not None:
            raise self.error
        return [build_trend_point()]

    async def get_at_risk_students_for_user(self, pool, user_id):
        if self.error is not None:
            raise self.error
        return [build_at_risk_student()]


def build_client(jwks_document, service: StubLecturerReportService) -> TestClient:
    app = create_app(enable_database=False)
    app.state.settings = build_settings()
    app.state.db_pool = FakePool(default_connection())
    app.dependency_overrides[get_authentication_service] = (
        lambda: build_authentication_service_for_tests(jwks_document)
    )
    app.dependency_overrides[get_lecturer_report_service] = lambda: service
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def client(jwks_document):
    with build_client(jwks_document, StubLecturerReportService()) as test_client:
        yield test_client


def test_returns_dashboard_overview(client: TestClient, make_access_token) -> None:
    response = client.get(OVERVIEW_URL, headers=authorize(lecturer_token(make_access_token)))

    assert response.status_code == 200
    body = response.json()
    assert body["activeCourseCount"] == 3
    assert body["pendingReviewCount"] == 0


def test_overview_rejects_non_lecturer_role(client: TestClient, make_access_token) -> None:
    response = client.get(
        OVERVIEW_URL,
        headers=authorize(make_access_token(subject=LINKED_STUDENT_SUBJECT, roles=("student",))),
    )

    assert response.status_code == 403


def test_overview_missing_profile_returns_404(jwks_document, make_access_token) -> None:
    service = StubLecturerReportService(error=LecturerProfileNotFoundError())
    with build_client(jwks_document, service) as client:
        response = client.get(OVERVIEW_URL, headers=authorize(lecturer_token(make_access_token)))

    assert response.status_code == 404


def test_returns_course_session_report(client: TestClient, make_access_token) -> None:
    response = client.get(REPORT_URL, headers=authorize(lecturer_token(make_access_token)))

    assert response.status_code == 200
    body = response.json()
    assert body[0]["sessionId"] == str(SESSION_ID)
    assert body[0]["status"] == "scheduled"


def test_report_for_unowned_course_returns_404(jwks_document, make_access_token) -> None:
    service = StubLecturerReportService(error=CourseOfferingNotFoundError())
    with build_client(jwks_document, service) as client:
        response = client.get(REPORT_URL, headers=authorize(lecturer_token(make_access_token)))

    assert response.status_code == 404


def test_returns_attendance_trend(client: TestClient, make_access_token) -> None:
    response = client.get(TREND_URL, headers=authorize(lecturer_token(make_access_token)))

    assert response.status_code == 200
    body = response.json()
    assert body[0]["attendanceRate"] == 88.5


def test_trend_missing_profile_returns_404(jwks_document, make_access_token) -> None:
    service = StubLecturerReportService(error=LecturerProfileNotFoundError())
    with build_client(jwks_document, service) as client:
        response = client.get(TREND_URL, headers=authorize(lecturer_token(make_access_token)))

    assert response.status_code == 404


def test_returns_at_risk_students(client: TestClient, make_access_token) -> None:
    response = client.get(AT_RISK_URL, headers=authorize(lecturer_token(make_access_token)))

    assert response.status_code == 200
    body = response.json()
    assert body[0]["studentId"] == str(STUDENT_ID)
    assert body[0]["attendanceRatePercent"] == 58.6


def test_at_risk_students_rejects_non_lecturer_role(client: TestClient, make_access_token) -> None:
    response = client.get(
        AT_RISK_URL,
        headers=authorize(make_access_token(subject=LINKED_STUDENT_SUBJECT, roles=("student",))),
    )

    assert response.status_code == 403


def test_requires_bearer_token(client: TestClient) -> None:
    response = client.get(OVERVIEW_URL)

    assert response.status_code == 401
