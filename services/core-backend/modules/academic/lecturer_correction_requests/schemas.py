from datetime import datetime, time
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CorrectionRequestType(StrEnum):
    COURSE_DATA = "course_data"
    TIMETABLE = "timetable"


class CorrectionCategory(StrEnum):
    COURSE_DETAILS = "course_details"
    ENROLMENT = "enrolment"
    LECTURER_ASSIGNMENT = "lecturer_assignment"
    TIMETABLE_DAY_TIME = "timetable_day_time"
    TIMETABLE_ROOM = "timetable_room"
    TIMETABLE_MISSING = "timetable_missing"
    OTHER = "other"


class CreateCorrectionRequestBody(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    request_type: CorrectionRequestType = Field(alias="requestType")
    category: CorrectionCategory
    course_offering_id: UUID | None = Field(default=None, alias="courseOfferingId")
    timetable_entry_id: UUID | None = Field(default=None, alias="timetableEntryId")
    description: str = Field(max_length=1000)


class CorrectionRequestResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: UUID
    request_type: str = Field(alias="requestType")
    category: str
    course_offering_id: UUID = Field(alias="courseOfferingId")
    timetable_entry_id: UUID | None = Field(alias="timetableEntryId")
    status: str


class OwnCorrectionRequestResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: UUID
    request_type: str = Field(alias="requestType")
    category: str
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
