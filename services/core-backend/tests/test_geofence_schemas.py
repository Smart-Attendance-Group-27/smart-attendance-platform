from datetime import UTC, datetime
from math import inf, nan
from uuid import UUID

import pytest
from pydantic import ValidationError

from modules.attendance_verification.geofence.schemas import (
    CreateGeofenceAttemptRequest,
    CreateGeofenceAttemptResponse,
)
from modules.attendance_verification.geofence.types import (
    GeofenceDecision,
    GeofenceNextStep,
)


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


def test_request_accepts_the_camel_case_mobile_contract() -> None:
    payload = CreateGeofenceAttemptRequest.model_validate(valid_payload())

    assert payload.latitude == 6.795132
    assert payload.longitude == 79.900421
    assert payload.accuracy_m == 18.5
    assert payload.captured_at == datetime(2026, 8, 13, 5, 30, 14, tzinfo=UTC)
    assert payload.mocked is False


def test_request_accepts_explicitly_unavailable_accuracy() -> None:
    payload = CreateGeofenceAttemptRequest.model_validate(
        valid_payload(accuracyM=None),
    )

    assert payload.accuracy_m is None


@pytest.mark.parametrize(
    "overrides",
    [
        {"latitude": -90.000001},
        {"latitude": 90.000001},
        {"longitude": -180.000001},
        {"longitude": 180.000001},
        {"latitude": nan},
        {"longitude": inf},
        {"accuracyM": -0.1},
        {"accuracyM": inf},
    ],
)
def test_request_rejects_invalid_coordinates_and_accuracy(overrides) -> None:
    with pytest.raises(ValidationError):
        CreateGeofenceAttemptRequest.model_validate(valid_payload(**overrides))


def test_request_requires_accuracy_field_even_when_it_is_unavailable() -> None:
    payload = valid_payload()
    del payload["accuracyM"]

    with pytest.raises(ValidationError):
        CreateGeofenceAttemptRequest.model_validate(payload)


def test_request_rejects_capture_time_without_timezone() -> None:
    with pytest.raises(ValidationError, match="must include a timezone"):
        CreateGeofenceAttemptRequest.model_validate(
            valid_payload(capturedAt="2026-08-13T05:30:14"),
        )


@pytest.mark.parametrize(
    "extra_field",
    [
        {"studentId": "23000000-0000-0000-0000-000000000002"},
        {"userId": "20000000-0000-0000-0000-000000000012"},
        {"decision": "PASSED"},
        {"centreLatitude": 6.795132},
        {"allowedRadiusM": 5000},
    ],
)
def test_request_forbids_identity_decision_and_geofence_overrides(extra_field) -> None:
    with pytest.raises(ValidationError):
        CreateGeofenceAttemptRequest.model_validate(
            valid_payload(**extra_field),
        )


def test_response_serializes_only_the_privacy_safe_camel_case_contract() -> None:
    response = CreateGeofenceAttemptResponse(
        verification_attempt_id=UUID("50000000-0000-0000-0000-000000000001"),
        attempt_number=1,
        decision=GeofenceDecision.PASSED,
        distance_m=18.7,
        allowed_radius_m=70,
        next_step=GeofenceNextStep.FACE_VERIFICATION,
        reason=None,
    )

    assert response.model_dump(mode="json", by_alias=True) == {
        "verificationAttemptId": "50000000-0000-0000-0000-000000000001",
        "attemptNumber": 1,
        "decision": "PASSED",
        "distanceM": 18.7,
        "allowedRadiusM": 70.0,
        "nextStep": "FACE_VERIFICATION",
        "reason": None,
    }
