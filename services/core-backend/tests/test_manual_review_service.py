from contextlib import asynccontextmanager
from dataclasses import fields
from datetime import UTC, datetime
from uuid import UUID

import pytest

from modules.academic.lecturer_profile.exception import LecturerProfileNotFoundError
from modules.academic.lecturer_profile.repository import LecturerProfileRecord
from modules.attendance_verification.attendance_state import FinalAttendanceStatus
from modules.attendance_verification.manual_attendance.exception import SessionCancelledError
from modules.attendance_verification.manual_review.exception import (
    VerificationAttemptNotFailedError,
    VerificationAttemptNotFoundError,
)
from modules.attendance_verification.manual_review.repository import (
    AttendanceRecordRecord,
    ManualReviewQueueItemRecord,
    ManualReviewRecord,
    ManualReviewRepository,
    VerificationAttemptDetailRecord,
)
from modules.attendance_verification.manual_review.schemas import ManualReviewDecision
from modules.attendance_verification.manual_review.service import ManualReviewService

USER_ID = UUID("20000000-0000-0000-0000-000000000002")
LECTURER_ID = UUID("22000000-0000-0000-0000-000000000001")
SESSION_ID = UUID("40000000-0000-0000-0000-000000000001")
STUDENT_ID = UUID("23000000-0000-0000-0000-000000000001")
ATTEMPT_ID = UUID("50000000-0000-0000-0000-000000000001")
CURRENT_TIME = datetime(2026, 8, 13, 5, 30, tzinfo=UTC)


class FakeTransaction:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, exc_type: object, exc: object, traceback: object) -> bool:
        return False


class FakeConnection:
    def transaction(self) -> FakeTransaction:
        return FakeTransaction()

    async def execute(self, query: str, *args) -> None:
        """Absorbs the write_audit_log() call made inside the same transaction."""


class FakeAcquire:
    def __init__(self, connection: FakeConnection) -> None:
        self.connection = connection

    async def __aenter__(self) -> FakeConnection:
        return self.connection

    async def __aexit__(self, exc_type: object, exc: object, traceback: object) -> bool:
        return False


class FakePool:
    def __init__(self) -> None:
        self.connection = FakeConnection()

    def acquire(self) -> FakeAcquire:
        return FakeAcquire(self.connection)


class FakeLecturerProfileRepository:
    def __init__(self, profile: LecturerProfileRecord | None) -> None:
        self.profile = profile

    async def find_by_user_id(self, connection, user_id: UUID) -> LecturerProfileRecord | None:
        return self.profile


class FakeManualReviewRepository:
    def __init__(
        self,
        *,
        attempt: VerificationAttemptDetailRecord | None,
        queue_item: ManualReviewQueueItemRecord | None = None,
        previous_review: ManualReviewRecord | None = None,
        previous_record: AttendanceRecordRecord | None = None,
    ) -> None:
        self.attempt = attempt
        self.queue_item = queue_item
        self.previous_review = previous_review
        self.previous_record = previous_record
        self.upserted_reviews: list[dict] = []

    async def find_attempt_for_lecturer(
        self,
        connection,
        verification_attempt_id: UUID,
        lecturer_id: UUID,
        *,
        lock_for_update: bool = False,
    ) -> VerificationAttemptDetailRecord | None:
        return self.attempt

    async def find_manual_review(self, connection, verification_attempt_id: UUID):
        return self.previous_review

    async def find_attendance_record(self, connection, session_id: UUID, student_id: UUID):
        return self.previous_record

    async def upsert_manual_review(self, connection, **kwargs) -> None:
        self.upserted_reviews.append(kwargs)

    async def find_queue_item_for_lecturer(
        self,
        connection,
        verification_attempt_id: UUID,
        lecturer_id: UUID,
    ):
        return self.queue_item


class FakeManualAttendanceService:
    """Stands in for ManualAttendanceService and records what review writes."""

    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[dict] = []

    async def set_status_in_transaction(self, connection, **kwargs) -> None:
        if self.error is not None:
            raise self.error
        self.calls.append(kwargs)


def build_profile() -> LecturerProfileRecord:
    return LecturerProfileRecord(
        id=LECTURER_ID,
        user_id=USER_ID,
        employee_number="EMP001",
        first_name="Nadeesha",
        middle_name=None,
        last_name="Perera",
        profile_status="active",
        university_email="n.perera@staff.uniattend.test",
    )


def build_attempt(*, status: str = "failed") -> VerificationAttemptDetailRecord:
    return VerificationAttemptDetailRecord(
        id=ATTEMPT_ID,
        session_id=SESSION_ID,
        student_id=STUDENT_ID,
        status=status,
    )


def build_queue_item(review_status: str = "approve") -> ManualReviewQueueItemRecord:
    return ManualReviewQueueItemRecord(
        verification_attempt_id=ATTEMPT_ID,
        session_id=SESSION_ID,
        course_code="CS3203",
        course_name="Software Engineering Project",
        classroom_code="LH-02",
        scheduled_start_at=CURRENT_TIME,
        student_id=STUDENT_ID,
        registration_number="230701A",
        full_name="Amal Perera",
        failure_reason="face_mismatch",
        started_at=CURRENT_TIME,
        completed_at=CURRENT_TIME,
        geofence_status="passed",
        geofence_failure_reason=None,
        face_status="failed",
        face_similarity_score=None,
        face_liveness_passed=False,
        qr_status=None,
        review_status=review_status,
        decision_reason="looked fine on camera",
        reviewed_at=CURRENT_TIME,
    )


def build_service(
    repository: FakeManualReviewRepository,
    manual_attendance: FakeManualAttendanceService | None = None,
) -> ManualReviewService:
    return ManualReviewService(
        repository=repository,
        lecturer_profile_repository=FakeLecturerProfileRepository(build_profile()),
        manual_attendance_service=manual_attendance or FakeManualAttendanceService(),
    )


