"""Shared test fixtures.

These tests never reach Keycloak or Supabase. Tokens are signed with a locally
generated RSA key, the JWKS document is served from memory, and the database is
a hand-written fake, so the whole suite runs offline.
"""

from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm

from core.config import Settings
from modules.identity.auth.jwks import JwksClient
from modules.identity.auth.service import AuthenticationService
from modules.identity.auth.token_verifier import KeycloakTokenVerifier

TEST_ISSUER = "http://keycloak.test:8080/realms/uniattend"
TEST_AUDIENCE = "uniattend-api"
TEST_KEY_ID = "test-signing-key-1"
TEST_JWKS_URL = "http://keycloak.test:8080/realms/uniattend/protocol/openid-connect/certs"

STUDENT_USER_ID = UUID("20000000-0000-0000-0000-000000000011")
STUDENT_PROFILE_ID = UUID("23000000-0000-0000-0000-000000000001")
LECTURER_USER_ID = UUID("20000000-0000-0000-0000-000000000002")
ADMINISTRATOR_USER_ID = UUID("20000000-0000-0000-0000-000000000003")

LINKED_STUDENT_SUBJECT = "keycloak-sub-linked-student"
LINKED_LECTURER_SUBJECT = "keycloak-sub-linked-lecturer"
LINKED_ADMINISTRATOR_SUBJECT = "keycloak-sub-linked-administrator"
INACTIVE_STUDENT_SUBJECT = "keycloak-sub-inactive-student"
UNLINKED_SUBJECT = "keycloak-sub-not-linked"


def generate_rsa_key() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def build_jwks_document(
    private_key: rsa.RSAPrivateKey,
    key_id: str = TEST_KEY_ID,
) -> dict[str, Any]:
    public_jwk = RSAAlgorithm.to_jwk(private_key.public_key(), as_dict=True)
    public_jwk.update({"kid": key_id, "alg": "RS256", "use": "sig"})
    return {"keys": [public_jwk]}


@pytest.fixture(scope="session")
def signing_key() -> rsa.RSAPrivateKey:
    return generate_rsa_key()


@pytest.fixture(scope="session")
def jwks_document(signing_key: rsa.RSAPrivateKey) -> dict[str, Any]:
    return build_jwks_document(signing_key)


@pytest.fixture
def make_access_token(signing_key: rsa.RSAPrivateKey):
    def build_token(
        *,
        subject: str = LINKED_STUDENT_SUBJECT,
        roles: tuple[str, ...] = ("student",),
        issuer: str = TEST_ISSUER,
        audience: str | list[str] = TEST_AUDIENCE,
        email: str | None = "230701a@student.uniattend.test",
        expires_in_seconds: int = 300,
        key_id: str = TEST_KEY_ID,
        private_key: rsa.RSAPrivateKey | None = None,
        algorithm: str = "RS256",
        extra_claims: dict[str, Any] | None = None,
    ) -> str:
        issued_at = datetime.now(UTC)
        claims: dict[str, Any] = {
            "sub": subject,
            "iss": issuer,
            "aud": audience,
            "iat": issued_at,
            "exp": issued_at + timedelta(seconds=expires_in_seconds),
            "realm_access": {"roles": list(roles)},
        }

        if email is not None:
            claims["email"] = email

        if extra_claims:
            claims.update(extra_claims)

        return jwt.encode(
            claims,
            private_key or signing_key,
            algorithm=algorithm,
            headers={"kid": key_id},
        )

    return build_token


class FakeConnection:
    """Minimal asyncpg connection stand-in that answers `fetchrow`."""

    def __init__(
        self,
        users_by_keycloak_id: dict[str, dict[str, Any]] | None = None,
        profiles_by_user_id: dict[UUID, dict[str, Any]] | None = None,
    ) -> None:
        self.users_by_keycloak_id = users_by_keycloak_id or {}
        self.profiles_by_user_id = profiles_by_user_id or {}
        self.executed_queries: list[str] = []

    async def fetchrow(self, query: str, *args: Any) -> dict[str, Any] | None:
        self.executed_queries.append(query)

        if "identity.users" in query and "student_profiles" not in query:
            return self.users_by_keycloak_id.get(args[0])

        if "student_profiles" in query:
            return self.profiles_by_user_id.get(args[0])

        return None


class FakePool:
    """Async context manager shaped like `asyncpg.Pool.acquire()`."""

    def __init__(self, connection: FakeConnection) -> None:
        self.connection = connection

    @asynccontextmanager
    async def acquire(self):
        yield self.connection


def build_user_row(
    *,
    user_id: UUID = STUDENT_USER_ID,
    email: str | None = "230701a@student.uniattend.test",
    account_status: str = "active",
    keycloak_user_id: str = LINKED_STUDENT_SUBJECT,
) -> dict[str, Any]:
    return {
        "id": user_id,
        "email": email,
        "account_status": account_status,
        "keycloak_user_id": keycloak_user_id,
    }


def build_profile_row(
    *,
    profile_id: UUID = STUDENT_PROFILE_ID,
    user_id: UUID = STUDENT_USER_ID,
    registration_number: str | None = "230701A",
    first_name: str | None = "Amal",
    middle_name: str | None = None,
    last_name: str | None = "Perera",
    profile_status: str = "active",
    university_email: str | None = "230701a@student.uniattend.test",
) -> dict[str, Any]:
    return {
        "id": profile_id,
        "user_id": user_id,
        "registration_number": registration_number,
        "first_name": first_name,
        "middle_name": middle_name,
        "last_name": last_name,
        "profile_status": profile_status,
        "university_email": university_email,
    }


def default_connection() -> FakeConnection:
    """A database containing one active student, one lecturer, one disabled user."""
    return FakeConnection(
        users_by_keycloak_id={
            LINKED_STUDENT_SUBJECT: build_user_row(),
            LINKED_LECTURER_SUBJECT: build_user_row(
                user_id=LECTURER_USER_ID,
                email="n.perera@staff.uniattend.test",
                keycloak_user_id=LINKED_LECTURER_SUBJECT,
            ),
            LINKED_ADMINISTRATOR_SUBJECT: build_user_row(
                user_id=ADMINISTRATOR_USER_ID,
                email="s.rathnayake@staff.uniattend.test",
                keycloak_user_id=LINKED_ADMINISTRATOR_SUBJECT,
            ),
            INACTIVE_STUDENT_SUBJECT: build_user_row(
                user_id=UUID("20000000-0000-0000-0000-000000000012"),
                email="230702b@student.uniattend.test",
                account_status="disabled",
                keycloak_user_id=INACTIVE_STUDENT_SUBJECT,
            ),
        },
        profiles_by_user_id={STUDENT_USER_ID: build_profile_row()},
    )


def build_settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "db_uri": "postgresql://user:password@localhost:5432/postgres",
        "keycloak_expected_issuer": TEST_ISSUER,
        "keycloak_jwks_url": TEST_JWKS_URL,
        "keycloak_audience": TEST_AUDIENCE,
    }
    values.update(overrides)
    return Settings(**values)


def build_authentication_service_for_tests(
    jwks_document: dict[str, Any],
    *,
    expected_issuer: str = TEST_ISSUER,
    audience: str = TEST_AUDIENCE,
) -> AuthenticationService:
    async def fetch_jwks() -> dict[str, Any]:
        return jwks_document

    return AuthenticationService(
        KeycloakTokenVerifier(
            {expected_issuer: JwksClient(fetch_jwks)},
            audience=audience,
        ),
    )
