import asyncio
from collections.abc import Callable
from time import monotonic
from urllib.parse import quote

import httpx

from core.config import Settings
from modules.identity.keycloak_admin.exception import (
    KeycloakAuthenticationError,
    KeycloakOperationError,
    KeycloakRoleNotFoundError,
    KeycloakUnavailableError,
    KeycloakUserAlreadyExistsError,
)


class KeycloakAdminClient:
    def __init__(
        self,
        *,
        base_url: str,
        realm: str,
        client_id: str,
        client_secret: str,
        timeout_seconds: float = 10,
        transport: httpx.AsyncBaseTransport | None = None,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._realm = quote(realm, safe="")
        self._client_id = client_id
        self._client_secret = client_secret
        self._timeout_seconds = timeout_seconds
        self._transport = transport
        self._clock = clock
        self._access_token: str | None = None
        self._token_expires_at = 0.0
        self._token_lock = asyncio.Lock()

    @classmethod
    def from_settings(cls, settings: Settings) -> "KeycloakAdminClient":
        settings.require_keycloak_admin_configuration()
        assert settings.keycloak_admin_base_url is not None
        assert settings.keycloak_admin_realm is not None
        assert settings.keycloak_admin_client_id is not None
        assert settings.keycloak_admin_client_secret is not None
        return cls(
            base_url=settings.keycloak_admin_base_url,
            realm=settings.keycloak_admin_realm,
            client_id=settings.keycloak_admin_client_id,
            client_secret=settings.keycloak_admin_client_secret.get_secret_value(),
            timeout_seconds=settings.keycloak_admin_timeout_seconds,
        )

    async def create_user(
        self,
        *,
        email: str,
        first_name: str,
        last_name: str,
    ) -> str:
        response = await self._admin_request(
            "POST",
            "/users",
            json={
                "username": email,
                "email": email,
                "firstName": first_name,
                "lastName": last_name,
                "enabled": True,
                "emailVerified": True,
            },
            expected_status=201,
            conflict_error=KeycloakUserAlreadyExistsError,
        )
        location = response.headers.get("Location", "")
        user_id = location.rstrip("/").rsplit("/", 1)[-1]
        if not user_id or user_id == "users":
            raise KeycloakOperationError("Keycloak did not return the created user identifier.")
        return user_id

    async def assign_realm_role(self, user_id: str, role_name: str) -> None:
        role_response = await self._admin_request(
            "GET",
            f"/roles/{quote(role_name, safe='')}",
            expected_status=200,
            not_found_error=KeycloakRoleNotFoundError,
        )
        await self._admin_request(
            "POST",
            f"/users/{quote(user_id, safe='')}/role-mappings/realm",
            json=[role_response.json()],
            expected_status=204,
        )

    async def set_temporary_password(self, user_id: str, password: str) -> None:
        await self._admin_request(
            "PUT",
            f"/users/{quote(user_id, safe='')}/reset-password",
            json={"type": "password", "value": password, "temporary": True},
            expected_status=204,
        )

    async def delete_user(self, user_id: str) -> None:
        await self._admin_request(
            "DELETE",
            f"/users/{quote(user_id, safe='')}",
            expected_status=(204, 404),
        )

    async def disable_user(self, user_id: str) -> None:
        await self._admin_request(
            "PUT",
            f"/users/{quote(user_id, safe='')}",
            json={"enabled": False},
            expected_status=204,
        )

    async def _get_access_token(self) -> str:
        if self._access_token and self._clock() < self._token_expires_at:
            return self._access_token

        async with self._token_lock:
            if self._access_token and self._clock() < self._token_expires_at:
                return self._access_token
            try:
                async with httpx.AsyncClient(
                    timeout=self._timeout_seconds,
                    transport=self._transport,
                ) as client:
                    response = await client.post(
                        f"{self._base_url}/realms/{self._realm}/protocol/openid-connect/token",
                        data={
                            "grant_type": "client_credentials",
                            "client_id": self._client_id,
                            "client_secret": self._client_secret,
                        },
                    )
            except (httpx.TimeoutException, httpx.RequestError) as error:
                raise KeycloakUnavailableError("Keycloak is unavailable.") from error

            if response.status_code in (401, 403):
                raise KeycloakAuthenticationError(
                    "The Keycloak provisioning service account was rejected.",
                )
            if response.status_code >= 500:
                raise KeycloakUnavailableError("Keycloak is unavailable.")
            if response.status_code != 200:
                raise KeycloakAuthenticationError(
                    "The Keycloak provisioning service account could not obtain a token.",
                )

            try:
                payload = response.json()
                access_token = payload["access_token"]
                expires_in = float(payload.get("expires_in", 60))
            except (KeyError, TypeError, ValueError) as error:
                raise KeycloakAuthenticationError(
                    "Keycloak returned an invalid service-account token response.",
                ) from error

            self._access_token = access_token
            self._token_expires_at = self._clock() + max(1, expires_in - 30)
            return access_token

    async def _admin_request(
        self,
        method: str,
        path: str,
        *,
        json: object | None = None,
        expected_status: int | tuple[int, ...],
        conflict_error: type[Exception] | None = None,
        not_found_error: type[Exception] | None = None,
    ) -> httpx.Response:
        token = await self._get_access_token()
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout_seconds,
                transport=self._transport,
            ) as client:
                response = await client.request(
                    method,
                    f"{self._base_url}/admin/realms/{self._realm}{path}",
                    headers={"Authorization": f"Bearer {token}"},
                    json=json,
                )
        except (httpx.TimeoutException, httpx.RequestError) as error:
            raise KeycloakUnavailableError("Keycloak is unavailable.") from error

        statuses = (expected_status,) if isinstance(expected_status, int) else expected_status
        if response.status_code in statuses:
            return response
        if response.status_code in (401, 403):
            self._access_token = None
            raise KeycloakAuthenticationError(
                "The Keycloak provisioning service account lacks required access.",
            )
        if response.status_code == 409 and conflict_error is not None:
            raise conflict_error("A matching Keycloak user already exists.")
        if response.status_code == 404 and not_found_error is not None:
            raise not_found_error("The requested Keycloak realm role does not exist.")
        if response.status_code >= 500:
            raise KeycloakUnavailableError("Keycloak is unavailable.")
        raise KeycloakOperationError("Keycloak rejected the account provisioning operation.")
