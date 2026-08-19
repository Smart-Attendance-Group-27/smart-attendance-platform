from collections.abc import Callable, Coroutine
from typing import Annotated, Any

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from core.config import ConfigurationError, Settings, get_settings
from modules.identity.auth.exception import (
    InactiveUserError,
    InsufficientRoleError,
    InvalidAccessTokenError,
    KeycloakUnavailableError,
    MissingAccessTokenError,
    UserNotLinkedError,
)
from modules.identity.auth.jwks import JwksClient, build_http_jwks_fetcher
from modules.identity.auth.schemas import AuthenticatedUser
from modules.identity.auth.service import AuthenticationService
from modules.identity.auth.token_verifier import KeycloakTokenVerifier

STUDENT_ROLE = "student"
LECTURER_ROLE = "lecturer"
ADMINISTRATOR_ROLE = "administrator"

# auto_error=False so a missing header produces our own 401 body rather than
# FastAPI's default, keeping every auth failure on one response shape.
bearer_scheme = HTTPBearer(auto_error=False)

BEARER_CHALLENGE = {"WWW-Authenticate": "Bearer"}


def _read_settings(request: Request) -> Settings:
    settings = getattr(request.app.state, "settings", None)
    if isinstance(settings, Settings):
        return settings
    return get_settings()


def build_authentication_service(settings: Settings) -> AuthenticationService:
    settings.require_keycloak_configuration()

    jwks_clients_by_issuer = {
        issuer: JwksClient(
            build_http_jwks_fetcher(jwks_url, settings.keycloak_jwks_timeout_seconds),
            cache_seconds=settings.keycloak_jwks_cache_seconds,
            min_refresh_seconds=settings.keycloak_jwks_min_refresh_seconds,
        )
        for issuer, jwks_url in settings.keycloak_issuer_jwks_pairs
    }
    token_verifier = KeycloakTokenVerifier(
        jwks_clients_by_issuer,
        audience=settings.keycloak_audience,
        authorized_clients=settings.keycloak_accepted_authorized_clients,
        algorithm=settings.keycloak_signing_algorithm,
        leeway_seconds=settings.keycloak_leeway_seconds,
    )

    return AuthenticationService(token_verifier)


def get_authentication_service(request: Request) -> AuthenticationService:
    """Returns the per-application authentication service.

    Built once and cached on app state so the JWKS cache is shared by every
    request instead of being rebuilt (and refetched) per call.
    """
    cached_service = getattr(request.app.state, "authentication_service", None)
    if isinstance(cached_service, AuthenticationService):
        return cached_service

    try:
        service = build_authentication_service(_read_settings(request))
    except ConfigurationError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error

    request.app.state.authentication_service = service
    return service


async def get_current_user(
    request: Request,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ] = None,
    authentication_service: Annotated[
        AuthenticationService,
        Depends(get_authentication_service),
    ] = None,  # type: ignore[assignment]
) -> AuthenticatedUser:
    """Resolves the caller's Keycloak token to an active application user."""
    try:
        access_token = _read_bearer_token(credentials)
        return await authentication_service.authenticate(
            request.app.state.db_pool,
            access_token,
        )
    except MissingAccessTokenError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="A bearer access token is required.",
            headers=BEARER_CHALLENGE,
        ) from error
    except InvalidAccessTokenError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=error.message,
            headers=BEARER_CHALLENGE,
        ) from error
    except UserNotLinkedError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No application user is linked to this Keycloak account.",
        ) from error
    except InactiveUserError as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This application account is not active.",
        ) from error
    except KeycloakUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not reach Keycloak to verify the access token.",
        ) from error


CurrentUser = Annotated[AuthenticatedUser, Depends(get_current_user)]


def require_realm_role(
    required_role: str,
) -> Callable[[AuthenticatedUser], Coroutine[Any, Any, AuthenticatedUser]]:
    """Builds a dependency that demands one Keycloak realm role."""

    async def check_role(current_user: CurrentUser) -> AuthenticatedUser:
        if not current_user.has_role(required_role):
            error = InsufficientRoleError(required_role)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"The '{required_role}' role is required.",
            ) from error

        return current_user

    return check_role


require_student_role = require_realm_role(STUDENT_ROLE)
CurrentStudent = Annotated[AuthenticatedUser, Depends(require_student_role)]

require_lecturer_role = require_realm_role(LECTURER_ROLE)
CurrentLecturer = Annotated[AuthenticatedUser, Depends(require_lecturer_role)]

require_administrator_role = require_realm_role(ADMINISTRATOR_ROLE)
CurrentAdministrator = Annotated[AuthenticatedUser, Depends(require_administrator_role)]


def _read_bearer_token(credentials: HTTPAuthorizationCredentials | None) -> str:
    if credentials is None:
        raise MissingAccessTokenError()

    if credentials.scheme.lower() != "bearer" or not credentials.credentials.strip():
        raise MissingAccessTokenError()

    return credentials.credentials
