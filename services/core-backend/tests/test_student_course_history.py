from datetime import UTC, datetime
from uuid import UUID

from modules.academic.student_courses.repository import StudentCourseSessionRecord
from modules.academic.student_courses.service import (
    _group_attendance_records_by_course,
    _group_sessions_by_course,
)

COURSE_ID = UUID("30000000-0000-0000-0000-000000000001")
START = datetime(2026, 7, 20, 10, 0, tzinfo=UTC)
END = datetime(2026, 7, 20, 11, 0, tzinfo=UTC)


def session(index: int, *, status: str | None = None, closed: bool = False,
            cancelled: bool = False) -> StudentCourseSessionRecord:
    return StudentCourseSessionRecord(
        id=UUID(f"40000000-0000-0000-0000-{index:012d}"),
        course_offering_id=COURSE_ID,
        session_title=f"Session {index}",
        session_type="lecture",
        scheduled_start_at=START,
        scheduled_end_at=END,
        check_in_opens_at=START,
        check_in_closes_at=END,
        venue="Room 1",
        status="active" if not closed and not cancelled else "closed",
        closed_at=END if closed else None,
        cancelled_at=END if cancelled else None,
        attendance_status=status,
        attendance_recorded_at=END if status else None,
    )


def test_history_includes_legacy_absence_and_cancelled_sessions() -> None:
    rows = [
        session(1, status="present", closed=True),
        session(2, status="late", closed=True),
        session(3, status="absent", closed=True),
        session(4, closed=True),  # Legacy close without an ABSENT row.
        session(5, cancelled=True),
        session(6),  # Check-in window ended, final attendance still pending.
    ]

    records = _group_attendance_records_by_course(rows)[COURSE_ID]
    sessions = _group_sessions_by_course(rows)[COURSE_ID]

    assert [record.status for record in records] == [
        "Present", "Late", "Absent", "Absent", "Cancelled", "Awaiting",
    ]
    assert [item.status for item in sessions] == [
        "marked", "late", "absent", "absent", "cancelled", "awaiting",
    ]
    assert records[3].recorded_text == "No attendance recorded"
    assert records[4].recorded_text == "Session cancelled"
