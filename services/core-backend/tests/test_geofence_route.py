from datetime import UTC, datetime
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
from modules.attendance_verification.geofence.exception import (
    ActiveStudentProfileNotFoundError,
    AttendanceSessionNotActiveError,
    AttendanceSessionNotFoundError,
    CheckInClosedError,
    CheckInNotOpenError,
    GeofenceAttemptLimitReachedError,
    GeofenceNotConfiguredError,
    GeofenceNotRequiredError,
    StudentNotEligibleError,
    VerificationAttemptClosedError,
)
from modules.attendance_verification.geofence.route import (
    get_geofence_validation_service,
)
from modules.attendance_verification.geofence.service import RecordedGeofenceAttempt
from modules.attendance_verification.geofence.types import (
    GeofenceDecision,
    GeofenceNextStep,
    GeofenceReading,
    GeofenceReason,
    GeofenceValidationResult,
)
from modules.identity.auth.dependencies import get_authentication_service

SESSION_ID = UUID("40000000-0000-0000-0000-000000000001")
VERIFICATION_ATTEMPT_ID = UUID("50000000-0000-0000-0000-000000000001")
ATTEMPT_URL = f"/api/v1/attendance-sessions/{SESSION_ID}/geofence-attempts"


def valid_payload(**overrides):
    payload = {
        "latitude": 6.795132,
        "longitude": 79.900421,
        "accuracyM": 18.5,
        "capturedAt": "2026-08-13T05:30:14Z",
        "mocked": False,
    }
    payload.update(overrides)
    return payload


