from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import pytest

from fakes import (
    FakeAttendancePolicyProvider,
    FakeQrEvidenceProvider,
    RecordingNotificationProducer,
)
from modules.academic.lecturer_profile.exception import LecturerProfileNotFoundError
from modules.academic.lecturer_profile.repository import LecturerProfileRecord
from modules.attendance_sessions.lecturer_sessions.exception import (
    ClassroomGeofenceNotConfiguredError,
    GeofenceRequiredError,
    InvalidCancellationReasonError,
    InvalidSessionScheduleError,
    SessionAlreadyActiveError,
    SessionAlreadyCancelledError,
    SessionAlreadyClosedError,
    SessionCancelledError,
    SessionNotActiveError,
    SessionNotFoundError,
    TimetableEntryNotFoundError,
)
from modules.attendance_sessions.lecturer_sessions.repository import (
    LecturerSessionRecord,
    TimetableEntryForSessionRecord,
)
from modules.attendance_sessions.lecturer_sessions.service import LecturerSessionService
from modules.contracts.attendance_policy import AttendancePolicy
from modules.attendance_verification.attendance_state import FinalAttendanceStatus, InitialCheckInStatus
from modules.attendance_verification.finalization.repository import RosterStudentState

ACTOR_ID = UUID("20000000-0000-0000-0000-000000000002")
LECTURER_ID = UUID("22000000-0000-0000-0000-000000000001")
SESSION_ID = UUID("40000000-0000-0000-0000-000000000001")
TIMETABLE_ENTRY_ID = UUID("3a000000-0000-0000-0000-000000000001")
COURSE_OFFERING_ID = UUID("30000000-0000-0000-0000-000000000001")
CLASSROOM_ID = UUID("10000000-0000-0000-0000-000000000001")
CURRENT_TIME = datetime(2026, 8, 13, 5, 30, tzinfo=UTC)


class FakeTransaction:
    async def __aenter__(self):
        return None

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class FakeConnection:
    def __init__(self) -> None:
        self.executed_queries: list[str] = []
        self.executed_args: list[tuple] = []

    def transaction(self) -> FakeTransaction:
        self.transactions_opened = getattr(self, "transactions_opened", 0) + 1
        return FakeTransaction()

    async def execute(self, query: str, *args) -> None:
        self.executed_queries.append(query)
        self.executed_args.append(args)


class FakeQrSessionRepository:
    """Stands in for Manushan's QrSessionRepository (I-11, frozen)."""

    def __init__(self, deactivated_batch_ids: list[UUID] | None = None) -> None:
        self.deactivated_batch_ids = deactivated_batch_ids or []
        self.calls: list[tuple[UUID, datetime]] = []

    async def close_existing_active_qr_sessions(self, connection, session_id, deactivated_at):
        self.calls.append((session_id, deactivated_at))
        return self.deactivated_batch_ids


class FakeAcquire:
    def __init__(self, connection: FakeConnection) -> None:
        self.connection = connection

    async def __aenter__(self) -> FakeConnection:
        return self.connection

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class FakePool:
    def __init__(self) -> None:
        self.connection = FakeConnection()

    def acquire(self) -> FakeAcquire:
        return FakeAcquire(self.connection)


class FakeLecturerProfileRepository:
    def __init__(self, profile: LecturerProfileRecord | None) -> None:
        self.profile = profile

    async def find_by_user_id(self, connection, user_id: UUID) -> LecturerProfileRecord | None:
        return self.profile


def build_profile() -> LecturerProfileRecord:
    return LecturerProfileRecord(
        id=LECTURER_ID,
        user_id=ACTOR_ID,
        employee_number="EMP001",
        first_name="Nadeesha",
        middle_name=None,
        last_name="Perera",
        profile_status="active",
        university_email="n.perera@staff.uniattend.test",
    )


def build_session(*, activated_at=None, closed_at=None, cancelled_at=None) -> LecturerSessionRecord:
    return LecturerSessionRecord(
        id=SESSION_ID,
        course_offering_id=UUID("30000000-0000-0000-0000-000000000001"),
        course_code="CS3203",
        course_name="Software Engineering Project",
        classroom_code="LH-02",
        scheduled_start_at=CURRENT_TIME,
        scheduled_end_at=CURRENT_TIME + timedelta(hours=1),
        check_in_opens_at=CURRENT_TIME - timedelta(minutes=5),
        check_in_closes_at=CURRENT_TIME + timedelta(minutes=30),
        late_after_at=CURRENT_TIME + timedelta(minutes=15),
        activated_at=activated_at,
        closed_at=closed_at,
        cancelled_at=cancelled_at,
        requires_face_verification=True,
        requires_geofence=True,
        requires_qr=False,
        enrolled_count=40,
        present_count=0,
        late_count=0,
        pending_review_count=0,
        checked_in_count=0,
        late_checked_in_count=0,
        failed_verification_count=0,
        absent_count=0,
        manual_count=0,
    )


