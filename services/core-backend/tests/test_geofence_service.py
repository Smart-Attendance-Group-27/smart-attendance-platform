from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

import pytest

from modules.attendance_verification.geofence.exception import (
    ActiveStudentProfileNotFoundError,
    AttendanceSessionNotActiveError,
    AttendanceSessionNotFoundError,
    CheckInClosedError,
    CheckInNotOpenError,
    GeofenceAttemptLimitReachedError,
    GeofenceNotConfiguredError,
    GeofenceNotRequiredError,
    StudentNotEligibleError,
    VerificationAttemptClosedError,
)
from modules.attendance_verification.geofence.policy import GeofenceValidationPolicy
from modules.attendance_verification.geofence.repository import (
    IN_PROGRESS_STATUS,
    AttendanceSessionRecord,
    SessionGeofenceRecord,
    StudentProfileRecord,
    VerificationAttemptRecord,
)
from modules.attendance_verification.geofence.service import (
    GeofenceValidationService,
)
from modules.attendance_verification.geofence.types import (
    GeofenceDecision,
    GeofenceNextStep,
    GeofenceReading,
    GeofenceReason,
)

USER_ID = UUID("20000000-0000-0000-0000-000000000011")
STUDENT_ID = UUID("23000000-0000-0000-0000-000000000001")
SESSION_ID = UUID("40000000-0000-0000-0000-000000000001")
VERIFICATION_ATTEMPT_ID = UUID("50000000-0000-0000-0000-000000000001")
CURRENT_TIME = datetime(2026, 8, 13, 5, 30, tzinfo=UTC)


class FakeTransaction:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, exc_type: object, exc: object, traceback: object) -> bool:
        return False


class FakeConnection:
    def transaction(self) -> FakeTransaction:
        return FakeTransaction()


class FakeAcquire:
    def __init__(self, connection: FakeConnection) -> None:
        self._connection = connection

    async def __aenter__(self) -> FakeConnection:
        return self._connection

    async def __aexit__(self, exc_type: object, exc: object, traceback: object) -> bool:
        return False


class FakePool:
    def __init__(self) -> None:
        self.connection = FakeConnection()

    def acquire(self) -> FakeAcquire:
        return FakeAcquire(self.connection)


class FakeRepository:
    def __init__(
        self,
        *,
        student: StudentProfileRecord | None = None,
        session: AttendanceSessionRecord | None = None,
        eligible: bool = True,
        geofence: SessionGeofenceRecord | None = None,
        verification_status: str | None = IN_PROGRESS_STATUS,
        verification_failure_reason: str | None = None,
        existing_attempt_count: int = 0,
    ) -> None:
        self.student = student if student is not None else build_student()
        self.session = session if session is not None else build_session()
        self.eligible = eligible
        self.geofence = geofence if geofence is not None else build_geofence()
        self.verification_status = verification_status
        self.verification_failure_reason = verification_failure_reason
        self.existing_attempt_count = existing_attempt_count
        self.verification_attempt_id = VERIFICATION_ATTEMPT_ID
        self.calls: list[str] = []
        self.inserted_attempts: list[dict[str, Any]] = []
        self.marked_failed: tuple[UUID, str, datetime] | None = None
        self.attendance_records_created = 0

    async def lock_student_profile_for_user(
        self,
        connection: FakeConnection,
        user_id: UUID,
    ) -> StudentProfileRecord | None:
        self.calls.append("student")
        return self.student

    async def lock_attendance_session(
        self,
        connection: FakeConnection,
        session_id: UUID,
    ) -> AttendanceSessionRecord | None:
        self.calls.append("session")
        return self.session

    async def lock_student_eligibility(
        self,
        connection: FakeConnection,
        session_id: UUID,
        student_id: UUID,
    ) -> bool:
        self.calls.append("eligibility")
        return self.eligible

    async def lock_session_geofence(
        self,
        connection: FakeConnection,
        session_id: UUID,
    ) -> SessionGeofenceRecord | None:
        self.calls.append("geofence")
        return self.geofence

    async def lock_or_create_verification_attempt(
        self,
        connection: FakeConnection,
        verification_attempt_id: UUID,
        session_id: UUID,
        student_id: UUID,
        started_at: datetime,
    ) -> VerificationAttemptRecord:
        self.calls.append("verification")
        return VerificationAttemptRecord(
            id=self.verification_attempt_id,
            status=self.verification_status,
            failure_reason=self.verification_failure_reason,
        )

    async def next_geofence_attempt_number(
        self,
        connection: FakeConnection,
        verification_attempt_id: UUID,
    ) -> int:
        self.calls.append("number")
        return self.existing_attempt_count + len(self.inserted_attempts) + 1

    async def insert_geofence_attempt(
        self,
        connection: FakeConnection,
        geofence_attempt_id: UUID,
        verification_attempt_id: UUID,
        attempt_number: int,
        accuracy_m: float | None,
        result: Any,
        captured_at: datetime,
        validated_at: datetime,
    ) -> None:
        self.calls.append("insert")
        self.inserted_attempts.append(
            {
                "id": geofence_attempt_id,
                "verification_attempt_id": verification_attempt_id,
                "attempt_number": attempt_number,
                "accuracy_m": accuracy_m,
                "result": result,
                "captured_at": captured_at,
                "validated_at": validated_at,
            }
        )

    async def mark_verification_attempt_failed(
        self,
        connection: FakeConnection,
        verification_attempt_id: UUID,
        failure_reason: str,
        completed_at: datetime,
    ) -> None:
        self.calls.append("mark_failed")
        self.marked_failed = (
            verification_attempt_id,
            failure_reason,
            completed_at,
        )
        self.verification_status = "failed"
        self.verification_failure_reason = failure_reason


