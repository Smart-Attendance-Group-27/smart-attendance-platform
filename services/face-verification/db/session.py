from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
)

# Ensure all ORM tables are registered in shared metadata before sessions are used.
import models


AsyncSessionFactory = async_sessionmaker[AsyncSession]


def create_session_factory(engine: AsyncEngine) -> AsyncSessionFactory:
    return async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        autoflush=False,
        expire_on_commit=False,
    )


@asynccontextmanager
async def session_scope(session_factory: AsyncSessionFactory,) -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
