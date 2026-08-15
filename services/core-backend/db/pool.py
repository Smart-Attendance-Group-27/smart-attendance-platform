import ssl

import asyncpg

from core.config import ConfigurationError, Settings


def _build_ssl_context(settings: Settings) -> ssl.SSLContext | bool:
    if settings.db_ssl_mode == "disable":
        return False

    context = ssl.create_default_context()
    if settings.db_ssl_mode in {"allow", "prefer", "require"}:
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

    return context


async def create_database_pool(settings: Settings) -> asyncpg.Pool:
    ssl_context = _build_ssl_context(settings)

    # DB_URI wins when present; the individual DB_* fields are the fallback.
    if settings.db_uri:
        return await asyncpg.create_pool(
            dsn=settings.db_uri,
            min_size=settings.db_pool_min_size,
            max_size=settings.db_pool_max_size,
            command_timeout=settings.db_command_timeout_seconds,
            ssl=ssl_context,
            statement_cache_size=0,
        )

    if not settings.db_host or not settings.db_user or settings.db_password is None:
        raise ConfigurationError(
            "Database configuration is incomplete. Set DB_URI, or set DB_HOST, "
            "DB_USER and DB_PASSWORD in services/core-backend/.env.",
        )

    return await asyncpg.create_pool(
        host=settings.db_host,
        port=settings.db_port,
        database=settings.db_name,
        user=settings.db_user,
        password=settings.db_password.get_secret_value(),
        min_size=settings.db_pool_min_size,
        max_size=settings.db_pool_max_size,
        command_timeout=settings.db_command_timeout_seconds,
        ssl=ssl_context,
        statement_cache_size=0,
    )


async def close_database_pool(pool: asyncpg.Pool | None) -> None:
    if pool is not None:
        await pool.close()
