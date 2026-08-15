from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from conftest import (
    LINKED_LECTURER_SUBJECT,
    STUDENT_USER_ID,
    FakePool,
    build_authentication_service_for_tests,
    build_settings,
    default_connection,
)
from main import create_app
from modules.academic.student_profile.exception import StudentProfileNotFoundError
from modules.attendance_sessions.active_sessions.repository import (
    ActiveAttendanceSessionRecord,
)
from modules.attendance_sessions.active_sessions.route import (
    get_active_attendance_session_service,
)
from modules.identity.auth.dependencies import get_authentication_service

ACTIVE_SESSIONS_URL = "/api/v1/students/me/attendance-sessions/active"
SESSION_ID = UUID("40000000-0000-0000-0000-000000000001")
CURRENT_TIME = datetime(2026, 8, 13, 5, 30, tzinfo=UTC)


def authorize(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def build_session() -> ActiveAttendanceSessionRecord:
    return ActiveAttendanceSessionRecord(
        id=SESSION_ID,
        course_code="CS3203",
        course_name="Software Engineering Project",
        session_title="Geofence Demo - Near Centre",
        session_type="lecture",
        scheduled_start_at=CURRENT_TIME - timedelta(minutes=5),
        scheduled_end_at=CURRENT_TIME + timedelta(hours=1),
        check_in_opens_at=CURRENT_TIME - timedelta(minutes=2),
        check_in_closes_at=CURRENT_TIME + timedelta(minutes=30),
        late_after_at=CURRENT_TIME + timedelta(minutes=15),
        venue="LH-02",
        requires_face_verification=True,
        requires_geofence=True,
        requires_qr=False,
    )


class StubActiveSessionService:
    def __init__(
        self,
        sessions: list[ActiveAttendanceSessionRecord] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.sessions = sessions if sessions is not None else [build_session()]
        self.error = error
        self.requested_user_id: UUID | None = None

    async def list_for_user(
        self,
        pool: object,
        user_id: UUID,
    ) -> list[ActiveAttendanceSessionRecord]:
        self.requested_user_id = user_id
        if self.error is not None:
            raise self.error
        return self.sessions


def build_client(jwks_document, service: StubActiveSessionService) -> TestClient:
    app = create_app(enable_database=False)
    app.state.settings = build_settings()
    app.state.db_pool = FakePool(default_connection())
    app.dependency_overrides[get_authentication_service] = (
        lambda: build_authentication_service_for_tests(jwks_document)
    )
    app.dependency_overrides[get_active_attendance_session_service] = lambda: service
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def service() -> StubActiveSessionService:
    return StubActiveSessionService()


@pytest.fixture
def client(jwks_document, service: StubActiveSessionService):
    with build_client(jwks_document, service) as test_client:
        yield test_client


def test_returns_privacy_safe_camel_case_sessions(
    client: TestClient,
    make_access_token,
) -> None:
    response = client.get(
        ACTIVE_SESSIONS_URL,
        headers=authorize(make_access_token()),
    )

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": str(SESSION_ID),
            "courseCode": "CS3203",
            "courseName": "Software Engineering Project",
            "sessionTitle": "Geofence Demo - Near Centre",
            "sessionType": "lecture",
            "scheduledStartAt": "2026-08-13T05:25:00Z",
            "scheduledEndAt": "2026-08-13T06:30:00Z",
            "checkInOpensAt": "2026-08-13T05:28:00Z",
            "checkInClosesAt": "2026-08-13T06:00:00Z",
            "lateAfterAt": "2026-08-13T05:45:00Z",
            "venue": "LH-02",
            "requiresFaceVerification": True,
            "requiresGeofence": True,
            "requiresQr": False,
        }
    ]

    for forbidden_field in (
        "studentId",
        "userId",
        "centreLatitude",
        "centreLongitude",
        "radiusM",
    ):
        assert forbidden_field not in response.text


def test_service_receives_user_identity_from_token(
    client: TestClient,
    service: StubActiveSessionService,
    make_access_token,
) -> None:
    response = client.get(
        ACTIVE_SESSIONS_URL,
        headers=authorize(make_access_token()),
    )

    assert response.status_code == 200
    assert service.requested_user_id == STUDENT_USER_ID


def test_returns_empty_list_when_no_session_is_open(
    jwks_document,
    make_access_token,
) -> None:
    with build_client(jwks_document, StubActiveSessionService(sessions=[])) as client:
        response = client.get(
            ACTIVE_SESSIONS_URL,
            headers=authorize(make_access_token()),
        )

    assert response.status_code == 200
    assert response.json() == []


def test_requires_bearer_token(client: TestClient) -> None:
    response = client.get(ACTIVE_SESSIONS_URL)

    assert response.status_code == 401


def test_rejects_invalid_token(client: TestClient) -> None:
    response = client.get(
        ACTIVE_SESSIONS_URL,
        headers=authorize("not-a-jwt"),
    )

    assert response.status_code == 401


def test_rejects_non_student_role(
    client: TestClient,
    make_access_token,
) -> None:
    response = client.get(
        ACTIVE_SESSIONS_URL,
        headers=authorize(
            make_access_token(
                subject=LINKED_LECTURER_SUBJECT,
                roles=("lecturer",),
            ),
        ),
    )

    assert response.status_code == 403


def test_missing_active_profile_returns_not_found(
    jwks_document,
    make_access_token,
) -> None:
    service = StubActiveSessionService(error=StudentProfileNotFoundError())

    with build_client(jwks_document, service) as client:
        response = client.get(
            ACTIVE_SESSIONS_URL,
            headers=authorize(make_access_token()),
        )

    assert response.status_code == 404
    assert response.json()["detail"] == (
        "An active student profile was not found for this account."
    )
