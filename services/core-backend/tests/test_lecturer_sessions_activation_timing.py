from datetime import UTC, datetime, timedelta

from modules.attendance_sessions.lecturer_sessions.activation_timing import (
    CheckInWindow,
    ExplicitCheckInFields,
    resolve_check_in_window_on_activation,
    resolve_effective_start,
)
from modules.contracts.attendance_policy import AttendancePolicy

SCHEDULED_START = datetime(2026, 9, 22, 9, 0, tzinfo=UTC)
SCHEDULED_END = datetime(2026, 9, 22, 10, 0, tzinfo=UTC)


def build_policy(window: int = 15, threshold: int = 10) -> AttendancePolicy:
    return AttendancePolicy(
        check_in_window_minutes=window,
        late_threshold_minutes=threshold,
        qr_default_validity_minutes=5,
    )


def build_current(
    *,
    opens: datetime = SCHEDULED_START,
    closes: datetime = SCHEDULED_START + timedelta(minutes=15),
    late: datetime = SCHEDULED_START + timedelta(minutes=10),
) -> CheckInWindow:
    return CheckInWindow(
        check_in_opens_at=opens,
        check_in_closes_at=closes,
        late_after_at=late,
    )


def resolve(
    *,
    activated_at: datetime,
    policy: AttendancePolicy | None = None,
    current: CheckInWindow | None = None,
    explicit: ExplicitCheckInFields | None = None,
    scheduled_start_at: datetime = SCHEDULED_START,
    scheduled_end_at: datetime = SCHEDULED_END,
) -> CheckInWindow:
    return resolve_check_in_window_on_activation(
        scheduled_start_at=scheduled_start_at,
        scheduled_end_at=scheduled_end_at,
        activated_at=activated_at,
        policy=policy,
        current=current or build_current(),
        explicit=explicit or ExplicitCheckInFields(),
    )


# --- resolve_effective_start -------------------------------------------------


def test_effective_start_is_the_scheduled_start_when_activation_is_early() -> None:
    activated_at = SCHEDULED_START - timedelta(minutes=26)

    assert (
        resolve_effective_start(
            scheduled_start_at=SCHEDULED_START,
            activated_at=activated_at,
        )
        == SCHEDULED_START
    )


def test_effective_start_is_the_activation_time_when_activation_is_late() -> None:
    activated_at = SCHEDULED_START + timedelta(minutes=20)

    assert (
        resolve_effective_start(
            scheduled_start_at=SCHEDULED_START,
            activated_at=activated_at,
        )
        == activated_at
    )


def test_effective_start_is_the_scheduled_start_when_activation_is_exactly_on_time() -> None:
    assert (
        resolve_effective_start(
            scheduled_start_at=SCHEDULED_START,
            activated_at=SCHEDULED_START,
        )
        == SCHEDULED_START
    )


# --- per-field: explicit fields are preserved --------------------------------


def test_an_explicit_opens_time_survives_a_late_activation_unchanged() -> None:
    explicit_opens = SCHEDULED_START - timedelta(minutes=5)
    late_activation = SCHEDULED_START + timedelta(minutes=20)

    window = resolve(
        activated_at=late_activation,
        policy=build_policy(),
        current=build_current(opens=explicit_opens),
        explicit=ExplicitCheckInFields(check_in_opens_at=True),
    )

    assert window.check_in_opens_at == explicit_opens


def test_an_explicit_closes_time_survives_a_late_activation_unchanged() -> None:
    explicit_closes = SCHEDULED_START + timedelta(minutes=8)
    late_activation = SCHEDULED_START + timedelta(minutes=20)

    window = resolve(
        activated_at=late_activation,
        policy=build_policy(),
        current=build_current(closes=explicit_closes),
        explicit=ExplicitCheckInFields(check_in_closes_at=True),
    )

    assert window.check_in_closes_at == explicit_closes


def test_an_explicit_late_time_survives_a_late_activation_unchanged() -> None:
    explicit_late = SCHEDULED_START + timedelta(minutes=12)
    late_activation = SCHEDULED_START + timedelta(minutes=20)

    window = resolve(
        activated_at=late_activation,
        policy=build_policy(),
        current=build_current(late=explicit_late),
        explicit=ExplicitCheckInFields(late_after_at=True),
    )

    assert window.late_after_at == explicit_late


# --- per-field: derived fields move with the effective start ----------------


def test_a_derived_opens_time_becomes_the_effective_start_on_late_activation() -> None:
    late_activation = SCHEDULED_START + timedelta(minutes=20)

    window = resolve(activated_at=late_activation, policy=build_policy())

    assert window.check_in_opens_at == late_activation


def test_a_derived_closes_time_follows_the_effective_start_clamped_at_the_scheduled_end() -> None:
    late_activation = SCHEDULED_START + timedelta(minutes=20)

    window = resolve(activated_at=late_activation, policy=build_policy(window=15))

    # effective_start + 15m = 09:35, well inside the 10:00 scheduled end.
    assert window.check_in_closes_at == late_activation + timedelta(minutes=15)


def test_a_derived_closes_time_is_clamped_at_the_scheduled_end() -> None:
    # Activating with only 10 minutes of lecture left: a 15-minute window
    # would run past scheduled_end_at without the clamp.
    late_activation = SCHEDULED_END - timedelta(minutes=10)

    window = resolve(activated_at=late_activation, policy=build_policy(window=15))

    assert window.check_in_closes_at == SCHEDULED_END


