from datetime import UTC, datetime
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from conftest import (
    LECTURER_USER_ID,
    LINKED_LECTURER_SUBJECT,
    LINKED_STUDENT_SUBJECT,
    FakePool,
    build_authentication_service_for_tests,
    build_settings,
    default_connection,
)
from main import create_app
from modules.academic.lecturer_profile.exception import LecturerProfileNotFoundError
from modules.attendance_verification.attendance_state import FinalAttendanceStatus
from modules.attendance_verification.manual_attendance.exception import (
    ManualReasonInvalidError,
    SessionCancelledError,
    SessionNotFoundError,
    SessionNotStartedError,
    StudentNotOnRosterError,
)
from modules.attendance_verification.manual_attendance.route import (
    get_manual_attendance_service,
)
from modules.attendance_verification.manual_attendance.service import ManualAttendanceResult
from modules.identity.auth.dependencies import get_authentication_service

SESSION_ID = UUID("40000000-0000-0000-0000-000000000001")
STUDENT_ID = UUID("23000000-0000-0000-0000-000000000001")
URL = f"/api/v1/lecturers/me/attendance-sessions/{SESSION_ID}/students/{STUDENT_ID}/attendance"
UPDATED_AT = datetime(2026, 9, 21, 10, 0, tzinfo=UTC)


def lecturer_headers(make_access_token) -> dict[str, str]:
    token = make_access_token(subject=LINKED_LECTURER_SUBJECT, roles=("lecturer",))
    return {"Authorization": f"Bearer {token}"}


class StubManualAttendanceService:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[dict] = []

    async def set_status(self, pool, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return ManualAttendanceResult(
            session_id=kwargs["session_id"],
            student_id=kwargs["student_id"],
            status=kwargs["status"],
            reason=kwargs["reason"],
            recorded_by=kwargs["lecturer_user_id"],
            updated_at=UPDATED_AT,
        )


def build_client(jwks_document, service: StubManualAttendanceService) -> TestClient:
    app = create_app(enable_database=False)
    app.state.settings = build_settings()
    app.state.db_pool = FakePool(default_connection())
    app.dependency_overrides[get_authentication_service] = (
        lambda: build_authentication_service_for_tests(jwks_document)
    )
    app.dependency_overrides[get_manual_attendance_service] = lambda: service
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def service() -> StubManualAttendanceService:
    return StubManualAttendanceService()


@pytest.fixture
def client(jwks_document, service: StubManualAttendanceService):
    with build_client(jwks_document, service) as test_client:
        yield test_client


def test_sets_the_status_and_returns_the_manual_record(
    client: TestClient,
    service: StubManualAttendanceService,
    make_access_token,
) -> None:
    response = client.put(
        URL,
        headers=lecturer_headers(make_access_token),
        json={"status": "late", "reason": "arrived after the bell"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "sessionId": str(SESSION_ID),
        "studentId": str(STUDENT_ID),
        "status": "late",
        "source": "manual",
        "reason": "arrived after the bell",
        "recordedBy": str(LECTURER_USER_ID),
        "updatedAt": "2026-09-21T10:00:00Z",
    }
    call = service.calls[0]
    assert call["lecturer_user_id"] == LECTURER_USER_ID
    assert call["session_id"] == SESSION_ID
    assert call["student_id"] == STUDENT_ID
    assert call["status"] is FinalAttendanceStatus.LATE


@pytest.mark.parametrize("status", ["present", "late", "absent"])
def test_every_final_status_can_be_set(
    client: TestClient,
    make_access_token,
    status: str,
) -> None:
    response = client.put(
        URL,
        headers=lecturer_headers(make_access_token),
        json={"status": status, "reason": "checked by hand"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == status


@pytest.mark.parametrize(
    "payload",
    [
        {"status": "late"},
        {"reason": "checked by hand"},
        {"status": "excused", "reason": "checked by hand"},
        {"status": "checked_in", "reason": "checked by hand"},
        {"status": "late", "reason": "ab"},
        {"status": "late", "reason": "   "},
        {"status": "late", "reason": "x" * 501},
        {"status": "late", "reason": "checked by hand", "source": "automatic"},
    ],
)
def test_invalid_requests_are_rejected_before_reaching_the_service(
    client: TestClient,
    service: StubManualAttendanceService,
    make_access_token,
    payload: dict,
) -> None:
    response = client.put(URL, headers=lecturer_headers(make_access_token), json=payload)

    assert response.status_code == 422
    assert service.calls == []


@pytest.mark.parametrize(
    ("error", "status_code", "code"),
    [
        (SessionNotFoundError(), 404, "SESSION_NOT_FOUND"),
        (StudentNotOnRosterError(), 404, "STUDENT_NOT_ON_ROSTER"),
        (SessionNotStartedError(), 409, "SESSION_NOT_STARTED"),
        (SessionCancelledError(), 409, "SESSION_CANCELLED"),
        (ManualReasonInvalidError(), 422, "REASON_INVALID"),
        (LecturerProfileNotFoundError(), 404, "LECTURER_PROFILE_NOT_FOUND"),
    ],
)
def test_domain_errors_map_to_the_documented_codes(
    jwks_document,
    make_access_token,
    error: Exception,
    status_code: int,
    code: str,
) -> None:
    with build_client(jwks_document, StubManualAttendanceService(error=error)) as client:
        response = client.put(
            URL,
            headers=lecturer_headers(make_access_token),
            json={"status": "late", "reason": "arrived after the bell"},
        )

    assert response.status_code == status_code
    assert response.json()["detail"]["code"] == code


def test_a_student_cannot_set_attendance(client: TestClient, make_access_token) -> None:
    token = make_access_token(subject=LINKED_STUDENT_SUBJECT, roles=("student",))

    response = client.put(
        URL,
        headers={"Authorization": f"Bearer {token}"},
        json={"status": "present", "reason": "trust me"},
    )

    assert response.status_code == 403


def test_requires_bearer_token(client: TestClient) -> None:
    response = client.put(URL, json={"status": "present", "reason": "trust me"})

    assert response.status_code == 401
