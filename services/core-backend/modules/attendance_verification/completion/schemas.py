from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from modules.attendance_verification.completion.service import CompletionResult


class CompleteCheckInResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    status: str
    attendance_status: str | None = Field(alias="attendanceStatus")
    missing_requirements: list[str] = Field(alias="missingRequirements")
    checked_in_at: datetime | None = Field(alias="checkedInAt")

    @staticmethod
    def from_result(result: CompletionResult) -> "CompleteCheckInResponse":
        return CompleteCheckInResponse(
            status=result.status.value,
            attendance_status=result.attendance_status,
            missing_requirements=result.missing_requirements,
            checked_in_at=result.checked_in_at,
        )
