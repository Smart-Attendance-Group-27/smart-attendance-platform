import asyncio
import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import asyncpg

from modules.attendance_sessions.lecturer_sessions.repository import LecturerSessionRepository
from modules.attendance_sessions.lecturer_sessions.service import LecturerSessionService

logger = logging.getLogger(__name__)

# Upper bound per scan so one cycle cannot hold the pool for long; anything
# left over is picked up by the next cycle.
MAX_SESSIONS_PER_SCAN = 50


class SessionAutoCloseScheduler:
    """Closes active sessions still open after their scheduled end plus grace.

    Every scan looks for overdue sessions from scratch, so a session that
    should have closed while the server was down is closed on the first scan
    after it comes back. Each close goes through
    ``LecturerSessionService.close_overdue_session``, which re-checks the
    session under its row lock, so a lecturer closing it at the same moment,
    or a second worker, never causes a second finalization.
    """

    def __init__(
        self,
        *,
        pool: asyncpg.Pool,
        service: LecturerSessionService,
        interval_seconds: float,
        grace_minutes: int,
        repository: LecturerSessionRepository | None = None,
        redis_client=None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._pool = pool
        self._service = service
        self._interval_seconds = interval_seconds
        self._grace = timedelta(minutes=grace_minutes)
        self._repository = repository or LecturerSessionRepository()
        self._redis_client = redis_client
        self._clock = clock or (lambda: datetime.now(UTC))

    async def run(self, stop_event: asyncio.Event) -> None:
        logger.info("Session auto-close scheduler started")
        try:
            while not stop_event.is_set():
                try:
                    closed = await self.run_once()
                    if closed:
                        logger.info(
                            "Overdue attendance sessions closed",
                            extra={"sessions_closed": closed},
                        )
                except asyncio.CancelledError:
                    raise
                except Exception as error:
                    logger.error(
                        "Session auto-close cycle failed",
                        extra={"auto_close_error_type": type(error).__name__},
                    )
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=self._interval_seconds)
                except TimeoutError:
                    pass
        finally:
            logger.info("Session auto-close scheduler stopped")

    async def run_once(self) -> int:
        cutoff = self._clock() - self._grace
        async with self._pool.acquire() as connection:
            session_ids = await self._repository.list_overdue_session_ids(
                connection,
                scheduled_end_before=cutoff,
                limit=MAX_SESSIONS_PER_SCAN,
            )

        closed = 0
        for session_id in session_ids:
            try:
                if await self._service.close_overdue_session(
                    self._pool,
                    session_id,
                    grace=self._grace,
                    redis_client=self._redis_client,
                ):
                    closed += 1
            except asyncio.CancelledError:
                raise
            except Exception as error:
                # One bad session must not stop the others from closing.
                logger.error(
                    "Could not auto-close attendance session",
                    extra={
                        "session_id": str(session_id),
                        "auto_close_error_type": type(error).__name__,
                    },
                )
        return closed


async def auto_close_schema_ready(pool: asyncpg.Pool) -> bool:
    """True once migration 20260930_01 has added ``closed_automatically``."""

    async with pool.acquire() as connection:
        return bool(
            await connection.fetchval(
                """
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'attendance_session'
                      AND table_name = 'sessions'
                      AND column_name = 'closed_automatically'
                )
                """,
            ),
        )


__all__ = ["MAX_SESSIONS_PER_SCAN", "SessionAutoCloseScheduler", "auto_close_schema_ready"]
