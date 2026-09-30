"""SessionOverrideService: the session-wide geofence waiver.

The rule under test is that a waiver changes what the session requires and
never what a student proved. Evidence tables are not touched here at all; the
repository fake records exactly what the service asked it to change.
"""

import json
from datetime import UTC, datetime
from uuid import UUID

import pytest

from modules.academic.lecturer_profile.exception import LecturerProfileNotFoundError
from modules.academic.lecturer_profile.repository import LecturerProfileRecord
from modules.attendance_verification.check_in.domain import (
    EffectiveVerificationPolicy,
    RequiredStep,
    StepRequirement,
)
from modules.attendance_verification.session_overrides.domain import (
    REOPENABLE_GEOFENCE_FAILURES,
    GeofenceHealth,
    GeofenceWaiverReason,
    OverrideScope,
    SessionVerificationOverride,
)
from modules.attendance_verification.session_overrides.exception import (
    GeofenceNotRequiredError,
    InvalidWaiverReasonError,
    SessionNotActiveError,
    SessionNotFoundError,
)
from modules.attendance_verification.session_overrides.repository import (
    OverrideSessionRecord,
    ReopenedAttempt,
)
from modules.attendance_verification.session_overrides.service import SessionOverrideService

USER_ID = UUID("20000000-0000-0000-0000-000000000002")
OTHER_USER_ID = UUID("20000000-0000-0000-0000-000000000099")
LECTURER_ID = UUID("22000000-0000-0000-0000-000000000001")
SESSION_ID = UUID("40000000-0000-0000-0000-000000000001")
OTHER_SESSION_ID = UUID("40000000-0000-0000-0000-000000000002")
OVERRIDE_ID = UUID("90000000-0000-0000-0000-000000000001")
FAILED_ATTEMPT_ID = UUID("50000000-0000-0000-0000-000000000001")
FAILED_STUDENT_ID = UUID("23000000-0000-0000-0000-000000000001")
NOW = datetime(2026, 9, 30, 9, 17, tzinfo=UTC)


class FakeTransaction:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, *exc: object) -> bool:
        return False


class FakeConnection:
    def __init__(self) -> None:
        self.executed: list[tuple[str, tuple]] = []

    def transaction(self) -> FakeTransaction:
        return FakeTransaction()

    async def execute(self, query: str, *args) -> None:
        self.executed.append((query, args))

    def audit_rows(self) -> list[tuple]:
        return [args for query, args in self.executed if "audit.audit_logs" in query]


class FakeAcquire:
    def __init__(self, connection: FakeConnection) -> None:
        self.connection = connection

    async def __aenter__(self) -> FakeConnection:
        return self.connection

    async def __aexit__(self, *exc: object) -> bool:
        return False


class FakePool:
    def __init__(self) -> None:
        self.connection = FakeConnection()

    def acquire(self) -> FakeAcquire:
        return FakeAcquire(self.connection)


class FakeLecturerProfiles:
    def __init__(self, status: str | None = "active") -> None:
        self.status = status

    async def find_by_user_id(self, connection, user_id):
        if self.status is None or user_id != USER_ID:
            return None
        return LecturerProfileRecord(
            id=LECTURER_ID, user_id=USER_ID, employee_number="E1", first_name="Dulani",
            middle_name=None, last_name="Meedeniya", profile_status=self.status,
            university_email="lecturer@example.edu",
        )


def active_session(session_id: UUID = SESSION_ID, **overrides) -> OverrideSessionRecord:
    values = dict(
        id=session_id, activated_at=NOW, closed_at=None, cancelled_at=None,
        requires_geofence=True, requires_face_verification=True,
    )
    values.update(overrides)
    return OverrideSessionRecord(**values)


