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
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class VerificationConfig(Base):
    __tablename__ = "verification_configs"
    __table_args__ = (
        CheckConstraint(
            "similarity_threshold >= 0 "
            "AND similarity_threshold <= 1",
            name="chk_similarity_threshold_range",
        ),
        Index(
            "uq_verification_configs_one_active",
            "is_active",
            unique=True,
            postgresql_where=text("is_active = true"),
        ),
        {"schema": "face_verification"},
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    similarity_threshold: Mapped[Decimal] = mapped_column(
        Numeric(6, 5),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
    )
    configured_by: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "identity.users.id",
            name="fk_verification_configs_configured_by",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    effective_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
