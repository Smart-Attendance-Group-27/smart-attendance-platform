"""The check-in rule itself, with no database in sight.

These are the cases that decide whether a student is marked late, so they are
written as statements about people rather than about columns.
"""

from datetime import UTC, datetime, timedelta

from modules.attendance_verification.attendance_state import InitialCheckInStatus
from modules.attendance_verification.check_in.domain import (
    RequiredStep,
    StepEvidence,
    evaluate_initial_evidence,
    resolve_initial_check_in_status,
)

LECTURE_START = datetime(2026, 9, 21, 9, 0, tzinfo=UTC)
LATE_AFTER = LECTURE_START + timedelta(minutes=15)


def geofence_at(moment: datetime | None) -> StepEvidence:
    return StepEvidence(step=RequiredStep.GEOFENCE, passed_at=moment)


def face_at(moment: datetime | None) -> StepEvidence:
    return StepEvidence(step=RequiredStep.FACE, passed_at=moment)


def test_check_in_happens_when_the_last_required_step_passes() -> None:
    geofence_time = LECTURE_START + timedelta(minutes=2)
    face_time = LECTURE_START + timedelta(minutes=5)

    checked_in_at, missing = evaluate_initial_evidence(
        (geofence_at(geofence_time), face_at(face_time)),
        fallback_checked_in_at=LECTURE_START,
    )

    assert checked_in_at == face_time
    assert missing == ()


def test_the_order_the_steps_passed_in_does_not_matter() -> None:
    geofence_time = LECTURE_START + timedelta(minutes=6)
    face_time = LECTURE_START + timedelta(minutes=1)

    checked_in_at, _ = evaluate_initial_evidence(
        (geofence_at(geofence_time), face_at(face_time)),
        fallback_checked_in_at=LECTURE_START,
    )

    assert checked_in_at == geofence_time


def test_a_step_that_has_not_passed_is_reported_as_missing() -> None:
    checked_in_at, missing = evaluate_initial_evidence(
        (geofence_at(LECTURE_START), face_at(None)),
        fallback_checked_in_at=LECTURE_START,
    )

    assert checked_in_at is None
    assert missing == (RequiredStep.FACE,)


def test_every_missing_step_is_reported_not_just_the_first() -> None:
    _, missing = evaluate_initial_evidence(
        (geofence_at(None), face_at(None)),
        fallback_checked_in_at=LECTURE_START,
    )

    assert missing == (RequiredStep.GEOFENCE, RequiredStep.FACE)


def test_a_session_requiring_no_initial_step_falls_back_to_the_attempt_start() -> None:
    checked_in_at, missing = evaluate_initial_evidence(
        (),
        fallback_checked_in_at=LECTURE_START,
    )

    assert checked_in_at == LECTURE_START
    assert missing == ()


def test_a_check_in_before_the_threshold_is_on_time() -> None:
    status = resolve_initial_check_in_status(
        checked_in_at=LATE_AFTER - timedelta(seconds=1),
        late_after_at=LATE_AFTER,
    )

    assert status is InitialCheckInStatus.CHECKED_IN


def test_a_check_in_exactly_on_the_threshold_is_still_on_time() -> None:
    status = resolve_initial_check_in_status(
        checked_in_at=LATE_AFTER,
        late_after_at=LATE_AFTER,
    )

    assert status is InitialCheckInStatus.CHECKED_IN


def test_a_check_in_after_the_threshold_is_late() -> None:
    status = resolve_initial_check_in_status(
        checked_in_at=LATE_AFTER + timedelta(seconds=1),
        late_after_at=LATE_AFTER,
    )

    assert status is InitialCheckInStatus.LATE_CHECKED_IN


def test_a_session_with_no_threshold_never_marks_anyone_late() -> None:
    status = resolve_initial_check_in_status(
        checked_in_at=LECTURE_START + timedelta(hours=3),
        late_after_at=None,
    )

    assert status is InitialCheckInStatus.CHECKED_IN


def test_starting_late_but_finishing_on_time_is_not_late() -> None:
    """The bug the old rule had: it judged students by when they started.

    A student who opens the app at 09:14 and finishes verifying at 09:14:30 was
    in the room before the threshold and is on time.
    """

    finished_at = LATE_AFTER - timedelta(seconds=30)

    checked_in_at, _ = evaluate_initial_evidence(
        (geofence_at(finished_at),),
        fallback_checked_in_at=LECTURE_START,
    )
    status = resolve_initial_check_in_status(
        checked_in_at=checked_in_at,
        late_after_at=LATE_AFTER,
    )

    assert status is InitialCheckInStatus.CHECKED_IN


def test_starting_on_time_but_finishing_late_is_late() -> None:
    """The mirror image: starting early must not buy an on-time check-in."""

    checked_in_at, _ = evaluate_initial_evidence(
        (
            geofence_at(LECTURE_START),
            face_at(LATE_AFTER + timedelta(minutes=10)),
        ),
        fallback_checked_in_at=LECTURE_START,
    )
    status = resolve_initial_check_in_status(
        checked_in_at=checked_in_at,
        late_after_at=LATE_AFTER,
    )

    assert status is InitialCheckInStatus.LATE_CHECKED_IN
