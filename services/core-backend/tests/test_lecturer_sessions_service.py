from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import pytest

from modules.academic.lecturer_profile.exception import LecturerProfileNotFoundError
from modules.academic.lecturer_profile.repository import LecturerProfileRecord
from modules.attendance_sessions.lecturer_sessions.exception import (
    ClassroomGeofenceNotConfiguredError,
    InvalidSessionScheduleError,
    SessionAlreadyActiveError,
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
        return FakeTransaction()

    async def execute(self, query: str, *args) -> None:
        self.executed_queries.append(query)
        self.executed_args.append(args)


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
        self.create_session_kwargs: dict | None = None
        self.create_session_geofence_kwargs: dict | None = None

    async def find_for_lecturer(self, connection, session_id, lecturer_id, *, lock_for_update=False):
        if self.calls and self.calls[-1] in ("activate", "close", "create_session"):
            return self.after
        return self.before

    async def activate(self, connection, session_id) -> None:
        self.calls.append("activate")

    async def close(self, connection, session_id) -> None:
        self.calls.append("close")

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
    service = LecturerSessionService(
        repository=repository,
        lecturer_profile_repository=FakeLecturerProfileRepository(build_profile()),
    )
    pool = FakePool()

    await service.close_for_user(pool, ACTOR_ID, SESSION_ID)

    audit_query, audit_args = pool.connection.executed_queries[0], pool.connection.executed_args[0]
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


async def test_create_allows_unconfigured_classroom_when_geofence_not_required() -> None:
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

    await service.create_for_user(
        FakePool(), ACTOR_ID, **build_create_kwargs(requires_geofence=False)
    )

    assert "create_session_geofence" not in repository.calls


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
