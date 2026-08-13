from dataclasses import dataclass
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


@dataclass(frozen=True)
class KeycloakTokenClaims:
    """The subset of verified token claims the application uses."""

    subject: str
    email: str | None
    roles: tuple[str, ...]


@dataclass(frozen=True)
class AuthenticatedUser:
    """A caller that presented a valid token and maps to an active app user.

    `user_id` is `identity.users.id`, the permanent internal application ID.
    `keycloak_user_id` is the opaque Keycloak `sub` claim.
    """

    user_id: UUID
    keycloak_user_id: str
    email: str | None
    roles: tuple[str, ...]

    def has_role(self, role: str) -> bool:
        return role in self.roles


class CurrentUserResponse(BaseModel):
    """Safe view of the signed-in application user.

    Deliberately excludes password hashes, lockout counters, token records and
    every Keycloak field other than the roles the client already knows about.
    """

    model_config = ConfigDict(populate_by_name=True)

    id: UUID
    email: str | None = None
    roles: list[str] = Field(default_factory=list)
