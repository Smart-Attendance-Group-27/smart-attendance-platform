from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from modules.academic.lecturer_reports.repository import (
    AtRiskStudentRecord,
    CourseSessionReportRecord,
    LecturerOverviewRecord,
    WeeklyTrendRecord,
)


def derive_session_report_status(record: CourseSessionReportRecord) -> str:
    if record.cancelled_at is not None:
        return "cancelled"
    if record.closed_at is not None:
        return "closed"
    if record.activated_at is not None:
        return "active"
    return "scheduled"


class LecturerDashboardOverviewResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    active_course_count: int = Field(alias="activeCourseCount")
    upcoming_session_count: int = Field(alias="upcomingSessionCount")
    today_session_count: int = Field(alias="todaySessionCount")
    average_attendance_rate_percent: float | None = Field(alias="averageAttendanceRatePercent")
    pending_review_count: int = Field(alias="pendingReviewCount")

    @staticmethod
    def from_record(record: LecturerOverviewRecord) -> "LecturerDashboardOverviewResponse":
        return LecturerDashboardOverviewResponse(
            active_course_count=record.active_course_count,
            upcoming_session_count=record.upcoming_session_count,
            today_session_count=record.today_session_count,
            average_attendance_rate_percent=(
                float(record.average_attendance_rate_percent)
                if record.average_attendance_rate_percent is not None
                else None
            ),
            pending_review_count=record.pending_review_count,
        )


class CourseSessionReportResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    session_id: UUID = Field(alias="sessionId")
    scheduled_start_at: datetime = Field(alias="scheduledStartAt")
    status: str
    enrolled_count: int = Field(alias="enrolledCount")
    present_count: int = Field(alias="presentCount")
    late_count: int = Field(alias="lateCount")
    absent_count: int = Field(alias="absentCount")
    pending_review_count: int = Field(alias="pendingReviewCount")

    @staticmethod
    def from_record(record: CourseSessionReportRecord) -> "CourseSessionReportResponse":
        return CourseSessionReportResponse(
            session_id=record.session_id,
            scheduled_start_at=record.scheduled_start_at,
            status=derive_session_report_status(record),
            enrolled_count=record.enrolled_count,
            present_count=record.present_count,
            late_count=record.late_count,
            absent_count=record.absent_count,
            pending_review_count=record.pending_review_count,
        )


class WeeklyTrendPointResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    label: str
    attendance_rate: float = Field(alias="attendanceRate")

    @staticmethod
    def from_record(record: WeeklyTrendRecord) -> "WeeklyTrendPointResponse":
        label = f"{record.week_start.strftime('%b')} {record.week_start.day}" if record.week_start else ""
        return WeeklyTrendPointResponse(
            label=label,
            attendance_rate=float(record.attendance_rate_percent),
        )


class AtRiskStudentResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    student_id: UUID = Field(alias="studentId")
    registration_number: str = Field(alias="registrationNumber")
    full_name: str = Field(alias="fullName")
    course_code: str = Field(alias="courseCode")
    attendance_rate_percent: float = Field(alias="attendanceRatePercent")
    late_count: int = Field(alias="lateCount")
    last_attended_at: datetime | None = Field(alias="lastAttendedAt")

    @staticmethod
    def from_record(record: AtRiskStudentRecord) -> "AtRiskStudentResponse":
        return AtRiskStudentResponse(
            student_id=record.student_id,
            registration_number=record.registration_number or "",
            full_name=record.full_name,
            course_code=record.course_code,
            attendance_rate_percent=float(record.attendance_rate_percent),
            late_count=record.late_count,
            last_attended_at=record.last_attended_at,
        )
