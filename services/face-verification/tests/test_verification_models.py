from sqlalchemy import CheckConstraint, UniqueConstraint
from sqlalchemy.sql.schema import Index

from models.face_validation_attempt import FaceValidationAttempt
from models.verification_config import VerificationConfig


def constraint_names(model: type) -> set[str | None]:
    return {
        constraint.name
        for constraint in model.__table__.constraints
        if isinstance(constraint, (CheckConstraint, UniqueConstraint))
    }


def index_names(model: type) -> set[str | None]:
    return {
        index.name
        for index in model.__table__.indexes
        if isinstance(index, Index)
    }


def test_verification_config_maps_to_expected_table() -> None:
    table = VerificationConfig.__table__

    assert table.schema == "face_verification"
    assert table.name == "verification_configs"
    assert set(table.columns.keys()) == {
        "id",
        "similarity_threshold",
        "is_active",
        "configured_by",
        "effective_from",
        "created_at",
    }
    assert table.c.similarity_threshold.type.precision == 6
    assert table.c.similarity_threshold.type.scale == 5
    assert table.c.is_active.nullable is False


def test_verification_config_constraints_and_index_match_migration() -> None:
    table = VerificationConfig.__table__
    active_index = next(iter(table.indexes))

    assert constraint_names(VerificationConfig) == {
        "chk_similarity_threshold_range"
    }
    assert active_index.name == "uq_verification_configs_one_active"
    assert active_index.unique is True
    assert str(active_index.dialect_options["postgresql"]["where"]) == (
        "is_active = true"
    )


def test_verification_config_foreign_key_matches_migration() -> None:
    foreign_key = next(iter(VerificationConfig.__table__.foreign_keys))

    assert foreign_key.name == "fk_verification_configs_configured_by"
    assert foreign_key.target_fullname == "identity.users.id"
    assert foreign_key.ondelete == "RESTRICT"


def test_face_validation_attempt_maps_to_expected_table() -> None:
    table = FaceValidationAttempt.__table__

    assert table.schema == "face_verification"
    assert table.name == "face_validation_attempts"
    assert set(table.columns.keys()) == {
        "id",
        "verification_attempt_id",
        "face_profile_id",
        "attempt_number",
        "liveness_passed",
        "quality_passed",
        "similarity_score",
        "verification_config_id",
        "validation_status",
        "failure_reason",
        "captured_at",
        "validated_at",
    }
    assert table.c.similarity_score.type.precision == 8
    assert table.c.similarity_score.type.scale == 7


def test_face_validation_attempt_constraints_and_indexes_match_migration() -> None:
    assert constraint_names(FaceValidationAttempt) == {
        "uq_face_attempts_verification_number",
        "chk_face_attempt_number_positive",
        "chk_face_similarity_score_range",
        "chk_face_validation_status",
        "chk_passed_face_attempt",
        "chk_failed_face_attempt",
    }
    assert index_names(FaceValidationAttempt) == {
        "idx_face_attempts_profile",
        "idx_face_attempts_config",
        "idx_face_attempts_status",
    }


def test_face_validation_attempt_foreign_keys_match_migration() -> None:
    foreign_keys = {
        foreign_key.name: (
            foreign_key.target_fullname,
            foreign_key.ondelete,
        )
        for foreign_key in FaceValidationAttempt.__table__.foreign_keys
    }

    assert foreign_keys == {
        "fk_face_attempts_verification_attempt": (
            "attendance_verification.verification_attempts.id",
            "RESTRICT",
        ),
        "fk_face_attempts_face_profile": (
            "face_verification.face_profiles.id",
            "RESTRICT",
        ),
        "fk_face_attempts_verification_config": (
            "face_verification.verification_configs.id",
            "RESTRICT",
        ),
    }
