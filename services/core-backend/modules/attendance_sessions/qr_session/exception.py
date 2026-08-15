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
