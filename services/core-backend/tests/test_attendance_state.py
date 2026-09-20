"""The attendance vocabulary is a frozen cross-member contract.

These tests exist so that renaming a value fails here first, instead of silently
disagreeing with a database CHECK constraint or another member's module.
"""

from modules.attendance_verification.attendance_state import (
    AttendanceRecordSource,
    FinalAttendanceStatus,
    InitialCheckInStatus,
    VerificationAttemptStatus,
)


def test_verification_attempt_status_values_are_frozen():
    assert [status.value for status in VerificationAttemptStatus] == [
        "in_progress",
        "checked_in",
        "failed",
    ]


def test_initial_check_in_status_values_are_frozen():
    assert [status.value for status in InitialCheckInStatus] == [
        "checked_in",
        "late_checked_in",
    ]


def test_final_attendance_status_values_are_frozen():
    assert [status.value for status in FinalAttendanceStatus] == [
        "present",
        "late",
        "absent",
    ]


def test_attendance_record_source_values_are_frozen():
    assert [source.value for source in AttendanceRecordSource] == [
        "automatic",
        "manual",
    ]


def test_there_is_no_finalized_verification_status():
    # Session close must not overwrite verification history, so the process
    # vocabulary deliberately has no terminal "finalized" value.
    assert "finalized" not in {status.value for status in VerificationAttemptStatus}


def test_statuses_compare_as_plain_strings():
    # Repositories bind these straight into SQL parameters, so the enum members
    # have to behave like the stored text.
    assert VerificationAttemptStatus.CHECKED_IN == "checked_in"
    assert InitialCheckInStatus.LATE_CHECKED_IN == "late_checked_in"
    assert FinalAttendanceStatus.ABSENT == "absent"
    assert AttendanceRecordSource.MANUAL == "manual"
