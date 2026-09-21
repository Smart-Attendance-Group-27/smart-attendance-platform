"""AttendanceFinalizationService, against fakes for everything it depends on.

The one behaviour worth losing sleep over is the face-pass/close race: a
student who finishes their last required step in the same instant the
lecturer closes the session must not end up absent depending on which
transaction happened to commit first. That's what the reconciliation tests
below are really checking.
"""

from datetime import UTC, datetime
from uuid import UUID

from fakes import FakeQrEvidenceProvider
from modules.attendance_verification.attendance_state import (
    FinalAttendanceStatus,
    InitialCheckInStatus,
)
from modules.attendance_verification.check_in.domain import InitialCheckIn, ReconciledCheckIn
from modules.attendance_verification.finalization.repository import RosterStudentState
from modules.attendance_verification.finalization.service import AttendanceFinalizationService
from modules.attendance_verification.finalization.types import FinalizationSummary

SESSION_ID = UUID("40000000-0000-0000-0000-000000000001")
ACTOR_ID = UUID("20000000-0000-0000-0000-000000000002")
CLOSED_AT = datetime(2026, 9, 21, 10, 0, tzinfo=UTC)

STUDENT_ON_TIME = UUID("23000000-0000-0000-0000-000000000001")
STUDENT_LATE = UUID("23000000-0000-0000-0000-000000000002")
STUDENT_ABSENT = UUID("23000000-0000-0000-0000-000000000003")
STUDENT_MANUAL = UUID("23000000-0000-0000-0000-000000000004")
STUDENT_QR_FAILED = UUID("23000000-0000-0000-0000-000000000005")
STUDENT_RECONCILED = UUID("23000000-0000-0000-0000-000000000006")

ATTEMPT_ON_TIME = UUID("50000000-0000-0000-0000-000000000001")
ATTEMPT_LATE = UUID("50000000-0000-0000-0000-000000000002")
ATTEMPT_MANUAL = UUID("50000000-0000-0000-0000-000000000004")
ATTEMPT_QR_FAILED = UUID("50000000-0000-0000-0000-000000000005")
ATTEMPT_RECONCILED = UUID("50000000-0000-0000-0000-000000000006")


class FakeCheckInService:
    def __init__(self, reconciled: list[ReconciledCheckIn] | None = None) -> None:
        self.reconciled = reconciled or []
        self.calls: list[tuple[UUID, datetime]] = []

    async def reconcile_before_close(self, connection, session_id, closed_at, *, session=None):
        self.calls.append((session_id, closed_at))
        return self.reconciled


class FakeFinalizationRepository:
    def __init__(self, roster: list[RosterStudentState]) -> None:
        self.roster = roster
        self.locked_session_ids: list[UUID] = []
        self.upserted: tuple | None = None

    async def lock_session_attempts(self, connection, session_id):
        self.locked_session_ids.append(session_id)

    async def fetch_roster_state(self, connection, session_id):
        return self.roster

    async def upsert_automatic_records(self, connection, session_id, results, decided_at):
        self.upserted = (session_id, list(results), decided_at)


def default_roster() -> list[RosterStudentState]:
    return [
        RosterStudentState(
            student_id=STUDENT_ON_TIME,
            verification_attempt_id=ATTEMPT_ON_TIME,
            initial_check_in_status=InitialCheckInStatus.CHECKED_IN.value,
            has_manual_record=False,
        ),
        RosterStudentState(
            student_id=STUDENT_LATE,
            verification_attempt_id=ATTEMPT_LATE,
            initial_check_in_status=InitialCheckInStatus.LATE_CHECKED_IN.value,
            has_manual_record=False,
        ),
        RosterStudentState(
            student_id=STUDENT_ABSENT,
            verification_attempt_id=None,
            initial_check_in_status=None,
            has_manual_record=False,
        ),
        RosterStudentState(
            student_id=STUDENT_MANUAL,
            verification_attempt_id=ATTEMPT_MANUAL,
            initial_check_in_status=InitialCheckInStatus.CHECKED_IN.value,
            has_manual_record=True,
        ),
    ]


