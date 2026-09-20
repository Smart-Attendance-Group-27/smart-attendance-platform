"""NotificationService — central notification orchestrator.

Responsibilities:
  1. Validate the notification type (exists, is active).
  2. Check the recipient's push preference (user pref → fall back to type default).
  3. Write a notification.notifications row.
  4. Find active device tokens for the recipient.
  5. Insert pending delivery_attempts rows.
  6. Fire push delivery as a background task (does NOT block the caller).
  7. Update delivery_attempts with the Expo result.
  8. Deactivate tokens that Expo reports as invalid.

Business services (e.g. LecturerSessionService) call `send_notification`.
They do not import ExpoPushProvider or touch delivery_attempts directly.
"""

import asyncio
import logging
from dataclasses import dataclass
from uuid import UUID, uuid4

import asyncpg

from modules.notification.device_tokens.repository import DeviceTokenRepository
from modules.notification.push.exception import (
    InactiveNotificationTypeError,
    NotificationTypeNotFoundError,
    PushDeliveryError,
)
from modules.notification.push.provider import PushMessage, PushProvider

logger = logging.getLogger(__name__)

DELIVERY_CHANNEL_PUSH = "push"
DELIVERY_STATUS_PENDING = "pending"
DELIVERY_STATUS_SENT = "sent"
DELIVERY_STATUS_FAILED = "failed"


@dataclass(frozen=True)
class _NotificationTypeRow:
    code: str
    default_push_enabled: bool
    default_in_app_enabled: bool
    is_active: bool


@dataclass(frozen=True)
class _PreferenceRow:
    push_enabled: bool


class NotificationService:
    """Orchestrates notification creation and push delivery.

    Inject a PushProvider implementation.  During tests pass a stub;
    in production pass an ExpoPushProvider instance.
    """

    def __init__(
        self,
        push_provider: PushProvider,
        device_token_repository: DeviceTokenRepository | None = None,
    ) -> None:
        self._push_provider = push_provider
        self._device_token_repo = device_token_repository or DeviceTokenRepository()

    async def send_notification(
        self,
        pool: asyncpg.Pool,
        *,
        recipient_user_id: UUID,
        notification_type: str,
        title: str,
        body: str,
        priority: str = "default",
        related_entity_type: str | None = None,
        related_entity_id: UUID | None = None,
        in_app_visible: bool = True,
        extra_data: dict | None = None,
    ) -> UUID:
        """Create a notification and schedule push delivery.

        Returns the notification_id immediately; push delivery runs in the
        background via asyncio.create_task so the calling HTTP handler is
        not blocked by Expo's network round-trip.

        One failed device does NOT prevent delivery to other devices.
        """
        async with pool.acquire() as connection:
            # 1. Validate notification type.
            ntype = await _fetch_notification_type(connection, notification_type)

            # 2. Resolve push preference for this user.
            push_enabled = await _resolve_push_preference(
                connection,
                user_id=recipient_user_id,
                notification_type=notification_type,
                default_push_enabled=ntype.default_push_enabled,
            )

            # 3. Insert notification row.
            notification_id = await _insert_notification(
                connection,
                notification_id=uuid4(),
                recipient_user_id=recipient_user_id,
                notification_type=notification_type,
                title=title,
                body=body,
                priority=priority,
                related_entity_type=related_entity_type,
                related_entity_id=related_entity_id,
                in_app_visible=in_app_visible,
            )

            if not push_enabled:
                logger.debug(
                    "Push disabled for user=%s type=%s — notification created "
                    "as in-app only.",
                    recipient_user_id,
                    notification_type,
                )
                return notification_id

            # 4. Find active device tokens.
            tokens = await self._device_token_repo.find_active_for_user(
                connection, recipient_user_id
            )

            if not tokens:
                logger.debug(
                    "No active device tokens for user=%s — skipping push.",
                    recipient_user_id,
                )
                return notification_id

            # 5. Insert one pending delivery_attempt per device.
            attempt_rows: list[tuple[UUID, UUID, str]] = []  # (attempt_id, token_id, expo_token)
            for token in tokens:
                attempt_id = await _insert_delivery_attempt(
                    connection,
                    notification_id=notification_id,
                    device_token_id=token.id,
                    channel=DELIVERY_CHANNEL_PUSH,
                )
                attempt_rows.append((attempt_id, token.id, token.expo_push_token))

        # 6. Fire push delivery as a background task (does not block caller).
        asyncio.create_task(
            self._deliver_push(
                pool=pool,
                notification_id=notification_id,
                title=title,
                body=body,
                priority=priority,
                extra_data=extra_data or {},
                attempt_rows=attempt_rows,
            )
        )

        return notification_id

    async def _deliver_push(
        self,
        *,
        pool: asyncpg.Pool,
        notification_id: UUID,
        title: str,
        body: str,
        priority: str,
        extra_data: dict,
        attempt_rows: list[tuple[UUID, UUID, str]],   # (attempt_id, token_id, expo_token)
    ) -> None:
        """Send push notifications and record results.

        Runs as an asyncio background task.  Failures for one device do not
        affect other devices.  Token invalidation is handled here.
        """
        messages = [
            PushMessage(
                to=expo_token,
                title=title,
                body=body,
                data={"notificationId": str(notification_id), **extra_data},
                priority=priority,
            )
            for _, _, expo_token in attempt_rows
        ]

        try:
            receipts = await self._push_provider.send_many(messages)
        except PushDeliveryError as exc:
            logger.error(
                "Push provider error for notification=%s: %s",
                notification_id,
                exc.message,
            )
            # Mark all attempts as failed — provider-level failure.
            async with pool.acquire() as connection:
                for attempt_id, _, _ in attempt_rows:
                    await _update_delivery_attempt(
                        connection,
                        attempt_id=attempt_id,
                        delivery_status=DELIVERY_STATUS_FAILED,
                        provider_message_id=None,
                        failure_reason=exc.message,
                    )
            return

        async with pool.acquire() as connection:
            for (attempt_id, token_id, _), receipt in zip(attempt_rows, receipts):
                if receipt.status == "ok":
                    await _update_delivery_attempt(
                        connection,
                        attempt_id=attempt_id,
                        delivery_status=DELIVERY_STATUS_SENT,
                        provider_message_id=receipt.provider_id,
                        failure_reason=None,
                    )
                else:
                    await _update_delivery_attempt(
                        connection,
                        attempt_id=attempt_id,
                        delivery_status=DELIVERY_STATUS_FAILED,
                        provider_message_id=None,
                        failure_reason=receipt.failure_reason,
                    )
                    if receipt.is_invalid_token:
                        logger.info(
                            "Deactivating invalid token token_id=%s for "
                            "notification=%s",
                            token_id,
                            notification_id,
                        )
                        device_token_repo = DeviceTokenRepository()
                        await device_token_repo.deactivate(connection, token_id)


