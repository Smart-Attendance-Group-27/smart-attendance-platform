from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest

from modules.academic.lecturer_profile.exception import LecturerProfileNotFoundError
from modules.academic.lecturer_profile.repository import LecturerProfileRecord
from modules.academic.lecturer_reports.exception import CourseOfferingNotFoundError
from modules.academic.lecturer_reports.repository import (
    AtRiskStudentRecord,
    CourseSessionReportRecord,
    LecturerOverviewRecord,
    WeeklyTrendRecord,
)
from modules.academic.lecturer_reports.service import LecturerReportService

USER_ID = UUID("20000000-0000-0000-0000-000000000002")
LECTURER_ID = UUID("22000000-0000-0000-0000-000000000001")
COURSE_OFFERING_ID = UUID("30000000-0000-0000-0000-000000000001")
STUDENT_ID = UUID("23000000-0000-0000-0000-000000000001")
CURRENT_TIME = datetime(2026, 8, 13, 5, 30, tzinfo=UTC)


class FakeAcquire:
    def __init__(self, connection: object) -> None:
        self.connection = connection

    async def __aenter__(self) -> object:
        return self.connection

    async def __aexit__(self, exc_type, exc, traceback) -> bool:
        return False


class FakePool:
    def __init__(self) -> None:
        self.connection = object()

    def acquire(self) -> FakeAcquire:
        return FakeAcquire(self.connection)


class FakeLecturerProfileRepository:
    def __init__(self, profile: LecturerProfileRecord | None) -> None:
        self.profile = profile

    async def find_by_user_id(self, connection, user_id: UUID) -> LecturerProfileRecord | None:
        return self.profile


class FakeLecturerReportRepository:
    def __init__(self, *, owns_course: bool = True) -> None:
        self.owns_course = owns_course
        self.overview = LecturerOverviewRecord(
            active_course_count=3,
            upcoming_session_count=1,
            today_session_count=0,
            average_attendance_rate_percent=Decimal("88.5"),
            pending_review_count=0,
        )
        self.session_report = [
            CourseSessionReportRecord(
                session_id=UUID("40000000-0000-0000-0000-000000000001"),
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
        ]
        self.trend = [WeeklyTrendRecord(week_start=CURRENT_TIME, attendance_rate_percent=Decimal("88.5"))]
        self.at_risk_students = [
            AtRiskStudentRecord(
                student_id=STUDENT_ID,
                registration_number="230701A",
                full_name="Amal Perera",
                course_code="CS3203",
                attendance_rate_percent=Decimal("58.6"),
                late_count=3,
                last_attended_at=CURRENT_TIME,
            )
        ]
        self.requested_course_offering_id: UUID | None = None

    async def get_overview_for_lecturer(self, connection, lecturer_id: UUID):
        return self.overview

    async def lecturer_owns_course_offering(self, connection, lecturer_id: UUID, course_offering_id: UUID) -> bool:
        self.requested_course_offering_id = course_offering_id
        return self.owns_course

    async def list_session_report_for_course(self, connection, course_offering_id: UUID):
        return self.session_report

    async def list_attendance_trend_for_lecturer(self, connection, lecturer_id: UUID, *, weeks: int = 8):
        return self.trend

    async def list_at_risk_students_for_lecturer(self, connection, lecturer_id: UUID, *, threshold_percent: int = 70):
        return self.at_risk_students


def build_profile() -> LecturerProfileRecord:
    return LecturerProfileRecord(
        id=LECTURER_ID,
        user_id=USER_ID,
        employee_number="EMP001",
        first_name="Nadeesha",
        middle_name=None,
        last_name="Perera",
        profile_status="active",
        university_email="n.perera@staff.uniattend.test",
    )


async def test_get_overview_returns_repository_data() -> None:
    repository = FakeLecturerReportRepository()
    service = LecturerReportService(
        repository=repository,
        lecturer_profile_repository=FakeLecturerProfileRepository(build_profile()),
    )

    overview = await service.get_overview_for_user(FakePool(), USER_ID)

    assert overview == repository.overview


async def test_get_course_session_report_checks_ownership_first() -> None:
    repository = FakeLecturerReportRepository(owns_course=True)
    service = LecturerReportService(
        repository=repository,
        lecturer_profile_repository=FakeLecturerProfileRepository(build_profile()),
    )

    report = await service.get_course_session_report_for_user(FakePool(), USER_ID, COURSE_OFFERING_ID)

    assert report == repository.session_report
    assert repository.requested_course_offering_id == COURSE_OFFERING_ID


async def test_get_course_session_report_rejects_unowned_course() -> None:
    repository = FakeLecturerReportRepository(owns_course=False)
    service = LecturerReportService(
        repository=repository,
        lecturer_profile_repository=FakeLecturerProfileRepository(build_profile()),
    )

    with pytest.raises(CourseOfferingNotFoundError):
        await service.get_course_session_report_for_user(FakePool(), USER_ID, COURSE_OFFERING_ID)


async def test_get_attendance_trend_returns_repository_data() -> None:
    repository = FakeLecturerReportRepository()
    service = LecturerReportService(
        repository=repository,
        lecturer_profile_repository=FakeLecturerProfileRepository(build_profile()),
    )

    trend = await service.get_attendance_trend_for_user(FakePool(), USER_ID)

    assert trend == repository.trend


async def test_get_at_risk_students_returns_repository_data() -> None:
    repository = FakeLecturerReportRepository()
    service = LecturerReportService(
        repository=repository,
        lecturer_profile_repository=FakeLecturerProfileRepository(build_profile()),
    )

    students = await service.get_at_risk_students_for_user(FakePool(), USER_ID)

    assert students == repository.at_risk_students


async def test_rejects_missing_lecturer_profile_for_every_method() -> None:
    repository = FakeLecturerReportRepository()
    service = LecturerReportService(
        repository=repository,
        lecturer_profile_repository=FakeLecturerProfileRepository(None),
    )

    with pytest.raises(LecturerProfileNotFoundError):
        await service.get_overview_for_user(FakePool(), USER_ID)
    with pytest.raises(LecturerProfileNotFoundError):
        await service.get_attendance_trend_for_user(FakePool(), USER_ID)
    with pytest.raises(LecturerProfileNotFoundError):
        await service.get_at_risk_students_for_user(FakePool(), USER_ID)
