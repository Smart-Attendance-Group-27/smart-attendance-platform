from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class StudentCourseSessionResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: UUID
    title: str
    time_text: str = Field(alias="timeText")
    type: str
    status: str
    recorded_time: str | None = Field(alias="recordedTime")
    week_header: str = Field(alias="weekHeader")
    # Real instants, so clients never have to parse the display text.
    starts_at: datetime = Field(alias="startsAt")
    ends_at: datetime = Field(alias="endsAt")
    venue: str | None


class StudentCourseAttendanceRecordResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: UUID
    day: str
    month: str
    title: str
    recorded_text: str = Field(alias="recordedText")
    status: str


class StudentCourseResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: UUID
    code: str
    title: str
    lecturer: str
    semester: str
    attended_sessions: int = Field(alias="attendedSessions")
    total_sessions: int = Field(alias="totalSessions")
    # 0 while the course has no closed session; clients use totalSessions to
    # tell "no data yet" from a real 0%.
    attendance_percentage: int = Field(alias="attendancePercentage")
    attendance_threshold_percent: float | None = Field(alias="attendanceThresholdPercent")
    sessions: list[StudentCourseSessionResponse]
    attendance_records: list[StudentCourseAttendanceRecordResponse] = Field(
        alias="attendanceRecords",
    )
