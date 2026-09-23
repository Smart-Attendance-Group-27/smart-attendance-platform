from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


ENV_FILE_PATH = Path(__file__).resolve().parents[1] / ".env"

SUPPORTED_SSL_MODES = frozenset(
    {"disable", "allow", "prefer", "require", "verify-ca", "verify-full"},
)


class ConfigurationError(RuntimeError):
    """Raised when required configuration is missing.

    The message names the missing environment variables only. Configured values
    are never included so that secrets stay out of logs and error responses.
    """


class Settings(BaseSettings):
    app_name: str = "UniAttend Core API"
    app_environment: str = "development"

    # Database connection. DB_URI takes precedence when it is set; the
    # individual DB_HOST/DB_PORT/DB_NAME/DB_USER/DB_PASSWORD fields are only
    # used when DB_URI is absent. See db/pool.py.
    db_uri: str | None = None
    db_host: str | None = None
    db_port: int = 5432
    db_name: str = "postgres"
    db_user: str | None = None
    db_password: SecretStr | None = None
    db_ssl_mode: str = "require"
    db_pool_min_size: int = Field(default=1, ge=1)
    db_pool_max_size: int = Field(default=5, ge=1)
    db_command_timeout_seconds: float = Field(default=10, gt=0)

    # Optional Redis cache used for QR batch metadata. A blank value disables
    # caching while keeping the database-backed QR flow available.
    redis_url: str | None = "redis://localhost:6379/0"

    # Keycloak access-token validation.
    # KEYCLOAK_EXPECTED_ISSUER must match the token `iss` claim exactly.
    # KEYCLOAK_JWKS_URL is resolved from the backend, so it may use a different
    # host than the issuer (for example localhost instead of a LAN address).
    keycloak_expected_issuer: str | None = None
    # Optional extra accepted issuers, each with its OWN signing-key source:
    # different Keycloak deployments (e.g. the local Docker Keycloak used by
    # the web app vs. the shared deployed Keycloak used by mobile) sign
    # tokens with different private keys, so trusting a second issuer name is
    # not enough — the matching JWKS must be fetched from that issuer's own
    # Keycloak too. Format is comma-separated "issuer|jwks_url" pairs:
    #   KEYCLOAK_ADDITIONAL_ISSUERS="http://a/realms/x|http://a/realms/x/protocol/openid-connect/certs,http://b/..."
    keycloak_additional_issuers: str | None = None
    keycloak_jwks_url: str | None = None
    keycloak_audience: str = "uniattend-api"
    # Some shared-development Keycloak clients may not include the API audience
    # in access tokens. In that case, accept tokens issued to one of these
    # public/confidential clients via the verified `azp` claim.
    keycloak_authorized_clients: str | None = "uniattend-mobile,uniattend-web"
    keycloak_signing_algorithm: str = "RS256"
    keycloak_jwks_cache_seconds: float = Field(default=300, gt=0)
    keycloak_jwks_min_refresh_seconds: float = Field(default=30, ge=0)
    keycloak_jwks_timeout_seconds: float = Field(default=5, gt=0)
    # Allow small clock differences between Keycloak and API hosts when
    # validating time-based JWT claims such as iat, nbf, and exp.
    keycloak_leeway_seconds: float = Field(default=5, ge=0)

    # Keycloak Admin API service account used only for account provisioning.
    # These settings are validated lazily so deployments that do not expose
    # provisioning can still run the rest of the API.
    keycloak_admin_base_url: str | None = None
    keycloak_admin_realm: str | None = None
    keycloak_admin_client_id: str | None = None
    keycloak_admin_client_secret: SecretStr | None = None
    keycloak_admin_timeout_seconds: float = Field(default=10, gt=0)

    # Required by dynamic QR generation and verification. Static QR sessions
    # do not use this secret.
    dynamic_qr_hmac_secret: SecretStr | None = None

    # Internal service URL for the separately deployed face-verification API.
    face_verification_service_url: str | None = "http://localhost:8001"
    face_verification_timeout_seconds: float = Field(default=30, gt=0)

    # Expo Push Notification Service.
    # expo_push_timeout_seconds: how long to wait for a response from Expo.
    # expo_access_token: required only when Expo Enhanced Push Security is
    # enabled on the project. Leave blank for development / OSS projects.
    expo_push_timeout_seconds: float = Field(default=10.0, gt=0)
    expo_access_token: SecretStr | None = None
    push_worker_enabled: bool = False
    push_worker_poll_interval_seconds: float = Field(default=2.0, gt=0)
    push_worker_batch_size: int = Field(default=100, ge=1, le=100)
    push_worker_receipt_batch_size: int = Field(default=1000, ge=1, le=1000)
    push_worker_receipt_delay_seconds: float = Field(default=15.0, ge=0)
    push_worker_lease_timeout_seconds: float = Field(default=60.0, gt=0)
    push_worker_max_attempts: int = Field(default=5, ge=1)
    push_worker_retry_base_seconds: float = Field(default=5.0, gt=0)
    push_worker_retry_max_seconds: float = Field(default=300.0, gt=0)
    push_worker_shutdown_timeout_seconds: float = Field(default=15.0, gt=0)
    reminder_scheduler_enabled: bool = False
    reminder_scheduler_interval_seconds: float = Field(default=60.0, gt=0)
    reminder_lead_minutes: int = Field(default=15, ge=1, le=1440)

    # General geofence safeguards. Session-specific radius, accuracy buffer and
    # maximum accuracy values are loaded from the session geofence snapshot.
    geofence_max_reading_age_seconds: float = Field(default=30, gt=0)
    geofence_max_future_skew_seconds: float = Field(default=5, ge=0)
    geofence_max_attempts: int = Field(default=3, ge=1)

    model_config = SettingsConfigDict(
        env_file=ENV_FILE_PATH,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    @field_validator(
        "db_uri",
        "db_host",
        "db_user",
        "redis_url",
        "dynamic_qr_hmac_secret",
        "face_verification_service_url",
        "expo_access_token",
        "keycloak_admin_base_url",
        "keycloak_admin_realm",
        "keycloak_admin_client_id",
        "keycloak_admin_client_secret",
        mode="before",
    )
    @classmethod
    def normalize_blank_text(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator(
        "keycloak_expected_issuer",
        "keycloak_jwks_url",
        mode="before",
    )
    @classmethod
    def normalize_blank_keycloak_url(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("keycloak_expected_issuer")
    @classmethod
    def strip_issuer_trailing_slash(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.rstrip("/")

    @field_validator("keycloak_admin_base_url")
    @classmethod
    def strip_admin_base_url_trailing_slash(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.rstrip("/")

    @field_validator("db_ssl_mode")
    @classmethod
    def validate_db_ssl_mode(cls, value: str) -> str:
        normalized = value.lower()
        if normalized not in SUPPORTED_SSL_MODES:
            raise ValueError("DB_SSL_MODE must be a valid PostgreSQL SSL mode")
        return normalized

    @field_validator("db_pool_max_size")
    @classmethod
    def validate_pool_size(cls, value: int, info) -> int:
        min_size = info.data.get("db_pool_min_size")
        if min_size is not None and value < min_size:
            raise ValueError("DB_POOL_MAX_SIZE must be greater than or equal to DB_POOL_MIN_SIZE")
        return value

    @model_validator(mode="after")
    def validate_database_configuration(self) -> "Settings":
        if self.push_worker_retry_max_seconds < self.push_worker_retry_base_seconds:
            raise ValueError(
                "PUSH_WORKER_RETRY_MAX_SECONDS must be greater than or equal "
                "to PUSH_WORKER_RETRY_BASE_SECONDS"
            )
        if self.db_uri:
            return self

        missing_variables = [
            variable_name
            for variable_name, value in (
                ("DB_HOST", self.db_host),
                ("DB_USER", self.db_user),
                ("DB_PASSWORD", self.db_password),
            )
            if not value
        ]

        if missing_variables:
            raise ValueError(
                "Database configuration is incomplete. Set DB_URI, or set "
                f"{', '.join(missing_variables)} in services/core-backend/.env. "
                "Copy .env.example and fill in the values locally.",
            )

        return self

    @property
    def keycloak_issuer_jwks_pairs(self) -> tuple[tuple[str, str], ...]:
        """(issuer, jwks_url) pairs this backend accepts, primary first.

        Each issuer carries its own JWKS source because different Keycloak
        deployments sign with different keys — trusting an issuer name alone
        is not enough to verify a token's signature. Deduplicated by issuer,
        first occurrence wins, order preserved.
        """
        pairs: list[tuple[str, str]] = []
        if self.keycloak_expected_issuer and self.keycloak_jwks_url:
            pairs.append((self.keycloak_expected_issuer, self.keycloak_jwks_url))

        if self.keycloak_additional_issuers:
            for raw in self.keycloak_additional_issuers.split(","):
                entry = raw.strip()
                if not entry:
                    continue
                if "|" not in entry:
                    raise ConfigurationError(
                        "KEYCLOAK_ADDITIONAL_ISSUERS entries must be "
                        '"issuer|jwks_url" pairs separated by commas.',
                    )
                issuer, jwks_url = entry.split("|", 1)
                issuer = issuer.strip().rstrip("/")
                jwks_url = jwks_url.strip()
                if not issuer or not jwks_url:
                    raise ConfigurationError(
                        "KEYCLOAK_ADDITIONAL_ISSUERS entries must include "
                        "both a non-empty issuer and a non-empty jwks_url.",
                    )
                pairs.append((issuer, jwks_url))

        seen: set[str] = set()
        deduped: list[tuple[str, str]] = []
        for issuer, jwks_url in pairs:
            if issuer in seen:
                continue
            seen.add(issuer)
            deduped.append((issuer, jwks_url))
        return tuple(deduped)

    @property
    def keycloak_accepted_issuers(self) -> tuple[str, ...]:
        """All issuer strings a token's `iss` claim may match."""
        return tuple(issuer for issuer, _ in self.keycloak_issuer_jwks_pairs)

    @property
    def keycloak_accepted_authorized_clients(self) -> tuple[str, ...]:
        if not self.keycloak_authorized_clients:
            return ()
        return tuple(
            dict.fromkeys(
                client
                for raw in self.keycloak_authorized_clients.split(",")
                if (client := raw.strip())
            )
        )

    @property
    def is_keycloak_configured(self) -> bool:
        return bool(self.keycloak_expected_issuer and self.keycloak_jwks_url)

    def require_keycloak_configuration(self) -> None:
        """Fail loudly when Keycloak validation settings are absent.

        Only variable names are reported; no configured value is included.
        """
        missing_variables = [
            variable_name
            for variable_name, value in (
                ("KEYCLOAK_EXPECTED_ISSUER", self.keycloak_expected_issuer),
                ("KEYCLOAK_JWKS_URL", self.keycloak_jwks_url),
                ("KEYCLOAK_AUDIENCE", self.keycloak_audience),
            )
            if not value
        ]

        if missing_variables:
            raise ConfigurationError(
                "Keycloak authentication is not configured. Set "
                f"{', '.join(missing_variables)} in services/core-backend/.env.",
            )

    def require_keycloak_admin_configuration(self) -> None:
        """Validate the dedicated service account without exposing values."""
        missing_variables = [
            variable_name
            for variable_name, value in (
                ("KEYCLOAK_ADMIN_BASE_URL", self.keycloak_admin_base_url),
                ("KEYCLOAK_ADMIN_REALM", self.keycloak_admin_realm),
                ("KEYCLOAK_ADMIN_CLIENT_ID", self.keycloak_admin_client_id),
                ("KEYCLOAK_ADMIN_CLIENT_SECRET", self.keycloak_admin_client_secret),
            )
            if not value
        ]
        if missing_variables:
            raise ConfigurationError(
                "Keycloak account provisioning is not configured. Set "
                f"{', '.join(missing_variables)} in services/core-backend/.env.",
            )


@lru_cache
def get_settings() -> Settings:
    return Settings()
