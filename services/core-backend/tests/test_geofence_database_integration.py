import asyncio
import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from urllib.parse import urlparse
from uuid import UUID, uuid4

import asyncpg
import pytest

from modules.attendance_verification.geofence.policy import GeofenceValidationPolicy
from modules.attendance_verification.geofence.repository import GeofenceRepository
from modules.attendance_verification.geofence.service import GeofenceValidationService
from modules.attendance_verification.geofence.types import (
    GeofenceDecision,
    GeofenceReading,
)

TEST_DATABASE_ENV = "GEOFENCE_TEST_DATABASE_DSN"
ALLOWED_TEST_DATABASE_HOSTS = frozenset(
    {"localhost", "127.0.0.1", "::1", "host.docker.internal"},
)
SOURCE_SESSION_ID = UUID("40000000-0000-0000-0000-000000000001")
USER_ID = UUID("20000000-0000-0000-0000-000000000011")
STUDENT_ID = UUID("23000000-0000-0000-0000-000000000001")
COURSE_ENROLMENT_ID = UUID("39000000-0000-0000-0000-000000000001")
CURRENT_TIME = datetime(2030, 1, 15, 5, 30, tzinfo=UTC)


@dataclass(frozen=True)
class DatabaseCase:
    session_id: UUID


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
        min_size=2,
        max_size=4,
        statement_cache_size=0,
    )
    try:
        yield pool
    finally:
        await pool.close()


@pytest.fixture
async def database_case(integration_pool: asyncpg.Pool):
    session_id = uuid4()
    session_student_id = uuid4()

    async with integration_pool.acquire() as connection:
        inserted_session_id = await connection.fetchval(
            """
            INSERT INTO attendance_session.sessions (
                id,
                course_offering_id,
                timetable_entry_id,
                timetable_exception_id,
                created_by,
                session_title,
                session_type,
                scheduled_start_at,
                scheduled_end_at,
                check_in_opens_at,
                check_in_closes_at,
                late_after_at,
                status,
                requires_face_verification,
                requires_geofence,
                requires_qr,
                activated_at,
                closed_at,
                cancelled_at,
                cancellation_reason,
                created_at,
                updated_at
            )
            SELECT
                $1,
                course_offering_id,
                timetable_entry_id,
                timetable_exception_id,
                created_by,
                'Geofence Repository Integration Test',
                session_type,
                $2::timestamptz - INTERVAL '5 minutes',
                $2::timestamptz + INTERVAL '1 hour',
                $2::timestamptz - INTERVAL '2 minutes',
                $2::timestamptz + INTERVAL '30 minutes',
                $2::timestamptz + INTERVAL '15 minutes',
                'active',
                true,
                true,
                false,
                $2::timestamptz - INTERVAL '2 minutes',
                NULL,
                NULL,
                NULL,
                $2::timestamptz,
                $2::timestamptz
            FROM attendance_session.sessions
            WHERE id = $3
            RETURNING id
            """,
            session_id,
            CURRENT_TIME,
            SOURCE_SESSION_ID,
        )
        if inserted_session_id is None:
            pytest.fail(
                "The local geofence demo seed is required for integration tests.",
                pytrace=False,
            )

        await connection.execute(
            """
            INSERT INTO attendance_session.session_geofences (
                session_id,
                centre_latitude,
                centre_longitude,
                radius_m,
                accuracy_buffer_m,
                maximum_allowed_accuracy_m,
                created_at,
                updated_at
            )
            VALUES ($1, 6.795132, 79.900421, 60, 10, 50, $2, $2)
            """,
            session_id,
            CURRENT_TIME,
        )
        await connection.execute(
            """
            INSERT INTO attendance_session.session_students (
                id,
                session_id,
                student_id,
                course_enrolment_id,
                created_at
            )
            VALUES ($1, $2, $3, $4, $5)
            """,
            session_student_id,
            session_id,
            STUDENT_ID,
            COURSE_ENROLMENT_ID,
            CURRENT_TIME,
        )

    try:
        yield DatabaseCase(session_id=session_id)
    finally:
        async with integration_pool.acquire() as connection:
            await connection.execute(
                """
                DELETE FROM attendance_verification.geofence_validation_attempts
                WHERE verification_attempt_id IN (
                    SELECT id
                    FROM attendance_verification.verification_attempts
                    WHERE session_id = $1
                )
                """,
                session_id,
            )
            await connection.execute(
                "DELETE FROM attendance_verification.attendance_records WHERE session_id = $1",
                session_id,
            )
            await connection.execute(
                "DELETE FROM attendance_verification.verification_attempts WHERE session_id = $1",
                session_id,
            )
            await connection.execute(
                "DELETE FROM attendance_session.session_students WHERE session_id = $1",
                session_id,
            )
            await connection.execute(
                "DELETE FROM attendance_session.session_geofences WHERE session_id = $1",
                session_id,
            )
            await connection.execute(
                "DELETE FROM attendance_session.sessions WHERE id = $1",
                session_id,
            )


