from collections.abc import Sequence
from datetime import datetime
from typing import Literal
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from models.face_profile import FaceProfile


ReadinessStatus = Literal[
    "not_checked",
    "passed",
    "failed",
    "expired",
]


class FaceProfileRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, profile_id: UUID) -> FaceProfile | None:
        return await self._session.get(FaceProfile, profile_id)

    async def get_by_student_id(self, student_id: UUID,) -> FaceProfile | None:
        statement = select(FaceProfile).where(FaceProfile.student_id == student_id)
        result = await self._session.execute(statement)

        return result.scalar_one_or_none()

    async def create_pending_profile(self, student_id: UUID,) -> FaceProfile:
        profile = FaceProfile(student_id=student_id, embedding_generation_status="pending", readiness_status="not_checked",)

        self._session.add(profile)
        await self._session.flush()

        return profile

    async def save_generated_embedding(self, profile_id: UUID, embedding: Sequence[float], *, generated_at: datetime | None = None,) -> FaceProfile | None:
        embedding_values = [float(value) for value in embedding]

        if not embedding_values:
            raise ValueError("Embedding must contain at least one value")

        statement = (update(FaceProfile).where(FaceProfile.id == profile_id)
            .values(
                embedding=embedding_values,
                embedding_generation_status="generated",
                generated_at=generated_at or func.now(),
                updated_at=func.now(),
            )
            .returning(FaceProfile)
        )

        result = await self._session.execute(statement)

        return result.scalar_one_or_none()

    async def mark_generation_failed(self, profile_id: UUID,) -> FaceProfile | None:
        statement = (update(FaceProfile).where(FaceProfile.id == profile_id)
            .values(
                embedding=None,
                embedding_generation_status="failed",
                generated_at=None,
                updated_at=func.now(),
            )
            .returning(FaceProfile)
        )
        result = await self._session.execute(statement)

        return result.scalar_one_or_none()

    async def update_readiness_result(self, profile_id: UUID, *, status: ReadinessStatus, verification_config_id: UUID | None, checked_at: datetime | None,) -> FaceProfile | None:
        statement = ( update(FaceProfile).where(FaceProfile.id == profile_id)
            .values(
                readiness_status=status,
                readiness_config_id=verification_config_id,
                readiness_checked_at=checked_at,
                updated_at=func.now(),
            )
            .returning(FaceProfile)
        )
        result = await self._session.execute(statement)

        return result.scalar_one_or_none()
