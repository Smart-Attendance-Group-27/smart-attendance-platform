import logging
from collections.abc import Awaitable, Callable

import asyncpg

logger = logging.getLogger(__name__)


async def announce(
    connection: asyncpg.Connection,
    notification: Callable[[], Awaitable[object]],
    *,
    label: str,
) -> None:
    """Runs one notification call without letting it break the change behind it.

    The call runs in a savepoint inside the caller's transaction, so the
    notification still appears only if the change commits. If the producer
    fails, only the savepoint rolls back: activating or closing a session must
    never fail because a notification could not be written.
    """

    try:
        async with connection.transaction():
            await notification()
    except Exception:
        logger.exception("Could not create the %s notification; continuing without it.", label)


__all__ = ["announce"]
