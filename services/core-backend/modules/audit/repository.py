import json
from typing import Any
from uuid import UUID

import asyncpg

SUCCESS_OUTCOME = "success"
FAILURE_OUTCOME = "failure"


async def write_audit_log(
    connection: asyncpg.Connection,
    *,
    actor_user_id: UUID,
    actor_type: str,
    action: str,
    entity_type: str,
    entity_id: UUID | None,
    outcome: str = SUCCESS_OUTCOME,
    old_values: dict[str, Any] | None = None,
    new_values: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
    failure_reason: str | None = None,
) -> None:
    """Writes one audit.audit_logs row.

    Callers pass already-redacted values — this function does not filter
    anything, so never pass tokens, passwords, or raw biometric data in
    old_values/new_values/metadata.
    """
    await connection.execute(
        """
        INSERT INTO audit.audit_logs (
            id, actor_user_id, actor_type, source_service, action,
            entity_type, entity_id, outcome, failure_reason,
            old_values, new_values, metadata, occurred_at
        )
        VALUES (
            gen_random_uuid(), $1, $2, 'core-backend', $3,
            $4, $5, $6, $7,
            $8::jsonb, $9::jsonb, $10::jsonb, now()
        )
        """,
        actor_user_id,
        actor_type,
        action,
        entity_type,
        entity_id,
        outcome,
        failure_reason,
        json.dumps(old_values) if old_values is not None else None,
        json.dumps(new_values) if new_values is not None else None,
        json.dumps(metadata) if metadata is not None else None,
    )
