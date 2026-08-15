import ssl

from sqlalchemy.engine import URL, make_url
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from core.config import Settings

# internal helper
def _build_database_url(settings: Settings) -> URL:
    if settings.db_uri:
        configured_url = make_url(settings.db_uri)
        query = dict(configured_url.query)
        query.pop("sslmode", None)

        return configured_url.set(
            drivername="postgresql+asyncpg",
            query=query,
        )

    return URL.create(
        drivername="postgresql+asyncpg",
        username=settings.db_user,
        password=settings.db_password.get_secret_value(),
        host=settings.db_host,
        port=settings.db_port,
        database=settings.db_name,
    )


def _build_ssl_context(settings: Settings) -> ssl.SSLContext | bool:
    if settings.db_ssl_mode == "disable":
        return False

    # creates a standard TLS configuration
    context = ssl.create_default_context()

    if settings.db_ssl_mode in {"allow", "prefer", "require"}:
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

    # returns the completed SSL configuration to the engine
    return context


def create_database_engine(settings: Settings) -> AsyncEngine:
    if settings.db_pool_max_size < settings.db_pool_min_size:
        raise ValueError(
            "DB_POOL_MAX_SIZE must be greater than or equal to "
            "DB_POOL_MIN_SIZE"
        )

    return create_async_engine(
        _build_database_url(settings),
        pool_size=settings.db_pool_min_size,
        max_overflow=(
            settings.db_pool_max_size - settings.db_pool_min_size
        ),
        pool_timeout=settings.db_command_timeout_seconds,
        pool_pre_ping=True,

        connect_args={
            "ssl": _build_ssl_context(settings),
            "timeout": settings.db_command_timeout_seconds,

            # default timeout for database operations
            "command_timeout": settings.db_command_timeout_seconds,
            "prepared_statement_cache_size": 0,
            "statement_cache_size": 0,
        },
    )


async def dispose_database_engine(engine: AsyncEngine | None) -> None:
    if engine is not None:
        await engine.dispose()
