"""SQL shape of the session override repository.

These tests do not run the SQL (see the lifecycle database integration test
for that); they pin the parts of each statement the waiver's guarantees rest
on, so a later edit cannot quietly drop one.
"""

from datetime import UTC, datetime
from uuid import UUID

from modules.attendance_verification.check_in.domain import RequiredStep
from modules.attendance_verification.session_overrides.domain import (
    REOPENABLE_GEOFENCE_FAILURES,
    GeofenceWaiverReason,
)
from modules.attendance_verification.session_overrides.repository import SessionOverrideRepository

SESSION_ID = UUID("40000000-0000-0000-0000-000000000001")
LECTURER_ID = UUID("22000000-0000-0000-0000-000000000001")
USER_ID = UUID("20000000-0000-0000-0000-000000000002")
NOW = datetime(2026, 9, 30, 9, 17, tzinfo=UTC)


class RecordingConnection:
    def __init__(self, *, fetch=None, fetchrow=None, fetchval=None) -> None:
        self.fetch_result = fetch or []
        self.fetchrow_result = fetchrow
        self.fetchval_result = fetchval
        self.query = ""
        self.args: tuple = ()

    async def fetch(self, query, *args):
        self.query, self.args = query, args
        return self.fetch_result

    async def fetchrow(self, query, *args):
        self.query, self.args = query, args
        return self.fetchrow_result

    async def fetchval(self, query, *args):
        self.query, self.args = query, args
        return self.fetchval_result


def normalized(query: str) -> str:
    return " ".join(query.split())


async def test_reopening_changes_only_the_attempt_process_state() -> None:
    connection = RecordingConnection()

    await SessionOverrideRepository().reopen_attempts_failed_by_geofence(
        connection, SESSION_ID, REOPENABLE_GEOFENCE_FAILURES,
    )

    query = normalized(connection.query)
    assert "UPDATE attendance_verification.verification_attempts" in query
    assert "UPDATE attendance_verification.geofence_validation_attempts" not in query
    assert "face_validation_attempts" not in query
    assert connection.args[0] == SESSION_ID
    assert set(connection.args[2]) == REOPENABLE_GEOFENCE_FAILURES
    assert connection.args[3] == "in_progress"


async def test_reopening_leaves_lecturer_decisions_alone() -> None:
    connection = RecordingConnection()

    await SessionOverrideRepository().reopen_attempts_failed_by_geofence(
        connection, SESSION_ID, REOPENABLE_GEOFENCE_FAILURES,
    )

    query = normalized(connection.query)
    assert "attendance_verification.attendance_records" in query
    assert "attendance_verification.manual_reviews" in query
    assert "review.review_status <> $5" in query
    assert connection.args[4] == "pending"


async def test_the_affected_count_is_roster_students_without_a_geofence_pass() -> None:
    connection = RecordingConnection(fetchval=187)

    count = await SessionOverrideRepository().count_students_without_geofence_pass(
        connection, SESSION_ID,
    )

    query = normalized(connection.query)
    assert count == 187
    assert "FROM attendance_session.session_students AS roster" in query
    assert "NOT EXISTS" in query
    assert connection.args == (SESSION_ID, "passed")


async def test_a_duplicate_waiver_insert_does_nothing() -> None:
    connection = RecordingConnection(fetchval=None)

    inserted = await SessionOverrideRepository().insert_override(
        connection,
        session_id=SESSION_ID,
        factor=RequiredStep.GEOFENCE,
        reason_code=GeofenceWaiverReason.GPS_UNAVAILABLE,
        reason_text=None,
        performed_by=USER_ID,
        performed_at=NOW,
        affected_student_count=3,
    )

    assert inserted is None
    assert "ON CONFLICT (session_id, verification_factor) DO NOTHING" in normalized(connection.query)
    assert connection.args[:5] == (SESSION_ID, "geofence", "session", "required", "waived")


async def test_the_session_lookup_is_scoped_to_the_assigned_lecturer_and_locks() -> None:
    connection = RecordingConnection()

    await SessionOverrideRepository().find_session_for_lecturer(
        connection, SESSION_ID, LECTURER_ID, lock_for_update=True,
    )

    query = normalized(connection.query)
    assert "academic.course_lecturers" in query
    assert "assignment.lecturer_id = $2" in query
    assert query.endswith("FOR UPDATE")
    assert connection.args == (SESSION_ID, LECTURER_ID)


async def test_geofence_health_counts_each_student_once() -> None:
    connection = RecordingConnection(fetchrow={"attempted": 193, "passed": 6})

    counts = await SessionOverrideRepository().geofence_counts(connection, SESSION_ID)

    assert counts == (193, 6)
    assert "GROUP BY attempt.id" in normalized(connection.query)
