from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from modules.attendance_verification.attendance_state import (
    FinalAttendanceStatus,
    InitialCheckInStatus,
)
from modules.attendance_verification.check_in.domain import CheckInOutcome, CheckInResult

LEGACY_STATUS_BY_OUTCOME = {
    CheckInOutcome.CHECKED_IN: "completed",
    CheckInOutcome.PENDING: "incomplete",
    CheckInOutcome.FAILED: "failed",
}

# The old clients only understand present/late, so the initial check-in is
# reported in their vocabulary. It is a translation for display, not a final
# attendance result: no attendance record exists until the session closes.
LEGACY_ATTENDANCE_STATUS_BY_CHECK_IN = {
    InitialCheckInStatus.CHECKED_IN: FinalAttendanceStatus.PRESENT.value,
    InitialCheckInStatus.LATE_CHECKED_IN: FinalAttendanceStatus.LATE.value,
}


class CompleteCheckInResponse(BaseModel):
    """The response shape the shipped mobile build already parses.

    It insists on ``status == "completed"`` together with an ``attendanceStatus``
    of ``present`` or ``late`` and a non-empty ``checkedInAt``, so all three are
    filled from the initial check-in.
    """

    model_config = ConfigDict(populate_by_name=True)

    status: str
    attendance_status: str | None = Field(alias="attendanceStatus")
    missing_requirements: list[str] = Field(alias="missingRequirements")
    checked_in_at: datetime | None = Field(alias="checkedInAt")

    @staticmethod
    def from_check_in(result: CheckInResult) -> "CompleteCheckInResponse":
        initial_check_in = result.initial_check_in
        return CompleteCheckInResponse(
            status=LEGACY_STATUS_BY_OUTCOME[result.outcome],
            attendance_status=(
                LEGACY_ATTENDANCE_STATUS_BY_CHECK_IN[initial_check_in.status]
                if initial_check_in is not None
                else None
            ),
            missing_requirements=result.missing_step_names,
            checked_in_at=initial_check_in.checked_in_at if initial_check_in else None,
        )


__all__ = ["CompleteCheckInResponse"]
