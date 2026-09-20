"""CheckInService against a fake repository.

The fake honours the ``not_after`` bound for real, because the whole point of
that bound is the race between a student finishing verification and a lecturer
closing the session — a fake that ignored it would make those tests decorative.
"""

import inspect
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from modules.attendance_verification.attendance_state import (
    InitialCheckInStatus,
    VerificationAttemptStatus,
)
from modules.attendance_verification.check_in.domain import CheckInOutcome, RequiredStep
from modules.attendance_verification.check_in.exception import (
    ActiveStudentProfileNotFoundError,
    AttendanceSessionNotFoundError,
    VerificationNotStartedError,
)
from modules.attendance_verification.check_in.repository import (
    AttemptEvidenceRecord,
    AttendanceSessionRecord,
    CheckInRepository,
    StudentProfileRecord,
    VerificationAttemptRecord,
)
from modules.attendance_verification.check_in.service import CheckInService

USER_ID = UUID("20000000-0000-0000-0000-000000000011")
STUDENT_ID = UUID("23000000-0000-0000-0000-000000000001")
SESSION_ID = UUID("40000000-0000-0000-0000-000000000001")
ATTEMPT_ID = UUID("50000000-0000-0000-0000-000000000001")

LECTURE_START = datetime(2026, 9, 21, 9, 0, tzinfo=UTC)
LATE_AFTER = LECTURE_START + timedelta(minutes=15)


class FakeTransaction:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> bool:
        return False


class FakeConnection:
    def transaction(self) -> FakeTransaction:
        return FakeTransaction()


class FakeAcquire:
    def __init__(self, connection: FakeConnection) -> None:
        self._connection = connection

    async def __aenter__(self) -> FakeConnection:
        return self._connection

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> bool:
        return False


class FakePool:
    def __init__(self) -> None:
        self.connection = FakeConnection()

    def acquire(self) -> FakeAcquire:
        return FakeAcquire(self.connection)


class PersistedCheckIn:
    def __init__(self, attempt_id: UUID, checked_in_at: datetime, status: str) -> None:
        self.attempt_id = attempt_id
        self.checked_in_at = checked_in_at
        self.status = status


_DEFAULT_STUDENT = object()


class FakeCheckInRepository:
    def __init__(
        self,
        *,
        student: StudentProfileRecord | None | object = _DEFAULT_STUDENT,
        session: AttendanceSessionRecord | None = None,
        attempt: VerificationAttemptRecord | None = None,
        geofence_passes: tuple[datetime, ...] = (),
        face_passes: tuple[datetime, ...] = (),
        session_attempts: tuple[AttemptEvidenceRecord, ...] = (),
    ) -> None:
        self.student = build_student() if student is _DEFAULT_STUDENT else student
        self.session = session
        self.attempt = attempt
        self.geofence_passes = geofence_passes
        self.face_passes = face_passes
        self.session_attempts = session_attempts
        self.persisted: list[PersistedCheckIn] = []
        self.evidence_bounds: list[datetime | None] = []

    async def lock_student_profile_for_user(self, connection, user_id):
        return self.student

    async def lock_attendance_session(self, connection, session_id):
        return self.session

    async def lock_verification_attempt(self, connection, session_id, student_id):
        return self.attempt

    async def geofence_passed_at(self, connection, attempt_id, *, not_after=None):
        self.evidence_bounds.append(not_after)
        return _earliest(self.geofence_passes, not_after)

    async def face_passed_at(self, connection, attempt_id, *, not_after=None):
        self.evidence_bounds.append(not_after)
        return _earliest(self.face_passes, not_after)

    async def persist_check_in(
        self,
        connection,
        attempt_id,
        *,
        checked_in_at,
        initial_check_in_status,
    ):
        self.persisted.append(
            PersistedCheckIn(attempt_id, checked_in_at, initial_check_in_status.value),
        )

    async def list_attempts_with_evidence(
        self,
        connection,
        session_id,
        *,
        not_after=None,
        statuses=(VerificationAttemptStatus.IN_PROGRESS.value,),
    ):
        self.evidence_bounds.append(not_after)
        return [
            AttemptEvidenceRecord(
                attempt_id=record.attempt_id,
                student_id=record.student_id,
                status=record.status,
                started_at=record.started_at,
                geofence_passed_at=_bound(record.geofence_passed_at, not_after),
                face_passed_at=_bound(record.face_passed_at, not_after),
            )
            for record in self.session_attempts
        ]


def _earliest(moments: tuple[datetime, ...], not_after: datetime | None) -> datetime | None:
    eligible = [moment for moment in moments if not_after is None or moment <= not_after]
    return min(eligible) if eligible else None


def _bound(moment: datetime | None, not_after: datetime | None) -> datetime | None:
    if moment is None or (not_after is not None and moment > not_after):
        return None
    return moment


def build_student(**overrides) -> StudentProfileRecord:
    values = dict(id=STUDENT_ID, profile_status="active")
    values.update(overrides)
    return StudentProfileRecord(**values)


