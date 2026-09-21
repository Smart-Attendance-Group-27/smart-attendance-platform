"""The composition root and its bound providers.

The QR evidence and attendance-policy providers are bound to their real
repositories. Notifications keep their no-op default until INT-3.
"""

import inspect
from uuid import uuid4

from modules.attendance_sessions.qr_session.evidence import QrEvidenceRepository
from modules.academic.attendance_policy.repository import AttendancePolicyRepository
from modules.attendance_verification.attendance_state import FinalAttendanceStatus
from modules.contracts import providers
from modules.contracts.attendance_policy import (
    AttendancePolicy,
    AttendancePolicyProvider,
)
from modules.contracts.notifications import (
    NoOpNotificationProducer,
    NotificationProducer,
)
from modules.contracts.qr_evidence import QrEvidenceProvider, QrRequirementProgress
from modules.notification.producer.service import NotificationProducer as RealNotificationProducer


def test_qr_evidence_provider_is_the_real_repository():
    provider = providers.get_qr_evidence_provider()

    assert isinstance(provider, QrEvidenceRepository)
    assert isinstance(provider, QrEvidenceProvider)


def test_the_bound_repository_takes_the_arguments_the_protocol_promises():
    # isinstance only checks the method exists; this checks its shape.
    parameters = list(inspect.signature(QrEvidenceRepository.progress_for_session).parameters)

    assert parameters == ["self", "connection", "session_id"]


def test_the_same_repository_is_shared_between_calls():
    assert providers.get_qr_evidence_provider() is providers.get_qr_evidence_provider()


def test_notification_producer_is_the_real_producer():
    producer = providers.get_notification_producer()

    assert isinstance(producer, RealNotificationProducer)
    assert isinstance(producer, NotificationProducer)


def test_attendance_policy_provider_is_the_real_repository():
    provider = providers.get_attendance_policy_provider()

    assert isinstance(provider, AttendancePolicyRepository)
    assert isinstance(provider, AttendancePolicyProvider)


def test_default_providers_are_reused_rather_than_rebuilt():
    assert providers.get_notification_producer() is providers.get_notification_producer()
    assert (
        providers.get_attendance_policy_provider()
        is providers.get_attendance_policy_provider()
    )


async def test_bound_policy_provider_reads_active_policy_from_caller_connection():
    provider = providers.get_attendance_policy_provider()
    class FakeConnection:
        def __init__(self):
            self.query = None

        async def fetchrow(self, query):
            self.query = query
            return {
                "check_in_window_minutes": 20,
                "late_threshold_minutes": 8,
                "qr_default_validity_minutes": 12,
            }

    connection = FakeConnection()

    assert await provider.get_active(connection) == AttendancePolicy(20, 8, 12)
    assert "academic.attendance_policies" in connection.query
    assert "WHERE is_active" in connection.query


async def test_no_op_producer_accepts_every_trigger_and_creates_nothing():
    producer = NoOpNotificationProducer()
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
