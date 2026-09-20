from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from conftest import (
    LINKED_LECTURER_SUBJECT,
    FakePool,
    build_authentication_service_for_tests,
    build_settings,
    default_connection,
)
from main import create_app
from modules.academic.student_profile.exception import StudentProfileNotFoundError
from modules.attendance_sessions.active_sessions.route import (
    get_student_attendance_state_service,
)
from modules.attendance_sessions.active_sessions.state_service import (
    FinalAttendanceState,
    InitialCheckInState,
    SessionNotFoundError,
    SessionState,
    StudentAttendanceState,
    VerificationState,
)
from modules.identity.auth.dependencies import get_authentication_service

SESSION_ID = UUID("40000000-0000-0000-0000-000000000001")
ATTENDANCE_URL = f"/api/v1/students/me/attendance-sessions/{SESSION_ID}/attendance"
CURRENT_TIME = datetime(2026, 9, 21, 9, 5, tzinfo=UTC)


def authorize(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def build_state(**overrides) -> StudentAttendanceState:
    values = dict(
        session_id=SESSION_ID,
        course_code="CS3203",
        course_name="Software Engineering Project",
        session_title="Week 7",
        session_type="lecture",
        session_state=SessionState.ACTIVE,
        scheduled_start_at=CURRENT_TIME - timedelta(minutes=5),
        scheduled_end_at=CURRENT_TIME + timedelta(hours=1),
        check_in_opens_at=CURRENT_TIME - timedelta(minutes=5),
        check_in_closes_at=CURRENT_TIME + timedelta(minutes=25),
        late_after_at=CURRENT_TIME + timedelta(minutes=15),
        requires_face_verification=True,
        qr_enabled=False,
        can_start_check_in=True,
        verification=VerificationState(
            attempt_status=None,
            failure_reason=None,
            geofence_status=None,
            face_status=None,
            liveness_passed=None,
        ),
        initial_check_in=None,
        final_attendance=None,
    )
    values.update(overrides)
    return StudentAttendanceState(**values)


class StubStateService:
    def __init__(
        self,
        *,
        state: StudentAttendanceState | None = None,
        error: Exception | None = None,
    ) -> None:
        self.state = state or build_state()
        self.error = error
        self.calls: list[tuple[UUID, UUID]] = []

    async def get_for_user(self, pool, user_id, session_id):
        self.calls.append((user_id, session_id))
        if self.error is not None:
            raise self.error
        return self.state


def build_client(jwks_document, service: StubStateService) -> TestClient:
    app = create_app(enable_database=False)
    app.state.settings = build_settings()
    app.state.db_pool = FakePool(default_connection())
    app.dependency_overrides[get_authentication_service] = (
        lambda: build_authentication_service_for_tests(jwks_document)
    )
    app.dependency_overrides[get_student_attendance_state_service] = lambda: service
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def service() -> StubStateService:
    return StubStateService()


@pytest.fixture
def client(jwks_document, service: StubStateService):
    with build_client(jwks_document, service) as test_client:
        yield test_client


def test_returns_the_camel_case_attendance_state(
    client: TestClient,
    make_access_token,
) -> None:
    response = client.get(ATTENDANCE_URL, headers=authorize(make_access_token()))

    assert response.status_code == 200
    body = response.json()
    assert body["sessionId"] == str(SESSION_ID)
    assert body["sessionState"] == "active"
    assert body["canStartCheckIn"] is True
    assert body["verification"] == {
        "attemptStatus": None,
        "failureReason": None,
        "geofenceStatus": None,
        "faceStatus": None,
        "livenessPassed": None,
    }
    assert body["initialCheckIn"] is None
    assert body["finalAttendance"] is None


def test_a_checked_in_state_serializes_its_nested_objects(
    jwks_document,
    make_access_token,
) -> None:
    checked_in_at = CURRENT_TIME - timedelta(minutes=2)
    state = build_state(
        can_start_check_in=False,
        verification=VerificationState(
            attempt_status="checked_in",
            failure_reason=None,
            geofence_status="passed",
            face_status="passed",
            liveness_passed=True,
        ),
        initial_check_in=InitialCheckInState(
            status="checked_in",
            checked_in_at=checked_in_at,
        ),
    )
    service = StubStateService(state=state)

    with build_client(jwks_document, service) as client:
        response = client.get(ATTENDANCE_URL, headers=authorize(make_access_token()))

    body = response.json()
    assert body["initialCheckIn"] == {
        "status": "checked_in",
        "checkedInAt": checked_in_at.isoformat().replace("+00:00", "Z"),
    }
    assert body["verification"]["livenessPassed"] is True


def test_a_final_attendance_record_serializes(
    jwks_document,
    make_access_token,
) -> None:
    decided_at = CURRENT_TIME - timedelta(hours=1)
    state = build_state(
        session_state=SessionState.CLOSED,
        can_start_check_in=False,
        final_attendance=FinalAttendanceState(
            status="present",
            source="automatic",
            decided_at=decided_at,
        ),
    )
    service = StubStateService(state=state)

    with build_client(jwks_document, service) as client:
        response = client.get(ATTENDANCE_URL, headers=authorize(make_access_token()))

    body = response.json()
    assert body["sessionState"] == "closed"
    assert body["finalAttendance"] == {
        "status": "present",
        "source": "automatic",
        "decidedAt": decided_at.isoformat().replace("+00:00", "Z"),
    }


def test_the_session_id_from_the_path_reaches_the_service(
    client: TestClient,
    service: StubStateService,
    make_access_token,
) -> None:
    client.get(ATTENDANCE_URL, headers=authorize(make_access_token()))

    assert [call[1] for call in service.calls] == [SESSION_ID]


def test_a_missing_session_or_a_non_roster_student_returns_session_not_found(
    jwks_document,
    make_access_token,
) -> None:
    service = StubStateService(error=SessionNotFoundError())

    with build_client(jwks_document, service) as client:
        response = client.get(ATTENDANCE_URL, headers=authorize(make_access_token()))

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "SESSION_NOT_FOUND"


def test_a_missing_student_profile_returns_student_profile_not_found(
    jwks_document,
    make_access_token,
) -> None:
    service = StubStateService(error=StudentProfileNotFoundError())

    with build_client(jwks_document, service) as client:
        response = client.get(ATTENDANCE_URL, headers=authorize(make_access_token()))

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "STUDENT_PROFILE_NOT_FOUND"


def test_requires_bearer_token(client: TestClient) -> None:
    response = client.get(ATTENDANCE_URL)

    assert response.status_code == 401


def test_rejects_non_student_role(client: TestClient, make_access_token) -> None:
    response = client.get(
        ATTENDANCE_URL,
        headers=authorize(
            make_access_token(subject=LINKED_LECTURER_SUBJECT, roles=("lecturer",)),
        ),
    )

    assert response.status_code == 403
