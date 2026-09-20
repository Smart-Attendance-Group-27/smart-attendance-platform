class CheckInServiceError(Exception):
    """Base class for initial check-in failures."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ActiveStudentProfileNotFoundError(CheckInServiceError):
    """Raised when an application user has no active student profile."""


class AttendanceSessionNotFoundError(CheckInServiceError):
    """Raised when the requested attendance session does not exist."""


class VerificationNotStartedError(CheckInServiceError):
    """Raised when no verification attempt exists yet — the student must
    complete the geofence step first, since that's what creates the attempt row
    every other step (face, QR, check-in) attaches to."""


__all__ = [
    "ActiveStudentProfileNotFoundError",
    "AttendanceSessionNotFoundError",
    "CheckInServiceError",
    "VerificationNotStartedError",
]
