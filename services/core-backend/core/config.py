from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


ENV_FILE_PATH = Path(__file__).resolve().parents[1] / ".env"


class Settings(BaseSettings):
    app_name: str = "UniAttend Core API"
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

    token_secret: SecretStr

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

    @field_validator("db_ssl_mode")
    @classmethod
    def validate_db_ssl_mode(cls, value: str) -> str:
        normalized = value.lower()
        if normalized not in {"disable", "allow", "prefer", "require", "verify-ca", "verify-full"}:
            raise ValueError("DB_SSL_MODE must be a valid PostgreSQL SSL mode")
        return normalized

    @field_validator("db_pool_max_size")
    @classmethod
    def validate_pool_size(cls, value: int, info) -> int:
        min_size = info.data.get("db_pool_min_size")
        if min_size is not None and value < min_size:
            raise ValueError("DB_POOL_MAX_SIZE must be greater than or equal to DB_POOL_MIN_SIZE")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
