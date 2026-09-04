from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from modules.attendance_verification.qr_evidence.repository import (
    MalformedQrWindowRecord,
    QrEvidenceRepository,
    QrWindowRecord,
)

SESSION_ID = UUID("40000000-0000-0000-0000-000000000001")
ATTEMPT_ID = UUID("70000000-0000-0000-0000-000000000001")
WINDOW_ONE = UUID("50000000-0000-0000-0000-000000000001")
WINDOW_TWO = UUID("50000000-0000-0000-0000-000000000002")
WINDOW_THREE = UUID("50000000-0000-0000-0000-000000000003")

LECTURE_START = datetime(2026, 8, 6, 9, 0, tzinfo=UTC)
CHECKED_IN_AT = LECTURE_START + timedelta(minutes=10)
FINALIZED_AT = LECTURE_START + timedelta(hours=2)


class FakeConnection:
    """Records the SQL and arguments the repository issues."""

    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self.rows = rows or []
        self.query = ""
        self.args: tuple[Any, ...] = ()

    async def fetch(self, query: str, *args: Any) -> list[dict[str, Any]]:
        self.query = query
        self.args = args
        return self.rows


def window_row(
    window_id: UUID,
    *,
    activated_at: datetime,
    expires_at: datetime,
    deactivated_at: datetime | None = None,
) -> dict[str, Any]:
    return {
        "id": window_id,
        "activated_at": activated_at,
        "expires_at": expires_at,
        "deactivated_at": deactivated_at,
    }


# ---------------------------------------------------------------------------
# effective_end_at
# ---------------------------------------------------------------------------


def test_effective_end_is_the_expiry_when_the_window_ran_its_course() -> None:
    window = QrWindowRecord(
        id=WINDOW_ONE,
        activated_at=LECTURE_START,
        expires_at=LECTURE_START + timedelta(minutes=5),
        deactivated_at=None,
    )

    assert window.effective_end_at == LECTURE_START + timedelta(minutes=5)


def test_effective_end_is_the_deactivation_when_a_later_window_replaced_it() -> None:
    """Opening a new QR window deactivates the previous one.

    A window scheduled to run for 30 minutes but killed after 5 was only
    scannable for those 5 minutes.
    """
    window = QrWindowRecord(
        id=WINDOW_ONE,
        activated_at=LECTURE_START,
        expires_at=LECTURE_START + timedelta(minutes=30),
        deactivated_at=LECTURE_START + timedelta(minutes=5),
    )

    assert window.effective_end_at == LECTURE_START + timedelta(minutes=5)


# ---------------------------------------------------------------------------
# list_applicable_windows
# ---------------------------------------------------------------------------


async def test_applicable_windows_are_scoped_and_ordered() -> None:
    connection = FakeConnection(
        [
            window_row(
                WINDOW_TWO,
                activated_at=LECTURE_START + timedelta(minutes=8),
                expires_at=LECTURE_START + timedelta(minutes=15),
            ),
            window_row(
                WINDOW_THREE,
                activated_at=LECTURE_START + timedelta(minutes=45),
                expires_at=LECTURE_START + timedelta(minutes=50),
            ),
        ]
    )

    windows = await QrEvidenceRepository().list_applicable_windows(
        connection, SESSION_ID, CHECKED_IN_AT, FINALIZED_AT
    )

    assert [window.id for window in windows] == [WINDOW_TWO, WINDOW_THREE]
    assert connection.args == (SESSION_ID, CHECKED_IN_AT, FINALIZED_AT)
    assert "ORDER BY activated_at ASC, id ASC" in connection.query


async def test_applicable_windows_query_excludes_windows_that_ended_before_check_in() -> None:
    """The rule the query has to express, spelled out.

    A student who checked in at 09:10 cannot be judged against a window
    that closed at 09:05 — scanning it was impossible for them.
    """
    connection = FakeConnection()

    await QrEvidenceRepository().list_applicable_windows(
        connection, SESSION_ID, CHECKED_IN_AT, FINALIZED_AT
    )

    normalized = " ".join(connection.query.split())
    assert "LEAST( expires_at, COALESCE(deactivated_at, expires_at) ) > $2" in normalized


