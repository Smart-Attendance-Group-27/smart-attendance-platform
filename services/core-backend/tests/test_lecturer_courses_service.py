from datetime import time
from decimal import Decimal
from uuid import UUID

import pytest

from modules.academic.lecturer_courses.repository import (
    LecturerCourseRecord,
    LecturerTimetableEntryRecord,
)
from modules.academic.lecturer_courses.service import LecturerCourseService
from modules.academic.lecturer_profile.exception import LecturerProfileNotFoundError
from modules.academic.lecturer_profile.repository import LecturerProfileRecord

USER_ID = UUID("20000000-0000-0000-0000-000000000002")
LECTURER_ID = UUID("22000000-0000-0000-0000-000000000001")


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
        self.requested_user_id: UUID | None = None

    async def find_by_user_id(self, connection, user_id: UUID) -> LecturerProfileRecord | None:
        self.requested_user_id = user_id
        return self.profile


class FakeLecturerCourseRepository:
    def __init__(
        self,
        courses: list[LecturerCourseRecord],
        timetable: list[LecturerTimetableEntryRecord],
    ) -> None:
        self.courses = courses
        self.timetable = timetable
        self.requested_lecturer_id_for_courses: UUID | None = None
        self.requested_lecturer_id_for_timetable: UUID | None = None

    async def list_courses_for_lecturer(self, connection, lecturer_id: UUID):
        self.requested_lecturer_id_for_courses = lecturer_id
        return self.courses

    async def list_timetable_for_lecturer(self, connection, lecturer_id: UUID):
        self.requested_lecturer_id_for_timetable = lecturer_id
        return self.timetable


def build_profile(*, status: str = "active") -> LecturerProfileRecord:
    return LecturerProfileRecord(
        id=LECTURER_ID,
        user_id=USER_ID,
        employee_number="EMP001",
        first_name="Nadeesha",
        middle_name=None,
        last_name="Perera",
        profile_status=status,
        university_email="n.perera@staff.uniattend.test",
    )


def build_course() -> LecturerCourseRecord:
    return LecturerCourseRecord(
        course_offering_id=UUID("30000000-0000-0000-0000-000000000001"),
        course_code="CS3203",
        course_name="Software Engineering Project",
        department_name="Computer Science",
        course_type="core",
        status="active",
        enrolled_count=40,
        attendance_rate_percent=Decimal("90.0"),
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


async def test_list_courses_resolves_lecturer_id_and_returns_repository_data() -> None:
    profile_repository = FakeLecturerProfileRepository(build_profile())
    course_repository = FakeLecturerCourseRepository([build_course()], [])
    service = LecturerCourseService(
        repository=course_repository,
        lecturer_profile_repository=profile_repository,
    )

    courses = await service.list_courses_for_user(FakePool(), USER_ID)

    assert courses == [build_course()]
    assert profile_repository.requested_user_id == USER_ID
    assert course_repository.requested_lecturer_id_for_courses == LECTURER_ID


async def test_list_timetable_resolves_lecturer_id_and_returns_repository_data() -> None:
    profile_repository = FakeLecturerProfileRepository(build_profile())
    course_repository = FakeLecturerCourseRepository([], [build_timetable_entry()])
    service = LecturerCourseService(
        repository=course_repository,
        lecturer_profile_repository=profile_repository,
    )

    timetable = await service.list_timetable_for_user(FakePool(), USER_ID)

    assert timetable == [build_timetable_entry()]
    assert course_repository.requested_lecturer_id_for_timetable == LECTURER_ID


@pytest.mark.parametrize("profile", [None, build_profile(status="archived")])
async def test_rejects_missing_or_inactive_lecturer_profile(
    profile: LecturerProfileRecord | None,
) -> None:
    course_repository = FakeLecturerCourseRepository([build_course()], [])
    service = LecturerCourseService(
        repository=course_repository,
        lecturer_profile_repository=FakeLecturerProfileRepository(profile),
    )

    with pytest.raises(LecturerProfileNotFoundError):
        await service.list_courses_for_user(FakePool(), USER_ID)

    assert course_repository.requested_lecturer_id_for_courses is None
