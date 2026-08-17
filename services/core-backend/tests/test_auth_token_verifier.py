from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
import pytest

from conftest import (
    TEST_AUDIENCE,
    TEST_ISSUER,
    TEST_KEY_ID,
    generate_rsa_key,
)
from modules.identity.auth.exception import InvalidAccessTokenError
from modules.identity.auth.jwks import JwksClient
from modules.identity.auth.token_verifier import KeycloakTokenVerifier


def build_verifier(
    jwks_document: dict[str, Any],
    *,
    expected_issuer: str | tuple[str, ...] = TEST_ISSUER,
    audience: str = TEST_AUDIENCE,
) -> KeycloakTokenVerifier:
    async def fetch_jwks() -> dict[str, Any]:
        return jwks_document

    return KeycloakTokenVerifier(
        JwksClient(fetch_jwks),
        expected_issuer=expected_issuer,
        audience=audience,
    )


async def test_accepts_a_valid_token(jwks_document, make_access_token) -> None:
    verifier = build_verifier(jwks_document)

    claims = await verifier.verify(make_access_token())

    assert claims.subject == "keycloak-sub-linked-student"
    assert claims.email == "230701a@student.uniattend.test"
    assert claims.roles == ("student",)


async def test_extracts_realm_access_roles(jwks_document, make_access_token) -> None:
    verifier = build_verifier(jwks_document)

    claims = await verifier.verify(
        make_access_token(roles=("student", "offline_access")),
    )

    assert claims.roles == ("student", "offline_access")


async def test_returns_no_roles_when_realm_access_is_absent(
    jwks_document,
    make_access_token,
) -> None:
    verifier = build_verifier(jwks_document)
    token = make_access_token(extra_claims={"realm_access": None})

    claims = await verifier.verify(token)

    assert claims.roles == ()


async def test_rejects_a_malformed_token(jwks_document) -> None:
    verifier = build_verifier(jwks_document)

    with pytest.raises(InvalidAccessTokenError) as error:
        await verifier.verify("this-is-not-a-jwt")

    assert "malformed" in str(error.value)


async def test_rejects_a_token_signed_by_another_key(
    jwks_document,
    make_access_token,
) -> None:
    verifier = build_verifier(jwks_document)
    # Same key ID, different private key: the signature must not verify.
    token = make_access_token(private_key=generate_rsa_key())

    with pytest.raises(InvalidAccessTokenError) as error:
        await verifier.verify(token)

    assert "signature" in str(error.value)


async def test_rejects_a_token_with_an_unknown_key_id(
    jwks_document,
    make_access_token,
) -> None:
    verifier = build_verifier(jwks_document)

    with pytest.raises(InvalidAccessTokenError) as error:
        await verifier.verify(make_access_token(key_id="some-other-key"))

    assert "signing key" in str(error.value)


async def test_rejects_an_expired_token(jwks_document, make_access_token) -> None:
    verifier = build_verifier(jwks_document)

    with pytest.raises(InvalidAccessTokenError) as error:
        await verifier.verify(make_access_token(expires_in_seconds=-60))

    assert "expired" in str(error.value)


async def test_rejects_a_token_from_another_issuer(
    jwks_document,
    make_access_token,
) -> None:
    verifier = build_verifier(jwks_document)
    token = make_access_token(issuer="http://evil.test:8080/realms/uniattend")

    with pytest.raises(InvalidAccessTokenError) as error:
        await verifier.verify(token)

    assert "issuer" in str(error.value)


async def test_rejects_a_token_whose_issuer_differs_only_by_host(
    jwks_document,
    make_access_token,
) -> None:
    # A phone signing in through a LAN address gets a LAN issuer. If the backend
    # expects localhost the token must be rejected, not quietly accepted.
    verifier = build_verifier(jwks_document)
    token = make_access_token(issuer="http://192.168.1.5:8080/realms/uniattend")

    with pytest.raises(InvalidAccessTokenError):
        await verifier.verify(token)


async def test_accepts_a_token_matching_any_of_several_issuers(
    jwks_document,
    make_access_token,
) -> None:
    lan_issuer = "http://192.168.1.5:8080/realms/uniattend"
    verifier = build_verifier(jwks_document, expected_issuer=(TEST_ISSUER, lan_issuer))
    token = make_access_token(issuer=lan_issuer)

    claims = await verifier.verify(token)

    assert claims.subject == "keycloak-sub-linked-student"


async def test_rejects_a_token_from_an_issuer_outside_the_accepted_set(
    jwks_document,
    make_access_token,
) -> None:
    verifier = build_verifier(
        jwks_document,
        expected_issuer=(TEST_ISSUER, "http://192.168.1.5:8080/realms/uniattend"),
    )
    token = make_access_token(issuer="http://evil.test:8080/realms/uniattend")

    with pytest.raises(InvalidAccessTokenError) as error:
        await verifier.verify(token)

    assert "issuer" in str(error.value)


async def test_rejects_a_token_for_another_audience(
    jwks_document,
    make_access_token,
) -> None:
    verifier = build_verifier(jwks_document)

    with pytest.raises(InvalidAccessTokenError) as error:
        await verifier.verify(make_access_token(audience="account"))

    assert "audience" in str(error.value)


async def test_accepts_a_token_listing_several_audiences(
    jwks_document,
    make_access_token,
) -> None:
    verifier = build_verifier(jwks_document)
    token = make_access_token(audience=["account", TEST_AUDIENCE])

    claims = await verifier.verify(token)

    assert claims.subject == "keycloak-sub-linked-student"


async def test_rejects_an_unsigned_token(jwks_document) -> None:
    # The classic "alg": "none" downgrade attack.
    verifier = build_verifier(jwks_document)
    issued_at = datetime.now(UTC)
    unsigned_token = jwt.encode(
        {
            "sub": "keycloak-sub-linked-student",
            "iss": TEST_ISSUER,
            "aud": TEST_AUDIENCE,
            "exp": issued_at + timedelta(seconds=300),
        },
        key=None,
        algorithm="none",
        headers={"kid": TEST_KEY_ID},
    )

    with pytest.raises(InvalidAccessTokenError) as error:
        await verifier.verify(unsigned_token)

    assert "algorithm" in str(error.value)


async def test_rejects_a_token_without_a_key_id(jwks_document, signing_key) -> None:
    verifier = build_verifier(jwks_document)
    token = jwt.encode({"sub": "anyone"}, signing_key, algorithm="RS256")

    with pytest.raises(InvalidAccessTokenError) as error:
        await verifier.verify(token)

    assert "signing key ID" in str(error.value)


async def test_rejects_a_token_without_a_subject(
    jwks_document,
    signing_key,
) -> None:
    verifier = build_verifier(jwks_document)
    issued_at = datetime.now(UTC)
    token = jwt.encode(
        {
            "iss": TEST_ISSUER,
            "aud": TEST_AUDIENCE,
            "exp": issued_at + timedelta(seconds=300),
        },
        signing_key,
        algorithm="RS256",
        headers={"kid": TEST_KEY_ID},
    )

    with pytest.raises(InvalidAccessTokenError) as error:
        await verifier.verify(token)

    assert "required claim" in str(error.value)
