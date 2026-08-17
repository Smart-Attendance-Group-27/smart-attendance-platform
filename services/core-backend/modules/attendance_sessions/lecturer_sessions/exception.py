class LecturerSessionError(Exception):
    """Base class for lecturer session-lifecycle domain errors."""


class SessionNotFoundError(LecturerSessionError):
    """The session does not exist, or does not belong to this lecturer."""


class SessionAlreadyActiveError(LecturerSessionError):
    """The session has already been activated."""


class SessionNotActiveError(LecturerSessionError):
    """The session must be active before this action is allowed."""


class SessionAlreadyClosedError(LecturerSessionError):
    """The session is already closed."""


class SessionCancelledError(LecturerSessionError):
    """The session was cancelled and cannot be acted on."""
