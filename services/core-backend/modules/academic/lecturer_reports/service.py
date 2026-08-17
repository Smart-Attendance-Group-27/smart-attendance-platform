from uuid import UUID

import asyncpg

from modules.academic.lecturer_profile.exception import LecturerProfileNotFoundError
from modules.academic.lecturer_profile.repository import LecturerProfileRepository
from modules.academic.lecturer_reports.exception import CourseOfferingNotFoundError
from modules.academic.lecturer_reports.repository import (
    CourseSessionReportRecord,
    LecturerOverviewRecord,
    LecturerReportRepository,
)

ACTIVE_PROFILE_STATUS = "active"


class LecturerReportService:
    def __init__(
        self,
        repository: LecturerReportRepository | None = None,
        lecturer_profile_repository: LecturerProfileRepository | None = None,
    ) -> None:
        self._repository = repository or LecturerReportRepository()
        self._lecturer_profile_repository = (
            lecturer_profile_repository or LecturerProfileRepository()
        )

    async def get_overview_for_user(
        self,
        pool: asyncpg.Pool,
        user_id: UUID,
    ) -> LecturerOverviewRecord:
        async with pool.acquire() as connection:
            lecturer_id = await self._resolve_active_lecturer_id(connection, user_id)
            return await self._repository.get_overview_for_lecturer(connection, lecturer_id)

    async def get_course_session_report_for_user(
        self,
        pool: asyncpg.Pool,
        user_id: UUID,
        course_offering_id: UUID,
    ) -> list[CourseSessionReportRecord]:
        async with pool.acquire() as connection:
            lecturer_id = await self._resolve_active_lecturer_id(connection, user_id)
            owns_course = await self._repository.lecturer_owns_course_offering(
                connection,
                lecturer_id,
                course_offering_id,
            )
            if not owns_course:
                raise CourseOfferingNotFoundError()

            return await self._repository.list_session_report_for_course(
                connection,
                course_offering_id,
            )

    async def _resolve_active_lecturer_id(
        self,
        connection: asyncpg.Connection,
        user_id: UUID,
    ) -> UUID:
        profile = await self._lecturer_profile_repository.find_by_user_id(connection, user_id)
        if profile is None or profile.profile_status != ACTIVE_PROFILE_STATUS:
            raise LecturerProfileNotFoundError("No active lecturer profile exists for this account.")
        return profile.id
