from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True, slots=True)
class StudentProfileReference:
    id: UUID
    registration_number: str
    profile_status: str | None


class StudentProfileRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_registration_number(self,registration_number: str,) -> StudentProfileReference | None:
        # The database has a unique index on registration_number
        statement = text(
            """
            SELECT id, registration_number, profile_status
            FROM academic.student_profiles
            WHERE registration_number = :registration_number
            """
        )
        result = await self._session.execute(statement,{"registration_number": registration_number},)
        row = result.mappings().one_or_none()

        if row is None:
            return None

        return StudentProfileReference(
            id=row["id"],
            registration_number=row["registration_number"],
            profile_status=row["profile_status"],
        )


__all__ = [
    "StudentProfileReference",
    "StudentProfileRepository",
]
