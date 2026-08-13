from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.routes.health import router as health_router
from core.config import get_settings
from db.pool import close_database_pool, create_database_pool


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()

    app.state.settings = settings
    app.state.db_pool = await create_database_pool(settings)

    try:
        yield
    finally:
        await close_database_pool(app.state.db_pool)


def create_app(*, enable_database: bool = True) -> FastAPI:
    app = FastAPI(
        title="UniAttend Face Verification Service",
        version="0.1.0",
        lifespan=lifespan if enable_database else None,
    )

    app.include_router(health_router)

    return app


app = create_app()