async def test_decides_present_late_and_absent_and_skips_manual() -> None:
    repository = FakeFinalizationRepository(default_roster())
    service = AttendanceFinalizationService(
        FakeQrEvidenceProvider(),
        check_in_service=FakeCheckInService(),
        repository=repository,
    )

    summary = await service.finalize(
        None,
        session_id=SESSION_ID,
        closed_at=CLOSED_AT,
        actor_user_id=ACTOR_ID,
    )

    assert summary.enrolled == 4
    assert summary.present == 1
    assert summary.late == 1
    assert summary.absent == 1
    assert summary.kept_manual == 1
    assert summary.finalized_at == CLOSED_AT

    decided_students = {result.student_id: result.status for result in summary.results}
    assert decided_students[STUDENT_ON_TIME] is FinalAttendanceStatus.PRESENT
    assert decided_students[STUDENT_LATE] is FinalAttendanceStatus.LATE
    assert decided_students[STUDENT_ABSENT] is FinalAttendanceStatus.ABSENT
    assert STUDENT_MANUAL not in decided_students


async def test_never_writes_a_result_for_a_student_with_a_manual_record() -> None:
    repository = FakeFinalizationRepository(default_roster())
    service = AttendanceFinalizationService(
        FakeQrEvidenceProvider(),
        check_in_service=FakeCheckInService(),
        repository=repository,
    )

    await service.finalize(
        None,
        session_id=SESSION_ID,
        closed_at=CLOSED_AT,
        actor_user_id=ACTOR_ID,
    )

    written_student_ids = {result.student_id for result in repository.upserted[1]}
    assert STUDENT_MANUAL not in written_student_ids


async def test_a_checked_in_student_who_failed_a_required_qr_scan_is_absent() -> None:
    roster = [
        RosterStudentState(
            student_id=STUDENT_QR_FAILED,
            verification_attempt_id=ATTEMPT_QR_FAILED,
            initial_check_in_status=InitialCheckInStatus.CHECKED_IN.value,
            has_manual_record=False,
        ),
    ]
    qr_evidence = FakeQrEvidenceProvider()
    qr_evidence.set_progress(ATTEMPT_QR_FAILED, required_count=1, passed_count=0)
    service = AttendanceFinalizationService(
        qr_evidence,
        check_in_service=FakeCheckInService(),
        repository=FakeFinalizationRepository(roster),
    )

    summary = await service.finalize(
        None,
        session_id=SESSION_ID,
        closed_at=CLOSED_AT,
        actor_user_id=ACTOR_ID,
    )

    assert summary.results[0].status is FinalAttendanceStatus.ABSENT


async def test_reconciliation_runs_before_the_roster_is_read() -> None:
    """The race this whole module exists for: a student who finished their
    last step in the same instant the session closed must not end up absent
    just because reconciliation happened to run after the roster was read."""

    reconciled = [
        ReconciledCheckIn(
            verification_attempt_id=ATTEMPT_RECONCILED,
            student_id=STUDENT_RECONCILED,
            initial_check_in=InitialCheckIn(
                checked_in_at=CLOSED_AT,
                status=InitialCheckInStatus.CHECKED_IN,
            ),
        ),
    ]
    check_in_service = FakeCheckInService(reconciled)
    # The roster already reflects the reconciled check-in, as it would once
    # reconcile_before_close has actually written it inside the same
    # transaction — the fake repository stands in for that persisted state.
    roster = [
        RosterStudentState(
            student_id=STUDENT_RECONCILED,
            verification_attempt_id=ATTEMPT_RECONCILED,
            initial_check_in_status=InitialCheckInStatus.CHECKED_IN.value,
            has_manual_record=False,
        ),
    ]
    service = AttendanceFinalizationService(
        FakeQrEvidenceProvider(),
        check_in_service=check_in_service,
        repository=FakeFinalizationRepository(roster),
    )

    summary = await service.finalize(
        None,
        session_id=SESSION_ID,
        closed_at=CLOSED_AT,
        actor_user_id=ACTOR_ID,
    )

    assert check_in_service.calls == [(SESSION_ID, CLOSED_AT)]
    assert summary.reconciled_student_ids == (STUDENT_RECONCILED,)
    assert summary.results[0].status is FinalAttendanceStatus.PRESENT
    assert summary.absent == 0


