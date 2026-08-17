import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from models.verification_config import VerificationConfig
from repositories.verification_config_repository import (
    VerificationConfigRepository,
)


def create_session() -> AsyncMock:
    return AsyncMock(spec=AsyncSession)


def test_gets_verification_config_by_id() -> None:
    session = create_session()
    config_id = uuid4()
    config = MagicMock(spec=VerificationConfig)
    session.get.return_value = config
    repository = VerificationConfigRepository(session)

    result = asyncio.run(repository.get_by_id(config_id))

    assert result is config
    session.get.assert_awaited_once_with(VerificationConfig, config_id)
    session.commit.assert_not_awaited()


def test_gets_active_verification_config() -> None:
    session = create_session()
    query_result = MagicMock()
    config = MagicMock(spec=VerificationConfig)
    query_result.scalar_one_or_none.return_value = config
    session.execute.return_value = query_result
    repository = VerificationConfigRepository(session)

    result = asyncio.run(repository.get_active())

    assert result is config
    session.execute.assert_awaited_once()
    session.commit.assert_not_awaited()


def test_creates_inactive_verification_config() -> None:
    session = create_session()
    configured_by = uuid4()

    effective_from = datetime.now(timezone.utc)
    repository = VerificationConfigRepository(session)

    config = asyncio.run(
        repository.create_config(
            similarity_threshold=Decimal("0.65000"),
            configured_by=configured_by,
            effective_from=effective_from,
        )
    )

    assert config.similarity_threshold == Decimal("0.65000")
    assert config.configured_by == configured_by
    assert config.effective_from == effective_from
    assert config.is_active is False

    session.add.assert_called_once_with(config)
    session.flush.assert_awaited_once_with()
    session.commit.assert_not_awaited()


@pytest.mark.parametrize(
    "threshold",
    [Decimal("-0.00001"), Decimal("1.00001")],
)
def test_rejects_out_of_range_threshold(threshold: Decimal) -> None:
    session = create_session()
    repository = VerificationConfigRepository(session)

    with pytest.raises(ValueError, match="Similarity threshold must be between 0 and 1",):
        asyncio.run(
            repository.create_config(
                similarity_threshold=threshold,
                configured_by=uuid4(),
            )
        )

    session.add.assert_not_called()
    session.flush.assert_not_awaited()


def test_activate_config_returns_none_when_config_is_missing() -> None:
    session = create_session()
    session.get.return_value = None
    repository = VerificationConfigRepository(session)

    result = asyncio.run(repository.activate_config(uuid4()))

    assert result is None
    session.execute.assert_not_awaited()
    session.commit.assert_not_awaited()


def test_activates_selected_config_after_deactivating_current() -> None:
    session = create_session()
    config_id = uuid4()
    config = MagicMock(spec=VerificationConfig)
    session.get.return_value = config
    deactivate_result = MagicMock()
    activate_result = MagicMock()
    activate_result.scalar_one_or_none.return_value = config
    session.execute.side_effect = [deactivate_result, activate_result]
    repository = VerificationConfigRepository(session)

    result = asyncio.run(
        repository.activate_config(
            config_id,
            effective_from=datetime.now(timezone.utc),
        )
    )

    assert result is config
    assert session.execute.await_count == 2
    session.commit.assert_not_awaited()
