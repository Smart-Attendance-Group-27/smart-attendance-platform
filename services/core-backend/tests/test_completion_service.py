from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from modules.attendance_verification.completion.exception import (
    ActiveStudentProfileNotFoundError,
    AttendanceSessionNotFoundError,
    AttendanceSessionNotOpenError,
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
    defaults = dict(
        id=ATTEMPT_ID,
        status="in_progress",
        started_at=CURRENT_TIME,
        checked_in_at=None,
    )
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
        self.checked_in_attempt_id: UUID | None = None
        self.checked_in_at: datetime | None = None
        self.qr_status_lookups = 0

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
        self.qr_status_lookups += 1
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

    async def mark_verification_attempt_checked_in(
        self, connection, verification_attempt_id, checked_in_at
    ):
        self.checked_in_attempt_id = verification_attempt_id
        self.checked_in_at = checked_in_at


async def test_checks_in_when_all_required_checks_passed() -> None:
    repository = FakeRepository()
    service = CompletionService(repository=repository)

    result = await service.complete_for_user(FakePool(), USER_ID, SESSION_ID)

    assert result.status is CompletionStatus.CHECKED_IN
    assert result.missing_requirements == []
    assert result.checked_in_at is not None
    assert repository.checked_in_attempt_id == ATTEMPT_ID
    assert repository.checked_in_at == result.checked_in_at


async def test_check_in_never_writes_a_final_attendance_record() -> None:
    """attendance_records is the FINAL result and belongs to finalization.

    Check-in must not pre-empt it, even for a student who is comfortably on
    time and has passed every required check.
    """
    repository = FakeRepository()
    service = CompletionService(repository=repository)

    result = await service.complete_for_user(FakePool(), USER_ID, SESSION_ID)

    assert result.status is CompletionStatus.CHECKED_IN
    assert result.attendance_status is None
    assert repository.inserted_attendance is None
    assert repository.completed_attempt_id is None


async def test_check_in_does_not_decide_late_even_past_the_late_threshold() -> None:
    """Late is a final-attendance concept, decided at finalization.

    A student who checks in after late_after_at is still CHECKED_IN here;
    only their checked_in_at timestamp records when it happened.
    """
    repository = FakeRepository(
        session=build_session(late_after_at=CURRENT_TIME - timedelta(minutes=1)),
    )
    service = CompletionService(repository=repository)

    result = await service.complete_for_user(FakePool(), USER_ID, SESSION_ID)

    assert result.status is CompletionStatus.CHECKED_IN
    assert result.attendance_status is None
    assert repository.inserted_attendance is None


async def test_reports_incomplete_when_a_required_check_has_not_passed() -> None:
    repository = FakeRepository(face_status="pending")
    service = CompletionService(repository=repository)

    result = await service.complete_for_user(FakePool(), USER_ID, SESSION_ID)

    assert result.status is CompletionStatus.INCOMPLETE
    assert result.missing_requirements == ["face_verification"]
    assert result.checked_in_at is None
    assert repository.checked_in_attempt_id is None
    assert repository.inserted_attendance is None


async def test_reports_incomplete_when_geofence_has_not_passed() -> None:
    repository = FakeRepository(geofence_status="failed")
    service = CompletionService(repository=repository)

    result = await service.complete_for_user(FakePool(), USER_ID, SESSION_ID)

    assert result.status is CompletionStatus.INCOMPLETE
    assert result.missing_requirements == ["geofence"]
    assert repository.checked_in_attempt_id is None


async def test_qr_is_never_required_for_initial_check_in() -> None:
    """QR windows are opened by the lecturer DURING the lecture.

    Requiring one to check in would make check-in impossible to complete,
    so requires_qr must not gate this step even when it is set.
    """
    repository = FakeRepository(session=build_session(requires_qr=True), qr_status=None)
    service = CompletionService(repository=repository)

    result = await service.complete_for_user(FakePool(), USER_ID, SESSION_ID)

    assert result.status is CompletionStatus.CHECKED_IN
    assert result.missing_requirements == []
    assert repository.checked_in_attempt_id == ATTEMPT_ID


async def test_check_in_does_not_read_qr_evidence_at_all() -> None:
    repository = FakeRepository(session=build_session(requires_qr=True), qr_status=None)
    service = CompletionService(repository=repository)

    await service.complete_for_user(FakePool(), USER_ID, SESSION_ID)

    assert repository.qr_status_lookups == 0


async def test_checks_in_when_session_does_not_require_qr() -> None:
    repository = FakeRepository(session=build_session(requires_qr=False), qr_status=None)
    service = CompletionService(repository=repository)

    result = await service.complete_for_user(FakePool(), USER_ID, SESSION_ID)

    assert result.status is CompletionStatus.CHECKED_IN


async def test_reports_failed_for_a_terminally_failed_attempt() -> None:
    repository = FakeRepository(attempt=build_attempt(status="failed"))
    service = CompletionService(repository=repository)

    result = await service.complete_for_user(FakePool(), USER_ID, SESSION_ID)

    assert result.status is CompletionStatus.FAILED
    assert repository.inserted_attendance is None


async def test_is_idempotent_for_an_already_checked_in_attempt() -> None:
    """Repeating the call must not move checked_in_at.

    QR applicability is anchored to that timestamp, so re-stamping it would
    silently change which QR windows a student is judged against.
    """
    original_checked_in_at = CURRENT_TIME - timedelta(minutes=5)
    repository = FakeRepository(
        attempt=build_attempt(status="checked_in", checked_in_at=original_checked_in_at),
    )
    service = CompletionService(repository=repository)

    result = await service.complete_for_user(FakePool(), USER_ID, SESSION_ID)

    assert result.status is CompletionStatus.CHECKED_IN
    assert result.checked_in_at == original_checked_in_at
    assert result.attendance_status is None
    assert repository.checked_in_attempt_id is None
    assert repository.inserted_attendance is None


async def test_reports_the_final_result_for_an_already_finalized_attempt() -> None:
    repository = FakeRepository(
        attempt=build_attempt(status="completed", checked_in_at=CURRENT_TIME),
        existing_attendance_status="present",
    )
    service = CompletionService(repository=repository)

    result = await service.complete_for_user(FakePool(), USER_ID, SESSION_ID)

    assert result.status is CompletionStatus.COMPLETED
    assert result.attendance_status == "present"
    assert repository.inserted_attendance is None
    assert repository.checked_in_attempt_id is None


async def test_rejects_a_closed_session() -> None:
    repository = FakeRepository(session=build_session(closed_at=CURRENT_TIME))
    service = CompletionService(repository=repository)

    with pytest.raises(AttendanceSessionNotOpenError):
        await service.complete_for_user(FakePool(), USER_ID, SESSION_ID)

    assert repository.checked_in_attempt_id is None


async def test_rejects_a_cancelled_session() -> None:
    repository = FakeRepository(session=build_session(cancelled_at=CURRENT_TIME))
    service = CompletionService(repository=repository)

    with pytest.raises(AttendanceSessionNotOpenError):
        await service.complete_for_user(FakePool(), USER_ID, SESSION_ID)


async def test_rejects_a_session_that_is_not_active() -> None:
    repository = FakeRepository(session=build_session(status="scheduled"))
    service = CompletionService(repository=repository)

    with pytest.raises(AttendanceSessionNotOpenError):
        await service.complete_for_user(FakePool(), USER_ID, SESSION_ID)


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
