from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

import asyncpg

from modules.academic.student_profile.exception import StudentProfileNotFoundError
from modules.academic.student_profile.repository import StudentProfileRepository
from modules.attendance_sessions.active_sessions.repository import (
    ActiveAttendanceSessionRecord,
    ActiveAttendanceSessionRepository,
)

ACTIVE_PROFILE_STATUS = "active"


class ActiveAttendanceSessionService:
    def __init__(
        self,
        repository: ActiveAttendanceSessionRepository | None = None,
        student_profile_repository: StudentProfileRepository | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository or ActiveAttendanceSessionRepository()
        self._student_profile_repository = (
            student_profile_repository or StudentProfileRepository()
        )
        self._clock = clock or self._utc_now

    async def list_for_user(
        self,
        pool: asyncpg.Pool,
        user_id: UUID,
    ) -> list[ActiveAttendanceSessionRecord]:
        current_time = self._as_utc(self._clock())

        async with pool.acquire() as connection:
            profile = await self._student_profile_repository.find_by_user_id(
                connection,
                user_id,
            )
            if profile is None or profile.profile_status != ACTIVE_PROFILE_STATUS:
                raise StudentProfileNotFoundError()

            return await self._repository.list_active_geofence_sessions_for_student(
                connection,
                profile.id,
                current_time,
            )

    @staticmethod
    def _utc_now() -> datetime:
        return datetime.now(UTC)

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("clock must include a timezone")
        return value.astimezone(UTC)
