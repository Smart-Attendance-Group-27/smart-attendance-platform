from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

import asyncpg


ACTIVE_STATUS = "active"
INACTIVE_STATUS = "inactive"
STATIC_QR_MODE = "static"
DYNAMIC_QR_MODE = "dynamic"
STATIC_QR_TOKEN_SEQUENCE_NUMBER = 1


@dataclass(frozen=True)
class AttendanceSessionRecord:
    id: UUID
    status: str | None
    scheduled_end_at: datetime
    closed_at: datetime | None
    cancelled_at: datetime | None


@dataclass(frozen=True)
class QrVerificationRecord:
    qr_session_id: UUID
    qr_mode: str | None
    refresh_interval_seconds: int | None
    batch_status: str | None
    batch_deactivated_at: datetime | None
    attendance_session_id: UUID | None
    attendance_session_status: str | None
    attendance_session_scheduled_end_at: datetime | None
    attendance_session_closed_at: datetime | None
    attendance_session_cancelled_at: datetime | None
    token_hash: str | None
    token_valid_from: datetime | None
    token_expires_at: datetime | None
    token_revoked_at: datetime | None


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
        mode: str,
        refresh_interval_seconds: int | None,
        activated_at: datetime,
    ) -> None:
        await connection.execute(
            """
            INSERT INTO attendance_session.qr_token_batches (
                id,
                session_id,
                mode,
                refresh_interval_seconds,
                issued_by,
                status,
                activated_at,
                deactivated_at,
                created_at
            )
            VALUES ($1, $2, $3, $4, NULL, $5, $6, NULL, $6)
            """,
            qr_session_id,
            attendance_session_id,
            mode,
            refresh_interval_seconds,
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

    async def fetch_qr_verification_record(
        self,
        connection: asyncpg.Connection,
        qr_session_id: UUID,
    ) -> QrVerificationRecord | None:
        row = await connection.fetchrow(
            """
            SELECT
                batch.id AS qr_session_id,
                batch.mode AS qr_mode,
                batch.refresh_interval_seconds AS refresh_interval_seconds,
                batch.status AS batch_status,
                batch.deactivated_at AS batch_deactivated_at,
                session.id AS attendance_session_id,
                session.status AS attendance_session_status,
                session.scheduled_end_at AS attendance_session_scheduled_end_at,
                session.closed_at AS attendance_session_closed_at,
                session.cancelled_at AS attendance_session_cancelled_at,
                token.token_hash AS token_hash,
                token.valid_from AS token_valid_from,
                token.expires_at AS token_expires_at,
                token.revoked_at AS token_revoked_at
            FROM attendance_session.qr_token_batches AS batch
            LEFT JOIN attendance_session.sessions AS session
                ON session.id = batch.session_id
            LEFT JOIN attendance_session.qr_tokens AS token
                ON token.qr_batch_id = batch.id
            WHERE batch.id = $1
            ORDER BY token.sequence_number ASC
            LIMIT 1
            """,
            qr_session_id,
        )

        if row is None:
            return None

        return QrVerificationRecord(
            qr_session_id=row["qr_session_id"],
            qr_mode=row["qr_mode"],
            refresh_interval_seconds=row["refresh_interval_seconds"],
            batch_status=row["batch_status"],
            batch_deactivated_at=row["batch_deactivated_at"],
            attendance_session_id=row["attendance_session_id"],
            attendance_session_status=row["attendance_session_status"],
            attendance_session_scheduled_end_at=row[
                "attendance_session_scheduled_end_at"
            ],
            attendance_session_closed_at=row["attendance_session_closed_at"],
            attendance_session_cancelled_at=row["attendance_session_cancelled_at"],
            token_hash=row["token_hash"],
            token_valid_from=row["token_valid_from"],
            token_expires_at=row["token_expires_at"],
            token_revoked_at=row["token_revoked_at"],
        )
