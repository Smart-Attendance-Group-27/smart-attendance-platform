class CompletionServiceError(Exception):
    """Base class for check-in completion failures."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ActiveStudentProfileNotFoundError(CompletionServiceError):
    """Raised when an application user has no active student profile."""


class AttendanceSessionNotFoundError(CompletionServiceError):
    """Raised when the requested attendance session does not exist."""


class AttendanceSessionNotOpenError(CompletionServiceError):
    """Raised when the session is closed or cancelled.

    Initial check-in reads the session's closed_at/cancelled_at/status the
    same way the geofence and QR steps already do, so a student holding an
    in-progress attempt cannot check in after the lecturer ended the lecture.
    """


class VerificationNotStartedError(CompletionServiceError):
    """Raised when no verification attempt exists yet — the student must
    complete the geofence step first, since that's what creates the
    attempt row every other step (face, QR, completion) attaches to."""
