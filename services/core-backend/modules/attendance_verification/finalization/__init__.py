"""Decides and writes final attendance when a lecturer closes a session.

Everything up to this point — check-in, geofence, face, QR scans — only ever
produced evidence. This module is where that evidence becomes a decision:
present, late or absent, written once per roster student to
``attendance_records``.

Inactive until INT-1 binds the real ``QrEvidenceProvider``. Until then, closing
a session behaves exactly as it does on ``main`` today (plus the status change
and QR shutdown), and never writes an attendance record.
"""

from modules.attendance_verification.finalization.service import (
    AttendanceFinalizationService,
)
from modules.attendance_verification.finalization.types import (
    FinalizationResult,
    FinalizationSummary,
    decide_final_attendance,
)

__all__ = [
    "AttendanceFinalizationService",
    "FinalizationResult",
    "FinalizationSummary",
    "decide_final_attendance",
]