async def test_approve_writes_the_status_the_lecturer_chose() -> None:
    repository = FakeManualReviewRepository(attempt=build_attempt(), queue_item=build_queue_item())
    manual_attendance = FakeManualAttendanceService()
    service = build_service(repository, manual_attendance)

    await service.decide_for_user(
        FakePool(),
        USER_ID,
        ATTEMPT_ID,
        ManualReviewDecision.APPROVE,
        "late",
        "looked fine on camera",
    )

    assert len(manual_attendance.calls) == 1
    call = manual_attendance.calls[0]
    assert call["status"] is FinalAttendanceStatus.LATE
    assert call["session_id"] == SESSION_ID
    assert call["student_id"] == STUDENT_ID
    assert call["lecturer_user_id"] == USER_ID
    assert call["reason"] == "looked fine on camera"
    assert repository.upserted_reviews[0]["review_status"] == "approve"


async def test_approve_as_present_writes_present() -> None:
    manual_attendance = FakeManualAttendanceService()
    service = build_service(
        FakeManualReviewRepository(attempt=build_attempt(), queue_item=build_queue_item()),
        manual_attendance,
    )

    await service.decide_for_user(
        FakePool(),
        USER_ID,
        ATTEMPT_ID,
        ManualReviewDecision.APPROVE,
        "present",
        "in the room",
    )

    assert manual_attendance.calls[0]["status"] is FinalAttendanceStatus.PRESENT


async def test_approve_needs_an_explicit_status() -> None:
    repository = FakeManualReviewRepository(attempt=build_attempt())
    manual_attendance = FakeManualAttendanceService()
    service = build_service(repository, manual_attendance)

    with pytest.raises(ValueError):
        await service.decide_for_user(
            FakePool(),
            USER_ID,
            ATTEMPT_ID,
            ManualReviewDecision.APPROVE,
            None,
            "in the room",
        )

    assert manual_attendance.calls == []
    assert repository.upserted_reviews == []


async def test_approve_cannot_be_used_to_write_absent() -> None:
    manual_attendance = FakeManualAttendanceService()
    service = build_service(FakeManualReviewRepository(attempt=build_attempt()), manual_attendance)

    with pytest.raises(ValueError):
        await service.decide_for_user(
            FakePool(),
            USER_ID,
            ATTEMPT_ID,
            ManualReviewDecision.APPROVE,
            "absent",
            "in the room",
        )

    assert manual_attendance.calls == []


async def test_reject_writes_absent() -> None:
    repository = FakeManualReviewRepository(
        attempt=build_attempt(),
        queue_item=build_queue_item("reject"),
    )
    manual_attendance = FakeManualAttendanceService()
    service = build_service(repository, manual_attendance)

    await service.decide_for_user(
        FakePool(),
        USER_ID,
        ATTEMPT_ID,
        ManualReviewDecision.REJECT,
        None,
        "no show",
    )

    assert manual_attendance.calls[0]["status"] is FinalAttendanceStatus.ABSENT
    assert manual_attendance.calls[0]["reason"] == "no show"
    assert repository.upserted_reviews[0]["review_status"] == "reject"


async def test_a_refused_attendance_write_leaves_no_review_row() -> None:
    repository = FakeManualReviewRepository(attempt=build_attempt(), queue_item=build_queue_item())
    service = build_service(repository, FakeManualAttendanceService(error=SessionCancelledError()))

    with pytest.raises(SessionCancelledError):
        await service.decide_for_user(
            FakePool(),
            USER_ID,
            ATTEMPT_ID,
            ManualReviewDecision.APPROVE,
            "present",
            "in the room",
        )

    assert repository.upserted_reviews == []


def test_lateness_is_never_inferred_from_when_the_attempt_started() -> None:
    field_names = {field.name for field in fields(VerificationAttemptDetailRecord)}

    assert "started_at" not in field_names
    assert "late_after_at" not in field_names


def test_retry_and_escalate_no_longer_exist() -> None:
    assert {decision.value for decision in ManualReviewDecision} == {"approve", "reject"}
    assert not hasattr(ManualReviewRepository, "reset_attempt_for_retry")
    assert not hasattr(ManualReviewRepository, "delete_attendance_record")
    assert not hasattr(ManualReviewRepository, "upsert_attendance_record")


async def test_rejects_missing_verification_attempt() -> None:
    service = build_service(FakeManualReviewRepository(attempt=None))

    with pytest.raises(VerificationAttemptNotFoundError):
        await service.decide_for_user(
            FakePool(),
            USER_ID,
            ATTEMPT_ID,
            ManualReviewDecision.APPROVE,
            "present",
            "in the room",
        )


async def test_rejects_attempt_that_is_not_failed() -> None:
    service = build_service(FakeManualReviewRepository(attempt=build_attempt(status="in_progress")))

    with pytest.raises(VerificationAttemptNotFailedError):
        await service.decide_for_user(
            FakePool(),
            USER_ID,
            ATTEMPT_ID,
            ManualReviewDecision.APPROVE,
            "present",
            "in the room",
        )


async def test_rejects_missing_lecturer_profile() -> None:
    service = ManualReviewService(
        repository=FakeManualReviewRepository(attempt=build_attempt()),
        lecturer_profile_repository=FakeLecturerProfileRepository(None),
        manual_attendance_service=FakeManualAttendanceService(),
    )

    with pytest.raises(LecturerProfileNotFoundError):
        await service.decide_for_user(
            FakePool(),
            USER_ID,
            ATTEMPT_ID,
            ManualReviewDecision.APPROVE,
            "present",
            "in the room",
        )
