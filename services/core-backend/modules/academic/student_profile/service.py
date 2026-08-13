from dataclasses import dataclass
from uuid import UUID

import asyncpg

from modules.academic.student_profile.exception import StudentProfileNotFoundError
from modules.academic.student_profile.repository import (
    StudentProfileRecord,
    StudentProfileRepository,
)

ACTIVE_PROFILE_STATUS = "active"


@dataclass(frozen=True)
class StudentProfile:
    id: UUID
    registration_number: str
    full_name: str
    university_email: str


class StudentProfileService:
    """Applies the rules for reading a student's own profile.

    A profile that is not active is reported as missing rather than returned,
    so a withdrawn or archived student cannot keep using the mobile app.
    """

    def __init__(self, repository: StudentProfileRepository | None = None) -> None:
        self._repository = repository or StudentProfileRepository()

    async def get_profile_for_user(
        self,
        pool: asyncpg.Pool,
        user_id: UUID,
    ) -> StudentProfile:
        async with pool.acquire() as connection:
            profile_record = await self._repository.find_by_user_id(connection, user_id)

        if profile_record is None:
            raise StudentProfileNotFoundError(
                "No student profile exists for this account.",
            )

        if profile_record.profile_status != ACTIVE_PROFILE_STATUS:
            raise StudentProfileNotFoundError(
                "No active student profile exists for this account.",
            )

        return StudentProfile(
            id=profile_record.id,
            registration_number=profile_record.registration_number or "",
            full_name=self._compose_full_name(profile_record),
            university_email=profile_record.university_email or "",
        )

    @staticmethod
    def _compose_full_name(profile_record: StudentProfileRecord) -> str:
        name_parts = (
            profile_record.first_name,
            profile_record.middle_name,
            profile_record.last_name,
        )

        return " ".join(part.strip() for part in name_parts if part and part.strip())
