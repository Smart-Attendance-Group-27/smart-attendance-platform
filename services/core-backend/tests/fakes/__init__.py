"""Shared test doubles for contracts owned by other team members.

Importing a fake from here is how a test says "this behaviour belongs to
another module; here is what it returns". The real implementations are bound in
production by the integration pull requests described in
``modules/contracts/providers.py``.
"""

from fakes.attendance_policy import FakeAttendancePolicyProvider
from fakes.notifications import RecordedNotification, RecordingNotificationProducer
from fakes.qr_evidence import FakeQrEvidenceProvider

__all__ = [
    "FakeAttendancePolicyProvider",
    "FakeQrEvidenceProvider",
    "RecordedNotification",
    "RecordingNotificationProducer",
]
