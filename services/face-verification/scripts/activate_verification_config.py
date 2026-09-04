import argparse
import asyncio
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from uuid import UUID

from core.config import get_settings
from db.engine import create_database_engine, dispose_database_engine
from db.session import create_session_factory
from repositories.verification_config_repository import (
    VerificationConfigRepository,
)

DEVELOPMENT_THRESHOLD_NOTICE = (
    "NOTICE: the activated threshold is a development/demo configuration. "
    "It must be calibrated against real evaluation data before production use."
)


@dataclass(frozen=True, slots=True)
class ActivationOutcome:
    config_id: UUID
    similarity_threshold: Decimal
    previously_active_config_id: UUID | None
    applied: bool


class ActivationTargetError(ValueError):
    """Raised when the requested config to activate does not exist."""


async def activate_existing(
    repository: VerificationConfigRepository,
    *,
    config_id: UUID,
    commit: bool,
) -> ActivationOutcome:
    """Activate an already-existing config by id.

    Uses VerificationConfigRepository.activate_config, which atomically
    deactivates whatever config is currently active before activating this
    one (also enforced by a DB partial-unique index on is_active), so at
    most one config is ever active.
    """

    target = await repository.get_by_id(config_id)
    if target is None:
        raise ActivationTargetError(f"No verification config exists with id={config_id}")

    previously_active = await repository.get_active()
    previously_active_id = (
        previously_active.id
        if previously_active is not None and previously_active.id != config_id
        else None
    )

    if not commit:
        return ActivationOutcome(
            config_id=target.id,
            similarity_threshold=target.similarity_threshold,
            previously_active_config_id=previously_active_id,
            applied=False,
        )

    activated = await repository.activate_config(config_id)
    if activated is None:
        raise ActivationTargetError(f"Config {config_id} disappeared during activation")

    return ActivationOutcome(
        config_id=activated.id,
        similarity_threshold=activated.similarity_threshold,
        previously_active_config_id=previously_active_id,
        applied=True,
    )


async def create_and_activate(
    repository: VerificationConfigRepository,
    *,
    similarity_threshold: Decimal,
    configured_by: UUID,
    commit: bool,
) -> ActivationOutcome:
    """Create a brand-new config row (always inserted inactive, per
    VerificationConfigRepository.create_config) and then activate it."""

    if not Decimal("0") <= similarity_threshold <= Decimal("1"):
        raise ValueError("Similarity threshold must be between 0 and 1")

    previously_active = await repository.get_active()
    previously_active_id = previously_active.id if previously_active is not None else None

    if not commit:
        return ActivationOutcome(
            config_id=UUID(int=0),
            similarity_threshold=similarity_threshold,
            previously_active_config_id=previously_active_id,
            applied=False,
        )

    created = await repository.create_config(
        similarity_threshold=similarity_threshold,
        configured_by=configured_by,
    )
    activated = await repository.activate_config(created.id)
    if activated is None:
        raise ActivationTargetError(
            f"Newly created config {created.id} disappeared during activation"
        )

    return ActivationOutcome(
        config_id=activated.id,
        similarity_threshold=activated.similarity_threshold,
        previously_active_config_id=previously_active_id,
        applied=True,
    )


async def run(arguments: argparse.Namespace) -> ActivationOutcome:
    settings = get_settings()
    database_engine = create_database_engine(settings)
    session_factory = create_session_factory(database_engine)

    try:
        async with session_factory() as session:
            repository = VerificationConfigRepository(session)

            if arguments.create:
                outcome = await create_and_activate(
                    repository,
                    similarity_threshold=arguments.threshold,
                    configured_by=arguments.configured_by,
                    commit=arguments.commit,
                )
            else:
                outcome = await activate_existing(
                    repository,
                    config_id=arguments.config_id,
                    commit=arguments.commit,
                )

            if arguments.commit:
                await session.commit()

            return outcome
    finally:
        await dispose_database_engine(database_engine)


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Activate a face-verification similarity-threshold configuration. "
            "Exactly one configuration may be active at a time (enforced by "
            "a database partial-unique index). The default mode performs no writes."
        )
    )
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument(
        "--config-id",
        type=UUID,
        help="Activate an existing verification_configs row by id.",
    )
    target.add_argument(
        "--create",
        action="store_true",
        help="Create a new inactive config with --threshold and --configured-by, then activate it.",
    )

    parser.add_argument(
        "--threshold",
        type=Decimal,
        help="Similarity threshold (0-1) for --create. Required with --create.",
    )
    parser.add_argument(
        "--configured-by",
        type=UUID,
        help="identity.users.id of the administrator configuring this threshold. Required with --create.",
    )
    parser.add_argument(
        "--commit",
        action="store_true",
        help="Perform the activation; without this flag, dry-run only.",
    )
    return parser


def print_outcome(outcome: ActivationOutcome, *, commit: bool) -> None:
    mode = "COMMIT" if commit else "DRY RUN"
    print()
    print(f"Verification config activation ({mode})")
    print(f"  Config id:              {outcome.config_id}")
    print(f"  Similarity threshold:   {outcome.similarity_threshold}")
    print(f"  Previously active:      {outcome.previously_active_config_id or '(none)'}")
    if commit:
        print()
        print(DEVELOPMENT_THRESHOLD_NOTICE)


def main() -> int:
    parser = build_argument_parser()
    arguments = parser.parse_args()

    if arguments.create and arguments.threshold is None:
        parser.error("--create requires --threshold")
    if arguments.create and arguments.configured_by is None:
        parser.error("--create requires --configured-by")

    try:
        outcome = asyncio.run(run(arguments))
    except (ActivationTargetError, ValueError, InvalidOperation) as error:
        parser.exit(1, f"Activation failed: {error}\n")

    print_outcome(outcome, commit=arguments.commit)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
