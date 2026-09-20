from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi.testclient import TestClient

from conftest import (
    LINKED_LECTURER_SUBJECT, LINKED_STUDENT_SUBJECT, FakePool,
    build_authentication_service_for_tests, build_settings, default_connection,
)
from main import create_app
from modules.attendance_sessions.qr_session.evidence import (
    QrBatchParticipation, StudentQrBatch,
)
from modules.attendance_sessions.qr_session.exception import (
    AttendanceSessionNotFoundError, LecturerSessionAccessError,
)
from modules.attendance_sessions.qr_session.route import get_qr_session_service
from modules.attendance_sessions.qr_session.service import StudentQrProgress
from modules.identity.auth.dependencies import get_authentication_service

SESSION_ID = UUID("40000000-0000-0000-0000-000000000001")
BATCH_ID = UUID("50000000-0000-0000-0000-000000000001")
START = datetime(2026, 8, 6, 10, 0, tzinfo=UTC)


class StubProgressService:
    def __init__(self, *, missing: bool = False) -> None:
        self.missing = missing

    async def get_qr_progress_for_student(self, pool, session_id, student_user_id):
        if self.missing:
            raise AttendanceSessionNotFoundError()
        batch = StudentQrBatch(
            qr_session_id=BATCH_ID, mode="static", status="active",
            activated_at=START, deactivated_at=None,
            expires_at=START + timedelta(minutes=5), voided=False,
            required=True, passed=False,
        )
        return StudentQrProgress(
            session_id=session_id, qr_enabled=True, checked_in_at=START - timedelta(minutes=1),
            required_count=1, passed_count=0, active_batch=batch, batches=[batch],
        )

    async def list_qr_batches_for_lecturer(self, pool, session_id, lecturer_user_id):
        if self.missing:
            raise LecturerSessionAccessError()
        return [QrBatchParticipation(
            qr_session_id=BATCH_ID, mode="static", status="active",
            activated_at=START, deactivated_at=None,
            expires_at=START + timedelta(minutes=5), voided=False, void_reason=None,
            required_student_count=7, passed_student_count=4,
        )]


def client_for(jwks_document, service) -> TestClient:
    app = create_app(enable_database=False)
    app.state.settings = build_settings()
    app.state.db_pool = FakePool(default_connection())
    app.dependency_overrides[get_authentication_service] = (
        lambda: build_authentication_service_for_tests(jwks_document)
    )
    app.dependency_overrides[get_qr_session_service] = lambda: service
    return TestClient(app, raise_server_exceptions=False)


def headers(make_access_token, subject: str, role: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {make_access_token(subject=subject, roles=(role,))}"}


def test_student_progress_shape_and_authorization(jwks_document, make_access_token) -> None:
    with client_for(jwks_document, StubProgressService()) as client:
        url = f"/api/v1/attendance-sessions/{SESSION_ID}/qr-progress"
        student = headers(make_access_token, LINKED_STUDENT_SUBJECT, "student")
        response = client.get(url, headers=student)
        assert response.status_code == 200
        body = response.json()
        assert body["sessionId"] == str(SESSION_ID)
        assert body["requiredCount"] == 1
        assert body["passedCount"] == 0
        assert body["activeBatch"]["qrSessionId"] == str(BATCH_ID)
        assert body["batches"][0]["voided"] is False
        assert client.get(url, headers=headers(
            make_access_token, LINKED_LECTURER_SUBJECT, "lecturer",
        )).status_code == 403
    with client_for(jwks_document, StubProgressService(missing=True)) as client:
        response = client.get(url, headers=student)
        assert response.status_code == 404
        assert response.json()["detail"]["code"] == "SESSION_NOT_FOUND"


def test_lecturer_batch_participation_shape_and_authorization(
    jwks_document, make_access_token,
) -> None:
    url = f"/api/v1/lecturers/me/attendance-sessions/{SESSION_ID}/qr-batches"
    lecturer = headers(make_access_token, LINKED_LECTURER_SUBJECT, "lecturer")
    with client_for(jwks_document, StubProgressService()) as client:
        response = client.get(url, headers=lecturer)
        assert response.status_code == 200
        assert response.json()[0]["requiredStudentCount"] == 7
        assert response.json()[0]["passedStudentCount"] == 4
        assert client.get(url, headers=headers(
            make_access_token, LINKED_STUDENT_SUBJECT, "student",
        )).status_code == 403
    with client_for(jwks_document, StubProgressService(missing=True)) as client:
        assert client.get(url, headers=lecturer).status_code == 404
