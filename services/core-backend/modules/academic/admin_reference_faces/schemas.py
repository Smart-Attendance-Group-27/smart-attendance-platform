from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from modules.academic.admin_reference_faces.repository import ReferenceFaceRecord

NOT_CHECKED_STATUS = "not_checked"


def derive_readiness_status(record: ReferenceFaceRecord) -> str:
    """No dedicated readiness table exists — this reads the outcome of the
    most recent live face_validation_attempts row for the student's profile,
    since that is the only real signal this schema has for "would this
    student's reference face currently pass a check"."""
    if record.latest_attempt_status is None:
        return NOT_CHECKED_STATUS
    return record.latest_attempt_status


class ReferenceFaceResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    student_id: UUID = Field(alias="studentId")
    student_name: str = Field(alias="studentName")
    registration_number: str = Field(alias="registrationNumber")
    embedding_generation_status: str = Field(alias="embeddingGenerationStatus")
    readiness_status: str = Field(alias="readinessStatus")
    generated_at: datetime | None = Field(alias="generatedAt")
    readiness_checked_at: datetime | None = Field(alias="readinessCheckedAt")

    @staticmethod
    def from_record(record: ReferenceFaceRecord) -> "ReferenceFaceResponse":
        return ReferenceFaceResponse(
            student_id=record.student_id,
            student_name=record.full_name,
            registration_number=record.registration_number or "",
            embedding_generation_status=record.embedding_generation_status or "pending",
            readiness_status=derive_readiness_status(record),
            generated_at=record.generated_at,
            readiness_checked_at=record.latest_attempt_validated_at,
        )
