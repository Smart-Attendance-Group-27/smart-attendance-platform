from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from modules.attendance_verification.manual_attendance.repository import (
    ManualAttendanceRepository,
)

SESSION_ID = UUID("40000000-0000-0000-0000-000000000001")
STUDENT_ID = UUID("23000000-0000-0000-0000-000000000001")
LECTURER_ID = UUID("22000000-0000-0000-0000-000000000001")
USER_ID = UUID("20000000-0000-0000-0000-000000000002")
RECORD_ID = UUID("60000000-0000-0000-0000-000000000001")
NOW = datetime(2026, 9, 21, 10, 0, tzinfo=UTC)


class FakeConnection:
    def __init__(self, *, row: dict[str, Any] | None = None, value: Any = None) -> None:
        self.row = row
        self.value = value
        self.calls: list[tuple[str, str, tuple]] = []

    async def fetchrow(self, query: str, *args: Any):
        self.calls.append(("fetchrow", query, args))
        return self.row

    async def fetchval(self, query: str, *args: Any):
        self.calls.append(("fetchval", query, args))
        return self.value


async def test_session_lookup_checks_ownership_and_takes_a_shared_lock() -> None:
    connection = FakeConnection(row={"id": SESSION_ID, "activated_at": NOW, "cancelled_at": None})

    session = await ManualAttendanceRepository().find_session_for_lecturer(
        connection,
        SESSION_ID,
        LECTURER_ID,
    )

    assert session is not None
    assert session.id == SESSION_ID
    assert session.activated_at == NOW
    _, query, args = connection.calls[0]
    assert "academic.course_lecturers" in query
    assert "assignment.lecturer_id = $2" in query
    # A close or cancel takes FOR UPDATE, so it waits for this write.
    assert "FOR SHARE OF session" in query
    assert args == (SESSION_ID, LECTURER_ID)


async def test_session_lookup_returns_none_for_a_session_the_lecturer_does_not_teach() -> None:
    connection = FakeConnection(row=None)

    session = await ManualAttendanceRepository().find_session_for_lecturer(
        connection,
        SESSION_ID,
        LECTURER_ID,
    )

    assert session is None


async def test_roster_check_reads_the_session_students_table() -> None:
    connection = FakeConnection(value=True)

    on_roster = await ManualAttendanceRepository().is_on_roster(connection, SESSION_ID, STUDENT_ID)

    assert on_roster is True
    _, query, args = connection.calls[0]
    assert "attendance_session.session_students" in query
    assert args == (SESSION_ID, STUDENT_ID)


async def test_existing_record_is_locked_so_the_audit_old_value_is_accurate() -> None:
    connection = FakeConnection(row={"attendance_status": "absent", "record_source": "automatic"})

    existing = await ManualAttendanceRepository().find_existing_record(
        connection,
        SESSION_ID,
        STUDENT_ID,
    )

    assert existing is not None
    assert existing.attendance_status == "absent"
    assert existing.record_source == "automatic"
    assert "FOR UPDATE" in connection.calls[0][1]


async def test_the_upsert_overwrites_whatever_is_there_and_marks_it_manual() -> None:
    connection = FakeConnection(value=NOW)

    updated_at = await ManualAttendanceRepository().upsert_manual_record(
        connection,
        record_id=RECORD_ID,
        session_id=SESSION_ID,
        student_id=STUDENT_ID,
        recorded_by=USER_ID,
        attendance_status="late",
        manual_reason="arrived after the bell",
    )

    assert updated_at == NOW
    _, query, args = connection.calls[0]
    assert "ON CONFLICT (session_id, student_id) DO UPDATE" in query
    assert "RETURNING updated_at" in query
    # Unlike finalization there is deliberately no WHERE guard here: a
    # lecturer's decision replaces an automatic record, or an earlier manual one.
    assert " WHERE attendance_records" not in query
    assert args == (
        RECORD_ID,
        SESSION_ID,
        STUDENT_ID,
        USER_ID,
        "late",
        "manual",
        "arrived after the bell",
    )