def build_timetable_entry(**overrides) -> TimetableEntryForSessionRecord:
    defaults = dict(
        id=TIMETABLE_ENTRY_ID,
        course_offering_id=COURSE_OFFERING_ID,
        classroom_id=CLASSROOM_ID,
        classroom_latitude=Decimal("6.7961"),
        classroom_longitude=Decimal("79.9007"),
        classroom_default_geofence_radius_m=Decimal("40"),
    )
    defaults.update(overrides)
    return TimetableEntryForSessionRecord(**defaults)


class FakeLecturerSessionRepository:
    def __init__(
        self,
        before: LecturerSessionRecord,
        after: LecturerSessionRecord,
        *,
        timetable_entry: TimetableEntryForSessionRecord | None = None,
        enrolled_count: int = 3,
    ) -> None:
        self.before = before
        self.after = after
        self.timetable_entry = timetable_entry
        self.enrolled_count = enrolled_count
        self.calls: list[str] = []
        self.cancel_reason: str | None = None
        self.create_session_kwargs: dict | None = None
        self.create_session_geofence_kwargs: dict | None = None

    async def find_for_lecturer(self, connection, session_id, lecturer_id, *, lock_for_update=False):
        if self.calls and self.calls[-1] in ("activate", "close", "cancel", "create_session"):
            return self.after
        return self.before

    async def activate(self, connection, session_id) -> None:
        self.calls.append("activate")

    async def close(self, connection, session_id) -> None:
        self.calls.append("close")

    async def cancel(self, connection, session_id, reason) -> None:
        self.calls.append("cancel")
        self.cancel_reason = reason

    async def find_timetable_entry_for_lecturer(self, connection, timetable_entry_id, lecturer_id):
        self.calls.append("find_timetable_entry")
        return self.timetable_entry

    async def create_session(self, connection, **kwargs) -> None:
        self.calls.append("create_session")
        self.create_session_kwargs = kwargs

    async def create_session_students_from_enrolments(self, connection, session_id, course_offering_id) -> int:
        self.calls.append("create_session_students")
        return self.enrolled_count

    async def create_session_geofence(self, connection, session_id, **kwargs) -> None:
        self.calls.append("create_session_geofence")
        self.create_session_geofence_kwargs = kwargs


async def test_activate_writes_an_audit_log_entry() -> None:
    before = build_session()
    after = build_session(activated_at=CURRENT_TIME)
    repository = FakeLecturerSessionRepository(before, after)
    service = LecturerSessionService(
        repository=repository,
        lecturer_profile_repository=FakeLecturerProfileRepository(build_profile()),
    )
    pool = FakePool()

    await service.activate_for_user(pool, ACTOR_ID, SESSION_ID)

    audit_query, audit_args = pool.connection.executed_queries[0], pool.connection.executed_args[0]
    assert "audit.audit_logs" in audit_query
    assert audit_args[0] == ACTOR_ID
    assert audit_args[1] == "lecturer"
    assert audit_args[2] == "session.activate"
    assert audit_args[3] == "attendance_session"
    assert audit_args[4] == SESSION_ID


async def test_close_writes_an_audit_log_entry() -> None:
    before = build_session(activated_at=CURRENT_TIME)
    after = build_session(activated_at=CURRENT_TIME, closed_at=CURRENT_TIME)
    repository = FakeLecturerSessionRepository(before, after)
    qr_session_repository = FakeQrSessionRepository()
    service = LecturerSessionService(
        repository=repository,
        lecturer_profile_repository=FakeLecturerProfileRepository(build_profile()),
        qr_session_repository=qr_session_repository,
    )
    pool = FakePool()

    session, finalization = await service.close_for_user(pool, ACTOR_ID, SESSION_ID)

    assert session == after
    # No QrEvidenceProvider bound, so finalization stays inactive: no
    # attendance record is written and the summary is null, matching main
    # today plus the status change and QR shutdown.
    assert finalization is None
    assert qr_session_repository.calls == [(SESSION_ID, CURRENT_TIME)]

    audit_query, audit_args = pool.connection.executed_queries[-1], pool.connection.executed_args[-1]
    assert "audit.audit_logs" in audit_query
    assert audit_args[2] == "session.close"


