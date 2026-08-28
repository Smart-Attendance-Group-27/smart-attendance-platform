import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncEngine

from adapters.core_api_student_profile_client import (
    CoreApiStudentProfileClient,
)
from adapters.insightface_engine import create_configured_insightface_engine
from api.routes.attendance import router as attendance_router
from api.routes.health import router as health_router
from api.routes.readiness import router as readiness_router
from core.config import get_settings
from db.engine import create_database_engine, dispose_database_engine
from db.session import create_session_factory


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    engine: AsyncEngine | None = None
    core_api_client: CoreApiStudentProfileClient | None = None

    app.state.settings = settings

    try:
        engine = create_database_engine(settings)
        app.state.db_engine = engine

        app.state.db_session_factory = create_session_factory(engine)

        core_api_client = CoreApiStudentProfileClient(base_url=settings.core_api_url,timeout_seconds=settings.core_api_timeout_seconds,)

        app.state.core_api_student_profile_client = core_api_client

        app.state.face_engine = await asyncio.to_thread(
            create_configured_insightface_engine,
            settings,
        )
        yield

    finally:
        if core_api_client is not None:
            await core_api_client.close()

        await dispose_database_engine(engine)


def create_app(*, enable_database: bool = True) -> FastAPI:
    app = FastAPI(
        title="UniAttend Face Verification Service",
        version="0.1.0",
        lifespan=lifespan if enable_database else None,
    )

    app.include_router(health_router)
    app.include_router(attendance_router)
    app.include_router(readiness_router)

    return app


app = create_app()
