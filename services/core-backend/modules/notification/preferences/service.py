from uuid import UUID

import asyncpg

from modules.notification.preferences.repository import (
    NotificationPreferenceRecord,
    NotificationPreferencesRepository,
)
from modules.notification.preferences.schemas import NotificationPreferenceUpdate


class InvalidNotificationPreferenceError(ValueError):
    def __init__(self, type_code: str) -> None:
        super().__init__(type_code)
        self.type_code = type_code


class NotificationPreferencesService:
    def __init__(
        self,
        repository: NotificationPreferencesRepository | None = None,
    ) -> None:
        self._repository = repository or NotificationPreferencesRepository()

    async def list_for_user(
        self,
        pool: asyncpg.Pool,
        user_id: UUID,
    ) -> list[NotificationPreferenceRecord]:
        async with pool.acquire() as connection:
            return await self._repository.list_effective(connection, user_id)

    async def update_for_user(
        self,
        pool: asyncpg.Pool,
        *,
        user_id: UUID,
        updates: list[NotificationPreferenceUpdate],
    ) -> list[NotificationPreferenceRecord]:
        type_codes = [update.type_code for update in updates]
        if len(type_codes) != len(set(type_codes)):
            raise InvalidNotificationPreferenceError("duplicate type code")

        async with pool.acquire() as connection:
            async with connection.transaction():
                for update in updates:
                    saved = await self._repository.upsert(
                        connection,
                        user_id=user_id,
                        type_code=update.type_code,
                        in_app_enabled=update.in_app_enabled,
                        push_enabled=update.push_enabled,
                    )
                    if not saved:
                        raise InvalidNotificationPreferenceError(update.type_code)
                return await self._repository.list_effective(connection, user_id)


__all__ = [
    "InvalidNotificationPreferenceError",
    "NotificationPreferencesService",
]
