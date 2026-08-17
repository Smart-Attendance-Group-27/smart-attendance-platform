from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from modules.academic.lecturer_profile.exception import LecturerProfileNotFoundError
from modules.academic.lecturer_profile.repository import LecturerProfileRecord
from modules.attendance_verification.manual_review.exception import (
    VerificationAttemptNotFailedError,
    VerificationAttemptNotFoundError,
)
from modules.attendance_verification.manual_review.repository import (
    AttendanceRecordRecord,
    ManualReviewQueueItemRecord,
    ManualReviewRecord,
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
        self.upserted_attendance_records: list[dict] = []
        self.deleted_attendance_records: list[tuple[UUID, UUID]] = []
        self.upserted_reviews: list[dict] = []
        self.reset_attempts: list[UUID] = []

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

    async def upsert_attendance_record(self, connection, **kwargs) -> None:
        self.upserted_attendance_records.append(kwargs)

    async def delete_attendance_record(self, connection, session_id: UUID, student_id: UUID) -> None:
        self.deleted_attendance_records.append((session_id, student_id))

    async def upsert_manual_review(self, connection, **kwargs) -> None:
        self.upserted_reviews.append(kwargs)

    async def reset_attempt_for_retry(self, connection, verification_attempt_id: UUID) -> None:
        self.reset_attempts.append(verification_attempt_id)

    async def find_queue_item_for_lecturer(
        self,
        connection,
        verification_attempt_id: UUID,
        lecturer_id: UUID,
    ):
        return self.queue_item


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


def build_attempt(
    *,
    status: str = "failed",
    started_at: datetime = CURRENT_TIME,
    late_after_at: datetime | None = CURRENT_TIME + timedelta(minutes=15),
) -> VerificationAttemptDetailRecord:
    return VerificationAttemptDetailRecord(
        id=ATTEMPT_ID,
        session_id=SESSION_ID,
        student_id=STUDENT_ID,
        status=status,
        started_at=started_at,
        late_after_at=late_after_at,
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


async def test_approve_marks_present_when_before_late_cutoff() -> None:
    repository = FakeManualReviewRepository(attempt=build_attempt(), queue_item=build_queue_item())
    service = ManualReviewService(
        repository=repository,
        lecturer_profile_repository=FakeLecturerProfileRepository(build_profile()),
    )

    await service.decide_for_user(
        FakePool(),
        USER_ID,
        ATTEMPT_ID,
        ManualReviewDecision.APPROVE,
        "looked fine on camera",
    )

    assert len(repository.upserted_attendance_records) == 1
    assert repository.upserted_attendance_records[0]["attendance_status"] == "present"
    assert repository.upserted_reviews[0]["review_status"] == "approve"


async def test_approve_marks_late_when_started_after_late_cutoff() -> None:
    attempt = build_attempt(started_at=CURRENT_TIME + timedelta(minutes=20))
    repository = FakeManualReviewRepository(attempt=attempt, queue_item=build_queue_item())
    service = ManualReviewService(
        repository=repository,
        lecturer_profile_repository=FakeLecturerProfileRepository(build_profile()),
    )

    await service.decide_for_user(FakePool(), USER_ID, ATTEMPT_ID, ManualReviewDecision.APPROVE, None)

    assert repository.upserted_attendance_records[0]["attendance_status"] == "late"


async def test_reject_marks_absent() -> None:
    repository = FakeManualReviewRepository(attempt=build_attempt(), queue_item=build_queue_item("reject"))
    service = ManualReviewService(
        repository=repository,
        lecturer_profile_repository=FakeLecturerProfileRepository(build_profile()),
    )

    await service.decide_for_user(FakePool(), USER_ID, ATTEMPT_ID, ManualReviewDecision.REJECT, "no show")

    assert repository.upserted_attendance_records[0]["attendance_status"] == "absent"
    assert repository.upserted_reviews[0]["review_status"] == "reject"


async def test_retry_resets_attempt_and_clears_any_prior_record() -> None:
    repository = FakeManualReviewRepository(attempt=build_attempt(), queue_item=build_queue_item("retry"))
    service = ManualReviewService(
        repository=repository,
        lecturer_profile_repository=FakeLecturerProfileRepository(build_profile()),
    )

    await service.decide_for_user(FakePool(), USER_ID, ATTEMPT_ID, ManualReviewDecision.RETRY, None)

    assert repository.reset_attempts == [ATTEMPT_ID]
    assert repository.deleted_attendance_records == [(SESSION_ID, STUDENT_ID)]
    assert repository.upserted_attendance_records == []


async def test_escalate_leaves_attendance_record_untouched() -> None:
    repository = FakeManualReviewRepository(attempt=build_attempt(), queue_item=build_queue_item("escalate"))
    service = ManualReviewService(
        repository=repository,
        lecturer_profile_repository=FakeLecturerProfileRepository(build_profile()),
    )

    await service.decide_for_user(FakePool(), USER_ID, ATTEMPT_ID, ManualReviewDecision.ESCALATE, None)

    assert repository.upserted_attendance_records == []
    assert repository.deleted_attendance_records == []
    assert repository.upserted_reviews[0]["review_status"] == "escalate"


async def test_rejects_missing_verification_attempt() -> None:
    repository = FakeManualReviewRepository(attempt=None)
    service = ManualReviewService(
        repository=repository,
        lecturer_profile_repository=FakeLecturerProfileRepository(build_profile()),
    )

    with pytest.raises(VerificationAttemptNotFoundError):
        await service.decide_for_user(FakePool(), USER_ID, ATTEMPT_ID, ManualReviewDecision.APPROVE, None)


async def test_rejects_attempt_that_is_not_failed() -> None:
    repository = FakeManualReviewRepository(attempt=build_attempt(status="in_progress"))
    service = ManualReviewService(
        repository=repository,
        lecturer_profile_repository=FakeLecturerProfileRepository(build_profile()),
    )

    with pytest.raises(VerificationAttemptNotFailedError):
        await service.decide_for_user(FakePool(), USER_ID, ATTEMPT_ID, ManualReviewDecision.APPROVE, None)


async def test_rejects_missing_lecturer_profile() -> None:
    repository = FakeManualReviewRepository(attempt=build_attempt())
    service = ManualReviewService(
        repository=repository,
        lecturer_profile_repository=FakeLecturerProfileRepository(None),
    )

    with pytest.raises(LecturerProfileNotFoundError):
        await service.decide_for_user(FakePool(), USER_ID, ATTEMPT_ID, ManualReviewDecision.APPROVE, None)
