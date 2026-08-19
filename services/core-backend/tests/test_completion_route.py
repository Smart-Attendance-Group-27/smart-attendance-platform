from datetime import UTC, datetime
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from conftest import (
    LINKED_LECTURER_SUBJECT,
    LINKED_STUDENT_SUBJECT,
    FakePool,
    build_authentication_service_for_tests,
    build_settings,
    default_connection,
)
from main import create_app
from modules.attendance_verification.completion.exception import (
    ActiveStudentProfileNotFoundError,
    AttendanceSessionNotFoundError,
    VerificationNotStartedError,
)
from modules.attendance_verification.completion.route import get_completion_service
from modules.attendance_verification.completion.service import (
    CompletionResult,
    CompletionStatus,
)
from modules.identity.auth.dependencies import get_authentication_service

SESSION_ID = UUID("40000000-0000-0000-0000-000000000001")
ATTEMPT_ID = UUID("50000000-0000-0000-0000-000000000001")
COMPLETE_URL = f"/api/v1/attendance-sessions/{SESSION_ID}/complete-check-in"


def authorize(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def student_token(make_access_token) -> str:
    return make_access_token(subject=LINKED_STUDENT_SUBJECT, roles=("student",))


class StubCompletionService:
    def __init__(self, *, result: CompletionResult | None = None, error: Exception | None = None) -> None:
        self.result = result or CompletionResult(
            status=CompletionStatus.COMPLETED,
            verification_attempt_id=ATTEMPT_ID,
            attendance_status="present",
            missing_requirements=[],
            checked_in_at=datetime(2026, 8, 13, 5, 30, tzinfo=UTC),
        )
        self.error = error
        self.calls: list[tuple[object, UUID, UUID]] = []

    async def complete_for_user(self, pool, user_id, session_id):
        self.calls.append((pool, user_id, session_id))
        if self.error is not None:
            raise self.error
        return self.result


def build_client(jwks_document, service: StubCompletionService) -> TestClient:
    app = create_app(enable_database=False)
    app.state.settings = build_settings()
    app.state.db_pool = FakePool(default_connection())
    app.dependency_overrides[get_authentication_service] = (
        lambda: build_authentication_service_for_tests(jwks_document)
    )
    app.dependency_overrides[get_completion_service] = lambda: service
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def service() -> StubCompletionService:
    return StubCompletionService()


@pytest.fixture
def client(jwks_document, service: StubCompletionService):
    with build_client(jwks_document, service) as test_client:
        yield test_client


def test_completed_returns_camel_case_contract(client: TestClient, make_access_token) -> None:
    response = client.post(COMPLETE_URL, headers=authorize(student_token(make_access_token)))

    assert response.status_code == 200
    assert response.json() == {
        "status": "completed",
        "attendanceStatus": "present",
        "missingRequirements": [],
        "checkedInAt": "2026-08-13T05:30:00Z",
    }


def test_incomplete_reports_missing_requirements(jwks_document, make_access_token) -> None:
    service = StubCompletionService(
        result=CompletionResult(
            status=CompletionStatus.INCOMPLETE,
            verification_attempt_id=ATTEMPT_ID,
            attendance_status=None,
            missing_requirements=["face_verification"],
            checked_in_at=None,
        )
    )
    with build_client(jwks_document, service) as client:
        response = client.post(COMPLETE_URL, headers=authorize(student_token(make_access_token)))

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "incomplete"
    assert body["missingRequirements"] == ["face_verification"]
    assert body["attendanceStatus"] is None


def test_rejects_non_student_role(client: TestClient, make_access_token) -> None:
    response = client.post(
        COMPLETE_URL,
        headers=authorize(make_access_token(subject=LINKED_LECTURER_SUBJECT, roles=("lecturer",))),
    )

    assert response.status_code == 403


def test_missing_student_profile_returns_404(jwks_document, make_access_token) -> None:
    service = StubCompletionService(error=ActiveStudentProfileNotFoundError("no profile"))
    with build_client(jwks_document, service) as client:
        response = client.post(COMPLETE_URL, headers=authorize(student_token(make_access_token)))

    assert response.status_code == 404


def test_missing_session_returns_404(jwks_document, make_access_token) -> None:
    service = StubCompletionService(error=AttendanceSessionNotFoundError("no session"))
    with build_client(jwks_document, service) as client:
        response = client.post(COMPLETE_URL, headers=authorize(student_token(make_access_token)))

    assert response.status_code == 404


def test_verification_not_started_returns_409(jwks_document, make_access_token) -> None:
    service = StubCompletionService(error=VerificationNotStartedError("not started"))
    with build_client(jwks_document, service) as client:
        response = client.post(COMPLETE_URL, headers=authorize(student_token(make_access_token)))

    assert response.status_code == 409


def test_requires_bearer_token(client: TestClient) -> None:
    response = client.post(COMPLETE_URL)

    assert response.status_code == 401
