class CorrectionRequestError(Exception):
    """Base class for correction-request domain errors."""


class CorrectionTargetNotFoundError(CorrectionRequestError):
    """Raised when the course or timetable entry is not assigned to the lecturer."""


class CorrectionRequestInvalidError(CorrectionRequestError):
    """Raised when the request fields are inconsistent or out of range."""
