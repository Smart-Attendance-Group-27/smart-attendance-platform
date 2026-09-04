from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

import asyncpg

ACCEPTED_QR_STATUS = "accepted"


@dataclass(frozen=True)
class QrWindowRecord:
    """One lecturer-created QR verification window."""

    id: UUID
    activated_at: datetime
    expires_at: datetime
    deactivated_at: datetime | None

    @property
    def effective_end_at(self) -> datetime:
        """When the window actually stopped accepting scans.

        Creating a new QR window deactivates the previous one, so a window
        can die well before its scheduled expiry.
        """
        if self.deactivated_at is None:
            return self.expires_at
        return min(self.expires_at, self.deactivated_at)


@dataclass(frozen=True)
class MalformedQrWindowRecord:
    """A QR batch that could never have been legitimately scanned.

    Reported rather than silently dropped so a configuration or data fault
    is visible, but excluded from what a student is judged against — an
    internal fault must not cost a genuine student their attendance.
    """

    id: UUID
    activated_at: datetime | None
    expires_at: datetime | None
    reason: str


class QrEvidenceRepository:
    """Answers the two questions final attendance needs about QR.

    1. Which QR windows apply to this student?
    2. Which of those did they actually satisfy?

    Both are expressed in terms of DISTINCT lecturer-created windows, never
    raw scan attempts: a student who retries the same window three times has
    satisfied one window, not three.
    """

    async def list_applicable_windows(
        self,
        connection: asyncpg.Connection,
        session_id: UUID,
        checked_in_at: datetime,
        finalized_at: datetime,
    ) -> list[QrWindowRecord]:
        """QR windows a student who checked in at `checked_in_at` must satisfy.

        A window applies when it was still live at some point after the
        student completed check-in. A window that had already ended before
        they checked in was impossible for them to scan, so it is not
        required — their lateness is handled by the late-attendance rule
        instead, not by failing them on a QR they could never have made.

        Malformed windows are excluded here; use `list_malformed_windows`
        to surface them.
        """
        rows = await connection.fetch(
            """
            SELECT id, activated_at, expires_at, deactivated_at
            FROM attendance_session.qr_token_batches
            WHERE session_id = $1
              AND activated_at IS NOT NULL
              AND expires_at IS NOT NULL
              AND expires_at > activated_at
              AND activated_at <= $3
              AND LEAST(
                    expires_at,
                    COALESCE(deactivated_at, expires_at)
                  ) > $2
            ORDER BY activated_at ASC, id ASC
            """,
            session_id,
            checked_in_at,
            finalized_at,
        )
        return [
            QrWindowRecord(
                id=row["id"],
                activated_at=row["activated_at"],
                expires_at=row["expires_at"],
                deactivated_at=row["deactivated_at"],
            )
            for row in rows
        ]

    async def list_malformed_windows(
        self,
        connection: asyncpg.Connection,
        session_id: UUID,
    ) -> list[MalformedQrWindowRecord]:
        """QR batches that are internally invalid, with the reason why.

        activated_at is nullable in the baseline schema, and the
        CK_qr_token_batches_expires_after_activation constraint cannot fire
        when it is NULL, so both faults are still reachable on older rows.
        """
        rows = await connection.fetch(
            """
            SELECT
                id,
                activated_at,
                expires_at,
                CASE
                    WHEN activated_at IS NULL THEN 'missing_activated_at'
                    WHEN expires_at IS NULL THEN 'missing_expires_at'
                    ELSE 'expiry_not_after_activation'
                END AS reason
            FROM attendance_session.qr_token_batches
            WHERE session_id = $1
              AND (
                    activated_at IS NULL
                    OR expires_at IS NULL
                    OR expires_at <= activated_at
                  )
            ORDER BY id ASC
            """,
            session_id,
        )
        return [
            MalformedQrWindowRecord(
                id=row["id"],
                activated_at=row["activated_at"],
                expires_at=row["expires_at"],
                reason=row["reason"],
            )
            for row in rows
        ]

    async def list_satisfied_window_ids(
        self,
        connection: asyncpg.Connection,
        verification_attempt_id: UUID,
    ) -> set[UUID]:
        """DISTINCT QR windows this student successfully verified.

        DISTINCT is the whole point: repeated scans against one window —
        two failures then a success, say — satisfy that one window once.
        """
        rows = await connection.fetch(
            """
            SELECT DISTINCT qr_batch_id
            FROM attendance_verification.qr_validation_attempts
            WHERE verification_attempt_id = $1
              AND validation_status = $2
              AND qr_batch_id IS NOT NULL
            """,
            verification_attempt_id,
            ACCEPTED_QR_STATUS,
        )
        return {row["qr_batch_id"] for row in rows}


__all__ = [
    "ACCEPTED_QR_STATUS",
    "MalformedQrWindowRecord",
    "QrEvidenceRepository",
    "QrWindowRecord",
]
