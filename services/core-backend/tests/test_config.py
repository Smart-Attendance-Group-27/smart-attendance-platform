from core.config import Settings


def test_settings_normalizes_blank_db_uri() -> None:
    settings = Settings(
        db_uri=" ",
        db_host="localhost",
        db_user="postgres",
        db_password="password",
        token_secret="secret",
    )

    assert settings.db_uri is None


def test_settings_normalizes_blank_redis_url() -> None:
    settings = Settings(
        db_host="localhost",
        db_user="postgres",
        db_password="password",
        redis_url=" ",
        token_secret="secret",
    )

    assert settings.redis_url is None


def test_settings_rejects_invalid_ssl_mode() -> None:
    try:
        Settings(
            db_host="localhost",
            db_user="postgres",
            db_password="password",
            db_ssl_mode="invalid",
            token_secret="secret",
        )
    except ValueError as error:
        assert "DB_SSL_MODE" in str(error)
    else:
        raise AssertionError("invalid DB_SSL_MODE should fail validation")
