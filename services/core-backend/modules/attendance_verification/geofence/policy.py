# Pure location rules: no database or HTTP calls. The service records this result
# and applies the configured attempt limit after this policy evaluates a reading.
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from math import asin, cos, isfinite, radians, sin, sqrt

from modules.attendance_verification.geofence.types import (
    GeofenceBoundary,
    GeofenceDecision,
    GeofenceNextStep,
    GeofenceReading,
    GeofenceReason,
    GeofenceValidationResult,
)

EARTH_RADIUS_M = 6_371_000.0


def haversine_distance_m(
    latitude_a: float,
    longitude_a: float,
    latitude_b: float,
    longitude_b: float,
) -> float:
    """Return the great-circle distance between two WGS 84 points in metres."""
    _validate_coordinate("latitude_a", latitude_a, -90, 90)
    _validate_coordinate("longitude_a", longitude_a, -180, 180)
    _validate_coordinate("latitude_b", latitude_b, -90, 90)
    _validate_coordinate("longitude_b", longitude_b, -180, 180)

    # Haversine calculates surface distance from latitude/longitude in radians;
    # multiplying the central angle by Earth's radius gives the distance in metres.
    latitude_a_rad = radians(latitude_a)
    latitude_b_rad = radians(latitude_b)
    latitude_delta = latitude_b_rad - latitude_a_rad
    longitude_delta = radians(longitude_b - longitude_a)

    haversine = (
        sin(latitude_delta / 2) ** 2
        + cos(latitude_a_rad)
        * cos(latitude_b_rad)
        * sin(longitude_delta / 2) ** 2
    )
    # Floating-point rounding can put an antipodal result just outside [0, 1].
    bounded_haversine = min(1.0, max(0.0, haversine))
    central_angle = 2 * asin(sqrt(bounded_haversine))
    return EARTH_RADIUS_M * central_angle


@dataclass(frozen=True)
class GeofenceValidationPolicy:
    max_reading_age_seconds: float
    max_future_skew_seconds: float

    def __post_init__(self) -> None:
        _validate_positive(
            "max_reading_age_seconds",
            self.max_reading_age_seconds,
        )
        _validate_nonnegative(
            "max_future_skew_seconds",
            self.max_future_skew_seconds,
        )

    def evaluate(
        self,
        reading: GeofenceReading,
        boundary: GeofenceBoundary,
        *,
        validated_at: datetime,
    ) -> GeofenceValidationResult:
        _validate_boundary(boundary)
        _validate_accuracy(reading.accuracy_m)

        # captured_at comes from the device; validated_at is the server's clock.
        # Normalize both to UTC before applying freshness and future-skew limits.
        captured_at = _as_utc("captured_at", reading.captured_at)
        current_time = _as_utc("validated_at", validated_at)
        distance_m = haversine_distance_m(
            reading.latitude,
            reading.longitude,
            boundary.centre_latitude,
            boundary.centre_longitude,
        )
        # The buffer is a fixed session allowance. Reported GPS accuracy is
        # considered separately below, rather than simply enlarging the fence.
        allowed_radius_m = boundary.radius_m + boundary.accuracy_buffer_m

        # A device-reported mocked location is a terminal failure, not a retry.
        if reading.mocked:
            return _result(
                GeofenceDecision.FAILED,
                distance_m,
                allowed_radius_m,
                GeofenceNextStep.NONE,
                GeofenceReason.MOCK_LOCATION_DETECTED,
            )

        # An excessively future-dated or stale reading needs a fresh capture.
        if captured_at > current_time + timedelta(
            seconds=self.max_future_skew_seconds,
        ):
            return _retry_result(
                distance_m,
                allowed_radius_m,
                GeofenceReason.CAPTURE_TIME_IN_FUTURE,
            )

        if current_time - captured_at > timedelta(
            seconds=self.max_reading_age_seconds,
        ):
            return _retry_result(
                distance_m,
                allowed_radius_m,
                GeofenceReason.STALE_LOCATION,
            )

        # Require usable accuracy before deciding whether the position is inside.
        # Unknown accuracy or error above the session limit asks for another fix.
        if reading.accuracy_m is None:
            return _retry_result(
                distance_m,
                allowed_radius_m,
                GeofenceReason.ACCURACY_UNAVAILABLE,
            )

        if reading.accuracy_m > boundary.maximum_allowed_accuracy_m:
            return _retry_result(
                distance_m,
                allowed_radius_m,
                GeofenceReason.LOCATION_ACCURACY_TOO_LOW,
            )

        # Let d = centre distance, a = reported error, R = allowed radius.
        # d + a <= R: the reading's whole uncertainty circle fits inside the fence.
        if distance_m + reading.accuracy_m <= allowed_radius_m:
            return _result(
                GeofenceDecision.PASSED,
                distance_m,
                allowed_radius_m,
                GeofenceNextStep.FACE_VERIFICATION,
                None,
            )

        # d - a > R: even the nearest edge of that circle is outside -> fail.
        if distance_m - reading.accuracy_m > allowed_radius_m:
            return _result(
                GeofenceDecision.FAILED,
                distance_m,
                allowed_radius_m,
                GeofenceNextStep.NONE,
                GeofenceReason.OUTSIDE_GEOFENCE,
            )

        # Otherwise the circle overlaps the boundary, so request a better reading.
        return _retry_result(
            distance_m,
            allowed_radius_m,
            GeofenceReason.NEAR_GEOFENCE_BOUNDARY,
        )


