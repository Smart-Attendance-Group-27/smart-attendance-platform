from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

import asyncpg


ACTIVE_STATUS = "active"
INACTIVE_STATUS = "inactive"
STATIC_QR_TOKEN_SEQUENCE_NUMBER = 1


@dataclass(frozen=True)
class AttendanceSessionRecord:
    id: UUID
    status: str | None
    scheduled_end_at: datetime
    closed_at: datetime | None
    cancelled_at: datetime | None


class QrSessionRepository:
    async def lock_attendance_session(
        self,
        connection: asyncpg.Connection,
        session_id: UUID,
    ) -> AttendanceSessionRecord | None:
        row = await connection.fetchrow(
            """
            SELECT id, status, scheduled_end_at, closed_at, cancelled_at
            FROM attendance_session.sessions
            WHERE id = $1
            FOR UPDATE
            """,
            session_id,
        )

        if row is None:
            return None

        return AttendanceSessionRecord(
            id=row["id"],
            status=row["status"],
            scheduled_end_at=row["scheduled_end_at"],
            closed_at=row["closed_at"],
            cancelled_at=row["cancelled_at"],
        )

    async def close_existing_active_qr_sessions(
        self,
        connection: asyncpg.Connection,
        session_id: UUID,
        deactivated_at: datetime,
    ) -> None:
        await connection.execute(
            """
            WITH deactivated_batches AS (
                UPDATE attendance_session.qr_token_batches
                SET status = $3,
                    deactivated_at = $2
                WHERE session_id = $1
                  AND status = $4
                  AND deactivated_at IS NULL
                RETURNING id
            )
            UPDATE attendance_session.qr_tokens AS token
            SET revoked_at = $2
            FROM deactivated_batches AS batch
            WHERE token.qr_batch_id = batch.id
              AND token.revoked_at IS NULL
            """,
            session_id,
            deactivated_at,
            INACTIVE_STATUS,
            ACTIVE_STATUS,
        )

    async def insert_qr_batch(
        self,
        connection: asyncpg.Connection,
        qr_session_id: UUID,
        attendance_session_id: UUID,
        activated_at: datetime,
    ) -> None:
        await connection.execute(
            """
            INSERT INTO attendance_session.qr_token_batches (
                id,
                session_id,
                refresh_interval_seconds,
                issued_by,
                status,
                activated_at,
                deactivated_at,
                created_at
            )
            VALUES ($1, $2, NULL, NULL, $3, $4, NULL, $4)
            """,
            qr_session_id,
            attendance_session_id,
            ACTIVE_STATUS,
            activated_at,
        )

    async def insert_qr_token(
        self,
        connection: asyncpg.Connection,
        qr_token_id: UUID,
        qr_session_id: UUID,
        token_hash: str,
        valid_from: datetime,
        expires_at: datetime,
    ) -> None:
        await connection.execute(
            """
            INSERT INTO attendance_session.qr_tokens (
                id,
                qr_batch_id,
                token_hash,
                sequence_number,
                valid_from,
                expires_at,
                revoked_at,
                created_at
            )
            VALUES ($1, $2, $3, $6, $4, $5, NULL, $4)
            """,
            qr_token_id,
            qr_session_id,
            token_hash,
            valid_from,
            expires_at,
            STATIC_QR_TOKEN_SEQUENCE_NUMBER,
        )