def build_session(**overrides) -> AttendanceSessionRecord:
    values = dict(
        id=SESSION_ID,
        status="active",
        closed_at=None,
        cancelled_at=None,
        late_after_at=LATE_AFTER,
        requires_geofence=True,
        requires_face_verification=False,
        requires_qr=False,
    )
    values.update(overrides)
    return AttendanceSessionRecord(**values)


def build_attempt(**overrides) -> VerificationAttemptRecord:
    values = dict(
        id=ATTEMPT_ID,
        status=VerificationAttemptStatus.IN_PROGRESS.value,
        started_at=LECTURE_START,
        checked_in_at=None,
        initial_check_in_status=None,
    )
    values.update(overrides)
    return VerificationAttemptRecord(**values)


def build_service(repository: FakeCheckInRepository) -> CheckInService:
    return CheckInService(repository=repository)


async def test_a_student_without_a_profile_is_rejected() -> None:
    repository = FakeCheckInRepository(student=None, session=build_session())

    with pytest.raises(ActiveStudentProfileNotFoundError):
        await build_service(repository).check_in_for_user(FakePool(), USER_ID, SESSION_ID)


async def test_an_inactive_profile_cannot_check_in() -> None:
    repository = FakeCheckInRepository(
        student=build_student(profile_status="suspended"),
        session=build_session(),
    )

    with pytest.raises(ActiveStudentProfileNotFoundError):
        await build_service(repository).check_in_for_user(FakePool(), USER_ID, SESSION_ID)


async def test_a_missing_session_is_rejected() -> None:
    repository = FakeCheckInRepository(session=None)

    with pytest.raises(AttendanceSessionNotFoundError):
        await build_service(repository).check_in_for_user(FakePool(), USER_ID, SESSION_ID)


async def test_checking_in_before_verifying_anything_is_a_conflict() -> None:
    repository = FakeCheckInRepository(session=build_session(), attempt=None)

    with pytest.raises(VerificationNotStartedError):
        await build_service(repository).check_in_for_user(FakePool(), USER_ID, SESSION_ID)


async def test_a_failed_attempt_reports_failure_and_writes_nothing() -> None:
    repository = FakeCheckInRepository(
        session=build_session(),
        attempt=build_attempt(status=VerificationAttemptStatus.FAILED.value),
    )

    result = await build_service(repository).check_in_for_user(FakePool(), USER_ID, SESSION_ID)

    assert result.outcome is CheckInOutcome.FAILED
    assert result.initial_check_in is None
    assert repository.persisted == []


async def test_passing_the_only_required_step_checks_the_student_in() -> None:
    passed_at = LECTURE_START + timedelta(minutes=3)
    repository = FakeCheckInRepository(
        session=build_session(),
        attempt=build_attempt(),
        geofence_passes=(passed_at,),
    )

    result = await build_service(repository).check_in_for_user(FakePool(), USER_ID, SESSION_ID)

    assert result.outcome is CheckInOutcome.CHECKED_IN
    assert result.was_persisted
    assert result.initial_check_in is not None
    assert result.initial_check_in.checked_in_at == passed_at
    assert result.initial_check_in.status is InitialCheckInStatus.CHECKED_IN
    assert [entry.checked_in_at for entry in repository.persisted] == [passed_at]


async def test_a_missing_face_step_leaves_the_student_pending() -> None:
    repository = FakeCheckInRepository(
        session=build_session(requires_face_verification=True),
        attempt=build_attempt(),
        geofence_passes=(LECTURE_START,),
    )

    result = await build_service(repository).check_in_for_user(FakePool(), USER_ID, SESSION_ID)

    assert result.outcome is CheckInOutcome.PENDING
    assert result.missing_steps == (RequiredStep.FACE,)
    assert repository.persisted == []


async def test_finishing_after_the_threshold_is_recorded_as_late() -> None:
    passed_at = LATE_AFTER + timedelta(minutes=4)
    repository = FakeCheckInRepository(
        session=build_session(),
        attempt=build_attempt(),
        geofence_passes=(passed_at,),
    )

    result = await build_service(repository).check_in_for_user(FakePool(), USER_ID, SESSION_ID)

    assert result.initial_check_in is not None
    assert result.initial_check_in.status is InitialCheckInStatus.LATE_CHECKED_IN
    assert repository.persisted[0].status == "late_checked_in"


async def test_checking_in_twice_does_not_move_the_recorded_time() -> None:
    already_checked_in_at = LECTURE_START + timedelta(minutes=1)
    repository = FakeCheckInRepository(
        session=build_session(),
        attempt=build_attempt(
            status=VerificationAttemptStatus.CHECKED_IN.value,
            checked_in_at=already_checked_in_at,
            initial_check_in_status=InitialCheckInStatus.CHECKED_IN.value,
        ),
        geofence_passes=(LECTURE_START + timedelta(minutes=30),),
    )

    result = await build_service(repository).check_in_for_user(FakePool(), USER_ID, SESSION_ID)

    assert result.outcome is CheckInOutcome.CHECKED_IN
    assert not result.was_persisted
    assert result.initial_check_in is not None
    assert result.initial_check_in.checked_in_at == already_checked_in_at
    assert repository.persisted == []


