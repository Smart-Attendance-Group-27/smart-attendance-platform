from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from modules.attendance_verification.attendance_state import FinalAttendanceStatus
from modules.attendance_verification.finalization.repository import FinalizationRepository
from modules.attendance_verification.finalization.types import FinalizationResult

SESSION_ID = UUID("40000000-0000-0000-0000-000000000001")
STUDENT_ID = UUID("23000000-0000-0000-0000-000000000001")
STUDENT_USER_ID = UUID("20000000-0000-0000-0000-000000000011")
ATTEMPT_ID = UUID("50000000-0000-0000-0000-000000000001")
DECIDED_AT = datetime(2026, 9, 21, 10, 0, tzinfo=UTC)


class FakeConnection:
    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self.rows = rows or []
        self.fetch_calls: list[tuple[str, tuple]] = []
        self.execute_calls: list[tuple[str, tuple]] = []

    async def fetch(self, query: str, *args: Any) -> list[dict[str, Any]]:
        self.fetch_calls.append((query, args))
        return self.rows

    async def execute(self, query: str, *args: Any) -> None:
        self.execute_calls.append((query, args))


async def test_lock_session_attempts_locks_every_attempt_of_the_session() -> None:
    connection = FakeConnection()

    await FinalizationRepository().lock_session_attempts(connection, SESSION_ID)

    query, args = connection.execute_calls[0]
    assert "FOR UPDATE" in query
    assert "WHERE session_id = $1" in query
    assert args == (SESSION_ID,)


async def test_fetch_roster_state_maps_rows() -> None:
    connection = FakeConnection(
        rows=[
            {
                "student_id": STUDENT_ID,
                "student_user_id": STUDENT_USER_ID,
                "verification_attempt_id": ATTEMPT_ID,
                "initial_check_in_status": "checked_in",
                "has_manual_record": False,
            },
        ],
    )

    roster = await FinalizationRepository().fetch_roster_state(connection, SESSION_ID)

    assert len(roster) == 1
    assert roster[0].student_id == STUDENT_ID
    assert roster[0].student_user_id == STUDENT_USER_ID
    assert roster[0].verification_attempt_id == ATTEMPT_ID
    assert roster[0].initial_check_in_status == "checked_in"
    assert roster[0].has_manual_record is False

    query, args = connection.fetch_calls[0]
    assert "attendance_session.session_students" in query
    assert "JOIN academic.student_profiles" in query
    assert "student.user_id AS student_user_id" in query
    assert "LEFT JOIN attendance_verification.verification_attempts" in query
    assert "LEFT JOIN attendance_verification.attendance_records" in query
    assert args == (SESSION_ID,)


async def test_upsert_automatic_records_writes_nothing_for_an_empty_result_set() -> None:
    connection = FakeConnection()

    await FinalizationRepository().upsert_automatic_records(
        connection,
        SESSION_ID,
        [],
        DECIDED_AT,
    )

    assert connection.execute_calls == []


async def test_upsert_automatic_records_sends_one_statement_for_every_student() -> None:
    connection = FakeConnection()
    results = [
        FinalizationResult(student_id=STUDENT_ID, status=FinalAttendanceStatus.PRESENT),
        FinalizationResult(
            student_id=UUID("23000000-0000-0000-0000-000000000002"),
            status=FinalAttendanceStatus.ABSENT,
        ),
    ]

    await FinalizationRepository().upsert_automatic_records(
        connection,
        SESSION_ID,
        results,
        DECIDED_AT,
    )

    assert len(connection.execute_calls) == 1
    query, args = connection.execute_calls[0]
    assert "ON CONFLICT (session_id, student_id) DO UPDATE" in query
    assert "WHERE attendance_records.record_source = $5" in query
    session_id, record_ids, student_ids, statuses, source, decided_at = args
    assert session_id == SESSION_ID
    assert len(record_ids) == 2
    assert len(set(record_ids)) == 2  # every automatic record gets its own id
    assert student_ids == [STUDENT_ID, UUID("23000000-0000-0000-0000-000000000002")]
    assert statuses == ["present", "absent"]
    assert source == "automatic"
    assert decided_at == DECIDED_AT
