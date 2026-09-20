from datetime import UTC, datetime, timedelta

from modules.attendance_sessions.active_sessions.state_service import (
    SessionState,
    can_start_check_in,
    derive_session_state,
)

WINDOW_OPENS = datetime(2026, 9, 21, 9, 0, tzinfo=UTC)
WINDOW_CLOSES = WINDOW_OPENS + timedelta(minutes=30)


def test_a_cancelled_session_is_cancelled_even_if_it_was_also_closed() -> None:
    state = derive_session_state(
        status="active",
        closed_at=WINDOW_OPENS,
        cancelled_at=WINDOW_OPENS,
    )

    assert state is SessionState.CANCELLED


def test_a_closed_session_is_closed_even_though_status_stays_active() -> None:
    # status is never updated to 'closed' today; closed_at is the real signal.
    state = derive_session_state(
        status="active",
        closed_at=WINDOW_OPENS,
        cancelled_at=None,
    )

    assert state is SessionState.CLOSED


def test_an_active_session_with_no_closed_or_cancelled_at_is_active() -> None:
    state = derive_session_state(status="active", closed_at=None, cancelled_at=None)

    assert state is SessionState.ACTIVE


def test_anything_else_is_scheduled() -> None:
    state = derive_session_state(status="scheduled", closed_at=None, cancelled_at=None)

    assert state is SessionState.SCHEDULED


def test_check_in_can_start_inside_the_window() -> None:
    started = can_start_check_in(
        session_state=SessionState.ACTIVE,
        check_in_opens_at=WINDOW_OPENS,
        check_in_closes_at=WINDOW_CLOSES,
        now=WINDOW_OPENS + timedelta(minutes=5),
        attempt_status=None,
        has_final_attendance=False,
    )

    assert started is True


def test_check_in_cannot_start_before_the_window_opens() -> None:
    started = can_start_check_in(
        session_state=SessionState.ACTIVE,
        check_in_opens_at=WINDOW_OPENS,
        check_in_closes_at=WINDOW_CLOSES,
        now=WINDOW_OPENS - timedelta(minutes=1),
        attempt_status=None,
        has_final_attendance=False,
    )

    assert started is False


def test_check_in_cannot_start_after_the_window_closes() -> None:
    started = can_start_check_in(
        session_state=SessionState.ACTIVE,
        check_in_opens_at=WINDOW_OPENS,
        check_in_closes_at=WINDOW_CLOSES,
        now=WINDOW_CLOSES,
        attempt_status=None,
        has_final_attendance=False,
    )

    assert started is False


def test_check_in_cannot_start_once_already_checked_in() -> None:
    started = can_start_check_in(
        session_state=SessionState.ACTIVE,
        check_in_opens_at=WINDOW_OPENS,
        check_in_closes_at=WINDOW_CLOSES,
        now=WINDOW_OPENS + timedelta(minutes=5),
        attempt_status="checked_in",
        has_final_attendance=False,
    )

    assert started is False


def test_check_in_cannot_start_after_a_failed_attempt() -> None:
    started = can_start_check_in(
        session_state=SessionState.ACTIVE,
        check_in_opens_at=WINDOW_OPENS,
        check_in_closes_at=WINDOW_CLOSES,
        now=WINDOW_OPENS + timedelta(minutes=5),
        attempt_status="failed",
        has_final_attendance=False,
    )

    assert started is False


def test_check_in_cannot_start_once_a_final_record_exists() -> None:
    started = can_start_check_in(
        session_state=SessionState.ACTIVE,
        check_in_opens_at=WINDOW_OPENS,
        check_in_closes_at=WINDOW_CLOSES,
        now=WINDOW_OPENS + timedelta(minutes=5),
        attempt_status="in_progress",
        has_final_attendance=True,
    )

    assert started is False


def test_check_in_cannot_start_on_a_closed_session() -> None:
    started = can_start_check_in(
        session_state=SessionState.CLOSED,
        check_in_opens_at=WINDOW_OPENS,
        check_in_closes_at=WINDOW_CLOSES,
        now=WINDOW_OPENS + timedelta(minutes=5),
        attempt_status=None,
        has_final_attendance=False,
    )

    assert started is False


def test_check_in_cannot_start_without_a_window() -> None:
    started = can_start_check_in(
        session_state=SessionState.ACTIVE,
        check_in_opens_at=None,
        check_in_closes_at=None,
        now=WINDOW_OPENS,
        attempt_status=None,
        has_final_attendance=False,
    )

    assert started is False
