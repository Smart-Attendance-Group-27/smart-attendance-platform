from datetime import UTC, datetime
from uuid import UUID

import pytest

from modules.academic.lecturer_profile.exception import LecturerProfileNotFoundError
from modules.academic.lecturer_profile.repository import LecturerProfileRecord
from modules.attendance_verification.attendance_state import (
    AttendanceRecordSource,
    FinalAttendanceStatus,
)
from modules.attendance_verification.manual_attendance.exception import (
    ManualReasonInvalidError,
    SessionCancelledError,
    SessionNotFoundError,
    SessionNotStartedError,
    StudentNotOnRosterError,
)
from modules.attendance_verification.manual_attendance.repository import (
    ExistingAttendanceRecord,
    SessionForManualAttendance,
)
from modules.attendance_verification.manual_attendance.service import ManualAttendanceService

USER_ID = UUID("20000000-0000-0000-0000-000000000002")
LECTURER_ID = UUID("22000000-0000-0000-0000-000000000001")
SESSION_ID = UUID("40000000-0000-0000-0000-000000000001")
STUDENT_ID = UUID("23000000-0000-0000-0000-000000000001")
NOW = datetime(2026, 9, 21, 10, 0, tzinfo=UTC)


class FakeTransaction:
    def __init__(self, connection: "FakeConnection") -> None:
        self.connection = connection

    async def __aenter__(self) -> None:
        self.connection.transactions_opened += 1

    async def __aexit__(self, exc_type: object, exc: object, traceback: object) -> bool:
        return False


class FakeConnection:
    def __init__(self) -> None:
        self.transactions_opened = 0
        self.executed: list[tuple[str, tuple]] = []

    def transaction(self) -> FakeTransaction:
        return FakeTransaction(self)

    async def execute(self, query: str, *args) -> None:
        self.executed.append((query, args))


class FakeAcquire:
    def __init__(self, connection: FakeConnection) -> None:
        self.connection = connection

    async def __aenter__(self) -> FakeConnection:
        return self.connection

    async def __aexit__(self, exc_type: object, exc: object, traceback: object) -> bool:
        return False


class FakePool:
    def __init__(self) -> None:
        self.connection = FakeConnection()

    def acquire(self) -> FakeAcquire:
        return FakeAcquire(self.connection)


class FakeLecturerProfileRepository:
    def __init__(self, profile: LecturerProfileRecord | None) -> None:
        self.profile = profile
        self.lookups = 0

    async def find_by_user_id(self, connection, user_id: UUID):
        self.lookups += 1
        return self.profile


class FakeManualAttendanceRepository:
    def __init__(
        self,
        *,
        session: SessionForManualAttendance | None,
        on_roster: bool = True,
        existing: ExistingAttendanceRecord | None = None,
    ) -> None:
        self.session = session
        self.on_roster = on_roster
        self.existing = existing
        self.written: list[dict] = []

    async def find_session_for_lecturer(self, connection, session_id, lecturer_id):
        return self.session

    async def is_on_roster(self, connection, session_id, student_id):
        return self.on_roster

    async def find_existing_record(self, connection, session_id, student_id):
        return self.existing

    async def upsert_manual_record(self, connection, **kwargs):
        self.written.append(kwargs)
        return NOW


def build_profile(status: str = "active") -> LecturerProfileRecord:
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


def build_session(**overrides) -> SessionForManualAttendance:
    values = dict(id=SESSION_ID, activated_at=NOW, cancelled_at=None)
    values.update(overrides)
    return SessionForManualAttendance(**values)


def build_service(
    repository: FakeManualAttendanceRepository,
    profile: LecturerProfileRecord | None = None,
) -> ManualAttendanceService:
    return ManualAttendanceService(
        repository=repository,
        lecturer_profile_repository=FakeLecturerProfileRepository(
            profile if profile is not None else build_profile(),
        ),
    )


async def set_status(service: ManualAttendanceService, pool=None, **overrides):
    values = dict(
        lecturer_user_id=USER_ID,
        session_id=SESSION_ID,
        student_id=STUDENT_ID,
        status=FinalAttendanceStatus.LATE,
        reason="arrived after the bell",
    )
    values.update(overrides)
    return await service.set_status(pool or FakePool(), **values)


async def test_writes_a_manual_record_and_reports_it() -> None:
    repository = FakeManualAttendanceRepository(session=build_session())

    result = await set_status(build_service(repository))

    assert result.status is FinalAttendanceStatus.LATE
    assert result.source is AttendanceRecordSource.MANUAL
    assert result.reason == "arrived after the bell"
    assert result.recorded_by == USER_ID
    assert result.updated_at == NOW
    assert len(repository.written) == 1
    written = repository.written[0]
    assert written["session_id"] == SESSION_ID
    assert written["student_id"] == STUDENT_ID
    assert written["recorded_by"] == USER_ID
    assert written["attendance_status"] == "late"
    assert written["manual_reason"] == "arrived after the bell"


async def test_the_reason_is_trimmed_before_it_is_stored() -> None:
    repository = FakeManualAttendanceRepository(session=build_session())

    result = await set_status(build_service(repository), reason="   in the lab   ")

    assert result.reason == "in the lab"
    assert repository.written[0]["manual_reason"] == "in the lab"


