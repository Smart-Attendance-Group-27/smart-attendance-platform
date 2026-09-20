"""The shared fakes behave like the contracts they stand in for.

Every attendance test that involves QR progress, notifications or the policy
leans on these, so a fake that drifts from its protocol would quietly make
those tests meaningless.
"""

from uuid import uuid4

from fakes import (
    FakeAttendancePolicyProvider,
    FakeQrEvidenceProvider,
    RecordingNotificationProducer,
)
from modules.attendance_verification.attendance_state import FinalAttendanceStatus
from modules.contracts.attendance_policy import AttendancePolicy, AttendancePolicyProvider
from modules.contracts.notifications import NotificationProducer
from modules.contracts.qr_evidence import QrEvidenceProvider, QrRequirementProgress


def test_fakes_satisfy_their_protocols():
    assert isinstance(FakeQrEvidenceProvider(), QrEvidenceProvider)
    assert isinstance(RecordingNotificationProducer(), NotificationProducer)
    assert isinstance(FakeAttendancePolicyProvider(), AttendancePolicyProvider)


async def test_qr_evidence_fake_returns_configured_progress():
    attempt_id = uuid4()
    session_id = uuid4()
    provider = FakeQrEvidenceProvider()
    provider.set_progress(attempt_id, required_count=2, passed_count=1)

    progress = await provider.progress_for_session(None, session_id)

    assert progress == {attempt_id: QrRequirementProgress(required_count=2, passed_count=1)}
    assert provider.requested_session_ids == [session_id]


async def test_qr_evidence_fake_defaults_to_no_progress():
    provider = FakeQrEvidenceProvider()

    assert await provider.progress_for_session(None, uuid4()) == {}


async def test_qr_evidence_fake_result_is_detached_from_its_state():
    attempt_id = uuid4()
    provider = FakeQrEvidenceProvider(
        {attempt_id: QrRequirementProgress(required_count=1, passed_count=1)},
    )

    returned = await provider.progress_for_session(None, uuid4())
    returned.clear()

    assert await provider.progress_for_session(None, uuid4()) != {}


async def test_notification_fake_records_each_trigger_with_its_payload():
    producer = RecordingNotificationProducer()
    session_id = uuid4()
    student_user_id = uuid4()

    await producer.session_opened(None, session_id=session_id)
    await producer.attendance_changed(
        None,
        session_id=session_id,
        student_user_id=student_user_id,
        status=FinalAttendanceStatus.LATE,
    )

    assert producer.kinds == ["session_opened", "attendance_changed"]
    changed = producer.only_call_of("attendance_changed")
    assert changed.payload["student_user_id"] == student_user_id
    assert changed.payload["status"] is FinalAttendanceStatus.LATE


async def test_notification_fake_returns_one_id_per_recipient():
    producer = RecordingNotificationProducer()
    recipients = [uuid4(), uuid4()]

    created = await producer.qr_batch_activated(
        None,
        session_id=uuid4(),
        qr_batch_id=uuid4(),
        recipient_user_ids=recipients,
    )

    assert len(created) == len(recipients)


async def test_notification_fake_rejects_an_ambiguous_single_call_lookup():
    producer = RecordingNotificationProducer()
    session_id = uuid4()
    await producer.session_opened(None, session_id=session_id)
    await producer.session_opened(None, session_id=session_id)

    try:
        producer.only_call_of("session_opened")
    except AssertionError as error:
        assert "exactly one" in str(error)
    else:  # pragma: no cover - the call above must raise
        raise AssertionError("only_call_of should reject two matching calls")


async def test_policy_fake_returns_its_policy_and_counts_reads():
    policy = AttendancePolicy(
        check_in_window_minutes=15,
        late_threshold_minutes=10,
        qr_default_validity_minutes=5,
    )
    provider = FakeAttendancePolicyProvider(policy)

    assert await provider.get_active(None) is policy
    assert await provider.get_active(None) is policy
    assert provider.read_count == 2


async def test_policy_fake_can_report_no_policy():
    provider = FakeAttendancePolicyProvider()

    assert await provider.get_active(None) is None
