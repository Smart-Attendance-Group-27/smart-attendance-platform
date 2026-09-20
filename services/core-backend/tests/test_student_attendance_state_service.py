from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from modules.academic.student_profile.exception import StudentProfileNotFoundError
from modules.academic.student_profile.repository import StudentProfileRecord
from modules.attendance_sessions.active_sessions.state_service import (
    SessionNotFoundError,
    SessionState,
    StudentAttendanceStateService,
    StudentAttemptRow,
    StudentFinalAttendanceRow,
    StudentSessionRow,
)

USER_ID = UUID("20000000-0000-0000-0000-000000000011")
STUDENT_ID = UUID("23000000-0000-0000-0000-000000000001")
SESSION_ID = UUID("40000000-0000-0000-0000-000000000001")
ATTEMPT_ID = UUID("50000000-0000-0000-0000-000000000001")
CURRENT_TIME = datetime(2026, 9, 21, 9, 5, tzinfo=UTC)


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


class FakeStudentProfileRepository:
    def __init__(self, profile: StudentProfileRecord | None) -> None:
        self.profile = profile

    async def find_by_user_id(self, connection, user_id):
        return self.profile


class FakeStateRepository:
    def __init__(
        self,
        *,
        session: StudentSessionRow | None,
        attempt: StudentAttemptRow | None = None,
        geofence_status: str | None = None,
        face_status: str | None = None,
        liveness_passed: bool | None = None,
        attendance_record: StudentFinalAttendanceRow | None = None,
    ) -> None:
        self.session = session
        self.attempt = attempt
        self.geofence_status = geofence_status
        self.face_status = face_status
        self.liveness_passed = liveness_passed
        self.attendance_record = attendance_record

    async def find_session_for_student(self, connection, session_id, student_id):
        return self.session

    async def find_verification_attempt(self, connection, session_id, student_id):
        return self.attempt

    async def latest_geofence_status(self, connection, verification_attempt_id):
        return self.geofence_status

    async def latest_face_status(self, connection, verification_attempt_id):
        return self.face_status, self.liveness_passed

    async def find_attendance_record(self, connection, session_id, student_id):
        return self.attendance_record


def build_profile(*, status: str = "active") -> StudentProfileRecord:
    return StudentProfileRecord(
        id=STUDENT_ID,
        user_id=USER_ID,
        registration_number="230701A",
        first_name="Amal",
        middle_name=None,
        last_name="Perera",
        profile_status=status,
        university_email="230701a@student.uniattend.test",
    )


def build_session_row(**overrides) -> StudentSessionRow:
    values = dict(
        id=SESSION_ID,
        course_code="CS3203",
        course_name="Software Engineering Project",
        session_title="Week 7",
        session_type="lecture",
        status="active",
        closed_at=None,
        cancelled_at=None,
        scheduled_start_at=CURRENT_TIME - timedelta(minutes=5),
        scheduled_end_at=CURRENT_TIME + timedelta(hours=1),
        check_in_opens_at=CURRENT_TIME - timedelta(minutes=5),
        check_in_closes_at=CURRENT_TIME + timedelta(minutes=25),
        late_after_at=CURRENT_TIME + timedelta(minutes=15),
        requires_face_verification=True,
        requires_qr=False,
    )
    values.update(overrides)
    return StudentSessionRow(**values)


_DEFAULT_PROFILE = object()


def build_service(
    *,
    session: StudentSessionRow | None,
    profile: StudentProfileRecord | None | object = _DEFAULT_PROFILE,
    attempt: StudentAttemptRow | None = None,
    geofence_status: str | None = None,
    face_status: str | None = None,
    liveness_passed: bool | None = None,
    attendance_record: StudentFinalAttendanceRow | None = None,
) -> StudentAttendanceStateService:
    return StudentAttendanceStateService(
        repository=FakeStateRepository(
            session=session,
            attempt=attempt,
            geofence_status=geofence_status,
            face_status=face_status,
            liveness_passed=liveness_passed,
            attendance_record=attendance_record,
        ),
        student_profile_repository=FakeStudentProfileRepository(
            build_profile() if profile is _DEFAULT_PROFILE else profile,
        ),
        clock=lambda: CURRENT_TIME,
    )


async def test_rejects_a_missing_or_inactive_profile() -> None:
    service = build_service(session=build_session_row(), profile=None)

    with pytest.raises(StudentProfileNotFoundError):
        await service.get_for_user(FakePool(), USER_ID, SESSION_ID)


async def test_a_session_the_student_is_not_on_the_roster_of_is_not_found() -> None:
    service = build_service(session=None)

    with pytest.raises(SessionNotFoundError):
        await service.get_for_user(FakePool(), USER_ID, SESSION_ID)


async def test_a_student_with_no_attempt_yet_gets_an_empty_verification_state() -> None:
    service = build_service(session=build_session_row())

    state = await service.get_for_user(FakePool(), USER_ID, SESSION_ID)

    assert state.session_state is SessionState.ACTIVE
    assert state.can_start_check_in is True
    assert state.verification.attempt_status is None
    assert state.initial_check_in is None
    assert state.final_attendance is None


async def test_a_checked_in_student_carries_the_initial_check_in() -> None:
    checked_in_at = CURRENT_TIME - timedelta(minutes=1)
    service = build_service(
        session=build_session_row(),
        attempt=StudentAttemptRow(
            id=ATTEMPT_ID,
            status="checked_in",
            failure_reason=None,
            checked_in_at=checked_in_at,
            initial_check_in_status="checked_in",
        ),
        geofence_status="passed",
        face_status="passed",
        liveness_passed=True,
    )

    state = await service.get_for_user(FakePool(), USER_ID, SESSION_ID)

    assert state.initial_check_in is not None
    assert state.initial_check_in.checked_in_at == checked_in_at
    assert state.verification.geofence_status == "passed"
    assert state.verification.face_status == "passed"
    assert state.verification.liveness_passed is True
    assert state.can_start_check_in is False


async def test_a_final_attendance_record_is_reported() -> None:
    decided_at = CURRENT_TIME - timedelta(hours=2)
    service = build_service(
        session=build_session_row(closed_at=CURRENT_TIME - timedelta(hours=1)),
        attendance_record=StudentFinalAttendanceRow(
            attendance_status="present",
            record_source="automatic",
            updated_at=decided_at,
        ),
    )

    state = await service.get_for_user(FakePool(), USER_ID, SESSION_ID)

    assert state.session_state is SessionState.CLOSED
    assert state.final_attendance is not None
    assert state.final_attendance.status == "present"
    assert state.final_attendance.source == "automatic"
    assert state.final_attendance.decided_at == decided_at
    assert state.can_start_check_in is False


async def test_a_cancelled_session_is_reported_as_cancelled() -> None:
    service = build_service(
        session=build_session_row(cancelled_at=CURRENT_TIME - timedelta(minutes=1)),
    )

    state = await service.get_for_user(FakePool(), USER_ID, SESSION_ID)

    assert state.session_state is SessionState.CANCELLED
    assert state.can_start_check_in is False


async def test_qr_enabled_mirrors_requires_qr() -> None:
    service = build_service(session=build_session_row(requires_qr=True))

    state = await service.get_for_user(FakePool(), USER_ID, SESSION_ID)

    assert state.qr_enabled is True