async def test_activate_rejects_already_active_session_without_audit_log() -> None:
    already_active = build_session(activated_at=CURRENT_TIME)
    repository = FakeLecturerSessionRepository(already_active, already_active)
    service = LecturerSessionService(
        repository=repository,
        lecturer_profile_repository=FakeLecturerProfileRepository(build_profile()),
    )
    pool = FakePool()

    with pytest.raises(SessionAlreadyActiveError):
        await service.activate_for_user(pool, ACTOR_ID, SESSION_ID)

    assert pool.connection.executed_queries == []


async def test_activate_rejects_cancelled_session() -> None:
    cancelled = build_session(cancelled_at=CURRENT_TIME)
    repository = FakeLecturerSessionRepository(cancelled, cancelled)
    service = LecturerSessionService(
        repository=repository,
        lecturer_profile_repository=FakeLecturerProfileRepository(build_profile()),
    )

    with pytest.raises(SessionCancelledError):
        await service.activate_for_user(FakePool(), ACTOR_ID, SESSION_ID)


async def test_activate_rejects_closed_session() -> None:
    closed = build_session(activated_at=CURRENT_TIME, closed_at=CURRENT_TIME)
    repository = FakeLecturerSessionRepository(closed, closed)
    service = LecturerSessionService(
        repository=repository,
        lecturer_profile_repository=FakeLecturerProfileRepository(build_profile()),
    )

    with pytest.raises(SessionAlreadyClosedError):
        await service.activate_for_user(FakePool(), ACTOR_ID, SESSION_ID)


async def test_close_rejects_session_not_active() -> None:
    scheduled = build_session()
    repository = FakeLecturerSessionRepository(scheduled, scheduled)
    service = LecturerSessionService(
        repository=repository,
        lecturer_profile_repository=FakeLecturerProfileRepository(build_profile()),
    )

    with pytest.raises(SessionNotActiveError):
        await service.close_for_user(FakePool(), ACTOR_ID, SESSION_ID)


async def test_rejects_missing_lecturer_profile() -> None:
    repository = FakeLecturerSessionRepository(build_session(), build_session())
    service = LecturerSessionService(
        repository=repository,
        lecturer_profile_repository=FakeLecturerProfileRepository(None),
    )

    with pytest.raises(LecturerProfileNotFoundError):
        await service.activate_for_user(FakePool(), ACTOR_ID, SESSION_ID)


def build_create_kwargs(**overrides) -> dict:
    defaults = dict(
        timetable_entry_id=TIMETABLE_ENTRY_ID,
        session_title="CS3203 Lecture",
        session_type="lecture",
        scheduled_start_at=CURRENT_TIME,
        scheduled_end_at=CURRENT_TIME + timedelta(hours=1),
        check_in_opens_at=None,
        check_in_closes_at=None,
        late_after_at=None,
        requires_face_verification=True,
        requires_geofence=True,
        requires_qr=False,
    )
    defaults.update(overrides)
    return defaults


async def test_create_writes_session_students_geofence_snapshot_and_audit_log() -> None:
    created = build_session(activated_at=None)
    repository = FakeLecturerSessionRepository(
        created,
        created,
        timetable_entry=build_timetable_entry(),
        enrolled_count=6,
    )
    service = LecturerSessionService(
        repository=repository,
        lecturer_profile_repository=FakeLecturerProfileRepository(build_profile()),
    )
    pool = FakePool()

    result = await service.create_for_user(pool, ACTOR_ID, **build_create_kwargs())

    assert result is created
    assert repository.calls == [
        "find_timetable_entry",
        "create_session",
        "create_session_students",
        "create_session_geofence",
    ]
    assert repository.create_session_kwargs["course_offering_id"] == COURSE_OFFERING_ID
    assert repository.create_session_kwargs["timetable_entry_id"] == TIMETABLE_ENTRY_ID
    assert repository.create_session_geofence_kwargs["centre_latitude"] == Decimal("6.7961")
    assert repository.create_session_geofence_kwargs["radius_m"] == Decimal("40")

    audit_query, audit_args = pool.connection.executed_queries[0], pool.connection.executed_args[0]
    assert "audit.audit_logs" in audit_query
    assert audit_args[2] == "session.create"
    assert audit_args[4] == repository.create_session_kwargs["session_id"]


