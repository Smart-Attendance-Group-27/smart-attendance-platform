from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from modules.attendance_verification.attendance_state import (
    AttendanceRecordSource,
    FinalAttendanceStatus,
)
from modules.attendance_verification.manual_attendance.service import ManualAttendanceResult

ManualReason = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=3, max_length=500),
]


class SetManualAttendanceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: FinalAttendanceStatus
    reason: ManualReason


class ManualAttendanceResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    session_id: UUID = Field(alias="sessionId")
    student_id: UUID = Field(alias="studentId")
    status: FinalAttendanceStatus
    source: AttendanceRecordSource
    reason: str
    recorded_by: UUID = Field(alias="recordedBy")
    updated_at: datetime = Field(alias="updatedAt")

    @staticmethod
    def from_result(result: ManualAttendanceResult) -> "ManualAttendanceResponse":
        return ManualAttendanceResponse(
            session_id=result.session_id,
            student_id=result.student_id,
            status=result.status,
            source=result.source,
            reason=result.reason,
            recorded_by=result.recorded_by,
            updated_at=result.updated_at,
        )
