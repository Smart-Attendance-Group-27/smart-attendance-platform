from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from models.verification_config import VerificationConfig


class VerificationConfigRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, config_id: UUID,) -> VerificationConfig | None:
        return await self._session.get(VerificationConfig, config_id)

    async def get_active(self) -> VerificationConfig | None:
        statement = select(VerificationConfig).where(VerificationConfig.is_active.is_(True))
        result = await self._session.execute(statement)

        return result.scalar_one_or_none()

    async def create_config(self, *, similarity_threshold: Decimal, configured_by: UUID, effective_from: datetime | None = None,) -> VerificationConfig:
        if not Decimal("0") <= similarity_threshold <= Decimal("1"):
            raise ValueError("Similarity threshold must be between 0 and 1")

        config = VerificationConfig(
            similarity_threshold=similarity_threshold,
            configured_by=configured_by,
            is_active=False,
        )

        if effective_from is not None:
            config.effective_from = effective_from

        self._session.add(config)
        await self._session.flush()

        return config

    async def activate_config(self, config_id: UUID, *, effective_from: datetime | None = None,) -> VerificationConfig | None:
        config = await self.get_by_id(config_id)

        if config is None:
            return None

        deactivate_current = (
            update(VerificationConfig).where(VerificationConfig.is_active.is_(True),VerificationConfig.id != config_id,)
            .values(is_active=False)
        )
        await self._session.execute(deactivate_current)

        activate_selected = (
            update(VerificationConfig).where(VerificationConfig.id == config_id)
            .values(is_active=True, effective_from=effective_from or func.now(),)
            .returning(VerificationConfig)
        )
        result = await self._session.execute(activate_selected)

        return result.scalar_one_or_none()
