"""Closing overdue sessions without a lecturer.

The service method and the scheduler are tested against fakes. The point is
that an automatic close goes through exactly the same finalization as a
lecturer's close, that it only ever happens once, and that the audit trail
says the system did it.
"""

import json
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fakes import FakeQrEvidenceProvider
from modules.academic.lecturer_profile.repository import LecturerProfileRecord
from modules.attendance_sessions.lecturer_sessions.auto_close import (
    MAX_SESSIONS_PER_SCAN,
    SessionAutoCloseScheduler,
)
from modules.attendance_sessions.lecturer_sessions.repository import (
    AutoCloseCandidate,
    LecturerSessionRecord,
)
from modules.attendance_sessions.lecturer_sessions.service import LecturerSessionService
from modules.attendance_verification.attendance_state import (
    FinalAttendanceStatus,
    InitialCheckInStatus,
)
from modules.attendance_verification.finalization.repository import RosterStudentState

ACTOR_ID = UUID("20000000-0000-0000-0000-000000000002")
LECTURER_ID = UUID("22000000-0000-0000-0000-000000000001")
SESSION_ID = UUID("40000000-0000-0000-0000-000000000001")
OTHER_SESSION_ID = UUID("40000000-0000-0000-0000-000000000002")
NOW = datetime(2026, 9, 30, 11, 0, tzinfo=UTC)
GRACE = timedelta(minutes=15)

ATTEMPT_ALL_QR = UUID("50000000-0000-0000-0000-000000000001")
ATTEMPT_SOME_QR = UUID("50000000-0000-0000-0000-000000000002")
ATTEMPT_NO_QR = UUID("50000000-0000-0000-0000-000000000003")
STUDENT_ALL_QR = UUID("23000000-0000-0000-0000-000000000001")
STUDENT_SOME_QR = UUID("23000000-0000-0000-0000-000000000002")
STUDENT_NO_QR = UUID("23000000-0000-0000-0000-000000000003")
STUDENT_ABSENT = UUID("23000000-0000-0000-0000-000000000004")


class FakeTransaction:
    async def __aenter__(self):
        return None

    async def __aexit__(self, *exc):
        return False


class FakeConnection:
    def __init__(self) -> None:
        self.executed: list[tuple[str, tuple]] = []

    def transaction(self) -> FakeTransaction:
        return FakeTransaction()

    async def execute(self, query: str, *args) -> None:
        self.executed.append((query, args))

    def audit_rows(self) -> list[tuple]:
        return [args for query, args in self.executed if "audit.audit_logs" in query]


class FakeAcquire:
    def __init__(self, connection: FakeConnection) -> None:
        self.connection = connection

    async def __aenter__(self) -> FakeConnection:
        return self.connection

    async def __aexit__(self, *exc):
        return False


class FakePool:
    def __init__(self) -> None:
        self.connection = FakeConnection()

    def acquire(self) -> FakeAcquire:
        return FakeAcquire(self.connection)


def build_record(*, closed_at: datetime | None = None) -> LecturerSessionRecord:
    return LecturerSessionRecord(
        id=SESSION_ID, course_offering_id=UUID(int=1), course_code="CS3053",
        course_name="Security", classroom_code="LH-01",
        scheduled_start_at=NOW - timedelta(hours=2), scheduled_end_at=NOW - timedelta(minutes=30),
        check_in_opens_at=None, check_in_closes_at=None, late_after_at=None,
        activated_at=NOW - timedelta(hours=2), closed_at=closed_at, cancelled_at=None,
        requires_face_verification=True, requires_geofence=True, requires_qr=True,
        enrolled_count=4, present_count=0, late_count=0, pending_review_count=0,
    )


class FakeSessionRepository:
    """One session row that can be closed exactly once, like the real table."""

    def __init__(self, scheduled_end_at: datetime, *, closed: bool = False) -> None:
        self.scheduled_end_at = scheduled_end_at
        self.closed_at: datetime | None = NOW if closed else None
        self.close_calls: list[bool] = []

    async def lock_open_session_for_auto_close(self, connection, session_id):
        if self.closed_at is not None:
            return None
        return AutoCloseCandidate(id=session_id, scheduled_end_at=self.scheduled_end_at)

    async def find_for_lecturer(self, connection, session_id, lecturer_id, *, lock_for_update=False):
        return build_record(closed_at=self.closed_at)

    async def close(self, connection, session_id, *, automatically=False):
        self.close_calls.append(automatically)
        self.closed_at = NOW

    async def find_closed_at(self, connection, session_id):
        return self.closed_at


