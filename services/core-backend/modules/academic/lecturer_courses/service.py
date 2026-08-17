from uuid import UUID

import asyncpg

from modules.academic.lecturer_courses.repository import (
    LecturerCourseRecord,
    LecturerCourseRepository,
    LecturerTimetableEntryRecord,
)
from modules.academic.lecturer_profile.exception import LecturerProfileNotFoundError
from modules.academic.lecturer_profile.repository import LecturerProfileRepository

ACTIVE_PROFILE_STATUS = "active"


class LecturerCourseService:
    """Applies the rules for a lecturer reading their own assigned academic data.

    A profile that is not active is reported as missing rather than returned,
    matching StudentProfileService's equivalent rule.
    """

    def __init__(
        self,
        repository: LecturerCourseRepository | None = None,
        lecturer_profile_repository: LecturerProfileRepository | None = None,
    ) -> None:
        self._repository = repository or LecturerCourseRepository()
        self._lecturer_profile_repository = (
            lecturer_profile_repository or LecturerProfileRepository()
        )

    async def list_courses_for_user(
        self,
        pool: asyncpg.Pool,
        user_id: UUID,
    ) -> list[LecturerCourseRecord]:
        async with pool.acquire() as connection:
            lecturer_id = await self._resolve_active_lecturer_id(connection, user_id)
            return await self._repository.list_courses_for_lecturer(connection, lecturer_id)

    async def list_timetable_for_user(
        self,
        pool: asyncpg.Pool,
        user_id: UUID,
    ) -> list[LecturerTimetableEntryRecord]:
        async with pool.acquire() as connection:
            lecturer_id = await self._resolve_active_lecturer_id(connection, user_id)
            return await self._repository.list_timetable_for_lecturer(connection, lecturer_id)

    async def _resolve_active_lecturer_id(
        self,
        connection: asyncpg.Connection,
        user_id: UUID,
    ) -> UUID:
        profile = await self._lecturer_profile_repository.find_by_user_id(connection, user_id)
        if profile is None or profile.profile_status != ACTIVE_PROFILE_STATUS:
            raise LecturerProfileNotFoundError("No active lecturer profile exists for this account.")
        return profile.id
