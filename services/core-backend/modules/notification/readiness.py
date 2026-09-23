from dataclasses import dataclass

import asyncpg


@dataclass(frozen=True)
class NotificationSchemaReadiness:
    push_worker_ready: bool
    reminder_scheduler_ready: bool


async def check_notification_schema_readiness(
    pool: asyncpg.Pool,
) -> NotificationSchemaReadiness:
    async with pool.acquire() as connection:
        async with connection.transaction(readonly=True):
            row = await connection.fetchrow(
                """
                SELECT
                    EXISTS (
                        SELECT 1
                        FROM information_schema.columns
                        WHERE table_schema = 'notification'
                          AND table_name = 'delivery_attempts'
                          AND column_name = 'next_attempt_at'
                    ) AS push_worker_ready,
                    EXISTS (
                        SELECT 1
                        FROM pg_indexes
                        WHERE schemaname = 'notification'
                          AND indexname = 'uq_notifications_upcoming_class_session_user'
                    ) AS reminder_scheduler_ready
                """,
            )
    return NotificationSchemaReadiness(
        push_worker_ready=bool(row["push_worker_ready"]),
        reminder_scheduler_ready=bool(row["reminder_scheduler_ready"]),
    )


__all__ = ["NotificationSchemaReadiness", "check_notification_schema_readiness"]
