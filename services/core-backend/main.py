from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from core.config import get_settings
from db.pool import close_database_pool, create_database_pool
from modules.routes.health import router as health_router


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
        title="UniAttend Core API",
        lifespan=lifespan if enable_database else None,
    )
    app.include_router(health_router)
    return app


app = create_app()
