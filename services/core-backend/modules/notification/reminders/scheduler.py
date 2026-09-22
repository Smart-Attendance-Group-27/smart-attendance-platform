import asyncio
import logging

import asyncpg

from modules.notification.producer.service import NotificationProducer

logger = logging.getLogger(__name__)


class UpcomingClassReminderScheduler:
    def __init__(
        self,
        *,
        pool: asyncpg.Pool,
        interval_seconds: float,
        lead_minutes: int,
        producer: NotificationProducer | None = None,
    ) -> None:
        self._pool = pool
        self._interval_seconds = interval_seconds
        self._lead_minutes = lead_minutes
        self._producer = producer or NotificationProducer()

    async def run(self, stop_event: asyncio.Event) -> None:
        logger.info("Upcoming class reminder scheduler started")
        try:
            while not stop_event.is_set():
                try:
                    created = await self.run_once()
                    if created:
                        logger.info(
                            "Upcoming class reminders queued",
                            extra={"reminders_created": created},
                        )
                except asyncio.CancelledError:
                    raise
                except Exception as error:
                    logger.error(
                        "Upcoming class reminder cycle failed",
                        extra={"reminder_error_type": type(error).__name__},
                    )
                try:
                    await asyncio.wait_for(
                        stop_event.wait(),
                        timeout=self._interval_seconds,
                    )
                except TimeoutError:
                    pass
        finally:
            logger.info("Upcoming class reminder scheduler stopped")

    async def run_once(self) -> int:
        async with self._pool.acquire() as connection:
            async with connection.transaction():
                return await self._producer.upcoming_class_reminders(
                    connection,
                    lead_minutes=self._lead_minutes,
                )


__all__ = ["UpcomingClassReminderScheduler"]
