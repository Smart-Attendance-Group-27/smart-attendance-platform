"""The composition root and its defaults.

The defaults are what production runs on until each integration pull request
binds the real implementation, so "safe and boring" is the behaviour under test:
nothing is created, nothing is configured, and no other member's module is
imported.
"""

from uuid import uuid4

from modules.attendance_verification.attendance_state import FinalAttendanceStatus
from modules.contracts import providers
from modules.contracts.attendance_policy import (
    AttendancePolicyProvider,
    DefaultAttendancePolicyProvider,
)
from modules.contracts.notifications import (
    NoOpNotificationProducer,
    NotificationProducer,
)
from modules.contracts.qr_evidence import QrEvidenceProvider, QrRequirementProgress


def test_qr_evidence_provider_is_unbound_until_int_1():
    # None means "QR evidence unavailable": the roster reports unknown progress
    # and session close does not finalize, instead of finalizing wrongly.
    assert providers.get_qr_evidence_provider() is None


def test_notification_producer_defaults_to_the_no_op_producer():
    producer = providers.get_notification_producer()

    assert isinstance(producer, NoOpNotificationProducer)
    assert isinstance(producer, NotificationProducer)


def test_attendance_policy_provider_defaults_to_no_policy():
    provider = providers.get_attendance_policy_provider()

    assert isinstance(provider, DefaultAttendancePolicyProvider)
    assert isinstance(provider, AttendancePolicyProvider)


def test_default_providers_are_reused_rather_than_rebuilt():
    assert providers.get_notification_producer() is providers.get_notification_producer()
    assert (
        providers.get_attendance_policy_provider()
        is providers.get_attendance_policy_provider()
    )


async def test_default_policy_provider_reports_no_policy():
    provider = providers.get_attendance_policy_provider()

    assert await provider.get_active(connection=None) is None


async def test_no_op_producer_accepts_every_trigger_and_creates_nothing():
    producer = providers.get_notification_producer()
    session_id = uuid4()
    user_id = uuid4()

    assert await producer.session_opened(None, session_id=session_id) == []
    assert (
        await producer.qr_batch_activated(
            None,
            session_id=session_id,
            qr_batch_id=uuid4(),
            recipient_user_ids=[user_id],
        )
        == []
    )
    assert (
        await producer.attendance_finalized(
            None,
            session_id=session_id,
            results=[(user_id, FinalAttendanceStatus.PRESENT)],
        )
        == []
    )
    assert (
        await producer.attendance_changed(
            None,
            session_id=session_id,
            student_user_id=user_id,
            status=FinalAttendanceStatus.LATE,
        )
        == []
    )
    assert await producer.session_cancelled(None, session_id=session_id) == []
    assert (
        await producer.notify_users(
            None,
            recipient_user_ids=[user_id],
            type_code="GENERAL",
            title="title",
            body="body",
        )
        == []
    )


def test_qr_requirement_progress_reports_whether_requirements_are_met():
    assert QrRequirementProgress(required_count=0, passed_count=0).is_satisfied
    assert QrRequirementProgress(required_count=2, passed_count=2).is_satisfied
    assert not QrRequirementProgress(required_count=2, passed_count=1).is_satisfied


def test_qr_evidence_protocol_is_structural():
    # Manushan's repository never imports this protocol; it only has to match
    # the method, so the check here is structural rather than inheritance-based.
    class Implementation:
        async def progress_for_session(self, connection, session_id):
            return {}

    assert isinstance(Implementation(), QrEvidenceProvider)
