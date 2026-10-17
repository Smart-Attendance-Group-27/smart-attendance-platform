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
    EffectiveVerificationPolicy,
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
        # Entry point for POST /check-in and Core's post-face-pass hook.
        # Resolve the authenticated user to a student; never trust a client pass flag.
        # This method aggregates saved evidence rather than running GPS or face checks.
        async with pool.acquire() as connection, connection.transaction():
            student = await self._repository.lock_student_profile_for_user(connection, user_id)
            if student is None or student.profile_status != ACTIVE_PROFILE_STATUS:
                raise ActiveStudentProfileNotFoundError(
                    "No active student profile exists for this account.",
                )

            session = await self._repository.lock_attendance_session(connection, session_id)
            if session is None:
                raise AttendanceSessionNotFoundError("The attendance session was not found.")

            # Reuse this transaction and the session we already locked.
            result = await self.try_check_in(
                connection,
                session_id=session_id,
                student_id=student.id,
                session=session,
            )
            if result is None:
                # Aggregation cannot create an attempt. The verification/start flow
                # must create one first (including the location-waived start path).
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

        Runs inside the caller's transaction. Geofence saves its pass and invokes
        this method on the same connection. Face evidence is committed by the
        separate Face service first; Core then calls ``check_in_for_user`` in
        another transaction. Returns ``None`` when there is no verification
        attempt yet; callers that care turn that into their own error.

        Safe to call on every pass: an already checked-in attempt is reported
        back unchanged rather than re-stamped with a later time.
        """
        ## Check the student in
        # Callers may supply records already locked in their own transaction.
        if session is None:
            session = await self._repository.lock_attendance_session(connection, session_id)
            if session is None:
                raise AttendanceSessionNotFoundError("The attendance session was not found.")

        # Otherwise lock this student's attempt so concurrent completion calls
        # coordinate their decision and preserve the first stored check-in.
        if attempt is None:
            attempt = await self._repository.lock_verification_attempt(
                connection,
                session_id,
                student_id,
            )
        if attempt is None:
            return None

        # A terminal failure stays failed; aggregation does not reopen the attempt.
        if attempt.status == VerificationAttemptStatus.FAILED.value:
            return CheckInResult(
                outcome=CheckInOutcome.FAILED,
                verification_attempt_id=attempt.id,
            )
        ## If the attempt is already checked in, return that rather than recomputing.
        # Idempotency: retries keep the original timestamp and on-time/late result.
        existing = self._existing_check_in(attempt)
        if existing is not None:
            return CheckInResult(
                outcome=CheckInOutcome.CHECKED_IN,
                verification_attempt_id=attempt.id,
                initial_check_in=existing,
            )
        ## Otherwise, read the evidence and decide whether to check in.
        # A closed session bounds qualifying evidence to its recorded close time.
        evidence = await self._read_evidence(
            connection,
            session=session,
            attempt_id=attempt.id,
            started_at=attempt.started_at,
            not_after=session.closed_at,
        )
        # Example: geofence first passed at 09:02 and face at 09:04 -> 09:04.
        # The domain takes the latest of the required steps' qualifying pass times.
        checked_in_at, missing = evaluate_initial_evidence(
            evidence.steps,
            fallback_checked_in_at=evidence.fallback_checked_in_at,
        )

        if checked_in_at is None:
            # Report missing steps without writing a partial check-in.
            return CheckInResult(
                outcome=CheckInOutcome.PENDING,
                verification_attempt_id=attempt.id,
                missing_steps=missing,
            )

        # Classify completion time, then update verification_attempts with
        # status=checked_in, checked_in_at and initial_check_in_status.
        # QR evidence and the final attendance_records row belong to finalization.
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

        # Recover unfinished attempts from saved evidence before finalization.
        # The repository locks candidates and excludes passes after closed_at.
        attempts = await self._repository.list_attempts_with_evidence(
            connection,
            session_id,
            not_after=closed_at,
        )

        reconciled: list[ReconciledCheckIn] = []
        for record in attempts:
            # Apply the same domain rule as live check-in, including any waiver.
            checked_in_at, _missing = evaluate_initial_evidence(
                self._steps_from_record(session, record),
                fallback_checked_in_at=record.started_at,
            )
            if checked_in_at is None:
                # Closure does not invent a pass for an incomplete student.
                continue

            # Preserve the evidence-derived time even though recovery runs later.
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
    def effective_policy(session: AttendanceSessionRecord) -> EffectiveVerificationPolicy:
        # A geofence waiver removes that requirement; face still follows its flag.
        # QR is a later participation check, so it is not an initial required step.
        return EffectiveVerificationPolicy.resolve(
            requires_geofence=session.requires_geofence,
            requires_face_verification=session.requires_face_verification,
            waived_steps=(
                frozenset({RequiredStep.GEOFENCE}) if session.geofence_waived else frozenset()
            ),
        )

    @classmethod
    def required_steps(cls, session: AttendanceSessionRecord) -> tuple[RequiredStep, ...]:
        """Steps that must genuinely pass. A waived step is not one of them."""
        return cls.effective_policy(session).required_steps

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
        # Strictly after the threshold is late; exactly on it remains on time.
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
        # Read only effective required steps, using the existing transaction.
        # Each repository lookup returns the earliest qualifying pass or None.
        for step in self.required_steps(session):
            if step is RequiredStep.GEOFENCE:
                passed_at = await self._repository.geofence_passed_at(
                    connection,
                    attempt_id,
                    not_after=not_after,
                )
            else:
                # Face evidence must have both a passed match and liveness_passed=True.
                passed_at = await self._repository.face_passed_at(
                    connection,
                    attempt_id,
                    not_after=not_after,
                )
            steps.append(StepEvidence(step=step, passed_at=passed_at))

        # With no required steps, the domain uses started_at as the check-in time.
        return _Evidence(steps=tuple(steps), fallback_checked_in_at=started_at)

    @classmethod
    def _steps_from_record(
        cls,
        session: AttendanceSessionRecord,
        record: AttemptEvidenceRecord,
    ) -> tuple[StepEvidence, ...]:
        # Closure fetched evidence in bulk. Convert it to the same input shape
        # used by live aggregation, filtering through the effective requirements.
        passed_at_by_step = {
            RequiredStep.GEOFENCE: record.geofence_passed_at,
            RequiredStep.FACE: record.face_passed_at,
        }
        return tuple(
            StepEvidence(step=step, passed_at=passed_at_by_step[step])
            for step in cls.required_steps(session)
        )


__all__ = ["CheckInService"]
