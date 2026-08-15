import os
from urllib.parse import urlparse
from uuid import UUID

import asyncpg
import pytest

from modules.attendance_sessions.active_sessions.service import (
    ActiveAttendanceSessionService,
)

TEST_DATABASE_ENV = "ACTIVE_SESSIONS_TEST_DATABASE_DSN"
ALLOWED_TEST_DATABASE_HOSTS = frozenset(
    {"localhost", "127.0.0.1", "::1", "host.docker.internal"},
)
USER_ID = UUID("20000000-0000-0000-0000-000000000011")
NEAR_SESSION_ID = UUID("40000000-0000-0000-0000-000000000001")
FAR_SESSION_ID = UUID("40000000-0000-0000-0000-000000000002")


@pytest.fixture
async def integration_pool() -> asyncpg.Pool:
    dsn = os.getenv(TEST_DATABASE_ENV)
    if not dsn:
        pytest.skip(f"Set {TEST_DATABASE_ENV} to run local PostgreSQL checks.")

    parsed_dsn = urlparse(dsn)
    if parsed_dsn.hostname not in ALLOWED_TEST_DATABASE_HOSTS:
        pytest.fail(
            f"{TEST_DATABASE_ENV} must target a local development database.",
            pytrace=False,
        )

    pool = await asyncpg.create_pool(
        dsn=dsn,
        min_size=1,
        max_size=2,
        statement_cache_size=0,
    )
    try:
        yield pool
    finally:
        await pool.close()


async def test_demo_student_discovers_both_open_geofence_sessions(
    integration_pool: asyncpg.Pool,
) -> None:
    sessions = await ActiveAttendanceSessionService().list_for_user(
        integration_pool,
        USER_ID,
    )

    assert [session.id for session in sessions] == [NEAR_SESSION_ID, FAR_SESSION_ID]
    assert [session.session_title for session in sessions] == [
        "Geofence Demo - Near Centre",
        "Geofence Demo - Far Centre",
    ]
    assert all(session.requires_geofence for session in sessions)
