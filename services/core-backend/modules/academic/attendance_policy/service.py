from uuid import UUID

import asyncpg

from modules.academic.attendance_policy.repository import (
    AttendancePolicyRepository,
    PolicySnapshot,
)
from modules.academic.attendance_policy.schemas import PolicyWriteRequest
from modules.audit.repository import write_audit_log


class PolicyUnavailableError(Exception):
    """The attendance policy migration has not seeded an active policy."""


class AttendancePolicyService:
    def __init__(self, repository: AttendancePolicyRepository | None = None) -> None:
        self._repository = repository or AttendancePolicyRepository()

    async def get_current(self, pool: asyncpg.Pool) -> PolicySnapshot:
        async with pool.acquire() as connection:
            policy = await self._repository.get_current(connection)
        if policy is None:
            raise PolicyUnavailableError()
        return policy

    async def replace_active(
        self,
        pool: asyncpg.Pool,
        actor_user_id: UUID,
        body: PolicyWriteRequest,
    ) -> PolicySnapshot:
        async with pool.acquire() as connection, connection.transaction():
            await self._repository.lock_for_replace(connection)
            before = await self._repository.get_current(connection)
            policy_id = await self._repository.replace_active(
                connection,
                actor_user_id=actor_user_id,
                check_in_window_minutes=body.check_in_window_minutes,
                late_threshold_minutes=body.late_threshold_minutes,
                qr_default_validity_minutes=body.qr_default_validity_minutes,
                face_confidence_threshold_percent=body.face_confidence_threshold_percent,
            )
            after = await self._repository.get_current(connection)
            assert after is not None
            await write_audit_log(
                connection,
                actor_user_id=actor_user_id,
                actor_type="administrator",
                action="attendance_policy.update",
                entity_type="attendance_policy",
                entity_id=policy_id,
                old_values=_values(before) if before else None,
                new_values=_values(after),
            )
            return after


def _values(policy: PolicySnapshot) -> dict[str, int]:
    return {
        "checkInWindowMinutes": policy.check_in_window_minutes,
        "lateThresholdMinutes": policy.late_threshold_minutes,
        "qrDefaultValidityMinutes": policy.qr_default_validity_minutes,
        "faceConfidenceThresholdPercent": policy.face_confidence_threshold_percent,
    }