async def test_create_defaults_check_in_window_and_late_after_from_schedule() -> None:
    created = build_session()
    repository = FakeLecturerSessionRepository(
        created, created, timetable_entry=build_timetable_entry()
    )
    service = LecturerSessionService(
        repository=repository,
        lecturer_profile_repository=FakeLecturerProfileRepository(build_profile()),
    )

    await service.create_for_user(FakePool(), ACTOR_ID, **build_create_kwargs())

    kwargs = repository.create_session_kwargs
    assert kwargs["check_in_opens_at"] == CURRENT_TIME
    assert kwargs["check_in_closes_at"] == CURRENT_TIME + timedelta(hours=1)
    assert kwargs["late_after_at"] == CURRENT_TIME + timedelta(minutes=10)


async def test_create_rejects_end_before_start() -> None:
    repository = FakeLecturerSessionRepository(
        build_session(), build_session(), timetable_entry=build_timetable_entry()
    )
    service = LecturerSessionService(
        repository=repository,
        lecturer_profile_repository=FakeLecturerProfileRepository(build_profile()),
    )

    with pytest.raises(InvalidSessionScheduleError):
        await service.create_for_user(
            FakePool(),
            ACTOR_ID,
            **build_create_kwargs(scheduled_end_at=CURRENT_TIME - timedelta(minutes=1)),
        )

    assert repository.calls == []


async def test_create_rejects_unowned_or_inactive_timetable_entry() -> None:
    repository = FakeLecturerSessionRepository(
        build_session(), build_session(), timetable_entry=None
    )
    service = LecturerSessionService(
        repository=repository,
        lecturer_profile_repository=FakeLecturerProfileRepository(build_profile()),
    )

    with pytest.raises(TimetableEntryNotFoundError):
        await service.create_for_user(FakePool(), ACTOR_ID, **build_create_kwargs())


async def test_create_rejects_when_geofence_required_but_classroom_unconfigured() -> None:
    unconfigured = build_timetable_entry(
        classroom_latitude=None,
        classroom_longitude=None,
        classroom_default_geofence_radius_m=None,
    )
    repository = FakeLecturerSessionRepository(
        build_session(), build_session(), timetable_entry=unconfigured
    )
    service = LecturerSessionService(
        repository=repository,
        lecturer_profile_repository=FakeLecturerProfileRepository(build_profile()),
    )

    with pytest.raises(ClassroomGeofenceNotConfiguredError):
        await service.create_for_user(
            FakePool(), ACTOR_ID, **build_create_kwargs(requires_geofence=True)
        )

    assert repository.calls == ["find_timetable_entry"]


async def test_create_rejects_a_session_that_does_not_require_geofence() -> None:
    repository = FakeLecturerSessionRepository(
        build_session(),
        build_session(),
        timetable_entry=build_timetable_entry(),
    )
    service = LecturerSessionService(
        repository=repository,
        lecturer_profile_repository=FakeLecturerProfileRepository(build_profile()),
    )
    pool = FakePool()

    with pytest.raises(GeofenceRequiredError):
        await service.create_for_user(pool, ACTOR_ID, **build_create_kwargs(requires_geofence=False))

    # Refused before any lookup or write.
    assert repository.calls == []
    assert pool.connection.executed_queries == []


async def test_create_rejects_missing_lecturer_profile() -> None:
    repository = FakeLecturerSessionRepository(
        build_session(), build_session(), timetable_entry=build_timetable_entry()
    )
    service = LecturerSessionService(
        repository=repository,
        lecturer_profile_repository=FakeLecturerProfileRepository(None),
    )

    with pytest.raises(LecturerProfileNotFoundError):
        await service.create_for_user(FakePool(), ACTOR_ID, **build_create_kwargs())


class FailingNotificationProducer(RecordingNotificationProducer):
    async def session_opened(self, connection, *, session_id):
        raise RuntimeError("notification store unavailable")

    async def attendance_finalized(self, connection, *, session_id, results):
        raise RuntimeError("notification store unavailable")


class FakeCheckInForClose:
    async def reconcile_before_close(self, connection, session_id, closed_at, *, session=None):
        return []


class FakeFinalizationRepository:
    def __init__(self, roster: list[RosterStudentState]) -> None:
        self.roster = roster

    async def lock_session_attempts(self, connection, session_id):
        return None

    async def fetch_roster_state(self, connection, session_id):
        return self.roster

    async def upsert_automatic_records(self, connection, session_id, results, decided_at):
        return None


STUDENT_ONE = UUID("23000000-0000-0000-0000-000000000001")
STUDENT_TWO = UUID("23000000-0000-0000-0000-000000000002")
STUDENT_ONE_USER = UUID("20000000-0000-0000-0000-000000000011")
STUDENT_TWO_USER = UUID("20000000-0000-0000-0000-000000000012")


