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
    attendance_percentage: int = Field(alias="attendancePercentage")
    sessions: list[StudentCourseSessionResponse]
    attendance_records: list[StudentCourseAttendanceRecordResponse] = Field(
        alias="attendanceRecords",
    )
