from dataclasses import dataclass

import asyncpg

from modules.academic.admin_academic_data.repository import (
    AdminAcademicDataRepository,
    AdminCourseOfferingRecord,
    AdminCourseRecord,
    AdminEnrolmentRecord,
    AdminTimetableEntryRecord,
)

# No real LMS/SIS integration exists in this codebase — no sync job, no
# external credentials, nothing scheduled. academic.*.last_synced_at columns
# hold seed-time values only, so reporting anything other than
# "not_configured" here would misrepresent the system to an administrator.
SOURCE_CONNECTION_STATUS = "not_configured"


@dataclass(frozen=True)
class AcademicData:
    source_connection_status: str
    courses: list[AdminCourseRecord]
    offerings: list[AdminCourseOfferingRecord]
    timetable: list[AdminTimetableEntryRecord]
    enrolments: list[AdminEnrolmentRecord]


class AdminAcademicDataService:
    def __init__(self, repository: AdminAcademicDataRepository | None = None) -> None:
        self._repository = repository or AdminAcademicDataRepository()

    async def get_academic_data(self, pool: asyncpg.Pool) -> AcademicData:
        async with pool.acquire() as connection:
            courses = await self._repository.list_courses(connection)
            offerings = await self._repository.list_course_offerings(connection)
            timetable = await self._repository.list_timetable(connection)
            enrolments = await self._repository.list_enrolments(connection)

        return AcademicData(
            source_connection_status=SOURCE_CONNECTION_STATUS,
            courses=courses,
            offerings=offerings,
            timetable=timetable,
            enrolments=enrolments,
        )
