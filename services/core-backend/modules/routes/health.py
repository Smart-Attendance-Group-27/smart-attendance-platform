from fastapi import APIRouter, Request

from db.health import check_database_connection

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/db")
async def database_health(request: Request) -> dict[str, str]:
    await check_database_connection(request.app.state.db_pool)
    return {"status": "ok", "database": "connected"}
