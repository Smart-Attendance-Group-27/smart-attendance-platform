"""Opt-in PostgreSQL test: set QR_EVIDENCE_TEST_DSN to an isolated migrated DB.

The fixture stays inside a rolled-back transaction. This proves the repository
sees uncommitted reconciliation and evaluates the strict QR requirement rule.
"""

import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import asyncpg
import pytest

from modules.attendance_sessions.qr_session.evidence import QrEvidenceRepository
from modules.contracts.qr_evidence import QrRequirementProgress


@pytest.mark.asyncio
async def test_strict_batch_requirements_and_same_transaction_visibility() -> None:
    dsn = os.getenv("QR_EVIDENCE_TEST_DSN")
    if not dsn:
        pytest.skip("Set QR_EVIDENCE_TEST_DSN to an isolated, migrated PostgreSQL database")
    connection = await asyncpg.connect(dsn)
    try:
        database_name = await connection.fetchval("SELECT current_database()")
        if not database_name.startswith("codex_m2_"):
            raise RuntimeError("QR evidence test requires an isolated codex_m2_ database")
        transaction = connection.transaction()
        await transaction.start()
        try:
            await exercise_evidence(connection)
        finally:
            await transaction.rollback()
    finally:
        await connection.close()


async def exercise_evidence(connection: asyncpg.Connection) -> None:
    lecturer_user = uuid4()
    student_users = [uuid4() for _ in range(3)]
    students = [uuid4() for _ in range(3)]
    course, offering, session = uuid4(), uuid4(), uuid4()
    attempts = [uuid4() for _ in range(3)]
    batches = [uuid4() for _ in range(5)]
    checked_in = datetime(2026, 9, 20, 10, 0, tzinfo=UTC)

    for user in [lecturer_user, *student_users]:
        await connection.execute(
            "INSERT INTO identity.users (id, email) VALUES ($1, $2)",
            user, f"m2-{user}@example.invalid",
        )
    for student, user in zip(students, student_users):
        await connection.execute(
            "INSERT INTO academic.student_profiles (id, user_id, profile_status) "
            "VALUES ($1, $2, 'active')", student, user,
        )
    await connection.execute(
        "INSERT INTO academic.courses (id, course_code) VALUES ($1, $2)",
        course, f"M2-{str(course)[:8]}",
    )
    await connection.execute(
        "INSERT INTO academic.course_offerings (id, course_id) VALUES ($1, $2)",
        offering, course,
    )
    await connection.execute(
        """INSERT INTO attendance_session.sessions
           (id, course_offering_id, created_by, status, requires_qr, scheduled_start_at,
            scheduled_end_at, activated_at)
           VALUES ($1, $2, $3, 'active', true, $4, $5, $4)""",
        session, offering, lecturer_user, checked_in, checked_in + timedelta(hours=1),
    )
    for student, attempt in zip(students, attempts):
        await connection.execute(
            "INSERT INTO attendance_session.session_students (id, session_id, student_id) "
            "VALUES ($1, $2, $3)", uuid4(), session, student,
        )
        index = students.index(student)
        status = "checked_in" if index < 2 else "in_progress"
        time = checked_in + timedelta(minutes=5) if index == 1 else checked_in
        await connection.execute(
            """INSERT INTO attendance_verification.verification_attempts
               (id, session_id, student_id, status, checked_in_at, initial_check_in_status)
               VALUES ($1, $2, $3, $4, $5, $6)""",
            attempt, session, student, status,
            time if index < 2 else None,
            "checked_in" if index < 2 else None,
        )
    for index, (batch, offset) in enumerate(zip(batches, [-1, 0, 1, 6, 7])):
        activated = checked_in + timedelta(minutes=offset)
        await connection.execute(
            """INSERT INTO attendance_session.qr_token_batches
               (id, session_id, mode, refresh_interval_seconds, issued_by, status, activated_at, expires_at,
                voided_at, voided_by, void_reason)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)""",
            batch, session, "dynamic" if index == 3 else "static",
            15 if index == 3 else None, lecturer_user,
            "active" if index == 3 else "inactive",
            activated, activated + timedelta(minutes=20),
            activated + timedelta(minutes=1) if index == 4 else None,
            lecturer_user if index == 4 else None,
            "Mistaken activation" if index == 4 else None,
        )
    # Accepted twice for the same batch still passes only one requirement.
    for number, batch in enumerate([batches[2], batches[2], batches[3]], start=1):
        await connection.execute(
            """INSERT INTO attendance_verification.qr_validation_attempts
               (id, verification_attempt_id, qr_batch_id, attempt_number, validation_status)
               VALUES ($1, $2, $3, $4, 'accepted')""",
            uuid4(), attempts[0], batch, number,
        )

    repository = QrEvidenceRepository()
    progress = await repository.progress_for_session(connection, session)
    assert progress == {
        attempts[0]: QrRequirementProgress(required_count=2, passed_count=2),
        attempts[1]: QrRequirementProgress(required_count=1, passed_count=0),
    }
    assert await repository.progress_for_attempt(connection, attempts[0]) == progress[attempts[0]]
    assert await repository.progress_for_attempt(connection, attempts[2]) is None

    state = await repository.student_state(connection, session, student_users[0])
    assert state is not None and state.checked_in_at == checked_in
    student_batches = await repository.student_batches(
        connection, session, state.checked_in_at, state.attempt_id,
    )
    assert {batch.qr_session_id for batch in student_batches if batch.required} == set(batches[2:4])
    assert {batch.qr_session_id for batch in student_batches if batch.passed} == set(batches[2:4])
    participation = await repository.batch_participation_for_session(connection, session)
    by_id = {batch.qr_session_id: batch for batch in participation}
    assert (by_id[batches[2]].required_student_count,
            by_id[batches[2]].passed_student_count) == (1, 1)
    assert (by_id[batches[3]].required_student_count,
            by_id[batches[3]].passed_student_count) == (2, 1)
    assert by_id[batches[1]].required_student_count == 0  # Equal check-in time.
    assert by_id[batches[4]].required_student_count == 0  # Voided.
    assert await repository.student_user_ids_required_for_batch(
        connection, batches[3],
    ) == sorted(student_users[:2])
    assert await repository.student_user_ids_required_for_batch(connection, batches[4]) == []

    empty_session, empty_attempt = uuid4(), uuid4()
    await connection.execute(
        """INSERT INTO attendance_session.sessions
           (id, course_offering_id, created_by, status, requires_qr, scheduled_start_at,
            scheduled_end_at, activated_at)
           VALUES ($1, $2, $3, 'active', true, $4, $5, $4)""",
        empty_session, offering, lecturer_user, checked_in,
        checked_in + timedelta(hours=1),
    )
    await connection.execute(
        "INSERT INTO attendance_session.session_students (id, session_id, student_id) "
        "VALUES ($1, $2, $3)", uuid4(), empty_session, students[0],
    )
    await connection.execute(
        """INSERT INTO attendance_verification.verification_attempts
           (id, session_id, student_id, status, checked_in_at, initial_check_in_status)
           VALUES ($1, $2, $3, 'checked_in', $4, 'checked_in')""",
        empty_attempt, empty_session, students[0], checked_in,
    )
    assert await repository.progress_for_session(connection, empty_session) == {
        empty_attempt: QrRequirementProgress(required_count=0, passed_count=0),
    }
    assert await repository.batch_participation_for_session(connection, empty_session) == []
