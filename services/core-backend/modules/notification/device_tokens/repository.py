from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

import asyncpg


@dataclass(frozen=True)
class DeviceTokenRecord:
    id: UUID
    user_id: UUID
    expo_push_token: str
    platform: str
    is_active: bool
    registered_at: datetime
    last_used_at: datetime | None
    revoked_at: datetime | None


class DeviceTokenRepository:
    async def find_by_token(
        self,
        connection: asyncpg.Connection,
        expo_push_token: str,
    ) -> DeviceTokenRecord | None:
        row = await connection.fetchrow(
            """
            SELECT id, user_id, expo_push_token, platform,
                   is_active, registered_at, last_used_at, revoked_at
            FROM notification.device_tokens
            WHERE expo_push_token = $1
            """,
            expo_push_token,
        )
        if row is None:
            return None
        return _row_to_record(row)

    async def upsert(
        self,
        connection: asyncpg.Connection,
        *,
        user_id: UUID,
        expo_push_token: str,
        platform: str,
    ) -> DeviceTokenRecord:
        """Insert a new token or reactivate an existing one.

        On conflict (same expo_push_token) the row is updated in place:
        - is_active   → true
        - revoked_at  → NULL  (clear any previous revocation)
        - last_used_at → now()
        The user_id is intentionally NOT updated on conflict so that an old
        revoked token cannot be hijacked to spy on a different user.
        """
        row = await connection.fetchrow(
            """
            INSERT INTO notification.device_tokens
                (id, user_id, expo_push_token, platform,
                 is_active, registered_at, last_used_at, revoked_at)
            VALUES
                (gen_random_uuid(), $1, $2, $3,
                 true, now(), now(), NULL)
            ON CONFLICT (expo_push_token) DO UPDATE
                SET is_active    = true,
                    revoked_at   = NULL,
                    last_used_at = now()
            RETURNING id, user_id, expo_push_token, platform,
                      is_active, registered_at, last_used_at, revoked_at
            """,
            user_id,
            expo_push_token,
            platform,
        )
        assert row is not None
        return _row_to_record(row)

    async def find_active_for_user(
        self,
        connection: asyncpg.Connection,
        user_id: UUID,
    ) -> list[DeviceTokenRecord]:
        rows = await connection.fetch(
            """
            SELECT id, user_id, expo_push_token, platform,
                   is_active, registered_at, last_used_at, revoked_at
            FROM notification.device_tokens
            WHERE user_id   = $1
              AND is_active  = true
              AND revoked_at IS NULL
            ORDER BY registered_at DESC
            """,
            user_id,
        )
        return [_row_to_record(row) for row in rows]

    async def deactivate(
        self,
        connection: asyncpg.Connection,
        token_id: UUID,
    ) -> None:
        """Mark a token as revoked (e.g. Expo reported DeviceNotRegistered)."""
        await connection.execute(
            """
            UPDATE notification.device_tokens
            SET is_active  = false,
                revoked_at = now()
            WHERE id = $1
            """,
            token_id,
        )


def _row_to_record(row: asyncpg.Record) -> DeviceTokenRecord:
    return DeviceTokenRecord(
        id=row["id"],
        user_id=row["user_id"],
        expo_push_token=row["expo_push_token"],
        platform=row["platform"],
        is_active=bool(row["is_active"]),
        registered_at=row["registered_at"],
        last_used_at=row["last_used_at"],
        revoked_at=row["revoked_at"],
    )
