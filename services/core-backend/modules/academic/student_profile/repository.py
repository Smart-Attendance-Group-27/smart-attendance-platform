from dataclasses import dataclass
from uuid import UUID

import asyncpg


@dataclass(frozen=True)
class StudentProfileRecord:
    id: UUID
    user_id: UUID
    registration_number: str | None
    first_name: str | None
    middle_name: str | None
    last_name: str | None
    profile_status: str | None
    university_email: str | None


class StudentProfileRepository:
    """Reads student profiles. It never decides whether access is allowed."""

    async def find_by_user_id(
        self,
        connection: asyncpg.Connection,
        user_id: UUID,
    ) -> StudentProfileRecord | None:
        row = await connection.fetchrow(
            """
            SELECT
                profile.id,
                profile.user_id,
                profile.registration_number,
                profile.first_name,
                profile.middle_name,
                profile.last_name,
                profile.profile_status,
                app_user.email AS university_email
            FROM academic.student_profiles AS profile
            JOIN identity.users AS app_user
                ON app_user.id = profile.user_id
            WHERE profile.user_id = $1
            """,
            user_id,
        )

        if row is None:
            return None

        return StudentProfileRecord(
            id=row["id"],
            user_id=row["user_id"],
            registration_number=row["registration_number"],
            first_name=row["first_name"],
            middle_name=row["middle_name"],
            last_name=row["last_name"],
            profile_status=row["profile_status"],
            university_email=row["university_email"],
        )
