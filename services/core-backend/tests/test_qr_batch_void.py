from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from conftest import (
    LINKED_LECTURER_SUBJECT, LINKED_STUDENT_SUBJECT, FakePool,
    build_authentication_service_for_tests, build_settings, default_connection,
)
from main import create_app
from modules.attendance_sessions.qr_session.evidence import QrBatchParticipation
from modules.attendance_sessions.qr_session.exception import (
    LecturerSessionAccessError, QrBatchAlreadyVoidedError,
    QrBatchVoidSessionError, QrSessionNotFoundError,
)
from modules.attendance_sessions.qr_session.repository import (
    AttendanceSessionRecord, QrBatchVoidState, QrSessionRepository,
)
from modules.attendance_sessions.qr_session.route import get_qr_session_service
from modules.attendance_sessions.qr_session.service import QrSessionService
from modules.identity.auth.dependencies import get_authentication_service


SESSION_ID = UUID("40000000-0000-0000-0000-000000000001")
BATCH_ID = UUID("50000000-0000-0000-0000-000000000001")
LECTURER_ID = UUID("20000000-0000-0000-0000-000000000002")
NOW = datetime(2026, 9, 21, 10, 0, tzinfo=UTC)


def participation(*, voided: bool) -> QrBatchParticipation:
    return QrBatchParticipation(
        qr_session_id=BATCH_ID, mode="static", status="inactive" if voided else "active",
        activated_at=NOW - timedelta(minutes=2),
        deactivated_at=NOW if voided else None,
        expires_at=NOW + timedelta(minutes=3), voided=voided,
        void_reason="Created by mistake" if voided else None,
        required_student_count=0 if voided else 2,
        passed_student_count=0 if voided else 1,
    )


class Transaction:
    async def __aenter__(self):
        return None

    async def __aexit__(self, *_):
        return False


class Connection:
    def __init__(self):
        self.statements = []

    def transaction(self):
        return Transaction()

    async def execute(self, query, *args):
        self.statements.append((query, args))


class Acquire:
    def __init__(self, connection):
        self.connection = connection

    async def __aenter__(self):
        return self.connection

    async def __aexit__(self, *_):
        return False


class Pool:
    def __init__(self):
        self.connection = Connection()

    def acquire(self):
        return Acquire(self.connection)


class Repository:
    def __init__(self, *, status="active", owned=True, batch=True, voided=False):
        self.session = AttendanceSessionRecord(
            id=SESSION_ID, status=status, scheduled_end_at=NOW + timedelta(hours=1),
            closed_at=NOW if status == "closed" else None,
            cancelled_at=NOW if status == "cancelled" else None,
        )
        self.owned = owned
        self.batch = QrBatchVoidState(BATCH_ID, NOW if voided else None) if batch else None
        self.void_call = None

    async def lock_attendance_session(self, connection, session_id):
        return self.session

    async def session_owned_by_lecturer(self, connection, session_id, lecturer_id):
        return self.owned

    async def lock_qr_batch_for_void(self, connection, session_id, qr_session_id):
        return self.batch

    async def void_qr_batch(self, connection, qr_session_id, voided_at, actor_id, reason):
        self.void_call = (connection, qr_session_id, voided_at, actor_id, reason)


class Evidence:
    def __init__(self):
        self.connection = None

    async def batch_participation_for_session(self, connection, session_id):
        self.connection = connection
        return [participation(voided=True)]


class Cache:
    def __init__(self):
        self.deleted = []

    async def delete_qr_batch_cache(self, batch_id):
        self.deleted.append(batch_id)


