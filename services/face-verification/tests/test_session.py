import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from db.engine import create_database_engine, dispose_database_engine
from db.session import create_session_factory, session_scope
from tests.test_engine import create_settings


def test_creates_sessions_without_expiring_committed_models() -> None:
    engine = create_database_engine(create_settings())
    session_factory = create_session_factory(engine)

    session = session_factory()

    assert isinstance(session, AsyncSession)
    assert session.sync_session.expire_on_commit is False

    asyncio.run(session.close())
    asyncio.run(dispose_database_engine(engine))


def test_session_scope_yields_and_closes_session() -> None:
    session = AsyncMock(spec=AsyncSession)
    session_context = MagicMock()
    session_context.__aenter__ = AsyncMock(return_value=session)
    session_context.__aexit__ = AsyncMock(return_value=None)
    session_factory = MagicMock(return_value=session_context)

    async def use_session() -> None:
        async with session_scope(session_factory) as yielded_session:
            assert yielded_session is session

    asyncio.run(use_session())

    session.rollback.assert_not_awaited()
    session_context.__aexit__.assert_awaited_once()


def test_session_scope_rolls_back_and_reraises_failures() -> None:
    session = AsyncMock(spec=AsyncSession)
    session_context = MagicMock()
    session_context.__aenter__ = AsyncMock(return_value=session)
    session_context.__aexit__ = AsyncMock(return_value=None)
    session_factory = MagicMock(return_value=session_context)

    async def fail_inside_session() -> None:
        async with session_scope(session_factory):
            raise RuntimeError("database operation failed")

    with pytest.raises(RuntimeError, match="database operation failed"):
        asyncio.run(fail_inside_session())

    session.rollback.assert_awaited_once_with()
    session_context.__aexit__.assert_awaited_once()
