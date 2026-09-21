"""The composition root for dependencies owned by other members' modules.

Service factories (the ``get_*_service`` functions in each route module) ask
these functions for their collaborators instead of importing another member's
implementation directly. That keeps every workstream independent: the
attendance lifecycle can be written, tested and merged while the QR,
notification and policy implementations are still being built.

Each function starts out returning a safe default, and exactly one small
integration pull request later swaps in the real implementation:

* ``get_qr_evidence_provider`` -> Manushan's ``QrEvidenceRepository`` (bound
  by **INT-1**). The lecturer roster reports real QR progress and closing a
  session finalizes attendance. It can still return ``None``, and callers must
  then degrade safely: no QR counts, and no finalization.
* ``get_notification_producer`` -> ``NoOpNotificationProducer`` until **INT-3**
  binds Ashen's producer. Trigger call sites run and are tested; nothing is
  created yet.
* ``get_attendance_policy_provider`` -> Manushan's
  ``AttendancePolicyRepository`` (bound by **INT-4**). Session creation and
  QR batches read the current active policy on their database connection.

Tests never rely on these defaults for behaviour they care about: they inject
the fakes from ``tests/fakes`` instead.
"""

from modules.attendance_sessions.qr_session.evidence import QrEvidenceRepository
from modules.academic.attendance_policy.repository import AttendancePolicyRepository
from modules.contracts.attendance_policy import (
    AttendancePolicyProvider,
)
from modules.contracts.notifications import (
    NoOpNotificationProducer,
    NotificationProducer,
)
from modules.contracts.qr_evidence import QrEvidenceProvider
from modules.notification.producer.service import NotificationProducer as RealNotificationProducer

# All three are stateless, so one shared instance is enough.
_QR_EVIDENCE_REPOSITORY = QrEvidenceRepository()
_ATTENDANCE_POLICY_REPOSITORY = AttendancePolicyRepository()
_NOTIFICATION_PRODUCER = RealNotificationProducer()


def get_qr_evidence_provider() -> QrEvidenceProvider | None:
    """Returns the bound QR evidence provider.

    Callers must still treat ``None`` as "QR evidence is unavailable" and
    degrade safely, since the return type allows it.
    """
    return _QR_EVIDENCE_REPOSITORY


def get_notification_producer() -> NotificationProducer:
    """Returns the bound notification producer (bound by INT-3)."""
    return _NOTIFICATION_PRODUCER


def get_attendance_policy_provider() -> AttendancePolicyProvider:
    """Returns the active-policy repository for session and QR defaults."""
    return _ATTENDANCE_POLICY_REPOSITORY


__all__ = [
    "get_attendance_policy_provider",
    "get_notification_producer",
    "get_qr_evidence_provider",
]
