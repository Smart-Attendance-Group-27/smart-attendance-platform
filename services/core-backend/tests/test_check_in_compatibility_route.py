"""The deprecated complete-check-in endpoint, as the shipped phones see it.

These assertions mirror what ``coreApiAttendanceService`` in the mobile app
actually parses: it discards the response unless ``status`` is ``completed``,
``attendanceStatus`` is ``present`` or ``late``, and ``checkedInAt`` is a
non-empty string. Loosening any of them silently breaks check-in on every phone
that has not been updated, which is exactly what this endpoint exists to
prevent.
"""

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
COMPLETE_URL = f"/api/v1/attendance-sessions/{SESSION_ID}/complete-check-in"
CHECKED_IN_AT = datetime(2026, 8, 13, 5, 30, tzinfo=UTC)


def authorize(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def student_token(make_access_token) -> str:
    return make_access_token(subject=LINKED_STUDENT_SUBJECT, roles=("student",))


def checked_in_result(status: InitialCheckInStatus) -> CheckInResult:
    return CheckInResult(
        outcome=CheckInOutcome.CHECKED_IN,
        verification_attempt_id=ATTEMPT_ID,
        initial_check_in=InitialCheckIn(checked_in_at=CHECKED_IN_AT, status=status),
    )


class StubCheckInService:
    def __init__(
        self,
        *,
        result: CheckInResult | None = None,
        error: Exception | None = None,
    ) -> None:
        self.result = result or checked_in_result(InitialCheckInStatus.CHECKED_IN)
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


def test_an_on_time_check_in_still_reads_as_present(
    client: TestClient,
    make_access_token,
) -> None:
    response = client.post(COMPLETE_URL, headers=authorize(student_token(make_access_token)))

    assert response.status_code == 200
    assert response.json() == {
        "status": "completed",
        "attendanceStatus": "present",
        "missingRequirements": [],
        "checkedInAt": "2026-08-13T05:30:00Z",
    }


def test_a_late_check_in_still_reads_as_late(jwks_document, make_access_token) -> None:
    service = StubCheckInService(
        result=checked_in_result(InitialCheckInStatus.LATE_CHECKED_IN),
    )
    with build_client(jwks_document, service) as client:
        response = client.post(COMPLETE_URL, headers=authorize(student_token(make_access_token)))

    body = response.json()
    assert body["status"] == "completed"
    assert body["attendanceStatus"] == "late"


def test_pending_reports_missing_requirements(jwks_document, make_access_token) -> None:
    service = StubCheckInService(
        result=CheckInResult(
            outcome=CheckInOutcome.PENDING,
            verification_attempt_id=ATTEMPT_ID,
            missing_steps=(RequiredStep.FACE,),
        ),
    )
    with build_client(jwks_document, service) as client:
        response = client.post(COMPLETE_URL, headers=authorize(student_token(make_access_token)))

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "incomplete"
    assert body["missingRequirements"] == ["face_verification"]
    assert body["attendanceStatus"] is None
    assert body["checkedInAt"] is None


def test_a_failed_attempt_maps_to_the_legacy_failed_status(
    jwks_document,
    make_access_token,
) -> None:
    service = StubCheckInService(
        result=CheckInResult(
            outcome=CheckInOutcome.FAILED,
            verification_attempt_id=ATTEMPT_ID,
        ),
    )
    with build_client(jwks_document, service) as client:
        response = client.post(COMPLETE_URL, headers=authorize(student_token(make_access_token)))

    body = response.json()
    assert body["status"] == "failed"
    assert body["attendanceStatus"] is None


def test_the_deprecated_endpoint_uses_the_same_service_as_the_new_one(
    client: TestClient,
    service: StubCheckInService,
    make_access_token,
) -> None:
    client.post(COMPLETE_URL, headers=authorize(student_token(make_access_token)))

    assert [call[2] for call in service.calls] == [SESSION_ID]


def test_rejects_non_student_role(client: TestClient, make_access_token) -> None:
    response = client.post(
        COMPLETE_URL,
        headers=authorize(make_access_token(subject=LINKED_LECTURER_SUBJECT, roles=("lecturer",))),
    )

    assert response.status_code == 403


def test_missing_student_profile_returns_404(jwks_document, make_access_token) -> None:
    service = StubCheckInService(error=ActiveStudentProfileNotFoundError("no profile"))
    with build_client(jwks_document, service) as client:
        response = client.post(COMPLETE_URL, headers=authorize(student_token(make_access_token)))

    assert response.status_code == 404


def test_missing_session_returns_404(jwks_document, make_access_token) -> None:
    service = StubCheckInService(error=AttendanceSessionNotFoundError("no session"))
    with build_client(jwks_document, service) as client:
        response = client.post(COMPLETE_URL, headers=authorize(student_token(make_access_token)))

    assert response.status_code == 404


def test_verification_not_started_returns_409(jwks_document, make_access_token) -> None:
    service = StubCheckInService(error=VerificationNotStartedError("not started"))
    with build_client(jwks_document, service) as client:
        response = client.post(COMPLETE_URL, headers=authorize(student_token(make_access_token)))

    assert response.status_code == 409


def test_requires_bearer_token(client: TestClient) -> None:
    response = client.post(COMPLETE_URL)

    assert response.status_code == 401
