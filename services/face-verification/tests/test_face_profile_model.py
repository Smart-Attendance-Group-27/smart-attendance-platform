from sqlalchemy import CheckConstraint, Integer, LargeBinary, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY

from models.face_profile import FaceProfile


def test_face_profile_maps_to_expected_table() -> None:
    table = FaceProfile.__table__

    assert table.schema == "face_verification"
    assert table.name == "face_profiles"
    assert set(table.columns.keys()) == {
        "id",
        "student_id",
        "embedding_encrypted",
        "embedding_model_name",
        "embedding_model_version",
        "embedding_dimension",
        "embedding_generation_status",
        "generated_at",
        "created_at",
        "updated_at",
        "readiness_status",
        "readiness_checked_at",
        "readiness_config_id",
    }


def test_face_profile_column_requirements_match_migrations() -> None:
    table = FaceProfile.__table__

    assert table.c.id.primary_key is True
    assert table.c.student_id.nullable is False
    assert isinstance(table.c.embedding_encrypted.type, LargeBinary)
    assert table.c.embedding_encrypted.nullable is True
    assert table.c.embedding_model_name.nullable is True
    assert table.c.embedding_model_version.nullable is True
    assert isinstance(table.c.embedding_dimension.type, Integer)
    assert table.c.embedding_dimension.nullable is True
    assert table.c.embedding_generation_status.nullable is False
    assert table.c.readiness_status.nullable is False
    assert table.c.readiness_config_id.nullable is True


def test_face_profile_constraints_and_index_match_migrations() -> None:
    table = FaceProfile.__table__
    constraint_names = {
        constraint.name
        for constraint in table.constraints
        if isinstance(constraint, (CheckConstraint, UniqueConstraint))
    }
    index_names = {index.name for index in table.indexes}

    assert constraint_names == {
        "uq_face_profiles_student_id",
        "chk_face_profile_generation_status",
        "chk_generated_profile_has_encrypted_embedding",
        "chk_face_profiles_readiness_status",
        "chk_passed_readiness_has_details",
        "chk_face_profiles_embedding_dimension",
    }
    assert index_names == {"idx_face_profiles_generation_status"}


def test_face_profile_foreign_keys_match_migrations() -> None:
    table = FaceProfile.__table__
    foreign_keys = {
        foreign_key.name: foreign_key.target_fullname
        for foreign_key in table.foreign_keys
    }

    assert foreign_keys == {
        "fk_face_profiles_student": "academic.student_profiles.id",
        "fk_face_profiles_readiness_config": (
            "face_verification.verification_configs.id"
        ),
    }
