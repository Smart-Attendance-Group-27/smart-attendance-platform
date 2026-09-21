import re
from uuid import UUID

import asyncpg

from modules.notification.device_tokens.exception import (
    InvalidExpoPushTokenError,
    UnsupportedPlatformError,
)
from modules.notification.device_tokens.repository import (
    DeviceTokenRecord,
    DeviceTokenRepository,
)

# Expo push tokens look like  ExponentPushToken[xxxxxxxxxxxxxxxxxxxxxx]
# or the newer  ExpoPushToken[xxxxxxxxxxxxxxxxxxxxxx]
_EXPO_TOKEN_PATTERN = re.compile(
    r"^Expo(nent)?PushToken\[.+\]$",
    re.IGNORECASE,
)

SUPPORTED_PLATFORMS = frozenset({"android"})


class DeviceTokenService:
    def __init__(
        self,
        repository: DeviceTokenRepository | None = None,
    ) -> None:
        self._repository = repository or DeviceTokenRepository()

    async def register(
        self,
        pool: asyncpg.Pool,
        *,
        user_id: UUID,
        expo_push_token: str,
        platform: str,
    ) -> DeviceTokenRecord:
        """Validate and persist (or reactivate) a device push token.

        The user_id comes from the verified JWT, not from the request body,
        so it is always the authenticated user's own ID.

        If the same token was previously registered (by any user) it is
        reactivated and its last_used_at is refreshed.  The owner (user_id)
        is NOT changed on reactivation — see repository.upsert for rationale.
        """
        _validate_token(expo_push_token)
        _validate_platform(platform)

        async with pool.acquire() as connection:
            return await self._repository.upsert(
                connection,
                user_id=user_id,
                expo_push_token=expo_push_token,
                platform=platform.lower(),
            )

    async def revoke(
        self,
        pool: asyncpg.Pool,
        *,
        user_id: UUID,
        expo_push_token: str,
    ) -> bool:
        """Validate and revoke an active device push token for the user."""
        _validate_token(expo_push_token)

        async with pool.acquire() as connection:
            return await self._repository.revoke(
                connection,
                user_id=user_id,
                expo_push_token=expo_push_token,
            )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _validate_token(token: str) -> None:
    if not token or not _EXPO_TOKEN_PATTERN.match(token.strip()):
        raise InvalidExpoPushTokenError(
            f"'{token}' is not a valid Expo push token. "
            "Expected format: ExponentPushToken[...] or ExpoPushToken[...]"
        )


def _validate_platform(platform: str) -> None:
    if platform.lower() not in SUPPORTED_PLATFORMS:
        raise UnsupportedPlatformError(
            f"'{platform}' is not a supported platform. "
            f"Supported values: {', '.join(sorted(SUPPORTED_PLATFORMS))}"
        )