async def test_applicable_windows_query_filters_malformed_batches() -> None:
    connection = FakeConnection()

    await QrEvidenceRepository().list_applicable_windows(
        connection, SESSION_ID, CHECKED_IN_AT, FINALIZED_AT
    )

    normalized = " ".join(connection.query.split())
    assert "activated_at IS NOT NULL" in normalized
    assert "expires_at IS NOT NULL" in normalized
    assert "expires_at > activated_at" in normalized


async def test_applicable_windows_query_ignores_windows_opened_after_finalization() -> None:
    connection = FakeConnection()

    await QrEvidenceRepository().list_applicable_windows(
        connection, SESSION_ID, CHECKED_IN_AT, FINALIZED_AT
    )

    normalized = " ".join(connection.query.split())
    assert "activated_at <= $3" in normalized


async def test_no_applicable_windows_when_the_lecturer_created_none() -> None:
    connection = FakeConnection([])

    windows = await QrEvidenceRepository().list_applicable_windows(
        connection, SESSION_ID, CHECKED_IN_AT, FINALIZED_AT
    )

    assert windows == []


# ---------------------------------------------------------------------------
# list_malformed_windows
# ---------------------------------------------------------------------------


async def test_malformed_windows_are_reported_with_a_reason() -> None:
    connection = FakeConnection(
        [
            {
                "id": WINDOW_ONE,
                "activated_at": None,
                "expires_at": LECTURE_START,
                "reason": "missing_activated_at",
            }
        ]
    )

    malformed = await QrEvidenceRepository().list_malformed_windows(
        connection, SESSION_ID
    )

    assert malformed == [
        MalformedQrWindowRecord(
            id=WINDOW_ONE,
            activated_at=None,
            expires_at=LECTURE_START,
            reason="missing_activated_at",
        )
    ]
    assert connection.args == (SESSION_ID,)


async def test_malformed_window_query_covers_every_impossible_shape() -> None:
    connection = FakeConnection()

    await QrEvidenceRepository().list_malformed_windows(connection, SESSION_ID)

    normalized = " ".join(connection.query.split())
    assert "activated_at IS NULL" in normalized
    assert "expires_at IS NULL" in normalized
    assert "expires_at <= activated_at" in normalized


# ---------------------------------------------------------------------------
# list_satisfied_window_ids
# ---------------------------------------------------------------------------


async def test_satisfied_windows_are_distinct_not_a_scan_count() -> None:
    """Retrying one window must not look like satisfying several.

    Two failures then a success against a single window is one satisfied
    window, not three pieces of evidence.
    """
    connection = FakeConnection(
        [{"qr_batch_id": WINDOW_ONE}, {"qr_batch_id": WINDOW_TWO}]
    )

    satisfied = await QrEvidenceRepository().list_satisfied_window_ids(
        connection, ATTEMPT_ID
    )

    assert satisfied == {WINDOW_ONE, WINDOW_TWO}
    assert connection.args == (ATTEMPT_ID, "accepted")
    normalized = " ".join(connection.query.split())
    assert "SELECT DISTINCT qr_batch_id" in normalized


async def test_satisfied_windows_only_counts_accepted_scans() -> None:
    connection = FakeConnection()

    await QrEvidenceRepository().list_satisfied_window_ids(connection, ATTEMPT_ID)

    normalized = " ".join(connection.query.split())
    assert "validation_status = $2" in normalized
    assert "qr_batch_id IS NOT NULL" in normalized


async def test_no_satisfied_windows_for_a_student_who_never_scanned() -> None:
    connection = FakeConnection([])

    satisfied = await QrEvidenceRepository().list_satisfied_window_ids(
        connection, ATTEMPT_ID
    )

    assert satisfied == set()
