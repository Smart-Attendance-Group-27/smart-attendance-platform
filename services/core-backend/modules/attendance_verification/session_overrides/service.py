from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

import asyncpg

from modules.academic.lecturer_profile.exception import LecturerProfileNotFoundError
from modules.academic.lecturer_profile.repository import LecturerProfileRepository
from modules.attendance_verification.check_in.domain import (
    EffectiveVerificationPolicy,
    RequiredStep,
    StepRequirement,
)
from modules.attendance_verification.session_overrides.domain import (
    REOPENABLE_GEOFENCE_FAILURES,
    GeofenceHealth,
    OverrideScope,
    SessionVerificationOverride,
    clean_waiver_reason,
)
from modules.attendance_verification.session_overrides.exception import (
    GeofenceNotRequiredError,
    InvalidWaiverReasonError,
    SessionNotActiveError,
    SessionNotFoundError,
)
from modules.attendance_verification.session_overrides.repository import (
    OverrideSessionRecord,
    SessionOverrideRepository,
)
from modules.audit.repository import write_audit_log

ACTIVE_PROFILE_STATUS = "active"
ACTOR_TYPE_LECTURER = "lecturer"
AUDIT_ACTION = "session.verification_override"
AUDIT_ENTITY_TYPE = "attendance_session"
DEFAULT_WARNING_MIN_ATTEMPTS = 10
DEFAULT_WARNING_FAILURE_RATE = 0.7


@dataclass(frozen=True)
class SessionVerificationPolicyView:
    session_id: UUID
    policy: EffectiveVerificationPolicy
    geofence_waiver: SessionVerificationOverride | None
    geofence_health: GeofenceHealth


@dataclass(frozen=True)
class GeofenceWaiverResult:
    view: SessionVerificationPolicyView
    # False when the session was already waived and nothing was written.
    created: bool
    reopened_attempt_count: int = 0


