"""The activation-time check-in window recompute, expressed without a database.

A session's check-in window is set once at creation from `scheduled_start_at`,
before anyone knows when the lecturer will actually activate it. A lecturer who
activates late opens a window that may have already closed; one who activates
early must not have the window open before the lecture is due to begin. Fixing
that is a display-and-fairness rule, not a database concern, so it lives here,
pure, and the service layer supplies the session's current values and calls it
inside the activation transaction.

A field the lecturer explicitly supplied at session creation is their own
decision and is never touched here, no matter when activation happens. Only a
field the request left for the active policy to fill in moves with activation
timing — see `resolve_check_in_window_on_activation`.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

from modules.contracts.attendance_policy import AttendancePolicy

# Mirrors LecturerSessionService.DEFAULT_LATE_AFTER_MINUTES: the fallback used
# when no attendance policy is configured. Kept as a separate constant here
# rather than imported, so this module stays free of any dependency on the
# service module it is called from.
DEFAULT_LATE_AFTER_MINUTES = 10


@dataclass(frozen=True, slots=True)
class CheckInWindow:
    """A session's three check-in timestamps, as currently stored or as
    resolved by this module — the same shape either way."""

    check_in_opens_at: datetime
    check_in_closes_at: datetime
    late_after_at: datetime


@dataclass(frozen=True, slots=True)
class ExplicitCheckInFields:
    """Which of a session's check-in times were explicitly supplied when the
    session was created, rather than derived from the active policy.

    A field the request never named is free to move when activation turns out
    to be early or late — the lecturer left the decision to the policy in
    force at the time. A field the request did name is the lecturer's own
    decision, made deliberately, and activation timing is never grounds to
    override it.
    """

    check_in_opens_at: bool = False
    check_in_closes_at: bool = False
    late_after_at: bool = False

    @property
    def all_explicit(self) -> bool:
        return (
            self.check_in_opens_at
            and self.check_in_closes_at
            and self.late_after_at
        )


def resolve_effective_start(
    *,
    scheduled_start_at: datetime,
    activated_at: datetime,
) -> datetime:
    """When the lecture effectively began, for timing purposes.

    A lecturer activating late must not leave students facing a check-in
    window that already closed before they had a chance to use it. A lecturer
    activating early must not open the window before the lecture is scheduled
    to start — the lecture is not "in progress" yet just because the button
    was pressed.
    """
    return max(scheduled_start_at, activated_at)


def resolve_check_in_window_on_activation(
    *,
    scheduled_start_at: datetime,
    scheduled_end_at: datetime,
    activated_at: datetime,
    policy: AttendancePolicy | None,
    current: CheckInWindow,
    explicit: ExplicitCheckInFields,
) -> CheckInWindow:
    """Recomputes only the check-in times the lecturer left for the active
    policy to decide, anchored to when the session actually started rather
    than when it was scheduled to.

    Every resulting time is bounded by `scheduled_end_at`: a very late
    activation can shrink the window to nothing, but it can never invent
    minutes the lecture does not have. The close time is clamped there
    directly; the late threshold is then clamped to whichever close time this
    call resolves to, so it can never land after check-in has already closed.

    An explicit field is returned exactly as stored — untouched, unclamped —
    because it was the lecturer's own decision and this function's job is to
    fix the fields nobody decided, not to re-validate the ones somebody did.
    """

    effective_start = resolve_effective_start(
        scheduled_start_at=scheduled_start_at,
        activated_at=activated_at,
    )

    if explicit.check_in_opens_at:
        check_in_opens_at = current.check_in_opens_at
    else:
        check_in_opens_at = min(effective_start, scheduled_end_at)

    if explicit.check_in_closes_at:
        check_in_closes_at = current.check_in_closes_at
    elif policy is not None:
        check_in_closes_at = min(
            effective_start + timedelta(minutes=policy.check_in_window_minutes),
            scheduled_end_at,
        )
    else:
        check_in_closes_at = scheduled_end_at

    if explicit.late_after_at:
        late_after_at = current.late_after_at
    elif policy is not None:
        late_after_at = min(
            effective_start + timedelta(minutes=policy.late_threshold_minutes),
            check_in_closes_at,
        )
    else:
        late_after_at = min(
            effective_start + timedelta(minutes=DEFAULT_LATE_AFTER_MINUTES),
            check_in_closes_at,
        )

    return CheckInWindow(
        check_in_opens_at=check_in_opens_at,
        check_in_closes_at=check_in_closes_at,
        late_after_at=late_after_at,
    )


__all__ = [
    "CheckInWindow",
    "DEFAULT_LATE_AFTER_MINUTES",
    "ExplicitCheckInFields",
    "resolve_check_in_window_on_activation",
    "resolve_effective_start",
]
