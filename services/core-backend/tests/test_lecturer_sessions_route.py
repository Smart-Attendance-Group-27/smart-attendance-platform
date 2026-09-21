from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
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
    GeofenceRequiredError,
    InvalidCancellationReasonError,
    InvalidSessionScheduleError,
    SessionAlreadyActiveError,
    SessionAlreadyCancelledError,
    SessionAlreadyClosedError,
    SessionNotActiveError,
    SessionNotFoundError,
    TimetableEntryNotFoundError,
)
from modules.attendance_sessions.lecturer_sessions.repository import (
    LecturerSessionRecord,
    SessionStudentRecord,
)
from modules.attendance_sessions.lecturer_sessions import route as lecturer_route
from modules.attendance_sessions.qr_session.evidence import QrEvidenceRepository
from modules.attendance_sessions.lecturer_sessions.route import get_lecturer_session_service
from modules.attendance_verification.finalization.types import (
    FinalizationResult,
    FinalizationSummary,
)
from modules.attendance_verification.attendance_state import FinalAttendanceStatus
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
        checked_in_count=0,
        late_checked_in_count=0,
        failed_verification_count=0,
        absent_count=0,
        manual_count=0,
    )
    defaults.update(overrides)
    return LecturerSessionRecord(**defaults)


def build_student(**overrides) -> SessionStudentRecord:
    defaults = dict(
        verification_attempt_id=None,
        student_id=STUDENT_ID,
        registration_number="230701A",
        full_name="Amal Perera",
        verification_status=None,
        failure_reason=None,
        geofence_status=None,
        face_status=None,
        face_similarity_score=None,
        face_liveness_passed=None,
        qr_status=None,
        initial_check_in_status=None,
        checked_in_at=None,
        attendance_status=None,
        record_source=None,
        manual_reason=None,
        record_updated_at=None,
        review_status=None,
    )
    defaults.update(overrides)
    return SessionStudentRecord(**defaults)


class StubLecturerSessionService:
    def __init__(
        self,
        session: LecturerSessionRecord | None = None,
        students: list[SessionStudentRecord] | None = None,
        error: Exception | None = None,
        finalization=None,
    ) -> None:
        self.session = session if session is not None else build_session()
        self.students = students if students is not None else [build_student()]
        self.error = error
        self.finalization = finalization
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

    async def cancel_for_user(self, pool, user_id, session_id, reason, redis_client=None):
        self.calls.append("cancel")
        self.cancel_args = (user_id, session_id, reason)
        if self.error is not None:
            raise self.error
        return self.session

    async def close_for_user(self, pool, user_id, session_id, redis_client=None):
        self.calls.append("close")
        if self.error is not None:
            raise self.error
        return self.session, self.finalization

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


def test_get_session_reports_the_new_roster_counts(
    jwks_document,
    make_access_token,
) -> None:
    session = build_session(
        activated_at=CURRENT_TIME,
        enrolled_count=10,
        checked_in_count=4,
        late_checked_in_count=1,
        failed_verification_count=2,
        absent_count=1,
        manual_count=1,
    )
    service = StubLecturerSessionService(session=session)
    with build_client(jwks_document, service) as client:
        response = client.get(
            f"{SESSIONS_URL}/{SESSION_ID}",
            headers=authorize(lecturer_token(make_access_token)),
        )

    body = response.json()
    assert body["checkedInCount"] == 4
    assert body["lateCheckedInCount"] == 1
    assert body["failedVerificationCount"] == 2
    assert body["absentCount"] == 1
    assert body["manualCount"] == 1
    # 10 enrolled - 4 checked in - 1 late checked in - 2 failed
    assert body["notCheckedInCount"] == 3


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
    # No provider bound behind the stub by default: finalization stays null.
    assert response.json()["finalization"] is None


def test_close_session_reports_the_finalization_summary(
    jwks_document,
    make_access_token,
) -> None:
    finalized_at = CURRENT_TIME
    summary = FinalizationSummary(
        enrolled=10,
        present=6,
        late=1,
        absent=2,
        kept_manual=1,
        reconciled_student_ids=(STUDENT_ID,),
        deactivated_qr_batch_ids=(STUDENT_ID,),
        results=(FinalizationResult(student_id=STUDENT_ID, status=FinalAttendanceStatus.PRESENT),),
        finalized_at=finalized_at,
    )
    service = StubLecturerSessionService(finalization=summary)

    with build_client(jwks_document, service) as client:
        response = client.post(
            f"{SESSIONS_URL}/{SESSION_ID}/close",
            headers=authorize(lecturer_token(make_access_token)),
        )

    body = response.json()
    assert body["finalization"] == {
        "enrolledCount": 10,
        "presentCount": 6,
        "lateCount": 1,
        "absentCount": 2,
        "keptManualCount": 1,
        "reconciledCount": 1,
        "deactivatedQrBatchCount": 1,
        "finalizedAt": finalized_at.isoformat().replace("+00:00", "Z"),
    }


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


def test_roster_row_reports_the_new_check_in_fields(
    jwks_document,
    make_access_token,
) -> None:
    student = build_student(
        failure_reason=None,
        initial_check_in_status="late_checked_in",
        checked_in_at=CURRENT_TIME,
        record_source="automatic",
        manual_reason=None,
        record_updated_at=CURRENT_TIME,
    )
    service = StubLecturerSessionService(students=[student])

    with build_client(jwks_document, service) as client:
        response = client.get(
            f"{SESSIONS_URL}/{SESSION_ID}/students",
            headers=authorize(lecturer_token(make_access_token)),
        )

    row = response.json()[0]
    assert row["initialCheckInStatus"] == "late_checked_in"
    assert row["checkedInAt"] is not None
    assert row["recordSource"] == "automatic"


