from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

import asyncpg


@dataclass(frozen=True)
class ReferenceFaceRecord:
    student_id: UUID
    registration_number: str | None
    full_name: str
    embedding_generation_status: str | None
    generated_at: datetime | None
    latest_attempt_status: str | None
    latest_attempt_validated_at: datetime | None


class AdminReferenceFaceRepository:
    async def list_reference_faces(
        self,
        connection: asyncpg.Connection,
    ) -> list[ReferenceFaceRecord]:
        # Never selects face_profiles.embedding — administrators govern
        # generation/readiness status only, never the raw biometric vector.
        rows = await connection.fetch(
            """
            SELECT
                student.id AS student_id,
                student.registration_number,
                TRIM(
                    CONCAT_WS(' ', student.first_name, NULLIF(student.middle_name, ''), student.last_name)
                ) AS full_name,
                profile.embedding_generation_status,
                profile.generated_at,
                latest_attempt.validation_status AS latest_attempt_status,
                latest_attempt.validated_at AS latest_attempt_validated_at
            FROM academic.student_profiles AS student
            LEFT JOIN face_verification.face_profiles AS profile
                ON profile.student_id = student.id
            LEFT JOIN LATERAL (
                SELECT attempt.validation_status, attempt.validated_at
                FROM face_verification.face_validation_attempts AS attempt
                WHERE attempt.face_profile_id = profile.id
                ORDER BY attempt.validated_at DESC NULLS LAST, attempt.attempt_number DESC
                LIMIT 1
            ) AS latest_attempt ON profile.id IS NOT NULL
            WHERE student.profile_status = 'active'
            ORDER BY student.registration_number ASC
            """,
        )
        return [
            ReferenceFaceRecord(
                student_id=row["student_id"],
                registration_number=row["registration_number"],
                full_name=row["full_name"] or "",
                embedding_generation_status=row["embedding_generation_status"],
                generated_at=row["generated_at"],
                latest_attempt_status=row["latest_attempt_status"],
                latest_attempt_validated_at=row["latest_attempt_validated_at"],
            )
            for row in rows
        ]
