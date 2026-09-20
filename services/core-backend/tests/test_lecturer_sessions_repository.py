"""The lecturer session repository's SQL, against a fake connection.

The service tests fake this repository out entirely, so this is the only place
the real queries — the new roster counts and the pending-review exclusion —
get checked at all.
"""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from modules.attendance_sessions.lecturer_sessions.repository import (
    LecturerSessionRepository,
    SessionStudentRecord,
)

LECTURER_ID = UUID("22000000-0000-0000-0000-000000000001")
SESSION_ID = UUID("40000000-0000-0000-0000-000000000001")
STUDENT_ID = UUID("23000000-0000-0000-0000-000000000001")
ATTEMPT_ID = UUID("50000000-0000-0000-0000-000000000001")
CURRENT_TIME = datetime(2026, 9, 21, 9, 5, tzinfo=UTC)


class FakeDatabaseConnection:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows
        self.query = ""
        self.args: tuple[Any, ...] = ()

    async def fetch(self, query: str, *args: Any) -> list[dict[str, Any]]:
        self.query = query
        self.args = args
        return self.rows


def build_session_row() -> dict[str, Any]:
    return {
        "id": SESSION_ID,
        "course_offering_id": UUID("30000000-0000-0000-0000-000000000001"),
        "course_code": "CS3203",
        "course_name": "Software Engineering Project",
        "classroom_code": "LH-02",
        "scheduled_start_at": CURRENT_TIME,
        "scheduled_end_at": CURRENT_TIME + timedelta(hours=1),
        "check_in_opens_at": CURRENT_TIME - timedelta(minutes=5),
        "check_in_closes_at": CURRENT_TIME + timedelta(minutes=30),
        "late_after_at": CURRENT_TIME + timedelta(minutes=15),
        "activated_at": CURRENT_TIME,
        "closed_at": None,
        "cancelled_at": None,
        "requires_face_verification": True,
        "requires_geofence": True,
        "requires_qr": False,
        "enrolled_count": 40,
        "present_count": 0,
        "late_count": 0,
        "pending_review_count": 1,
        "checked_in_count": 10,
        "late_checked_in_count": 2,
        "failed_verification_count": 1,
        "absent_count": 0,
        "manual_count": 0,
    }


async def test_the_roster_query_asks_for_every_new_count() -> None:
    connection = FakeDatabaseConnection([build_session_row()])

    records = await LecturerSessionRepository().list_for_lecturer(connection, LECTURER_ID)

    assert len(records) == 1
    record = records[0]
    assert record.checked_in_count == 10
    assert record.late_checked_in_count == 2
    assert record.failed_verification_count == 1
    assert record.absent_count == 0
    assert record.manual_count == 0

    assert "AS checked_in_count" in connection.query
    assert "AS late_checked_in_count" in connection.query
    assert "AS failed_verification_count" in connection.query
    assert "AS absent_count" in connection.query
    assert "AS manual_count" in connection.query
    assert "va.initial_check_in_status = 'checked_in'" in connection.query
    assert "va.initial_check_in_status = 'late_checked_in'" in connection.query


async def test_pending_review_excludes_a_student_who_already_has_a_manual_record() -> None:
    connection = FakeDatabaseConnection([build_session_row()])

    await LecturerSessionRepository().list_for_lecturer(connection, LECTURER_ID)

    assert "NOT EXISTS" in connection.query
    assert "ar.record_source = 'manual'" in connection.query


def build_student_row(**overrides: Any) -> dict[str, Any]:
    values: dict[str, Any] = {
        "verification_attempt_id": ATTEMPT_ID,
        "student_id": STUDENT_ID,
        "registration_number": "230701A",
        "full_name": "Amal Perera",
        "verification_status": "checked_in",
        "failure_reason": None,
        "geofence_status": "passed",
        "face_status": "passed",
        "face_similarity_score": None,
        "face_liveness_passed": True,
        "qr_status": None,
        "initial_check_in_status": "checked_in",
        "checked_in_at": CURRENT_TIME,
        "attendance_status": None,
        "record_source": None,
        "manual_reason": None,
        "record_updated_at": None,
        "review_status": None,
    }
    values.update(overrides)
    return values


async def test_the_roster_row_carries_the_real_check_in_time_and_source_fields() -> None:
    connection = FakeDatabaseConnection([build_student_row()])

    students = await LecturerSessionRepository().list_students_for_session(
        connection,
        SESSION_ID,
    )

    assert students == [
        SessionStudentRecord(
            verification_attempt_id=ATTEMPT_ID,
            student_id=STUDENT_ID,
            registration_number="230701A",
            full_name="Amal Perera",
            verification_status="checked_in",
            failure_reason=None,
            geofence_status="passed",
            face_status="passed",
            face_similarity_score=None,
            face_liveness_passed=True,
            qr_status=None,
            initial_check_in_status="checked_in",
            checked_in_at=CURRENT_TIME,
            attendance_status=None,
            record_source=None,
            manual_reason=None,
            record_updated_at=None,
            review_status=None,
        )
    ]
    assert "va.checked_in_at" in connection.query
    assert "va.failure_reason" in connection.query
    assert "va.initial_check_in_status" in connection.query
    assert "record.record_source" in connection.query
    assert "record.manual_reason" in connection.query
    assert "record.updated_at AS record_updated_at" in connection.query
    # va.started_at was the old (wrong) stand-in for the check-in time.
    assert "va.started_at AS checked_in_at" not in connection.query
