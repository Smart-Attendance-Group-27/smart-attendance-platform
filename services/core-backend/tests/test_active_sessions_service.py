from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import pytest

from modules.academic.student_profile.exception import StudentProfileNotFoundError
from modules.academic.student_profile.repository import StudentProfileRecord
from modules.attendance_sessions.active_sessions.repository import (
    ActiveAttendanceSessionRecord,
    ActiveAttendanceSessionRepository,
)
from modules.attendance_sessions.active_sessions.service import (
    ActiveAttendanceSessionService,
)

USER_ID = UUID("20000000-0000-0000-0000-000000000011")
STUDENT_ID = UUID("23000000-0000-0000-0000-000000000001")
SESSION_ID = UUID("40000000-0000-0000-0000-000000000001")
CURRENT_TIME = datetime(2026, 8, 13, 5, 30, tzinfo=UTC)


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
        self.requested_user_id: UUID | None = None

    async def find_by_user_id(
        self,
        connection: object,
        user_id: UUID,
    ) -> StudentProfileRecord | None:
        self.requested_user_id = user_id
        return self.profile


class FakeActiveSessionRepository:
    def __init__(self, sessions: list[ActiveAttendanceSessionRecord]) -> None:
        self.sessions = sessions
        self.request: tuple[UUID, datetime] | None = None

    async def list_open_geofence_sessions_for_student(
        self,
        connection: object,
        student_id: UUID,
        current_time: datetime,
    ) -> list[ActiveAttendanceSessionRecord]:
        self.request = (student_id, current_time)
        return self.sessions


class FakeDatabaseConnection:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows
        self.query = ""
        self.args: tuple[Any, ...] = ()

    async def fetch(self, query: str, *args: Any) -> list[dict[str, Any]]:
        self.query = query
        self.args = args
        return self.rows


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


def build_session() -> ActiveAttendanceSessionRecord:
    return ActiveAttendanceSessionRecord(
        id=SESSION_ID,
        course_code="CS3203",
        course_name="Software Engineering Project",
        lecturer_names="Indika Perera",
        session_title="Geofence Demo - Near Centre",
        session_type="lecture",
        scheduled_start_at=CURRENT_TIME - timedelta(minutes=5),
        scheduled_end_at=CURRENT_TIME + timedelta(hours=1),
        check_in_opens_at=CURRENT_TIME - timedelta(minutes=2),
        check_in_closes_at=CURRENT_TIME + timedelta(minutes=30),
        late_after_at=CURRENT_TIME + timedelta(minutes=15),
        venue="LH-02",
        requires_face_verification=True,
        requires_geofence=True,
        requires_qr=False,
    )


async def test_lists_sessions_for_the_profile_derived_from_user() -> None:
    profile_repository = FakeStudentProfileRepository(build_profile())
    session_repository = FakeActiveSessionRepository([build_session()])
    service = ActiveAttendanceSessionService(
        repository=session_repository,
        student_profile_repository=profile_repository,
        clock=lambda: CURRENT_TIME,
    )

    sessions = await service.list_for_user(FakePool(), USER_ID)

    assert sessions == [build_session()]
    assert profile_repository.requested_user_id == USER_ID
    assert session_repository.request == (STUDENT_ID, CURRENT_TIME)


async def test_returns_an_empty_list_when_no_session_is_open() -> None:
    service = ActiveAttendanceSessionService(
        repository=FakeActiveSessionRepository([]),
        student_profile_repository=FakeStudentProfileRepository(build_profile()),
        clock=lambda: CURRENT_TIME,
    )

    assert await service.list_for_user(FakePool(), USER_ID) == []


@pytest.mark.parametrize("profile", [None, build_profile(status="archived")])
async def test_rejects_missing_or_inactive_student_profile(
    profile: StudentProfileRecord | None,
) -> None:
    session_repository = FakeActiveSessionRepository([build_session()])
    service = ActiveAttendanceSessionService(
        repository=session_repository,
        student_profile_repository=FakeStudentProfileRepository(profile),
        clock=lambda: CURRENT_TIME,
    )

    with pytest.raises(StudentProfileNotFoundError):
        await service.list_for_user(FakePool(), USER_ID)

    assert session_repository.request is None


async def test_rejects_naive_clock() -> None:
    service = ActiveAttendanceSessionService(
        repository=FakeActiveSessionRepository([]),
        student_profile_repository=FakeStudentProfileRepository(build_profile()),
        clock=lambda: CURRENT_TIME.replace(tzinfo=None),
    )

    with pytest.raises(ValueError, match="clock must include a timezone"):
        await service.list_for_user(FakePool(), USER_ID)


async def test_repository_maps_rows_and_enforces_discovery_filters() -> None:
    session = build_session()
    connection = FakeDatabaseConnection(
        [
            {
                "id": session.id,
                "course_code": session.course_code,
                "course_name": session.course_name,
                "lecturer_names": session.lecturer_names,
                "session_title": session.session_title,
                "session_type": session.session_type,
                "scheduled_start_at": session.scheduled_start_at,
                "scheduled_end_at": session.scheduled_end_at,
                "check_in_opens_at": session.check_in_opens_at,
                "check_in_closes_at": session.check_in_closes_at,
                "late_after_at": session.late_after_at,
                "venue": session.venue,
                "requires_face_verification": True,
                "requires_geofence": True,
                "requires_qr": False,
            }
        ],
    )

    records = (
        await ActiveAttendanceSessionRepository().list_open_geofence_sessions_for_student(
            connection,
            STUDENT_ID,
            CURRENT_TIME,
        )
    )

    assert records == [session]
    assert connection.args == (STUDENT_ID, CURRENT_TIME)
    assert "attendance_session.session_students" in connection.query
    assert "eligible_student.student_id = $1" in connection.query
    assert "session.status = 'active'" in connection.query
    assert "session.requires_geofence IS TRUE" in connection.query
    assert "session.check_in_opens_at <= $2" in connection.query
    assert "session.check_in_closes_at > $2" in connection.query
    assert "ORDER BY session.scheduled_start_at ASC, session.id ASC" in connection.query
    assert "centre_latitude" not in connection.query
    assert "centre_longitude" not in connection.query
