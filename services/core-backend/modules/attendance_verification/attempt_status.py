"""Status vocabulary for attendance_verification.verification_attempts.

One attempt row per (session, student) carries the student through the
lecture, and three modules read or write its status: geofence starts it,
check-in completion promotes it, and QR verification records evidence
against it. Keeping the values here stops the three from drifting apart.

Lifecycle:

    in_progress  -> geofence created the attempt; check-in not finished
    checked_in   -> geofence AND face passed; provisionally present
    completed    -> session finalized; a final attendance record exists
    failed       -> terminally failed (e.g. outside the geofence)

`failed` and `completed` are terminal. `in_progress` and `checked_in` are
open: the student is still moving through the lecture, so verification
evidence may still be recorded against the attempt.
"""

IN_PROGRESS_STATUS = "in_progress"
CHECKED_IN_STATUS = "checked_in"
COMPLETED_STATUS = "completed"
FAILED_STATUS = "failed"

#: Statuses that still accept new verification evidence.
OPEN_ATTEMPT_STATUSES = frozenset({IN_PROGRESS_STATUS, CHECKED_IN_STATUS})

#: Statuses that no longer accept new verification evidence.
TERMINAL_ATTEMPT_STATUSES = frozenset({COMPLETED_STATUS, FAILED_STATUS})


def is_open_attempt_status(status: str | None) -> bool:
    """True when an attempt can still record verification evidence.

    A NULL status is treated as closed: manual review's retry path clears
    the column, and such a row needs an explicit decision before it accepts
    more evidence.
    """
    return status in OPEN_ATTEMPT_STATUSES


__all__ = [
    "CHECKED_IN_STATUS",
    "COMPLETED_STATUS",
    "FAILED_STATUS",
    "IN_PROGRESS_STATUS",
    "OPEN_ATTEMPT_STATUSES",
    "TERMINAL_ATTEMPT_STATUSES",
    "is_open_attempt_status",
]
