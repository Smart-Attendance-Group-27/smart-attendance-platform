from datetime import time
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from modules.academic.admin_academic_data.repository import (
    AdminCourseOfferingRecord,
    AdminCourseRecord,
    AdminEnrolmentRecord,
    AdminTimetableEntryRecord,
)
from modules.academic.admin_academic_data.service import AcademicData


class AdminCourseResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    course_id: UUID = Field(alias="courseId")
    course_code: str = Field(alias="courseCode")
    course_name: str = Field(alias="courseName")
    department: str | None = Field(alias="department")
    credits: float | None
    status: str = Field(alias="status")

    @staticmethod
    def from_record(record: AdminCourseRecord) -> "AdminCourseResponse":
        return AdminCourseResponse(
            course_id=record.id,
            course_code=record.course_code or "",
            course_name=record.course_name or "",
            department=record.department_name,
            credits=float(record.credits) if record.credits is not None else None,
            status=record.status or "",
        )


class AdminCourseOfferingResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    offering_id: UUID = Field(alias="offeringId")
    course_code: str = Field(alias="courseCode")
    course_name: str = Field(alias="courseName")
    semester_label: str = Field(alias="semesterLabel")
    batch_year: int | None = Field(alias="batchYear")
    course_type: str | None = Field(alias="courseType")
    attendance_threshold_percent: float | None = Field(alias="attendanceThresholdPercent")
    enrolled_count: int = Field(alias="enrolledCount")
    status: str = Field(alias="status")

    @staticmethod
    def from_record(record: AdminCourseOfferingRecord) -> "AdminCourseOfferingResponse":
        return AdminCourseOfferingResponse(
            offering_id=record.id,
            course_code=record.course_code or "",
            course_name=record.course_name or "",
            semester_label=record.semester_label,
            batch_year=record.batch_year,
            course_type=record.course_type,
            attendance_threshold_percent=(
                float(record.attendance_threshold_percent)
                if record.attendance_threshold_percent is not None
                else None
            ),
            enrolled_count=record.enrolled_count,
            status=record.status or "",
        )


class AdminTimetableEntryResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: UUID
    course_code: str = Field(alias="courseCode")
    course_name: str = Field(alias="courseName")
    day_of_week: int = Field(alias="dayOfWeek")
    start_time: time = Field(alias="startTime")
    end_time: time = Field(alias="endTime")
    classroom_code: str | None = Field(alias="classroomCode")
    lecturer_name: str | None = Field(alias="lecturerName")

    @staticmethod
    def from_record(record: AdminTimetableEntryRecord) -> "AdminTimetableEntryResponse":
        return AdminTimetableEntryResponse(
            id=record.id,
            course_code=record.course_code or "",
            course_name=record.course_name or "",
            day_of_week=record.day_of_week,
            start_time=record.start_time,
            end_time=record.end_time,
            classroom_code=record.classroom_code,
            lecturer_name=record.lecturer_name,
        )


class AdminEnrolmentResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    enrolment_id: UUID = Field(alias="enrolmentId")
    student_name: str = Field(alias="studentName")
    registration_number: str = Field(alias="registrationNumber")
    course_code: str = Field(alias="courseCode")
    semester_label: str = Field(alias="semesterLabel")
    enrolment_status: str = Field(alias="enrolmentStatus")

    @staticmethod
    def from_record(record: AdminEnrolmentRecord) -> "AdminEnrolmentResponse":
        return AdminEnrolmentResponse(
            enrolment_id=record.id,
            student_name=record.student_name,
            registration_number=record.registration_number or "",
            course_code=record.course_code or "",
            semester_label=record.semester_label,
            enrolment_status=record.enrolment_status or "",
        )


class AdminAcademicDataResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    source_connection_status: str = Field(alias="sourceConnectionStatus")
    courses: list[AdminCourseResponse]
    offerings: list[AdminCourseOfferingResponse]
    timetable: list[AdminTimetableEntryResponse]
    enrolments: list[AdminEnrolmentResponse]

    @staticmethod
    def from_data(data: AcademicData) -> "AdminAcademicDataResponse":
        return AdminAcademicDataResponse(
            source_connection_status=data.source_connection_status,
            courses=[AdminCourseResponse.from_record(c) for c in data.courses],
            offerings=[AdminCourseOfferingResponse.from_record(o) for o in data.offerings],
            timetable=[AdminTimetableEntryResponse.from_record(t) for t in data.timetable],
            enrolments=[AdminEnrolmentResponse.from_record(e) for e in data.enrolments],
        )
