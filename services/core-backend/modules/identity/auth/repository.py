from dataclasses import dataclass
from uuid import UUID

import asyncpg


@dataclass(frozen=True)
class ApplicationUserRecord:
    id: UUID
    email: str | None
    account_status: str | None
    keycloak_user_id: str | None


class AuthUserRepository:
    """Reads application users. It never decides whether access is allowed."""

    async def find_by_keycloak_user_id(
        self,
        connection: asyncpg.Connection,
        keycloak_user_id: str,
    ) -> ApplicationUserRecord | None:
        row = await connection.fetchrow(
            """
            SELECT id, email, account_status, keycloak_user_id
            FROM identity.users
            WHERE keycloak_user_id = $1
            """,
            keycloak_user_id,
        )

        if row is None:
            return None

        return ApplicationUserRecord(
            id=row["id"],
            email=row["email"],
            account_status=row["account_status"],
            keycloak_user_id=row["keycloak_user_id"],
        )
