import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from core.config import get_settings
from db.pool import close_database_pool, create_database_pool
from modules.academic.student_profile.route import router as student_profile_router
from modules.attendance_sessions.qr_session.route import router as qr_session_router
from modules.identity.auth.route import router as auth_router
from modules.routes.health import router as health_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    app.state.settings = settings

    if not settings.is_keycloak_configured:
        logger.warning(
            "Keycloak validation is not configured. Set KEYCLOAK_EXPECTED_ISSUER "
            "and KEYCLOAK_JWKS_URL; authenticated endpoints will return 503.",
        )

    app.state.db_pool = await create_database_pool(settings)
    # Deliberately no connection details here: the URI, user and password must
    # never reach the logs.
    logger.info(
        "Database pool ready (ssl_mode=%s, pool=%s-%s)",
        settings.db_ssl_mode,
        settings.db_pool_min_size,
        settings.db_pool_max_size,
    )

    try:
        yield
    finally:
        await close_database_pool(app.state.db_pool)


def create_app(*, enable_database: bool = True) -> FastAPI:
    app = FastAPI(
        title="UniAttend Core API",
        lifespan=lifespan if enable_database else None,
    )
    app.include_router(health_router)
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(student_profile_router, prefix="/api/v1")
    app.include_router(qr_session_router, prefix="/api/v1")
    return app


app = create_app()
