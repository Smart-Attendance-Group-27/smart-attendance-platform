"""LecturerSessionService.list_students_for_user against FakeQrEvidenceProvider.

This is the merge that answers "how much QR evidence does this student have":
null when nobody has bound a real provider yet (before INT-1), null for a
student who never checked in (the provider never reports on them), and the
real counts otherwise.
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from fakes import FakeQrEvidenceProvider
from modules.academic.lecturer_profile.repository import LecturerProfileRecord
from modules.attendance_sessions.lecturer_sessions.repository import (
    LecturerSessionRecord,
    SessionStudentRecord,
)
from modules.attendance_sessions.lecturer_sessions.service import LecturerSessionService

USER_ID = UUID("20000000-0000-0000-0000-000000000002")
LECTURER_ID = UUID("22000000-0000-0000-0000-000000000001")
SESSION_ID = UUID("40000000-0000-0000-0000-000000000001")
CHECKED_IN_STUDENT_ID = UUID("23000000-0000-0000-0000-000000000001")
NOT_CHECKED_IN_STUDENT_ID = UUID("23000000-0000-0000-0000-000000000002")
CHECKED_IN_ATTEMPT_ID = UUID("50000000-0000-0000-0000-000000000001")


class FakeAcquire:
    def __init__(self, connection: object) -> None:
        self.connection = connection

    async def __aenter__(self) -> object:
        return self.connection

    async def __aexit__(self, exc_type: object, exc: object, traceback: object) -> bool:
        return False


class FakePool:
    def __init__(self) -> None:
        self.connection = object()

    def acquire(self) -> FakeAcquire:
        return FakeAcquire(self.connection)


class FakeLecturerProfileRepository:
    async def find_by_user_id(self, connection, user_id):
        return LecturerProfileRecord(
            id=LECTURER_ID,
            user_id=USER_ID,
            employee_number="E001",
            first_name="Nimal",
            middle_name=None,
            last_name="Perera",
            profile_status="active",
            university_email="n.perera@staff.uniattend.test",
        )


class FakeLecturerSessionRepository:
    def __init__(self, session: LecturerSessionRecord, students: list[SessionStudentRecord]) -> None:
        self.session = session
        self.students = students

    async def find_for_lecturer(self, connection, session_id, lecturer_id, *, lock_for_update=False):
        return self.session

    async def list_students_for_session(self, connection, session_id):
        return self.students


def build_session() -> LecturerSessionRecord:
    now = datetime(2026, 9, 21, 9, 5, tzinfo=UTC)
    return LecturerSessionRecord(
        id=SESSION_ID,
        course_offering_id=UUID("30000000-0000-0000-0000-000000000001"),
        course_code="CS3203",
        course_name="Software Engineering Project",
        classroom_code="LH-02",
        scheduled_start_at=now,
        scheduled_end_at=now + timedelta(hours=1),
        check_in_opens_at=now - timedelta(minutes=5),
        check_in_closes_at=now + timedelta(minutes=30),
        late_after_at=now + timedelta(minutes=15),
        activated_at=now,
        closed_at=None,
        cancelled_at=None,
        requires_face_verification=True,
        requires_geofence=True,
        requires_qr=True,
        enrolled_count=2,
        present_count=0,
        late_count=0,
        pending_review_count=0,
        checked_in_count=1,
        late_checked_in_count=0,
        failed_verification_count=0,
        absent_count=0,
        manual_count=0,
    )


def build_student(**overrides) -> SessionStudentRecord:
    values = dict(
        verification_attempt_id=CHECKED_IN_ATTEMPT_ID,
        student_id=CHECKED_IN_STUDENT_ID,
        registration_number="230701A",
        full_name="Amal Perera",
        verification_status="checked_in",
        failure_reason=None,
        geofence_status="passed",
        face_status=None,
        face_similarity_score=None,
        face_liveness_passed=None,
        initial_check_in_status="checked_in",
        checked_in_at=None,
        attendance_status=None,
        record_source=None,
        manual_reason=None,
        record_updated_at=None,
        review_status=None,
    )
    values.update(overrides)
    return SessionStudentRecord(**values)


def build_service(
    students: list[SessionStudentRecord],
    *,
    qr_evidence=None,
) -> LecturerSessionService:
    return LecturerSessionService(
        repository=FakeLecturerSessionRepository(build_session(), students),
        lecturer_profile_repository=FakeLecturerProfileRepository(),
        qr_evidence=qr_evidence,
    )


async def test_qr_counts_are_null_while_no_provider_is_bound() -> None:
    service = build_service([build_student()], qr_evidence=None)

    students = await service.list_students_for_user(FakePool(), USER_ID, SESSION_ID)

    assert students[0].qr_required_count is None
    assert students[0].qr_passed_count is None


async def test_qr_counts_are_filled_in_for_a_checked_in_student() -> None:
    provider = FakeQrEvidenceProvider()
    provider.set_progress(CHECKED_IN_ATTEMPT_ID, required_count=2, passed_count=1)
    service = build_service([build_student()], qr_evidence=provider)

    students = await service.list_students_for_user(FakePool(), USER_ID, SESSION_ID)

    assert students[0].qr_required_count == 2
    assert students[0].qr_passed_count == 1
    assert provider.requested_session_ids == [SESSION_ID]


async def test_a_student_who_never_checked_in_gets_null_qr_counts_even_when_bound() -> None:
    provider = FakeQrEvidenceProvider()
    provider.set_progress(CHECKED_IN_ATTEMPT_ID, required_count=1, passed_count=1)
    never_verified = build_student(
        verification_attempt_id=None,
        student_id=NOT_CHECKED_IN_STUDENT_ID,
        verification_status=None,
        initial_check_in_status=None,
        geofence_status=None,
    )
    service = build_service([build_student(), never_verified], qr_evidence=provider)

    students = await service.list_students_for_user(FakePool(), USER_ID, SESSION_ID)

    by_student = {student.student_id: student for student in students}
    assert by_student[CHECKED_IN_STUDENT_ID].qr_required_count == 1
    assert by_student[NOT_CHECKED_IN_STUDENT_ID].qr_required_count is None
    assert by_student[NOT_CHECKED_IN_STUDENT_ID].qr_passed_count is None


async def test_the_rest_of_the_student_record_is_left_untouched_by_the_merge() -> None:
    provider = FakeQrEvidenceProvider()
    provider.set_progress(CHECKED_IN_ATTEMPT_ID, required_count=1, passed_count=1)
    service = build_service(
        [build_student(full_name="Nimal Silva", registration_number="230702B")],
        qr_evidence=provider,
    )

    students = await service.list_students_for_user(FakePool(), USER_ID, SESSION_ID)

    assert students[0].full_name == "Nimal Silva"
    assert students[0].registration_number == "230702B"