async def test_writes_one_audit_row_naming_the_session_and_student() -> None:
    pool = FakePool()
    repository = FakeManualAttendanceRepository(session=build_session())

    await set_status(build_service(repository), pool)

    assert len(pool.connection.executed) == 1
    query, args = pool.connection.executed[0]
    assert "audit.audit_logs" in query
    assert USER_ID in args
    assert "attendance.manual_set" in args
    assert SESSION_ID in args


async def test_audit_remembers_the_record_that_was_replaced() -> None:
    pool = FakePool()
    repository = FakeManualAttendanceRepository(
        session=build_session(),
        existing=ExistingAttendanceRecord(attendance_status="absent", record_source="automatic"),
    )

    await set_status(build_service(repository), pool)

    _, args = pool.connection.executed[0]
    serialized = " ".join(str(arg) for arg in args)
    assert "absent" in serialized
    assert "automatic" in serialized


async def test_a_lecturer_can_overwrite_an_automatic_record() -> None:
    repository = FakeManualAttendanceRepository(
        session=build_session(),
        existing=ExistingAttendanceRecord(attendance_status="absent", record_source="automatic"),
    )

    result = await set_status(build_service(repository), status=FinalAttendanceStatus.PRESENT)

    assert result.status is FinalAttendanceStatus.PRESENT
    assert repository.written[0]["attendance_status"] == "present"


async def test_a_session_the_lecturer_does_not_teach_is_not_found() -> None:
    repository = FakeManualAttendanceRepository(session=None)

    with pytest.raises(SessionNotFoundError):
        await set_status(build_service(repository))

    assert repository.written == []


async def test_a_cancelled_session_refuses_the_write() -> None:
    repository = FakeManualAttendanceRepository(session=build_session(cancelled_at=NOW))

    with pytest.raises(SessionCancelledError):
        await set_status(build_service(repository))

    assert repository.written == []


async def test_a_cancelled_session_is_reported_as_cancelled_even_if_never_started() -> None:
    repository = FakeManualAttendanceRepository(
        session=build_session(activated_at=None, cancelled_at=NOW),
    )

    with pytest.raises(SessionCancelledError):
        await set_status(build_service(repository))


async def test_a_session_that_has_not_started_refuses_the_write() -> None:
    repository = FakeManualAttendanceRepository(session=build_session(activated_at=None))

    with pytest.raises(SessionNotStartedError):
        await set_status(build_service(repository))

    assert repository.written == []


async def test_a_student_not_on_the_roster_is_refused() -> None:
    repository = FakeManualAttendanceRepository(session=build_session(), on_roster=False)

    with pytest.raises(StudentNotOnRosterError):
        await set_status(build_service(repository))

    assert repository.written == []


@pytest.mark.parametrize("reason", ["", "  ", "ab", "  a  ", "x" * 501])
async def test_a_reason_outside_three_to_five_hundred_characters_is_refused(reason: str) -> None:
    repository = FakeManualAttendanceRepository(session=build_session())
    profiles = FakeLecturerProfileRepository(build_profile())
    service = ManualAttendanceService(repository=repository, lecturer_profile_repository=profiles)

    with pytest.raises(ManualReasonInvalidError):
        await set_status(service, reason=reason)

    assert repository.written == []
    # Refused before any lookup: no point touching the database for bad input.
    assert profiles.lookups == 0


@pytest.mark.parametrize("length", [3, 500])
async def test_the_reason_length_limits_are_inclusive(length: int) -> None:
    repository = FakeManualAttendanceRepository(session=build_session())

    result = await set_status(build_service(repository), reason="y" * length)

    assert len(result.reason) == length


async def test_a_missing_lecturer_profile_is_refused() -> None:
    service = ManualAttendanceService(
        repository=FakeManualAttendanceRepository(session=build_session()),
        lecturer_profile_repository=FakeLecturerProfileRepository(None),
    )

    with pytest.raises(LecturerProfileNotFoundError):
        await set_status(service)


async def test_an_inactive_lecturer_profile_is_refused() -> None:
    service = build_service(
        FakeManualAttendanceRepository(session=build_session()),
        profile=build_profile(status="archived"),
    )

    with pytest.raises(LecturerProfileNotFoundError):
        await set_status(service)


async def test_set_status_opens_its_own_transaction() -> None:
    pool = FakePool()

    await set_status(build_service(FakeManualAttendanceRepository(session=build_session())), pool)

    assert pool.connection.transactions_opened == 1


async def test_set_status_in_transaction_uses_the_callers_transaction() -> None:
    connection = FakeConnection()
    service = build_service(FakeManualAttendanceRepository(session=build_session()))

    await service.set_status_in_transaction(
        connection,
        lecturer_user_id=USER_ID,
        session_id=SESSION_ID,
        student_id=STUDENT_ID,
        status=FinalAttendanceStatus.ABSENT,
        reason="not in the room",
    )

    assert connection.transactions_opened == 0
    assert len(connection.executed) == 1
