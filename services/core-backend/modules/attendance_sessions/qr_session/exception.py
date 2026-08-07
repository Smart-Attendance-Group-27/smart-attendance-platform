class QrSessionError(Exception):
    """Base class for QR-session domain errors."""


class AttendanceSessionNotFoundError(QrSessionError):
    """Raised when the target attendance session does not exist."""


class AttendanceSessionNotActiveError(QrSessionError):
    """Raised when a QR session cannot be created for the current session state."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message