def build_service() -> GeofenceValidationService:
    return GeofenceValidationService(
        policy=GeofenceValidationPolicy(
            max_reading_age_seconds=30,
            max_future_skew_seconds=5,
        ),
        max_attempts=3,
        clock=lambda: CURRENT_TIME,
    )


def build_reading(*, accuracy_m: float) -> GeofenceReading:
    return GeofenceReading(
        latitude=6.795132,
        longitude=79.900421,
        accuracy_m=accuracy_m,
        captured_at=CURRENT_TIME - timedelta(seconds=1),
        mocked=False,
    )


async def test_concurrent_requests_share_one_overall_attempt_and_unique_numbers(
    integration_pool: asyncpg.Pool,
    database_case: DatabaseCase,
) -> None:
    reading = build_reading(accuracy_m=55.0)

    outcomes = await asyncio.gather(
        build_service().validate_attempt(
            integration_pool,
            USER_ID,
            database_case.session_id,
            reading,
        ),
        build_service().validate_attempt(
            integration_pool,
            USER_ID,
            database_case.session_id,
            reading,
        ),
    )

    assert sorted(outcome.attempt_number for outcome in outcomes) == [1, 2]
    assert all(
        outcome.result.decision is GeofenceDecision.RETRY_REQUIRED
        for outcome in outcomes
    )

    async with integration_pool.acquire() as connection:
        counts = await connection.fetchrow(
            """
            SELECT
                count(DISTINCT verification.id) AS verification_attempts,
                count(geofence.id) AS geofence_attempts,
                count(DISTINCT geofence.attempt_number) AS distinct_numbers
            FROM attendance_verification.verification_attempts AS verification
            LEFT JOIN attendance_verification.geofence_validation_attempts AS geofence
                ON geofence.verification_attempt_id = verification.id
            WHERE verification.session_id = $1
              AND verification.student_id = $2
            """,
            database_case.session_id,
            STUDENT_ID,
        )

    assert counts["verification_attempts"] == 1
    assert counts["geofence_attempts"] == 2
    assert counts["distinct_numbers"] == 2


async def test_pass_persists_derived_data_without_creating_attendance(
    integration_pool: asyncpg.Pool,
    database_case: DatabaseCase,
) -> None:
    outcome = await build_service().validate_attempt(
        integration_pool,
        USER_ID,
        database_case.session_id,
        build_reading(accuracy_m=5.0),
    )

    assert outcome.result.decision is GeofenceDecision.PASSED

    async with integration_pool.acquire() as connection:
        stored = await connection.fetchrow(
            """
            SELECT
                verification.status AS verification_status,
                geofence.accuracy_m,
                geofence.distance_from_centre_m,
                geofence.validation_status,
                geofence.failure_reason,
                (
                    SELECT count(*)
                    FROM attendance_verification.attendance_records
                    WHERE session_id = $1
                      AND student_id = $2
                ) AS attendance_records
            FROM attendance_verification.verification_attempts AS verification
            JOIN attendance_verification.geofence_validation_attempts AS geofence
                ON geofence.verification_attempt_id = verification.id
            WHERE verification.session_id = $1
              AND verification.student_id = $2
            """,
            database_case.session_id,
            STUDENT_ID,
        )

    assert stored["verification_status"] == "in_progress"
    assert stored["accuracy_m"] == Decimal("5.0")
    assert stored["distance_from_centre_m"] == Decimal("0.0")
    assert stored["validation_status"] == "passed"
    assert stored["failure_reason"] is None
    assert stored["attendance_records"] == 0


async def test_repository_snapshot_does_not_follow_classroom_changes(
    integration_pool: asyncpg.Pool,
    database_case: DatabaseCase,
) -> None:
    async with integration_pool.acquire() as connection:
        transaction = connection.transaction()
        await transaction.start()
        try:
            classroom_id = await connection.fetchval(
                """
                SELECT timetable.classroom_id
                FROM attendance_session.sessions AS session
                JOIN academic.timetable_entries AS timetable
                    ON timetable.id = session.timetable_entry_id
                WHERE session.id = $1
                """,
                database_case.session_id,
            )
            await connection.execute(
                """
                UPDATE academic.classrooms
                SET latitude = 7.5,
                    longitude = 80.5,
                    default_geofence_radius_m = 500
                WHERE id = $1
                """,
                classroom_id,
            )

            snapshot = await GeofenceRepository().lock_session_geofence(
                connection,
                database_case.session_id,
            )

            assert snapshot is not None
            assert snapshot.centre_latitude == Decimal("6.795132")
            assert snapshot.centre_longitude == Decimal("79.900421")
            assert snapshot.radius_m == Decimal("60")
        finally:
            await transaction.rollback()
