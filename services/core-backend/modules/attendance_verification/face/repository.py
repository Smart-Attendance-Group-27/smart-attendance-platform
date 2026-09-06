from uuid import UUID

import asyncpg


class AttendanceFaceProgressRepository:
    async def has_passed(
        self,
        pool: asyncpg.Pool,
        *,
        user_id: UUID,
        session_id: UUID,
    ) -> bool:
        async with pool.acquire() as connection:
            value = await connection.fetchval(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM academic.student_profiles AS student
                    JOIN attendance_verification.verification_attempts AS attempt
                      ON attempt.student_id = student.id
                    JOIN face_verification.face_validation_attempts AS face
                      ON face.verification_attempt_id = attempt.id
                    WHERE student.user_id = $1
                      AND student.profile_status = 'active'
                      AND attempt.session_id = $2
                      AND face.validation_status = 'passed'
                )
                """,
                user_id,
                session_id,
            )
        return bool(value)


__all__ = ["AttendanceFaceProgressRepository"]
