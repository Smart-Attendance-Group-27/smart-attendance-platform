"""The initial check-in: the start-of-lecture verification, and nothing more.

A check-in means every verification step the session requires *at the start of
the lecture* has genuinely passed, proven server-side against the same attempt
tables geofence and face already write to. It records when that happened and
whether it happened late.

What this module deliberately does **not** do is decide attendance. It never
writes ``attendance_verification.attendance_records``. Final attendance is
decided once, for every roster student, when the lecturer closes the session,
because evidence that arrives after check-in (a QR batch activated mid-lecture)
can still change the outcome. Treating a check-in as the final answer is the
bug this module replaces.
"""

from modules.attendance_verification.check_in.domain import (
    CheckInOutcome,
    CheckInResult,
    InitialCheckIn,
    ReconciledCheckIn,
    RequiredStep,
    StepEvidence,
    evaluate_initial_evidence,
    resolve_initial_check_in_status,
)
from modules.attendance_verification.check_in.repository import CheckInRepository
from modules.attendance_verification.check_in.service import CheckInService

__all__ = [
    "CheckInOutcome",
    "CheckInRepository",
    "CheckInResult",
    "CheckInService",
    "InitialCheckIn",
    "ReconciledCheckIn",
    "RequiredStep",
    "StepEvidence",
    "evaluate_initial_evidence",
    "resolve_initial_check_in_status",
]
