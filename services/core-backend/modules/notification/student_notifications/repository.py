from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

import asyncpg


@dataclass(frozen=True)
class StudentNotificationRecord:
    id: UUID
    notification_type: str | None
    title: str | None
    body: str | None
    related_entity_type: str | None
    related_entity_id: UUID | None
    read_at: datetime | None
    created_at: datetime


class StudentNotificationRepository:
    async def list_for_user(
        self,
        connection: asyncpg.Connection,
        user_id: UUID,
        *,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[StudentNotificationRecord]:
        rows = await connection.fetch(
            """
            SELECT
                id,
                notification_type,
                title,
                body,
                related_entity_type,
                related_entity_id,
                read_at,
                created_at
            FROM notification.notifications
            WHERE recipient_user_id = $1
              AND in_app_visible IS TRUE
              AND (expires_at IS NULL OR expires_at > now())
              AND (scheduled_for IS NULL OR scheduled_for <= now())
            ORDER BY created_at DESC, id ASC
            LIMIT $2 OFFSET $3
            """,
            user_id,
            limit,
            offset,
        )

        return [
            StudentNotificationRecord(
                id=row["id"],
                notification_type=row["notification_type"],
                title=row["title"],
                body=row["body"],
                related_entity_type=row["related_entity_type"],
                related_entity_id=row["related_entity_id"],
                read_at=row["read_at"],
                created_at=row["created_at"],
            )
            for row in rows
        ]

    async def mark_as_read(
        self,
        connection: asyncpg.Connection,
        *,
        user_id: UUID,
        notification_id: UUID,
    ) -> bool:
        result = await connection.execute(
            """
            UPDATE notification.notifications
            SET read_at = COALESCE(read_at, now())
            WHERE id = $1
              AND recipient_user_id = $2
              AND in_app_visible IS TRUE
            """,
            notification_id,
            user_id,
        )
        return result == "UPDATE 1"

    async def unread_count(self, connection: asyncpg.Connection, user_id: UUID) -> int:
        return int(await connection.fetchval(
            """
            SELECT count(*) FROM notification.notifications
            WHERE recipient_user_id = $1
              AND in_app_visible IS TRUE
              AND read_at IS NULL
              AND (expires_at IS NULL OR expires_at > now())
              AND (scheduled_for IS NULL OR scheduled_for <= now())
            """,
            user_id,
        ))

    async def mark_all_as_read(self, connection: asyncpg.Connection, user_id: UUID) -> int:
        result = await connection.execute(
            """
            UPDATE notification.notifications SET read_at = now()
            WHERE recipient_user_id = $1
              AND in_app_visible IS TRUE
              AND read_at IS NULL
              AND (expires_at IS NULL OR expires_at > now())
              AND (scheduled_for IS NULL OR scheduled_for <= now())
            """,
            user_id,
        )
        return int(result.split()[-1])
