import base64
import binascii
from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


ENV_FILE_PATH = Path(__file__).resolve().parents[1] / ".env"


class Settings(BaseSettings):
    app_name: str = "UniAttend Face Verification Service"
    app_environment: str = "development"

    db_uri: str | None = None
    db_host: str
    db_port: int = 5432
    db_name: str = "postgres"
    db_user: str
    db_password: SecretStr
    db_ssl_mode: str = "require"

    db_pool_min_size: int = Field(default=1, ge=1)
    db_pool_max_size: int = Field(default=5, ge=1)
    db_command_timeout_seconds: float = Field(default=10, gt=0)

    face_embedding_encryption_key: SecretStr

    face_model_name: str = "buffalo_l"
    face_model_version: str = "1"
    face_execution_provider: str = "CPUExecutionProvider"
    face_context_id: int = -1
    face_detection_size: int = Field(default=640, ge=1)
    face_minimum_detection_confidence: float = Field(default=0.60, ge=0,le=1,)
    face_max_concurrent_inferences: int = Field(default=1, ge=1)

    # The Core Backend owns Keycloak validation and student-profile lookup.
    core_api_url: str = "http://localhost:8000"
    core_api_timeout_seconds: float = Field(default=5, gt=0)

    model_config = SettingsConfigDict(
        env_file=ENV_FILE_PATH,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    @field_validator("db_uri", mode="before")
    @classmethod
    def normalize_blank_db_uri(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None

        return value

    @field_validator("core_api_url")
    @classmethod
    def normalize_core_api_url(cls, value: str) -> str:
        normalized = value.strip().rstrip("/")

        if not normalized:
            raise ValueError("CORE_API_URL cannot be blank")

        return normalized

    @field_validator("db_ssl_mode")
    @classmethod
    def validate_db_ssl_mode(cls, value: str) -> str:
        normalized = value.lower()

        allowed_modes = {
            "disable",
            "allow",
            "prefer",
            "require",
            "verify-ca",
            "verify-full",
        }

        if normalized not in allowed_modes:
            raise ValueError("DB_SSL_MODE must be a valid PostgreSQL SSL mode")

        return normalized

    @field_validator("face_embedding_encryption_key", mode="before")
    @classmethod
    def validate_face_embedding_encryption_key(cls, value: object) -> object:
            
            if isinstance(value, SecretStr):
                key = value.get_secret_value().strip()

            elif isinstance(value, str):
                key = value.strip()

            else:
                raise ValueError("FACE_EMBEDDING_ENCRYPTION_KEY must be a string")

            if not key:
                raise ValueError("FACE_EMBEDDING_ENCRYPTION_KEY cannot be empty")

            try:
                decoded = base64.urlsafe_b64decode(key.encode("utf-8"))

            except (binascii.Error, ValueError) as error:
                raise ValueError("FACE_EMBEDDING_ENCRYPTION_KEY must be valid urlsafe base64") from error

            if len(decoded) != 32:
                raise ValueError("FACE_EMBEDDING_ENCRYPTION_KEY must decode to exactly 32 bytes")

            return key

    @field_validator("face_model_name","face_model_version","face_execution_provider",)
    @classmethod
    def validate_non_blank_face_setting(cls, value: str) -> str:
        normalized = value.strip()

        if not normalized:
            raise ValueError("Face model settings cannot be blank")

        return normalized

@lru_cache
def get_settings() -> Settings:
    return Settings()
