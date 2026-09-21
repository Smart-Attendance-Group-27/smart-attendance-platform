"""A whole lecture, run through the real services against a real PostgreSQL.

Every other attendance test uses fakes, so none of them ever runs the SQL. This
one does: geofence check-ins, QR evidence, a manual record, the close-time race
and finalization, all through the same service factory production uses.

It needs a local database with the baseline, the seed and every migration
applied. It creates one session of its own and deletes it afterwards, and it
refuses to run against anything that isn't a local database.
"""

import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from urllib.parse import urlparse
from uuid import UUID, uuid4

import asyncpg
import pytest

from modules.attendance_sessions.lecturer_sessions.exception import SessionAlreadyClosedError
from modules.attendance_sessions.lecturer_sessions.route import get_lecturer_session_service
from modules.attendance_verification.attendance_state import FinalAttendanceStatus
from modules.attendance_verification.geofence.policy import GeofenceValidationPolicy
from modules.attendance_verification.geofence.service import GeofenceValidationService
from modules.attendance_verification.geofence.types import GeofenceReading
from modules.attendance_verification.manual_attendance.service import ManualAttendanceService

TEST_DATABASE_ENV = "ATTENDANCE_LIFECYCLE_TEST_DATABASE_DSN"
ALLOWED_TEST_DATABASE_HOSTS = frozenset(
    {"localhost", "127.0.0.1", "::1", "host.docker.internal"},
)

LECTURER_USER_ID = UUID("20000000-0000-0000-0000-000000000002")
COURSE_OFFERING_ID = UUID("37000000-0000-0000-0000-000000000001")

CENTRE_LATITUDE = 6.795132
CENTRE_LONGITUDE = 79.900421

# The seeded students, as (profile id, user id).
STUDENT_ON_TIME_WITH_QR = (
    UUID("23000000-0000-0000-0000-000000000001"),
    UUID("20000000-0000-0000-0000-000000000011"),
)
STUDENT_ON_TIME_MISSED_QR = (
    UUID("23000000-0000-0000-0000-000000000002"),
    UUID("20000000-0000-0000-0000-000000000012"),
)
STUDENT_NEVER_ARRIVED = (
    UUID("23000000-0000-0000-0000-000000000003"),
    UUID("20000000-0000-0000-0000-000000000013"),
)
STUDENT_MARKED_BY_HAND = (
    UUID("23000000-0000-0000-0000-000000000004"),
    UUID("20000000-0000-0000-0000-000000000014"),
)
STUDENT_EARNED_BUT_UNWRITTEN = (
    UUID("23000000-0000-0000-0000-000000000005"),
    UUID("20000000-0000-0000-0000-000000000015"),
)
STUDENT_LATE_WITH_QR = (
    UUID("23000000-0000-0000-0000-000000000006"),
    UUID("20000000-0000-0000-0000-000000000016"),
)
ROSTER = [
    STUDENT_ON_TIME_WITH_QR,
    STUDENT_ON_TIME_MISSED_QR,
    STUDENT_NEVER_ARRIVED,
    STUDENT_MARKED_BY_HAND,
    STUDENT_EARNED_BUT_UNWRITTEN,
    STUDENT_LATE_WITH_QR,
]


@dataclass
class Lecture:
    session_id: UUID
    batch_id: UUID
    attempt_ids: dict[UUID, UUID]


@pytest.fixture
async def pool() -> asyncpg.Pool:
    dsn = os.getenv(TEST_DATABASE_ENV)
    if not dsn:
        pytest.skip(f"Set {TEST_DATABASE_ENV} to run the lifecycle check on a local PostgreSQL.")

    if urlparse(dsn).hostname not in ALLOWED_TEST_DATABASE_HOSTS:
        pytest.fail(f"{TEST_DATABASE_ENV} must target a local development database.", pytrace=False)

    database_pool = await asyncpg.create_pool(
        dsn=dsn,
        min_size=1,
        max_size=3,
        statement_cache_size=0,
    )
    try:
        yield database_pool
    finally:
        await database_pool.close()


def geofence_service(at: datetime) -> GeofenceValidationService:
    return GeofenceValidationService(
        policy=GeofenceValidationPolicy(max_reading_age_seconds=30, max_future_skew_seconds=5),
        max_attempts=3,
        clock=lambda: at,
    )


async def check_in_at(pool: asyncpg.Pool, session_id: UUID, student, at: datetime):
    return await geofence_service(at).validate_attempt(
        pool,
        student[1],
        session_id,
        GeofenceReading(
            latitude=CENTRE_LATITUDE,
            longitude=CENTRE_LONGITUDE,
            accuracy_m=5.0,
            captured_at=at,
        ),
    )