def checked_in(student_id: UUID, user_id: UUID | None) -> RosterStudentState:
    return RosterStudentState(
        student_id=student_id,
        verification_attempt_id=None,
        initial_check_in_status=InitialCheckInStatus.CHECKED_IN.value,
        has_manual_record=False,
        student_user_id=user_id,
    )


def never_arrived(student_id: UUID, user_id: UUID | None) -> RosterStudentState:
    return RosterStudentState(
        student_id=student_id,
        verification_attempt_id=None,
        initial_check_in_status=None,
        has_manual_record=False,
        student_user_id=user_id,
    )


def build_closing_service(
    producer: RecordingNotificationProducer,
    roster: list[RosterStudentState] | None = None,
    *,
    with_qr_provider: bool = True,
) -> LecturerSessionService:
    before = build_session(activated_at=CURRENT_TIME)
    after = build_session(activated_at=CURRENT_TIME, closed_at=CURRENT_TIME)
    return LecturerSessionService(
        repository=FakeLecturerSessionRepository(before, after),
        lecturer_profile_repository=FakeLecturerProfileRepository(build_profile()),
        qr_evidence=FakeQrEvidenceProvider() if with_qr_provider else None,
        qr_session_repository=FakeQrSessionRepository(),
        check_in_service=FakeCheckInForClose(),
        finalization_repository=FakeFinalizationRepository(roster or []),
        notification_producer=producer,
    )


async def test_activating_announces_that_the_session_opened() -> None:
    producer = RecordingNotificationProducer()
    before = build_session()
    after = build_session(activated_at=CURRENT_TIME)
    service = LecturerSessionService(
        repository=FakeLecturerSessionRepository(before, after),
        lecturer_profile_repository=FakeLecturerProfileRepository(build_profile()),
        notification_producer=producer,
    )

    await service.activate_for_user(FakePool(), ACTOR_ID, SESSION_ID)

    assert producer.kinds == ["session_opened"]
    assert producer.only_call_of("session_opened").payload == {"session_id": SESSION_ID}


async def test_a_refused_activation_announces_nothing() -> None:
    producer = RecordingNotificationProducer()
    already_active = build_session(activated_at=CURRENT_TIME)
    service = LecturerSessionService(
        repository=FakeLecturerSessionRepository(already_active, already_active),
        lecturer_profile_repository=FakeLecturerProfileRepository(build_profile()),
        notification_producer=producer,
    )

    with pytest.raises(SessionAlreadyActiveError):
        await service.activate_for_user(FakePool(), ACTOR_ID, SESSION_ID)

    assert producer.calls == []


async def test_the_announcement_runs_in_a_savepoint_inside_the_activation() -> None:
    producer = RecordingNotificationProducer()
    service = LecturerSessionService(
        repository=FakeLecturerSessionRepository(
            build_session(),
            build_session(activated_at=CURRENT_TIME),
        ),
        lecturer_profile_repository=FakeLecturerProfileRepository(build_profile()),
        notification_producer=producer,
    )
    pool = FakePool()

    await service.activate_for_user(pool, ACTOR_ID, SESSION_ID)

    # The activation's own transaction, plus the savepoint around the announcement.
    assert pool.connection.transactions_opened == 2


async def test_a_failing_producer_does_not_stop_a_session_from_activating() -> None:
    after = build_session(activated_at=CURRENT_TIME)
    service = LecturerSessionService(
        repository=FakeLecturerSessionRepository(build_session(), after),
        lecturer_profile_repository=FakeLecturerProfileRepository(build_profile()),
        notification_producer=FailingNotificationProducer(),
    )
    pool = FakePool()

    result = await service.activate_for_user(pool, ACTOR_ID, SESSION_ID)

    assert result == after
    assert "audit.audit_logs" in pool.connection.executed_queries[0]


async def test_closing_tells_each_student_their_final_attendance() -> None:
    producer = RecordingNotificationProducer()
    roster = [
        checked_in(STUDENT_ONE, STUDENT_ONE_USER),
        never_arrived(STUDENT_TWO, STUDENT_TWO_USER),
    ]
    service = build_closing_service(producer, roster)

    await service.close_for_user(FakePool(), ACTOR_ID, SESSION_ID)

    payload = producer.only_call_of("attendance_finalized").payload
    assert payload["session_id"] == SESSION_ID
    assert payload["results"] == [
        (STUDENT_ONE_USER, FinalAttendanceStatus.PRESENT),
        (STUDENT_TWO_USER, FinalAttendanceStatus.ABSENT),
    ]


