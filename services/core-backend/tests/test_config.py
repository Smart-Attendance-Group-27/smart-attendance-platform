import pytest

from core.config import ConfigurationError, Settings


def build_settings(**overrides) -> Settings:
    values = {
        "db_host": "localhost",
        "db_user": "postgres",
        "db_password": "password",
        "_env_file": None,
    }
    values.update(overrides)
    return Settings(**values)


def test_settings_normalizes_blank_db_uri() -> None:
    settings = build_settings(db_uri=" ")

    assert settings.db_uri is None


def test_settings_normalizes_blank_redis_url() -> None:
    settings = Settings(
        db_host="localhost",
        db_user="postgres",
        db_password="password",
        redis_url=" ",
        token_secret="secret",
        _env_file=None,
    )

    assert settings.redis_url is None


def test_settings_normalizes_blank_dynamic_qr_hmac_secret() -> None:
    settings = Settings(
        db_host="localhost",
        db_user="postgres",
        db_password="password",
        dynamic_qr_hmac_secret=" ",
        token_secret="secret",
        _env_file=None,
    )

    assert settings.dynamic_qr_hmac_secret is None


def test_settings_rejects_invalid_ssl_mode() -> None:
    with pytest.raises(ValueError) as error:
        build_settings(db_ssl_mode="invalid")

    assert "DB_SSL_MODE" in str(error.value)


def test_settings_defaults_to_a_small_development_pool() -> None:
    settings = build_settings()

    assert settings.db_pool_min_size == 1
    assert settings.db_pool_max_size == 5
    assert settings.db_command_timeout_seconds == 10
    assert settings.db_ssl_mode == "require"


def test_settings_defaults_to_the_initial_geofence_safeguards() -> None:
    settings = build_settings()

    assert settings.geofence_max_reading_age_seconds == 30
    assert settings.geofence_max_future_skew_seconds == 5
    assert settings.geofence_max_attempts == 3


@pytest.mark.parametrize(
    ("setting_name", "invalid_value"),
    [
        ("geofence_max_reading_age_seconds", 0),
        ("geofence_max_future_skew_seconds", -1),
        ("geofence_max_attempts", 0),
    ],
)
def test_settings_rejects_invalid_geofence_safeguards(
    setting_name: str,
    invalid_value: int,
) -> None:
    with pytest.raises(ValueError):
        build_settings(**{setting_name: invalid_value})


def test_settings_rejects_a_max_pool_smaller_than_the_min_pool() -> None:
    with pytest.raises(ValueError) as error:
        build_settings(db_pool_min_size=5, db_pool_max_size=2)

    assert "DB_POOL_MAX_SIZE" in str(error.value)


def test_db_uri_alone_is_enough() -> None:
    settings = Settings(
        db_uri="postgresql://user:password@host:5432/postgres",
        _env_file=None,
    )

    assert settings.db_uri is not None
    assert settings.db_host is None


def test_missing_database_configuration_names_the_variables_only() -> None:
    with pytest.raises(ValueError) as error:
        Settings(
            db_uri=None,
            db_host=None,
            db_user=None,
            db_password=None,
            _env_file=None,
        )

    message = str(error.value)
    assert "DB_HOST" in message
    assert "DB_USER" in message
    assert "DB_PASSWORD" in message


def test_settings_never_reveal_the_database_password() -> None:
    settings = build_settings(db_password="super-secret-value")

    assert "super-secret-value" not in repr(settings)
    assert "super-secret-value" not in str(settings)
    assert settings.db_password is not None
    assert settings.db_password.get_secret_value() == "super-secret-value"


def test_keycloak_configuration_is_detected() -> None:
    settings = build_settings(
        keycloak_expected_issuer="http://localhost:8080/realms/uniattend",
        keycloak_jwks_url="http://localhost:8080/realms/uniattend/protocol/openid-connect/certs",
    )

    assert settings.is_keycloak_configured
    settings.require_keycloak_configuration()


def test_missing_keycloak_configuration_names_the_variables_only() -> None:
    settings = build_settings()

    assert not settings.is_keycloak_configured

    with pytest.raises(ConfigurationError) as error:
        settings.require_keycloak_configuration()

    message = str(error.value)
    assert "KEYCLOAK_EXPECTED_ISSUER" in message
    assert "KEYCLOAK_JWKS_URL" in message


def test_issuer_trailing_slash_is_normalized() -> None:
    settings = build_settings(
        keycloak_expected_issuer="http://localhost:8080/realms/uniattend/",
    )

    assert settings.keycloak_expected_issuer == "http://localhost:8080/realms/uniattend"


def test_deprecated_token_secret_is_optional() -> None:
    settings = build_settings()

    assert settings.token_secret is None


def test_accepted_issuers_includes_only_the_primary_issuer_by_default() -> None:
    settings = build_settings(
        keycloak_expected_issuer="http://localhost:8080/realms/uniattend",
    )

    assert settings.keycloak_accepted_issuers == ("http://localhost:8080/realms/uniattend",)


def test_accepted_issuers_includes_additional_issuers() -> None:
    settings = build_settings(
        keycloak_expected_issuer="http://localhost:8080/realms/uniattend",
        keycloak_additional_issuers="http://10.0.0.5:8080/realms/uniattend/, http://10.0.0.6:8080/realms/uniattend",
    )

    assert settings.keycloak_accepted_issuers == (
        "http://localhost:8080/realms/uniattend",
        "http://10.0.0.5:8080/realms/uniattend",
        "http://10.0.0.6:8080/realms/uniattend",
    )


def test_accepted_issuers_deduplicates_repeated_values() -> None:
    settings = build_settings(
        keycloak_expected_issuer="http://localhost:8080/realms/uniattend",
        keycloak_additional_issuers="http://localhost:8080/realms/uniattend",
    )

    assert settings.keycloak_accepted_issuers == ("http://localhost:8080/realms/uniattend",)


def test_accepted_issuers_is_empty_when_nothing_is_configured() -> None:
    settings = build_settings()

    assert settings.keycloak_accepted_issuers == ()
