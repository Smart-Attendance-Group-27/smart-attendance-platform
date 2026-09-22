from datetime import date, time
from decimal import Decimal
from types import MethodType
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

import modules.academic.admin_academic_data.service as service_module
from conftest import FakePool, default_connection
from modules.academic.admin_academic_data.exception import AcademicConflictError
from modules.academic.admin_academic_data.repository import (
    AdminAcademicDataRepository,
    AdminCourseOfferingRecord,
    AdminCourseRecord,
    AdminEnrolmentRecord,
    AdminTimetableEntryRecord,
)
from modules.academic.admin_academic_data.service import AdminAcademicDataService


COURSE_ID = UUID("36000000-0000-0000-0000-000000000001")
OFFERING_ID = UUID("37000000-0000-0000-0000-000000000001")
LECTURER_ID = UUID("38000000-0000-0000-0000-000000000001")
ENROLMENT_ID = UUID("39000000-0000-0000-0000-000000000001")
ENTRY_ID = UUID("3a000000-0000-0000-0000-000000000001")
DEPARTMENT_ID = UUID("35000000-0000-0000-0000-000000000001")
SEMESTER_ID = UUID("34000000-0000-0000-0000-000000000001")
STUDENT_ID = UUID("33000000-0000-0000-0000-000000000001")
CLASSROOM_ID = UUID("3b000000-0000-0000-0000-000000000001")


def course() -> AdminCourseRecord:
    return AdminCourseRecord(
        id=COURSE_ID,
        course_code="CS3203",
        course_name="Software Engineering Project",
        department_id=DEPARTMENT_ID,
        department_name="Computer Science",
        credits=Decimal("3"),
        status="active",
    )


def offering() -> AdminCourseOfferingRecord:
    return AdminCourseOfferingRecord(
        id=OFFERING_ID,
        course_id=COURSE_ID,
        semester_id=SEMESTER_ID,
        lecturer_id=LECTURER_ID,
        lecturer_name="N. Perera",
        course_code="CS3203",
        course_name="Software Engineering Project",
        semester_label="Semester 1 (2026)",
        batch_year=2023,
        course_type="core",
        attendance_threshold_percent=Decimal("80"),
        enrolled_count=1,
        status="active",
    )


def enrolment(status: str = "enrolled") -> AdminEnrolmentRecord:
    return AdminEnrolmentRecord(
        id=ENROLMENT_ID,
        course_offering_id=OFFERING_ID,
        student_id=STUDENT_ID,
        student_name="Amal Perera",
        registration_number="230701A",
        course_code="CS3203",
        semester_label="Semester 1 (2026)",
        enrolment_status=status,
    )


def timetable(status: str = "active") -> AdminTimetableEntryRecord:
    return AdminTimetableEntryRecord(
        id=ENTRY_ID,
        course_offering_id=OFFERING_ID,
        classroom_id=CLASSROOM_ID,
        course_code="CS3203",
        course_name="Software Engineering Project",
        day_of_week=1,
        start_time=time(9),
        end_time=time(11),
        classroom_code="LH-02",
        lecturer_name="N. Perera",
        course_type="lecture",
        valid_from=date(2026, 1, 1),
        valid_until=date(2026, 6, 30),
        status=status,
    )


@pytest.fixture
def pool() -> FakePool:
    class Transaction:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return False

    connection = default_connection()
    connection.transaction = MethodType(lambda self: Transaction(), connection)
    return FakePool(connection)


@pytest.fixture
def repository() -> AsyncMock:
    repository = AsyncMock(spec=AdminAcademicDataRepository)
    repository.reference_exists.return_value = True
    repository.course_code_exists.return_value = False
    repository.offering_natural_key_exists.return_value = False
    repository.timetable_key_exists.return_value = False
    return repository


@pytest.fixture
def audit(monkeypatch) -> AsyncMock:
    write = AsyncMock()
    monkeypatch.setattr(service_module, "write_audit_log", write)
    return write


