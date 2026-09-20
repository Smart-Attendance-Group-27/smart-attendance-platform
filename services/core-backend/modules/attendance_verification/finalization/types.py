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


def decide_final_attendance(
    *,
    initial_check_in_status: InitialCheckInStatus | None,
    qr_progress: QrRequirementProgress | None,
) -> FinalAttendanceStatus:
    """The one rule finalization applies to every non-manual student.

    A student who never checked in, or whose verification failed outright, is
    absent — there is no initial check-in to read. A student who checked in
    but never satisfied a QR batch activated after they arrived is also
    absent: QR evidence during the lecture is what confirms they stayed, and
    ``qr_progress`` only reports on students who had something required of
    them (see ``QrEvidenceProvider``), so ``None`` means nothing was required.
    Otherwise the initial check-in's own on-time/late verdict stands.
    """

    if initial_check_in_status is None:
        return FinalAttendanceStatus.ABSENT

    if qr_progress is not None and not qr_progress.is_satisfied:
        return FinalAttendanceStatus.ABSENT

    if initial_check_in_status is InitialCheckInStatus.LATE_CHECKED_IN:
        return FinalAttendanceStatus.LATE

    return FinalAttendanceStatus.PRESENT


__all__ = [
    "FinalizationResult",
    "FinalizationSummary",
    "decide_final_attendance",
]