def build_student(**overrides: Any) -> StudentProfileRecord:
    values = {"id": STUDENT_ID, "profile_status": "active"}
    values.update(overrides)
    return StudentProfileRecord(**values)


def build_session(**overrides: Any) -> AttendanceSessionRecord:
    values = {
        "id": SESSION_ID,
        "status": "active",
        "check_in_opens_at": CURRENT_TIME - timedelta(minutes=5),
        "check_in_closes_at": CURRENT_TIME + timedelta(minutes=30),
        "requires_geofence": True,
        "requires_face_verification": True,
        "closed_at": None,
        "cancelled_at": None,
    }
    values.update(overrides)
    return AttendanceSessionRecord(**values)


def build_geofence(**overrides: Any) -> SessionGeofenceRecord:
    values = {
        "centre_latitude": Decimal("6.795132"),
        "centre_longitude": Decimal("79.900421"),
        "radius_m": Decimal("60"),
        "accuracy_buffer_m": Decimal("10"),
        "maximum_allowed_accuracy_m": Decimal("50"),
    }
    values.update(overrides)
    return SessionGeofenceRecord(**values)


def build_reading(**overrides: Any) -> GeofenceReading:
    values = {
        "latitude": 6.795132,
        "longitude": 79.900421,
        "accuracy_m": 5.0,
        "captured_at": CURRENT_TIME - timedelta(seconds=1),
        "mocked": False,
    }
    values.update(overrides)
    return GeofenceReading(**values)


def build_service(
    repository: FakeRepository,
    *,
    max_attempts: int = 3,
) -> GeofenceValidationService:
    next_uuid = 100

    def uuid_factory() -> UUID:
        nonlocal next_uuid
        next_uuid += 1
        return UUID(int=next_uuid)

    return GeofenceValidationService(
        policy=GeofenceValidationPolicy(
            max_reading_age_seconds=30,
            max_future_skew_seconds=5,
        ),
        max_attempts=max_attempts,
        repository=repository,
        clock=lambda: CURRENT_TIME,
        uuid_factory=uuid_factory,
    )


async def test_eligible_student_pass_is_stored_and_remains_in_progress() -> None:
    repository = FakeRepository()

    outcome = await build_service(repository).validate_attempt(
        FakePool(),
        USER_ID,
        SESSION_ID,
        build_reading(),
    )

    assert outcome.verification_attempt_id == VERIFICATION_ATTEMPT_ID
    assert outcome.attempt_number == 1
    assert outcome.result.decision is GeofenceDecision.PASSED
    assert outcome.result.next_step is GeofenceNextStep.FACE_VERIFICATION
    assert repository.inserted_attempts[0]["accuracy_m"] == 5.0
    assert repository.marked_failed is None
    assert repository.verification_status == IN_PROGRESS_STATUS
    assert repository.attendance_records_created == 0


