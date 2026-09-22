class KeycloakAdminError(Exception):
    """Base class for sanitized Keycloak administration failures."""


class KeycloakAuthenticationError(KeycloakAdminError):
    """The provisioning service account could not authenticate or authorize."""


class KeycloakUserAlreadyExistsError(KeycloakAdminError):
    """Keycloak already contains the requested user."""


class KeycloakRoleNotFoundError(KeycloakAdminError):
    """The configured realm does not contain the requested role."""


class KeycloakUnavailableError(KeycloakAdminError):
    """Keycloak could not be reached or returned a transient server failure."""


class KeycloakOperationError(KeycloakAdminError):
    """Keycloak rejected an otherwise well-formed administration operation."""