class FakeOverrideRepository:
    """Holds sessions and waivers per session, like the real tables."""

    def __init__(self, sessions: list[OverrideSessionRecord], *, affected: int = 187) -> None:
        self.sessions = {session.id: session for session in sessions}
        self.overrides: dict[UUID, SessionVerificationOverride] = {}
        self.affected = affected
        self.reopened: list[ReopenedAttempt] = [
            ReopenedAttempt(FAILED_ATTEMPT_ID, FAILED_STUDENT_ID, "ATTEMPT_LIMIT_REACHED"),
        ]
        self.reopen_calls: list[tuple[UUID, frozenset[str]]] = []
        self.lock_requests: list[bool] = []
        self.insert_race = False

    async def find_session_for_lecturer(self, connection, session_id, lecturer_id, *, lock_for_update=False):
        self.lock_requests.append(lock_for_update)
        return self.sessions.get(session_id) if lecturer_id == LECTURER_ID else None

    async def find_override(self, connection, session_id, factor):
        return self.overrides.get(session_id)

    async def count_students_without_geofence_pass(self, connection, session_id):
        return self.affected

    async def insert_override(self, connection, **values):
        if self.insert_race or values["session_id"] in self.overrides:
            self.overrides.setdefault(values["session_id"], self._override(values))
            return None
        self.overrides[values["session_id"]] = self._override(values)
        return OVERRIDE_ID

    async def reopen_attempts_failed_by_geofence(self, connection, session_id, reasons):
        self.reopen_calls.append((session_id, reasons))
        return self.reopened

    async def geofence_counts(self, connection, session_id):
        return 193, 6

    @staticmethod
    def _override(values) -> SessionVerificationOverride:
        return SessionVerificationOverride(
            id=OVERRIDE_ID, session_id=values["session_id"],
            verification_factor=values["factor"], scope=OverrideScope.SESSION,
            previous_policy=StepRequirement.REQUIRED, new_policy=StepRequirement.WAIVED,
            reason_code=values["reason_code"], reason_text=values["reason_text"],
            performed_by=values["performed_by"], performed_by_name="Dulani Meedeniya",
            performed_at=values["performed_at"],
            affected_student_count=values["affected_student_count"],
        )


def build_service(repository: FakeOverrideRepository, profiles=None) -> SessionOverrideService:
    return SessionOverrideService(
        repository=repository,
        lecturer_profile_repository=profiles or FakeLecturerProfiles(),
        clock=lambda: NOW,
    )


async def waive(service, pool, *, session_id=SESSION_ID, user_id=USER_ID,
                reason_code="GPS_INACCURATE", reason_text=None):
    return await service.waive_geofence_for_user(
        pool, user_id, session_id, reason_code=reason_code, reason_text=reason_text,
    )


async def test_waiving_changes_the_effective_policy_to_waived() -> None:
    repository = FakeOverrideRepository([active_session()])

    result = await waive(build_service(repository), FakePool())

    assert result.created is True
    assert result.view.policy.geofence is StepRequirement.WAIVED
    assert result.view.policy.face is StepRequirement.REQUIRED
    assert result.view.policy.required_steps == (RequiredStep.FACE,)
    assert result.view.geofence_waiver is not None
    assert result.view.geofence_waiver.reason_code is GeofenceWaiverReason.GPS_INACCURATE
    assert repository.lock_requests == [True]


async def test_waiving_reopens_only_geofence_failures_and_edits_no_evidence() -> None:
    repository = FakeOverrideRepository([active_session()])
    pool = FakePool()

    result = await waive(build_service(repository), pool)

    assert repository.reopen_calls == [(SESSION_ID, REOPENABLE_GEOFENCE_FAILURES)]
    assert "MOCK_LOCATION_DETECTED" not in REOPENABLE_GEOFENCE_FAILURES
    assert result.reopened_attempt_count == 1
    # The only statement the service runs itself is the audit insert.
    assert all("audit.audit_logs" in query for query, _ in pool.connection.executed)


async def test_waiving_writes_a_structured_audit_record() -> None:
    repository = FakeOverrideRepository([active_session()], affected=238)
    pool = FakePool()

    await waive(build_service(repository), pool, reason_code="OTHER", reason_text="Projector room GPS dead zone")

    [audit] = pool.connection.audit_rows()
    actor_user_id, actor_type, action, entity_type, entity_id = audit[:5]
    old_values, new_values, metadata = (json.loads(value) for value in audit[7:10])
    assert (actor_user_id, actor_type, action) == (USER_ID, "lecturer", "session.verification_override")
    assert (entity_type, entity_id) == ("attendance_session", SESSION_ID)
    assert old_values == {"geofence": "required"}
    assert new_values == {"geofence": "waived"}
    assert metadata["overrideId"] == str(OVERRIDE_ID)
    assert metadata["verificationFactor"] == "geofence"
    assert metadata["scope"] == "session"
    assert (metadata["previousPolicy"], metadata["newPolicy"]) == ("required", "waived")
    assert (metadata["reasonCode"], metadata["reasonText"]) == ("OTHER", "Projector room GPS dead zone")
    assert metadata["affectedStudentCount"] == 238
    assert metadata["performedAt"] == NOW.isoformat()
    assert metadata["reopenedAttempts"] == [{
        "verificationAttemptId": str(FAILED_ATTEMPT_ID),
        "studentId": str(FAILED_STUDENT_ID),
        "previousFailureReason": "ATTEMPT_LIMIT_REACHED",
    }]


async def test_affected_student_count_is_stored_on_the_waiver() -> None:
    repository = FakeOverrideRepository([active_session()], affected=42)

    result = await waive(build_service(repository), FakePool())

    assert result.view.geofence_waiver.affected_student_count == 42


