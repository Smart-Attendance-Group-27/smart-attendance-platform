from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from modules.attendance_verification.attendance_state import (
    FinalAttendanceStatus,
    InitialCheckInStatus,
)
from modules.contracts.qr_evidence import QrRequirementProgress


@dataclass(frozen=True)
class FinalizationResult:
    """One student's final decision."""

    student_id: UUID
    status: FinalAttendanceStatus
    # The account that receives notifications about this result.
    student_user_id: UUID | None = None


@dataclass(frozen=True)
class FinalizationSummary:
    """What happened when a session closed.

    ``deactivated_qr_batch_ids`` is filled in by the caller, not by
    ``finalize`` itself — QR batches are deactivated unconditionally on close,
    whether or not a QR evidence provider is bound, so that bookkeeping isn't
    this service's to own.
    """

    enrolled: int
    present: int
    late: int
    absent: int
    kept_manual: int
    reconciled_student_ids: tuple[UUID, ...]
    deactivated_qr_batch_ids: tuple[UUID, ...]
    results: tuple[FinalizationResult, ...]
    finalized_at: datetime
    left_early: int = 0


def decide_final_attendance(
    *,
    initial_check_in_status: InitialCheckInStatus | None,
    qr_progress: QrRequirementProgress | None,
) -> FinalAttendanceStatus:
    """The one rule finalization applies to every non-manual student.

    The initial check-in is the base requirement. It only exists once every
    step the session's effective policy required has passed (geofence may be
    satisfied by a session waiver, see ``EffectiveVerificationPolicy``), so a
    student without one is absent no matter what QR evidence they have.

    QR counts only cover required, non-void batches (see
    ``QrEvidenceProvider``). With a check-in in place:

    * no required batches, or all of them passed -> the check-in's own
      on-time/late verdict (present or late)
    * at least one passed but not all -> left early
    * none passed -> absent
    """

    if initial_check_in_status is None:
        return FinalAttendanceStatus.ABSENT

    if qr_progress is not None and qr_progress.required_count > 0:
        if qr_progress.passed_count <= 0:
            return FinalAttendanceStatus.ABSENT
        if qr_progress.passed_count < qr_progress.required_count:
            return FinalAttendanceStatus.LEFT_EARLY

    if initial_check_in_status is InitialCheckInStatus.LATE_CHECKED_IN:
        return FinalAttendanceStatus.LATE

    return FinalAttendanceStatus.PRESENT


__all__ = [
    "FinalizationResult",
    "FinalizationSummary",
    "decide_final_attendance",
]