def _validate_boundary(boundary: GeofenceBoundary) -> None:
    _validate_coordinate(
        "centre_latitude",
        boundary.centre_latitude,
        -90,
        90,
    )
    _validate_coordinate(
        "centre_longitude",
        boundary.centre_longitude,
        -180,
        180,
    )
    _validate_positive("radius_m", boundary.radius_m)
    _validate_nonnegative("accuracy_buffer_m", boundary.accuracy_buffer_m)
    _validate_nonnegative(
        "maximum_allowed_accuracy_m",
        boundary.maximum_allowed_accuracy_m,
    )


def _validate_accuracy(accuracy_m: float | None) -> None:
    if accuracy_m is not None:
        _validate_nonnegative("accuracy_m", accuracy_m)


def _validate_coordinate(
    field_name: str,
    value: float,
    minimum: float,
    maximum: float,
) -> None:
    _validate_finite(field_name, value)
    if value < minimum or value > maximum:
        raise ValueError(f"{field_name} must be between {minimum} and {maximum}")


def _validate_positive(field_name: str, value: float) -> None:
    _validate_finite(field_name, value)
    if value <= 0:
        raise ValueError(f"{field_name} must be greater than zero")


def _validate_nonnegative(field_name: str, value: float) -> None:
    _validate_finite(field_name, value)
    if value < 0:
        raise ValueError(f"{field_name} must not be negative")


def _validate_finite(field_name: str, value: float) -> None:
    # Reject bool, NaN and infinity even when the policy is called outside the API.
    if isinstance(value, bool) or not isfinite(value):
        raise ValueError(f"{field_name} must be a finite number")


def _as_utc(field_name: str, value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must include a timezone")
    return value.astimezone(UTC)


def _retry_result(
    distance_m: float,
    allowed_radius_m: float,
    reason: GeofenceReason,
) -> GeofenceValidationResult:
    return _result(
        GeofenceDecision.RETRY_REQUIRED,
        distance_m,
        allowed_radius_m,
        GeofenceNextStep.RETRY_LOCATION,
        reason,
    )


def _result(
    decision: GeofenceDecision,
    distance_m: float,
    allowed_radius_m: float,
    next_step: GeofenceNextStep,
    reason: GeofenceReason | None,
) -> GeofenceValidationResult:
    return GeofenceValidationResult(
        decision=decision,
        distance_m=distance_m,
        allowed_radius_m=allowed_radius_m,
        next_step=next_step,
        reason=reason,
    )