@pytest.mark.asyncio
async def test_void_batch_audits_and_reads_updated_participation_on_same_connection() -> None:
    pool = Pool()
    repository = Repository()
    evidence = Evidence()
    cache = Cache()
    service = QrSessionService(
        repository=repository, evidence_repository=evidence,
        qr_batch_cache=cache, clock=lambda: NOW,
    )

    result = await service.void_qr_batch(
        pool, SESSION_ID, BATCH_ID, LECTURER_ID, "Created by mistake",
    )

    assert result.voided and result.required_student_count == 0
    assert repository.void_call == (
        pool.connection, BATCH_ID, NOW, LECTURER_ID, "Created by mistake",
    )
    assert evidence.connection is pool.connection
    assert any("qr_session.void" in str(args) for _, args in pool.connection.statements)
    assert cache.deleted == [BATCH_ID]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("repository", "expected_error"),
    [
        (Repository(status="closed"), QrBatchVoidSessionError),
        (Repository(status="cancelled"), QrBatchVoidSessionError),
        (Repository(owned=False), LecturerSessionAccessError),
        (Repository(batch=False), QrSessionNotFoundError),
        (Repository(voided=True), QrBatchAlreadyVoidedError),
    ],
)
async def test_void_batch_rejects_invalid_state_without_writing(repository, expected_error) -> None:
    pool = Pool()
    service = QrSessionService(repository=repository, clock=lambda: NOW)

    with pytest.raises(expected_error):
        await service.void_qr_batch(pool, SESSION_ID, BATCH_ID, LECTURER_ID, "Mistake")

    assert repository.void_call is None


@pytest.mark.asyncio
async def test_repository_voids_batch_and_revokes_static_tokens() -> None:
    connection = Connection()
    await QrSessionRepository().void_qr_batch(
        connection, BATCH_ID, NOW, LECTURER_ID, "Mistake",
    )
    assert len(connection.statements) == 2
    assert "voided_at = $2" in connection.statements[0][0]
    assert "revoked_at = COALESCE" in connection.statements[1][0]
    assert connection.statements[0][1] == (BATCH_ID, NOW, LECTURER_ID, "Mistake")


class StubVoidService:
    def __init__(self, error=None):
        self.error = error
        self.call = None

    async def void_qr_batch(self, pool, session_id, batch_id, lecturer_id, reason):
        self.call = (session_id, batch_id, lecturer_id, reason)
        if self.error:
            raise self.error
        return participation(voided=True)


def client_for(jwks_document, service):
    app = create_app(enable_database=False)
    app.state.settings = build_settings()
    app.state.db_pool = FakePool(default_connection())
    app.dependency_overrides[get_authentication_service] = (
        lambda: build_authentication_service_for_tests(jwks_document)
    )
    app.dependency_overrides[get_qr_session_service] = lambda: service
    return TestClient(app, raise_server_exceptions=False)


def headers(make_access_token, subject, role):
    return {"Authorization": f"Bearer {make_access_token(subject=subject, roles=(role,))}"}


def test_void_route_requires_lecturer_and_returns_c09_item(jwks_document, make_access_token):
    service = StubVoidService()
    url = f"/api/v1/lecturers/me/attendance-sessions/{SESSION_ID}/qr-batches/{BATCH_ID}/void"
    with client_for(jwks_document, service) as client:
        lecturer = headers(make_access_token, LINKED_LECTURER_SUBJECT, "lecturer")
        response = client.post(url, json={"reason": "  Created by mistake  "}, headers=lecturer)
        assert response.status_code == 200
        assert response.json()["voided"] is True
        assert response.json()["requiredStudentCount"] == 0
        assert service.call[-1] == "Created by mistake"
        assert client.post(url, json={"reason": "Mistake"}, headers=headers(
            make_access_token, LINKED_STUDENT_SUBJECT, "student",
        )).status_code == 403
        assert client.post(url, json={"reason": "  "}, headers=lecturer).status_code == 422


@pytest.mark.parametrize(
    ("error", "status", "code"),
    [
        (QrBatchAlreadyVoidedError(), 409, "BATCH_ALREADY_VOIDED"),
        (QrBatchVoidSessionError("SESSION_ALREADY_CLOSED"), 409, "SESSION_ALREADY_CLOSED"),
        (QrBatchVoidSessionError("SESSION_CANCELLED"), 409, "SESSION_CANCELLED"),
        (QrSessionNotFoundError(), 404, "BATCH_NOT_FOUND"),
    ],
)
def test_void_route_maps_domain_errors(jwks_document, make_access_token, error, status, code):
    url = f"/api/v1/lecturers/me/attendance-sessions/{SESSION_ID}/qr-batches/{BATCH_ID}/void"
    with client_for(jwks_document, StubVoidService(error)) as client:
        response = client.post(url, json={"reason": "Mistake"}, headers=headers(
            make_access_token, LINKED_LECTURER_SUBJECT, "lecturer",
        ))
    assert response.status_code == status
    assert response.json()["detail"]["code"] == code
