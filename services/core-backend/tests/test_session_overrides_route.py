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
from modules.attendance_verification.check_in.domain import (
    EffectiveVerificationPolicy,
    InitialCheckIn,
    RequiredStep,
    StepRequirement,
)
from modules.attendance_verification.geofence.exception import (
    GeofenceStillRequiredError,
    GeofenceWaivedError,
)
from modules.attendance_verification.geofence.route import get_geofence_validation_service
from modules.attendance_verification.geofence.service import StartedVerification
from modules.attendance_verification.attendance_state import InitialCheckInStatus
from modules.attendance_verification.session_overrides.domain import (
    GeofenceHealth,
    GeofenceWaiverReason,
    OverrideScope,
    SessionVerificationOverride,
)
from modules.attendance_verification.session_overrides.exception import (
    InvalidWaiverReasonError,
    SessionNotActiveError,
    SessionNotFoundError,
)
from modules.attendance_verification.session_overrides.route import get_session_override_service
from modules.attendance_verification.session_overrides.service import (
    GeofenceWaiverResult,
    SessionVerificationPolicyView,
)
from modules.identity.auth.dependencies import get_authentication_service

SESSION_ID = UUID("40000000-0000-0000-0000-000000000001")
ATTEMPT_ID = UUID("50000000-0000-0000-0000-000000000001")
OVERRIDE_ID = UUID("90000000-0000-0000-0000-000000000001")
NOW = datetime(2026, 9, 30, 9, 17, tzinfo=UTC)
POLICY_URL = f"/api/v1/lecturers/me/attendance-sessions/{SESSION_ID}/verification-policy"
WAIVER_URL = f"/api/v1/lecturers/me/attendance-sessions/{SESSION_ID}/verification-overrides/geofence"
START_URL = f"/api/v1/attendance-sessions/{SESSION_ID}/verification-attempts"
GEOFENCE_URL = f"/api/v1/attendance-sessions/{SESSION_ID}/geofence-attempts"


