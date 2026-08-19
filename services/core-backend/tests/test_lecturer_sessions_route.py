from datetime import UTC, datetime, timedelta
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
from modules.attendance_sessions.lecturer_sessions.exception import (
    ClassroomGeofenceNotConfiguredError,
    InvalidSessionScheduleError,
    SessionAlreadyActiveError,
    SessionNotActiveError,
    SessionNotFoundError,
    TimetableEntryNotFoundError,
)
from modules.attendance_sessions.lecturer_sessions.repository import (
    LecturerSessionRecord,
    SessionStudentRecord,
)
from modules.attendance_sessions.lecturer_sessions.route import get_lecturer_session_service
from modules.identity.auth.dependencies import get_authentication_service

SESSIONS_URL = "/api/v1/lecturers/me/attendance-sessions"
SESSION_ID = UUID("40000000-0000-0000-0000-000000000001")
STUDENT_ID = UUID("23000000-0000-0000-0000-000000000001")
CURRENT_TIME = datetime(2026, 8, 13, 5, 30, tzinfo=UTC)


def authorize(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def lecturer_token(make_access_token) -> str:
    return make_access_token(subject=LINKED_LECTURER_SUBJECT, roles=("lecturer",))


def build_session(**overrides) -> LecturerSessionRecord:
    defaults = dict(
        id=SESSION_ID,
        course_offering_id=UUID("30000000-0000-0000-0000-000000000001"),
        course_code="CS3203",
        course_name="Software Engineering Project",
        classroom_code="LH-02",
        scheduled_start_at=CURRENT_TIME,
        scheduled_end_at=CURRENT_TIME + timedelta(hours=1),
        check_in_opens_at=CURRENT_TIME - timedelta(minutes=5),
        check_in_closes_at=CURRENT_TIME + timedelta(minutes=30),
        late_after_at=CURRENT_TIME + timedelta(minutes=15),
        activated_at=None,
        closed_at=None,
        cancelled_at=None,
        requires_face_verification=True,
        requires_geofence=True,
        requires_qr=False,
        enrolled_count=40,
        present_count=0,
        late_count=0,
        pending_review_count=0,
    )
    defaults.update(overrides)
    return LecturerSessionRecord(**defaults)


def build_student() -> SessionStudentRecord:
    return SessionStudentRecord(
        verification_attempt_id=None,
        student_id=STUDENT_ID,
        registration_number="230701A",
        full_name="Amal Perera",
        verification_status=None,
        geofence_status=None,
        face_status=None,
        face_similarity_score=None,
        face_liveness_passed=None,
        qr_status=None,
        attendance_status=None,
        review_status=None,
        checked_in_at=None,
    )


class StubLecturerSessionService:
    def __init__(
        self,
        session: LecturerSessionRecord | None = None,
        students: list[SessionStudentRecord] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.session = session if session is not None else build_session()
        self.students = students if students is not None else [build_student()]
        self.error = error
        self.calls: list[str] = []

    async def list_for_user(self, pool, user_id):
        self.calls.append("list")
        if self.error is not None:
            raise self.error
        return [self.session]

    async def get_for_user(self, pool, user_id, session_id):
        self.calls.append("get")
        if self.error is not None:
            raise self.error
        return self.session

    async def create_for_user(self, pool, user_id, **kwargs):
        self.calls.append("create")
        if self.error is not None:
            raise self.error
        return self.session

    async def activate_for_user(self, pool, user_id, session_id):
        self.calls.append("activate")
        if self.error is not None:
            raise self.error
        return self.session

    async def close_for_user(self, pool, user_id, session_id):
        self.calls.append("close")
        if self.error is not None:
            raise self.error
        return self.session

    async def list_students_for_user(self, pool, user_id, session_id):
        self.calls.append("students")
        if self.error is not None:
            raise self.error
        return self.students


def build_client(jwks_document, service: StubLecturerSessionService) -> TestClient:
    app = create_app(enable_database=False)
    app.state.settings = build_settings()
    app.state.db_pool = FakePool(default_connection())
    app.dependency_overrides[get_authentication_service] = (
        lambda: build_authentication_service_for_tests(jwks_document)
    )
    app.dependency_overrides[get_lecturer_session_service] = lambda: service
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def service() -> StubLecturerSessionService:
    return StubLecturerSessionService()


@pytest.fixture
def client(jwks_document, service: StubLecturerSessionService):
    with build_client(jwks_document, service) as test_client:
        yield test_client


def test_lists_my_sessions(client: TestClient, make_access_token) -> None:
    response = client.get(SESSIONS_URL, headers=authorize(lecturer_token(make_access_token)))

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["id"] == str(SESSION_ID)
    assert body[0]["status"] == "scheduled"


def test_rejects_non_lecturer_role(client: TestClient, make_access_token) -> None:
    response = client.get(
        SESSIONS_URL,
        headers=authorize(make_access_token(subject=LINKED_STUDENT_SUBJECT, roles=("student",))),
    )

    assert response.status_code == 403


def test_get_session_returns_derived_status_for_active_session(
    jwks_document,
    make_access_token,
) -> None:
    service = StubLecturerSessionService(session=build_session(activated_at=CURRENT_TIME))
    with build_client(jwks_document, service) as client:
        response = client.get(
            f"{SESSIONS_URL}/{SESSION_ID}",
            headers=authorize(lecturer_token(make_access_token)),
        )

    assert response.status_code == 200
    assert response.json()["status"] == "active"


def test_get_missing_session_returns_404(jwks_document, make_access_token) -> None:
    service = StubLecturerSessionService(error=SessionNotFoundError())
    with build_client(jwks_document, service) as client:
        response = client.get(
            f"{SESSIONS_URL}/{SESSION_ID}",
            headers=authorize(lecturer_token(make_access_token)),
        )

    assert response.status_code == 404


def build_create_payload(**overrides) -> dict:
    payload = {
        "timetableEntryId": "3a000000-0000-0000-0000-000000000001",
        "sessionTitle": "CS3203 Lecture",
        "sessionType": "lecture",
        "scheduledStartAt": CURRENT_TIME.isoformat(),
        "scheduledEndAt": (CURRENT_TIME + timedelta(hours=1)).isoformat(),
        "requiresFaceVerification": True,
        "requiresGeofence": True,
        "requiresQr": False,
    }
    payload.update(overrides)
    return payload


def test_create_session(client: TestClient, service: StubLecturerSessionService, make_access_token) -> None:
    response = client.post(
        SESSIONS_URL,
        json=build_create_payload(),
        headers=authorize(lecturer_token(make_access_token)),
    )

    assert response.status_code == 201
    assert service.calls == ["create"]
    assert response.json()["id"] == str(SESSION_ID)


def test_create_session_rejects_non_lecturer_role(client: TestClient, make_access_token) -> None:
    response = client.post(
        SESSIONS_URL,
        json=build_create_payload(),
        headers=authorize(make_access_token(subject=LINKED_STUDENT_SUBJECT, roles=("student",))),
    )

    assert response.status_code == 403


def test_create_session_missing_timetable_entry_returns_404(jwks_document, make_access_token) -> None:
    service = StubLecturerSessionService(error=TimetableEntryNotFoundError())
    with build_client(jwks_document, service) as client:
        response = client.post(
            SESSIONS_URL,
            json=build_create_payload(),
            headers=authorize(lecturer_token(make_access_token)),
        )

    assert response.status_code == 404


def test_create_session_invalid_schedule_returns_422(jwks_document, make_access_token) -> None:
    service = StubLecturerSessionService(error=InvalidSessionScheduleError("bad schedule"))
    with build_client(jwks_document, service) as client:
        response = client.post(
            SESSIONS_URL,
            json=build_create_payload(),
            headers=authorize(lecturer_token(make_access_token)),
        )

    assert response.status_code == 422


def test_create_session_geofence_not_configured_returns_422(jwks_document, make_access_token) -> None:
    service = StubLecturerSessionService(error=ClassroomGeofenceNotConfiguredError("no geofence"))
    with build_client(jwks_document, service) as client:
        response = client.post(
            SESSIONS_URL,
            json=build_create_payload(),
            headers=authorize(lecturer_token(make_access_token)),
        )

    assert response.status_code == 422


def test_activate_session(client: TestClient, service: StubLecturerSessionService, make_access_token) -> None:
    response = client.post(
        f"{SESSIONS_URL}/{SESSION_ID}/activate",
        headers=authorize(lecturer_token(make_access_token)),
    )

    assert response.status_code == 200
    assert service.calls == ["activate"]


def test_activate_already_active_session_returns_409(jwks_document, make_access_token) -> None:
    service = StubLecturerSessionService(error=SessionAlreadyActiveError())
    with build_client(jwks_document, service) as client:
        response = client.post(
            f"{SESSIONS_URL}/{SESSION_ID}/activate",
            headers=authorize(lecturer_token(make_access_token)),
        )

    assert response.status_code == 409


def test_close_session(client: TestClient, service: StubLecturerSessionService, make_access_token) -> None:
    response = client.post(
        f"{SESSIONS_URL}/{SESSION_ID}/close",
        headers=authorize(lecturer_token(make_access_token)),
    )

    assert response.status_code == 200
    assert service.calls == ["close"]


def test_close_inactive_session_returns_409(jwks_document, make_access_token) -> None:
    service = StubLecturerSessionService(error=SessionNotActiveError())
    with build_client(jwks_document, service) as client:
        response = client.post(
            f"{SESSIONS_URL}/{SESSION_ID}/close",
            headers=authorize(lecturer_token(make_access_token)),
        )

    assert response.status_code == 409


def test_lists_students_without_leaking_biometric_data(client: TestClient, make_access_token) -> None:
    response = client.get(
        f"{SESSIONS_URL}/{SESSION_ID}/students",
        headers=authorize(lecturer_token(make_access_token)),
    )

    assert response.status_code == 200
    body = response.json()
    assert body[0]["studentId"] == str(STUDENT_ID)
    for forbidden_field in ("faceEmbedding", "faceImage", "latitude", "longitude"):
        assert forbidden_field not in response.text


def test_missing_lecturer_profile_returns_404(jwks_document, make_access_token) -> None:
    service = StubLecturerSessionService(error=LecturerProfileNotFoundError())
    with build_client(jwks_document, service) as client:
        response = client.get(SESSIONS_URL, headers=authorize(lecturer_token(make_access_token)))

    assert response.status_code == 404


def test_requires_bearer_token(client: TestClient) -> None:
    response = client.get(SESSIONS_URL)

    assert response.status_code == 401
