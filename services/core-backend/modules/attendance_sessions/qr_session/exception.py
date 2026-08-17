class QrSessionError(Exception):
    """Base class for QR-session domain errors."""


class AttendanceSessionNotFoundError(QrSessionError):
    """Raised when the target attendance session does not exist."""


class AttendanceSessionNotActiveError(QrSessionError):
    """Raised when a QR session cannot be created for the current session state."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class QrSessionNotFoundError(QrSessionError):
    """Raised when the target QR session does not exist."""


class DynamicQrSessionUnavailableError(QrSessionError):
    """Raised when current dynamic QR generation is not allowed."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class DynamicQrConfigurationError(QrSessionError):
    """Raised when dynamic QR generation is invoked without required config."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class LecturerSessionAccessError(QrSessionError):
    """Raised when the attendance session does not belong to this lecturer."""


class QrNotRequiredError(QrSessionError):
    """Raised when QR is not enabled for the attendance session."""


class ActiveStudentProfileNotFoundError(QrSessionError):
    """Raised when the caller has no active student profile."""


class StudentNotEligibleError(QrSessionError):
    """Raised when the student is not in the session eligibility snapshot."""


class VerificationNotStartedError(QrSessionError):
    """Raised when QR is submitted before any verification attempt exists.

    QR is an additional check on top of geofence/face verification, not a
    replacement for it — a student must already have an in-progress
    verification attempt for this session.
    """
