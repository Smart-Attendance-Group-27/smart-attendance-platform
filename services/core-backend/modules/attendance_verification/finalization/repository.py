from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

import asyncpg

from modules.attendance_verification.finalization.types import FinalizationResult

AUTOMATIC_RECORD_SOURCE = "automatic"


@dataclass(frozen=True)
class RosterStudentState:
    student_id: UUID
    verification_attempt_id: UUID | None
    initial_check_in_status: str | None
    has_manual_record: bool


class FinalizationRepository:
    async def lock_session_attempts(
        self,
        connection: asyncpg.Connection,
        session_id: UUID,
    ) -> None:
        """Locks every attempt of the session for the rest of the transaction.

        Reconciliation only needs the ``in_progress`` ones, but the roster read
        right after it must see a snapshot nothing else can change underneath
        it, so this locks the whole session up front.
        """

        await connection.execute(
            """
            SELECT id
            FROM attendance_verification.verification_attempts
            WHERE session_id = $1
            FOR UPDATE
            """,
            session_id,
        )

    async def fetch_roster_state(
        self,
        connection: asyncpg.Connection,
        session_id: UUID,
    ) -> list[RosterStudentState]:
        rows = await connection.fetch(
            """
            SELECT
                ss.student_id,
                va.id AS verification_attempt_id,
                va.initial_check_in_status,
                (
                    record.record_source IS NOT NULL
                    AND record.record_source <> 'automatic'
                ) AS has_manual_record
            FROM attendance_session.session_students AS ss
            LEFT JOIN attendance_verification.verification_attempts AS va
                ON va.session_id = ss.session_id AND va.student_id = ss.student_id
            LEFT JOIN attendance_verification.attendance_records AS record
                ON record.session_id = ss.session_id AND record.student_id = ss.student_id
            WHERE ss.session_id = $1
            """,
            session_id,
        )
        return [
            RosterStudentState(
                student_id=row["student_id"],
                verification_attempt_id=row["verification_attempt_id"],
                initial_check_in_status=row["initial_check_in_status"],
                has_manual_record=bool(row["has_manual_record"]),
            )
            for row in rows
        ]

    async def upsert_automatic_records(
        self,
        connection: asyncpg.Connection,
        session_id: UUID,
        results: list[FinalizationResult],
        decided_at: datetime,
    ) -> None:
        """Writes every decision at once. Never touches a manual record.

        The ``WHERE`` on the ``DO UPDATE`` is the actual guard: it only fires
        when the existing row is already automatic, so a manual record written
        after ``fetch_roster_state`` read the roster — a real race, since this
        holds no lock on ``attendance_records`` — is still never overwritten.
        """

        if not results:
            return

        record_ids = [uuid4() for _ in results]
        student_ids = [result.student_id for result in results]
        statuses = [result.status.value for result in results]

        await connection.execute(
            """
            INSERT INTO attendance_verification.attendance_records (
                id, session_id, student_id, recorded_by,
                attendance_status, record_source, manual_reason,
                created_at, updated_at
            )
            SELECT
                unnest($2::uuid[]), $1, unnest($3::uuid[]), NULL,
                unnest($4::text[]), $5, NULL,
                $6, $6
            ON CONFLICT (session_id, student_id) DO UPDATE
            SET attendance_status = EXCLUDED.attendance_status,
                record_source = EXCLUDED.record_source,
                updated_at = EXCLUDED.updated_at
            WHERE attendance_records.record_source = $5
            """,
            session_id,
            record_ids,
            student_ids,
            statuses,
            AUTOMATIC_RECORD_SOURCE,
            decided_at,
        )


__all__ = ["FinalizationRepository", "RosterStudentState"]
