from datetime import datetime, time
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from modules.academic.admin_correction_requests.repository import AdminCorrectionRequestRecord


class ReviewDecision(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"
    RESOLVED = "resolved"


class DecideCorrectionRequestBody(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    decision: ReviewDecision
    note: str = Field(default="", max_length=1000)


class AdminCorrectionRequestResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: UUID
    request_type: str = Field(alias="requestType")
    category: str
    requester_name: str = Field(alias="requesterName")
    requester_employee_number: str | None = Field(alias="requesterEmployeeNumber")
    course_code: str | None = Field(alias="courseCode")
    course_name: str | None = Field(alias="courseName")
    timetable_day_of_week: int | None = Field(alias="timetableDayOfWeek")
    timetable_start_time: time | None = Field(alias="timetableStartTime")
    timetable_end_time: time | None = Field(alias="timetableEndTime")
    timetable_classroom_code: str | None = Field(alias="timetableClassroomCode")
    description: str
    status: str
    review_note: str | None = Field(alias="reviewNote")
    created_at: datetime = Field(alias="createdAt")
    reviewed_at: datetime | None = Field(alias="reviewedAt")

    @classmethod
    def from_record(cls, record: AdminCorrectionRequestRecord) -> "AdminCorrectionRequestResponse":
        return cls(
            id=record.id,
            request_type=record.request_type,
            category=record.category,
            requester_name=record.requester_name,
            requester_employee_number=record.requester_employee_number,
            course_code=record.course_code,
            course_name=record.course_name,
            timetable_day_of_week=record.timetable_day_of_week,
            timetable_start_time=record.timetable_start_time,
            timetable_end_time=record.timetable_end_time,
            timetable_classroom_code=record.timetable_classroom_code,
            description=record.description,
            status=record.status,
            review_note=record.review_note,
            created_at=record.created_at,
            reviewed_at=record.reviewed_at,
        )
