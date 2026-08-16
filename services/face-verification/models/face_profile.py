from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class FaceProfile(Base):
    __tablename__ = "face_profiles"
    __table_args__ = (
        UniqueConstraint(
            "student_id",
            name="uq_face_profiles_student_id",
        ),
        CheckConstraint(
            "embedding_generation_status IN "
            "('pending', 'generated', 'failed', 'revoked')",
            name="chk_face_profile_generation_status",
        ),
        CheckConstraint(
            "embedding_generation_status <> 'generated' "
            "OR (embedding_encrypted IS NOT NULL "
            "AND octet_length(embedding_encrypted) > 0 "
            "AND embedding_model_name IS NOT NULL "
            "AND length(trim(embedding_model_name)) > 0 "
            "AND embedding_model_version IS NOT NULL "
            "AND length(trim(embedding_model_version)) > 0 "
            "AND embedding_dimension IS NOT NULL "
            "AND embedding_dimension > 0 "
            "AND generated_at IS NOT NULL)",
            name="chk_generated_profile_has_encrypted_embedding",
        ),
        CheckConstraint(
            "readiness_status IN "
            "('not_checked', 'passed', 'failed', 'expired')",
            name="chk_face_profiles_readiness_status",
        ),
        CheckConstraint(
            "readiness_status <> 'passed' "
            "OR (readiness_checked_at IS NOT NULL "
            "AND readiness_config_id IS NOT NULL)",
            name="chk_passed_readiness_has_details",
        ),
        CheckConstraint(
            "embedding_dimension IS NULL OR embedding_dimension > 0",
            name="chk_face_profiles_embedding_dimension",
        ),
        
        Index(
            "idx_face_profiles_generation_status",
            "embedding_generation_status",
        ),
        {"schema": "face_verification"},
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    student_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "academic.student_profiles.id",
            name="fk_face_profiles_student",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    embedding_encrypted: Mapped[bytes | None] = mapped_column(
            LargeBinary,       
            nullable=True,
    )

    embedding_model_name: Mapped[str| None] = mapped_column(
        String(100),
        nullable=True,
    )

    embedding_model_version: Mapped[str| None] = mapped_column(
        String(50),
        nullable=True,
    )

    embedding_dimension: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    embedding_generation_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'pending'"),
    )
    generated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    readiness_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'not_checked'"),
    )
    readiness_checked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    readiness_config_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "face_verification.verification_configs.id",
            name="fk_face_profiles_readiness_config",
            ondelete="RESTRICT",
        ),
        nullable=True,
    )
