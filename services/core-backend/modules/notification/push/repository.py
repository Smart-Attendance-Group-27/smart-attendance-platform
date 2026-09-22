from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID

import asyncpg

from modules.notification.push.state import (
    DELIVERY_STATUS_DELIVERED,
    DELIVERY_STATUS_FAILED,
    DELIVERY_STATUS_IN_FLIGHT,
    DELIVERY_STATUS_QUEUED,
    DELIVERY_STATUS_SENT,
)


@dataclass(frozen=True)
class ClaimedDelivery:
    id: UUID
    notification_id: UUID
    device_token_id: UUID
    expo_push_token: str
    attempt_number: int
    title: str
    body: str
    priority: str
    related_entity_type: str | None
    related_entity_id: UUID | None
    token_is_active: bool


@dataclass(frozen=True)
class SentDelivery:
    id: UUID
    device_token_id: UUID
    provider_message_id: str
    attempt_number: int


class PushDeliveryRepository:
    """Owns short push-queue transactions.

    Claims are committed before the worker calls Expo. This keeps PostgreSQL
    locks away from network I/O while the ``in_flight`` lease prevents another
    worker from selecting the same attempt.
    """

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def claim_ready(
        self,
        *,
        batch_size: int,
        lease_timeout_seconds: float,
    ) -> list[ClaimedDelivery]:
        async with self._pool.acquire() as connection:
            async with connection.transaction():
                rows = await connection.fetch(
                    """
                    SELECT
                        da.id,
                        da.notification_id,
                        da.device_token_id,
                        COALESCE(da.attempt_number, 0) AS attempt_number,
                        dt.expo_push_token,
                        dt.is_active AS token_is_active,
                        n.title,
                        n.body,
                        n.priority,
                        n.related_entity_type,
                        n.related_entity_id
                    FROM notification.delivery_attempts da
                    JOIN notification.notifications n
                      ON n.id = da.notification_id
                    JOIN notification.device_tokens dt
                      ON dt.id = da.device_token_id
                    WHERE da.channel = 'push'
                      AND (
                        (
                          da.delivery_status = $1
                          AND COALESCE(da.next_attempt_at, da.queued_at) <= now()
                        )
                        OR (
                          da.delivery_status = $2
                          AND da.attempted_at <= now() - $3::interval
                        )
                      )
                    ORDER BY COALESCE(da.next_attempt_at, da.queued_at), da.id
                    FOR UPDATE OF da SKIP LOCKED
                    LIMIT $4
                    """,
                    DELIVERY_STATUS_QUEUED,
                    DELIVERY_STATUS_IN_FLIGHT,
                    timedelta(seconds=lease_timeout_seconds),
                    batch_size,
                )
                if not rows:
                    return []

                attempt_ids = [row["id"] for row in rows]
                await connection.execute(
                    """
                    UPDATE notification.delivery_attempts
                    SET delivery_status = $2,
                        attempt_number = COALESCE(attempt_number, 0) + 1,
                        attempted_at = now(),
                        completed_at = NULL,
                        next_attempt_at = NULL,
                        failure_reason = NULL
                    WHERE id = ANY($1::uuid[])
                    """,
                    attempt_ids,
                    DELIVERY_STATUS_IN_FLIGHT,
                )

        return [
            ClaimedDelivery(
                id=row["id"],
                notification_id=row["notification_id"],
                device_token_id=row["device_token_id"],
                expo_push_token=row["expo_push_token"],
                attempt_number=int(row["attempt_number"]) + 1,
                title=row["title"],
                body=row["body"],
                priority=row["priority"] or "default",
                related_entity_type=row["related_entity_type"],
                related_entity_id=row["related_entity_id"],
                token_is_active=bool(row["token_is_active"]),
            )
            for row in rows
        ]

    async def claim_sent_for_receipts(
        self,
        *,
        batch_size: int,
        receipt_delay_seconds: float,
    ) -> list[SentDelivery]:
        async with self._pool.acquire() as connection:
            async with connection.transaction():
                rows = await connection.fetch(
                    """
                    SELECT id, device_token_id, provider_message_id, attempt_number
                    FROM notification.delivery_attempts
                    WHERE delivery_status = $1
                      AND provider_message_id IS NOT NULL
                      AND attempted_at <= now() - $2::interval
                    ORDER BY attempted_at, id
                    FOR UPDATE SKIP LOCKED
                    LIMIT $3
                    """,
                    DELIVERY_STATUS_SENT,
                    timedelta(seconds=receipt_delay_seconds),
                    batch_size,
                )
                if not rows:
                    return []

                await connection.execute(
                    """
                    UPDATE notification.delivery_attempts
                    SET attempted_at = now()
                    WHERE id = ANY($1::uuid[])
                    """,
                    [row["id"] for row in rows],
                )

        return [
            SentDelivery(
                id=row["id"],
                device_token_id=row["device_token_id"],
                provider_message_id=row["provider_message_id"],
                attempt_number=int(row["attempt_number"]),
            )
            for row in rows
        ]

    async def mark_sent(self, attempt_id: UUID, provider_message_id: str) -> None:
        await self._execute(
            """
            UPDATE notification.delivery_attempts
            SET delivery_status = $2,
                provider_message_id = $3,
                failure_reason = NULL,
                attempted_at = now(),
                completed_at = NULL,
                next_attempt_at = NULL
            WHERE id = $1
            """,
            attempt_id,
            DELIVERY_STATUS_SENT,
            provider_message_id,
        )

    async def mark_delivered(self, attempt_id: UUID) -> None:
        await self._execute(
            """
            UPDATE notification.delivery_attempts
            SET delivery_status = $2,
                failure_reason = NULL,
                completed_at = now(),
                next_attempt_at = NULL
            WHERE id = $1
            """,
            attempt_id,
            DELIVERY_STATUS_DELIVERED,
        )

    async def schedule_retry(
        self,
        attempt_id: UUID,
        *,
        failure_reason: str,
        delay_seconds: float,
    ) -> None:
        await self._execute(
            """
            UPDATE notification.delivery_attempts
            SET delivery_status = $2,
                provider_message_id = NULL,
                failure_reason = left($3, 255),
                completed_at = NULL,
                next_attempt_at = now() + $4::interval
            WHERE id = $1
            """,
            attempt_id,
            DELIVERY_STATUS_QUEUED,
            failure_reason,
            timedelta(seconds=delay_seconds),
        )

    async def mark_failed(self, attempt_id: UUID, *, failure_reason: str) -> None:
        await self._execute(
            """
            UPDATE notification.delivery_attempts
            SET delivery_status = $2,
                failure_reason = left($3, 255),
                completed_at = now(),
                next_attempt_at = NULL
            WHERE id = $1
            """,
            attempt_id,
            DELIVERY_STATUS_FAILED,
            failure_reason,
        )

    async def deactivate_token(self, token_id: UUID) -> None:
        await self._execute(
            """
            UPDATE notification.device_tokens
            SET is_active = false,
                revoked_at = COALESCE(revoked_at, now())
            WHERE id = $1
            """,
            token_id,
        )

    async def _execute(self, query: str, *args: object) -> None:
        async with self._pool.acquire() as connection:
            await connection.execute(query, *args)


__all__ = ["ClaimedDelivery", "PushDeliveryRepository", "SentDelivery"]
