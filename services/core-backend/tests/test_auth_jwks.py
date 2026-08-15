from typing import Any

import httpx
import pytest

from conftest import TEST_KEY_ID, build_jwks_document, generate_rsa_key
from modules.identity.auth.exception import (
    InvalidAccessTokenError,
    KeycloakUnavailableError,
)
from modules.identity.auth.jwks import JwksClient


class CountingFetcher:
    def __init__(self, documents: list[dict[str, Any]]) -> None:
        self.documents = documents
        self.call_count = 0

    async def __call__(self) -> dict[str, Any]:
        self.call_count += 1
        index = min(self.call_count - 1, len(self.documents) - 1)
        return self.documents[index]


class MutableClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


async def test_fetches_keys_once_and_serves_later_requests_from_cache(
    jwks_document,
) -> None:
    fetcher = CountingFetcher([jwks_document])
    client = JwksClient(fetcher, cache_seconds=300)

    for _ in range(5):
        assert await client.get_signing_key(TEST_KEY_ID) is not None

    assert fetcher.call_count == 1


async def test_refetches_keys_after_the_cache_expires(jwks_document) -> None:
    clock = MutableClock()
    fetcher = CountingFetcher([jwks_document])
    client = JwksClient(fetcher, cache_seconds=300, clock=clock)

    await client.get_signing_key(TEST_KEY_ID)
    clock.advance(301)
    await client.get_signing_key(TEST_KEY_ID)

    assert fetcher.call_count == 2


async def test_refreshes_early_when_an_unknown_key_id_appears(signing_key) -> None:
    rotated_key = generate_rsa_key()
    fetcher = CountingFetcher(
        [
            build_jwks_document(signing_key, key_id="old-key"),
            build_jwks_document(rotated_key, key_id="new-key"),
        ],
    )
    client = JwksClient(fetcher, cache_seconds=300, min_refresh_seconds=0)

    await client.get_signing_key("old-key")
    rotated_signing_key = await client.get_signing_key("new-key")

    assert rotated_signing_key is not None
    assert fetcher.call_count == 2


async def test_rate_limits_refreshes_for_repeated_unknown_key_ids(
    jwks_document,
) -> None:
    clock = MutableClock()
    fetcher = CountingFetcher([jwks_document])
    client = JwksClient(
        fetcher,
        cache_seconds=300,
        min_refresh_seconds=30,
        clock=clock,
    )

    await client.get_signing_key(TEST_KEY_ID)

    # A burst of tokens carrying bogus key IDs must not become a burst of
    # requests to Keycloak.
    for _ in range(10):
        with pytest.raises(InvalidAccessTokenError):
            await client.get_signing_key("attacker-supplied-key")

    assert fetcher.call_count == 1

    # Once the window has passed, exactly one refresh is allowed through, no
    # matter how many unknown key IDs arrive.
    clock.advance(31)
    for _ in range(10):
        with pytest.raises(InvalidAccessTokenError):
            await client.get_signing_key("attacker-supplied-key")

    assert fetcher.call_count == 2


async def test_reports_keycloak_as_unavailable_when_the_fetch_fails() -> None:
    async def failing_fetch() -> dict[str, Any]:
        raise httpx.ConnectError("connection refused")

    client = JwksClient(failing_fetch)

    with pytest.raises(KeycloakUnavailableError):
        await client.get_signing_key(TEST_KEY_ID)


async def test_reports_keycloak_as_unavailable_for_an_unusable_document() -> None:
    async def bad_document() -> dict[str, Any]:
        return {"not-keys": []}

    client = JwksClient(bad_document)

    with pytest.raises(KeycloakUnavailableError):
        await client.get_signing_key(TEST_KEY_ID)