# ---------------------------------------------------------------------------
# Private SQL helpers — keep SQL close to where it is used (project pattern)
# ---------------------------------------------------------------------------


async def _fetch_notification_type(
    connection: asyncpg.Connection,
    code: str,
) -> _NotificationTypeRow:
    row = await connection.fetchrow(
        """
        SELECT code, default_push_enabled, default_in_app_enabled, is_active
        FROM notification.notification_types
        WHERE code = $1
        """,
        code,
    )
    if row is None:
        raise NotificationTypeNotFoundError(code)
    if not row["is_active"]:
        raise InactiveNotificationTypeError(code)
    return _NotificationTypeRow(
        code=row["code"],
        default_push_enabled=bool(row["default_push_enabled"]),
        default_in_app_enabled=bool(row["default_in_app_enabled"]),
        is_active=bool(row["is_active"]),
    )


async def _resolve_push_preference(
    connection: asyncpg.Connection,
    *,
    user_id: UUID,
    notification_type: str,
    default_push_enabled: bool,
) -> bool:
    """Return whether push is enabled for this user + type combination.

    Uses the explicit user preference when one exists; falls back to the
    type's default_push_enabled value otherwise.
    """
    row = await connection.fetchrow(
        """
        SELECT push_enabled
        FROM notification.notification_preferences
        WHERE user_id           = $1
          AND notification_type = $2
        """,
        user_id,
        notification_type,
    )
    if row is None:
        return default_push_enabled
    return bool(row["push_enabled"])


async def _insert_notification(
    connection: asyncpg.Connection,
    *,
    notification_id: UUID,
    recipient_user_id: UUID,
    notification_type: str,
    title: str,
    body: str,
    priority: str,
    related_entity_type: str | None,
    related_entity_id: UUID | None,
    in_app_visible: bool,
) -> UUID:
    await connection.execute(
        """
        INSERT INTO notification.notifications (
            id, recipient_user_id, notification_type,
            title, body, priority,
            related_entity_type, related_entity_id,
            in_app_visible, created_at
        )
        VALUES (
            $1, $2, $3,
            $4, $5, $6,
            $7, $8,
            $9, now()
        )
        """,
        notification_id,
        recipient_user_id,
        notification_type,
        title,
        body,
        priority,
        related_entity_type,
        related_entity_id,
        in_app_visible,
    )
    return notification_id


async def _insert_delivery_attempt(
    connection: asyncpg.Connection,
    *,
    notification_id: UUID,
    device_token_id: UUID,
    channel: str,
) -> UUID:
    attempt_id = uuid4()
    await connection.execute(
        """
        INSERT INTO notification.delivery_attempts (
            id, notification_id, channel, device_token_id,
            attempt_number, delivery_status, queued_at
        )
        VALUES (
            $1, $2, $3, $4,
            1, $5, now()
        )
        """,
        attempt_id,
        notification_id,
        channel,
        device_token_id,
        DELIVERY_STATUS_PENDING,
    )
    return attempt_id


async def _update_delivery_attempt(
    connection: asyncpg.Connection,
    *,
    attempt_id: UUID,
    delivery_status: str,
    provider_message_id: str | None,
    failure_reason: str | None,
) -> None:
    await connection.execute(
        """
        UPDATE notification.delivery_attempts
        SET delivery_status      = $2,
            provider_message_id  = $3,
            failure_reason       = $4,
            attempted_at         = now(),
            completed_at         = now()
        WHERE id = $1
        """,
        attempt_id,
        delivery_status,
        provider_message_id,
        failure_reason,
    )