def authorize(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def build_view(*, waived: bool) -> SessionVerificationPolicyView:
    waiver = SessionVerificationOverride(
        id=OVERRIDE_ID, session_id=SESSION_ID, verification_factor=RequiredStep.GEOFENCE,
        scope=OverrideScope.SESSION, previous_policy=StepRequirement.REQUIRED,
        new_policy=StepRequirement.WAIVED, reason_code=GeofenceWaiverReason.GPS_INACCURATE,
        reason_text=None, performed_by=LECTURER_USER_ID, performed_by_name="Dulani Meedeniya",
        performed_at=NOW, affected_student_count=187,
    )
    return SessionVerificationPolicyView(
        session_id=SESSION_ID,
        policy=EffectiveVerificationPolicy.resolve(
            requires_geofence=True,
            requires_face_verification=True,
            waived_steps=frozenset({RequiredStep.GEOFENCE}) if waived else frozenset(),
        ),
        geofence_waiver=waiver if waived else None,
        geofence_health=GeofenceHealth(193, 6, minimum_attempts=10, warning_failure_rate=0.7),
    )


class StubOverrideService:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.waive_calls: list[tuple] = []

    async def get_policy_for_user(self, pool, user_id, session_id):
        if self.error:
            raise self.error
        return build_view(waived=False)

    async def waive_geofence_for_user(self, pool, user_id, session_id, *, reason_code, reason_text):
        self.waive_calls.append((user_id, session_id, reason_code, reason_text))
        if self.error:
            raise self.error
        return GeofenceWaiverResult(view=build_view(waived=True), created=True, reopened_attempt_count=4)


class StubGeofenceService:
    def __init__(self, error: Exception | None = None, check_in: InitialCheckIn | None = None) -> None:
        self.error = error
        self.check_in = check_in

    async def start_without_location(self, pool, user_id, session_id):
        if self.error:
            raise self.error
        return StartedVerification(verification_attempt_id=ATTEMPT_ID, initial_check_in=self.check_in)

    async def validate_attempt(self, pool, user_id, session_id, reading):
        raise self.error


def build_client(jwks_document, overrides=None, geofence=None) -> TestClient:
    app = create_app(enable_database=False)
    app.state.settings = build_settings()
    app.state.db_pool = FakePool(default_connection())
    app.dependency_overrides[get_authentication_service] = (
        lambda: build_authentication_service_for_tests(jwks_document)
    )
    if overrides is not None:
        app.dependency_overrides[get_session_override_service] = lambda: overrides
    if geofence is not None:
        app.dependency_overrides[get_geofence_validation_service] = lambda: geofence
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def lecturer_headers(make_access_token):
    return authorize(make_access_token(subject=LINKED_LECTURER_SUBJECT, roles=("lecturer",)))


@pytest.fixture
def student_headers(make_access_token):
    return authorize(make_access_token(subject=LINKED_STUDENT_SUBJECT, roles=("student",)))


def test_policy_reports_requirements_and_geofence_health(jwks_document, lecturer_headers) -> None:
    with build_client(jwks_document, overrides=StubOverrideService()) as client:
        response = client.get(POLICY_URL, headers=lecturer_headers)

    assert response.status_code == 200
    body = response.json()
    assert (body["geofence"], body["face"]) == ("required", "required")
    assert body["geofenceWaiver"] is None
    assert body["geofenceHealth"] == {
        "attempted": 193, "passed": 6, "failed": 187, "failureRatePercent": 96.9,
        "warning": True, "warningMinimumAttempts": 10, "warningFailureRatePercent": 70.0,
    }


def test_waiving_returns_the_waived_policy_and_who_did_it(jwks_document, lecturer_headers) -> None:
    service = StubOverrideService()
    with build_client(jwks_document, overrides=service) as client:
        response = client.post(
            WAIVER_URL, headers=lecturer_headers,
            json={"reasonCode": "GPS_INACCURATE", "reasonText": "Indoor hall"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["geofence"] == "waived"
    assert body["created"] is True
    assert body["reopenedAttemptCount"] == 4
    assert body["geofenceWaiver"]["performedByName"] == "Dulani Meedeniya"
    assert body["geofenceWaiver"]["affectedStudentCount"] == 187
    assert service.waive_calls == [(LECTURER_USER_ID, SESSION_ID, "GPS_INACCURATE", "Indoor hall")]


def test_an_unknown_reason_code_is_rejected(jwks_document, lecturer_headers) -> None:
    service = StubOverrideService()
    with build_client(jwks_document, overrides=service) as client:
        response = client.post(WAIVER_URL, headers=lecturer_headers, json={"reasonCode": "BORED"})

    assert response.status_code == 422
    assert service.waive_calls == []


@pytest.mark.parametrize(
    ("error", "status", "code"),
    [
        (SessionNotFoundError(), 404, "SESSION_NOT_FOUND"),
        (SessionNotActiveError(), 409, "SESSION_NOT_ACTIVE"),
        (InvalidWaiverReasonError("missing"), 422, "REASON_INVALID"),
    ],
)
def test_waiver_errors_map_to_http(jwks_document, lecturer_headers, error, status, code) -> None:
    with build_client(jwks_document, overrides=StubOverrideService(error)) as client:
        response = client.post(WAIVER_URL, headers=lecturer_headers, json={"reasonCode": "OTHER"})

    assert response.status_code == status
    assert response.json()["detail"]["code"] == code


def test_students_cannot_waive_geofence(jwks_document, student_headers) -> None:
    service = StubOverrideService()
    with build_client(jwks_document, overrides=service) as client:
        response = client.post(WAIVER_URL, headers=student_headers, json={"reasonCode": "GPS_UNAVAILABLE"})

    assert response.status_code == 403
    assert service.waive_calls == []


def test_a_student_starts_verification_without_a_location(jwks_document, student_headers) -> None:
    with build_client(jwks_document, geofence=StubGeofenceService()) as client:
        response = client.post(START_URL, headers=student_headers)

    assert response.status_code == 200
    assert response.json() == {
        "verificationAttemptId": str(ATTEMPT_ID),
        "geofenceRequirement": "waived",
        "nextStep": "FACE_VERIFICATION",
        "initialCheckIn": None,
    }


def test_starting_without_a_location_can_check_in_when_face_is_not_required(
    jwks_document, student_headers,
) -> None:
    check_in = InitialCheckIn(checked_in_at=NOW, status=InitialCheckInStatus.CHECKED_IN)
    with build_client(jwks_document, geofence=StubGeofenceService(check_in=check_in)) as client:
        response = client.post(START_URL, headers=student_headers)

    assert response.json()["nextStep"] == "NONE"
    assert response.json()["initialCheckIn"]["status"] == "checked_in"


def test_starting_without_a_location_needs_a_waiver(jwks_document, student_headers) -> None:
    error = GeofenceStillRequiredError("Location verification is still required for this session.")
    with build_client(jwks_document, geofence=StubGeofenceService(error)) as client:
        response = client.post(START_URL, headers=student_headers)

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "GEOFENCE_REQUIRED"


def test_a_location_reading_after_a_waiver_is_answered_with_geofence_waived(
    jwks_document, student_headers,
) -> None:
    error = GeofenceWaivedError("Location verification was waived for this session.")
    with build_client(jwks_document, geofence=StubGeofenceService(error)) as client:
        response = client.post(
            GEOFENCE_URL, headers=student_headers,
            json={"latitude": 6.79, "longitude": 79.9, "accuracyM": 5, "capturedAt": NOW.isoformat()},
        )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "GEOFENCE_WAIVED"


def test_no_qr_cancel_or_waive_endpoint_exists() -> None:
    # Voiding is the one way to take a QR batch out of attendance.
    app = create_app(enable_database=False)
    qr_paths = [path for path in app.openapi()["paths"] if "qr" in path]
    assert any(path.endswith("/void") for path in qr_paths)
    assert not any("cancel" in path or "waive" in path or "override" in path for path in qr_paths)