async def test_a_student_with_no_account_to_notify_is_left_out() -> None:
    producer = RecordingNotificationProducer()
    roster = [checked_in(STUDENT_ONE, STUDENT_ONE_USER), checked_in(STUDENT_TWO, None)]
    service = build_closing_service(producer, roster)

    await service.close_for_user(FakePool(), ACTOR_ID, SESSION_ID)

    results = producer.only_call_of("attendance_finalized").payload["results"]
    assert results == [(STUDENT_ONE_USER, FinalAttendanceStatus.PRESENT)]


async def test_closing_without_finalization_announces_nothing() -> None:
    producer = RecordingNotificationProducer()
    service = build_closing_service(producer, with_qr_provider=False)

    _, summary = await service.close_for_user(FakePool(), ACTOR_ID, SESSION_ID)

    assert summary is None
    assert producer.calls == []


async def test_closing_an_empty_roster_announces_nothing() -> None:
    producer = RecordingNotificationProducer()
    service = build_closing_service(producer, [])

    await service.close_for_user(FakePool(), ACTOR_ID, SESSION_ID)

    assert producer.calls == []


async def test_a_failing_producer_does_not_stop_a_session_from_closing() -> None:
    roster = [checked_in(STUDENT_ONE, STUDENT_ONE_USER)]
    service = build_closing_service(FailingNotificationProducer(), roster)
    pool = FakePool()

    session, summary = await service.close_for_user(pool, ACTOR_ID, SESSION_ID)

    assert session.closed_at is not None
    assert summary is not None
    assert summary.present == 1
    assert "audit.audit_logs" in pool.connection.executed_queries[-1]
class RecordingRedis:
    def __init__(self) -> None:
        self.deleted_keys: list[str] = []

    async def delete(self, key: str) -> None:
        self.deleted_keys.append(key)


def build_cancel_service(
    before: LecturerSessionRecord | None,
    after: LecturerSessionRecord | None = None,
    *,
    deactivated_batch_ids: list[UUID] | None = None,
    profile: LecturerProfileRecord | None = None,
):
    repository = FakeLecturerSessionRepository(before, after or before)
    qr_session_repository = FakeQrSessionRepository(deactivated_batch_ids)
    service = LecturerSessionService(
        repository=repository,
        lecturer_profile_repository=FakeLecturerProfileRepository(profile or build_profile()),
        qr_session_repository=qr_session_repository,
    )
    return service, repository, qr_session_repository


async def test_cancel_marks_the_session_cancelled_with_its_reason() -> None:
    before = build_session(activated_at=CURRENT_TIME)
    after = build_session(activated_at=CURRENT_TIME, cancelled_at=CURRENT_TIME)
    service, repository, _ = build_cancel_service(before, after)

    result = await service.cancel_for_user(FakePool(), ACTOR_ID, SESSION_ID, "  room flooded  ")

    assert result == after
    assert repository.calls == ["cancel"]
    assert repository.cancel_reason == "room flooded"


async def test_a_session_that_never_started_can_be_cancelled() -> None:
    before = build_session()
    after = build_session(cancelled_at=CURRENT_TIME)
    service, repository, _ = build_cancel_service(before, after)

    await service.cancel_for_user(FakePool(), ACTOR_ID, SESSION_ID, "lecturer unwell")

    assert repository.calls == ["cancel"]


async def test_cancel_shuts_down_the_sessions_qr_batches() -> None:
    before = build_session(activated_at=CURRENT_TIME)
    after = build_session(activated_at=CURRENT_TIME, cancelled_at=CURRENT_TIME)
    service, _, qr_session_repository = build_cancel_service(before, after)

    await service.cancel_for_user(FakePool(), ACTOR_ID, SESSION_ID, "room flooded")

    assert qr_session_repository.calls == [(SESSION_ID, CURRENT_TIME)]


async def test_cancel_writes_one_audit_row_and_nothing_else() -> None:
    before = build_session(activated_at=CURRENT_TIME)
    after = build_session(activated_at=CURRENT_TIME, cancelled_at=CURRENT_TIME)
    service, _, _ = build_cancel_service(before, after)
    pool = FakePool()

    await service.cancel_for_user(pool, ACTOR_ID, SESSION_ID, "room flooded")

    # The only statement run on the connection is the audit row: no attendance
    # record is written, because a cancelled session has nothing to decide.
    assert len(pool.connection.executed_queries) == 1
    assert "audit.audit_logs" in pool.connection.executed_queries[0]
    assert "attendance_records" not in pool.connection.executed_queries[0]
    args = pool.connection.executed_args[0]
    assert args[2] == "session.cancel"
    assert args[4] == SESSION_ID
    assert "room flooded" in " ".join(str(arg) for arg in args)


