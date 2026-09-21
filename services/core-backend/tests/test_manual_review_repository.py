from typing import Any
from uuid import UUID

from modules.attendance_verification.manual_review.repository import ManualReviewRepository

LECTURER_ID = UUID("22000000-0000-0000-0000-000000000001")
SESSION_ID = UUID("40000000-0000-0000-0000-000000000001")
ATTEMPT_ID = UUID("50000000-0000-0000-0000-000000000001")
STUDENT_ID = UUID("23000000-0000-0000-0000-000000000001")


class FakeConnection:
    def __init__(self, row: dict[str, Any] | None = None) -> None:
        self.row = row
        self.queries: list[str] = []

    async def fetch(self, query: str, *args: Any) -> list:
        self.queries.append(query)
        return []

    async def fetchrow(self, query: str, *args: Any):
        self.queries.append(query)
        return self.row


async def test_the_queue_skips_students_who_already_have_a_manual_record() -> None:
    connection = FakeConnection()

    await ManualReviewRepository().list_queue_for_lecturer(connection, LECTURER_ID)

    query = connection.queries[0]
    assert "NOT EXISTS" in query
    assert "manual_record.record_source = 'manual'" in query


async def test_the_queue_still_only_lists_failed_and_undecided_attempts() -> None:
    connection = FakeConnection()

    await ManualReviewRepository().list_queue_for_lecturer(connection, LECTURER_ID)

    query = connection.queries[0]
    assert "va.status = 'failed'" in query
    assert "review.review_status IS NULL OR review.review_status = 'pending'" in query


async def test_looking_up_an_attempt_reads_nothing_that_could_infer_lateness() -> None:
    connection = FakeConnection(
        row={
            "id": ATTEMPT_ID,
            "session_id": SESSION_ID,
            "student_id": STUDENT_ID,
            "status": "failed",
        },
    )

    attempt = await ManualReviewRepository().find_attempt_for_lecturer(
        connection,
        ATTEMPT_ID,
        LECTURER_ID,
        lock_for_update=True,
    )

    assert attempt is not None
    assert attempt.status == "failed"
    query = connection.queries[0]
    assert "started_at" not in query
    assert "late_after_at" not in query
    assert "FOR UPDATE OF va" in query
