from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

import asyncpg

from modules.contracts.attendance_policy import AttendancePolicy


@dataclass(frozen=True, slots=True)
class PolicySnapshot:
    id: UUID
    check_in_window_minutes: int
    late_threshold_minutes: int
    qr_default_validity_minutes: int
    face_confidence_threshold_percent: int
    updated_at: datetime
    updated_by_name: str | None


class AttendancePolicyRepository:
    """The I-04 provider and the write store for C17."""

    async def get_active(
        self, connection: asyncpg.Connection,
    ) -> AttendancePolicy | None:
        row = await connection.fetchrow(
            """
            SELECT check_in_window_minutes, late_threshold_minutes,
                   qr_default_validity_minutes
            FROM academic.attendance_policies
            WHERE is_active
            """,
        )
        return None if row is None else AttendancePolicy(
            check_in_window_minutes=row["check_in_window_minutes"],
            late_threshold_minutes=row["late_threshold_minutes"],
            qr_default_validity_minutes=row["qr_default_validity_minutes"],
        )

    async def get_current(self, connection: asyncpg.Connection) -> PolicySnapshot | None:
        row = await connection.fetchrow(
            """
            SELECT policy.id, policy.check_in_window_minutes,
                   policy.late_threshold_minutes, policy.qr_default_validity_minutes,
                   policy.effective_from AS updated_at,
                   NULLIF(TRIM(CONCAT_WS(' ', administrator.first_name,
                       NULLIF(administrator.middle_name, ''), administrator.last_name)), '')
                       AS updated_by_name,
                   face.similarity_threshold
            FROM academic.attendance_policies AS policy
            LEFT JOIN academic.administrator_profiles AS administrator
                ON administrator.user_id = policy.configured_by
            LEFT JOIN LATERAL (
                SELECT similarity_threshold
                FROM face_verification.verification_configs
                ORDER BY is_active DESC, effective_from DESC, created_at DESC, id DESC
                LIMIT 1
            ) AS face ON true
            WHERE policy.is_active
            """,
        )
        if row is None:
            return None
        threshold = row["similarity_threshold"]
        return PolicySnapshot(
            id=row["id"],
            check_in_window_minutes=row["check_in_window_minutes"],
            late_threshold_minutes=row["late_threshold_minutes"],
            qr_default_validity_minutes=row["qr_default_validity_minutes"],
            face_confidence_threshold_percent=(
                int((Decimal(str(threshold)) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
                if threshold is not None else 75
            ),
            updated_at=row["updated_at"],
            updated_by_name=row["updated_by_name"],
        )

    async def lock_for_replace(self, connection: asyncpg.Connection) -> None:
        await connection.execute(
            "SELECT pg_advisory_xact_lock(hashtext('academic.attendance_policies'))",
        )

    async def replace_active(
        self,
        connection: asyncpg.Connection,
        *,
        actor_user_id: UUID,
        check_in_window_minutes: int,
        late_threshold_minutes: int,
        qr_default_validity_minutes: int,
        face_confidence_threshold_percent: int,
    ) -> UUID:
        await connection.execute(
            "UPDATE academic.attendance_policies SET is_active = false WHERE is_active",
        )
        policy_id = await connection.fetchval(
            """
            INSERT INTO academic.attendance_policies (
                check_in_window_minutes, late_threshold_minutes,
                qr_default_validity_minutes, is_active, configured_by
            ) VALUES ($1, $2, $3, true, $4)
            RETURNING id
            """,
            check_in_window_minutes, late_threshold_minutes,
            qr_default_validity_minutes, actor_user_id,
        )
        await connection.execute(
            "UPDATE face_verification.verification_configs "
            "SET is_active = false WHERE is_active",
        )
        await connection.execute(
            """
            INSERT INTO face_verification.verification_configs (
                similarity_threshold, is_active, configured_by
            ) VALUES ($1, true, $2)
            """,
            Decimal(face_confidence_threshold_percent) / 100, actor_user_id,
        )
        return policy_id
