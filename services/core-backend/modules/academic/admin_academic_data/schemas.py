from datetime import date, time
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from modules.academic.admin_academic_data.repository import (
    AcademicOptionRecord,
    AdminCourseOfferingRecord,
    AdminCourseRecord,
    AdminEnrolmentRecord,
    AdminTimetableEntryRecord,
)

AcademicStatus = Literal["active", "inactive"]


class AdminCourseResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    course_id: UUID = Field(alias="courseId")
    course_code: str = Field(alias="courseCode")
    course_name: str = Field(alias="courseName")
    department_id: UUID | None = Field(alias="departmentId")
    department: str | None
    credits: float | None
    status: str

    @staticmethod
    def from_record(record: AdminCourseRecord) -> "AdminCourseResponse":
        return AdminCourseResponse(
            course_id=record.id,
            course_code=record.course_code or "",
            course_name=record.course_name or "",
            department_id=record.department_id,
            department=record.department_name,
            credits=float(record.credits) if record.credits is not None else None,
            status=record.status or "",
        )


class CourseWriteRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, str_strip_whitespace=True)

    course_code: str = Field(alias="courseCode", min_length=1, max_length=30)
    course_name: str = Field(alias="courseName", min_length=1, max_length=255)
    department_id: UUID = Field(alias="departmentId")
    credits: Decimal = Field(ge=0, le=60)
    status: AcademicStatus = "active"


class AdminCourseOfferingResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    offering_id: UUID = Field(alias="offeringId")
    course_id: UUID = Field(alias="courseId")
    semester_id: UUID = Field(alias="semesterId")
    lecturer_id: UUID | None = Field(alias="lecturerId")
    lecturer_name: str | None = Field(alias="lecturerName")
    course_code: str = Field(alias="courseCode")
    course_name: str = Field(alias="courseName")
    semester_label: str = Field(alias="semesterLabel")
    batch_year: int | None = Field(alias="batchYear")
    course_type: str | None = Field(alias="courseType")
    attendance_threshold_percent: float | None = Field(alias="attendanceThresholdPercent")
    enrolled_count: int = Field(alias="enrolledCount")
    status: str

    @staticmethod
    def from_record(record: AdminCourseOfferingRecord) -> "AdminCourseOfferingResponse":
        return AdminCourseOfferingResponse(
            offering_id=record.id,
            course_id=record.course_id,
            semester_id=record.semester_id,
            lecturer_id=record.lecturer_id,
            lecturer_name=record.lecturer_name,
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


class OfferingWriteRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, str_strip_whitespace=True)

    course_id: UUID = Field(alias="courseId")
    semester_id: UUID = Field(alias="semesterId")
    lecturer_id: UUID = Field(alias="lecturerId")
    batch_year: int = Field(alias="batchYear", ge=1900, le=2200)
    course_type: str = Field(alias="courseType", min_length=1, max_length=20)
    attendance_threshold_percent: Decimal = Field(
        alias="attendanceThresholdPercent", ge=0, le=100
    )
    status: AcademicStatus = "active"


class LecturerAssignmentRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    lecturer_id: UUID = Field(alias="lecturerId")


class AdminTimetableEntryResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: UUID
    course_offering_id: UUID = Field(alias="courseOfferingId")
    classroom_id: UUID | None = Field(alias="classroomId")
    course_code: str = Field(alias="courseCode")
    course_name: str = Field(alias="courseName")
    day_of_week: int = Field(alias="dayOfWeek")
    start_time: time = Field(alias="startTime")
    end_time: time = Field(alias="endTime")
    classroom_code: str | None = Field(alias="classroomCode")
    lecturer_name: str | None = Field(alias="lecturerName")
    course_type: str | None = Field(alias="courseType")
    valid_from: date = Field(alias="validFrom")
    valid_until: date | None = Field(alias="validUntil")
    status: str

    @staticmethod
    def from_record(record: AdminTimetableEntryRecord) -> "AdminTimetableEntryResponse":
        return AdminTimetableEntryResponse(
            id=record.id,
            course_offering_id=record.course_offering_id,
            classroom_id=record.classroom_id,
            course_code=record.course_code or "",
            course_name=record.course_name or "",
            day_of_week=record.day_of_week,
            start_time=record.start_time,
            end_time=record.end_time,
            classroom_code=record.classroom_code,
            lecturer_name=record.lecturer_name,
            course_type=record.course_type,
            valid_from=record.valid_from,
            valid_until=record.valid_until,
            status=record.status or "",
        )


class TimetableWriteRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, str_strip_whitespace=True)

    course_offering_id: UUID = Field(alias="courseOfferingId")
    classroom_id: UUID = Field(alias="classroomId")
    day_of_week: int = Field(alias="dayOfWeek", ge=1, le=7)
    start_time: time = Field(alias="startTime")
    end_time: time = Field(alias="endTime")
    course_type: str = Field(alias="courseType", min_length=1, max_length=20)
    valid_from: date = Field(alias="validFrom")
    valid_until: date | None = Field(default=None, alias="validUntil")
    status: AcademicStatus = "active"

    @model_validator(mode="after")
    def validate_times_and_dates(self) -> "TimetableWriteRequest":
        if self.end_time <= self.start_time:
            raise ValueError("endTime must be later than startTime")
        if self.valid_until is not None and self.valid_until < self.valid_from:
            raise ValueError("validUntil must not be earlier than validFrom")
        return self


class AdminEnrolmentResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    enrolment_id: UUID = Field(alias="enrolmentId")
    course_offering_id: UUID = Field(alias="courseOfferingId")
    student_id: UUID = Field(alias="studentId")
    student_name: str = Field(alias="studentName")
    registration_number: str = Field(alias="registrationNumber")
    course_code: str = Field(alias="courseCode")
    semester_label: str = Field(alias="semesterLabel")
    enrolment_status: str = Field(alias="enrolmentStatus")

    @staticmethod
    def from_record(record: AdminEnrolmentRecord) -> "AdminEnrolmentResponse":
        return AdminEnrolmentResponse(
            enrolment_id=record.id,
            course_offering_id=record.course_offering_id,
            student_id=record.student_id,
            student_name=record.student_name,
            registration_number=record.registration_number or "",
            course_code=record.course_code or "",
            semester_label=record.semester_label,
            enrolment_status=record.enrolment_status or "",
        )


class EnrolmentWriteRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    student_id: UUID = Field(alias="studentId")


class AcademicOptionResponse(BaseModel):
    id: UUID
    label: str

    @staticmethod
    def from_record(record: AcademicOptionRecord) -> "AcademicOptionResponse":
        return AcademicOptionResponse(id=record.id, label=record.label)


class AcademicReferenceDataResponse(BaseModel):
    departments: list[AcademicOptionResponse]
    semesters: list[AcademicOptionResponse]
    lecturers: list[AcademicOptionResponse]
    students: list[AcademicOptionResponse]
    classrooms: list[AcademicOptionResponse]


class AdminAcademicDataResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    source_connection_status: str = Field(alias="sourceConnectionStatus")
    courses: list[AdminCourseResponse]
    offerings: list[AdminCourseOfferingResponse]
    timetable: list[AdminTimetableEntryResponse]
    enrolments: list[AdminEnrolmentResponse]