def test_roster_row_reports_qr_progress(jwks_document, make_access_token) -> None:
    student = build_student(qr_required_count=2, qr_passed_count=1)
    service = StubLecturerSessionService(students=[student])

    with build_client(jwks_document, service) as client:
        response = client.get(
            f"{SESSIONS_URL}/{SESSION_ID}/students",
            headers=authorize(lecturer_token(make_access_token)),
        )

    row = response.json()[0]
    assert row["qrRequiredCount"] == 2
    assert row["qrPassedCount"] == 1


def test_missing_lecturer_profile_returns_404(jwks_document, make_access_token) -> None:
    service = StubLecturerSessionService(error=LecturerProfileNotFoundError())
    with build_client(jwks_document, service) as client:
        response = client.get(SESSIONS_URL, headers=authorize(lecturer_token(make_access_token)))

    assert response.status_code == 404


def test_requires_bearer_token(client: TestClient) -> None:
    response = client.get(SESSIONS_URL)

    assert response.status_code == 401


def test_the_service_factory_passes_the_bound_qr_provider_through(monkeypatch) -> None:
    provider = object()
    monkeypatch.setattr(lecturer_route, "get_qr_evidence_provider", lambda: provider)
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace()))

    service = get_lecturer_session_service(request)

    assert service._qr_evidence is provider
    assert service._notification_service is None


def test_create_session_without_geofence_returns_the_documented_422(
    jwks_document,
    make_access_token,
) -> None:
    service = StubLecturerSessionService(error=GeofenceRequiredError())
    with build_client(jwks_document, service) as client:
        response = client.post(
            SESSIONS_URL,
            json=build_create_payload(requiresGeofence=False),
            headers=authorize(lecturer_token(make_access_token)),
        )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "GEOFENCE_REQUIRED"


def test_cancel_session(client: TestClient, service: StubLecturerSessionService, make_access_token) -> None:
    cancelled = build_session(activated_at=CURRENT_TIME, cancelled_at=CURRENT_TIME)
    service.session = cancelled

    response = client.post(
        f"{SESSIONS_URL}/{SESSION_ID}/cancel",
        json={"reason": "  room flooded  "},
        headers=authorize(lecturer_token(make_access_token)),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"
    assert response.json()["id"] == str(SESSION_ID)
    assert service.calls == ["cancel"]
    user_id, session_id, reason = service.cancel_args
    assert user_id == LECTURER_USER_ID
    assert session_id == SESSION_ID
    assert reason == "room flooded"


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"reason": ""},
        {"reason": "   "},
        {"reason": "ab"},
        {"reason": "x" * 501},
        {"reason": "room flooded", "status": "closed"},
    ],
)
def test_cancel_rejects_an_invalid_reason_before_reaching_the_service(
    client: TestClient,
    service: StubLecturerSessionService,
    make_access_token,
    payload: dict,
) -> None:
    response = client.post(
        f"{SESSIONS_URL}/{SESSION_ID}/cancel",
        json=payload,
        headers=authorize(lecturer_token(make_access_token)),
    )

    assert response.status_code == 422
    assert service.calls == []


@pytest.mark.parametrize(
    ("error", "status_code", "code"),
    [
        (SessionAlreadyClosedError(), 409, "SESSION_ALREADY_CLOSED"),
        (SessionAlreadyCancelledError(), 409, "SESSION_ALREADY_CANCELLED"),
        (InvalidCancellationReasonError(), 422, "REASON_INVALID"),
    ],
)
def test_cancel_maps_domain_errors_to_the_documented_codes(
    jwks_document,
    make_access_token,
    error: Exception,
    status_code: int,
    code: str,
) -> None:
    with build_client(jwks_document, StubLecturerSessionService(error=error)) as client:
        response = client.post(
            f"{SESSIONS_URL}/{SESSION_ID}/cancel",
            json={"reason": "room flooded"},
            headers=authorize(lecturer_token(make_access_token)),
        )

    assert response.status_code == status_code
    assert response.json()["detail"]["code"] == code


@pytest.mark.parametrize(
    "error",
    [SessionNotFoundError(), LecturerProfileNotFoundError()],
)
def test_cancel_returns_404_for_a_missing_session_or_profile(
    jwks_document,
    make_access_token,
    error: Exception,
) -> None:
    with build_client(jwks_document, StubLecturerSessionService(error=error)) as client:
        response = client.post(
            f"{SESSIONS_URL}/{SESSION_ID}/cancel",
            json={"reason": "room flooded"},
            headers=authorize(lecturer_token(make_access_token)),
        )

    assert response.status_code == 404


def test_a_student_cannot_cancel_a_session(client: TestClient, make_access_token) -> None:
    response = client.post(
        f"{SESSIONS_URL}/{SESSION_ID}/cancel",
        json={"reason": "room flooded"},
        headers=authorize(make_access_token(subject=LINKED_STUDENT_SUBJECT, roles=("student",))),
    )

    assert response.status_code == 403


def test_cancel_requires_a_bearer_token(client: TestClient) -> None:
    response = client.post(f"{SESSIONS_URL}/{SESSION_ID}/cancel", json={"reason": "room flooded"})

    assert response.status_code == 401


def test_the_service_factory_is_wired_to_the_real_qr_evidence_by_default() -> None:
    """Nothing patched: this is what production builds after INT-1.

    Finalization only runs, and the roster only shows QR counts, when the
    service is given a provider, so losing this wiring would silently switch
    both off again.
    """

    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace()))

    service = get_lecturer_session_service(request)

    assert isinstance(service._qr_evidence, QrEvidenceRepository)
