from modules.attendance_verification.geofence.types import GeofenceReason


class GeofenceServiceError(Exception):
    """Base class for geofence service failures."""

    reason: GeofenceReason | None = None

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ActiveStudentProfileNotFoundError(GeofenceServiceError):
    """Raised when an application user has no active student profile."""


class AttendanceSessionNotFoundError(GeofenceServiceError):
    """Raised when the requested attendance session does not exist."""


class AttendanceSessionNotActiveError(GeofenceServiceError):
    """Raised when the requested attendance session is not active."""

    reason = GeofenceReason.SESSION_NOT_ACTIVE


class CheckInNotOpenError(GeofenceServiceError):
    """Raised when the attendance session check-in window has not opened."""

    reason = GeofenceReason.CHECK_IN_NOT_OPEN


class CheckInClosedError(GeofenceServiceError):
    """Raised when the attendance session check-in window has closed."""

    reason = GeofenceReason.CHECK_IN_CLOSED


class GeofenceNotRequiredError(GeofenceServiceError):
    """Raised when geofence validation is disabled for the session."""


class StudentNotEligibleError(GeofenceServiceError):
    """Raised when the student is not in the session eligibility snapshot."""

    reason = GeofenceReason.STUDENT_NOT_ELIGIBLE


class GeofenceNotConfiguredError(GeofenceServiceError):
    """Raised when the session has no complete geofence snapshot."""

    reason = GeofenceReason.GEOFENCE_NOT_CONFIGURED


class GeofenceAttemptLimitReachedError(GeofenceServiceError):
    """Raised when no further geofence attempts may be stored."""

    reason = GeofenceReason.ATTEMPT_LIMIT_REACHED

    def __init__(self, max_attempts: int) -> None:
        super().__init__(
            f"The maximum of {max_attempts} geofence attempts has been reached.",
        )
        self.max_attempts = max_attempts


class VerificationAttemptClosedError(GeofenceServiceError):
    """Raised when the overall verification attempt is already terminal."""
