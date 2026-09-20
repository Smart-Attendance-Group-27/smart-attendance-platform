"""The check-in decision, expressed without a database.

Everything here is pure: given what the session requires and when each required
step passed, it answers "is this student checked in, and was it late?". The
service layer supplies the evidence and persists the answer; keeping the rule
itself free of SQL is what makes the awkward cases (a step that never passed, a
session that requires nothing, evidence that landed after the session closed)
cheap to test.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from modules.attendance_verification.attendance_state import InitialCheckInStatus


class RequiredStep(StrEnum):
    """A verification step that must pass before a student is checked in.

    QR is absent on purpose. A QR batch is activated during the lecture to prove
    the student is *still* there, so it is continuous evidence weighed at
    finalization, never a precondition of the initial check-in. Requiring it
    here would mean nobody could check in until the lecturer happened to
    activate a batch.
    """

    GEOFENCE = "geofence"
    FACE = "face_verification"


@dataclass(frozen=True)
class StepEvidence:
    """When a required step passed, or ``None`` if it has not passed yet."""

    step: RequiredStep
    passed_at: datetime | None


@dataclass(frozen=True)
class InitialCheckIn:
    """A stored initial check-in. Never a final attendance result."""

    checked_in_at: datetime
    status: InitialCheckInStatus

    @property
    def is_late(self) -> bool:
        return self.status is InitialCheckInStatus.LATE_CHECKED_IN


class CheckInOutcome(StrEnum):
    """What a check-in attempt concluded."""

    CHECKED_IN = "checked_in"
    PENDING = "pending"
    FAILED = "failed"


@dataclass(frozen=True)
class CheckInResult:
    outcome: CheckInOutcome
    verification_attempt_id: UUID
    initial_check_in: InitialCheckIn | None = None
    missing_steps: tuple[RequiredStep, ...] = ()
    # True only for the call that actually wrote the check-in, so a caller can
    # tell "just checked in" from "was already checked in" without re-reading.
    was_persisted: bool = False

    @property
    def is_checked_in(self) -> bool:
        return self.outcome is CheckInOutcome.CHECKED_IN

    @property
    def missing_step_names(self) -> list[str]:
        return [step.value for step in self.missing_steps]


@dataclass(frozen=True)
class ReconciledCheckIn:
    """A check-in written during reconciliation, rather than by the student."""

    verification_attempt_id: UUID
    student_id: UUID
    initial_check_in: InitialCheckIn


def evaluate_initial_evidence(
    evidence: tuple[StepEvidence, ...],
    *,
    fallback_checked_in_at: datetime | None,
) -> tuple[datetime | None, tuple[RequiredStep, ...]]:
    """Decide when the student became checked in, or which steps are missing.

    The check-in time is the ``validated_at`` of the **last** required step to
    pass, not the time this function runs. A student who passed geofence at
    09:00 and face at 09:02 checked in at 09:02, and that stays true whether the
    answer is computed at 09:02 or during reconciliation an hour later. Deciding
    lateness from a wall clock instead would punish students for when the server
    got around to asking.

    ``fallback_checked_in_at`` covers a session that requires no initial step at
    all: there is no evidence timestamp to use, so the attempt's own
    ``started_at`` stands in. A session with no requirements and no attempt
    never reaches here.
    """

    missing = tuple(item.step for item in evidence if item.passed_at is None)
    if missing:
        return None, missing

    passed_times = [item.passed_at for item in evidence if item.passed_at is not None]
    if not passed_times:
        return fallback_checked_in_at, ()

    return max(passed_times), ()


def resolve_initial_check_in_status(
    *,
    checked_in_at: datetime,
    late_after_at: datetime | None,
) -> InitialCheckInStatus:
    """Late when the check-in itself landed after the threshold.

    This asks when the student *finished* verifying, not when they started. The
    old completion path compared ``started_at``, which marked a student late for
    opening the app late even though they were in the room on time, and marked
    another on time for starting early and finishing well after the threshold.
    """

    if late_after_at is not None and checked_in_at > late_after_at:
        return InitialCheckInStatus.LATE_CHECKED_IN
    return InitialCheckInStatus.CHECKED_IN


__all__ = [
    "CheckInOutcome",
    "CheckInResult",
    "InitialCheckIn",
    "ReconciledCheckIn",
    "RequiredStep",
    "StepEvidence",
    "evaluate_initial_evidence",
    "resolve_initial_check_in_status",
]