async def test_a_second_waiver_is_idempotent_and_writes_nothing_more() -> None:
    repository = FakeOverrideRepository([active_session()])
    service = build_service(repository)
    pool = FakePool()
    await waive(service, pool)

    again = await waive(service, pool, reason_code="GPS_UNAVAILABLE")

    assert again.created is False
    assert again.view.geofence_waiver.reason_code is GeofenceWaiverReason.GPS_INACCURATE
    assert len(pool.connection.audit_rows()) == 1
    assert len(repository.reopen_calls) == 1


async def test_a_concurrent_duplicate_insert_is_reported_as_existing() -> None:
    repository = FakeOverrideRepository([active_session()])
    repository.insert_race = True
    pool = FakePool()

    result = await waive(build_service(repository), pool)

    assert result.created is False
    assert repository.reopen_calls == []
    assert pool.connection.audit_rows() == []


async def test_a_waiver_applies_only_to_its_own_session() -> None:
    repository = FakeOverrideRepository([active_session(), active_session(OTHER_SESSION_ID)])
    service = build_service(repository)
    pool = FakePool()
    await waive(service, pool)

    other = await service.get_policy_for_user(pool, USER_ID, OTHER_SESSION_ID)

    assert other.policy.geofence is StepRequirement.REQUIRED
    assert other.geofence_waiver is None


async def test_a_lecturer_not_assigned_to_the_session_cannot_waive() -> None:
    repository = FakeOverrideRepository([active_session()])
    repository.sessions = {}  # the ownership query finds nothing for this lecturer

    with pytest.raises(SessionNotFoundError):
        await waive(build_service(repository), FakePool())
    assert repository.overrides == {}


async def test_an_account_without_an_active_lecturer_profile_cannot_waive() -> None:
    repository = FakeOverrideRepository([active_session()])

    with pytest.raises(LecturerProfileNotFoundError):
        await waive(build_service(repository), FakePool(), user_id=OTHER_USER_ID)
    assert repository.overrides == {}


@pytest.mark.parametrize(
    "session",
    [
        active_session(activated_at=None),
        active_session(closed_at=NOW),
        active_session(cancelled_at=NOW),
    ],
)
async def test_only_an_active_session_can_be_waived(session) -> None:
    repository = FakeOverrideRepository([session])

    with pytest.raises(SessionNotActiveError):
        await waive(build_service(repository), FakePool())


async def test_a_session_without_geofence_has_nothing_to_waive() -> None:
    repository = FakeOverrideRepository([active_session(requires_geofence=False)])

    with pytest.raises(GeofenceNotRequiredError):
        await waive(build_service(repository), FakePool())


async def test_other_needs_a_description() -> None:
    repository = FakeOverrideRepository([active_session()])

    with pytest.raises(InvalidWaiverReasonError):
        await waive(build_service(repository), FakePool(), reason_code="OTHER", reason_text="   ")
    assert repository.overrides == {}


async def test_the_policy_view_reports_geofence_health() -> None:
    repository = FakeOverrideRepository([active_session()])

    view = await build_service(repository).get_policy_for_user(FakePool(), USER_ID, SESSION_ID)

    assert (view.geofence_health.attempted, view.geofence_health.passed) == (193, 6)
    assert view.geofence_health.failed == 187
    assert round(view.geofence_health.failure_rate * 100, 1) == 96.9
    assert view.geofence_health.warning is True


def test_the_health_warning_needs_enough_attempts_and_failures() -> None:
    assert GeofenceHealth(9, 0, minimum_attempts=10, warning_failure_rate=0.7).warning is False
    assert GeofenceHealth(10, 4, minimum_attempts=10, warning_failure_rate=0.7).warning is False
    assert GeofenceHealth(10, 3, minimum_attempts=10, warning_failure_rate=0.7).warning is True
    assert GeofenceHealth(0, 0, minimum_attempts=10, warning_failure_rate=0.7).failure_rate == 0.0


def test_the_effective_policy_keeps_waived_distinct_from_not_required() -> None:
    waived = EffectiveVerificationPolicy.resolve(
        requires_geofence=True,
        requires_face_verification=True,
        waived_steps=frozenset({RequiredStep.GEOFENCE}),
    )
    normal = EffectiveVerificationPolicy.resolve(
        requires_geofence=True, requires_face_verification=False,
    )

    assert waived.geofence is StepRequirement.WAIVED
    assert waived.required_steps == (RequiredStep.FACE,)
    assert normal.geofence is StepRequirement.REQUIRED
    assert normal.face is StepRequirement.NOT_REQUIRED
    assert normal.required_steps == (RequiredStep.GEOFENCE,)
