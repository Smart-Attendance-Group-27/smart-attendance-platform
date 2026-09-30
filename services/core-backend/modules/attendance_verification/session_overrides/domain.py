"""Session-wide verification overrides, expressed without a database."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from modules.attendance_verification.check_in.domain import RequiredStep, StepRequirement
from modules.attendance_verification.geofence.types import GeofenceReason


class OverrideScope(StrEnum):
    SESSION = "session"


class GeofenceWaiverReason(StrEnum):
    GPS_UNAVAILABLE = "GPS_UNAVAILABLE"
    GPS_INACCURATE = "GPS_INACCURATE"
    WRONG_SESSION_LOCATION = "WRONG_SESSION_LOCATION"
    DEVICE_LOCATION_FAILURE = "DEVICE_LOCATION_FAILURE"
    OTHER = "OTHER"


# Attempts that failed only because of the location check are reopened by a
# geofence waiver so the student can continue to face verification. A mock
# location is evidence of tampering rather than a GPS problem, so those stay
# failed and remain in manual review.
REOPENABLE_GEOFENCE_FAILURES: frozenset[str] = frozenset(
    {
        GeofenceReason.OUTSIDE_GEOFENCE.value,
        # Poor accuracy, stale or boundary readings end here after the last retry.
        GeofenceReason.ATTEMPT_LIMIT_REACHED.value,
    },
)


@dataclass(frozen=True)
class SessionVerificationOverride:
    """One recorded waiver. The row itself is the source of truth."""

    id: UUID
    session_id: UUID
    verification_factor: RequiredStep
    scope: OverrideScope
    previous_policy: StepRequirement
    new_policy: StepRequirement
    reason_code: GeofenceWaiverReason
    reason_text: str | None
    performed_by: UUID
    performed_by_name: str | None
    performed_at: datetime
    affected_student_count: int


@dataclass(frozen=True)
class GeofenceHealth:
    """How the location check is going across the whole session.

    Counted per student, not per reading: ``attempted`` is every student who
    submitted at least one location, ``passed`` those with at least one passing
    reading, and ``failed`` the rest of ``attempted`` (still retrying or
    stopped). A student who retried five times still counts once.
    """

    attempted: int
    passed: int
    minimum_attempts: int
    warning_failure_rate: float

    @property
    def failed(self) -> int:
        return max(self.attempted - self.passed, 0)

    @property
    def failure_rate(self) -> float:
        return self.failed / self.attempted if self.attempted else 0.0

    @property
    def warning(self) -> bool:
        """True when enough students tried and most of them could not pass.

        Only ever a prompt for the lecturer; nothing is waived automatically.
        """
        return (
            self.attempted >= self.minimum_attempts
            and self.failure_rate >= self.warning_failure_rate
        )


def clean_waiver_reason(
    reason_code: str,
    reason_text: str | None,
) -> tuple[GeofenceWaiverReason, str | None]:
    """Validates a waiver reason. OTHER needs a description; others may add a note."""

    code = GeofenceWaiverReason(reason_code)
    text = (reason_text or "").strip() or None
    if code is GeofenceWaiverReason.OTHER and text is None:
        raise ValueError("A description is required when the reason is OTHER.")
    return code, text


__all__ = [
    "REOPENABLE_GEOFENCE_FAILURES",
    "GeofenceHealth",
    "GeofenceWaiverReason",
    "OverrideScope",
    "SessionVerificationOverride",
    "clean_waiver_reason",
]
