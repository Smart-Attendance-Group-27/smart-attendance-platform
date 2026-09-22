from collections import Counter

import httpx
import pytest

from modules.identity.keycloak_admin.client import KeycloakAdminClient
from modules.identity.keycloak_admin.exception import (
    KeycloakAuthenticationError,
    KeycloakRoleNotFoundError,
    KeycloakUnavailableError,
    KeycloakUserAlreadyExistsError,
)


def build_client(handler, *, clock=lambda: 100.0) -> KeycloakAdminClient:
    return KeycloakAdminClient(
        base_url="http://keycloak.test",
        realm="Uni Attend",
        client_id="provisioner",
        client_secret="secret",
        transport=httpx.MockTransport(handler),
        clock=clock,
    )


def token_response() -> httpx.Response:
    return httpx.Response(200, json={"access_token": "admin-token", "expires_in": 300})


async def test_creates_user_and_reuses_cached_service_account_token() -> None:
    calls: Counter[str] = Counter()

    def handler(request: httpx.Request) -> httpx.Response:
        calls[request.url.path] += 1
        if request.url.path.endswith("/protocol/openid-connect/token"):
            assert b"client_secret=secret" in request.content
            return token_response()
        return httpx.Response(
            201,
            headers={"Location": "http://keycloak.test/admin/realms/Uni%20Attend/users/kc-user-1"},
        )

    client = build_client(handler)

    assert await client.create_user(email="new@example.test", first_name="New", last_name="User") == "kc-user-1"
    await client.create_user(email="second@example.test", first_name="Second", last_name="User")

    assert calls["/realms/Uni Attend/protocol/openid-connect/token"] == 1


async def test_assigns_realm_role_and_sets_temporary_password() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/protocol/openid-connect/token"):
            return token_response()
        requests.append(request)
        if request.method == "GET":
            return httpx.Response(200, json={"id": "role-1", "name": "student"})
        return httpx.Response(204)

    client = build_client(handler)
    await client.assign_realm_role("kc-user", "student")
    await client.set_temporary_password("kc-user", "Temporary-Password1!")

    assert requests[1].url.path.endswith("/users/kc-user/role-mappings/realm")
    assert requests[2].url.path.endswith("/users/kc-user/reset-password")
    assert requests[2].read().decode().find('"temporary":true') >= 0


async def test_deletes_or_disables_user_for_compensation() -> None:
    methods: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/protocol/openid-connect/token"):
            return token_response()
        methods.append(request.method)
        return httpx.Response(204)

    client = build_client(handler)
    await client.delete_user("kc-user")
    await client.disable_user("kc-user")

    assert methods == ["DELETE", "PUT"]


@pytest.mark.parametrize(
    ("status_code", "expected_error"),
    [(409, KeycloakUserAlreadyExistsError), (500, KeycloakUnavailableError)],
)
async def test_maps_create_user_failures(status_code, expected_error) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/protocol/openid-connect/token"):
            return token_response()
        return httpx.Response(status_code)

    with pytest.raises(expected_error):
        await build_client(handler).create_user(
            email="duplicate@example.test",
            first_name="Duplicate",
            last_name="User",
        )


async def test_maps_missing_realm_role() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/protocol/openid-connect/token"):
            return token_response()
        return httpx.Response(404)

    with pytest.raises(KeycloakRoleNotFoundError):
        await build_client(handler).assign_realm_role("kc-user", "student")


async def test_maps_service_account_rejection_without_exposing_secret() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401)

    with pytest.raises(KeycloakAuthenticationError) as error:
        await build_client(handler).create_user(
            email="new@example.test",
            first_name="New",
            last_name="User",
        )

    assert "secret" not in str(error.value)


async def test_maps_network_failure_to_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline", request=request)

    with pytest.raises(KeycloakUnavailableError):
        await build_client(handler).create_user(
            email="new@example.test",
            first_name="New",
            last_name="User",
        )
