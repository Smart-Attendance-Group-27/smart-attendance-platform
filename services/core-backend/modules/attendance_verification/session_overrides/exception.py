class SessionOverrideError(Exception):
    """Base error for session verification overrides."""


class SessionNotFoundError(SessionOverrideError):
    """The session does not exist or is not assigned to this lecturer."""


class SessionNotActiveError(SessionOverrideError):
    """Overrides can only be recorded while the session is active."""


class GeofenceNotRequiredError(SessionOverrideError):
    """The session never required geofence, so there is nothing to waive."""


class InvalidWaiverReasonError(SessionOverrideError):
    """The reason code is unknown, or OTHER was given without a description."""


__all__ = [
    "GeofenceNotRequiredError",
    "InvalidWaiverReasonError",
    "SessionNotActiveError",
    "SessionNotFoundError",
    "SessionOverrideError",
]
