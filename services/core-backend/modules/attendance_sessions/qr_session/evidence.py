"""Read-only QR evidence shared by finalization and progress endpoints.

Every method uses the supplied connection. In particular, finalization calls
``progress_for_session`` after reconciling check-ins in its own transaction.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

import asyncpg

from modules.contracts.qr_evidence import QrRequirementProgress


@dataclass(frozen=True)
class StudentQrState:
    session_id: UUID
    session_status: str
    qr_enabled: bool
    attempt_id: UUID | None
    checked_in_at: datetime | None


@dataclass(frozen=True)
class StudentQrBatch:
    qr_session_id: UUID
    mode: str
    status: str
    activated_at: datetime
    deactivated_at: datetime | None
    expires_at: datetime
    voided: bool
    required: bool
    passed: bool


@dataclass(frozen=True)
class QrBatchParticipation:
    qr_session_id: UUID
    mode: str
    status: str
    activated_at: datetime
    deactivated_at: datetime | None
    expires_at: datetime
    voided: bool
    void_reason: str | None
    required_student_count: int
    passed_student_count: int


class QrEvidenceRepository:
    async def progress_for_session(
        self, connection: asyncpg.Connection, session_id: UUID,
    ) -> Mapping[UUID, QrRequirementProgress]:
        rows = await connection.fetch(
            """
            SELECT attempt.id AS attempt_id,
                   COUNT(batch.id) AS required_count,
                   COUNT(batch.id) FILTER (WHERE EXISTS (
                       SELECT 1 FROM attendance_verification.qr_validation_attempts AS scan
                       WHERE scan.verification_attempt_id = attempt.id
                         AND scan.qr_batch_id = batch.id
                         AND scan.validation_status = 'accepted'
                   )) AS passed_count
            FROM attendance_verification.verification_attempts AS attempt
            LEFT JOIN attendance_session.qr_token_batches AS batch
                ON batch.session_id = attempt.session_id
               AND batch.activated_at > attempt.checked_in_at
               AND batch.voided_at IS NULL
            WHERE attempt.session_id = $1
              AND attempt.status = 'checked_in'
              AND attempt.checked_in_at IS NOT NULL
            GROUP BY attempt.id
            """,
            session_id,
        )
        return {
            row["attempt_id"]: QrRequirementProgress(
                required_count=row["required_count"], passed_count=row["passed_count"],
            )
            for row in rows
        }

    async def progress_for_attempt(
        self, connection: asyncpg.Connection, attempt_id: UUID,
    ) -> QrRequirementProgress | None:
        row = await connection.fetchrow(
            """
            SELECT COUNT(batch.id) AS required_count,
                   COUNT(batch.id) FILTER (WHERE EXISTS (
                       SELECT 1 FROM attendance_verification.qr_validation_attempts AS scan
                       WHERE scan.verification_attempt_id = attempt.id
                         AND scan.qr_batch_id = batch.id
                         AND scan.validation_status = 'accepted'
                   )) AS passed_count
            FROM attendance_verification.verification_attempts AS attempt
            LEFT JOIN attendance_session.qr_token_batches AS batch
                ON batch.session_id = attempt.session_id
               AND batch.activated_at > attempt.checked_in_at
               AND batch.voided_at IS NULL
            WHERE attempt.id = $1
              AND attempt.status = 'checked_in'
              AND attempt.checked_in_at IS NOT NULL
            GROUP BY attempt.id
            """,
            attempt_id,
        )
        return None if row is None else QrRequirementProgress(
            required_count=row["required_count"], passed_count=row["passed_count"],
        )

    async def student_state(
        self, connection: asyncpg.Connection, session_id: UUID, student_user_id: UUID,
    ) -> StudentQrState | None:
        row = await connection.fetchrow(
            """
            SELECT session.id AS session_id, session.status AS session_status,
                   session.requires_qr AS qr_enabled,
                   attempt.id AS attempt_id, attempt.checked_in_at
            FROM attendance_session.sessions AS session
            JOIN attendance_session.session_students AS roster
                ON roster.session_id = session.id
            JOIN academic.student_profiles AS student
                ON student.id = roster.student_id
            LEFT JOIN attendance_verification.verification_attempts AS attempt
                ON attempt.session_id = session.id
               AND attempt.student_id = student.id
               AND attempt.status = 'checked_in'
            WHERE session.id = $1 AND student.user_id = $2
              AND student.profile_status = 'active'
            """,
            session_id, student_user_id,
        )
        return None if row is None else StudentQrState(
            session_id=row["session_id"], session_status=row["session_status"],
            qr_enabled=bool(row["qr_enabled"]), attempt_id=row["attempt_id"],
            checked_in_at=row["checked_in_at"],
        )

    async def student_batches(
        self, connection: asyncpg.Connection, session_id: UUID,
        checked_in_at: datetime | None, attempt_id: UUID | None,
    ) -> list[StudentQrBatch]:
        rows = await connection.fetch(
            """
            SELECT batch.id, batch.mode, batch.status, batch.activated_at,
                   batch.deactivated_at, batch.expires_at, batch.voided_at,
                   ($2::timestamptz IS NOT NULL
                    AND batch.activated_at > $2
                    AND batch.voided_at IS NULL) AS required,
                   (batch.voided_at IS NULL AND EXISTS (
                       SELECT 1 FROM attendance_verification.qr_validation_attempts AS scan
                       WHERE scan.verification_attempt_id = $3
                         AND scan.qr_batch_id = batch.id
                         AND scan.validation_status = 'accepted'
                   )) AS passed
            FROM attendance_session.qr_token_batches AS batch
            WHERE batch.session_id = $1
            ORDER BY batch.activated_at DESC, batch.id DESC
            """,
            session_id, checked_in_at, attempt_id,
        )
        return [StudentQrBatch(
            qr_session_id=row["id"], mode=row["mode"], status=row["status"],
            activated_at=row["activated_at"], deactivated_at=row["deactivated_at"],
            expires_at=row["expires_at"], voided=row["voided_at"] is not None,
            required=row["required"], passed=row["passed"],
        ) for row in rows]

    async def batch_participation_for_session(
        self, connection: asyncpg.Connection, session_id: UUID,
    ) -> list[QrBatchParticipation]:
        rows = await connection.fetch(
            """
            SELECT batch.id, batch.mode, batch.status, batch.activated_at,
                   batch.deactivated_at, batch.expires_at, batch.voided_at,
                   batch.void_reason,
                   COUNT(attempt.id) AS required_student_count,
                   COUNT(attempt.id) FILTER (WHERE EXISTS (
                       SELECT 1 FROM attendance_verification.qr_validation_attempts AS scan
                       WHERE scan.verification_attempt_id = attempt.id
                         AND scan.qr_batch_id = batch.id
                         AND scan.validation_status = 'accepted'
                   )) AS passed_student_count
            FROM attendance_session.qr_token_batches AS batch
            LEFT JOIN attendance_verification.verification_attempts AS attempt
                ON attempt.session_id = batch.session_id
               AND attempt.status = 'checked_in'
               AND attempt.checked_in_at IS NOT NULL
               AND batch.activated_at > attempt.checked_in_at
               AND batch.voided_at IS NULL
               AND EXISTS (
                   SELECT 1 FROM attendance_session.session_students AS roster
                   WHERE roster.session_id = attempt.session_id
                     AND roster.student_id = attempt.student_id
               )
            WHERE batch.session_id = $1
            GROUP BY batch.id
            ORDER BY batch.activated_at DESC, batch.id DESC
            """,
            session_id,
        )
        return [QrBatchParticipation(
            qr_session_id=row["id"], mode=row["mode"], status=row["status"],
            activated_at=row["activated_at"], deactivated_at=row["deactivated_at"],
            expires_at=row["expires_at"], voided=row["voided_at"] is not None,
            void_reason=row["void_reason"],
            required_student_count=row["required_student_count"],
            passed_student_count=row["passed_student_count"],
        ) for row in rows]

    async def student_user_ids_required_for_batch(
        self, connection: asyncpg.Connection, qr_batch_id: UUID,
    ) -> list[UUID]:
        rows = await connection.fetch(
            """
            SELECT student.user_id
            FROM attendance_session.qr_token_batches AS batch
            JOIN attendance_verification.verification_attempts AS attempt
                ON attempt.session_id = batch.session_id
               AND attempt.status = 'checked_in'
               AND attempt.checked_in_at IS NOT NULL
               AND batch.activated_at > attempt.checked_in_at
            JOIN attendance_session.session_students AS roster
                ON roster.session_id = attempt.session_id
               AND roster.student_id = attempt.student_id
            JOIN academic.student_profiles AS student
                ON student.id = attempt.student_id
            WHERE batch.id = $1 AND batch.voided_at IS NULL
            ORDER BY student.user_id
            """,
            qr_batch_id,
        )
        return [row["user_id"] for row in rows]
