from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    SmallInteger,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class FaceValidationAttempt(Base):
    __tablename__ = "face_validation_attempts"
    __table_args__ = (
        UniqueConstraint(
            "verification_attempt_id",
            "attempt_number",
            name="uq_face_attempts_verification_number",
        ),
        CheckConstraint(
            "attempt_number > 0",
            name="chk_face_attempt_number_positive",
        ),
        CheckConstraint(
            "similarity_score IS NULL "
            "OR similarity_score BETWEEN -1 AND 1",
            name="chk_face_similarity_score_range",
        ),
        CheckConstraint(
            "validation_status IN ('pending', 'passed', 'failed')",
            name="chk_face_validation_status",
        ),
        CheckConstraint(
            "validation_status <> 'passed' "
            "OR (liveness_passed = true "
            "AND quality_passed = true "
            "AND similarity_score IS NOT NULL "
            "AND validated_at IS NOT NULL)",
            name="chk_passed_face_attempt",
        ),
        CheckConstraint(
            "validation_status <> 'failed' "
            "OR (failure_reason IS NOT NULL "
            "AND validated_at IS NOT NULL)",
            name="chk_failed_face_attempt",
        ),
        Index("idx_face_attempts_profile", "face_profile_id"),
        Index("idx_face_attempts_config", "verification_config_id"),
        Index("idx_face_attempts_status", "validation_status"),
        {"schema": "face_verification"},
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    verification_attempt_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "attendance_verification.verification_attempts.id",
            name="fk_face_attempts_verification_attempt",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    face_profile_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "face_verification.face_profiles.id",
            name="fk_face_attempts_face_profile",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    attempt_number: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
    )
    liveness_passed: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
    )
    quality_passed: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
    )
    similarity_score: Mapped[Decimal | None] = mapped_column(
        Numeric(8, 7),
        nullable=True,
    )
    verification_config_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "face_verification.verification_configs.id",
            name="fk_face_attempts_verification_config",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    validation_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'pending'"),
    )
    failure_reason: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    validated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
