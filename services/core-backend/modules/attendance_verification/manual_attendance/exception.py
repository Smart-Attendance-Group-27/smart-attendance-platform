class ManualAttendanceError(Exception):
    """Base class for manual attendance failures."""


class SessionNotFoundError(ManualAttendanceError):
    """The session does not exist, or the lecturer does not teach it."""


class StudentNotOnRosterError(ManualAttendanceError):
    """The student is not on this session's roster."""


class SessionNotStartedError(ManualAttendanceError):
    """The session has not been activated yet."""


class SessionCancelledError(ManualAttendanceError):
    """The session was cancelled."""


class ManualReasonInvalidError(ManualAttendanceError):
    """A manual record needs a reason of 3 to 500 characters."""
