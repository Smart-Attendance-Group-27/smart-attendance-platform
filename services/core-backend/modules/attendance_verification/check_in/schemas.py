from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from modules.attendance_verification.check_in.domain import CheckInResult, InitialCheckIn


class InitialCheckInPayload(BaseModel):
    """The stored initial check-in. Not an attendance result.

    ``status`` is ``checked_in`` or ``late_checked_in``. Clients that want the
    final present/late/absent outcome read the attendance record, which only
    exists once the lecturer closes the session.
    """

    model_config = ConfigDict(populate_by_name=True)

    status: str
    checked_in_at: datetime = Field(alias="checkedInAt")

    @staticmethod
    def from_domain(initial_check_in: InitialCheckIn) -> "InitialCheckInPayload":
        return InitialCheckInPayload(
            status=initial_check_in.status.value,
            checked_in_at=initial_check_in.checked_in_at,
        )


class CheckInResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    status: str
    verification_attempt_id: UUID = Field(alias="verificationAttemptId")
    initial_check_in: InitialCheckInPayload | None = Field(alias="initialCheckIn")
    missing_requirements: list[str] = Field(alias="missingRequirements")

    @staticmethod
    def from_result(result: CheckInResult) -> "CheckInResponse":
        return CheckInResponse(
            status=result.outcome.value,
            verification_attempt_id=result.verification_attempt_id,
            initial_check_in=(
                InitialCheckInPayload.from_domain(result.initial_check_in)
                if result.initial_check_in is not None
                else None
            ),
            missing_requirements=result.missing_step_names,
        )


__all__ = ["CheckInResponse", "InitialCheckInPayload"]
