from datetime import UTC, datetime, timedelta
from math import inf, nan

import pytest

from modules.attendance_verification.geofence.policy import (
    GeofenceValidationPolicy,
    haversine_distance_m,
)
from modules.attendance_verification.geofence.types import (
    GeofenceBoundary,
    GeofenceDecision,
    GeofenceNextStep,
    GeofenceReading,
    GeofenceReason,
)

VALIDATED_AT = datetime(2026, 8, 13, 5, 30, 20, tzinfo=UTC)


def build_boundary(**overrides: float) -> GeofenceBoundary:
    values = {
        "centre_latitude": 0.0,
        "centre_longitude": 0.0,
        "radius_m": 50.0,
        "accuracy_buffer_m": 10.0,
        "maximum_allowed_accuracy_m": 50.0,
    }
    values.update(overrides)
    return GeofenceBoundary(**values)


def build_reading(**overrides: object) -> GeofenceReading:
    values: dict[str, object] = {
        "latitude": 0.0,
        "longitude": 0.0001,
        "accuracy_m": 5.0,
        "captured_at": VALIDATED_AT - timedelta(seconds=5),
        "mocked": False,
    }
    values.update(overrides)
    return GeofenceReading(**values)  # type: ignore[arg-type]


def build_policy() -> GeofenceValidationPolicy:
    return GeofenceValidationPolicy(
        max_reading_age_seconds=30,
        max_future_skew_seconds=5,
    )


def evaluate(
    reading: GeofenceReading | None = None,
    boundary: GeofenceBoundary | None = None,
):
    return build_policy().evaluate(
        reading or build_reading(),
        boundary or build_boundary(),
        validated_at=VALIDATED_AT,
    )


def test_identical_coordinates_produce_zero_distance() -> None:
    assert haversine_distance_m(6.795132, 79.900421, 6.795132, 79.900421) == 0


def test_known_coordinate_pair_produces_expected_distance() -> None:
    distance_m = haversine_distance_m(0, 0, 0, 1)

    assert distance_m == pytest.approx(111_194.93, abs=0.1)


@pytest.mark.parametrize(
    ("coordinates", "field_name"),
    [
        ((91, 0, 0, 0), "latitude_a"),
        ((0, -181, 0, 0), "longitude_a"),
        ((0, 0, -91, 0), "latitude_b"),
        ((0, 0, 0, 181), "longitude_b"),
        ((nan, 0, 0, 0), "latitude_a"),
        ((0, inf, 0, 0), "longitude_a"),
    ],
)
def test_distance_rejects_invalid_coordinates(
    coordinates: tuple[float, float, float, float],
    field_name: str,
) -> None:
    with pytest.raises(ValueError, match=field_name):
        haversine_distance_m(*coordinates)


def test_clearly_inside_with_good_accuracy_passes() -> None:
    result = evaluate()

    assert result.decision is GeofenceDecision.PASSED
    assert result.reason is None
    assert result.next_step is GeofenceNextStep.FACE_VERIFICATION
    assert result.allowed_radius_m == 60
    assert result.distance_m == pytest.approx(11.12, abs=0.1)


def test_clearly_outside_fails() -> None:
    result = evaluate(build_reading(longitude=0.001))

    assert result.decision is GeofenceDecision.FAILED
    assert result.reason is GeofenceReason.OUTSIDE_GEOFENCE
    assert result.next_step is GeofenceNextStep.NONE


def test_uncertainty_overlapping_boundary_requests_retry() -> None:
    result = evaluate(build_reading(longitude=0.00055))

    assert result.decision is GeofenceDecision.RETRY_REQUIRED
    assert result.reason is GeofenceReason.NEAR_GEOFENCE_BOUNDARY
    assert result.next_step is GeofenceNextStep.RETRY_LOCATION


def test_poor_accuracy_requests_retry() -> None:
    result = evaluate(build_reading(accuracy_m=51.0))

    assert result.decision is GeofenceDecision.RETRY_REQUIRED
    assert result.reason is GeofenceReason.LOCATION_ACCURACY_TOO_LOW


def test_unavailable_accuracy_requests_retry() -> None:
    result = evaluate(build_reading(accuracy_m=None))

    assert result.decision is GeofenceDecision.RETRY_REQUIRED
    assert result.reason is GeofenceReason.ACCURACY_UNAVAILABLE


def test_mock_location_fails() -> None:
    result = evaluate(build_reading(mocked=True))

    assert result.decision is GeofenceDecision.FAILED
    assert result.reason is GeofenceReason.MOCK_LOCATION_DETECTED
    assert result.next_step is GeofenceNextStep.NONE


def test_stale_timestamp_requests_retry() -> None:
    result = evaluate(
        build_reading(captured_at=VALIDATED_AT - timedelta(seconds=31)),
    )

    assert result.decision is GeofenceDecision.RETRY_REQUIRED
    assert result.reason is GeofenceReason.STALE_LOCATION


def test_future_timestamp_requests_retry() -> None:
    result = evaluate(
        build_reading(captured_at=VALIDATED_AT + timedelta(seconds=6)),
    )

    assert result.decision is GeofenceDecision.RETRY_REQUIRED
    assert result.reason is GeofenceReason.CAPTURE_TIME_IN_FUTURE


@pytest.mark.parametrize("accuracy_m", [-1.0, inf, nan])
def test_invalid_accuracy_is_rejected(accuracy_m: float) -> None:
    with pytest.raises(ValueError, match="accuracy_m"):
        evaluate(build_reading(accuracy_m=accuracy_m))


@pytest.mark.parametrize(
    ("boundary_overrides", "field_name"),
    [
        ({"centre_latitude": 91.0}, "centre_latitude"),
        ({"centre_longitude": 181.0}, "centre_longitude"),
        ({"radius_m": 0.0}, "radius_m"),
        ({"accuracy_buffer_m": -1.0}, "accuracy_buffer_m"),
        ({"maximum_allowed_accuracy_m": -1.0}, "maximum_allowed_accuracy_m"),
    ],
)
def test_invalid_boundary_is_rejected(
    boundary_overrides: dict[str, float],
    field_name: str,
) -> None:
    with pytest.raises(ValueError, match=field_name):
        evaluate(boundary=build_boundary(**boundary_overrides))


def test_naive_capture_timestamp_is_rejected() -> None:
    with pytest.raises(ValueError, match="captured_at"):
        evaluate(build_reading(captured_at=datetime(2026, 8, 13, 5, 30, 15)))


@pytest.mark.parametrize(
    "policy",
    [
        GeofenceValidationPolicy(
            max_reading_age_seconds=30,
            max_future_skew_seconds=0,
        ),
    ],
)
def test_zero_future_skew_is_allowed(policy: GeofenceValidationPolicy) -> None:
    result = policy.evaluate(
        build_reading(captured_at=VALIDATED_AT),
        build_boundary(),
        validated_at=VALIDATED_AT,
    )

    assert result.decision is GeofenceDecision.PASSED


@pytest.mark.parametrize(
    ("max_reading_age_seconds", "max_future_skew_seconds"),
    [(0, 5), (-1, 5), (30, -1), (inf, 5), (30, nan)],
)
def test_invalid_policy_limits_are_rejected(
    max_reading_age_seconds: float,
    max_future_skew_seconds: float,
) -> None:
    with pytest.raises(ValueError):
        GeofenceValidationPolicy(
            max_reading_age_seconds=max_reading_age_seconds,
            max_future_skew_seconds=max_future_skew_seconds,
        )
