from collections.abc import Sequence
from datetime import datetime
from typing import Literal
from uuid import UUID
from dataclasses import dataclass
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
from core.embedding_crypto import EmbeddingCrypto
from models.face_profile import FaceProfile


ReadinessStatus = Literal[
    "not_checked",
    "passed",
    "failed",
    "expired",
]

@dataclass(frozen=True, slots=True)
class StoredFaceEmbedding:
    profile_id: UUID
    student_id: UUID
    embedding: tuple[float, ...]
    model_name: str
    model_version: str
    dimension: int

class FaceProfileRepository:
    def __init__(self, session: AsyncSession, *, embedding_crypto: EmbeddingCrypto | None = None,) -> None:
        self._session = session

        self._embedding_crypto = embedding_crypto or EmbeddingCrypto(get_settings().face_embedding_encryption_key.get_secret_value())

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

    async def save_generated_embedding(
        self,
        profile_id: UUID,
        embedding: Sequence[float],
        *,
        model_name: str,
        model_version: str,
        generated_at: datetime | None = None,
    ) -> FaceProfile | None:
        
        embedding_values = [float(value) for value in embedding]

        if not embedding_values:
            raise ValueError("Embedding must contain at least one value")

        normalized_model_name = model_name.strip()

        if not normalized_model_name:
            raise ValueError("Model name cannot be blank")

        selected_model_version = model_version.strip()
        
        if not selected_model_version:
            raise ValueError("Model version cannot be blank")

        encrypted_embedding = self._embedding_crypto.encrypt(embedding_values)

        statement = (update(FaceProfile).where(FaceProfile.id == profile_id)
            .values(
                embedding_encrypted=encrypted_embedding,
                embedding_model_name=normalized_model_name,
                embedding_model_version=selected_model_version,
                embedding_dimension=len(embedding_values),
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
                embedding_encrypted=None,
                embedding_model_name=None,
                embedding_model_version=None,
                embedding_dimension=None,
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

    async def get_stored_embedding_for_comparison(self,student_id: UUID,) -> StoredFaceEmbedding | None:

        profile = await self.get_by_student_id(student_id)

        if profile is None:
            return None

        if profile.embedding_generation_status != "generated":
            return None

        if profile.embedding_encrypted is None:
            raise ValueError("Generated profile is missing encrypted embedding data")

        if not profile.embedding_model_name:
            raise ValueError("Generated profile is missing model name")

        if not profile.embedding_model_version:
            raise ValueError("Generated profile is missing model version")

        if profile.embedding_dimension is None or profile.embedding_dimension <= 0:
            raise ValueError("Generated profile has an invalid embedding dimension")

        embedding = self._embedding_crypto.decrypt(profile.embedding_encrypted)

        if len(embedding) != profile.embedding_dimension:
            raise ValueError("Decrypted embedding dimension does not match stored metadata")

        return StoredFaceEmbedding(
            profile_id=profile.id,
            student_id=profile.student_id,
            embedding=embedding,
            model_name=profile.embedding_model_name,
            model_version=profile.embedding_model_version,
            dimension=profile.embedding_dimension,
        )