def test_a_derived_late_time_follows_the_effective_start() -> None:
    late_activation = SCHEDULED_START + timedelta(minutes=5)

    window = resolve(activated_at=late_activation, policy=build_policy(threshold=10))

    assert window.late_after_at == late_activation + timedelta(minutes=10)


def test_a_derived_late_time_is_clamped_at_the_resolved_closes_time() -> None:
    # A 30-minute late threshold against only a 15-minute window: the
    # threshold must never land after check-in has already closed.
    late_activation = SCHEDULED_START + timedelta(minutes=5)

    window = resolve(
        activated_at=late_activation,
        policy=build_policy(window=15, threshold=30),
    )

    assert window.late_after_at == window.check_in_closes_at


# --- mixed: only the derived fields move -------------------------------------


def test_one_explicit_field_survives_while_the_other_two_move() -> None:
    explicit_late = SCHEDULED_START + timedelta(minutes=45)
    late_activation = SCHEDULED_START + timedelta(minutes=20)

    window = resolve(
        activated_at=late_activation,
        policy=build_policy(window=15, threshold=5),
        current=build_current(late=explicit_late),
        explicit=ExplicitCheckInFields(late_after_at=True),
    )

    assert window.check_in_opens_at == late_activation
    assert window.check_in_closes_at == late_activation + timedelta(minutes=15)
    assert window.late_after_at == explicit_late


def test_all_three_fields_explicit_means_activation_changes_nothing() -> None:
    current = build_current(
        opens=SCHEDULED_START - timedelta(minutes=5),
        closes=SCHEDULED_START + timedelta(minutes=25),
        late=SCHEDULED_START + timedelta(minutes=15),
    )
    late_activation = SCHEDULED_START + timedelta(minutes=20)

    window = resolve(
        activated_at=late_activation,
        policy=build_policy(),
        current=current,
        explicit=ExplicitCheckInFields(
            check_in_opens_at=True,
            check_in_closes_at=True,
            late_after_at=True,
        ),
    )

    assert window == current


# --- early activation ---------------------------------------------------------


def test_early_activation_does_not_open_the_window_before_the_scheduled_start() -> None:
    early_activation = SCHEDULED_START - timedelta(minutes=26)

    window = resolve(activated_at=early_activation, policy=build_policy())

    assert window.check_in_opens_at == SCHEDULED_START


def test_early_activation_derives_closes_and_late_from_the_scheduled_start() -> None:
    early_activation = SCHEDULED_START - timedelta(minutes=26)

    window = resolve(
        activated_at=early_activation,
        policy=build_policy(window=15, threshold=10),
    )

    assert window.check_in_closes_at == SCHEDULED_START + timedelta(minutes=15)
    assert window.late_after_at == SCHEDULED_START + timedelta(minutes=10)


# --- no policy configured: documented fallback -------------------------------


def test_with_no_policy_a_derived_closes_time_falls_back_to_the_scheduled_end() -> None:
    late_activation = SCHEDULED_START + timedelta(minutes=20)

    window = resolve(activated_at=late_activation, policy=None)

    assert window.check_in_closes_at == SCHEDULED_END


def test_with_no_policy_a_derived_late_time_falls_back_to_the_built_in_default() -> None:
    late_activation = SCHEDULED_START + timedelta(minutes=5)

    window = resolve(activated_at=late_activation, policy=None)

    assert window.late_after_at == late_activation + timedelta(minutes=10)


def test_with_no_policy_the_late_fallback_is_still_clamped_at_the_scheduled_end() -> None:
    # Only 5 minutes of lecture left when activated; the 10-minute default
    # late threshold must not run past it.
    late_activation = SCHEDULED_END - timedelta(minutes=5)

    window = resolve(activated_at=late_activation, policy=None)

    assert window.late_after_at == SCHEDULED_END


# --- every result is bounded by scheduled_end_at ------------------------------


def test_every_derived_field_is_bounded_by_the_scheduled_end_even_on_extreme_late_activation() -> None:
    # Activated well after the lecture was scheduled to have finished.
    very_late_activation = SCHEDULED_END + timedelta(hours=2)

    window = resolve(activated_at=very_late_activation, policy=build_policy())

    assert window.check_in_opens_at <= SCHEDULED_END
    assert window.check_in_closes_at <= SCHEDULED_END
    assert window.late_after_at <= SCHEDULED_END


def test_every_derived_field_is_bounded_by_the_scheduled_end_with_no_policy() -> None:
    very_late_activation = SCHEDULED_END + timedelta(hours=2)

    window = resolve(activated_at=very_late_activation, policy=None)

    assert window.check_in_opens_at <= SCHEDULED_END
    assert window.check_in_closes_at <= SCHEDULED_END
    assert window.late_after_at <= SCHEDULED_END


# --- ExplicitCheckInFields.all_explicit ---------------------------------------


def test_all_explicit_is_false_when_any_field_is_derived() -> None:
    assert not ExplicitCheckInFields(
        check_in_opens_at=True,
        check_in_closes_at=True,
        late_after_at=False,
    ).all_explicit


def test_all_explicit_is_true_when_every_field_is_explicit() -> None:
    assert ExplicitCheckInFields(
        check_in_opens_at=True,
        check_in_closes_at=True,
        late_after_at=True,
    ).all_explicit


def test_all_explicit_is_false_by_default() -> None:
    assert not ExplicitCheckInFields().all_explicit
