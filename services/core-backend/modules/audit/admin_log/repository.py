import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

import asyncpg

DEFAULT_LIST_LIMIT = 200
MAX_LIST_LIMIT = 500


@dataclass(frozen=True)
class AuditLogRecord:
    id: UUID
    occurred_at: datetime
    actor_user_id: UUID | None
    actor_type: str | None
    actor_name: str
    action: str
    entity_type: str
    entity_id: UUID | None
    outcome: str | None
    failure_reason: str | None
    old_values: dict[str, Any] | None = None
    new_values: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None
    # Filled when the entity is an attendance session, so the log can name it.
    session_course_code: str | None = None
    session_scheduled_start_at: datetime | None = None


def _json_object(value: object) -> dict[str, Any] | None:
    # asyncpg returns jsonb as text unless a codec is registered.
    if value is None:
        return None
    if isinstance(value, str):
        value = json.loads(value)
    return value if isinstance(value, dict) else None


class AuditLogRepository:
    async def list_audit_logs(
        self,
        connection: asyncpg.Connection,
        *,
        limit: int = DEFAULT_LIST_LIMIT,
    ) -> list[AuditLogRecord]:
        bounded_limit = min(max(limit, 1), MAX_LIST_LIMIT)
        rows = await connection.fetch(
            """
            SELECT
                log.id,
                log.occurred_at,
                log.actor_user_id,
                log.actor_type,
                COALESCE(
                    NULLIF(TRIM(CONCAT_WS(
                        ' ', admin_p.first_name, NULLIF(admin_p.middle_name, ''), admin_p.last_name
                    )), ''),
                    NULLIF(TRIM(CONCAT_WS(
                        ' ', lecturer_p.first_name, NULLIF(lecturer_p.middle_name, ''), lecturer_p.last_name
                    )), ''),
                    NULLIF(TRIM(CONCAT_WS(
                        ' ', student_p.first_name, NULLIF(student_p.middle_name, ''), student_p.last_name
                    )), ''),
                    app_user.email,
                    'System'
                ) AS actor_name,
                log.action,
                log.entity_type,
                log.entity_id,
                log.outcome,
                log.failure_reason,
                log.old_values,
                log.new_values,
                log.metadata,
                course.course_code AS session_course_code,
                session.scheduled_start_at AS session_scheduled_start_at
            FROM audit.audit_logs AS log
            LEFT JOIN identity.users AS app_user
                ON app_user.id = log.actor_user_id
            LEFT JOIN academic.administrator_profiles AS admin_p
                ON admin_p.user_id = log.actor_user_id
            LEFT JOIN academic.lecturer_profiles AS lecturer_p
                ON lecturer_p.user_id = log.actor_user_id
            LEFT JOIN academic.student_profiles AS student_p
                ON student_p.user_id = log.actor_user_id
            LEFT JOIN attendance_session.sessions AS session
                ON log.entity_type = 'attendance_session' AND session.id = log.entity_id
            LEFT JOIN academic.course_offerings AS offering
                ON offering.id = session.course_offering_id
            LEFT JOIN academic.courses AS course
                ON course.id = offering.course_id
            ORDER BY log.occurred_at DESC
            LIMIT $1
            """,
            bounded_limit,
        )
        return [
            AuditLogRecord(
                id=row["id"],
                occurred_at=row["occurred_at"],
                actor_user_id=row["actor_user_id"],
                actor_type=row["actor_type"],
                actor_name=row["actor_name"],
                action=row["action"],
                entity_type=row["entity_type"],
                entity_id=row["entity_id"],
                outcome=row["outcome"],
                failure_reason=row["failure_reason"],
                old_values=_json_object(row["old_values"]),
                new_values=_json_object(row["new_values"]),
                metadata=_json_object(row["metadata"]),
                session_course_code=row["session_course_code"],
                session_scheduled_start_at=row["session_scheduled_start_at"],
            )
            for row in rows
        ]