async def test_retry_attempts_receive_sequential_numbers() -> None:
    repository = FakeRepository()
    service = build_service(repository)
    reading = build_reading(accuracy_m=55.0)

    first = await service.validate_attempt(FakePool(), USER_ID, SESSION_ID, reading)
    second = await service.validate_attempt(FakePool(), USER_ID, SESSION_ID, reading)

    assert first.attempt_number == 1
    assert second.attempt_number == 2
    assert first.result.decision is GeofenceDecision.RETRY_REQUIRED
    assert second.result.decision is GeofenceDecision.RETRY_REQUIRED
    assert [item["attempt_number"] for item in repository.inserted_attempts] == [1, 2]


async def test_last_retry_becomes_terminal_attempt_limit_failure() -> None:
    repository = FakeRepository(existing_attempt_count=2)

    outcome = await build_service(repository).validate_attempt(
        FakePool(),
        USER_ID,
        SESSION_ID,
        build_reading(accuracy_m=55.0),
    )

    assert outcome.attempt_number == 3
    assert outcome.result.decision is GeofenceDecision.FAILED
    assert outcome.result.next_step is GeofenceNextStep.NONE
    assert outcome.result.reason is GeofenceReason.ATTEMPT_LIMIT_REACHED
    assert repository.marked_failed == (
        VERIFICATION_ATTEMPT_ID,
        GeofenceReason.ATTEMPT_LIMIT_REACHED.value,
        CURRENT_TIME,
    )


async def test_attempt_limit_rejects_an_additional_attempt() -> None:
    repository = FakeRepository(existing_attempt_count=3)

    with pytest.raises(GeofenceAttemptLimitReachedError) as exc_info:
        await build_service(repository).validate_attempt(
            FakePool(),
            USER_ID,
            SESSION_ID,
            build_reading(),
        )

    assert exc_info.value.max_attempts == 3
    assert repository.inserted_attempts == []


async def test_attempt_limit_reason_is_preserved_after_terminal_retry() -> None:
    repository = FakeRepository(
        verification_status="failed",
        verification_failure_reason=GeofenceReason.ATTEMPT_LIMIT_REACHED.value,
        existing_attempt_count=3,
    )

    with pytest.raises(GeofenceAttemptLimitReachedError):
        await build_service(repository).validate_attempt(
            FakePool(),
            USER_ID,
            SESSION_ID,
            build_reading(),
        )

    assert repository.inserted_attempts == []


async def test_outside_result_marks_overall_verification_failed() -> None:
    repository = FakeRepository()

    outcome = await build_service(repository).validate_attempt(
        FakePool(),
        USER_ID,
        SESSION_ID,
        build_reading(latitude=6.9, accuracy_m=5.0),
    )

    assert outcome.result.decision is GeofenceDecision.FAILED
    assert outcome.result.reason is GeofenceReason.OUTSIDE_GEOFENCE
    assert repository.marked_failed == (
        VERIFICATION_ATTEMPT_ID,
        GeofenceReason.OUTSIDE_GEOFENCE.value,
        CURRENT_TIME,
    )


@pytest.mark.parametrize("student", [None, build_student(profile_status="archived")])
async def test_missing_or_inactive_student_profile_is_rejected(
    student: StudentProfileRecord | None,
) -> None:
    repository = FakeRepository()
    repository.student = student

    with pytest.raises(ActiveStudentProfileNotFoundError):
        await build_service(repository).validate_attempt(
            FakePool(),
            USER_ID,
            SESSION_ID,
            build_reading(),
        )

    assert repository.calls == ["student"]


async def test_missing_session_is_rejected() -> None:
    repository = FakeRepository()
    repository.session = None

    with pytest.raises(AttendanceSessionNotFoundError):
        await build_service(repository).validate_attempt(
            FakePool(),
            USER_ID,
            SESSION_ID,
            build_reading(),
        )


