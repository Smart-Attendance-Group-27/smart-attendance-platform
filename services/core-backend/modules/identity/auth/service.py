import asyncpg

from modules.identity.auth.exception import (
    InactiveUserError,
    UserNotLinkedError,
)
from modules.identity.auth.repository import AuthUserRepository
from modules.identity.auth.schemas import AuthenticatedUser
from modules.identity.auth.token_verifier import KeycloakTokenVerifier

ACTIVE_ACCOUNT_STATUS = "active"


class AuthenticationService:
    """Turns a bearer token into an application user.

    Keycloak proves who the caller is. This service decides whether that caller
    corresponds to a usable UniAttend account:

        token sub -> identity.users.keycloak_user_id -> identity.users.id
    """

    def __init__(
        self,
        token_verifier: KeycloakTokenVerifier,
        repository: AuthUserRepository | None = None,
    ) -> None:
        self._token_verifier = token_verifier
        self._repository = repository or AuthUserRepository()

    async def authenticate(
        self,
        pool: asyncpg.Pool,
        access_token: str,
    ) -> AuthenticatedUser:
        claims = await self._token_verifier.verify(access_token)

        async with pool.acquire() as connection:
            user_record = await self._repository.find_by_keycloak_user_id(
                connection,
                claims.subject,
            )

        if user_record is None:
            raise UserNotLinkedError(
                "No application user is linked to this Keycloak account.",
            )

        if user_record.account_status != ACTIVE_ACCOUNT_STATUS:
            raise InactiveUserError("This application account is not active.")

        return AuthenticatedUser(
            user_id=user_record.id,
            keycloak_user_id=claims.subject,
            # Prefer the application record so a stale token cannot change the
            # email the API reports.
            email=user_record.email or claims.email,
            roles=claims.roles,
        )
