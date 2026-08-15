class StudentProfileError(Exception):
    """Base class for student-profile domain errors."""


class StudentProfileNotFoundError(StudentProfileError):
    """Raised when the application user has no usable student profile."""
