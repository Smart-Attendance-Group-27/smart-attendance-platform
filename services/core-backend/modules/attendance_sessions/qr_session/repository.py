from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

import asyncpg

from modules.attendance_sessions.qr_session.metadata import QrBatchMetadata


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
    requires_qr: bool | None = True


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
    # Repository methods are intentionally thin: raw SQL lives here, while QR
    # business decisions stay in QrSessionService.
    async def fetch_attendance_session(
        self,
        connection: asyncpg.Connection,
        session_id: UUID,
    ) -> AttendanceSessionRecord | None:
        # Creation locks the parent attendance session so two lecturer actions
        # cannot create conflicting active QR batches at the same time.
        row = await connection.fetchrow(
            """
            SELECT id, status, scheduled_end_at, closed_at, cancelled_at, requires_qr
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
            requires_qr=row["requires_qr"],
        )

    async def session_owned_by_lecturer(
        self,
        connection: asyncpg.Connection,
        session_id: UUID,
        lecturer_user_id: UUID,
    ) -> bool:
        # course_lecturers.lecturer_id references academic.lecturer_profiles.id,
        # not identity.users.id — join through the profile on user_id rather
        # than comparing the caller's identity.users id directly.
        row = await connection.fetchrow(
            """
            SELECT 1
            FROM attendance_session.sessions AS session
            JOIN academic.course_offerings AS offering
                ON offering.id = session.course_offering_id
            JOIN academic.course_lecturers AS assignment
                ON assignment.course_offering_id = offering.id
            JOIN academic.lecturer_profiles AS profile
                ON profile.id = assignment.lecturer_id
            WHERE session.id = $1
              AND profile.user_id = $2
              AND profile.profile_status = 'active'
            """,
            session_id,
            lecturer_user_id,
        )
        return row is not None

    async def qr_batch_owned_by_lecturer(
        self,
        connection: asyncpg.Connection,
        qr_session_id: UUID,
        lecturer_user_id: UUID,
    ) -> bool:
        row = await connection.fetchrow(
            """
            SELECT 1
            FROM attendance_session.qr_token_batches AS batch
            JOIN attendance_session.sessions AS session
                ON session.id = batch.session_id
            JOIN academic.course_offerings AS offering
                ON offering.id = session.course_offering_id
            JOIN academic.course_lecturers AS assignment
                ON assignment.course_offering_id = offering.id
            JOIN academic.lecturer_profiles AS profile
                ON profile.id = assignment.lecturer_id
            WHERE batch.id = $1
              AND profile.user_id = $2
              AND profile.profile_status = 'active'
            """,
            qr_session_id,
            lecturer_user_id,
        )
        return row is not None

    async def close_existing_active_qr_sessions(
        self,
        connection: asyncpg.Connection,
        session_id: UUID,
        deactivated_at: datetime,
    ) -> list[UUID]:
        # A session should have at most one active QR batch. When a lecturer
        # launches a new QR, older active batches are deactivated and their
        # static token rows are revoked.
        rows = await connection.fetch(
            """
            WITH deactivated_batches AS (
                UPDATE attendance_session.qr_token_batches
                SET status = $3,
                    deactivated_at = $2
                WHERE session_id = $1
                  AND status = $4
                  AND deactivated_at IS NULL
                RETURNING id
            ),
            revoked_tokens AS (
                UPDATE attendance_session.qr_tokens AS token
                SET revoked_at = $2
                FROM deactivated_batches AS batch
                WHERE token.qr_batch_id = batch.id
                  AND token.revoked_at IS NULL
                RETURNING token.id
            )
            SELECT id
            FROM deactivated_batches
            """,
            session_id,
            deactivated_at,
            INACTIVE_STATUS,
            ACTIVE_STATUS,
        )
        return [row["id"] for row in rows]

    async def insert_qr_batch(
        self,
        connection: asyncpg.Connection,
        qr_session_id: UUID,
        attendance_session_id: UUID,
        mode: str,
        refresh_interval_seconds: int | None,
        activated_at: datetime,
        expires_at: datetime,
        issued_by: UUID,
    ) -> None:
        # qr_token_batches is the QR session table. Its id is the qr_session_id
        # used later by mobile verification and dynamic stream endpoints.
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
                expires_at,
                deactivated_at,
                created_at
            )
            VALUES ($1, $2, $3, $4, $8, $5, $6, $7, NULL, $6)
            """,
            qr_session_id,
            attendance_session_id,
            mode,
            refresh_interval_seconds,
            ACTIVE_STATUS,
            activated_at,
            expires_at,
            issued_by,
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
        # Static QR has one token row containing only token_hash. Dynamic QR has
        # no rotating token rows because values are generated with HMAC.
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

    async def lock_student_eligibility(
        self,
        connection: asyncpg.Connection,
        session_id: UUID,
        student_id: UUID,
    ) -> bool:
        row = await connection.fetchrow(
            """
            SELECT id
            FROM attendance_session.session_students
            WHERE session_id = $1 AND student_id = $2
            FOR SHARE
            """,
            session_id,
            student_id,
        )
        return row is not None

    async def find_qr_token_id_for_batch(
        self,
        connection: asyncpg.Connection,
        qr_batch_id: UUID,
    ) -> UUID | None:
        # Static mode has exactly one qr_tokens row per batch; dynamic mode has
        # none (its values are generated on the fly, never persisted).
        return await connection.fetchval(
            """
            SELECT id
            FROM attendance_session.qr_tokens
            WHERE qr_batch_id = $1
            """,
            qr_batch_id,
        )

    async def next_qr_attempt_number(
        self,
        connection: asyncpg.Connection,
        verification_attempt_id: UUID,
    ) -> int:
        value = await connection.fetchval(
            """
            SELECT COALESCE(MAX(attempt_number), 0) + 1
            FROM attendance_verification.qr_validation_attempts
            WHERE verification_attempt_id = $1
            """,
            verification_attempt_id,
        )
        return int(value)

    async def insert_qr_validation_attempt(
        self,
        connection: asyncpg.Connection,
        qr_validation_attempt_id: UUID,
        verification_attempt_id: UUID,
        qr_token_id: UUID | None,
        attempt_number: int,
        validation_status: str,
        failure_reason: str | None,
        validated_at: datetime,
    ) -> None:
        await connection.execute(
            """
            INSERT INTO attendance_verification.qr_validation_attempts (
                id,
                verification_attempt_id,
                qr_token_id,
                attempt_number,
                validation_status,
                failure_reason,
                validated_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            """,
            qr_validation_attempt_id,
            verification_attempt_id,
            qr_token_id,
            attempt_number,
            validation_status,
            failure_reason,
            validated_at,
        )

    async def fetch_qr_batch_metadata(
        self,
        connection: asyncpg.Connection,
        qr_session_id: UUID,
    ) -> QrBatchMetadata | None:
        # Metadata read used by dynamic stream generation. This is the shape
        # cached in Redis because the stream asks for it repeatedly.
        row = await connection.fetchrow(
            """
            SELECT
                batch.id,
                batch.session_id,
                session.status AS attendance_session_status,
                session.scheduled_end_at AS attendance_session_scheduled_end_at,
                session.closed_at AS attendance_session_closed_at,
                session.cancelled_at AS attendance_session_cancelled_at,
                batch.mode,
                batch.status,
                batch.activated_at,
                batch.deactivated_at,
                batch.refresh_interval_seconds,
                batch.expires_at
            FROM attendance_session.qr_token_batches AS batch
            LEFT JOIN attendance_session.sessions AS session
                ON session.id = batch.session_id
            WHERE batch.id = $1
            """,
            qr_session_id,
        )

        if row is None:
            return None

        return QrBatchMetadata(
            id=row["id"],
            attendance_session_id=row["session_id"],
            attendance_session_status=row["attendance_session_status"],
            attendance_session_scheduled_end_at=row[
                "attendance_session_scheduled_end_at"
            ],
            attendance_session_closed_at=row["attendance_session_closed_at"],
            attendance_session_cancelled_at=row["attendance_session_cancelled_at"],
            mode=row["mode"],
            status=row["status"],
            activated_at=row["activated_at"],
            deactivated_at=row["deactivated_at"],
            refresh_interval_seconds=row["refresh_interval_seconds"],
            expires_at=row["expires_at"],
        )

    async def fetch_qr_verification_record(
        self,
        connection: asyncpg.Connection,
        qr_session_id: UUID,
    ) -> QrVerificationRecord | None:
        # Verification needs the QR batch, parent attendance session, and token
        # state in one read so the service can classify the scan safely.
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