class FakeLecturerProfiles:
    async def find_by_user_id(self, connection, user_id):
        return LecturerProfileRecord(
            id=LECTURER_ID, user_id=ACTOR_ID, employee_number="E1", first_name="A",
            middle_name=None, last_name="B", profile_status="active",
            university_email="a@example.edu",
        )


class FakeQrSessionRepository:
    async def close_existing_active_qr_sessions(self, connection, session_id, deactivated_at):
        return []


class FakeCheckIn:
    async def reconcile_before_close(self, connection, session_id, closed_at, *, session=None):
        return []


class RecordingFinalizationRepository:
    def __init__(self) -> None:
        self.upserted: list = []

    async def lock_session_attempts(self, connection, session_id):
        return None

    async def fetch_roster_state(self, connection, session_id):
        def state(student_id, attempt_id, status):
            return RosterStudentState(
                student_id=student_id, verification_attempt_id=attempt_id,
                initial_check_in_status=status, has_manual_record=False,
            )

        checked_in = InitialCheckInStatus.CHECKED_IN.value
        return [
            state(STUDENT_ALL_QR, ATTEMPT_ALL_QR, checked_in),
            state(STUDENT_SOME_QR, ATTEMPT_SOME_QR, checked_in),
            state(STUDENT_NO_QR, ATTEMPT_NO_QR, checked_in),
            state(STUDENT_ABSENT, None, None),
        ]

    async def upsert_automatic_records(self, connection, session_id, results, decided_at):
        self.upserted.append({result.student_id: result.status for result in results})


def qr_evidence() -> FakeQrEvidenceProvider:
    evidence = FakeQrEvidenceProvider()
    evidence.set_progress(ATTEMPT_ALL_QR, required_count=2, passed_count=2)
    evidence.set_progress(ATTEMPT_SOME_QR, required_count=2, passed_count=1)
    evidence.set_progress(ATTEMPT_NO_QR, required_count=2, passed_count=0)
    return evidence


def build_service(repository: FakeSessionRepository, finalization: RecordingFinalizationRepository):
    return LecturerSessionService(
        repository=repository,
        lecturer_profile_repository=FakeLecturerProfiles(),
        qr_evidence=qr_evidence(),
        qr_session_repository=FakeQrSessionRepository(),
        check_in_service=FakeCheckIn(),
        finalization_repository=finalization,
        clock=lambda: NOW,
    )


EXPECTED_DECISIONS = {
    STUDENT_ALL_QR: FinalAttendanceStatus.PRESENT,
    STUDENT_SOME_QR: FinalAttendanceStatus.LEFT_EARLY,
    STUDENT_NO_QR: FinalAttendanceStatus.ABSENT,
    STUDENT_ABSENT: FinalAttendanceStatus.ABSENT,
}


async def test_an_overdue_active_session_is_closed_and_finalized() -> None:
    repository = FakeSessionRepository(NOW - timedelta(minutes=30))
    finalization = RecordingFinalizationRepository()
    pool = FakePool()

    closed = await build_service(repository, finalization).close_overdue_session(
        pool, SESSION_ID, grace=GRACE,
    )

    assert closed is True
    assert repository.close_calls == [True]
    assert finalization.upserted == [EXPECTED_DECISIONS]


async def test_the_automatic_close_is_audited_as_the_system() -> None:
    scheduled_end = NOW - timedelta(minutes=30)
    repository = FakeSessionRepository(scheduled_end)
    pool = FakePool()

    await build_service(repository, RecordingFinalizationRepository()).close_overdue_session(
        pool, SESSION_ID, grace=GRACE,
    )

    [audit] = pool.connection.audit_rows()
    actor_user_id, actor_type, action, entity_type, entity_id = audit[:5]
    new_values = json.loads(audit[8])
    assert (actor_user_id, actor_type, action) == (None, "system", "session.auto_close")
    assert (entity_type, entity_id) == ("attendance_session", SESSION_ID)
    assert new_values["scheduledEndAt"] == scheduled_end.isoformat()
    assert new_values["closedAt"] == NOW.isoformat()
    assert new_values["graceMinutes"] == 15
    assert new_values["reason"] == "Scheduled end plus grace period exceeded"
    assert new_values["finalization"]["leftEarly"] == 1


async def test_a_session_still_within_its_grace_period_stays_open() -> None:
    repository = FakeSessionRepository(NOW - timedelta(minutes=10))
    finalization = RecordingFinalizationRepository()
    pool = FakePool()

    closed = await build_service(repository, finalization).close_overdue_session(
        pool, SESSION_ID, grace=GRACE,
    )

    assert closed is False
    assert repository.close_calls == []
    assert finalization.upserted == []
    assert pool.connection.audit_rows() == []


