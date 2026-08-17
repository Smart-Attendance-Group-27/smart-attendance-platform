class LecturerProfileError(Exception):
    """Base class for lecturer-profile domain errors."""


class LecturerProfileNotFoundError(LecturerProfileError):
    """Raised when the application user has no usable lecturer profile."""