async def attempt_id_of(pool: asyncpg.Pool, session_id: UUID, student) -> UUID:
    return await pool.fetchval(
        """
        SELECT id FROM attendance_verification.verification_attempts
        WHERE session_id = $1 AND student_id = $2
        """,
        session_id,
        student[0],
    )


async def remove_lecture(pool: asyncpg.Pool, session_id: UUID) -> None:
    async with pool.acquire() as connection, connection.transaction():
        attempts = "SELECT id FROM attendance_verification.verification_attempts WHERE session_id = $1"
        batches = "SELECT id FROM attendance_session.qr_token_batches WHERE session_id = $1"
        await connection.execute(
            f"DELETE FROM attendance_verification.qr_validation_attempts "
            f"WHERE verification_attempt_id IN ({attempts})",
            session_id,
        )
        await connection.execute(
            f"DELETE FROM attendance_session.qr_tokens WHERE qr_batch_id IN ({batches})",
            session_id,
        )
        await connection.execute(
            f"DELETE FROM attendance_verification.geofence_validation_attempts "
            f"WHERE verification_attempt_id IN ({attempts})",
            session_id,
        )
        await connection.execute(
            f"DELETE FROM attendance_verification.manual_reviews "
            f"WHERE verification_attempt_id IN ({attempts})",
            session_id,
        )
        for statement in (
            "DELETE FROM attendance_verification.verification_attempts WHERE session_id = $1",
            "DELETE FROM attendance_verification.attendance_records WHERE session_id = $1",
            "DELETE FROM attendance_session.qr_token_batches WHERE session_id = $1",
            "DELETE FROM attendance_session.session_students WHERE session_id = $1",
            "DELETE FROM attendance_session.session_geofences WHERE session_id = $1",
            "DELETE FROM audit.audit_logs WHERE entity_id = $1",
            "DELETE FROM attendance_session.sessions WHERE id = $1",
        ):
            await connection.execute(statement, session_id)