async def test_an_already_closed_session_is_not_finalized_again() -> None:
    repository = FakeSessionRepository(NOW - timedelta(hours=1), closed=True)
    finalization = RecordingFinalizationRepository()
    pool = FakePool()

    closed = await build_service(repository, finalization).close_overdue_session(
        pool, SESSION_ID, grace=GRACE,
    )

    assert closed is False
    assert repository.close_calls == []
    assert finalization.upserted == []
    assert pool.connection.audit_rows() == []


async def test_closing_twice_finalizes_once() -> None:
    repository = FakeSessionRepository(NOW - timedelta(hours=1))
    finalization = RecordingFinalizationRepository()
    service = build_service(repository, finalization)

    first = await service.close_overdue_session(FakePool(), SESSION_ID, grace=GRACE)
    second = await service.close_overdue_session(FakePool(), SESSION_ID, grace=GRACE)

    assert (first, second) == (True, False)
    assert len(finalization.upserted) == 1


async def test_manual_and_automatic_close_decide_attendance_the_same_way() -> None:
    manual_finalization = RecordingFinalizationRepository()
    await build_service(
        FakeSessionRepository(NOW - timedelta(hours=1)), manual_finalization,
    ).close_for_user(FakePool(), ACTOR_ID, SESSION_ID)

    automatic_finalization = RecordingFinalizationRepository()
    await build_service(
        FakeSessionRepository(NOW - timedelta(hours=1)), automatic_finalization,
    ).close_overdue_session(FakePool(), SESSION_ID, grace=GRACE)

    assert manual_finalization.upserted == automatic_finalization.upserted == [EXPECTED_DECISIONS]


async def test_a_lecturers_close_is_audited_as_the_lecturer() -> None:
    pool = FakePool()
    repository = FakeSessionRepository(NOW - timedelta(hours=1))

    await build_service(repository, RecordingFinalizationRepository()).close_for_user(
        pool, ACTOR_ID, SESSION_ID,
    )

    [audit] = pool.connection.audit_rows()
    assert audit[:3] == (ACTOR_ID, "lecturer", "session.close")
    assert repository.close_calls == [False]


class FakeOverdueRepository:
    def __init__(self, session_ids: list[UUID]) -> None:
        self.session_ids = session_ids
        self.requests: list[tuple[datetime, int]] = []

    async def list_overdue_session_ids(self, connection, *, scheduled_end_before, limit):
        self.requests.append((scheduled_end_before, limit))
        return self.session_ids


class FakeClosingService:
    def __init__(self, failing: set[UUID] | None = None) -> None:
        self.failing = failing or set()
        self.calls: list[tuple[UUID, timedelta]] = []

    async def close_overdue_session(self, pool, session_id, *, grace, redis_client=None):
        self.calls.append((session_id, grace))
        if session_id in self.failing:
            raise RuntimeError("database hiccup")
        return True


def build_scheduler(repository, service) -> SessionAutoCloseScheduler:
    return SessionAutoCloseScheduler(
        pool=FakePool(),
        service=service,
        interval_seconds=60,
        grace_minutes=15,
        repository=repository,
        clock=lambda: NOW,
    )


async def test_the_scheduler_looks_for_sessions_past_their_end_plus_grace() -> None:
    repository = FakeOverdueRepository([SESSION_ID])
    service = FakeClosingService()

    closed = await build_scheduler(repository, service).run_once()

    assert closed == 1
    assert repository.requests == [(NOW - GRACE, MAX_SESSIONS_PER_SCAN)]
    assert service.calls == [(SESSION_ID, GRACE)]


async def test_a_session_missed_while_the_server_was_down_is_closed_on_the_next_scan() -> None:
    # Nothing is scheduled per session: every scan asks for everything overdue,
    # so a session that ended hours ago is found just like one that ended now.
    repository = FakeOverdueRepository([SESSION_ID, OTHER_SESSION_ID])
    service = FakeClosingService()

    closed = await build_scheduler(repository, service).run_once()

    assert closed == 2


async def test_one_failing_session_does_not_stop_the_others() -> None:
    repository = FakeOverdueRepository([SESSION_ID, OTHER_SESSION_ID])
    service = FakeClosingService(failing={SESSION_ID})

    closed = await build_scheduler(repository, service).run_once()

    assert closed == 1
    assert [session_id for session_id, _ in service.calls] == [SESSION_ID, OTHER_SESSION_ID]
