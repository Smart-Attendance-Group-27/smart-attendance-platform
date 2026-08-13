from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from cache.redis import close_redis_client, create_redis_client
from core.config import get_settings
from db.pool import close_database_pool, create_database_pool
from modules.attendance_sessions.qr_session.route import router as qr_session_router
from modules.routes.health import router as health_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    app.state.settings = settings
    app.state.db_pool = await create_database_pool(settings)
    app.state.redis_client = await create_redis_client(settings)

    try:
        yield
    finally:
        await close_redis_client(app.state.redis_client)
        await close_database_pool(app.state.db_pool)


def create_app(*, enable_database: bool = True) -> FastAPI:
    app = FastAPI(
        title="UniAttend Core API",
        lifespan=lifespan if enable_database else None,
    )
    app.include_router(health_router)
    app.include_router(qr_session_router, prefix="/api/v1")
    return app


app = create_app()
