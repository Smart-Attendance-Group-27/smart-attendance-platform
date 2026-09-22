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
from modules.attendance_verification.attendance_state import InitialCheckInStatus
from modules.attendance_verification.check_in.domain import (
    CheckInOutcome,
    CheckInResult,
    InitialCheckIn,
    RequiredStep,
)
from modules.attendance_verification.check_in.exception import (
    ActiveStudentProfileNotFoundError,
    AttendanceSessionNotFoundError,
    VerificationNotStartedError,
)
from modules.attendance_verification.check_in.route import get_check_in_service
from modules.identity.auth.dependencies import get_authentication_service

SESSION_ID = UUID("40000000-0000-0000-0000-000000000001")
ATTEMPT_ID = UUID("50000000-0000-0000-0000-000000000001")
CHECK_IN_URL = f"/api/v1/attendance-sessions/{SESSION_ID}/check-in"
CHECKED_IN_AT = datetime(2026, 9, 21, 9, 3, tzinfo=UTC)


def authorize(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def student_token(make_access_token) -> str:
    return make_access_token(subject=LINKED_STUDENT_SUBJECT, roles=("student",))


def checked_in_result(status: InitialCheckInStatus = InitialCheckInStatus.CHECKED_IN):
    return CheckInResult(
        outcome=CheckInOutcome.CHECKED_IN,
        verification_attempt_id=ATTEMPT_ID,
        initial_check_in=InitialCheckIn(checked_in_at=CHECKED_IN_AT, status=status),
        was_persisted=True,
    )


class StubCheckInService:
    def __init__(
        self,
        *,
        result: CheckInResult | None = None,
        error: Exception | None = None,
    ) -> None:
        self.result = result or checked_in_result()
        self.error = error
        self.calls: list[tuple[object, UUID, UUID]] = []

    async def check_in_for_user(self, pool, user_id, session_id):
        self.calls.append((pool, user_id, session_id))
        if self.error is not None:
            raise self.error
        return self.result


def build_client(jwks_document, service: StubCheckInService) -> TestClient:
    app = create_app(enable_database=False)
    app.state.settings = build_settings()
    app.state.db_pool = FakePool(default_connection())
    app.dependency_overrides[get_authentication_service] = (
        lambda: build_authentication_service_for_tests(jwks_document)
    )
    app.dependency_overrides[get_check_in_service] = lambda: service
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def service() -> StubCheckInService:
    return StubCheckInService()


@pytest.fixture
def client(jwks_document, service: StubCheckInService):
    with build_client(jwks_document, service) as test_client:
        yield test_client


def test_a_check_in_is_returned_in_camel_case(client: TestClient, make_access_token) -> None:
    response = client.post(CHECK_IN_URL, headers=authorize(student_token(make_access_token)))

    assert response.status_code == 200
    assert response.json() == {
        "status": "checked_in",
        "verificationAttemptId": str(ATTEMPT_ID),
        "initialCheckIn": {
            "status": "checked_in",
            "checkedInAt": "2026-09-21T09:03:00Z",
        },
        "missingRequirements": [],
    }


def test_a_late_check_in_says_so(jwks_document, make_access_token) -> None:
    service = StubCheckInService(
        result=checked_in_result(InitialCheckInStatus.LATE_CHECKED_IN),
    )
    with build_client(jwks_document, service) as client:
        response = client.post(CHECK_IN_URL, headers=authorize(student_token(make_access_token)))

    assert response.json()["initialCheckIn"]["status"] == "late_checked_in"


def test_a_pending_check_in_lists_what_is_missing(jwks_document, make_access_token) -> None:
    service = StubCheckInService(
        result=CheckInResult(
            outcome=CheckInOutcome.PENDING,
            verification_attempt_id=ATTEMPT_ID,
            missing_steps=(RequiredStep.FACE,),
        ),
    )
    with build_client(jwks_document, service) as client:
        response = client.post(CHECK_IN_URL, headers=authorize(student_token(make_access_token)))

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "pending"
    assert body["initialCheckIn"] is None
    assert body["missingRequirements"] == ["face_verification"]


def test_a_failed_attempt_reports_failure(jwks_document, make_access_token) -> None:
    service = StubCheckInService(
        result=CheckInResult(
            outcome=CheckInOutcome.FAILED,
            verification_attempt_id=ATTEMPT_ID,
        ),
    )
    with build_client(jwks_document, service) as client:
        response = client.post(CHECK_IN_URL, headers=authorize(student_token(make_access_token)))

    assert response.json()["status"] == "failed"
    assert response.json()["initialCheckIn"] is None


def test_the_session_id_from_the_path_reaches_the_service(
    client: TestClient,
    service: StubCheckInService,
    make_access_token,
) -> None:
    client.post(CHECK_IN_URL, headers=authorize(student_token(make_access_token)))

    assert [call[2] for call in service.calls] == [SESSION_ID]


def test_a_lecturer_cannot_check_a_student_in(client: TestClient, make_access_token) -> None:
    response = client.post(
        CHECK_IN_URL,
        headers=authorize(make_access_token(subject=LINKED_LECTURER_SUBJECT, roles=("lecturer",))),
    )

    assert response.status_code == 403


def test_missing_student_profile_returns_404(jwks_document, make_access_token) -> None:
    service = StubCheckInService(error=ActiveStudentProfileNotFoundError("no profile"))
    with build_client(jwks_document, service) as client:
        response = client.post(CHECK_IN_URL, headers=authorize(student_token(make_access_token)))

    assert response.status_code == 404
    assert response.json()["detail"] == {
        "code": "STUDENT_PROFILE_NOT_FOUND",
        "message": "no profile",
    }


def test_missing_session_returns_404(jwks_document, make_access_token) -> None:
    service = StubCheckInService(error=AttendanceSessionNotFoundError("no session"))
    with build_client(jwks_document, service) as client:
        response = client.post(CHECK_IN_URL, headers=authorize(student_token(make_access_token)))

    assert response.status_code == 404
    assert response.json()["detail"] == {
        "code": "SESSION_NOT_FOUND",
        "message": "no session",
    }


def test_checking_in_before_verifying_returns_409(jwks_document, make_access_token) -> None:
    service = StubCheckInService(error=VerificationNotStartedError("not started"))
    with build_client(jwks_document, service) as client:
        response = client.post(CHECK_IN_URL, headers=authorize(student_token(make_access_token)))

    assert response.status_code == 409
    assert response.json()["detail"] == {
        "code": "VERIFICATION_NOT_STARTED",
        "message": "not started",
    }


def test_requires_bearer_token(client: TestClient) -> None:
    response = client.post(CHECK_IN_URL)

    assert response.status_code == 401


def test_the_old_complete_check_in_endpoint_is_gone(client: TestClient, make_access_token) -> None:
    response = client.post(
        f"/api/v1/attendance-sessions/{SESSION_ID}/complete-check-in",
        headers=authorize(student_token(make_access_token)),
    )

    assert response.status_code == 404
