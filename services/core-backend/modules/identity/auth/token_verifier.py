from typing import Any

import jwt
from jwt.exceptions import (
    ExpiredSignatureError,
    InvalidAudienceError,
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
    algorithm, the expiry, the exact issuer, and the API audience. None of these
    checks is optional: a token that fails any of them is rejected.
    """

    def __init__(
        self,
        jwks_client: JwksClient,
        *,
        expected_issuer: str,
        audience: str,
        algorithm: str = "RS256",
        leeway_seconds: float = 0,
    ) -> None:
        self._jwks_client = jwks_client
        self._expected_issuer = expected_issuer
        self._audience = audience
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

        signing_key = await self._jwks_client.get_signing_key(key_id)
        claims = self._decode(access_token, signing_key.key)

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

    def _decode(self, access_token: str, signing_key: Any) -> dict[str, Any]:
        try:
            return jwt.decode(
                access_token,
                key=signing_key,
                algorithms=[self._algorithm],
                audience=self._audience,
                issuer=self._expected_issuer,
                leeway=self._leeway_seconds,
                options={
                    "require": list(REQUIRED_CLAIMS),
                    "verify_signature": True,
                    "verify_exp": True,
                    "verify_aud": True,
                    "verify_iss": True,
                },
            )
        except ExpiredSignatureError as error:
            raise InvalidAccessTokenError("Access token has expired.") from error
        except InvalidIssuerError as error:
            raise InvalidAccessTokenError("Access token issuer is not accepted.") from error
        except InvalidAudienceError as error:
            raise InvalidAccessTokenError("Access token audience is not accepted.") from error
        except InvalidSignatureError as error:
            raise InvalidAccessTokenError("Access token signature is not valid.") from error
        except MissingRequiredClaimError as error:
            raise InvalidAccessTokenError("Access token is missing a required claim.") from error
        except InvalidTokenError as error:
            raise InvalidAccessTokenError("Access token is not valid.") from error

    @staticmethod
    def _read_realm_roles(claims: dict[str, Any]) -> tuple[str, ...]:
        realm_access = claims.get("realm_access")
        if not isinstance(realm_access, dict):
            return ()

        roles = realm_access.get("roles")
        if not isinstance(roles, list):
            return ()

        return tuple(role for role in roles if isinstance(role, str))
