from datetime import UTC, datetime, timezone
from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo

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
from modules.academic.student_courses.repository import (
    StudentCourseRecord,
    StudentCourseSessionRecord,
)
from modules.academic.student_courses.route import get_student_course_service
from modules.academic.student_courses.service import (
    StudentCourse,
    StudentCourseService,
    StudentCourseSession,
    _format_week_header,
    _group_attendance_records_by_course,
    _group_sessions_by_course,
    resolve_time_zone,
)
from modules.academic.student_profile.repository import StudentProfileRecord
from modules.identity.auth.dependencies import get_authentication_service

COLOMBO = ZoneInfo("Asia/Colombo")
OFFERING_ID = UUID("30000000-0000-0000-0000-000000000001")
SESSION_ID = UUID("40000000-0000-0000-0000-000000000001")
USER_ID = UUID("20000000-0000-0000-0000-000000000001")
STUDENT_ID = UUID("21000000-0000-0000-0000-000000000001")


def session_at(start_utc: datetime, end_utc: datetime | None = None) -> StudentCourseSessionRecord:
    end = end_utc or start_utc.replace(hour=(start_utc.hour + 2) % 24)
    return StudentCourseSessionRecord(
        id=SESSION_ID,
        course_offering_id=OFFERING_ID,
        session_title="Lecture",
        session_type="lecture",
        scheduled_start_at=start_utc,
        scheduled_end_at=end,
        check_in_opens_at=start_utc,
        check_in_closes_at=end,
        venue="Hall 02",
        status="scheduled",
        closed_at=None,
        cancelled_at=None,
        attendance_status=None,
        attendance_recorded_at=None,
    )


def test_session_times_are_shown_in_the_institution_timezone() -> None:
    start = datetime(2026, 9, 25, 3, 30, tzinfo=UTC)  # 09:00 in Colombo
    end = datetime(2026, 9, 25, 5, 30, tzinfo=UTC)
    now = datetime(2026, 9, 25, 2, 0, tzinfo=UTC)

    [session] = _group_sessions_by_course([session_at(start, end)], COLOMBO, now)[OFFERING_ID]

    assert session.time_text == "Today · 09:00-11:00 · Hall 02 · Lecture"
    assert session.starts_at == start
    assert session.ends_at == end
    assert session.venue == "Hall 02"


def test_today_and_tomorrow_follow_local_dates_not_utc() -> None:
    # 00:30 on the 25th in Colombo is still the 24th in UTC.
    start = datetime(2026, 9, 24, 19, 0, tzinfo=UTC)
    now = datetime(2026, 9, 24, 12, 0, tzinfo=UTC)  # 17:30 on the 24th in Colombo

    [session] = _group_sessions_by_course([session_at(start)], COLOMBO, now)[OFFERING_ID]
    [record] = _group_attendance_records_by_course([session_at(start)], COLOMBO, now)[OFFERING_ID]

    assert session.time_text.startswith("Tomorrow · 00:30")
    assert (record.day, record.month) == ("25", "SEP")


def test_recorded_time_uses_the_local_clock() -> None:
    start = datetime(2026, 9, 25, 3, 30, tzinfo=UTC)
    row = session_at(start)
    row = StudentCourseSessionRecord(
        **{**row.__dict__, "attendance_status": "present", "attendance_recorded_at": start, "closed_at": start},
    )

    [session] = _group_sessions_by_course([row], COLOMBO, start)[OFFERING_ID]

    assert session.recorded_time == "Recorded at 09:00"


@pytest.mark.parametrize(
    ("session_day", "expected"),
    [
        (datetime(2026, 9, 23, 6, 0, tzinfo=UTC), "This week"),  # Wed, same week as Fri 25th
        (datetime(2026, 9, 28, 6, 0, tzinfo=UTC), "Next week"),
        (datetime(2026, 9, 17, 6, 0, tzinfo=UTC), "Last week"),
        (datetime(2026, 9, 2, 6, 0, tzinfo=UTC), "31 Aug–06 Sep"),
    ],
)
def test_week_headers_group_by_monday_to_sunday_week(session_day, expected) -> None:
    now = datetime(2026, 9, 25, 6, 0, tzinfo=UTC)

    assert _format_week_header(session_day, COLOMBO, now) == expected


def test_unknown_timezone_falls_back_to_utc() -> None:
    assert resolve_time_zone("Not/AZone") is timezone.utc
    assert resolve_time_zone("Asia/Colombo").key == "Asia/Colombo"


