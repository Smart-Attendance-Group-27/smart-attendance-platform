from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncEngine

from api.routes.health import router as health_router
from api.routes.readiness import router as readiness_router
from core.config import get_settings
from db.engine import create_database_engine, dispose_database_engine
from db.session import create_session_factory


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    engine: AsyncEngine | None = None

    app.state.settings = settings

    try:
        engine = create_database_engine(settings)
        app.state.db_engine = engine
        app.state.db_session_factory = create_session_factory(engine)

        yield
    finally:
        await dispose_database_engine(engine)


def create_app(*, enable_database: bool = True) -> FastAPI:
    app = FastAPI(
        title="UniAttend Face Verification Service",
        version="0.1.0",
        lifespan=lifespan if enable_database else None,
    )

    app.include_router(health_router)
    app.include_router(readiness_router)

    return app


app = create_app()
