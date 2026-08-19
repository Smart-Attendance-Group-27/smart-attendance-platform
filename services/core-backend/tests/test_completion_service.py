from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from modules.attendance_verification.completion.exception import (
    ActiveStudentProfileNotFoundError,
    AttendanceSessionNotFoundError,
    VerificationNotStartedError,
)
from modules.attendance_verification.completion.repository import (
    AttendanceSessionRecord,
    StudentProfileRecord,
    VerificationAttemptRecord,
)
from modules.attendance_verification.completion.service import (
    CompletionService,
    CompletionStatus,
)

USER_ID = UUID("20000000-0000-0000-0000-000000000011")
STUDENT_ID = UUID("23000000-0000-0000-0000-000000000001")
SESSION_ID = UUID("40000000-0000-0000-0000-000000000001")
ATTEMPT_ID = UUID("50000000-0000-0000-0000-000000000001")
CURRENT_TIME = datetime(2026, 8, 13, 5, 30, tzinfo=UTC)


class FakeTransaction:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, exc_type: object, exc: object, traceback: object) -> bool:
        return False


class FakeConnection:
    def transaction(self) -> FakeTransaction:
        return FakeTransaction()


class FakeAcquire:
    def __init__(self, connection: FakeConnection) -> None:
        self._connection = connection

    async def __aenter__(self) -> FakeConnection:
        return self._connection

    async def __aexit__(self, exc_type: object, exc: object, traceback: object) -> bool:
        return False


class FakePool:
    def __init__(self) -> None:
        self.connection = FakeConnection()

    def acquire(self) -> FakeAcquire:
        return FakeAcquire(self.connection)


def build_student(**overrides) -> StudentProfileRecord:
    defaults = dict(id=STUDENT_ID, profile_status="active")
    defaults.update(overrides)
    return StudentProfileRecord(**defaults)


def build_session(**overrides) -> AttendanceSessionRecord:
    defaults = dict(
        id=SESSION_ID,
        status="active",
        closed_at=None,
        cancelled_at=None,
        late_after_at=CURRENT_TIME + timedelta(minutes=15),
        requires_geofence=True,
        requires_face_verification=True,
        requires_qr=False,
    )
    defaults.update(overrides)
    return AttendanceSessionRecord(**defaults)


def build_attempt(**overrides) -> VerificationAttemptRecord:
    defaults = dict(id=ATTEMPT_ID, status="in_progress", started_at=CURRENT_TIME)
    defaults.update(overrides)
    return VerificationAttemptRecord(**defaults)


_MISSING = object()


class FakeRepository:
    def __init__(
        self,
        *,
        student: StudentProfileRecord | None | object = _MISSING,
        session: AttendanceSessionRecord | None | object = _MISSING,
        attempt: VerificationAttemptRecord | None | object = _MISSING,
        geofence_status: str | None = "passed",
        face_status: str | None = "passed",
        qr_status: str | None = "accepted",
        existing_attendance_status: str | None = None,
    ) -> None:
        self.student = build_student() if student is _MISSING else student
        self.session = build_session() if session is _MISSING else session
        self.attempt = build_attempt() if attempt is _MISSING else attempt
        self.geofence_status = geofence_status
        self.face_status = face_status
        self.qr_status = qr_status
        self.existing_attendance_status = existing_attendance_status
        self.inserted_attendance: dict | None = None
        self.completed_attempt_id: UUID | None = None

    async def lock_student_profile_for_user(self, connection, user_id):
        return self.student

    async def lock_attendance_session(self, connection, session_id):
        return self.session

    async def lock_verification_attempt(self, connection, session_id, student_id):
        return self.attempt

    async def latest_geofence_status(self, connection, verification_attempt_id):
        return self.geofence_status

    async def latest_face_status(self, connection, verification_attempt_id):
        return self.face_status

    async def latest_qr_status(self, connection, verification_attempt_id):
        return self.qr_status

    async def find_attendance_status(self, connection, session_id, student_id):
        return self.existing_attendance_status

    async def insert_attendance_record(self, connection, *, record_id, session_id, student_id, attendance_status):
        self.inserted_attendance = {
            "session_id": session_id,
            "student_id": student_id,
            "attendance_status": attendance_status,
        }

    async def complete_verification_attempt(self, connection, verification_attempt_id, completed_at):
        self.completed_attempt_id = verification_attempt_id


