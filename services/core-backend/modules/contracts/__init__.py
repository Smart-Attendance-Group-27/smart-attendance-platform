"""Contracts between modules owned by different team members.

Each file here declares what one module needs from another as a protocol, plus
a safe default implementation. Consumers depend on the protocol, develop
against a fake, and the real implementation is bound once in
``providers.py`` by a small integration pull request.
"""

from modules.contracts.attendance_policy import (
    AttendancePolicy,
    AttendancePolicyProvider,
    DefaultAttendancePolicyProvider,
)
from modules.contracts.notifications import (
    NoOpNotificationProducer,
    NotificationProducer,
)
from modules.contracts.qr_evidence import QrEvidenceProvider, QrRequirementProgress

__all__ = [
    "AttendancePolicy",
    "AttendancePolicyProvider",
    "DefaultAttendancePolicyProvider",
    "NoOpNotificationProducer",
    "NotificationProducer",
    "QrEvidenceProvider",
    "QrRequirementProgress",
]
