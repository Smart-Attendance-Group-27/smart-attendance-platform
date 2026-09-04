import asyncio
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from models.verification_config import VerificationConfig
from repositories.verification_config_repository import (
    VerificationConfigRepository,
)
from scripts.activate_verification_config import (
    ActivationTargetError,
    activate_existing,
    create_and_activate,
)


def make_config(*, config_id, threshold: Decimal) -> MagicMock:
    config = MagicMock(spec=VerificationConfig)
    config.id = config_id
    config.similarity_threshold = threshold
    return config


def create_repository() -> tuple[VerificationConfigRepository, AsyncMock]:
    session = AsyncMock()
    return VerificationConfigRepository(session), session


def test_activate_existing_dry_run_does_not_write() -> None:
    repository, session = create_repository()
    config_id = uuid4()
    existing = make_config(config_id=config_id, threshold=Decimal("0.65000"))
    repository.get_by_id = AsyncMock(return_value=existing)
    repository.get_active = AsyncMock(return_value=None)
    repository.activate_config = AsyncMock()

    outcome = asyncio.run(
        activate_existing(repository, config_id=config_id, commit=False)
    )

    assert outcome.applied is False
    assert outcome.config_id == config_id
    assert outcome.similarity_threshold == Decimal("0.65000")
    repository.activate_config.assert_not_called()
    session.commit.assert_not_awaited()


def test_activate_existing_commit_activates_only_the_selected_config() -> None:
    repository, session = create_repository()
    config_id = uuid4()
    other_active_id = uuid4()
    existing = make_config(config_id=config_id, threshold=Decimal("0.50000"))
    currently_active = make_config(config_id=other_active_id, threshold=Decimal("0.40000"))
    activated = make_config(config_id=config_id, threshold=Decimal("0.50000"))

    repository.get_by_id = AsyncMock(return_value=existing)
    repository.get_active = AsyncMock(return_value=currently_active)
    repository.activate_config = AsyncMock(return_value=activated)

    outcome = asyncio.run(
        activate_existing(repository, config_id=config_id, commit=True)
    )

    assert outcome.applied is True
    assert outcome.config_id == config_id
    assert outcome.previously_active_config_id == other_active_id
    repository.activate_config.assert_awaited_once_with(config_id)


def test_activate_existing_rejects_missing_config_id() -> None:
    repository, session = create_repository()
    config_id = uuid4()
    repository.get_by_id = AsyncMock(return_value=None)
    repository.get_active = AsyncMock(return_value=None)
    repository.activate_config = AsyncMock()

    with pytest.raises(ActivationTargetError, match="No verification config exists"):
        asyncio.run(activate_existing(repository, config_id=config_id, commit=True))

    repository.activate_config.assert_not_called()
    session.commit.assert_not_awaited()


def test_activate_existing_is_idempotent_when_already_active() -> None:
    repository, session = create_repository()
    config_id = uuid4()
    existing = make_config(config_id=config_id, threshold=Decimal("0.50000"))

    repository.get_by_id = AsyncMock(return_value=existing)
    repository.get_active = AsyncMock(return_value=existing)
    repository.activate_config = AsyncMock(return_value=existing)

    outcome = asyncio.run(
        activate_existing(repository, config_id=config_id, commit=True)
    )

    assert outcome.previously_active_config_id is None
    repository.activate_config.assert_awaited_once_with(config_id)


def test_create_and_activate_dry_run_does_not_write() -> None:
    repository, session = create_repository()
    repository.get_active = AsyncMock(return_value=None)
    repository.create_config = AsyncMock()
    repository.activate_config = AsyncMock()

    outcome = asyncio.run(
        create_and_activate(
            repository,
            similarity_threshold=Decimal("0.55"),
            configured_by=uuid4(),
            commit=False,
        )
    )

    assert outcome.applied is False
    repository.create_config.assert_not_called()
    repository.activate_config.assert_not_called()


def test_create_and_activate_commit_creates_then_activates() -> None:
    repository, session = create_repository()
    configured_by = uuid4()
    created_id = uuid4()
    created = make_config(config_id=created_id, threshold=Decimal("0.55"))
    activated = make_config(config_id=created_id, threshold=Decimal("0.55"))

    repository.get_active = AsyncMock(return_value=None)
    repository.create_config = AsyncMock(return_value=created)
    repository.activate_config = AsyncMock(return_value=activated)

    outcome = asyncio.run(
        create_and_activate(
            repository,
            similarity_threshold=Decimal("0.55"),
            configured_by=configured_by,
            commit=True,
        )
    )

    assert outcome.applied is True
    assert outcome.config_id == created_id
    repository.create_config.assert_awaited_once_with(
        similarity_threshold=Decimal("0.55"),
        configured_by=configured_by,
    )
    repository.activate_config.assert_awaited_once_with(created_id)


@pytest.mark.parametrize("threshold", [Decimal("-0.01"), Decimal("1.01")])
def test_create_and_activate_rejects_invalid_threshold_before_touching_db(
    threshold: Decimal,
) -> None:
    repository, session = create_repository()
    repository.get_active = AsyncMock(return_value=None)
    repository.create_config = AsyncMock()
    repository.activate_config = AsyncMock()

    with pytest.raises(ValueError, match="Similarity threshold must be between 0 and 1"):
        asyncio.run(
            create_and_activate(
                repository,
                similarity_threshold=threshold,
                configured_by=uuid4(),
                commit=True,
            )
        )

    repository.create_config.assert_not_called()
    repository.activate_config.assert_not_called()