@pytest.fixture
async def lecture(pool: asyncpg.Pool):
    """A running lecture, up to the moment before the lecturer closes it.

    Timeline (T is now): the session opens at T-60m, the late threshold is
    T-40m, a QR batch goes live at T-20m. Each student's story is the name of
    their constant above.
    """

    now = datetime.now(UTC).replace(microsecond=0)
    session_id = uuid4()
    batch_id = uuid4()

    async with pool.acquire() as connection, connection.transaction():
        await connection.execute(
            """
            INSERT INTO attendance_session.sessions (
                id, course_offering_id, timetable_entry_id, timetable_exception_id,
                created_by, session_title, session_type,
                scheduled_start_at, scheduled_end_at,
                check_in_opens_at, check_in_closes_at, late_after_at,
                status, requires_face_verification, requires_geofence, requires_qr,
                activated_at, closed_at, cancelled_at, cancellation_reason,
                created_at, updated_at
            )
            VALUES (
                $1, $2, NULL, NULL,
                $3, 'Lifecycle integration check', 'lecture',
                $4, $5,
                $6, $7, $8,
                'active', false, true, true,
                $6, NULL, NULL, NULL,
                now(), now()
            )
            """,
            session_id,
            COURSE_OFFERING_ID,
            LECTURER_USER_ID,
            now - timedelta(minutes=60),
            now + timedelta(minutes=60),
            now - timedelta(minutes=60),
            now + timedelta(minutes=30),
            now - timedelta(minutes=40),
        )
        await connection.execute(
            """
            INSERT INTO attendance_session.session_geofences (
                session_id, centre_latitude, centre_longitude, radius_m,
                accuracy_buffer_m, maximum_allowed_accuracy_m, created_at, updated_at
            )
            VALUES ($1, $2, $3, 70, 10, 50, now(), now())
            """,
            session_id,
            CENTRE_LATITUDE,
            CENTRE_LONGITUDE,
        )
        await connection.execute(
            """
            INSERT INTO attendance_session.session_students (
                id, session_id, student_id, course_enrolment_id, created_at
            )
            SELECT gen_random_uuid(), $1, enrolment.student_id, enrolment.id, now()
            FROM academic.course_enrolments AS enrolment
            WHERE enrolment.course_offering_id = $2 AND enrolment.student_id = ANY($3::uuid[])
            """,
            session_id,
            COURSE_OFFERING_ID,
            [student[0] for student in ROSTER],
        )

    try:
        # Real check-ins, each with the clock set to when that student arrived.
        for student, minutes_ago in (
            (STUDENT_ON_TIME_WITH_QR, 55),
            (STUDENT_ON_TIME_MISSED_QR, 50),
            (STUDENT_LATE_WITH_QR, 30),
        ):
            outcome = await check_in_at(
                pool,
                session_id,
                student,
                now - timedelta(minutes=minutes_ago),
            )
            assert outcome.initial_check_in is not None, "geofence should have checked them in"

        # The race: this student finished their last step, but nothing had
        # written the check-in yet when the lecturer closed the session.
        earned_attempt = uuid4()
        earned_at = now - timedelta(minutes=5)
        async with pool.acquire() as connection, connection.transaction():
            await connection.execute(
                """
                INSERT INTO attendance_verification.verification_attempts (
                    id, session_id, student_id, status, started_at
                )
                VALUES ($1, $2, $3, 'in_progress', $4)
                """,
                earned_attempt,
                session_id,
                STUDENT_EARNED_BUT_UNWRITTEN[0],
                earned_at,
            )
            await connection.execute(
                """
                INSERT INTO attendance_verification.geofence_validation_attempts (
                    id, verification_attempt_id, attempt_number, accuracy_m,
                    distance_from_centre_m, validation_status, failure_reason,
                    captured_at, validated_at
                )
                VALUES ($1, $2, 1, 5, 2, 'passed', NULL, $3, $3)
                """,
                uuid4(),
                earned_attempt,
                earned_at,
            )
            await connection.execute(
                """
                INSERT INTO attendance_session.qr_token_batches (
                    id, session_id, mode, refresh_interval_seconds, issued_by,
                    status, activated_at, expires_at, deactivated_at, created_at
                )
                VALUES ($1, $2, 'dynamic', 10, $3, 'active', $4, $5, NULL, $4)
                """,
                batch_id,
                session_id,
                LECTURER_USER_ID,
                now - timedelta(minutes=20),
                now + timedelta(minutes=30),
            )

        for student, minutes_ago in ((STUDENT_ON_TIME_WITH_QR, 19), (STUDENT_LATE_WITH_QR, 18)):
            await pool.execute(
                """
                INSERT INTO attendance_verification.qr_validation_attempts (
                    id, verification_attempt_id, qr_token_id, attempt_number,
                    validation_status, failure_reason, validated_at, qr_batch_id
                )
                VALUES ($1, $2, NULL, 1, 'accepted', NULL, $3, $4)
                """,
                uuid4(),
                await attempt_id_of(pool, session_id, student),
                now - timedelta(minutes=minutes_ago),
                batch_id,
            )

        await ManualAttendanceService().set_status(
            pool,
            lecturer_user_id=LECTURER_USER_ID,
            session_id=session_id,
            student_id=STUDENT_MARKED_BY_HAND[0],
            status=FinalAttendanceStatus.LATE,
            reason="arrived after the bell",
        )

        yield Lecture(
            session_id=session_id,
            batch_id=batch_id,
            attempt_ids={student[0]: await attempt_id_of(pool, session_id, student) for student in ROSTER},
        )
    finally:
        await remove_lecture(pool, session_id)


def lecturer_service():
    """Built by the same factory the API uses, so this checks the real wiring."""

    return get_lecturer_session_service(SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace())))


async def records_of(pool: asyncpg.Pool, session_id: UUID) -> dict[UUID, asyncpg.Record]:
    rows = await pool.fetch(
        """
        SELECT student_id, attendance_status, record_source, recorded_by, manual_reason
        FROM attendance_verification.attendance_records
        WHERE session_id = $1
        """,
        session_id,
    )
    return {row["student_id"]: row for row in rows}


async def test_closing_decides_every_students_attendance_from_the_real_evidence(
    pool: asyncpg.Pool,
    lecture: Lecture,
) -> None:
    session, summary = await lecturer_service().close_for_user(
        pool,
        LECTURER_USER_ID,
        lecture.session_id,
    )

    assert session.closed_at is not None
    assert summary is not None
    assert summary.enrolled == 6
    assert summary.present == 1  # on time, and scanned the batch
    assert summary.late == 2  # arrived late and scanned / earned but unwritten
    assert summary.absent == 2  # missed the batch / never arrived
    assert summary.kept_manual == 1
    assert summary.reconciled_student_ids == (STUDENT_EARNED_BUT_UNWRITTEN[0],)
    assert summary.deactivated_qr_batch_ids == (lecture.batch_id,)

    records = await records_of(pool, lecture.session_id)
    assert len(records) == 6
    expected = {
        STUDENT_ON_TIME_WITH_QR: ("present", "automatic"),
        STUDENT_ON_TIME_MISSED_QR: ("absent", "automatic"),
        STUDENT_NEVER_ARRIVED: ("absent", "automatic"),
        STUDENT_LATE_WITH_QR: ("late", "automatic"),
        STUDENT_EARNED_BUT_UNWRITTEN: ("late", "automatic"),
        STUDENT_MARKED_BY_HAND: ("late", "manual"),
    }
    for student, (status, source) in expected.items():
        record = records[student[0]]
        assert (record["attendance_status"], record["record_source"]) == (status, source), student

    by_hand = records[STUDENT_MARKED_BY_HAND[0]]
    assert by_hand["recorded_by"] == LECTURER_USER_ID
    assert by_hand["manual_reason"] == "arrived after the bell"