class FakeProfiles:
    async def find_by_user_id(self, connection, user_id):
        return StudentProfileRecord(
            id=STUDENT_ID,
            user_id=USER_ID,
            registration_number="230701A",
            first_name="Amal",
            middle_name=None,
            last_name="Perera",
            profile_status="active",
            university_email=None,
        )


class FakeCourseRepository:
    def __init__(self, percentage, threshold) -> None:
        self.percentage = percentage
        self.threshold = threshold

    async def list_courses_for_student(self, connection, student_id):
        return [
            StudentCourseRecord(
                course_offering_id=OFFERING_ID,
                course_code="CS3203",
                course_name="Software Engineering Project",
                lecturers=None,
                semester_number=2,
                academic_year_start=None,
                attended_sessions=0,
                total_sessions=0,
                attendance_percentage=self.percentage,
                attendance_threshold=self.threshold,
            )
        ]

    async def list_sessions_for_student_courses(self, connection, student_id):
        return []


class FakeAcquire:
    async def __aenter__(self):
        return object()

    async def __aexit__(self, *exc):
        return False


class FakeServicePool:
    def acquire(self):
        return FakeAcquire()


async def test_a_course_without_closed_sessions_reports_zero_sessions_and_carries_its_threshold() -> None:
    service = StudentCourseService(FakeCourseRepository(None, Decimal("75")), FakeProfiles())

    [course] = await service.list_courses_for_user(FakeServicePool(), USER_ID, "Asia/Colombo")

    assert course.total_sessions == 0
    assert course.attendance_percentage == 0
    assert course.attendance_threshold_percent == 75.0


async def test_a_course_without_a_threshold_reports_none() -> None:
    service = StudentCourseService(FakeCourseRepository(Decimal("64.6"), None), FakeProfiles())

    [course] = await service.list_courses_for_user(FakeServicePool(), USER_ID)

    assert course.attendance_percentage == 65
    assert course.attendance_threshold_percent is None


class StubCourseService:
    def __init__(self) -> None:
        self.time_zone: str | None = None

    async def list_courses_for_user(self, pool, user_id, time_zone_name="UTC"):
        self.time_zone = time_zone_name
        start = datetime(2026, 9, 25, 3, 30, tzinfo=UTC)
        return [
            StudentCourse(
                id=OFFERING_ID,
                code="CS3203",
                title="Software Engineering Project",
                lecturer="Dr N. Perera",
                semester="Semester 2, 2026",
                attended_sessions=0,
                total_sessions=0,
                attendance_percentage=0,
                attendance_threshold_percent=80.0,
                sessions=[
                    StudentCourseSession(
                        id=SESSION_ID,
                        title="Lecture",
                        time_text="Today · 09:00-11:00 · Hall 02 · Lecture",
                        type="Lecture",
                        status="upcoming",
                        recorded_time=None,
                        week_header="This week",
                        starts_at=start,
                        ends_at=start.replace(hour=5),
                        venue="Hall 02",
                    )
                ],
                attendance_records=[],
            )
        ]


def build_client(jwks_document, service) -> TestClient:
    app = create_app(enable_database=False)
    app.state.settings = build_settings(app_timezone="Asia/Colombo")
    app.state.db_pool = FakePool(default_connection())
    app.dependency_overrides[get_authentication_service] = (
        lambda: build_authentication_service_for_tests(jwks_document)
    )
    app.dependency_overrides[get_student_course_service] = lambda: service
    return TestClient(app, raise_server_exceptions=False)


def test_courses_endpoint_returns_real_timestamps_and_threshold_and_keeps_percentage_numeric(
    jwks_document, make_access_token,
) -> None:
    service = StubCourseService()
    token = make_access_token(subject=LINKED_STUDENT_SUBJECT, roles=("student",))
    with build_client(jwks_document, service) as client:
        response = client.get("/api/v1/students/me/courses", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    [course] = response.json()
    assert course["attendancePercentage"] == 0
    assert course["attendanceThresholdPercent"] == 80.0
    assert course["sessions"][0]["startsAt"] == "2026-09-25T03:30:00Z"
    assert course["sessions"][0]["venue"] == "Hall 02"
    assert service.time_zone == "Asia/Colombo"


def test_courses_endpoint_is_student_only(jwks_document, make_access_token) -> None:
    token = make_access_token(subject=LINKED_LECTURER_SUBJECT, roles=("lecturer",))
    with build_client(jwks_document, StubCourseService()) as client:
        response = client.get("/api/v1/students/me/courses", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 403
