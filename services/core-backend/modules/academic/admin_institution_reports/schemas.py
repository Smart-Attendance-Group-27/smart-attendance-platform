from pydantic import BaseModel, ConfigDict, Field

from modules.academic.admin_institution_reports.repository import (
    AtRiskCourseRecord,
    FacultyAttendanceRecord,
    InstitutionSummaryRecord,
    WeeklyTrendRecord,
)
from modules.academic.admin_institution_reports.service import InstitutionReports


class InstitutionSummaryResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    overall_attendance_percent: float = Field(alias="overallAttendancePercent")
    total_sessions_completed: int = Field(alias="totalSessionsCompleted")
    total_students: int = Field(alias="totalStudents")
    total_lecturers: int = Field(alias="totalLecturers")
    students_at_risk_count: int = Field(alias="studentsAtRiskCount")

    @staticmethod
    def from_record(record: InstitutionSummaryRecord) -> "InstitutionSummaryResponse":
        return InstitutionSummaryResponse(
            overall_attendance_percent=(
                float(record.overall_attendance_percent)
                if record.overall_attendance_percent is not None
                else 0.0
            ),
            total_sessions_completed=record.total_sessions_completed,
            total_students=record.total_students,
            total_lecturers=record.total_lecturers,
            students_at_risk_count=record.students_at_risk_count,
        )


class WeeklyTrendPointResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    label: str
    attendance_rate: float = Field(alias="attendanceRate")

    @staticmethod
    def from_record(record: WeeklyTrendRecord) -> "WeeklyTrendPointResponse":
        # %-d (no leading zero) is a glibc extension, not portable to Windows —
        # build the label manually instead of relying on it.
        label = f"{record.week_start.strftime('%b')} {record.week_start.day}" if record.week_start else ""
        return WeeklyTrendPointResponse(
            label=label,
            attendance_rate=float(record.attendance_rate_percent),
        )


class FacultyAttendanceResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    faculty_name: str = Field(alias="facultyName")
    attendance_rate_percent: float = Field(alias="attendanceRatePercent")

    @staticmethod
    def from_record(record: FacultyAttendanceRecord) -> "FacultyAttendanceResponse":
        return FacultyAttendanceResponse(
            faculty_name=record.faculty_name,
            attendance_rate_percent=(
                float(record.attendance_rate_percent)
                if record.attendance_rate_percent is not None
                else 0.0
            ),
        )


class AtRiskCourseResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    course_code: str = Field(alias="courseCode")
    course_name: str = Field(alias="courseName")
    attendance_rate_percent: float = Field(alias="attendanceRatePercent")

    @staticmethod
    def from_record(record: AtRiskCourseRecord) -> "AtRiskCourseResponse":
        return AtRiskCourseResponse(
            course_code=record.course_code,
            course_name=record.course_name,
            attendance_rate_percent=float(record.attendance_rate_percent),
        )


class InstitutionReportsResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    summary: InstitutionSummaryResponse
    attendance_trend: list[WeeklyTrendPointResponse] = Field(alias="attendanceTrend")
    attendance_by_faculty: list[FacultyAttendanceResponse] = Field(alias="attendanceByFaculty")
    at_risk_courses: list[AtRiskCourseResponse] = Field(alias="atRiskCourses")

    @staticmethod
    def from_reports(reports: InstitutionReports) -> "InstitutionReportsResponse":
        return InstitutionReportsResponse(
            summary=InstitutionSummaryResponse.from_record(reports.summary),
            attendance_trend=[WeeklyTrendPointResponse.from_record(r) for r in reports.attendance_trend],
            attendance_by_faculty=[
                FacultyAttendanceResponse.from_record(r) for r in reports.attendance_by_faculty
            ],
            at_risk_courses=[AtRiskCourseResponse.from_record(r) for r in reports.at_risk_courses],
        )