async def test_completes_and_marks_present_when_all_required_checks_passed() -> None:
    repository = FakeRepository()
    service = CompletionService(repository=repository)

    result = await service.complete_for_user(FakePool(), USER_ID, SESSION_ID)

    assert result.status is CompletionStatus.COMPLETED
    assert result.attendance_status == "present"
    assert result.missing_requirements == []
    assert repository.inserted_attendance == {
        "session_id": SESSION_ID,
        "student_id": STUDENT_ID,
        "attendance_status": "present",
    }
    assert repository.completed_attempt_id == ATTEMPT_ID


async def test_marks_late_when_started_after_late_threshold() -> None:
    repository = FakeRepository(
        session=build_session(late_after_at=CURRENT_TIME - timedelta(minutes=1)),
    )
    service = CompletionService(repository=repository)

    result = await service.complete_for_user(FakePool(), USER_ID, SESSION_ID)

    assert result.attendance_status == "late"
    assert repository.inserted_attendance["attendance_status"] == "late"


async def test_reports_incomplete_when_a_required_check_has_not_passed() -> None:
    repository = FakeRepository(face_status="pending")
    service = CompletionService(repository=repository)

    result = await service.complete_for_user(FakePool(), USER_ID, SESSION_ID)

    assert result.status is CompletionStatus.INCOMPLETE
    assert result.missing_requirements == ["face_verification"]
    assert repository.inserted_attendance is None
    assert repository.completed_attempt_id is None


async def test_skips_qr_check_when_session_does_not_require_it() -> None:
    repository = FakeRepository(session=build_session(requires_qr=False), qr_status=None)
    service = CompletionService(repository=repository)

    result = await service.complete_for_user(FakePool(), USER_ID, SESSION_ID)

    assert result.status is CompletionStatus.COMPLETED


async def test_reports_missing_qr_when_session_requires_it() -> None:
    repository = FakeRepository(session=build_session(requires_qr=True), qr_status=None)
    service = CompletionService(repository=repository)

    result = await service.complete_for_user(FakePool(), USER_ID, SESSION_ID)

    assert result.status is CompletionStatus.INCOMPLETE
    assert result.missing_requirements == ["qr"]


async def test_reports_failed_for_a_terminally_failed_attempt() -> None:
    repository = FakeRepository(attempt=build_attempt(status="failed"))
    service = CompletionService(repository=repository)

    result = await service.complete_for_user(FakePool(), USER_ID, SESSION_ID)

    assert result.status is CompletionStatus.FAILED
    assert repository.inserted_attendance is None


async def test_is_idempotent_for_an_already_completed_attempt() -> None:
    repository = FakeRepository(
        attempt=build_attempt(status="completed"),
        existing_attendance_status="present",
    )
    service = CompletionService(repository=repository)

    result = await service.complete_for_user(FakePool(), USER_ID, SESSION_ID)

    assert result.status is CompletionStatus.COMPLETED
    assert result.attendance_status == "present"
    assert repository.inserted_attendance is None
    assert repository.completed_attempt_id is None


async def test_rejects_missing_student_profile() -> None:
    repository = FakeRepository(student=None)
    service = CompletionService(repository=repository)

    with pytest.raises(ActiveStudentProfileNotFoundError):
        await service.complete_for_user(FakePool(), USER_ID, SESSION_ID)


async def test_rejects_missing_session() -> None:
    repository = FakeRepository(session=None)
    service = CompletionService(repository=repository)

    with pytest.raises(AttendanceSessionNotFoundError):
        await service.complete_for_user(FakePool(), USER_ID, SESSION_ID)


async def test_rejects_when_no_verification_attempt_exists() -> None:
    repository = FakeRepository(attempt=None)
    service = CompletionService(repository=repository)

    with pytest.raises(VerificationNotStartedError):
        await service.complete_for_user(FakePool(), USER_ID, SESSION_ID)
