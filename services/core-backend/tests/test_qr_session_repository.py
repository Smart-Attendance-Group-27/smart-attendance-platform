from datetime import UTC, datetime
from uuid import UUID

import pytest

from modules.attendance_sessions.qr_session.repository import QrSessionRepository


class RecordingConnection:
    def __init__(self, row=None, value=None) -> None:
        self.row = row
        self.value = value
        self.query = ""
        self.args: tuple = ()

    async def fetchrow(self, query: str, *args):
        self.query, self.args = query, args
        return self.row

    async def fetchval(self, query: str, *args):
        self.query, self.args = query, args
        return self.value

    async def execute(self, query: str, *args):
        self.query, self.args = query, args


@pytest.mark.asyncio
async def test_find_student_attempt_reads_check_in_and_locks_for_write() -> None:
    session_id = UUID("40000000-0000-0000-0000-000000000001")
    student_id = UUID("23000000-0000-0000-0000-000000000001")
    attempt_id = UUID("70000000-0000-0000-0000-000000000001")
    checked_in_at = datetime(2026, 8, 6, 9, 59, tzinfo=UTC)
    connection = RecordingConnection(row={
        "id": attempt_id, "status": "checked_in", "checked_in_at": checked_in_at,
    })

    result = await QrSessionRepository().find_student_attempt(
        connection, session_id, student_id, lock_for_update=True,
    )

    assert (result.id, result.status, result.checked_in_at) == (
        attempt_id, "checked_in", checked_in_at,
    )
    assert "FOR UPDATE" in connection.query
    assert connection.args == (session_id, student_id)


@pytest.mark.asyncio
async def test_insert_qr_attempt_always_binds_batch_id() -> None:
    ids = [UUID(f"{number:08d}-0000-0000-0000-000000000001") for number in (8, 7, 5)]
    now = datetime(2026, 8, 6, 10, 0, tzinfo=UTC)
    connection = RecordingConnection()

    await QrSessionRepository().insert_qr_validation_attempt(
        connection, ids[0], ids[1], ids[2], None, 1, "accepted", None, now,
    )

    assert "qr_batch_id" in connection.query
    assert connection.args == (ids[0], ids[1], ids[2], None, 1, "accepted", None, now)


@pytest.mark.asyncio
async def test_lock_session_for_qr_write_uses_share_lock() -> None:
    session_id = UUID("40000000-0000-0000-0000-000000000001")
    connection = RecordingConnection(row={
        "id": session_id, "status": "active",
        "scheduled_end_at": datetime(2026, 8, 6, 11, 0, tzinfo=UTC),
        "closed_at": None, "cancelled_at": None, "requires_qr": True,
    })

    result = await QrSessionRepository().lock_session_for_qr_write(connection, session_id)

    assert result.status == "active"
    assert "FOR SHARE" in connection.query
    assert connection.args == (session_id,)
