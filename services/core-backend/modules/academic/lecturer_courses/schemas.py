from datetime import time
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class LecturerCourseResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    course_offering_id: UUID = Field(alias="courseOfferingId")
    course_code: str = Field(alias="courseCode")
    course_name: str = Field(alias="courseName")
    department_name: str | None = Field(alias="departmentName")
    course_type: str | None = Field(alias="courseType")
    status: str = Field(alias="status")
    enrolled_count: int = Field(alias="enrolledCount")
    # Percentage of attendance_records marked present/late across every session
    # under this offering; null when no session has recorded attendance yet.
    attendance_rate_percent: float | None = Field(alias="attendanceRatePercent")


class LecturerTimetableEntryResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: UUID
    course_code: str = Field(alias="courseCode")
    course_name: str = Field(alias="courseName")
    # Raw academic.timetable_entries.day_of_week value (0-6) — the seed data's
    # own convention isn't documented, so this is passed through rather than
    # guessed at; map to a day name at the presentation layer once confirmed.
    day_of_week: int = Field(alias="dayOfWeek")
    start_time: time = Field(alias="startTime")
    end_time: time = Field(alias="endTime")
    classroom_code: str | None = Field(alias="classroomCode")
    building_name: str | None = Field(alias="buildingName")
