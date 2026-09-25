from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

import asyncpg

from modules.notification.student_notifications.repository import (
    StudentNotificationRecord,
    StudentNotificationRepository,
)


@dataclass(frozen=True)
class StudentNotification:
    id: UUID
    title: str
    message: str
    type: str
    code: str
    created_at: datetime
    is_read: bool
    related_id: UUID | None
    related_entity_type: str | None


@dataclass(frozen=True)
class StudentNotificationPage:
    items: list[StudentNotification]
    next_offset: int | None
    unread_count: int


class StudentNotificationService:
    def __init__(
        self,
        repository: StudentNotificationRepository | None = None,
    ) -> None:
        self._repository = repository or StudentNotificationRepository()

    async def list_for_user(
        self,
        pool: asyncpg.Pool,
        user_id: UUID,
    ) -> list[StudentNotification]:
        async with pool.acquire() as connection:
            records = await self._repository.list_for_user(connection, user_id)

        return [_to_notification(record) for record in records]

    async def page_for_user(
        self, pool: asyncpg.Pool, user_id: UUID, *, limit: int, offset: int,
    ) -> StudentNotificationPage:
        async with pool.acquire() as connection:
            records = await self._repository.list_for_user(
                connection, user_id, limit=limit + 1, offset=offset,
            )
            unread_count = await self._repository.unread_count(connection, user_id)
        has_more = len(records) > limit
        return StudentNotificationPage(
            items=[_to_notification(record) for record in records[:limit]],
            next_offset=offset + limit if has_more else None,
            unread_count=unread_count,
        )

    async def unread_count(self, pool: asyncpg.Pool, user_id: UUID) -> int:
        async with pool.acquire() as connection:
            return await self._repository.unread_count(connection, user_id)

    async def mark_all_as_read(self, pool: asyncpg.Pool, user_id: UUID) -> int:
        async with pool.acquire() as connection:
            return await self._repository.mark_all_as_read(connection, user_id)

    async def mark_as_read(
        self,
        pool: asyncpg.Pool,
        *,
        user_id: UUID,
        notification_id: UUID,
    ) -> bool:
        async with pool.acquire() as connection:
            return await self._repository.mark_as_read(
                connection,
                user_id=user_id,
                notification_id=notification_id,
            )


def _to_notification(record: StudentNotificationRecord) -> StudentNotification:
    return StudentNotification(
        id=record.id,
        title=record.title or "Notification",
        message=record.body or "",
        type=_map_notification_type(record.notification_type),
        code=record.notification_type or "GENERAL",
        created_at=record.created_at,
        is_read=record.read_at is not None,
        related_id=record.related_entity_id,
        related_entity_type=record.related_entity_type,
    )


def _map_notification_type(value: str | None) -> str:
    if value in {"QR_REQUIRED", "QR_SESSION_ACTIVE"}:
        return "qr_session"
    if value in {
        "ATTENDANCE_SESSION_STARTED",
        "ATTENDANCE_SESSION_OPENED",
        "UPCOMING_CLASS",
        "UPCOMING_SESSION_REMINDER",
    }:
        return "attendance"
    if value in {"ATTENDANCE_RESULT"}:
        return "attendance_update"
    return "general"
