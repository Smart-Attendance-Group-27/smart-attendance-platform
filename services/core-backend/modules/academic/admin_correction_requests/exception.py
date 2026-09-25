class AdminCorrectionRequestError(Exception):
    """Base class for correction-request review errors."""


class CorrectionRequestNotFoundError(AdminCorrectionRequestError):
    """The correction request does not exist."""


class InvalidDecisionError(AdminCorrectionRequestError):
    """The decision is not allowed for the request's current status."""


class InvalidReviewNoteError(AdminCorrectionRequestError):
    """The review note is missing or out of range."""