async def test_locks_the_session_before_touching_anything_else() -> None:
    repository = FakeFinalizationRepository([])
    service = AttendanceFinalizationService(
        FakeQrEvidenceProvider(),
        check_in_service=FakeCheckInService(),
        repository=repository,
    )

    await service.finalize(
        None,
        session_id=SESSION_ID,
        closed_at=CLOSED_AT,
        actor_user_id=ACTOR_ID,
    )

    assert repository.locked_session_ids == [SESSION_ID]


async def test_deactivated_qr_batch_ids_are_left_for_the_caller_to_fill_in() -> None:
    service = AttendanceFinalizationService(
        FakeQrEvidenceProvider(),
        check_in_service=FakeCheckInService(),
        repository=FakeFinalizationRepository([]),
    )

    summary = await service.finalize(
        None,
        session_id=SESSION_ID,
        closed_at=CLOSED_AT,
        actor_user_id=ACTOR_ID,
    )

    assert summary.deactivated_qr_batch_ids == ()


class RecordingRedis:
    def __init__(self) -> None:
        self.deleted_keys: list[str] = []

    async def delete(self, key: str) -> None:
        self.deleted_keys.append(key)


async def test_after_commit_clears_the_cache_for_every_deactivated_batch() -> None:
    batch_a = UUID("60000000-0000-0000-0000-000000000001")
    batch_b = UUID("60000000-0000-0000-0000-000000000002")
    summary = FinalizationSummary(
        enrolled=0,
        present=0,
        late=0,
        absent=0,
        kept_manual=0,
        reconciled_student_ids=(),
        deactivated_qr_batch_ids=(batch_a, batch_b),
        results=(),
        finalized_at=CLOSED_AT,
    )
    redis_client = RecordingRedis()

    await AttendanceFinalizationService.after_commit(summary, redis_client)

    assert redis_client.deleted_keys == [f"qr:batch:{batch_a}", f"qr:batch:{batch_b}"]


async def test_after_commit_is_a_no_op_with_nothing_deactivated() -> None:
    summary = FinalizationSummary(
        enrolled=0,
        present=0,
        late=0,
        absent=0,
        kept_manual=0,
        reconciled_student_ids=(),
        deactivated_qr_batch_ids=(),
        results=(),
        finalized_at=CLOSED_AT,
    )
    redis_client = RecordingRedis()

    await AttendanceFinalizationService.after_commit(summary, redis_client)

    assert redis_client.deleted_keys == []


async def test_each_result_carries_the_account_to_notify() -> None:
    user_id = UUID("20000000-0000-0000-0000-000000000011")
    roster = [
        RosterStudentState(
            student_id=STUDENT_ON_TIME,
            verification_attempt_id=ATTEMPT_ON_TIME,
            initial_check_in_status=InitialCheckInStatus.CHECKED_IN.value,
            has_manual_record=False,
            student_user_id=user_id,
        ),
    ]
    service = AttendanceFinalizationService(
        FakeQrEvidenceProvider(),
        check_in_service=FakeCheckInService(),
        repository=FakeFinalizationRepository(roster),
    )

    summary = await service.finalize(
        None,
        session_id=SESSION_ID,
        closed_at=CLOSED_AT,
        actor_user_id=ACTOR_ID,
    )

    assert summary.results[0].student_id == STUDENT_ON_TIME
    assert summary.results[0].student_user_id == user_id

