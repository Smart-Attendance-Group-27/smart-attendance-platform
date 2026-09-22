import asyncio
import logging
from dataclasses import dataclass

from modules.notification.push.exception import PushDeliveryError
from modules.notification.push.provider import PushMessage, PushProvider
from modules.notification.push.repository import (
    ClaimedDelivery,
    PushDeliveryRepository,
    SentDelivery,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PushWorkerConfig:
    batch_size: int = 100
    receipt_batch_size: int = 1000
    poll_interval_seconds: float = 2.0
    receipt_delay_seconds: float = 15.0
    lease_timeout_seconds: float = 60.0
    max_attempts: int = 5
    retry_base_seconds: float = 5.0
    retry_max_seconds: float = 300.0


@dataclass
class PushWorkerStats:
    claimed: int = 0
    tickets_persisted: int = 0
    delivered: int = 0
    retried: int = 0
    failed: int = 0
    tokens_deactivated: int = 0


def retry_delay_seconds(
    attempt_number: int,
    *,
    base_seconds: float,
    max_seconds: float,
) -> float:
    """Return capped exponential backoff after a failed numbered attempt."""
    exponent = max(attempt_number - 1, 0)
    return min(base_seconds * (2**exponent), max_seconds)


class PushDeliveryWorker:
    def __init__(
        self,
        *,
        repository: PushDeliveryRepository,
        provider: PushProvider,
        config: PushWorkerConfig,
    ) -> None:
        self._repository = repository
        self._provider = provider
        self._config = config

    async def run(self, stop_event: asyncio.Event) -> None:
        logger.info("Push delivery worker started")
        try:
            while not stop_event.is_set():
                try:
                    stats = await self.run_once()
                    if any(vars(stats).values()):
                        logger.info(
                            "Push delivery cycle complete",
                            extra={
                                "push_claimed": stats.claimed,
                                "push_tickets_persisted": stats.tickets_persisted,
                                "push_delivered": stats.delivered,
                                "push_retried": stats.retried,
                                "push_failed": stats.failed,
                                "push_tokens_deactivated": stats.tokens_deactivated,
                            },
                        )
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    # Do not interpolate exception text: provider failures can
                    # contain request data, including a push token.
                    logger.error(
                        "Push delivery cycle failed",
                        extra={"push_error_type": type(exc).__name__},
                    )

                try:
                    await asyncio.wait_for(
                        stop_event.wait(),
                        timeout=self._config.poll_interval_seconds,
                    )
                except TimeoutError:
                    pass
        finally:
            logger.info("Push delivery worker stopped")

    async def run_once(self) -> PushWorkerStats:
        stats = PushWorkerStats()
        await self._send_ready(stats)
        await self._poll_receipts(stats)
        return stats

    async def _send_ready(self, stats: PushWorkerStats) -> None:
        attempts = await self._repository.claim_ready(
            batch_size=self._config.batch_size,
            lease_timeout_seconds=self._config.lease_timeout_seconds,
        )
        stats.claimed = len(attempts)
        if not attempts:
            return

        active_attempts: list[ClaimedDelivery] = []
        for attempt in attempts:
            if attempt.token_is_active:
                active_attempts.append(attempt)
            else:
                await self._repository.mark_failed(
                    attempt.id,
                    failure_reason="Device token is inactive",
                )
                stats.failed += 1

        if not active_attempts:
            return

        messages = [self._message_for(attempt) for attempt in active_attempts]
        try:
            tickets = await self._provider.send_many(messages)
        except PushDeliveryError as exc:
            for attempt in active_attempts:
                await self._retry_or_fail(attempt, exc.message, stats)
            return

        for index, attempt in enumerate(active_attempts):
            if index >= len(tickets):
                await self._retry_or_fail(
                    attempt,
                    "Expo returned no ticket for the message",
                    stats,
                )
                continue

            ticket = tickets[index]
            if ticket.status == "ok" and ticket.provider_id:
                await self._repository.mark_sent(attempt.id, ticket.provider_id)
                stats.tickets_persisted += 1
                continue

            reason = ticket.failure_reason or "Expo rejected the message"
            if ticket.is_invalid_token:
                await self._repository.mark_failed(
                    attempt.id,
                    failure_reason=reason,
                )
                await self._repository.deactivate_token(attempt.device_token_id)
                stats.failed += 1
                stats.tokens_deactivated += 1
            else:
                await self._retry_or_fail(attempt, reason, stats)

    async def _poll_receipts(self, stats: PushWorkerStats) -> None:
        attempts = await self._repository.claim_sent_for_receipts(
            batch_size=self._config.receipt_batch_size,
            receipt_delay_seconds=self._config.receipt_delay_seconds,
        )
        if not attempts:
            return

        try:
            receipts = await self._provider.fetch_receipts(
                [attempt.provider_message_id for attempt in attempts]
            )
        except PushDeliveryError:
            # The receipt rows remain sent and become eligible again after the
            # receipt delay. This does not consume a delivery attempt.
            logger.warning(
                "Expo receipt poll failed",
                extra={"push_receipt_count": len(attempts)},
            )
            return

        for attempt in attempts:
            receipt = receipts.get(attempt.provider_message_id)
            if receipt is None:
                continue
            if receipt.status == "ok":
                await self._repository.mark_delivered(attempt.id)
                stats.delivered += 1
                continue

            reason = receipt.failure_reason or "Expo reported delivery failure"
            if receipt.is_invalid_token:
                await self._repository.mark_failed(
                    attempt.id,
                    failure_reason=reason,
                )
                await self._repository.deactivate_token(attempt.device_token_id)
                stats.failed += 1
                stats.tokens_deactivated += 1
            else:
                await self._retry_or_fail(attempt, reason, stats)

    async def _retry_or_fail(
        self,
        attempt: ClaimedDelivery | SentDelivery,
        reason: str,
        stats: PushWorkerStats,
    ) -> None:
        if attempt.attempt_number >= self._config.max_attempts:
            await self._repository.mark_failed(
                attempt.id,
                failure_reason=reason,
            )
            stats.failed += 1
            return

        delay = retry_delay_seconds(
            attempt.attempt_number,
            base_seconds=self._config.retry_base_seconds,
            max_seconds=self._config.retry_max_seconds,
        )
        await self._repository.schedule_retry(
            attempt.id,
            failure_reason=reason,
            delay_seconds=delay,
        )
        stats.retried += 1

    @staticmethod
    def _message_for(attempt: ClaimedDelivery) -> PushMessage:
        data = {"notificationId": str(attempt.notification_id)}
        if attempt.related_entity_type:
            data["relatedEntityType"] = attempt.related_entity_type
        if attempt.related_entity_id:
            data["relatedEntityId"] = str(attempt.related_entity_id)
        return PushMessage(
            to=attempt.expo_push_token,
            title=attempt.title,
            body=attempt.body,
            data=data,
            priority=attempt.priority,
        )


__all__ = [
    "PushDeliveryWorker",
    "PushWorkerConfig",
    "PushWorkerStats",
    "retry_delay_seconds",
]