@pytest.mark.parametrize(
    "session",
    [
        build_session(status="closed"),
        build_session(closed_at=CURRENT_TIME),
        build_session(cancelled_at=CURRENT_TIME),
    ],
)
async def test_inactive_closed_or_cancelled_session_is_rejected(
    session: AttendanceSessionRecord,
) -> None:
    repository = FakeRepository(session=session)

    with pytest.raises(AttendanceSessionNotActiveError):
        await build_service(repository).validate_attempt(
            FakePool(),
            USER_ID,
            SESSION_ID,
            build_reading(),
        )


async def test_check_in_that_has_not_opened_is_rejected() -> None:
    repository = FakeRepository(
        session=build_session(check_in_opens_at=CURRENT_TIME + timedelta(seconds=1)),
    )

    with pytest.raises(CheckInNotOpenError):
        await build_service(repository).validate_attempt(
            FakePool(),
            USER_ID,
            SESSION_ID,
            build_reading(),
        )


async def test_closed_check_in_window_is_rejected() -> None:
    repository = FakeRepository(
        session=build_session(check_in_closes_at=CURRENT_TIME),
    )

    with pytest.raises(CheckInClosedError):
        await build_service(repository).validate_attempt(
            FakePool(),
            USER_ID,
            SESSION_ID,
            build_reading(),
        )


async def test_session_without_check_in_window_is_not_active() -> None:
    repository = FakeRepository(
        session=build_session(check_in_opens_at=None),
    )

    with pytest.raises(AttendanceSessionNotActiveError):
        await build_service(repository).validate_attempt(
            FakePool(),
            USER_ID,
            SESSION_ID,
            build_reading(),
        )


async def test_session_that_does_not_require_geofence_is_rejected() -> None:
    repository = FakeRepository(
        session=build_session(requires_geofence=False),
    )

    with pytest.raises(GeofenceNotRequiredError):
        await build_service(repository).validate_attempt(
            FakePool(),
            USER_ID,
            SESSION_ID,
            build_reading(),
        )


async def test_student_not_in_session_snapshot_is_rejected() -> None:
    repository = FakeRepository(eligible=False)

    with pytest.raises(StudentNotEligibleError):
        await build_service(repository).validate_attempt(
            FakePool(),
            USER_ID,
            SESSION_ID,
            build_reading(),
        )

    assert "verification" not in repository.calls


@pytest.mark.parametrize(
    "geofence",
    [
        None,
        build_geofence(centre_latitude=None),
        build_geofence(centre_longitude=None),
        build_geofence(radius_m=None),
        build_geofence(accuracy_buffer_m=None),
        build_geofence(maximum_allowed_accuracy_m=None),
    ],
)
async def test_missing_or_partial_geofence_snapshot_is_rejected(
    geofence: SessionGeofenceRecord | None,
) -> None:
    repository = FakeRepository()
    repository.geofence = geofence

    with pytest.raises(GeofenceNotConfiguredError):
        await build_service(repository).validate_attempt(
            FakePool(),
            USER_ID,
            SESSION_ID,
            build_reading(),
        )


async def test_terminal_overall_verification_cannot_accept_another_attempt() -> None:
    repository = FakeRepository(verification_status="failed")

    with pytest.raises(VerificationAttemptClosedError):
        await build_service(repository).validate_attempt(
            FakePool(),
            USER_ID,
            SESSION_ID,
            build_reading(),
        )

    assert repository.inserted_attempts == []


async def test_naive_service_clock_is_rejected() -> None:
    repository = FakeRepository()
    service = GeofenceValidationService(
        policy=GeofenceValidationPolicy(30, 5),
        max_attempts=3,
        repository=repository,
        clock=lambda: CURRENT_TIME.replace(tzinfo=None),
    )

    with pytest.raises(ValueError, match="clock must include a timezone"):
        await service.validate_attempt(
            FakePool(),
            USER_ID,
            SESSION_ID,
            build_reading(),
        )


def test_max_attempts_must_be_positive() -> None:
    with pytest.raises(ValueError, match="at least one"):
        GeofenceValidationService(
            policy=GeofenceValidationPolicy(30, 5),
            max_attempts=0,
        )
