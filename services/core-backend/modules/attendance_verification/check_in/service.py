from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

import asyncpg

from modules.attendance_verification.attendance_state import (
    InitialCheckInStatus,
    VerificationAttemptStatus,
)
from modules.attendance_verification.check_in.domain import (
    CheckInOutcome,
    CheckInResult,
    InitialCheckIn,
    ReconciledCheckIn,
    RequiredStep,
    StepEvidence,
    evaluate_initial_evidence,
    resolve_initial_check_in_status,
)
from modules.attendance_verification.check_in.exception import (
    ActiveStudentProfileNotFoundError,
    AttendanceSessionNotFoundError,
    VerificationNotStartedError,
)
from modules.attendance_verification.check_in.repository import (
    AttemptEvidenceRecord,
    AttendanceSessionRecord,
    CheckInRepository,
    VerificationAttemptRecord,
)

ACTIVE_PROFILE_STATUS = "active"


@dataclass(frozen=True)
class _Evidence:
    """The evidence for one attempt, already bounded by any close time."""

    steps: tuple[StepEvidence, ...]
    fallback_checked_in_at: datetime | None


class CheckInService:
    """Decides and stores the initial check-in.

    Three entry points, one rule:

    * ``check_in_for_user`` — the student asks, over HTTP.
    * ``try_check_in`` — a verification step just passed and checks the student
      in from inside that step's own transaction.
    * ``reconcile_before_close`` — the lecturer is closing the session; students
      whose evidence completed before the close get their check-in written
      before attendance is decided.

    None of them writes ``attendance_records``. That belongs to finalization.
    """

    def __init__(self, repository: CheckInRepository | None = None) -> None:
        self._repository = repository or CheckInRepository()

    async def check_in_for_user(
        self,
        pool: asyncpg.Pool,
        user_id: UUID,
        session_id: UUID,
    ) -> CheckInResult:
        async with pool.acquire() as connection, connection.transaction():
            student = await self._repository.lock_student_profile_for_user(connection, user_id)
            if student is None or student.profile_status != ACTIVE_PROFILE_STATUS:
                raise ActiveStudentProfileNotFoundError(
                    "No active student profile exists for this account.",
                )

            session = await self._repository.lock_attendance_session(connection, session_id)
            if session is None:
                raise AttendanceSessionNotFoundError("The attendance session was not found.")

            result = await self.try_check_in(
                connection,
                session_id=session_id,
                student_id=student.id,
                session=session,
            )
            if result is None:
                raise VerificationNotStartedError(
                    "No verification attempt exists yet — complete the geofence "
                    "check first.",
                )

            return result

    async def try_check_in(
        self,
        connection: asyncpg.Connection,
        *,
        session_id: UUID,
        student_id: UUID,
        session: AttendanceSessionRecord | None = None,
        attempt: VerificationAttemptRecord | None = None,
    ) -> CheckInResult | None:
        """Check the student in if every required step has passed.

        Runs inside the caller's transaction, so a geofence or face pass and the
        check-in it triggers land together or not at all. Returns ``None`` when
        there is no verification attempt yet; callers that care turn that into
        their own error.

        Safe to call on every pass: an already checked-in attempt is reported
        back unchanged rather than re-stamped with a later time.
        """

        if session is None:
            session = await self._repository.lock_attendance_session(connection, session_id)
            if session is None:
                raise AttendanceSessionNotFoundError("The attendance session was not found.")

        if attempt is None:
            attempt = await self._repository.lock_verification_attempt(
                connection,
                session_id,
                student_id,
            )
        if attempt is None:
            return None

        if attempt.status == VerificationAttemptStatus.FAILED.value:
            return CheckInResult(
                outcome=CheckInOutcome.FAILED,
                verification_attempt_id=attempt.id,
            )

        existing = self._existing_check_in(attempt)
        if existing is not None:
            return CheckInResult(
                outcome=CheckInOutcome.CHECKED_IN,
                verification_attempt_id=attempt.id,
                initial_check_in=existing,
            )

        evidence = await self._read_evidence(
            connection,
            session=session,
            attempt_id=attempt.id,
            started_at=attempt.started_at,
            not_after=session.closed_at,
        )
        checked_in_at, missing = evaluate_initial_evidence(
            evidence.steps,
            fallback_checked_in_at=evidence.fallback_checked_in_at,
        )

        if checked_in_at is None:
            return CheckInResult(
                outcome=CheckInOutcome.PENDING,
                verification_attempt_id=attempt.id,
                missing_steps=missing,
            )

        initial_check_in = self._build_check_in(checked_in_at, session.late_after_at)
        await self._repository.persist_check_in(
            connection,
            attempt.id,
            checked_in_at=initial_check_in.checked_in_at,
            initial_check_in_status=initial_check_in.status,
        )

        return CheckInResult(
            outcome=CheckInOutcome.CHECKED_IN,
            verification_attempt_id=attempt.id,
            initial_check_in=initial_check_in,
            was_persisted=True,
        )

    async def reconcile_before_close(
        self,
        connection: asyncpg.Connection,
        session_id: UUID,
        closed_at: datetime,
        *,
        session: AttendanceSessionRecord | None = None,
    ) -> list[ReconciledCheckIn]:
        """Write the check-ins that were earned before the session closed.

        A student can finish their last verification step in the same second the
        lecturer hits close. Without this, whichever transaction commits second
        loses: the attempt is still ``in_progress`` when attendance is decided,
        and a student who did everything right is marked absent. Bounding the
        evidence at ``closed_at`` keeps the decision the same no matter which
        order the two transactions happened to commit in.

        Call this inside the closing transaction, before finalization reads the
        attempts.
        """

        if session is None:
            session = await self._repository.lock_attendance_session(connection, session_id)
            if session is None:
                raise AttendanceSessionNotFoundError("The attendance session was not found.")

        attempts = await self._repository.list_attempts_with_evidence(
            connection,
            session_id,
            not_after=closed_at,
        )

        reconciled: list[ReconciledCheckIn] = []
        for record in attempts:
            checked_in_at, _missing = evaluate_initial_evidence(
                self._steps_from_record(session, record),
                fallback_checked_in_at=record.started_at,
            )
            if checked_in_at is None:
                continue

            initial_check_in = self._build_check_in(checked_in_at, session.late_after_at)
            await self._repository.persist_check_in(
                connection,
                record.attempt_id,
                checked_in_at=initial_check_in.checked_in_at,
                initial_check_in_status=initial_check_in.status,
            )
            reconciled.append(
                ReconciledCheckIn(
                    verification_attempt_id=record.attempt_id,
                    student_id=record.student_id,
                    initial_check_in=initial_check_in,
                ),
            )

        return reconciled

    @staticmethod
    def required_steps(session: AttendanceSessionRecord) -> tuple[RequiredStep, ...]:
        steps: list[RequiredStep] = []
        if session.requires_geofence:
            steps.append(RequiredStep.GEOFENCE)
        if session.requires_face_verification:
            steps.append(RequiredStep.FACE)
        return tuple(steps)

    @staticmethod
    def _existing_check_in(attempt: VerificationAttemptRecord) -> InitialCheckIn | None:
        if attempt.checked_in_at is None or attempt.initial_check_in_status is None:
            return None
        try:
            status = InitialCheckInStatus(attempt.initial_check_in_status)
        except ValueError:
            # A status outside the frozen vocabulary means something wrote a
            # value this code does not understand. Recomputing would overwrite
            # it, so the check-in is reported as the stored time with the
            # conservative reading.
            status = InitialCheckInStatus.CHECKED_IN
        return InitialCheckIn(checked_in_at=attempt.checked_in_at, status=status)

    @staticmethod
    def _build_check_in(
        checked_in_at: datetime,
        late_after_at: datetime | None,
    ) -> InitialCheckIn:
        return InitialCheckIn(
            checked_in_at=checked_in_at,
            status=resolve_initial_check_in_status(
                checked_in_at=checked_in_at,
                late_after_at=late_after_at,
            ),
        )

    async def _read_evidence(
        self,
        connection: asyncpg.Connection,
        *,
        session: AttendanceSessionRecord,
        attempt_id: UUID,
        started_at: datetime | None,
        not_after: datetime | None,
    ) -> _Evidence:
        steps: list[StepEvidence] = []
        for step in self.required_steps(session):
            if step is RequiredStep.GEOFENCE:
                passed_at = await self._repository.geofence_passed_at(
                    connection,
                    attempt_id,
                    not_after=not_after,
                )
            else:
                passed_at = await self._repository.face_passed_at(
                    connection,
                    attempt_id,
                    not_after=not_after,
                )
            steps.append(StepEvidence(step=step, passed_at=passed_at))

        return _Evidence(steps=tuple(steps), fallback_checked_in_at=started_at)

    @classmethod
    def _steps_from_record(
        cls,
        session: AttendanceSessionRecord,
        record: AttemptEvidenceRecord,
    ) -> tuple[StepEvidence, ...]:
        passed_at_by_step = {
            RequiredStep.GEOFENCE: record.geofence_passed_at,
            RequiredStep.FACE: record.face_passed_at,
        }
        return tuple(
            StepEvidence(step=step, passed_at=passed_at_by_step[step])
            for step in cls.required_steps(session)
        )


__all__ = ["CheckInService"]