def authorize(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def build_outcome(
    decision: GeofenceDecision = GeofenceDecision.PASSED,
) -> RecordedGeofenceAttempt:
    if decision is GeofenceDecision.PASSED:
        result = GeofenceValidationResult(
            decision=decision,
            distance_m=18.7,
            allowed_radius_m=70.0,
            next_step=GeofenceNextStep.FACE_VERIFICATION,
            reason=None,
        )
    elif decision is GeofenceDecision.FAILED:
        result = GeofenceValidationResult(
            decision=decision,
            distance_m=1140.5,
            allowed_radius_m=70.0,
            next_step=GeofenceNextStep.NONE,
            reason=GeofenceReason.OUTSIDE_GEOFENCE,
        )
    else:
        result = GeofenceValidationResult(
            decision=decision,
            distance_m=66.0,
            allowed_radius_m=70.0,
            next_step=GeofenceNextStep.RETRY_LOCATION,
            reason=GeofenceReason.NEAR_GEOFENCE_BOUNDARY,
        )

    return RecordedGeofenceAttempt(
        verification_attempt_id=VERIFICATION_ATTEMPT_ID,
        attempt_number=1,
        result=result,
    )


class StubGeofenceService:
    def __init__(
        self,
        *,
        outcome: RecordedGeofenceAttempt | None = None,
        error: Exception | None = None,
    ) -> None:
        self.outcome = outcome or build_outcome()
        self.error = error
        self.calls: list[tuple[object, UUID, UUID, GeofenceReading]] = []

    async def validate_attempt(
        self,
        pool: object,
        user_id: UUID,
        session_id: UUID,
        reading: GeofenceReading,
    ) -> RecordedGeofenceAttempt:
        self.calls.append((pool, user_id, session_id, reading))
        if self.error is not None:
            raise self.error
        return self.outcome


def build_client(jwks_document, service: StubGeofenceService) -> TestClient:
    app = create_app(enable_database=False)
    app.state.settings = build_settings()
    app.state.db_pool = FakePool(default_connection())
    app.dependency_overrides[get_authentication_service] = (
        lambda: build_authentication_service_for_tests(jwks_document)
    )
    app.dependency_overrides[get_geofence_validation_service] = lambda: service
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def service() -> StubGeofenceService:
    return StubGeofenceService()


@pytest.fixture
def client(jwks_document, service: StubGeofenceService):
    with build_client(jwks_document, service) as test_client:
        yield test_client


def test_pass_returns_the_camel_case_contract(
    client: TestClient,
    make_access_token,
) -> None:
    response = client.post(
        ATTEMPT_URL,
        json=valid_payload(),
        headers=authorize(make_access_token()),
    )

    assert response.status_code == 200
    assert response.json() == {
        "verificationAttemptId": str(VERIFICATION_ATTEMPT_ID),
        "attemptNumber": 1,
        "decision": "PASSED",
        "distanceM": 18.7,
        "allowedRadiusM": 70.0,
        "nextStep": "FACE_VERIFICATION",
        "reason": None,
    }


@pytest.mark.parametrize(
    ("decision", "expected_payload"),
    [
        (
            GeofenceDecision.FAILED,
            {
                "decision": "FAILED",
                "distanceM": 1140.5,
                "nextStep": "NONE",
                "reason": "OUTSIDE_GEOFENCE",
            },
        ),
        (
            GeofenceDecision.RETRY_REQUIRED,
            {
                "decision": "RETRY_REQUIRED",
                "distanceM": 66.0,
                "nextStep": "RETRY_LOCATION",
                "reason": "NEAR_GEOFENCE_BOUNDARY",
            },
        ),
    ],
)
def test_failed_and_retry_decisions_are_successful_http_results(
    jwks_document,
    make_access_token,
    decision: GeofenceDecision,
    expected_payload: dict[str, object],
) -> None:
    service = StubGeofenceService(outcome=build_outcome(decision))

    with build_client(jwks_document, service) as client:
        response = client.post(
            ATTEMPT_URL,
            json=valid_payload(),
            headers=authorize(make_access_token()),
        )

    assert response.status_code == 200
    for field, value in expected_payload.items():
        assert response.json()[field] == value


def test_service_receives_identity_from_token_and_mobile_reading(
    client: TestClient,
    service: StubGeofenceService,
    make_access_token,
) -> None:
    response = client.post(
        ATTEMPT_URL,
        json=valid_payload(accuracyM=None, mocked=True),
        headers=authorize(make_access_token()),
    )

    assert response.status_code == 200
    pool, user_id, session_id, reading = service.calls[0]
    assert pool is not None
    assert user_id == STUDENT_USER_ID
    assert session_id == SESSION_ID
    assert reading == GeofenceReading(
        latitude=6.795132,
        longitude=79.900421,
        accuracy_m=None,
        captured_at=datetime(2026, 8, 13, 5, 30, 14, tzinfo=UTC),
        mocked=True,
    )


def test_response_never_exposes_coordinates_or_student_identity(
    client: TestClient,
    make_access_token,
) -> None:
    response = client.post(
        ATTEMPT_URL,
        json=valid_payload(),
        headers=authorize(make_access_token()),
    )

    assert response.status_code == 200
    payload = response.json()
    for forbidden_field in (
        "latitude",
        "longitude",
        "centreLatitude",
        "centreLongitude",
        "studentId",
        "userId",
    ):
        assert forbidden_field not in payload


def test_requires_a_bearer_token(client: TestClient) -> None:
    response = client.post(ATTEMPT_URL, json=valid_payload())

    assert response.status_code == 401
    assert response.json()["detail"] == "A bearer access token is required."


def test_rejects_an_invalid_token(client: TestClient) -> None:
    response = client.post(
        ATTEMPT_URL,
        json=valid_payload(),
        headers=authorize("not-a-jwt"),
    )

    assert response.status_code == 401


def test_rejects_a_non_student_role(
    client: TestClient,
    make_access_token,
) -> None:
    response = client.post(
        ATTEMPT_URL,
        json=valid_payload(),
        headers=authorize(
            make_access_token(
                subject=LINKED_LECTURER_SUBJECT,
                roles=("lecturer",),
            ),
        ),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "The 'student' role is required."


@pytest.mark.parametrize(
    "extra_field",
    [
        {"studentId": "23000000-0000-0000-0000-000000000002"},
        {"decision": "PASSED"},
        {"centreLatitude": 6.795132},
        {"allowedRadiusM": 5000},
    ],
)
def test_rejects_client_supplied_identity_decision_and_configuration(
    client: TestClient,
    service: StubGeofenceService,
    make_access_token,
    extra_field: dict[str, object],
) -> None:
    response = client.post(
        ATTEMPT_URL,
        json=valid_payload(**extra_field),
        headers=authorize(make_access_token()),
    )

    assert response.status_code == 422
    assert service.calls == []


@pytest.mark.parametrize(
    "payload",
    [
        {"longitude": 79.900421, "accuracyM": 5, "capturedAt": "2026-08-13T05:30:14Z"},
        valid_payload(latitude=91),
        valid_payload(accuracyM=-1),
        valid_payload(capturedAt="2026-08-13T05:30:14"),
    ],
)
def test_rejects_invalid_requests(
    client: TestClient,
    service: StubGeofenceService,
    make_access_token,
    payload: dict[str, object],
) -> None:
    response = client.post(
        ATTEMPT_URL,
        json=payload,
        headers=authorize(make_access_token()),
    )

    assert response.status_code == 422
    assert service.calls == []


def test_rejects_a_malformed_session_id(
    client: TestClient,
    make_access_token,
) -> None:
    response = client.post(
        "/api/v1/attendance-sessions/not-a-uuid/geofence-attempts",
        json=valid_payload(),
        headers=authorize(make_access_token()),
    )

    assert response.status_code == 422


@pytest.mark.parametrize(
    ("error", "expected_detail"),
    [
        (
            ActiveStudentProfileNotFoundError(
                "No active student profile exists for this account.",
            ),
            "No active student profile exists for this account.",
        ),
        (
            AttendanceSessionNotFoundError("The attendance session was not found."),
            "The attendance session was not found.",
        ),
    ],
)
def test_maps_missing_resources_to_not_found(
    jwks_document,
    make_access_token,
    error: Exception,
    expected_detail: str,
) -> None:
    with build_client(
        jwks_document,
        StubGeofenceService(error=error),
    ) as client:
        response = client.post(
            ATTEMPT_URL,
            json=valid_payload(),
            headers=authorize(make_access_token()),
        )

    assert response.status_code == 404
    assert response.json()["detail"] == expected_detail


def test_maps_ineligible_student_to_forbidden(
    jwks_document,
    make_access_token,
) -> None:
    error = StudentNotEligibleError(
        "The student is not eligible for this attendance session.",
    )

    with build_client(
        jwks_document,
        StubGeofenceService(error=error),
    ) as client:
        response = client.post(
            ATTEMPT_URL,
            json=valid_payload(),
            headers=authorize(make_access_token()),
        )

    assert response.status_code == 403
    assert response.json()["detail"] == "STUDENT_NOT_ELIGIBLE"


@pytest.mark.parametrize(
    ("error", "expected_detail"),
    [
        (
            AttendanceSessionNotActiveError("The attendance session is not active."),
            "SESSION_NOT_ACTIVE",
        ),
        (CheckInNotOpenError("Check-in has not opened yet."), "CHECK_IN_NOT_OPEN"),
        (CheckInClosedError("Check-in is closed."), "CHECK_IN_CLOSED"),
        (
            GeofenceNotRequiredError(
                "Geofence validation is not required for this session.",
            ),
            "Geofence validation is not required for this session.",
        ),
        (
            GeofenceNotConfiguredError(
                "The attendance session has no complete geofence snapshot.",
            ),
            "GEOFENCE_NOT_CONFIGURED",
        ),
        (GeofenceAttemptLimitReachedError(3), "ATTEMPT_LIMIT_REACHED"),
        (
            VerificationAttemptClosedError(
                "The verification attempt is already complete.",
            ),
            "The verification attempt is already complete.",
        ),
    ],
)
def test_maps_session_and_attempt_conflicts(
    jwks_document,
    make_access_token,
    error: Exception,
    expected_detail: str,
) -> None:
    with build_client(
        jwks_document,
        StubGeofenceService(error=error),
    ) as client:
        response = client.post(
            ATTEMPT_URL,
            json=valid_payload(),
            headers=authorize(make_access_token()),
        )

    assert response.status_code == 409
    assert response.json()["detail"] == expected_detail
