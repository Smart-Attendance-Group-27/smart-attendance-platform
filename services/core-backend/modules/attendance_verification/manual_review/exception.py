class ManualReviewError(Exception):
    """Base class for manual-review domain errors."""


class LecturerSessionAccessError(ManualReviewError):
    """The verification attempt does not belong to a session this lecturer teaches."""


class VerificationAttemptNotFoundError(ManualReviewError):
    """The verification attempt does not exist."""


class VerificationAttemptNotFailedError(ManualReviewError):
    """Only failed verification attempts can be manually reviewed."""