@pytest.mark.asyncio
async def test_create_course_writes_audit_row(pool, repository, audit) -> None:
    repository.find_course.return_value = course()
    service = AdminAcademicDataService(repository)
    actor = uuid4()

    result = await service.create_course(
        pool,
        actor,
        course_code="cs3203",
        course_name="Software Engineering Project",
        department_id=DEPARTMENT_ID,
        credits=Decimal("3"),
        status="active",
    )

    assert result.course_code == "CS3203"
    assert repository.create_course.await_args.kwargs["course_code"] == "CS3203"
    assert audit.await_args.kwargs["action"] == "course.create"


@pytest.mark.asyncio
async def test_duplicate_course_code_is_clean_conflict(pool, repository, audit) -> None:
    repository.course_code_exists.return_value = True
    service = AdminAcademicDataService(repository)

    with pytest.raises(AcademicConflictError):
        await service.create_course(
            pool,
            uuid4(),
            course_code="CS3203",
            course_name="Duplicate",
            department_id=DEPARTMENT_ID,
            credits=Decimal("3"),
            status="active",
        )

    repository.create_course.assert_not_awaited()
    audit.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_offering_assigns_lecturer_and_audits(pool, repository, audit) -> None:
    repository.find_offering.return_value = offering()
    service = AdminAcademicDataService(repository)

    await service.create_offering(
        pool,
        uuid4(),
        course_id=COURSE_ID,
        semester_id=SEMESTER_ID,
        lecturer_id=LECTURER_ID,
        batch_year=2023,
        course_type="core",
        attendance_threshold=Decimal("80"),
        status="active",
    )

    repository.set_offering_lecturer.assert_awaited_once()
    assert audit.await_args.kwargs["action"] == "course_offering.create"


@pytest.mark.asyncio
async def test_enrol_student_reactivates_dropped_row_and_audits(pool, repository, audit) -> None:
    repository.find_enrolment.side_effect = [enrolment("dropped"), enrolment()]
    service = AdminAcademicDataService(repository)

    result = await service.enrol_student(pool, uuid4(), OFFERING_ID, STUDENT_ID)

    assert result.enrolment_status == "enrolled"
    assert repository.enrol_student.await_args.kwargs["enrolment_id"] == ENROLMENT_ID
    assert audit.await_args.kwargs["action"] == "course_enrolment.enrol"


@pytest.mark.asyncio
async def test_create_timetable_entry_audits(pool, repository, audit) -> None:
    repository.find_timetable_entry.return_value = timetable()
    service = AdminAcademicDataService(repository)

    await service.create_timetable_entry(
        pool,
        uuid4(),
        offering_id=OFFERING_ID,
        classroom_id=CLASSROOM_ID,
        day_of_week=1,
        start_time=time(9),
        end_time=time(11),
        course_type="lecture",
        valid_from=date(2026, 1, 1),
        valid_until=date(2026, 6, 30),
        status="active",
    )

    assert audit.await_args.kwargs["action"] == "timetable_entry.create"


@pytest.mark.asyncio
async def test_drop_enrolment_updates_status_without_deleting_row() -> None:
    connection = AsyncMock()
    connection.execute.return_value = "UPDATE 1"

    updated = await AdminAcademicDataRepository().drop_enrolment(
        connection, OFFERING_ID, STUDENT_ID
    )

    assert updated is True
    query = connection.execute.await_args.args[0]
    assert "UPDATE academic.course_enrolments" in query
    assert "enrolment_status='dropped'" in query
    assert "DELETE" not in query


@pytest.mark.asyncio
async def test_roster_query_is_scoped_to_offering() -> None:
    connection = AsyncMock()
    connection.fetch.return_value = [{
        "id": ENROLMENT_ID,
        "course_offering_id": OFFERING_ID,
        "student_id": STUDENT_ID,
        "student_name": "Amal Perera",
        "registration_number": "230701A",
        "course_code": "CS3203",
        "semester_label": "Semester 1 (2026)",
        "enrolment_status": "enrolled",
    }]

    records = await AdminAcademicDataRepository().list_enrolments(connection, OFFERING_ID)

    assert records[0].student_id == STUDENT_ID
    query, argument = connection.fetch.await_args.args
    assert "enrolment.course_offering_id=$1" in query
    assert argument == OFFERING_ID
