from dataclasses import dataclass
from uuid import UUID

import asyncpg

from modules.notification.producer.repository import NotificationProducerRepository


@dataclass(frozen=True)
class NotificationPreferenceRecord:
    type_code: str
    description: str
    in_app_enabled: bool
    push_enabled: bool
    is_customized: bool


class NotificationPreferencesRepository:
    def __init__(
        self,
        producer_repository: NotificationProducerRepository | None = None,
    ) -> None:
        self._producer_repository = producer_repository or NotificationProducerRepository()

    async def list_effective(
        self,
        connection: asyncpg.Connection,
        user_id: UUID,
    ) -> list[NotificationPreferenceRecord]:
        rows = await connection.fetch(
            """
            SELECT
                nt.code,
                nt.description,
                np.user_id IS NOT NULL AS is_customized
            FROM notification.notification_types nt
            LEFT JOIN notification.notification_preferences np
              ON np.notification_type = nt.code
             AND np.user_id = $1
            WHERE nt.is_active IS TRUE
              AND nt.user_configurable IS TRUE
            ORDER BY nt.code
            """,
            user_id,
        )
        records: list[NotificationPreferenceRecord] = []
        for row in rows:
            effective = await self._producer_repository.fetch_user_preferences(
                connection,
                [user_id],
                row["code"],
            )
            in_app_enabled, push_enabled = effective[user_id]
            records.append(
                NotificationPreferenceRecord(
                    type_code=row["code"],
                    description=row["description"] or row["code"],
                    in_app_enabled=in_app_enabled,
                    push_enabled=push_enabled,
                    is_customized=bool(row["is_customized"]),
                )
            )
        return records

    async def upsert(
        self,
        connection: asyncpg.Connection,
        *,
        user_id: UUID,
        type_code: str,
        in_app_enabled: bool,
        push_enabled: bool,
    ) -> bool:
        row = await connection.fetchrow(
            """
            INSERT INTO notification.notification_preferences (
                user_id,
                notification_type,
                in_app_enabled,
                push_enabled,
                email_enabled,
                updated_at
            )
            SELECT
                $1,
                nt.code,
                $3,
                $4,
                COALESCE(nt.default_email_enabled, false),
                now()
            FROM notification.notification_types nt
            WHERE nt.code = $2
              AND nt.is_active IS TRUE
              AND nt.user_configurable IS TRUE
            ON CONFLICT (user_id, notification_type) DO UPDATE
            SET in_app_enabled = EXCLUDED.in_app_enabled,
                push_enabled = EXCLUDED.push_enabled,
                updated_at = now()
            RETURNING notification_type
            """,
            user_id,
            type_code,
            in_app_enabled,
            push_enabled,
        )
        return row is not None


__all__ = ["NotificationPreferenceRecord", "NotificationPreferencesRepository"]
