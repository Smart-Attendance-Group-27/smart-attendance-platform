from collections.abc import Container, Mapping
from typing import Any

import jwt
from jwt.exceptions import (
    ExpiredSignatureError,
    InvalidIssuerError,
    InvalidSignatureError,
    InvalidTokenError,
    MissingRequiredClaimError,
    PyJWTError,
)

from modules.identity.auth.exception import InvalidAccessTokenError
from modules.identity.auth.jwks import JwksClient
from modules.identity.auth.schemas import KeycloakTokenClaims

REQUIRED_CLAIMS = ("exp", "iss", "aud", "sub")


class KeycloakTokenVerifier:
    """Verifies a Keycloak access token end to end.

    Checks the signature against Keycloak's published keys, the signing
    algorithm, the expiry, the issuer, and the accepted token client. A token is
    accepted when either its `aud` contains the configured API audience or its
    `azp` matches an explicitly allowed Keycloak client.

    jwks_clients_by_issuer maps each trusted issuer to the JwksClient that
    fetches *that issuer's own* signing keys. This supports more than one
    Keycloak deployment at once (e.g. local Docker Keycloak for the web app
    and a shared deployed Keycloak for mobile) — trusting an issuer name
    alone is not enough, since each deployment signs with its own key, so the
    correct key source must be selected per token rather than fixed globally.
    The unverified `iss` claim is read only to pick which JWKS source to
    check against; the token is still fully signature-verified against that
    source's keys afterward, so a forged `iss` cannot bypass verification.
    """

    def __init__(
        self,
        jwks_clients_by_issuer: Mapping[str, JwksClient],
        *,
        audience: str,
        authorized_clients: Container[str] = (),
        algorithm: str = "RS256",
        leeway_seconds: float = 0,
    ) -> None:
        if not jwks_clients_by_issuer:
            raise ValueError("At least one accepted issuer must be configured")
        self._jwks_clients_by_issuer = dict(jwks_clients_by_issuer)
        self._audience = audience
        self._authorized_clients = authorized_clients
        self._algorithm = algorithm
        self._leeway_seconds = leeway_seconds

    async def verify(self, access_token: str) -> KeycloakTokenClaims:
        header = self._read_header(access_token)

        token_algorithm = header.get("alg")
        if token_algorithm != self._algorithm:
            # Blocks "alg": "none" and any downgrade to a symmetric algorithm.
            raise InvalidAccessTokenError("Access token algorithm is not accepted.")

        key_id = header.get("kid")
        if not isinstance(key_id, str) or not key_id:
            raise InvalidAccessTokenError("Access token has no signing key ID.")

        issuer = self._read_unverified_issuer(access_token)
        jwks_client = self._jwks_clients_by_issuer.get(issuer)
        if jwks_client is None:
            raise InvalidAccessTokenError("Access token issuer is not accepted.")

        signing_key = await jwks_client.get_signing_key(key_id)
        claims = self._decode(access_token, signing_key.key, issuer)
        self._validate_token_client(claims)

        subject = claims.get("sub")
        if not isinstance(subject, str) or not subject:
            raise InvalidAccessTokenError("Access token has no subject claim.")

        email = claims.get("email")

        return KeycloakTokenClaims(
            subject=subject,
            email=email if isinstance(email, str) and email else None,
            roles=self._read_realm_roles(claims),
        )

    def _read_header(self, access_token: str) -> dict[str, Any]:
        try:
            return jwt.get_unverified_header(access_token)
        except PyJWTError as error:
            raise InvalidAccessTokenError("Access token is malformed.") from error

    def _read_unverified_issuer(self, access_token: str) -> str:
        try:
            claims = jwt.decode(
                access_token,
                options={
                    "verify_signature": False,
                    "verify_exp": False,
                    "verify_aud": False,
                    "verify_iss": False,
                },
            )
        except PyJWTError as error:
            raise InvalidAccessTokenError("Access token is malformed.") from error

        issuer = claims.get("iss")
        if not isinstance(issuer, str) or not issuer:
            raise InvalidAccessTokenError("Access token is missing a required claim.")
        return issuer

    def _decode(self, access_token: str, signing_key: Any, issuer: str) -> dict[str, Any]:
        try:
            return jwt.decode(
                access_token,
                key=signing_key,
                algorithms=[self._algorithm],
                issuer=issuer,
                leeway=self._leeway_seconds,
                options={
                    "require": list(REQUIRED_CLAIMS),
                    "verify_signature": True,
                    "verify_exp": True,
                    # Keycloak public-client tokens on the shared dev realm may
                    # identify the caller in `azp` rather than listing this API
                    # in `aud`. Verify issuer/signature/expiry here, then apply
                    # the audience/authorized-party policy explicitly below.
                    "verify_aud": False,
                    "verify_iss": True,
                },
            )
        except ExpiredSignatureError as error:
            raise InvalidAccessTokenError("Access token has expired.") from error
        except InvalidIssuerError as error:
            raise InvalidAccessTokenError("Access token issuer is not accepted.") from error
        except InvalidSignatureError as error:
            raise InvalidAccessTokenError("Access token signature is not valid.") from error
        except MissingRequiredClaimError as error:
            raise InvalidAccessTokenError("Access token is missing a required claim.") from error
        except InvalidTokenError as error:
            raise InvalidAccessTokenError("Access token is not valid.") from error

    def _validate_token_client(self, claims: dict[str, Any]) -> None:
        audience = claims.get("aud")
        audiences: tuple[str, ...]
        if isinstance(audience, str):
            audiences = (audience,)
        elif isinstance(audience, list):
            audiences = tuple(value for value in audience if isinstance(value, str))
        else:
            audiences = ()

        if self._audience in audiences:
            return

        authorized_party = claims.get("azp")
        if (
            isinstance(authorized_party, str)
            and authorized_party in self._authorized_clients
        ):
            return

        raise InvalidAccessTokenError("Access token audience is not accepted.")

    @staticmethod
    def _read_realm_roles(claims: dict[str, Any]) -> tuple[str, ...]:
        realm_access = claims.get("realm_access")
        if not isinstance(realm_access, dict):
            return ()

        roles = realm_access.get("roles")
        if not isinstance(roles, list):
            return ()

        return tuple(role for role in roles if isinstance(role, str))
