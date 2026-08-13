class AuthError(Exception):
    """Base class for authentication and authorization domain errors."""


class MissingAccessTokenError(AuthError):
    """Raised when the Authorization header is absent or not a bearer token."""


class InvalidAccessTokenError(AuthError):
    """Raised when a bearer token fails validation.

    The message is safe to return to the caller: it never contains the token,
    a key, or any configured value.
    """

    def __init__(self, message: str = "Access token is not valid.") -> None:
        super().__init__(message)
        self.message = message


class UserNotLinkedError(AuthError):
    """Raised when no application user is linked to the token's `sub` claim."""


class InactiveUserError(AuthError):
    """Raised when the linked application user is not active."""


class InsufficientRoleError(AuthError):
    """Raised when the caller's realm roles do not permit the operation."""

    def __init__(self, required_role: str) -> None:
        super().__init__(f"Role '{required_role}' is required.")
        self.required_role = required_role


class KeycloakUnavailableError(AuthError):
    """Raised when Keycloak's JWKS endpoint cannot be reached."""
