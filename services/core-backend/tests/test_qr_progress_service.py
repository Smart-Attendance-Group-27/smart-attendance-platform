from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from modules.attendance_sessions.qr_session.evidence import (
    QrBatchParticipation, StudentQrBatch, StudentQrState,
)
from modules.attendance_sessions.qr_session.exception import (
    AttendanceSessionNotFoundError, LecturerSessionAccessError,
)
from modules.attendance_sessions.qr_session.service import QrSessionService

SESSION_ID = UUID("40000000-0000-0000-0000-000000000001")
STUDENT_USER_ID = UUID("20000000-0000-0000-0000-000000000001")
LECTURER_USER_ID = UUID("20000000-0000-0000-0000-000000000002")
ATTEMPT_ID = UUID("60000000-0000-0000-0000-000000000001")
NOW = datetime(2026, 8, 6, 10, 4, tzinfo=UTC)


class Acquire:
    def __init__(self, connection):
        self.connection = connection

    async def __aenter__(self):
        return self.connection

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class Pool:
    def __init__(self):
        self.connection = object()

    def acquire(self):
        return Acquire(self.connection)


class FakeEvidence:
    def __init__(self):
        self.connection = None
        self.state = StudentQrState(SESSION_ID, "active", True, ATTEMPT_ID, NOW - timedelta(minutes=2))
        self.batches = [
            StudentQrBatch(UUID(int=1), "static", "inactive", NOW - timedelta(minutes=3),
                           NOW - timedelta(minutes=1), NOW, False, False, True),
            StudentQrBatch(UUID(int=2), "dynamic", "active", NOW - timedelta(minutes=1),
                           None, NOW + timedelta(minutes=2), False, True, True),
            StudentQrBatch(UUID(int=3), "static", "active", NOW - timedelta(minutes=1),
                           None, NOW + timedelta(minutes=2), True, False, False),
        ]

    async def student_state(self, connection, session_id, user_id):
        self.connection = connection
        assert (session_id, user_id) == (SESSION_ID, STUDENT_USER_ID)
        return self.state

    async def student_batches(self, connection, session_id, checked_in_at, attempt_id):
        assert connection is self.connection
        assert (session_id, checked_in_at, attempt_id) == (
            SESSION_ID, self.state.checked_in_at, ATTEMPT_ID,
        )
        return self.batches

    async def batch_participation_for_session(self, connection, session_id):
        self.connection = connection
        assert session_id == SESSION_ID
        return [QrBatchParticipation(
            UUID(int=2), "dynamic", "active", NOW, None, NOW + timedelta(minutes=2),
            False, None, 3, 2,
        )]


class FakeQrRepository:
    def __init__(self, owns: bool = True):
        self.owns = owns

    async def session_owned_by_lecturer(self, connection, session_id, user_id):
        assert (session_id, user_id) == (SESSION_ID, LECTURER_USER_ID)
        return self.owns


@pytest.mark.asyncio
async def test_student_progress_counts_only_required_nonvoided_batches() -> None:
    pool = Pool()
    evidence = FakeEvidence()
    service = QrSessionService(evidence_repository=evidence, clock=lambda: NOW)

    progress = await service.get_qr_progress_for_student(pool, SESSION_ID, STUDENT_USER_ID)

    assert evidence.connection is pool.connection
    assert progress.required_count == 1
    assert progress.passed_count == 1
    assert progress.active_batch.qr_session_id == UUID(int=2)
    assert len(progress.batches) == 3

    evidence.state = None
    with pytest.raises(AttendanceSessionNotFoundError):
        await service.get_qr_progress_for_student(pool, SESSION_ID, STUDENT_USER_ID)


@pytest.mark.asyncio
async def test_lecturer_progress_requires_course_ownership() -> None:
    pool = Pool()
    evidence = FakeEvidence()
    service = QrSessionService(
        repository=FakeQrRepository(), evidence_repository=evidence, clock=lambda: NOW,
    )
    batches = await service.list_qr_batches_for_lecturer(pool, SESSION_ID, LECTURER_USER_ID)
    assert evidence.connection is pool.connection
    assert batches[0].required_student_count == 3

    denied = QrSessionService(
        repository=FakeQrRepository(owns=False), evidence_repository=evidence,
    )
    with pytest.raises(LecturerSessionAccessError):
        await denied.list_qr_batches_for_lecturer(pool, SESSION_ID, LECTURER_USER_ID)
