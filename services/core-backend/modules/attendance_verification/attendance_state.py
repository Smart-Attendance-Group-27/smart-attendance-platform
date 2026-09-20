"""The shared vocabulary of the attendance lifecycle.

Attendance is tracked in three separate layers, and every module that touches
attendance uses the names below rather than writing the literal strings:

1. Verification process - ``verification_attempts.status``
   What happened while the student verified. Closing a session preserves it.
2. Initial check-in - ``verification_attempts.checked_in_at`` and
   ``verification_attempts.initial_check_in_status``
   An intermediate state: the start-of-lecture verification succeeded, and when.
   It is never a final attendance result.
3. Final attendance - ``attendance_records.attendance_status`` with
   ``attendance_records.record_source``
   Written for every roster student when the lecturer closes the session, or at
   any time by a lecturer, in which case the manual record always wins.

There is deliberately no generic "finalized" verification status: a failed
attempt stays failed and an unfinished one stays in progress, so the
verification history keeps telling the truth after the session is closed.

These values are a frozen contract shared across the team. Changing one means
changing the database CHECK constraints and every consumer, so they are treated
as fixed vocabulary rather than an implementation detail.
"""

from enum import StrEnum


class VerificationAttemptStatus(StrEnum):
    """Where a student's verification attempt is in the process.

    ``attendance_verification.verification_attempts.status``.
    """

    IN_PROGRESS = "in_progress"
    CHECKED_IN = "checked_in"
    FAILED = "failed"


class InitialCheckInStatus(StrEnum):
    """The stored outcome of the start-of-lecture verification.

    ``attendance_verification.verification_attempts.initial_check_in_status``.
    NULL until every required initial step has passed. ``LATE_CHECKED_IN`` means
    the check-in completed after the session's ``late_after_at``.
    """

    CHECKED_IN = "checked_in"
    LATE_CHECKED_IN = "late_checked_in"


class FinalAttendanceStatus(StrEnum):
    """The official attendance outcome.

    ``attendance_verification.attendance_records.attendance_status``.
    """

    PRESENT = "present"
    LATE = "late"
    ABSENT = "absent"


class AttendanceRecordSource(StrEnum):
    """Who wrote a final attendance record.

    ``attendance_verification.attendance_records.record_source``. ``AUTOMATIC``
    rows come from finalization at session close and may be recalculated;
    ``MANUAL`` rows come from a lecturer decision and are never overwritten by
    finalization.
    """

    AUTOMATIC = "automatic"
    MANUAL = "manual"


__all__ = [
    "AttendanceRecordSource",
    "FinalAttendanceStatus",
    "InitialCheckInStatus",
    "VerificationAttemptStatus",
]