async def test_evidence_recorded_after_the_session_closed_does_not_check_anyone_in() -> None:
    closed_at = LECTURE_START + timedelta(hours=1)
    repository = FakeCheckInRepository(
        session=build_session(status="closed", closed_at=closed_at),
        attempt=build_attempt(),
        geofence_passes=(closed_at + timedelta(minutes=5),),
    )

    result = await build_service(repository).check_in_for_user(FakePool(), USER_ID, SESSION_ID)

    assert result.outcome is CheckInOutcome.PENDING
    assert repository.persisted == []


async def test_evidence_recorded_before_the_close_still_counts() -> None:
    closed_at = LECTURE_START + timedelta(hours=1)
    passed_at = closed_at - timedelta(minutes=5)
    repository = FakeCheckInRepository(
        session=build_session(status="closed", closed_at=closed_at),
        attempt=build_attempt(),
        geofence_passes=(passed_at,),
    )

    result = await build_service(repository).check_in_for_user(FakePool(), USER_ID, SESSION_ID)

    assert result.outcome is CheckInOutcome.CHECKED_IN
    assert result.initial_check_in is not None
    assert result.initial_check_in.checked_in_at == passed_at


async def test_try_check_in_reports_no_attempt_rather_than_raising() -> None:
    repository = FakeCheckInRepository(session=build_session(), attempt=None)

    result = await build_service(repository).try_check_in(
        FakeConnection(),
        session_id=SESSION_ID,
        student_id=STUDENT_ID,
    )

    assert result is None


async def test_reconciliation_checks_in_students_whose_evidence_beat_the_close() -> None:
    closed_at = LECTURE_START + timedelta(hours=1)
    in_time = UUID("50000000-0000-0000-0000-000000000002")
    too_late = UUID("50000000-0000-0000-0000-000000000003")
    never_arrived = UUID("50000000-0000-0000-0000-000000000004")
    repository = FakeCheckInRepository(
        session=build_session(status="closed", closed_at=closed_at),
        session_attempts=(
            AttemptEvidenceRecord(
                attempt_id=in_time,
                student_id=STUDENT_ID,
                status=VerificationAttemptStatus.IN_PROGRESS.value,
                started_at=LECTURE_START,
                geofence_passed_at=closed_at - timedelta(seconds=1),
                face_passed_at=None,
            ),
            AttemptEvidenceRecord(
                attempt_id=too_late,
                student_id=STUDENT_ID,
                status=VerificationAttemptStatus.IN_PROGRESS.value,
                started_at=LECTURE_START,
                geofence_passed_at=closed_at + timedelta(seconds=1),
                face_passed_at=None,
            ),
            AttemptEvidenceRecord(
                attempt_id=never_arrived,
                student_id=STUDENT_ID,
                status=VerificationAttemptStatus.IN_PROGRESS.value,
                started_at=LECTURE_START,
                geofence_passed_at=None,
                face_passed_at=None,
            ),
        ),
    )

    reconciled = await build_service(repository).reconcile_before_close(
        FakeConnection(),
        SESSION_ID,
        closed_at,
    )

    assert [entry.verification_attempt_id for entry in reconciled] == [in_time]
    assert [entry.attempt_id for entry in repository.persisted] == [in_time]


async def test_reconciliation_marks_a_last_second_check_in_late_when_it_was_late() -> None:
    closed_at = LATE_AFTER + timedelta(hours=1)
    attempt_id = UUID("50000000-0000-0000-0000-000000000005")
    repository = FakeCheckInRepository(
        session=build_session(status="closed", closed_at=closed_at),
        session_attempts=(
            AttemptEvidenceRecord(
                attempt_id=attempt_id,
                student_id=STUDENT_ID,
                status=VerificationAttemptStatus.IN_PROGRESS.value,
                started_at=LECTURE_START,
                geofence_passed_at=LATE_AFTER + timedelta(minutes=2),
                face_passed_at=None,
            ),
        ),
    )

    reconciled = await build_service(repository).reconcile_before_close(
        FakeConnection(),
        SESSION_ID,
        closed_at,
    )

    assert reconciled[0].initial_check_in.status is InitialCheckInStatus.LATE_CHECKED_IN


def test_the_check_in_repository_never_writes_an_attendance_record() -> None:
    """Check-in decides nothing about attendance; the session close does.

    Asserted against the source so that adding such a write later trips this
    test rather than silently resurrecting the bug this module was built to fix.
    """

    source = inspect.getsource(CheckInRepository)

    assert "INSERT INTO attendance_verification.attendance_records" not in source
    assert "UPDATE attendance_verification.attendance_records" not in source
