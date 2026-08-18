from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from services.readiness_verification_service import (
    ReadinessProfileStatus,
    ReadinessVerificationStatus,
)


class ReadinessVerificationResponse(BaseModel):
    status: ReadinessVerificationStatus
    message: str


class ReadinessStatusResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    status: ReadinessProfileStatus
    requires_readiness_check: bool = Field(alias="requiresReadinessCheck")
    checked_at: datetime | None = Field(alias="checkedAt")
