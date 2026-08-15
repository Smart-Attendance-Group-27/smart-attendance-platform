import asyncio
import logging
from collections.abc import Awaitable, Callable
from time import monotonic
from typing import Any

import httpx
from jwt import PyJWK, PyJWKSet
from jwt.exceptions import PyJWKError, PyJWKSetError

from modules.identity.auth.exception import (
    InvalidAccessTokenError,
    KeycloakUnavailableError,
)

logger = logging.getLogger(__name__)

JwksFetcher = Callable[[], Awaitable[dict[str, Any]]]


def build_http_jwks_fetcher(jwks_url: str, timeout_seconds: float) -> JwksFetcher:
    async def fetch_jwks() -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            response = await client.get(jwks_url)
            response.raise_for_status()
            return response.json()

    return fetch_jwks


class JwksClient:
    """Caches Keycloak's signing keys so they are not fetched per request.

    Keys are reused until `cache_seconds` elapses. An unknown `kid` triggers one
    early refresh, rate limited by `min_refresh_seconds` so that a flood of
    tokens carrying bogus key IDs cannot be turned into a flood of requests to
    Keycloak.
    """

    def __init__(
        self,
        fetch_jwks: JwksFetcher,
        *,
        cache_seconds: float = 300,
        min_refresh_seconds: float = 30,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self._fetch_jwks = fetch_jwks
        self._cache_seconds = cache_seconds
        self._min_refresh_seconds = min_refresh_seconds
        self._clock = clock or monotonic
        self._keys_by_id: dict[str, PyJWK] = {}
        self._fetched_at: float | None = None
        self._last_fetch_attempt_at: float | None = None
        self._lock = asyncio.Lock()

    async def get_signing_key(self, key_id: str) -> PyJWK:
        cached_key = self._read_fresh_cached_key(key_id)
        if cached_key is not None:
            return cached_key

        async with self._lock:
            # Another coroutine may have refreshed while this one waited.
            cached_key = self._read_fresh_cached_key(key_id)
            if cached_key is not None:
                return cached_key

            if self._may_refresh(key_id):
                await self._refresh()

        signing_key = self._keys_by_id.get(key_id)
        if signing_key is None:
            raise InvalidAccessTokenError("Access token signing key is unknown.")

        return signing_key

    def _read_fresh_cached_key(self, key_id: str) -> PyJWK | None:
        if self._is_cache_expired():
            return None
        return self._keys_by_id.get(key_id)

    def _is_cache_expired(self) -> bool:
        if self._fetched_at is None:
            return True
        return self._clock() - self._fetched_at >= self._cache_seconds

    def _may_refresh(self, key_id: str) -> bool:
        if self._is_cache_expired():
            return True

        # Cache is still fresh but this key ID is not in it. Allow one rate
        # limited refresh so genuine key rotation is picked up quickly.
        if key_id in self._keys_by_id:
            return False

        if self._last_fetch_attempt_at is None:
            return True

        return self._clock() - self._last_fetch_attempt_at >= self._min_refresh_seconds

    async def _refresh(self) -> None:
        self._last_fetch_attempt_at = self._clock()

        try:
            jwks_document = await self._fetch_jwks()
        except httpx.HTTPError as error:
            # The URL is intentionally not logged: it is configuration, and the
            # exception text from httpx can contain the full request target.
            logger.warning("Could not fetch Keycloak signing keys.")
            raise KeycloakUnavailableError(
                "Could not reach Keycloak to verify the access token.",
            ) from error

        try:
            key_set = PyJWKSet.from_dict(jwks_document)
        except (PyJWKSetError, PyJWKError, AttributeError, TypeError) as error:
            logger.warning("Keycloak returned an unusable JWKS document.")
            raise KeycloakUnavailableError(
                "Keycloak returned an unusable signing key document.",
            ) from error

        self._keys_by_id = {
            signing_key.key_id: signing_key
            for signing_key in key_set.keys
            if signing_key.key_id
        }
        self._fetched_at = self._clock()