async def test_the_close_time_race_writes_the_earned_check_in(
    pool: asyncpg.Pool,
    lecture: Lecture,
) -> None:
    attempt_id = lecture.attempt_ids[STUDENT_EARNED_BUT_UNWRITTEN[0]]
    before = await pool.fetchrow(
        "SELECT status, checked_in_at FROM attendance_verification.verification_attempts WHERE id = $1",
        attempt_id,
    )
    assert before["status"] == "in_progress"
    assert before["checked_in_at"] is None

    await lecturer_service().close_for_user(pool, LECTURER_USER_ID, lecture.session_id)

    after = await pool.fetchrow(
        """
        SELECT status, checked_in_at, initial_check_in_status
        FROM attendance_verification.verification_attempts WHERE id = $1
        """,
        attempt_id,
    )
    assert after["status"] == "checked_in"
    assert after["checked_in_at"] is not None
    assert after["initial_check_in_status"] == "late_checked_in"


async def test_closing_shuts_down_the_qr_batch_and_leaves_an_audit_row(
    pool: asyncpg.Pool,
    lecture: Lecture,
) -> None:
    await lecturer_service().close_for_user(pool, LECTURER_USER_ID, lecture.session_id)

    batch = await pool.fetchrow(
        "SELECT status, deactivated_at FROM attendance_session.qr_token_batches WHERE id = $1",
        lecture.batch_id,
    )
    assert batch["status"] != "active"
    assert batch["deactivated_at"] is not None

    audit = await pool.fetchrow(
        """
        SELECT new_values FROM audit.audit_logs
        WHERE entity_id = $1 AND action = 'session.close'
        """,
        lecture.session_id,
    )
    assert audit is not None
    assert "finalization" in audit["new_values"]


async def test_the_roster_reports_real_qr_progress(
    pool: asyncpg.Pool,
    lecture: Lecture,
) -> None:
    students = await lecturer_service().list_students_for_user(
        pool,
        LECTURER_USER_ID,
        lecture.session_id,
    )

    progress = {
        student.student_id: (student.qr_required_count, student.qr_passed_count)
        for student in students
    }
    assert progress[STUDENT_ON_TIME_WITH_QR[0]] == (1, 1)
    assert progress[STUDENT_ON_TIME_MISSED_QR[0]] == (1, 0)
    assert progress[STUDENT_LATE_WITH_QR[0]] == (1, 1)
    # Never checked in, or checked in but not yet written: nothing to report.
    assert progress[STUDENT_NEVER_ARRIVED[0]] == (None, None)
    assert progress[STUDENT_EARNED_BUT_UNWRITTEN[0]] == (None, None)


async def test_closing_twice_is_refused_and_writes_nothing_more(
    pool: asyncpg.Pool,
    lecture: Lecture,
) -> None:
    service = lecturer_service()
    await service.close_for_user(pool, LECTURER_USER_ID, lecture.session_id)
    records_after_first_close = await records_of(pool, lecture.session_id)

    with pytest.raises(SessionAlreadyClosedError):
        await service.close_for_user(pool, LECTURER_USER_ID, lecture.session_id)

    assert await records_of(pool, lecture.session_id) == records_after_first_close


async def test_a_lecturers_change_after_closing_replaces_the_automatic_record(
    pool: asyncpg.Pool,
    lecture: Lecture,
) -> None:
    await lecturer_service().close_for_user(pool, LECTURER_USER_ID, lecture.session_id)

    await ManualAttendanceService().set_status(
        pool,
        lecturer_user_id=LECTURER_USER_ID,
        session_id=lecture.session_id,
        student_id=STUDENT_ON_TIME_MISSED_QR[0],
        status=FinalAttendanceStatus.PRESENT,
        reason="was in the room, scanner failed",
    )

    record = (await records_of(pool, lecture.session_id))[STUDENT_ON_TIME_MISSED_QR[0]]
    assert record["attendance_status"] == "present"
    assert record["record_source"] == "manual"
