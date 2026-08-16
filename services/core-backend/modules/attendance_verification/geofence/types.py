from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class GeofenceDecision(StrEnum):
    PASSED = "PASSED"
    FAILED = "FAILED"
    RETRY_REQUIRED = "RETRY_REQUIRED"


class GeofenceNextStep(StrEnum):
    FACE_VERIFICATION = "FACE_VERIFICATION"
    RETRY_LOCATION = "RETRY_LOCATION"
    NONE = "NONE"


class GeofenceReason(StrEnum):
    MOCK_LOCATION_DETECTED = "MOCK_LOCATION_DETECTED"
    ACCURACY_UNAVAILABLE = "ACCURACY_UNAVAILABLE"
    LOCATION_ACCURACY_TOO_LOW = "LOCATION_ACCURACY_TOO_LOW"
    STALE_LOCATION = "STALE_LOCATION"
    CAPTURE_TIME_IN_FUTURE = "CAPTURE_TIME_IN_FUTURE"
    OUTSIDE_GEOFENCE = "OUTSIDE_GEOFENCE"
    NEAR_GEOFENCE_BOUNDARY = "NEAR_GEOFENCE_BOUNDARY"
    SESSION_NOT_ACTIVE = "SESSION_NOT_ACTIVE"
    CHECK_IN_NOT_OPEN = "CHECK_IN_NOT_OPEN"
    CHECK_IN_CLOSED = "CHECK_IN_CLOSED"
    STUDENT_NOT_ELIGIBLE = "STUDENT_NOT_ELIGIBLE"
    GEOFENCE_NOT_CONFIGURED = "GEOFENCE_NOT_CONFIGURED"
    ATTEMPT_LIMIT_REACHED = "ATTEMPT_LIMIT_REACHED"


@dataclass(frozen=True)
class GeofenceReading:
    latitude: float
    longitude: float
    accuracy_m: float | None
    captured_at: datetime
    mocked: bool = False


@dataclass(frozen=True)
class GeofenceBoundary:
    centre_latitude: float
    centre_longitude: float
    radius_m: float
    accuracy_buffer_m: float
    maximum_allowed_accuracy_m: float


@dataclass(frozen=True)
class GeofenceValidationResult:
    decision: GeofenceDecision
    distance_m: float
    allowed_radius_m: float
    next_step: GeofenceNextStep
    reason: GeofenceReason | None