async def test_cancel_clears_the_cache_for_every_deactivated_batch_after_commit() -> None:
    batch_a = UUID("60000000-0000-0000-0000-000000000001")
    batch_b = UUID("60000000-0000-0000-0000-000000000002")
    before = build_session(activated_at=CURRENT_TIME)
    after = build_session(activated_at=CURRENT_TIME, cancelled_at=CURRENT_TIME)
    service, _, _ = build_cancel_service(before, after, deactivated_batch_ids=[batch_a, batch_b])
    redis_client = RecordingRedis()

    await service.cancel_for_user(FakePool(), ACTOR_ID, SESSION_ID, "room flooded", redis_client)

    assert redis_client.deleted_keys == [f"qr:batch:{batch_a}", f"qr:batch:{batch_b}"]


async def test_cancel_touches_no_cache_when_no_batch_was_active() -> None:
    before = build_session(activated_at=CURRENT_TIME)
    after = build_session(activated_at=CURRENT_TIME, cancelled_at=CURRENT_TIME)
    service, _, _ = build_cancel_service(before, after)
    redis_client = RecordingRedis()

    await service.cancel_for_user(FakePool(), ACTOR_ID, SESSION_ID, "room flooded", redis_client)

    assert redis_client.deleted_keys == []


async def test_cancel_works_with_no_cache_available() -> None:
    batch = UUID("60000000-0000-0000-0000-000000000001")
    before = build_session(activated_at=CURRENT_TIME)
    after = build_session(activated_at=CURRENT_TIME, cancelled_at=CURRENT_TIME)
    service, _, _ = build_cancel_service(before, after, deactivated_batch_ids=[batch])

    result = await service.cancel_for_user(FakePool(), ACTOR_ID, SESSION_ID, "room flooded", None)

    assert result == after


async def test_an_already_cancelled_session_is_refused_without_writing() -> None:
    cancelled = build_session(cancelled_at=CURRENT_TIME)
    service, repository, qr_session_repository = build_cancel_service(cancelled)
    pool = FakePool()
    redis_client = RecordingRedis()

    with pytest.raises(SessionAlreadyCancelledError):
        await service.cancel_for_user(pool, ACTOR_ID, SESSION_ID, "room flooded", redis_client)

    assert repository.calls == []
    assert qr_session_repository.calls == []
    assert pool.connection.executed_queries == []
    assert redis_client.deleted_keys == []


async def test_a_closed_session_cannot_be_cancelled() -> None:
    closed = build_session(activated_at=CURRENT_TIME, closed_at=CURRENT_TIME)
    service, repository, qr_session_repository = build_cancel_service(closed)

    with pytest.raises(SessionAlreadyClosedError):
        await service.cancel_for_user(FakePool(), ACTOR_ID, SESSION_ID, "room flooded")

    assert repository.calls == []
    assert qr_session_repository.calls == []


async def test_cancelling_a_session_the_lecturer_does_not_teach_is_not_found() -> None:
    service, repository, _ = build_cancel_service(None)

    with pytest.raises(SessionNotFoundError):
        await service.cancel_for_user(FakePool(), ACTOR_ID, SESSION_ID, "room flooded")

    assert repository.calls == []


async def test_cancel_rejects_a_missing_lecturer_profile() -> None:
    service = LecturerSessionService(
        repository=FakeLecturerSessionRepository(build_session(), build_session()),
        lecturer_profile_repository=FakeLecturerProfileRepository(None),
        qr_session_repository=FakeQrSessionRepository(),
    )

    with pytest.raises(LecturerProfileNotFoundError):
        await service.cancel_for_user(FakePool(), ACTOR_ID, SESSION_ID, "room flooded")


@pytest.mark.parametrize("reason", ["", "  ", "ab", "x" * 501])
async def test_a_reason_outside_three_to_five_hundred_characters_is_refused(reason: str) -> None:
    service, repository, _ = build_cancel_service(build_session(activated_at=CURRENT_TIME))
    pool = FakePool()

    with pytest.raises(InvalidCancellationReasonError):
        await service.cancel_for_user(pool, ACTOR_ID, SESSION_ID, reason)

    assert repository.calls == []
    assert pool.connection.executed_queries == []


def build_policy(window: int = 20, threshold: int = 5) -> AttendancePolicy:
    return AttendancePolicy(
        check_in_window_minutes=window,
        late_threshold_minutes=threshold,
        qr_default_validity_minutes=5,
    )


