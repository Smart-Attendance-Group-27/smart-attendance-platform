from dataclasses import dataclass

import asyncpg

from modules.academic.admin_institution_reports.repository import (
    AdminInstitutionReportRepository,
    AtRiskCourseRecord,
    FacultyAttendanceRecord,
    InstitutionSummaryRecord,
    WeeklyTrendRecord,
)


@dataclass(frozen=True)
class InstitutionReports:
    summary: InstitutionSummaryRecord
    attendance_trend: list[WeeklyTrendRecord]
    attendance_by_faculty: list[FacultyAttendanceRecord]
    at_risk_courses: list[AtRiskCourseRecord]


class AdminInstitutionReportService:
    def __init__(self, repository: AdminInstitutionReportRepository | None = None) -> None:
        self._repository = repository or AdminInstitutionReportRepository()

    async def get_reports(self, pool: asyncpg.Pool) -> InstitutionReports:
        async with pool.acquire() as connection:
            summary = await self._repository.get_summary(connection)
            attendance_trend = await self._repository.list_attendance_trend(connection)
            attendance_by_faculty = await self._repository.list_attendance_by_faculty(connection)
            at_risk_courses = await self._repository.list_at_risk_courses(connection)

        return InstitutionReports(
            summary=summary,
            attendance_trend=attendance_trend,
            attendance_by_faculty=attendance_by_faculty,
            at_risk_courses=at_risk_courses,
        )
