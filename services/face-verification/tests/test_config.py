from core.config import Settings


def test_database_settings_accept_explicit_values() -> None:
    settings = Settings(
        db_host="localhost",
        db_port=5432,
        db_name="postgres",
        db_user="face_service",
        db_password="test-password",
        db_ssl_mode="disable",
        face_embedding_encryption_key="MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=",
        _env_file=None,
    )

    assert settings.db_host == "localhost"
    assert settings.db_port == 5432
    assert settings.db_name == "postgres"
    assert settings.db_user == "face_service"
    assert settings.db_password.get_secret_value() == "test-password"
    assert settings.db_ssl_mode == "disable"