async def create_with_policy(
    policy: AttendancePolicy | None,
    **request_overrides,
) -> tuple[dict, FakeAttendancePolicyProvider]:
    provider = FakeAttendancePolicyProvider(policy)
    created = build_session()
    repository = FakeLecturerSessionRepository(
        created,
        created,
        timetable_entry=build_timetable_entry(),
    )
    service = LecturerSessionService(
        repository=repository,
        lecturer_profile_repository=FakeLecturerProfileRepository(build_profile()),
        attendance_policy=provider,
    )

    await service.create_for_user(FakePool(), ACTOR_ID, **build_create_kwargs(**request_overrides))

    return repository.create_session_kwargs, provider


async def test_a_policy_fills_in_the_window_and_the_late_threshold() -> None:
    kwargs, _ = await create_with_policy(build_policy(window=20, threshold=5))

    assert kwargs["check_in_opens_at"] == CURRENT_TIME
    assert kwargs["check_in_closes_at"] == CURRENT_TIME + timedelta(minutes=20)
    assert kwargs["late_after_at"] == CURRENT_TIME + timedelta(minutes=5)


async def test_a_window_longer_than_the_session_is_capped_at_its_end() -> None:
    kwargs, _ = await create_with_policy(build_policy(window=90, threshold=5))

    assert kwargs["check_in_closes_at"] == CURRENT_TIME + timedelta(hours=1)


async def test_a_late_threshold_longer_than_the_window_is_capped_at_the_close() -> None:
    kwargs, _ = await create_with_policy(build_policy(window=20, threshold=30))

    assert kwargs["check_in_closes_at"] == CURRENT_TIME + timedelta(minutes=20)
    assert kwargs["late_after_at"] == CURRENT_TIME + timedelta(minutes=20)


async def test_an_explicit_close_wins_and_the_threshold_is_measured_against_it() -> None:
    explicit_close = CURRENT_TIME + timedelta(minutes=8)

    kwargs, _ = await create_with_policy(
        build_policy(window=20, threshold=30),
        check_in_closes_at=explicit_close,
    )

    assert kwargs["check_in_closes_at"] == explicit_close
    assert kwargs["late_after_at"] == explicit_close


async def test_an_explicit_late_time_wins() -> None:
    explicit_late = CURRENT_TIME + timedelta(minutes=12)

    kwargs, _ = await create_with_policy(
        build_policy(window=20, threshold=5),
        late_after_at=explicit_late,
    )

    assert kwargs["late_after_at"] == explicit_late
    assert kwargs["check_in_closes_at"] == CURRENT_TIME + timedelta(minutes=20)


async def test_an_explicit_opening_time_is_what_the_window_counts_from() -> None:
    explicit_open = CURRENT_TIME - timedelta(minutes=10)

    kwargs, _ = await create_with_policy(
        build_policy(window=20, threshold=5),
        check_in_opens_at=explicit_open,
    )

    assert kwargs["check_in_opens_at"] == explicit_open
    assert kwargs["check_in_closes_at"] == CURRENT_TIME + timedelta(minutes=10)
    # the late threshold still counts from the scheduled start
    assert kwargs["late_after_at"] == CURRENT_TIME + timedelta(minutes=5)


async def test_the_policy_is_not_read_when_the_request_already_says_everything() -> None:
    kwargs, provider = await create_with_policy(
        build_policy(),
        check_in_closes_at=CURRENT_TIME + timedelta(minutes=30),
        late_after_at=CURRENT_TIME + timedelta(minutes=10),
    )

    assert provider.read_count == 0
    assert kwargs["check_in_closes_at"] == CURRENT_TIME + timedelta(minutes=30)


async def test_the_policy_is_read_once() -> None:
    _, provider = await create_with_policy(build_policy())

    assert provider.read_count == 1


async def test_with_no_policy_the_built_in_defaults_are_kept() -> None:
    kwargs, provider = await create_with_policy(None)

    assert provider.read_count == 1
    assert kwargs["check_in_closes_at"] == CURRENT_TIME + timedelta(hours=1)
    assert kwargs["late_after_at"] == CURRENT_TIME + timedelta(minutes=10)


async def test_a_policy_that_produces_an_impossible_window_is_refused_before_anything_is_written() -> None:
    created = build_session()
    repository = FakeLecturerSessionRepository(
        created,
        created,
        timetable_entry=build_timetable_entry(),
    )
    service = LecturerSessionService(
        repository=repository,
        lecturer_profile_repository=FakeLecturerProfileRepository(build_profile()),
        attendance_policy=FakeAttendancePolicyProvider(build_policy(window=0, threshold=0)),
    )
    pool = FakePool()

    with pytest.raises(InvalidSessionScheduleError):
        await service.create_for_user(pool, ACTOR_ID, **build_create_kwargs())

    assert repository.calls == []
    assert pool.connection.executed_queries == []