class SessionOverrideService:
    """Records session-wide verification waivers and reports on them.

    Only the geofence factor can be waived. A waiver changes the session's
    effective policy; it never edits a verification reading.
    """

    def __init__(
        self,
        repository: SessionOverrideRepository | None = None,
        lecturer_profile_repository: LecturerProfileRepository | None = None,
        *,
        warning_min_attempts: int = DEFAULT_WARNING_MIN_ATTEMPTS,
        warning_failure_rate: float = DEFAULT_WARNING_FAILURE_RATE,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository or SessionOverrideRepository()
        self._lecturer_profile_repository = (
            lecturer_profile_repository or LecturerProfileRepository()
        )
        self._warning_min_attempts = warning_min_attempts
        self._warning_failure_rate = warning_failure_rate
        self._clock = clock or (lambda: datetime.now(UTC))

    async def get_policy_for_user(
        self,
        pool: asyncpg.Pool,
        user_id: UUID,
        session_id: UUID,
    ) -> SessionVerificationPolicyView:
        async with pool.acquire() as connection:
            lecturer_id = await self._resolve_active_lecturer_id(connection, user_id)
            session = await self._repository.find_session_for_lecturer(
                connection,
                session_id,
                lecturer_id,
            )
            if session is None:
                raise SessionNotFoundError()
            return await self._build_view(connection, session)

    async def waive_geofence_for_user(
        self,
        pool: asyncpg.Pool,
        user_id: UUID,
        session_id: UUID,
        *,
        reason_code: str,
        reason_text: str | None,
    ) -> GeofenceWaiverResult:
        try:
            code, text = clean_waiver_reason(reason_code, reason_text)
        except ValueError as error:
            raise InvalidWaiverReasonError(str(error)) from error

        async with pool.acquire() as connection, connection.transaction():
            lecturer_id = await self._resolve_active_lecturer_id(connection, user_id)
            session = await self._repository.find_session_for_lecturer(
                connection,
                session_id,
                lecturer_id,
                lock_for_update=True,
            )
            if session is None:
                raise SessionNotFoundError()
            if (
                session.activated_at is None
                or session.closed_at is not None
                or session.cancelled_at is not None
            ):
                raise SessionNotActiveError()
            if not session.requires_geofence:
                raise GeofenceNotRequiredError()

            existing = await self._repository.find_override(
                connection,
                session_id,
                RequiredStep.GEOFENCE,
            )
            if existing is not None:
                return GeofenceWaiverResult(
                    view=await self._build_view(connection, session),
                    created=False,
                )

            # affected_student_count: roster students who had not passed
            # geofence at the moment of the waiver (whether they had failed,
            # were still retrying, or had not started). Counted before the
            # waiver row exists, inside the same locked transaction.
            affected = await self._repository.count_students_without_geofence_pass(
                connection,
                session_id,
            )
            performed_at = self._as_utc(self._clock())
            override_id = await self._repository.insert_override(
                connection,
                session_id=session_id,
                factor=RequiredStep.GEOFENCE,
                reason_code=code,
                reason_text=text,
                performed_by=user_id,
                performed_at=performed_at,
                affected_student_count=affected,
            )
            if override_id is None:
                return GeofenceWaiverResult(
                    view=await self._build_view(connection, session),
                    created=False,
                )

            reopened = await self._repository.reopen_attempts_failed_by_geofence(
                connection,
                session_id,
                REOPENABLE_GEOFENCE_FAILURES,
            )

            await write_audit_log(
                connection,
                actor_user_id=user_id,
                actor_type=ACTOR_TYPE_LECTURER,
                action=AUDIT_ACTION,
                entity_type=AUDIT_ENTITY_TYPE,
                entity_id=session_id,
                old_values={"geofence": StepRequirement.REQUIRED.value},
                new_values={"geofence": StepRequirement.WAIVED.value},
                metadata={
                    "overrideId": str(override_id),
                    "sessionId": str(session_id),
                    "verificationFactor": RequiredStep.GEOFENCE.value,
                    "scope": OverrideScope.SESSION.value,
                    "previousPolicy": StepRequirement.REQUIRED.value,
                    "newPolicy": StepRequirement.WAIVED.value,
                    "reasonCode": code.value,
                    "reasonText": text,
                    "performedAt": performed_at.isoformat(),
                    "affectedStudentCount": affected,
                    # Attempts put back in progress. Their geofence readings
                    # were not changed; this records the process-state change.
                    "reopenedAttempts": [
                        {
                            "verificationAttemptId": str(item.verification_attempt_id),
                            "studentId": str(item.student_id),
                            "previousFailureReason": item.previous_failure_reason,
                        }
                        for item in reopened
                    ],
                },
            )

            view = await self._build_view(connection, session)

        return GeofenceWaiverResult(
            view=view,
            created=True,
            reopened_attempt_count=len(reopened),
        )

    async def _build_view(
        self,
        connection: asyncpg.Connection,
        session: OverrideSessionRecord,
    ) -> SessionVerificationPolicyView:
        waiver = await self._repository.find_override(
            connection,
            session.id,
            RequiredStep.GEOFENCE,
        )
        attempted, passed = await self._repository.geofence_counts(connection, session.id)
        return SessionVerificationPolicyView(
            session_id=session.id,
            policy=EffectiveVerificationPolicy.resolve(
                requires_geofence=session.requires_geofence,
                requires_face_verification=session.requires_face_verification,
                waived_steps=(
                    frozenset({RequiredStep.GEOFENCE}) if waiver is not None else frozenset()
                ),
            ),
            geofence_waiver=waiver,
            geofence_health=GeofenceHealth(
                attempted=attempted,
                passed=passed,
                minimum_attempts=self._warning_min_attempts,
                warning_failure_rate=self._warning_failure_rate,
            ),
        )

    async def _resolve_active_lecturer_id(
        self,
        connection: asyncpg.Connection,
        user_id: UUID,
    ) -> UUID:
        profile = await self._lecturer_profile_repository.find_by_user_id(connection, user_id)
        if profile is None or profile.profile_status != ACTIVE_PROFILE_STATUS:
            raise LecturerProfileNotFoundError("No active lecturer profile exists for this account.")
        return profile.id

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("clock must include a timezone")
        return value.astimezone(UTC)


__all__ = [
    "GeofenceWaiverResult",
    "SessionOverrideService",
    "SessionVerificationPolicyView",
]
