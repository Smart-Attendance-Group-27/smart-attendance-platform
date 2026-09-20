from modules.attendance_verification.attendance_state import (
    FinalAttendanceStatus,
    InitialCheckInStatus,
)
from modules.attendance_verification.finalization.types import decide_final_attendance
from modules.contracts.qr_evidence import QrRequirementProgress


def test_a_student_who_never_checked_in_is_absent() -> None:
    status = decide_final_attendance(initial_check_in_status=None, qr_progress=None)

    assert status is FinalAttendanceStatus.ABSENT


def test_an_on_time_check_in_with_nothing_required_is_present() -> None:
    status = decide_final_attendance(
        initial_check_in_status=InitialCheckInStatus.CHECKED_IN,
        qr_progress=None,
    )

    assert status is FinalAttendanceStatus.PRESENT


def test_a_late_check_in_with_nothing_required_is_late() -> None:
    status = decide_final_attendance(
        initial_check_in_status=InitialCheckInStatus.LATE_CHECKED_IN,
        qr_progress=None,
    )

    assert status is FinalAttendanceStatus.LATE


def test_a_checked_in_student_who_satisfied_qr_is_present() -> None:
    status = decide_final_attendance(
        initial_check_in_status=InitialCheckInStatus.CHECKED_IN,
        qr_progress=QrRequirementProgress(required_count=2, passed_count=2),
    )

    assert status is FinalAttendanceStatus.PRESENT


def test_a_checked_in_student_who_did_not_satisfy_qr_is_absent() -> None:
    status = decide_final_attendance(
        initial_check_in_status=InitialCheckInStatus.CHECKED_IN,
        qr_progress=QrRequirementProgress(required_count=2, passed_count=1),
    )

    assert status is FinalAttendanceStatus.ABSENT


def test_qr_failure_overrides_an_on_time_check_in() -> None:
    """Checking in on time is not enough on its own if evidence during the
    lecture says the student did not stay."""

    status = decide_final_attendance(
        initial_check_in_status=InitialCheckInStatus.CHECKED_IN,
        qr_progress=QrRequirementProgress(required_count=1, passed_count=0),
    )

    assert status is FinalAttendanceStatus.ABSENT
